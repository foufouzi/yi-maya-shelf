"""
merge_to_world.py

Maya 2025 / Python 3

Purpose
    An object is animated, but its parent group (or the whole parent chain) is
    animated / offset too. The motion you actually see is the combination of
    both. This tool bakes that combined WORLD-SPACE motion onto a new object
    that lives directly under the world, so the result no longer depends on
    any group.

    Works on any transform-level node: camera, locator, joint, prop mesh,
    nurbs curve, group, image plane parent, etc.

    - Source objects and their groups are untouched during the bake.
    - Animated SHAPE attributes (camera focalLength, light intensity, ...)
      are baked across too; static ones are copied.
    - Optionally deletes the source top group afterwards.

Usage
    import merge_to_world as mtw
    mtw.merge_to_world()                                  # selection
    mtw.merge_to_world(delete_source=True)
    mtw.merge_to_world(mode="locator")                    # bake onto a locator
    mtw.show_merge_to_world_ui()

Limitations
    This bakes TRANSFORM animation only. Deforming geometry (skinCluster,
    blendShape, lattice) is not transferred by the duplicate - use an
    Alembic / GPU cache export for that. For deforming objects prefer
    mode="locator" and constrain the real object to the result.
"""

import maya.cmds as cmds


XFORM_ATTRS = [
    "translateX", "translateY", "translateZ",
    "rotateX", "rotateY", "rotateZ",
    "scaleX", "scaleY", "scaleZ",
]

SKIP_SHAPE_ATTRS = {
    "visibility", "intermediateObject", "instObjGroups",
}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _resolve_objects(objects=None):
    """Return a list of transform full paths."""
    if objects is None:
        objects = cmds.ls(selection=True, long=True) or []
    elif isinstance(objects, str):
        objects = [objects]

    result = []
    for node in objects:
        if not cmds.objExists(node):
            cmds.warning("[skip] Does not exist: {0}".format(node))
            continue
        node = cmds.ls(node, long=True)[0]
        if not cmds.objectType(node, isAType="transform"):
            parents = cmds.listRelatives(node, parent=True, fullPath=True) or []
            if not parents:
                cmds.warning("[skip] No transform for: {0}".format(node))
                continue
            node = parents[0]
        if node not in result:
            result.append(node)
    return result


def _ancestors(node):
    result = []
    current = node
    while True:
        parents = cmds.listRelatives(current, parent=True, fullPath=True) or []
        if not parents:
            break
        result.append(parents[0])
        current = parents[0]
    return result


def _top_ancestor(node):
    chain = _ancestors(node)
    return chain[-1] if chain else None


def _key_range(nodes):
    times = []
    for node in nodes:
        targets = [node]
        targets += cmds.listRelatives(node, shapes=True, fullPath=True) or []
        for target in targets:
            times.extend(cmds.keyframe(target, query=True,
                                       timeChange=True) or [])
    if not times:
        return None
    return int(min(times)), int(max(times))


def _resolve_range(nodes, start=None, end=None, verbose=True):
    if start is not None and end is not None:
        return int(start), int(end)
    found = _key_range(nodes)
    if found:
        if verbose:
            print("[info] Key range detected: {0} - {1}".format(*found))
        return found
    start = int(cmds.playbackOptions(query=True, minTime=True))
    end = int(cmds.playbackOptions(query=True, maxTime=True))
    if verbose:
        print("[warn] No keys found, falling back to timeline: "
              "{0} - {1}".format(start, end))
    return start, end


def _is_settable(plug):
    if not cmds.objExists(plug):
        return False
    if cmds.getAttr(plug, lock=True):
        return False
    if cmds.listConnections(plug, source=True, destination=False,
                            skipConversionNodes=True):
        return False
    return True


def _unlock_xform(node, verbose=True):
    for attr in XFORM_ATTRS + ["visibility"]:
        plug = "{0}.{1}".format(node, attr)
        if cmds.objExists(plug) and cmds.getAttr(plug, lock=True):
            cmds.setAttr(plug, lock=False)
            if verbose:
                print("[info] Unlocked {0}".format(plug))


def _strip_anim(node):
    """Delete anim curves driving a node's transform attrs."""
    for attr in XFORM_ATTRS:
        plug = "{0}.{1}".format(node, attr)
        if not cmds.objExists(plug):
            continue
        curves = cmds.listConnections(plug, source=True, destination=False,
                                      type="animCurve") or []
        if curves:
            cmds.delete(curves)


