"""
locator_checker.py

Maya 2025 / Python 3

Locator Checker / Fixer  +  Size & Color tools
----------------------------------------------
Diagnoses and fixes locators (or any transform) that exist in the scene but
do not render in the viewport: visibility, localScale, drawing overrides,
template state, parent hierarchy, display layers, isolate select and the
viewport "Show > Locators" toggle.

Usage:
    import locator_checker as lc
    lc.fix_locator_visibility()                      # check & fix current selection
    lc.set_locator_size(5.0)                         # set locator display size
    lc.set_locator_color(17)                         # set Maya override color index (0-31)
    lc.fix_locator_visibility(size=5.0, color="#F29E9D") # apply exact RGB color
    lc.show_locator_checker_ui()                     # open the UI window
"""

import maya.cmds as cmds

# ------------------------------------------------------------------
# Maya override color index table (0-31)
# ------------------------------------------------------------------
COLOR_INDEX_NAMES = {
    0: "Default (grey)", 1: "Black", 2: "Dark Grey", 3: "Light Grey",
    4: "Dark Red", 5: "Navy", 6: "Blue", 7: "Dark Green",
    8: "Dark Purple", 9: "Magenta", 10: "Brown", 11: "Dark Brown",
    12: "Dark Orange", 13: "Red", 14: "Green", 15: "Cornflower Blue",
    16: "White", 17: "Yellow", 18: "Light Cyan", 19: "Mint",
    20: "Pink", 21: "Skin", 22: "Light Yellow", 23: "Sea Green",
    24: "Tan", 25: "Olive", 26: "Yellow Green", 27: "Forest Green",
    28: "Teal", 29: "Steel Blue", 30: "Purple", 31: "Dark Magenta",
}

# Maya override color index -> RGB (0-1), used for UI swatches
COLOR_INDEX_RGB = {
    0: (0.500, 0.500, 0.500), 1: (0.000, 0.000, 0.000), 2: (0.247, 0.247, 0.247),
    3: (0.498, 0.498, 0.498), 4: (0.608, 0.000, 0.157), 5: (0.000, 0.016, 0.376),
    6: (0.000, 0.000, 1.000), 7: (0.000, 0.275, 0.098), 8: (0.149, 0.000, 0.263),
    9: (0.784, 0.000, 0.784), 10: (0.541, 0.282, 0.200), 11: (0.247, 0.137, 0.121),
    12: (0.600, 0.149, 0.000), 13: (1.000, 0.000, 0.000), 14: (0.000, 1.000, 0.000),
    15: (0.000, 0.255, 0.600), 16: (1.000, 1.000, 1.000), 17: (1.000, 1.000, 0.000),
    18: (0.392, 0.863, 1.000), 19: (0.263, 1.000, 0.639), 20: (1.000, 0.690, 0.690),
    21: (0.894, 0.675, 0.475), 22: (1.000, 1.000, 0.388), 23: (0.000, 0.600, 0.325),
    24: (0.630, 0.414, 0.188), 25: (0.620, 0.627, 0.188), 26: (0.408, 0.631, 0.188),
    27: (0.188, 0.631, 0.365), 28: (0.188, 0.627, 0.627), 29: (0.188, 0.404, 0.627),
    30: (0.435, 0.188, 0.627), 31: (0.627, 0.188, 0.412),
}

