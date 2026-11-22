"""Bake evaluated world-space motion onto selected Maya transforms."""

import maya.cmds as cmds


def bake_world_space_to_self(objects=None, start=None, end=None, sample_by=1.0,
                             attributes=None, verbose=True):
    """Bake evaluated motion onto each object's own transform channels.

    Args:
        objects (list[str] | None): Objects to bake. Defaults to current selection.
        start (float | None): First frame. Defaults to playback minimum.
        end (float | None): Last frame. Defaults to playback maximum.
        sample_by (float): Sampling interval in frames; must be greater than zero.
        attributes (list[str] | None): Transform attributes to bake. Defaults to
            translate and rotate channels.
        verbose (bool): Print a concise result report.

    Returns:
        list[str]: Successfully baked object names.
    """
    if objects is None:
        objects = cmds.ls(selection=True, long=True, type="transform") or []
    else:
        resolved = []
        for obj in objects:
            matches = cmds.ls(obj, long=True, type="transform") or []
            if matches:
                resolved.extend(matches)
        objects = list(dict.fromkeys(resolved))

    if not objects:
        if verbose:
            cmds.warning("[fail] Select one or more transform objects to bake.")
        return []

    if sample_by <= 0:
        raise ValueError("sample_by must be greater than zero.")

    if start is None:
        start = cmds.playbackOptions(query=True, minTime=True)
    if end is None:
        end = cmds.playbackOptions(query=True, maxTime=True)
    if end < start:
        raise ValueError("end must be greater than or equal to start.")

    if attributes is None:
        attributes = ["translateX", "translateY", "translateZ",
                      "rotateX", "rotateY", "rotateZ"]

    successful = []
    for obj in objects:
        bake_attrs = []
        for attr in attributes:
            plug = "{}.{}".format(obj, attr)
            if not cmds.objExists(plug):
                continue
            if cmds.getAttr(plug, lock=True):
                if verbose:
                    print("[warn] Skipping locked channel: {}".format(plug))
                continue
            bake_attrs.append(attr)

        if not bake_attrs:
            if verbose:
                print("[skip] No unlocked requested channels: {}".format(obj))
            continue

        try:
            cmds.bakeResults(
                obj,
                time=(start, end),
                sampleBy=sample_by,
                attribute=bake_attrs,
                simulation=True,
                preserveOutsideKeys=True,
                minimizeRotation=True,
                disableImplicitControl=True,
                hierarchy="none",
                controlPoints=False,
                shape=False,
            )
            successful.append(obj)
            if verbose:
                print("[ok] Baked {} from {} to {} by {} frame(s).".format(
                    obj, start, end, sample_by))
        except Exception as exc:
            if verbose:
                print("[fail] Could not bake {}: {}".format(obj, exc))

    return successful


def show_world_space_bake_ui():
    """Show a compact UI for baking the current selection."""
    window_name = "worldSpaceBakeWindow"
    if cmds.window(window_name, exists=True):
        cmds.deleteUI(window_name)

    start_frame = cmds.playbackOptions(query=True, minTime=True)
    end_frame = cmds.playbackOptions(query=True, maxTime=True)

    window = cmds.window(window_name, title="World Space Bake", sizeable=False)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=8, columnOffset=("both", 10))
    cmds.text(label="Bake evaluated motion onto the selected object's own channels.")
    cmds.text(label="Channels to bake")
    translate_check = cmds.checkBox(label="Translate", value=True)
    rotate_check = cmds.checkBox(label="Rotate", value=True)
    cmds.rowLayout(numberOfColumns=2, adjustableColumn=2)
    cmds.text(label="Start frame")
    start_field = cmds.floatField(value=start_frame, precision=2)
    cmds.setParent("..")
    cmds.rowLayout(numberOfColumns=2, adjustableColumn=2)
    cmds.text(label="End frame")
    end_field = cmds.floatField(value=end_frame, precision=2)
    cmds.setParent("..")
    cmds.rowLayout(numberOfColumns=2, adjustableColumn=2)
    cmds.text(label="Sample by")
    sample_field = cmds.floatField(value=1.0, precision=2, minValue=0.01)
    cmds.setParent("..")

    def _run_bake(*_):
        attributes = []
        if cmds.checkBox(translate_check, query=True, value=True):
            attributes.extend(["translateX", "translateY", "translateZ"])
        if cmds.checkBox(rotate_check, query=True, value=True):
            attributes.extend(["rotateX", "rotateY", "rotateZ"])
        if not attributes:
            cmds.warning("[fail] Enable Translate and/or Rotate before baking.")
            return
        bake_world_space_to_self(
            start=cmds.floatField(start_field, query=True, value=True),
            end=cmds.floatField(end_field, query=True, value=True),
            sample_by=cmds.floatField(sample_field, query=True, value=True),
            attributes=attributes,
        )

    cmds.button(label="Bake Selected", command=_run_bake, height=32)
    cmds.showWindow(window)
    return window


if __name__ == "__main__":
    show_world_space_bake_ui()
