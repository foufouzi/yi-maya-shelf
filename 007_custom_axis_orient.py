"""Custom Axis Orientation helper for Maya 2025.

Sets the Move / Rotate manipulator to "Custom axis orientation" and aligns it
to a reference object's world rotation. Re-run it whenever Maya drops the
custom orientation back to Object mode (selection change, undo, tool switch).

Usage:
    import custom_axis_orient as cao
    cao.orient_from()                 # last-selected object = reference
    cao.orient_from("locator1")       # explicit reference
    cao.reset_orient()                # back to Object mode
    cao.show_custom_axis_ui()         # small UI with Set / Reset

Note:
    pinPivot only has an effect in component mode; it is harmless in object
    mode. For long working sessions on rig controls, a temp locator/group or
    animBot's Temp Pivot is more robust than the Custom axis setting.
"""

import maya.cmds as cmds

MOVE_CTX = "Move"
ROTATE_CTX = "Rotate"
SCALE_CTX = "Scale"

MODE_OBJECT = 0
MODE_CUSTOM = 6


def _reference_object(reference=None, verbose=True):
    """Return a reference transform: explicit arg, else last selected object."""
    if reference:
        if not cmds.objExists(reference):
            if verbose:
                cmds.warning("[fail] reference does not exist: %s" % reference)
            return None
        return reference

    sel = cmds.ls(selection=True, objectsOnly=True, long=True) or []
    if not sel:
        if verbose:
            cmds.warning("[fail] nothing selected. Select the target, then the reference last.")
        return None
    if len(sel) < 2 and verbose:
        cmds.warning("[info] only one object selected - using it as the reference.")
    return sel[-1]


def orient_from(reference=None, move=True, rotate=False, scale=False,
                pin_pivot=True, verbose=True):
    """Align manipulators to reference object's world orientation.

    By default only the Move manipulator is affected. Pass rotate=True /
    scale=True to include those tools as well.
    """
    ref = _reference_object(reference, verbose=verbose)
    if not ref:
        return None

    try:
        rot = cmds.xform(ref, query=True, worldSpace=True, rotation=True)
    except Exception:
        cmds.warning("[fail] could not query world rotation of %s" % ref)
        return None

    targets = []
    if move:
        targets.append((MOVE_CTX, cmds.manipMoveContext))
    if rotate:
        targets.append((ROTATE_CTX, cmds.manipRotateContext))
    if scale:
        targets.append((SCALE_CTX, cmds.manipScaleContext))

    for ctx, fn in targets:
        if not cmds.contextInfo(ctx, exists=True):
            if verbose:
                cmds.warning("[skip] context not found: %s" % ctx)
            continue
        try:
            fn(ctx, edit=True, mode=MODE_CUSTOM)
        except Exception as err:
            cmds.warning("[fail] %s mode: %s" % (ctx, err))
            continue
        # orientAxes expects radians in some builds; orientObject is safer.
        try:
            fn(ctx, edit=True, orientObject=ref)
        except Exception:
            try:
                import math
                fn(ctx, edit=True,
                   orientAxes=[math.radians(a) for a in rot])
            except Exception as err:
                cmds.warning("[warn] %s orient fallback failed: %s" % (ctx, err))
        if pin_pivot:
            try:
                fn(ctx, edit=True, pinPivot=True)
            except Exception:
                pass
        if verbose:
            print("[ok] %s manipulator oriented to %s" % (ctx, ref.split("|")[-1]))

    return ref


def reset_orient(move=True, rotate=False, scale=False, verbose=True):
    """Return manipulators to Object axis orientation. Move only by default."""
    wanted = []
    if move:
        wanted.append((MOVE_CTX, cmds.manipMoveContext))
    if rotate:
        wanted.append((ROTATE_CTX, cmds.manipRotateContext))
    if scale:
        wanted.append((SCALE_CTX, cmds.manipScaleContext))

    for ctx, fn in wanted:
        if not cmds.contextInfo(ctx, exists=True):
            continue
        try:
            fn(ctx, edit=True, mode=MODE_OBJECT)
        except Exception as err:
            cmds.warning("[warn] %s reset failed: %s" % (ctx, err))
    if verbose:
        print("[ok] manipulators reset to Object axis orientation")


def show_custom_axis_ui():
    win = "customAxisOrientWin"
    if cmds.window(win, exists=True):
        cmds.deleteUI(win)
    cmds.window(win, title="Custom Axis Orientation", widthHeight=(240, 120),
                sizeable=False)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=6,
                      columnOffset=("both", 8))
    cmds.text(label="Select target, then reference LAST.", align="left")
    chk = cmds.checkBox("caoIncludeRotate", label="Also affect Rotate tool",
                        value=False,
                        annotation="Off = Move manipulator only")

    def _set(*_):
        also_rot = cmds.checkBox(chk, query=True, value=True)
        orient_from(rotate=also_rot)

    def _reset(*_):
        also_rot = cmds.checkBox(chk, query=True, value=True)
        reset_orient(rotate=also_rot)

    cmds.button(label="Set From Last Selected",
                annotation="Orient the Move manipulator to the last selected object",
                command=_set)
    cmds.button(label="Reset To Object",
                annotation="Back to Object axis orientation",
                command=_reset)
    cmds.setParent("..")
    cmds.showWindow(win)


if __name__ == "__main__":
    show_custom_axis_ui()
