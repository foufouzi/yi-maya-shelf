"""
Purpose:
    Force the shape nodes of the currently selected control(s) to always
    draw on top of geometry in Viewport 2.0, so controls near or inside
    a mesh (e.g. IK pole vector controls) never get visually buried.

    Also restores the override color after enabling overrideEnabled,
    since turning overrideEnabled on resets the display color. Colors
    use the 27-swatch animBot style palette (RGB override). Two color
    modes are available:
        - Auto: picked from the control's name
              token "L" (e.g. L_leg_ik_control)  -> blue
              token "R" (e.g. R_leg_ik_control)  -> red
              anything else / center controls    -> yellow
        - Manual: any swatch from the 27-color palette, or any hex
          value typed into the hex field.

Usage:
    Plain function call (no UI):

        import control_always_on_top as caot
        caot.set_always_on_top()                        # auto color
        caot.set_always_on_top(color="#4F9FD0")         # hex RGB
        caot.set_always_on_top(color=(1.0, 0.5, 0.2))   # 0-1 RGB
        caot.set_always_on_top(color_index=13)          # legacy index mode

    UI panel / shelf button command:

        import control_always_on_top as caot
        import importlib
        importlib.reload(caot)
        caot.show_control_always_on_top_ui()

Notes:
    - Safe on reference edits: this only calls setAttr on override
      attributes, it never touches the rig file itself.
    - Locked or connection-driven attributes are skipped with a [skip]
      message instead of raising an error. A warning is printed when
      the shape's draw override is driven by a Display Layer.
    - alwaysDrawOnTop only has a visible effect in Viewport 2.0.
    - Every shape under a multi-shape control is updated.
    - The UI applies to whatever is selected when "Apply to Selection"
      is clicked.
"""

from functools import partial

import maya.cmds as cmds

# ---------------------------------------------------------------------------
# Palette (animBot style, 9 columns x 3 rows)
# ---------------------------------------------------------------------------

PALETTE_HEX = [
    # row 1: greys, reds, oranges
    "#3C3C3C", "#333333", "#2A2A2A",
    "#EFA1A4", "#BC4A4A", "#8A3434",
    "#F4A582", "#E0703A", "#8A4A22",
    # row 2: yellows, greens, cyans
    "#F2E27A", "#C8B832", "#857A18",
    "#8EE79A", "#4FAF5F", "#2F7A3F",
    "#A6EEF2", "#3FAAB5", "#2F7279",
    # row 3: blues, purples, pinks
    "#C5E3F5", "#4F9FD0", "#2E5C7A",
    "#DCD0F0", "#A88FD8", "#5E4A80",
    "#F4CCEE", "#D98AD0", "#7E4A7E",
]
PALETTE_COLUMNS = 9

SIDE_COLORS = {"L": "#4F9FD0", "R": "#BC4A4A"}
DEFAULT_COLOR = "#F2E27A"

# UI theme (matches the Shelf Icon Generator look)
UI_WIDTH = 360
UI_SECTION_BG = (0.255, 0.255, 0.255)
UI_INSET_BG = (0.215, 0.215, 0.215)
UI_BUTTON_BG = (0.36, 0.36, 0.36)


# ---------------------------------------------------------------------------
# Color helpers
# ---------------------------------------------------------------------------