# Animbot color palette sampled from the supplied reference image.
ANIMBOT_PALETTE = [
    ("Dark Gray", "#3C3C3C"),
    ("Charcoal", "#333333"),
    ("Near Black", "#282828"),
    ("Light Salmon Pink", "#F29E9D"),
    ("Muted Red", "#BA5251"),
    ("Deep Red", "#7F3635"),
    ("Peach", "#F2A785"),
    ("Burnt Orange", "#DF6D39"),
    ("Brown", "#7F3D1F"),
    ("Pale Yellow", "#F2E66C"),
    ("Mustard Yellow", "#BFB32C"),
    ("Dark Olive", "#7F7615"),
    ("Mint Green", "#84F296"),
    ("Medium Green", "#51AC61"),
    ("Forest Green", "#357F42"),
    ("Pale Cyan", "#9DECF2"),
    ("Teal", "#43AAB6"),
    ("Deep Teal", "#3F777F"),
    ("Pale Blue", "#C1E2F2"),
    ("Sky Blue", "#54A4CE"),
    ("Steel Blue", "#35637F"),
    ("Pale Lavender", "#D9D0F2"),
    ("Lavender", "#AE9ADD"),
    ("Muted Purple", "#665980"),
    ("Light Pink", "#F2C3ED"),
    ("Orchid Pink", "#D384CA"),
    ("Plum", "#7F4A77"),
]