def _animated_shape_attrs(shape):
    """Keyable shape attrs that are driven by anim curves."""
    result = []
    attrs = cmds.listAttr(shape, keyable=True) or []
    for attr in attrs:
        if attr in SKIP_SHAPE_ATTRS:
            continue
        plug = "{0}.{1}".format(shape, attr)
        if not cmds.objExists(plug):
            continue
        if cmds.listConnections(plug, source=True, destination=False,
                                type="animCurve"):
            result.append(attr)
    return result


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def merge_to_world(objects=None, mode="duplicate", suffix="_world",
                   start=None, end=None, keep_children=False,
                   delete_source=False, verbose=True):
    """Bake combined world-space animation onto new world-parented nodes.

    objects       : transforms (or shapes). None = current selection.
    mode          : "duplicate" -> copy of the object itself (keeps camera /
                    mesh / curve shape and its attributes)
                    "locator"   -> plain locator carrying the motion only
    suffix        : appended to the new node name.
    start / end   : bake range. None = key range of object + all ancestors.
    keep_children : duplicate mode only. False strips child transforms.
    delete_source : delete each source object's TOP ancestor group afterwards.
    verbose       : print a report.

    Returns list of new transforms (full paths).
    """
    sources = _resolve_objects(objects)
    if not sources:
        cmds.warning("[fail] Nothing to process. Select one or more objects.")
        return []

    chain = []
    for src in sources:
        chain.append(src)
        chain.extend(_ancestors(src))
    start, end = _resolve_range(chain, start, end, verbose)
    if end < start:
        cmds.warning("[fail] Invalid range: {0} - {1}".format(start, end))
        return []

    new_nodes = []
    bake_plugs = []
    constraints = []
    temp_plugs = []

    for src in sources:
        short = src.split("|")[-1].split(":")[-1]
        target_name = "{0}{1}".format(short, suffix)

        # --- create the new world node -------------------------------------
        if mode == "locator":
            new_node = cmds.spaceLocator(name=target_name)[0]
            new_node = cmds.ls(new_node, long=True)[0]
        else:
            dup = cmds.duplicate(src, returnRootsOnly=True,
                                 upstreamNodes=False,
                                 inputConnections=False,
                                 name=target_name)[0]
            new_node = cmds.ls(dup, long=True)[0]
            if cmds.listRelatives(new_node, parent=True):
                new_node = cmds.ls(cmds.parent(new_node, world=True)[0],
                                   long=True)[0]
            if not keep_children:
                kids = cmds.listRelatives(new_node, children=True,
                                          fullPath=True,
                                          type="transform") or []
                if kids:
                    cmds.delete(kids)
            _unlock_xform(new_node, verbose)
            _strip_anim(new_node)

        new_nodes.append(new_node)

        # --- constrain to source -------------------------------------------
        constraints.append(cmds.parentConstraint(src, new_node,
                                                 maintainOffset=False)[0])
        constraints.append(cmds.scaleConstraint(src, new_node,
                                                maintainOffset=False)[0])
        bake_plugs.extend("{0}.{1}".format(new_node, a) for a in XFORM_ATTRS)

        # --- animated shape attrs (camera focalLength, light intensity ...) -
        if mode == "duplicate":
            src_shapes = cmds.listRelatives(src, shapes=True,
                                            fullPath=True) or []
            new_shapes = cmds.listRelatives(new_node, shapes=True,
                                            fullPath=True) or []
            for index, src_shape in enumerate(src_shapes):
                if index >= len(new_shapes):
                    break
                new_shape = new_shapes[index]
                for attr in _animated_shape_attrs(src_shape):
                    src_plug = "{0}.{1}".format(src_shape, attr)
                    dst_plug = "{0}.{1}".format(new_shape, attr)
                    if not _is_settable(dst_plug):
                        if verbose:
                            print("[skip] Not settable: {0}".format(dst_plug))
                        continue
                    try:
                        cmds.connectAttr(src_plug, dst_plug, force=True)
                    except RuntimeError:
                        if verbose:
                            print("[skip] Could not connect {0}".format(attr))
                        continue
                    temp_plugs.append(dst_plug)
                    bake_plugs.append(dst_plug)
                    if verbose:
                        print("[info] Will bake shape attr: {0}".format(attr))

        if verbose:
            print("[ok] Created {0}".format(new_node))

    # --- bake everything in one pass ---------------------------------------
    try:
        cmds.bakeResults(
            bake_plugs,
            simulation=True,
            time=(start, end),
            sampleBy=1,
            oversamplingRate=1,
            disableImplicitControl=True,
            preserveOutsideKeys=False,
            sparseAnimCurveBake=False,
            removeBakedAttributeFromLayer=False,
            bakeOnOverrideLayer=False,
            minimizeRotation=True,
            controlPoints=False,
            shape=False,
        )
    finally:
        for plug in temp_plugs:
            for source in (cmds.listConnections(plug, source=True,
                                                destination=False,
                                                plugs=True) or []):
                node_type = cmds.nodeType(source.split(".")[0])
                if not node_type.startswith("animCurve"):
                    try:
                        cmds.disconnectAttr(source, plug)
                    except RuntimeError:
                        pass
        for con in constraints:
            if cmds.objExists(con):
                cmds.delete(con)

    cmds.filterCurve(bake_plugs)

    if verbose:
        print("[ok] Baked {0} - {1} ({2} frames) onto {3} object(s)".format(
            start, end, end - start + 1, len(new_nodes)))

    # --- optional cleanup ---------------------------------------------------
    if delete_source:
        tops = []
        for src in sources:
            top = _top_ancestor(src) or src
            if top not in tops:
                tops.append(top)
        for top in tops:
            descendants = cmds.listRelatives(top, allDescendents=True,
                                             fullPath=True,
                                             type="transform") or []
            others = [n for n in descendants
                      if n not in sources
                      and not any(n.startswith(s + "|") for s in sources)]
            if others and verbose:
                print("[warn] Deleting {0} also removes {1} other "
                      "transform(s): {2}".format(
                          top.split("|")[-1], len(others),
                          ", ".join(n.split("|")[-1] for n in others[:10])))
            try:
                cmds.delete(top)
                if verbose:
                    print("[ok] Deleted source group: {0}".format(top))
            except RuntimeError:
                cmds.warning("[fail] Could not delete: {0}".format(top))

    if new_nodes:
        cmds.select(new_nodes, replace=True)
    return new_nodes


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