def hex_to_rgb(hex_str):
    """'#RRGGBB' or 'RRGGBB' -> (r, g, b) floats 0-1. Returns None if invalid."""
    if not hex_str:
        return None
    value = hex_str.strip().lstrip("#")
    if len(value) == 3:
        value = "".join(c * 2 for c in value)
    if len(value) != 6:
        return None
    try:
        return tuple(int(value[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    except ValueError:
        return None


def rgb_to_hex(rgb):
    return "#{0:02X}{1:02X}{2:02X}".format(
        *[max(0, min(255, int(round(c * 255)))) for c in rgb]
    )


def _normalize_color(color):
    """Accept hex string or (r, g, b) tuple, return (r, g, b) or None."""
    if color is None:
        return None
    if isinstance(color, str):
        return hex_to_rgb(color)
    if len(color) == 3:
        return tuple(float(c) for c in color)
    return None


# ---------------------------------------------------------------------------
# Plain functions
# ---------------------------------------------------------------------------

def set_always_on_top(objects=None, color=None, color_index=None, verbose=True):
    """
    Enable always-draw-on-top and set an override color for the given
    controls' shape nodes.

    Args:
        objects (list[str] or None): control transforms to process.
            Falls back to the current selection when None.
        color (str or tuple or None): hex string or 0-1 RGB tuple forced
            on every shape (RGB override). When None and color_index is
            None, the color is picked per object from its name.
        color_index (int or None): legacy Maya override color index
            (0-31). Used only when color is None.
        verbose (bool): print a report line per shape.

    Returns:
        list[tuple(str, bool)]: (shape_path, fully_succeeded) per shape.
    """
    if objects is None:
        objects = cmds.ls(selection=True, long=True)

    if not objects:
        cmds.warning("[control_always_on_top] Nothing selected.")
        return []

    forced_rgb = _normalize_color(color)
    if color is not None and forced_rgb is None:
        cmds.warning("[control_always_on_top] Invalid color: {0}".format(color))
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

        if forced_rgb is not None:
            rgb, index = forced_rgb, None
        elif color_index is not None:
            rgb, index = None, color_index
        else:
            rgb, index = hex_to_rgb(_color_from_name(obj)), None

        for shape in shapes:
            ok = _apply_always_on_top(shape, rgb, index, verbose)
            results.append((shape, ok))

    return results


def _color_from_name(obj):
    short_name = obj.split("|")[-1].split(":")[-1]
    tokens = short_name.split("_")
    for side, hex_color in SIDE_COLORS.items():
        if side in tokens:
            return hex_color
    return DEFAULT_COLOR


def _is_locked_or_driven(plug):
    if cmds.getAttr(plug, lock=True):
        return True, "locked"
    conns = cmds.listConnections(plug, source=True, destination=False)
    if conns:
        return True, "driven by {0}".format(conns[0])
    return False, None


def _apply_always_on_top(shape, rgb, index, verbose):
    short_name = shape.split("|")[-1]

    layer_conns = cmds.listConnections(
        shape + ".drawOverride", source=True, destination=False, type="displayLayer"
    )
    if layer_conns and verbose:
        print(
            "[warn] {0} draw override is driven by display layer {1}.".format(
                short_name, layer_conns[0]
            )
        )

    plugs = [("overrideEnabled", 1), ("alwaysDrawOnTop", 1)]
    if rgb is not None:
        plugs += [("overrideRGBColors", 1), ("overrideColorRGB", rgb)]
        color_desc = rgb_to_hex(rgb)
    else:
        plugs += [("overrideRGBColors", 0), ("overrideColor", index)]
        color_desc = "index {0}".format(index)

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
        if isinstance(value, tuple):
            cmds.setAttr(plug, value[0], value[1], value[2], type="double3")
        else:
            cmds.setAttr(plug, value)

    if verbose:
        if all_ok:
            print("[ok] {0} always-draw-on-top set, color {1}.".format(
                short_name, color_desc))
        else:
            print("[warn] {0} partially updated, see [skip] lines above.".format(
                short_name))

    return all_ok


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

_UI_WINDOW = "controlAlwaysOnTopWin"
_UI_STATE = {"manual_hex": "#BC4A4A"}
_UI_WIDGETS = {}


def show_control_always_on_top_ui():
    if cmds.window(_UI_WINDOW, exists=True):
        cmds.deleteUI(_UI_WINDOW)

    cmds.window(
        _UI_WINDOW, title="Control Always On Top",
        widthHeight=(UI_WIDTH, 520), sizeable=False,
    )
    cmds.columnLayout(
        adjustableColumn=True, rowSpacing=8, columnAttach=("both", 10),
        width=UI_WIDTH,
    )

    cmds.separator(height=4, style="none")
    cmds.text(
        label="Select control(s) in the viewport, choose a color mode, then Apply.",
        align="left", wordWrap=True,
    )

    # --- Color mode --------------------------------------------------------
    cmds.text(label="Color Mode:", align="left")
    _UI_WIDGETS["mode"] = cmds.radioButtonGrp(
        labelArray2=["Auto (by L_/R_ name)", "Manual (pick below)"],
        numberOfRadioButtons=2, select=1,
        columnWidth2=(165, 165),
    )

    # --- Control color section --------------------------------------------
    cmds.columnLayout(
        adjustableColumn=True, rowSpacing=8, columnAttach=("both", 10),
        backgroundColor=UI_SECTION_BG,
    )
    cmds.separator(height=2, style="none")
    cmds.text(label="Control Color", align="left")

    cmds.rowLayout(
        numberOfColumns=2, adjustableColumn=2,
        columnWidth2=(38, 280), columnAttach2=("left", "left"),
        columnOffset2=(0, 8),
    )
    _UI_WIDGETS["preview"] = cmds.canvas(
        rgbValue=hex_to_rgb(_UI_STATE["manual_hex"]), width=28, height=28,
    )
    _UI_WIDGETS["hex"] = cmds.textField(
        text=_UI_STATE["manual_hex"], height=28,
        changeCommand=_on_hex_changed,
        annotation="Type a hex color, e.g. #4F9FD0, then press Enter.",
    )
    cmds.setParent("..")

    # inset swatch grid
    cmds.columnLayout(
        adjustableColumn=True, columnAttach=("both", 12),
        backgroundColor=UI_INSET_BG,
    )
    cmds.separator(height=8, style="none")
    rows = len(PALETTE_HEX) // PALETTE_COLUMNS
    cmds.rowColumnLayout(
        numberOfColumns=PALETTE_COLUMNS,
        columnWidth=[(c + 1, 31) for c in range(PALETTE_COLUMNS)],
        rowSpacing=[(r + 1, 6) for r in range(rows)],
    )
    for hex_color in PALETTE_HEX:
        cmds.iconTextButton(
            style="iconOnly", width=24, height=20,
            backgroundColor=hex_to_rgb(hex_color),
            annotation=hex_color,
            command=partial(_on_swatch_clicked, hex_color),
        )
    cmds.setParent("..")
    cmds.separator(height=8, style="none")
    cmds.setParent("..")  # inset

    cmds.separator(height=4, style="none")
    cmds.setParent("..")  # section

    # --- Apply ------------------------------------------------------------
    cmds.iconTextButton(
        style="textOnly", label="Apply to Selection",
        font="boldLabelFont", height=40,
        backgroundColor=UI_BUTTON_BG,
        command=_on_apply_clicked,
    )

    _UI_WIDGETS["log"] = cmds.scrollField(
        editable=False, wordWrap=True, height=110,
    )
    cmds.separator(height=4, style="none")

    cmds.showWindow(_UI_WINDOW)
    cmds.window(_UI_WINDOW, edit=True, width=UI_WIDTH)


def _set_manual_color(hex_color):
    rgb = hex_to_rgb(hex_color)
    if rgb is None:
        return False
    hex_color = rgb_to_hex(rgb)
    _UI_STATE["manual_hex"] = hex_color
    cmds.canvas(_UI_WIDGETS["preview"], edit=True, rgbValue=rgb)
    cmds.textField(_UI_WIDGETS["hex"], edit=True, text=hex_color)
    # picking a color implies the user wants manual mode
    cmds.radioButtonGrp(_UI_WIDGETS["mode"], edit=True, select=2)
    return True


def _on_swatch_clicked(hex_color, *_args):
    _set_manual_color(hex_color)


def _on_hex_changed(text, *_args):
    if not _set_manual_color(text):
        cmds.warning("[control_always_on_top] Invalid hex color: {0}".format(text))
        cmds.textField(_UI_WIDGETS["hex"], edit=True, text=_UI_STATE["manual_hex"])


def _on_apply_clicked(*_args):
    mode = cmds.radioButtonGrp(_UI_WIDGETS["mode"], query=True, select=True)
    color = None if mode == 1 else _UI_STATE["manual_hex"]

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
        set_always_on_top(objects=objects, color=color, verbose=True)
    finally:
        builtins.print = real_print

    _append_log("\n".join(lines) if lines else "[warn] No shapes processed.")


def _append_log(text):
    existing = cmds.scrollField(_UI_WIDGETS["log"], query=True, text=True)
    combined = (existing + "\n" + text).strip() if existing else text
    cmds.scrollField(_UI_WIDGETS["log"], edit=True, text=combined)


if __name__ == "__main__":
    show_control_always_on_top_ui()