def _hex_to_rgb(color):
    """Convert a #RRGGBB string to an RGB tuple in Maya's 0-1 range."""
    value = color.strip().lstrip("#")
    if len(value) != 6 or not all(c in "0123456789abcdefABCDEF" for c in value):
        raise ValueError("Color must be a 6-digit HEX value, for example #F29E9D")
    return tuple(int(value[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def _is_color_attr_editable(node, attr):
    """Return whether an override attribute can be safely changed."""
    plug = "{}.{}".format(node, attr)
    if cmds.getAttr(plug, lock=True):
        cmds.warning("{} is locked, skipped".format(plug))
        return False
    if cmds.listConnections(plug, source=True, destination=False):
        cmds.warning("{} is connected (possibly driven by a Display Layer), skipped".format(plug))
        return False
    return True


def _get_targets(objects=None, warn_msg="Please select an object first"):
    """Resolve a target list from an argument or the current selection."""
    if objects is None:
        targets = cmds.ls(selection=True, long=True)
        if not targets:
            cmds.warning(warn_msg)
            return []
        return targets
    if isinstance(objects, str):
        objects = [objects]
    valid = []
    for o in objects:
        if cmds.objExists(o):
            valid.append(o)
        else:
            cmds.warning("Object not found: {}".format(o))
    return valid


# ==================================================================
#  SIZE
# ==================================================================
def set_locator_size(size=5.0, objects=None, verbose=True):
    """
    Set the display size (localScale) of locator shapes.
    Non-locator transforms are skipped.

    Args:
        size: float, or (x, y, z) tuple for per-axis values
        objects: object name / list; None uses the current selection
    """
    targets = _get_targets(
        objects, "Select a locator, or pass a name to set_locator_size()")
    if not targets:
        return

    if isinstance(size, (list, tuple)):
        sx, sy, sz = size
    else:
        sx = sy = sz = float(size)

    done = 0
    for obj in targets:
        shapes = cmds.listRelatives(obj, shapes=True, fullPath=True) or []
        # obj itself may already be a shape
        if cmds.objectType(obj) == "locator":
            shapes = [obj]
        loc_shapes = [s for s in shapes if cmds.objectType(s) == "locator"]
        if not loc_shapes:
            if verbose:
                print("[skip] {} has no locator shape".format(obj))
            continue
        for shape in loc_shapes:
            for attr, val in (("localScaleX", sx), ("localScaleY", sy), ("localScaleZ", sz)):
                plug = "{}.{}".format(shape, attr)
                if cmds.getAttr(plug, lock=True):
                    cmds.warning("{} is locked, cannot edit".format(plug))
                    continue
                if cmds.listConnections(plug, source=True, destination=False):
                    cmds.warning("{} is connected (driven), skipped".format(plug))
                    continue
                cmds.setAttr(plug, val)
            done += 1
            if verbose:
                print("[ok] {} size set to ({}, {}, {})".format(shape, sx, sy, sz))
    if verbose:
        print("--- size applied to {} locator shape(s) ---".format(done))


def get_locator_size(obj):
    """Return the localScale of the first locator shape under obj."""
    shapes = cmds.listRelatives(obj, shapes=True, fullPath=True) or []
    if cmds.objectType(obj) == "locator":
        shapes = [obj]
    for s in shapes:
        if cmds.objectType(s) == "locator":
            return cmds.getAttr("{}.localScale".format(s))[0]
    return None


# ==================================================================
#  COLOR  (Maya index 0-31 or exact RGB override)
# ==================================================================
def set_locator_color(index=17, objects=None, apply_to="shape", verbose=True):
    """Set a Maya indexed override or an exact RGB override color.

    Args:
        index: Maya index 0-31, a #RRGGBB string, or an RGB tuple in 0-1 range.
               Pass None or a negative index to disable the override.
        objects: object name / list; None uses the current selection
        apply_to: "shape" (default) / "transform" / "both"
    """
    targets = _get_targets(
        objects, "Select an object, or pass a name to set_locator_color()")
    if not targets:
        return

    disable = index is None or (isinstance(index, (int, float)) and index < 0)
    rgb = None
    color_index = None
    if not disable:
        if isinstance(index, str):
            try:
                rgb = _hex_to_rgb(index)
            except ValueError as error:
                cmds.warning(str(error))
                return
        elif isinstance(index, (tuple, list)) and len(index) == 3:
            try:
                rgb = tuple(float(channel) for channel in index)
            except (TypeError, ValueError):
                cmds.warning("RGB color must contain three numeric values from 0 to 1")
                return
            if any(channel < 0.0 or channel > 1.0 for channel in rgb):
                cmds.warning("RGB color channels must be in the 0-1 range")
                return
        elif isinstance(index, int) and 0 <= index <= 31:
            color_index = index
        else:
            cmds.warning("Color must be an index from 0-31, a #RRGGBB value, or an RGB tuple")
            return

    done = 0
    for obj in targets:
        nodes = []
        shapes = cmds.listRelatives(obj, shapes=True, fullPath=True) or []
        if apply_to in ("shape", "both"):
            nodes += shapes
        if apply_to in ("transform", "both") or not shapes:
            nodes.append(obj)

        for node in nodes:
            if not cmds.attributeQuery("overrideEnabled", node=node, exists=True):
                continue
            if cmds.listConnections("{}.overrideEnabled".format(node),
                                    source=True, destination=False):
                cmds.warning("{} override is driven by a Display Layer. "
                             "Set the color on the layer, or remove the object "
                             "from it.".format(node))
                continue
            if not _is_color_attr_editable(node, "overrideEnabled"):
                continue

            if disable:
                cmds.setAttr("{}.overrideEnabled".format(node), 0)
                done += 1
                if verbose:
                    print("[ok] {} color override disabled".format(node))
                continue

            if not _is_color_attr_editable(node, "overrideRGBColors"):
                continue
            if color_index is not None:
                if not _is_color_attr_editable(node, "overrideColor"):
                    continue
                cmds.setAttr("{}.overrideEnabled".format(node), 1)
                cmds.setAttr("{}.overrideRGBColors".format(node), 0)
                cmds.setAttr("{}.overrideColor".format(node), color_index)
                result = "index {} ({})".format(
                    color_index, COLOR_INDEX_NAMES.get(color_index, "?"))
            else:
                if not _is_color_attr_editable(node, "overrideColorRGB"):
                    continue
                cmds.setAttr("{}.overrideEnabled".format(node), 1)
                cmds.setAttr("{}.overrideRGBColors".format(node), 1)
                cmds.setAttr("{}.overrideColorRGB".format(node),
                             rgb[0], rgb[1], rgb[2], type="double3")
                result = "RGB ({:.3f}, {:.3f}, {:.3f})".format(*rgb)
            done += 1
            if verbose:
                print("[ok] {} color set to {}".format(node, result))
    if verbose:
        print("--- color applied to {} node(s) ---".format(done))


# ==================================================================
#  VISIBILITY CHECK / FIX
# ==================================================================
def fix_locator_visibility(locator=None, verbose=True, size=None, color=None):
    """
    Diagnose and fix visibility issues for a locator (or any transform).

    Args:
        locator: name of the locator transform. If None, uses current selection.
        verbose: print a report of what was found/changed.
        size: if given, also set the locator size (localScale) afterwards
        color: if given, set an index (0-31), #RRGGBB, or RGB tuple afterwards
    """
    targets = _get_targets(
        locator, "Select a locator, or pass a name to fix_locator_visibility()")
    if not targets:
        return

    for obj in targets:
        _fix_single(obj, verbose)

    if size is not None:
        set_locator_size(size, objects=targets, verbose=verbose)
    if color is not None:
        set_locator_color(color, objects=targets, verbose=verbose)


def _fix_single(obj, verbose):
    print("\n" + "=" * 50)
    print("Checking: {}".format(obj))
    print("=" * 50)

    changes = []
    shapes = cmds.listRelatives(obj, shapes=True, fullPath=True) or []
    is_locator_shape = any(cmds.objectType(s) == "locator" for s in shapes)
    if not is_locator_shape and cmds.objectType(obj) != "locator":
        print("[warn] {} has no locator shape; running generic "
              "visibility checks anyway".format(obj))

    # ---------- 1. Transform visibility ----------
    if cmds.attributeQuery("visibility", node=obj, exists=True):
        vis = cmds.getAttr("{}.visibility".format(obj))
        vis_locked = cmds.getAttr("{}.visibility".format(obj), lock=True)
        vis_connected = cmds.listConnections("{}.visibility".format(obj),
                                             source=True, destination=False)
        if not vis:
            if vis_locked:
                print("[fail] {}.visibility is off and locked; "
                      "fix manually".format(obj))
            elif vis_connected:
                print("[fail] {}.visibility is off and connected to: {} "
                      "(driven; check the source manually)".format(obj, vis_connected))
            else:
                cmds.setAttr("{}.visibility".format(obj), True)
                changes.append("enabled transform visibility")
        else:
            print("[ok] {}.visibility is on".format(obj))

    # ---------- 2. Shape visibility ----------
    for shape in shapes:
        if cmds.attributeQuery("visibility", node=shape, exists=True):
            if not cmds.getAttr("{}.visibility".format(shape)):
                if cmds.getAttr("{}.visibility".format(shape), lock=True):
                    print("[fail] {}.visibility is off and locked; "
                          "fix manually".format(shape))
                else:
                    cmds.setAttr("{}.visibility".format(shape), True)
                    changes.append("enabled shape visibility ({})".format(shape))
            else:
                print("[ok] {}.visibility is on".format(shape))

    # ---------- 3. localScale of zero ----------
    for shape in shapes:
        if cmds.objectType(shape) == "locator":
            try:
                scale = cmds.getAttr("{}.localScale".format(shape))[0]
                if scale == (0.0, 0.0, 0.0):
                    cmds.setAttr("{}.localScaleX".format(shape), 1)
                    cmds.setAttr("{}.localScaleY".format(shape), 1)
                    cmds.setAttr("{}.localScaleZ".format(shape), 1)
                    changes.append("{} localScale was 0, reset to 1,1,1".format(shape))
                else:
                    print("[ok] {}.localScale is fine: {}".format(shape, scale))
            except Exception as e:
                print("[warn] cannot read {}.localScale: {}".format(shape, e))

    # ---------- 4. Drawing overrides ----------
    for node in [obj] + shapes:
        if cmds.attributeQuery("overrideEnabled", node=node, exists=True):
            if cmds.getAttr("{}.overrideEnabled".format(node)):
                if not cmds.getAttr("{}.overrideVisibility".format(node)):
                    cmds.setAttr("{}.overrideVisibility".format(node), True)
                    changes.append("{} override visibility was off, "
                                   "enabled".format(node))
                if cmds.getAttr("{}.overrideDisplayType".format(node)) == 2:
                    print("[info] {} override display type is Reference".format(node))
                if cmds.getAttr("{}.overrideRGBColors".format(node)):
                    rgb = cmds.getAttr("{}.overrideColorRGB".format(node))[0]
                    print("[info] {} override color RGB = {}".format(node, rgb))
                else:
                    idx = cmds.getAttr("{}.overrideColor".format(node))
                    print("[info] {} override color index = {} ({})".format(
                        node, idx, COLOR_INDEX_NAMES.get(idx, "?")))

    # ---------- 5. Template attribute ----------
    for node in [obj] + shapes:
        if cmds.attributeQuery("template", node=node, exists=True):
            if cmds.getAttr("{}.template".format(node)):
                cmds.setAttr("{}.template".format(node), False)
                changes.append("{} was templated (unselectable / wireframe), "
                               "disabled".format(node))

    # ---------- 6. Walk up and check parent visibility ----------
    current = obj
    while True:
        parent = cmds.listRelatives(current, parent=True, fullPath=True)
        if not parent:
            break
        parent = parent[0]
        if cmds.attributeQuery("visibility", node=parent, exists=True):
            if not cmds.getAttr("{}.visibility".format(parent)):
                if cmds.getAttr("{}.visibility".format(parent), lock=True):
                    print("[fail] parent {} visibility is off and locked; "
                          "fix manually".format(parent))
                else:
                    cmds.setAttr("{}.visibility".format(parent), True)
                    changes.append("parent {} visibility was off, "
                                   "enabled".format(parent))
            else:
                print("[ok] parent {}.visibility is on".format(parent))
        current = parent

    # ---------- 7. Display layers ----------
    layers = cmds.listConnections(obj, type="displayLayer") or []
    for shape in shapes:
        layers += cmds.listConnections(shape, type="displayLayer") or []
    layers = list(set(layers))
    for layer in layers:
        if layer == "defaultLayer":
            continue
        if not cmds.getAttr("{}.visibility".format(layer)):
            cmds.setAttr("{}.visibility".format(layer), True)
            changes.append("display layer '{}' was hidden, enabled".format(layer))
        else:
            print("[ok] display layer '{}' is visible".format(layer))
        if cmds.getAttr("{}.displayType".format(layer)) == 1:
            print("[info] display layer '{}' is in Template mode "
                  "(unselectable)".format(layer))

    # ---------- 8. Isolate Select ----------
    panel = cmds.getPanel(withFocus=True)
    if panel and cmds.getPanel(typeOf=panel) == "modelPanel":
        if cmds.isolateSelect(panel, query=True, state=True):
            print("[warn] Isolate Select is on in panel {}. If {} is not in the "
                  "isolate set it will stay hidden.".format(panel, obj))

    # ---------- Extra: viewport locator display flag ----------
    for mp in cmds.getPanel(type="modelPanel") or []:
        if not cmds.modelEditor(mp, query=True, locators=True):
            cmds.modelEditor(mp, edit=True, locators=True)
            changes.append("viewport '{}' had Show Locators off, "
                           "enabled".format(mp))

    # ---------- Summary ----------
    print("-" * 50)
    if changes:
        print("Fixed {} item(s):".format(len(changes)))
        for c in changes:
            print("   - {}".format(c))
    else:
        print("Nothing auto-fixable was found.")
        print("If it is still not visible, possible causes:")
        print("   1. The locator is outside the camera view or behind other geo")
        print("   2. Another object with the same name exists elsewhere "
              "(different namespace)")
        print("   3. It is not part of the viewport's Isolate Select set")
    print("=" * 50)


# ==================================================================
#  UI
# ==================================================================
WINDOW_NAME = "locatorCheckerWin"


def show_locator_checker_ui():
    """Open the Locator Checker panel with compact Animbot color swatches."""
    if cmds.window(WINDOW_NAME, exists=True):
        cmds.deleteUI(WINDOW_NAME)

    win = cmds.window(WINDOW_NAME, title="Locator Checker", widthHeight=(360, 440),
                      sizeable=True)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=6,
                      columnOffset=("both", 10))

    cmds.separator(height=8, style="none")
    cmds.text(label="Acts on the current selection", align="left",
              font="boldLabelFont")
    cmds.separator(height=8, style="in")

    cmds.text(label="Size (localScale)", align="left")
    size_field = cmds.floatSliderGrp(
        field=True, minValue=5.0, maxValue=10.0,
        fieldMinValue=0.001, fieldMaxValue=10000.0,
        value=5.0, step=0.1, precision=2,
        columnWidth3=(0, 60, 220), columnAlign=(1, "left"))

    cmds.rowLayout(numberOfColumns=6, columnWidth6=(55,) * 6)
    for preset in (5, 6, 7, 8, 9, 10):
        cmds.button(label=str(preset), height=22,
                    command=lambda x, p=preset, f=size_field: (
                        cmds.floatSliderGrp(f, edit=True, value=float(p)),
                        set_locator_size(float(p))))
    cmds.setParent("..")

    cmds.button(label="Apply Size", height=28, backgroundColor=(0.35, 0.45, 0.55),
                command=lambda x: set_locator_size(
                    cmds.floatSliderGrp(size_field, query=True, value=True)))

    cmds.separator(height=10, style="in")
    cmds.text(label="Color", align="left")

    state = {"color": ANIMBOT_PALETTE[0][1]}
    current_preview = [None]
    current_label = [None]

    def _select_color(hex_color, apply_now=True):
        state["color"] = hex_color
        rgb = _hex_to_rgb(hex_color)
        cmds.canvas(current_preview[0], edit=True, rgbValue=rgb)
        cmds.text(current_label[0], edit=True, label="Current: {}".format(hex_color))
        if apply_now:
            set_locator_color(hex_color, verbose=True)

    cmds.rowColumnLayout(numberOfColumns=9,
                         columnWidth=[(column, 26) for column in range(1, 10)],
                         rowSpacing=(1, 3),
                         columnSpacing=[(column, 2) for column in range(2, 10)])
    for name, hex_color in ANIMBOT_PALETTE:
        r, g, b = _hex_to_rgb(hex_color)
        cmds.iconTextButton(
            style="textOnly", label="", width=20, height=20,
            backgroundColor=(r, g, b),
            annotation="{} - {}".format(name, hex_color),
            command=lambda unused, color=hex_color: _select_color(color))
    cmds.setParent("..")

    cmds.rowLayout(numberOfColumns=2, columnWidth2=(100, 240),
                   columnAlign2=("left", "left"),
                   columnAttach2=("both", "both"))
    current_label[0] = cmds.text(label="Current: {}".format(state["color"]))
    current_preview[0] = cmds.canvas(width=220, height=20,
                                     rgbValue=_hex_to_rgb(state["color"]))
    cmds.setParent("..")

    cmds.button(label="Apply Color", height=28, backgroundColor=(0.55, 0.45, 0.35),
                command=lambda unused: set_locator_color(state["color"]))
    cmds.button(label="Clear Color Override", height=24,
                command=lambda unused: set_locator_color(-1))

    cmds.separator(height=10, style="in")
    cmds.button(label="Check & Fix Visibility", height=34,
                backgroundColor=(0.35, 0.55, 0.35),
                command=lambda unused: fix_locator_visibility())
    cmds.button(label="Check & Fix + Apply Size and Color", height=30,
                command=lambda unused: fix_locator_visibility(
                    size=cmds.floatSliderGrp(size_field, query=True, value=True),
                    color=state["color"]))

    cmds.separator(height=8, style="none")
    _select_color(state["color"], apply_now=False)
    cmds.showWindow(win)
    return win


# ==================================================================
# Entry point
# ==================================================================
if __name__ == "__main__":
    show_locator_checker_ui()
