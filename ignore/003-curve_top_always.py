"""
Purpose:
    Force the shape nodes of the currently selected control(s) to always
    draw on top of geometry in Viewport 2.0, so controls near or inside
    a mesh (e.g. IK pole vector controls) never get visually buried.

    Also restores the override color after enabling overrideEnabled,
    since turning overrideEnabled on resets the display color. Two
    color modes are available:
        - Auto: picked from the control's name
              token "L" (e.g. L_leg_ik_control)  -> blue   (index 6)
              token "R" (e.g. R_leg_ik_control)  -> red    (index 13)
              anything else / center controls    -> yellow (index 17)
        - Manual: any Maya override color index 0-31, picked from a
          swatch grid in the UI.

Usage:
    Plain function call (no UI), same as before:

        import control_always_on_top as caot
        caot.set_always_on_top()                       # auto color
        caot.set_always_on_top(color_index=13)          # force red

    UI panel:

        import control_always_on_top as caot
        import importlib
        importlib.reload(caot)
        caot.show_control_always_on_top_ui()

    Shelf button command:

        import control_always_on_top as caot
        import importlib
        importlib.reload(caot)
        caot.show_control_always_on_top_ui()

Notes:
    - Safe on reference edits: this only calls setAttr on override
      attributes, it never touches the rig file itself.
    - If an attribute is locked or driven by a connection (e.g. an SDK
      or expression inside the rig), it is skipped with a [skip]
      message instead of raising an error.
    - alwaysDrawOnTop only has a visible effect in Viewport 2.0, not
      the Legacy Default Viewport.
    - A control built from multiple curve shapes (common for pole
      vector icons) has every shape under it updated, not just the
      first one.
    - The UI applies to whatever is selected in the viewport at the
      moment "Apply to Selection" is clicked, not a snapshot taken
      when the window was opened.
"""

from functools import partial

import maya.cmds as cmds

SIDE_COLORS = {"L": 6, "R": 13}
DEFAULT_COLOR = 17

# Standard Maya override color index 0-31, approximate RGB (0.0-1.0)
# and display name, used to build the swatch grid in the UI.
MAYA_INDEX_COLORS = {
    0: (0.627, 0.627, 0.627), 1: (0.000, 0.000, 0.000),
    2: (0.247, 0.247, 0.247), 3: (0.498, 0.498, 0.498),
    4: (0.608, 0.000, 0.157), 5: (0.000, 0.016, 0.373),
    6: (0.000, 0.000, 1.000), 7: (0.000, 0.275, 0.094),
    8: (0.145, 0.000, 0.263), 9: (0.780, 0.000, 0.780),
    10: (0.537, 0.278, 0.200), 11: (0.243, 0.133, 0.122),
    12: (0.600, 0.145, 0.000), 13: (1.000, 0.000, 0.000),
    14: (0.000, 1.000, 0.000), 15: (0.000, 0.255, 0.600),
    16: (1.000, 1.000, 1.000), 17: (1.000, 1.000, 0.000),
    18: (0.388, 0.863, 1.000), 19: (0.263, 1.000, 0.639),
    20: (1.000, 0.686, 0.686), 21: (0.890, 0.675, 0.475),
    22: (1.000, 1.000, 0.388), 23: (0.000, 0.600, 0.376),
    24: (0.631, 0.416, 0.188), 25: (0.620, 0.631, 0.188),
    26: (0.408, 0.631, 0.188), 27: (0.188, 0.631, 0.365),
    28: (0.188, 0.631, 0.631), 29: (0.188, 0.404, 0.631),
    30: (0.435, 0.188, 0.631), 31: (0.631, 0.188, 0.416),
}

MAYA_INDEX_NAMES = {
    0: "none", 1: "black", 2: "dark grey", 3: "light grey",
    4: "maroon", 5: "navy", 6: "blue", 7: "dark green",
    8: "dark purple", 9: "magenta", 10: "brown", 11: "dark brown",
    12: "brick", 13: "red", 14: "green", 15: "medium blue",
    16: "white", 17: "yellow", 18: "cyan", 19: "mint",
    20: "pink", 21: "tan", 22: "light yellow", 23: "sea green",
    24: "bronze", 25: "olive", 26: "yellow green", 27: "forest",
    28: "teal", 29: "steel blue", 30: "purple", 31: "wine",
}


# ---------------------------------------------------------------------------
# Plain functions
# ---------------------------------------------------------------------------

def set_always_on_top(objects=None, color_index=None, verbose=True):
    """
    Enable always-draw-on-top and set an override color for the given
    controls' shape nodes.

    Args:
        objects (list[str] or None): control transforms to process.
            Falls back to the current selection when None.
        color_index (int or None): Maya override color index (0-31) to
            force on every shape. When None, the color is picked per
            object from its name (see module docstring).
        verbose (bool): print a report line per shape.

    Returns:
        list[tuple(str, bool)]: (shape_path, fully_succeeded) per shape.
    """
    if objects is None:
        objects = cmds.ls(selection=True, long=True)

    if not objects:
        cmds.warning("[control_always_on_top] Nothing selected.")
        return []

    results = []

    for obj in objects:
        if not cmds.objExists(obj):
            if verbose:
                print("[warn] {0} does not exist, skipped.".format(obj))
            continue

        shapes = cmds.listRelatives(
            obj, shapes=True, fullPath=True, noIntermediate=True
        ) or []

        if not shapes:
            if verbose:
                print("[warn] {0} has no shape nodes, skipped.".format(obj))
            continue

        applied_color = (
            color_index if color_index is not None else _color_index_from_name(obj)
        )

        for shape in shapes:
            ok = _apply_always_on_top(shape, applied_color, verbose)
            results.append((shape, ok))

    return results


