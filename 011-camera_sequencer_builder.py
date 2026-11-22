"""
Camera Sequencer Builder - Maya 2025 / Python 3

Builds Camera Sequencer shots from selected cameras, checks the whole
transform hierarchy for non-unit scale (the usual cause of
"Cannot create ubercam. Transform of `cam' has been scaled."),
fixes the scale automatically, and optionally creates the ubercam.

Shot ranges are taken from each camera's own keyframe range.
Falls back to the playback range when a camera has no keys.

Warning
    Fix Scale hard-resets scale to 1. If the framing was set up using scale,
    the composition will change - run Check Scale first.

Usage:
    import camera_sequencer_builder as csb
    csb.show_camera_sequencer_builder_ui()

    # or headless
    csb.check_camera_scale()                 # report only
    csb.fix_camera_scale()                   # force scale back to 1
    csb.build_shots_from_cameras(create_ubercam=True)
"""

import maya.cmds as cmds
import maya.mel as mel

TOL = 1e-5
SCALE_ATTRS = ("scaleX", "scaleY", "scaleZ")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _selected_cameras(objects=None):
    """Return camera transforms (full paths) from objects or the selection."""
    if objects is None:
        objects = cmds.ls(selection=True, long=True) or []
    elif isinstance(objects, str):
        objects = [objects]

    cams = []
    for obj in objects:
        if not cmds.objExists(obj):
            continue
        node = cmds.ls(obj, long=True)[0]
        if cmds.nodeType(node) == "camera":
            parents = cmds.listRelatives(node, parent=True, fullPath=True) or []
            node = parents[0] if parents else node
        shapes = cmds.listRelatives(node, shapes=True, type="camera",
                                    fullPath=True) or []
        if shapes and node not in cams:
            cams.append(node)
    return cams


def _camera_shape(cam_transform):
    shapes = cmds.listRelatives(cam_transform, shapes=True, type="camera",
                                fullPath=True) or []
    return shapes[0] if shapes else None


def _hierarchy_chain(node):
    """Return [node, parent, grandparent, ...] as full paths."""
    chain = []
    current = cmds.ls(node, long=True)[0]
    while current:
        chain.append(current)
        parents = cmds.listRelatives(current, parent=True, fullPath=True)
        current = parents[0] if parents else None
    return chain


def _scale_of(node):
    return cmds.getAttr(node + ".scale")[0]


def _is_scaled(node):
    return any(abs(v - 1.0) > TOL for v in _scale_of(node))


def _short(node):
    return node.split("|")[-1]


# ---------------------------------------------------------------------------
# scale check / fix
# ---------------------------------------------------------------------------

def check_camera_scale(objects=None, verbose=True):
    """Report every scaled transform in each camera's hierarchy.

    Returns {camera_transform: [scaled_node, ...]}.
    """
    cams = _selected_cameras(objects)
    if not cams:
        cmds.warning("[warn] No camera selected.")
        return {}

    result = {}
    for cam in cams:
        bad = [n for n in _hierarchy_chain(cam) if _is_scaled(n)]
        result[cam] = bad
        if verbose:
            if bad:
                print("[fail] %s - scaled node(s) in hierarchy:" % _short(cam))
                for node in bad:
                    sx, sy, sz = _scale_of(node)
                    print("       %s  scale = (%.4f, %.4f, %.4f)"
                          % (node, sx, sy, sz))
            else:
                print("[ok]   %s - hierarchy is unscaled." % _short(cam))
    return result


def fix_camera_scale(objects=None, verbose=True):
    """Force every scaled transform in each camera's hierarchy back to 1.

    Removes scale keys and breaks incoming connections on the scale
    channels first. Locked attributes are skipped with a warning.
    Returns (fixed_nodes, skipped_nodes).
    """
    report = check_camera_scale(objects, verbose=False)
    fixed, skipped = [], []

    for cam, bad_nodes in report.items():
        for node in bad_nodes:
            blocked = []
            for attr in SCALE_ATTRS:
                plug = "%s.%s" % (node, attr)
                if cmds.getAttr(plug, lock=True):
                    blocked.append(attr)
            if blocked:
                skipped.append(node)
                cmds.warning("[skip] %s - locked scale attr(s): %s"
                             % (node, ", ".join(blocked)))
                continue

            for attr in SCALE_ATTRS:
                plug = "%s.%s" % (node, attr)
                cmds.cutKey(plug, clear=True)
                if cmds.listConnections(plug, source=True, destination=False,
                                        plugs=True):
                    cmds.delete(plug, inputConnectionsAndNodes=False,
                                icn=True)
                cmds.setAttr(plug, 1.0)

            fixed.append(node)
            if verbose:
                print("[ok]   %s - scale reset to (1, 1, 1)." % node)

    if verbose:
        print("[info] fix_camera_scale: %d fixed, %d skipped."
              % (len(fixed), len(skipped)))
        if skipped:
            print("[info] Unlock the listed nodes and run again.")
    return fixed, skipped


# ---------------------------------------------------------------------------
# shot building
# ---------------------------------------------------------------------------