WIN = "mergeToWorldWin"


def show_merge_to_world_ui():
    if cmds.window(WIN, exists=True):
        cmds.deleteUI(WIN)

    cmds.window(WIN, title="Merge To World", widthHeight=(340, 250),
                sizeable=False)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=6,
                      columnOffset=("both", 10))
    cmds.text(label="", height=4)
    cmds.text(label="Bakes object + parent group animation", align="left")
    cmds.text(label="onto new nodes under the world.", align="left")
    cmds.separator(height=8, style="in")

    mode_rc = cmds.radioButtonGrp(
        label="Mode", numberOfRadioButtons=2,
        labelArray2=("Duplicate", "Locator"), select=1,
        annotation="Duplicate keeps the original shape (camera, mesh, curve). "
                   "Locator carries motion only.",
        columnWidth3=(60, 110, 110))

    suffix_field = cmds.textFieldGrp(label="Suffix", text="_world",
                                     columnWidth2=(60, 240))

    auto_cb = cmds.checkBox(label="Auto range from keys", value=True)
    range_field = cmds.intFieldGrp(
        numberOfFields=2, label="Range",
        value1=int(cmds.playbackOptions(query=True, minTime=True)),
        value2=int(cmds.playbackOptions(query=True, maxTime=True)),
        enable=False, columnWidth3=(60, 70, 70))
    cmds.checkBox(auto_cb, edit=True, changeCommand=lambda v: cmds.intFieldGrp(
        range_field, edit=True, enable=not v))

    kids_cb = cmds.checkBox(label="Keep child transforms", value=False)
    del_cb = cmds.checkBox(label="Delete source group after merge", value=False)

    cmds.separator(height=8, style="in")

    def _run(*_):
        mode = "duplicate" if cmds.radioButtonGrp(
            mode_rc, query=True, select=True) == 1 else "locator"
        auto = cmds.checkBox(auto_cb, query=True, value=True)
        start = end = None
        if not auto:
            start = cmds.intFieldGrp(range_field, query=True, value1=True)
            end = cmds.intFieldGrp(range_field, query=True, value2=True)
        merge_to_world(
            mode=mode,
            suffix=cmds.textFieldGrp(suffix_field, query=True, text=True)
            or "_world",
            start=start,
            end=end,
            keep_children=cmds.checkBox(kids_cb, query=True, value=True),
            delete_source=cmds.checkBox(del_cb, query=True, value=True),
        )

    cmds.button(label="Merge Selected", height=32, command=_run)
    cmds.showWindow(WIN)


if __name__ == "__main__":
    show_merge_to_world_ui()
