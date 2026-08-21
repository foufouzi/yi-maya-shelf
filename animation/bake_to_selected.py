"""
bake_to_selected.py

Maya 2025 / Python 3

Purpose
    Select object A (source) first, then B (target). Bakes A's world-space
    animation onto B across the whole frame range using a temporary
    parentConstraint + bakeResults, then cleans up.

Notes
    - Locked channels on B are skipped with a warning instead of erroring out.
    - If B has an incoming offsetParentMatrix connection, the baked translate
      values are expressed in that parent space: the position looks right but
      the numbers differ from A's world translate.
    - simulation=False is used for speed; switch to True if the rig depends on
      dynamics or evaluation order.

Usage
    import bake_to_selected as bts
    bts.bake_to_selected()
"""

import maya.cmds as cmds


def _resolve_range(source, start, end):
    if start is not None and end is not None:
        return float(start), float(end)

    keys = cmds.keyframe(source, query=True, timeChange=True)
    if keys:
        return min(keys), max(keys)

    return (cmds.playbackOptions(query=True, minTime=True),
            cmds.playbackOptions(query=True, maxTime=True))


def _bakeable_attrs(node, translate, rotate, scale):
    groups = []
    if translate:
        groups.append("tx ty tz")
    if rotate:
        groups.append("rx ry rz")
    if scale:
        groups.append("sx sy sz")

    attrs = []
    for names in groups:
        for attr in names.split():
            plug = "{0}.{1}".format(node, attr)
            if not cmds.objExists(plug):
                continue
            if cmds.getAttr(plug, lock=True):
                cmds.warning("Skipping locked attribute: {0}".format(plug))
                continue
            attrs.append(attr)
    return attrs


def bake_to_selected(maintain_offset=False,
                     translate=True,
                     rotate=True,
                     scale=False,
                     start=None,
                     end=None,
                     sample_by=1.0):
    """Bake the first selected object's animation onto the last selected object."""

    sel = cmds.ls(selection=True, long=True)
    if len(sel) < 2:
        cmds.error("Select the source object first, then the target object.")

    source, target = sel[0], sel[-1]

    attrs = _bakeable_attrs(target, translate, rotate, scale)
    if not attrs:
        cmds.error("No bakeable attributes on target: {0}".format(target))

    start, end = _resolve_range(source, start, end)

    constraints = []
    if translate or rotate:
        skip_t = [ax for ax in "xyz" if not translate]
        skip_r = [ax for ax in "xyz" if not rotate]
        constraints.append(cmds.parentConstraint(
            source, target,
            maintainOffset=maintain_offset,
            skipTranslate=skip_t or "none",
            skipRotate=skip_r or "none")[0])
    if scale:
        constraints.append(cmds.scaleConstraint(
            source, target, maintainOffset=maintain_offset)[0])

    try:
        cmds.bakeResults(
            target,
            attribute=attrs,
            time=(start, end),
            sampleBy=sample_by,
            simulation=False,
            disableImplicitControl=True,
            preserveOutsideKeys=True,
            sparseAnimCurveBake=False,
            removeBakedAttributeFromLayer=False,
            bakeOnOverrideLayer=False,
            minimizeRotation=True)
    finally:
        if constraints:
            cmds.delete(constraints)

    if rotate:
        cmds.filterCurve(
            ["{0}.{1}".format(target, a) for a in attrs if a.startswith("r")],
            filter="euler")

    cmds.select(target, replace=True)
    print("Baked {0} -> {1}  frames {2:.0f}-{3:.0f}".format(
        source.split("|")[-1], target.split("|")[-1], start, end))

    return target


if __name__ == "__main__":
    bake_to_selected()