def _color_index_from_name(obj):
    short_name = obj.split("|")[-1].split(":")[-1]
    tokens = short_name.split("_")
    for side, index in SIDE_COLORS.items():
        if side in tokens:
            return index
    return DEFAULT_COLOR


def _is_locked_or_driven(plug):
    if cmds.getAttr(plug, lock=True):
        return True, "locked"
    conns = cmds.listConnections(plug, source=True, destination=False)
    if conns:
        return True, "driven by {0}".format(conns[0])
    return False, None


def _apply_always_on_top(shape, color_index, verbose):
    plugs = [
        ("overrideEnabled", 1),
        ("alwaysDrawOnTop", 1),
        ("overrideRGBColors", 0),
        ("overrideColor", color_index),
    ]

    short_name = shape.split("|")[-1]
    all_ok = True

    for attr, value in plugs:
        plug = shape + "." + attr
        blocked, reason = _is_locked_or_driven(plug)
        if blocked:
            if verbose:
                print(
                    "[skip] {0}.{1} ({2}), value not changed.".format(
                        short_name, attr, reason
                    )
                )
            all_ok = False
            continue
        cmds.setAttr(plug, value)

    if verbose:
        if all_ok:
            print(
                "[ok] {0} always-draw-on-top set, color index {1} ({2}).".format(
                    short_name, color_index, MAYA_INDEX_NAMES.get(color_index, "?")
                )
            )
        else:
            print(
                "[warn] {0} partially updated, see [skip] lines above.".format(
                    short_name
                )
            )

    return all_ok


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

_UI_WINDOW = "controlAlwaysOnTopWin"
_UI_STATE = {"manual_index": 13}
_UI_WIDGETS = {}


def show_control_always_on_top_ui():
    if cmds.window(_UI_WINDOW, exists=True):
        cmds.deleteUI(_UI_WINDOW)

    cmds.window(_UI_WINDOW, title="Control Always On Top", widthHeight=(280, 430), sizeable=False)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=8, columnAttach=("both", 10))

    cmds.text(
        label="Select control(s) in the viewport, choose a color mode, then Apply.",
        align="left", wordWrap=True, height=40,
    )

    cmds.separator(height=6, style="in")

    cmds.text(label="Color Mode", align="left", font="boldLabelFont")
    color_mode = cmds.radioButtonGrp(
        labelArray2=["Auto (by L_/R_ name)", "Manual (pick below)"],
        numberOfRadioButtons=2, select=1,
        columnWidth2=(140, 140),
        changeCommand=_on_mode_changed,
    )
    _UI_WIDGETS["mode"] = color_mode

    cmds.separator(height=6, style="in")

    cmds.text(label="Manual Color (index 0-31)", align="left", font="boldLabelFont")
    cmds.gridLayout(numberOfColumns=8, cellWidthHeight=(28, 28))
    for idx in range(32):
        rgb = MAYA_INDEX_COLORS[idx]
        cmds.iconTextButton(
            style="iconOnly",
            backgroundColor=rgb,
            annotation="Index {0} - {1}".format(idx, MAYA_INDEX_NAMES[idx]),
            command=partial(_on_swatch_clicked, idx),
        )
    cmds.setParent("..")

    manual_label = cmds.text(
        label="Manual pick: index 13 (red)", align="left"
    )
    _UI_WIDGETS["manual_label"] = manual_label

    cmds.separator(height=6, style="in")

    cmds.button(label="Apply to Selection", height=32, command=_on_apply_clicked)

    cmds.separator(height=6, style="in")

    log_field = cmds.scrollField(editable=False, wordWrap=True, height=100)
    _UI_WIDGETS["log"] = log_field

    cmds.showWindow(_UI_WINDOW)


def _on_mode_changed(*_args):
    pass  # nothing to update, swatch grid stays clickable regardless of mode


def _on_swatch_clicked(idx, *_args):
    _UI_STATE["manual_index"] = idx
    cmds.text(
        _UI_WIDGETS["manual_label"], edit=True,
        label="Manual pick: index {0} ({1})".format(idx, MAYA_INDEX_NAMES[idx]),
    )
    # picking a swatch implies the user wants manual mode
    cmds.radioButtonGrp(_UI_WIDGETS["mode"], edit=True, select=2)


def _on_apply_clicked(*_args):
    mode = cmds.radioButtonGrp(_UI_WIDGETS["mode"], query=True, select=True)
    color_index = None if mode == 1 else _UI_STATE["manual_index"]

    objects = cmds.ls(selection=True, long=True)
    if not objects:
        cmds.warning("[control_always_on_top] Nothing selected.")
        _append_log("[warn] Nothing selected.")
        return

    lines = []

    def _capture_print(*args, **kwargs):
        lines.append(" ".join(str(a) for a in args))

    import builtins
    real_print = builtins.print
    builtins.print = _capture_print
    try:
        set_always_on_top(objects=objects, color_index=color_index, verbose=True)
    finally:
        builtins.print = real_print

    _append_log("\n".join(lines) if lines else "[warn] No shapes processed.")


def _append_log(text):
    existing = cmds.scrollField(_UI_WIDGETS["log"], query=True, text=True)
    combined = (existing + "\n" + text).strip() if existing else text
    cmds.scrollField(_UI_WIDGETS["log"], edit=True, text=combined)


if __name__ == "__main__":
    show_control_always_on_top_ui()