def camera_key_range(cam_transform):
    """Return (start, end) from the camera's own animation keys.

    Falls back to the playback range when the camera has no keys.
    """
    nodes = [cam_transform]
    shape = _camera_shape(cam_transform)
    if shape:
        nodes.append(shape)

    times = cmds.keyframe(nodes, query=True, timeChange=True) or []
    if times:
        return float(min(times)), float(max(times))

    return (float(cmds.playbackOptions(query=True, min=True)),
            float(cmds.playbackOptions(query=True, max=True)))


def build_shots_from_cameras(objects=None, auto_fix_scale=True,
                             create_ubercam=False, verbose=True):
    """Create one Camera Sequencer shot per selected camera.

    Shots use each camera's own key range and are laid back-to-back on
    the sequence timeline in selection order.
    """
    cams = _selected_cameras(objects)
    if not cams:
        cmds.warning("[warn] Select at least one camera.")
        return []

    if auto_fix_scale:
        fixed, skipped = fix_camera_scale(cams, verbose=verbose)
        if skipped:
            cmds.warning("[warn] Some transforms are still scaled. "
                         "Ubercam creation will fail.")
    elif verbose:
        check_camera_scale(cams, verbose=True)

    shots = []
    sequence_time = 1.0
    for cam in cams:
        shape = _camera_shape(cam)
        if not shape:
            cmds.warning("[skip] %s has no camera shape." % cam)
            continue

        start, end = camera_key_range(cam)
        if end <= start:
            end = start + 1.0
        duration = end - start

        shot_name = "%s_shot" % _short(cam).split(":")[-1]
        shot = cmds.shot(shot_name,
                         startTime=start,
                         endTime=end,
                         sequenceStartTime=sequence_time,
                         sequenceEndTime=sequence_time + duration,
                         currentCamera=shape)
        shots.append(shot)
        if verbose:
            print("[ok]   shot '%s'  cam=%s  frames %.1f-%.1f  seq %.1f-%.1f"
                  % (shot, _short(cam), start, end,
                     sequence_time, sequence_time + duration))
        sequence_time += duration + 1.0

    if verbose:
        print("[info] Created %d shot(s)." % len(shots))

    if create_ubercam and shots:
        make_ubercam(verbose=verbose)

    return shots


def make_ubercam(verbose=True):
    """Run the Camera Sequencer 'Create Ubercam' command."""
    for command in ('source "ubercam.mel"; createUbercam();',
                    "createUbercam();",
                    "doCreateUbercam();"):
        try:
            mel.eval(command)
            if verbose:
                print("[ok]   Ubercam created.")
            return True
        except RuntimeError:
            continue
    cmds.warning("[fail] Could not run Create Ubercam. Use the Camera "
                 "Sequencer menu: Create > Ubercam.")
    return False


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

WINDOW = "cameraSequencerBuilderWin"


def _ui_check(*args):
    print("--- check scale ---")
    check_camera_scale(verbose=True)


def _ui_fix(*args):
    print("--- fix scale ---")
    fix_camera_scale(verbose=True)


def _ui_build(*args):
    print("--- build shots ---")
    auto_fix = cmds.checkBox("csbAutoFix", query=True, value=True)
    uber = cmds.checkBox("csbUbercam", query=True, value=True)
    build_shots_from_cameras(auto_fix_scale=auto_fix,
                             create_ubercam=uber, verbose=True)


def _ui_ubercam(*args):
    print("--- create ubercam ---")
    make_ubercam(verbose=True)


def show_camera_sequencer_builder_ui():
    if cmds.window(WINDOW, exists=True):
        cmds.deleteUI(WINDOW)

    cmds.window(WINDOW, title="Camera Sequencer Builder",
                widthHeight=(320, 250), sizeable=False)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=6,
                      columnOffset=("both", 10))

    cmds.text(label="", height=2)
    cmds.text(label="Select cameras, then build shots.",
              align="left")
    cmds.text(label="Shot range = each camera's own key range.",
              align="left")
    cmds.separator(height=8, style="in")

    cmds.button(label="Check Scale (report only)",
                height=30, command=_ui_check,
                annotation="List every scaled transform in the camera "
                           "hierarchy without changing anything.")
    cmds.button(label="Fix Scale (reset to 1)",
                height=30, command=_ui_fix,
                annotation="Clear scale keys, break incoming connections "
                           "and set scale back to 1.")

    cmds.separator(height=8, style="in")
    cmds.checkBox("csbAutoFix", label="Auto fix scale before building",
                  value=True)
    cmds.checkBox("csbUbercam", label="Create Ubercam after building",
                  value=False)
    cmds.button(label="Build Shots", height=36, command=_ui_build,
                annotation="Create one shot per selected camera, laid "
                           "back-to-back on the sequence timeline.")

    cmds.separator(height=8, style="in")
    cmds.button(label="Create Ubercam Only", height=28,
                command=_ui_ubercam,
                annotation="Run Create Ubercam on the existing shots.")
    cmds.text(label="", height=4)

    cmds.showWindow(WINDOW)


if __name__ == "__main__":
    show_camera_sequencer_builder_ui()
