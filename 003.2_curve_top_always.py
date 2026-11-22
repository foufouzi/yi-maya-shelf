"""
control_always_on_top.py

Maya 2025 / Python 3 / PySide6

Purpose:
    Force the shape nodes of the currently selected control(s) to always
    draw on top of geometry in Viewport 2.0, so controls near or inside
    a mesh (e.g. IK pole vector controls) never get visually buried.

    Also restores the override color after enabling overrideEnabled,
    since turning overrideEnabled on resets the display color. Colors
    use the same 27-swatch palette as the Shelf Icon Generator (RGB
    override). Two color modes are available:
        - Auto: picked from the control's name
              token "L" (e.g. L_leg_ik_control)  -> Sky Blue
              token "R" (e.g. R_leg_ik_control)  -> Muted Red
              anything else / center controls    -> Pale Yellow
        - Manual: any palette swatch, the system color dialog, or any
          hex value typed into the hex field.

Usage:
    Plain function call (no UI):

        import control_always_on_top as caot
        caot.set_always_on_top()                        # auto color
        caot.set_always_on_top(color="#54A4CE")         # hex RGB
        caot.set_always_on_top(color=(1.0, 0.5, 0.2))   # 0-1 RGB
        caot.set_always_on_top(color_index=13)          # legacy index mode

    UI panel / shelf button command:

        import control_always_on_top as caot
        import importlib
        importlib.reload(caot)
        caot.show()

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

import builtins
import traceback

import maya.cmds as cmds
import maya.OpenMayaUI as omui
from shiboken6 import wrapInstance
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QLineEdit, QTextEdit, QColorDialog, QFrame, QGroupBox, QRadioButton,
    QButtonGroup,
)


def get_maya_main_window():
    """Returns Maya's main window as a QWidget for dialog parenting."""
    main_window_ptr = omui.MQtUtil.mainWindow()
    if main_window_ptr is None:
        return None
    return wrapInstance(int(main_window_ptr), QDialog).window()


# ==========================================
# COLOR PALETTE (same as icon_generator.py)
# ==========================================
COLOR_PALETTE = [
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

SIDE_COLORS = {"L": "#54A4CE", "R": "#BA5251"}
DEFAULT_COLOR = "#F2E66C"


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
# UI (same look as icon_generator.py)
# ---------------------------------------------------------------------------

class ColorSwatchButton(QPushButton):
    """A small square button showing a color, used for both palette swatches
    and the current-color indicator next to the color field."""

    def __init__(self, hex_color, size=22, tooltip=None):
        super().__init__()
        self.setFixedSize(size, size)
        self.set_color(hex_color)
        if tooltip:
            self.setToolTip(tooltip)

    def set_color(self, hex_color):
        self.hex_color = hex_color
        self.setStyleSheet(
            "background-color: {0}; border: 1px solid #111111; border-radius: 3px;".format(
                hex_color
            )
        )


class ControlAlwaysOnTopUI(QDialog):
    """Settings window for Control Always On Top."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Control Always On Top")
        self.resize(360, 460)

        self.manual_color = "#BA5251"

        main_layout = QVBoxLayout(self)

        intro = QLabel(
            "Select control(s) in the viewport, choose a color mode, then Apply."
        )
        intro.setWordWrap(True)
        main_layout.addWidget(intro)

        # --- Color mode ---------------------------------------------------
        main_layout.addWidget(QLabel("Color Mode:"))
        mode_row = QHBoxLayout()
        self.auto_radio = QRadioButton("Auto (by L_/R_ name)")
        self.manual_radio = QRadioButton("Manual (pick below)")
        self.auto_radio.setChecked(True)
        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.auto_radio)
        self.mode_group.addButton(self.manual_radio)
        mode_row.addWidget(self.auto_radio)
        mode_row.addWidget(self.manual_radio)
        main_layout.addLayout(mode_row)

        # --- Control color group -----------------------------------------
        color_group = QGroupBox("Control Color")
        color_layout = QVBoxLayout(color_group)

        current_row = QHBoxLayout()
        self.current_swatch = ColorSwatchButton(self.manual_color, size=28)
        self.current_swatch.clicked.connect(self.pick_color)
        self.hex_field = QLineEdit(self.manual_color)
        self.hex_field.editingFinished.connect(self.on_hex_edited)
        current_row.addWidget(self.current_swatch)
        current_row.addWidget(self.hex_field)
        color_layout.addLayout(current_row)

        color_layout.addWidget(self.build_palette_grid())
        main_layout.addWidget(color_group)

        # --- Apply --------------------------------------------------------
        apply_btn = QPushButton("Apply to Selection")
        apply_btn.setStyleSheet("font-weight: bold; padding: 6px;")
        apply_btn.clicked.connect(self.on_apply)
        main_layout.addWidget(apply_btn)

        # --- Log ----------------------------------------------------------
        self.log_field = QTextEdit()
        self.log_field.setReadOnly(True)
        self.log_field.setFixedHeight(110)
        main_layout.addWidget(self.log_field)

    def build_palette_grid(self):
        """Builds a grid of clickable palette swatches."""
        frame = QFrame()
        grid = QGridLayout(frame)
        grid.setSpacing(4)
        grid.setContentsMargins(0, 4, 0, 4)

        columns = 9
        for index, (name, hex_color) in enumerate(COLOR_PALETTE):
            row = index // columns
            col = index % columns
            swatch = ColorSwatchButton(
                hex_color, size=20, tooltip="{0}\n{1}".format(name, hex_color)
            )
            swatch.clicked.connect(lambda checked=False, c=hex_color: self.set_color(c))
            grid.addWidget(swatch, row, col)

        return frame

    def pick_color(self):
        color = QColorDialog.getColor(QColor(self.manual_color), self, "Choose Color")
        if color.isValid():
            self.set_color(color.name())

    def set_color(self, hex_color):
        hex_color = hex_color.upper()
        self.manual_color = hex_color
        self.current_swatch.set_color(hex_color)
        self.hex_field.setText(hex_color)
        # picking a color implies the user wants manual mode
        self.manual_radio.setChecked(True)

    def on_hex_edited(self):
        hex_color = self.hex_field.text().strip()
        if not hex_color.startswith("#"):
            hex_color = "#" + hex_color
        if QColor(hex_color).isValid() and hex_to_rgb(hex_color) is not None:
            self.set_color(hex_color)
        else:
            self.hex_field.setText(self.manual_color)

    def on_apply(self):
        try:
            color = None if self.auto_radio.isChecked() else self.manual_color

            objects = cmds.ls(selection=True, long=True)
            if not objects:
                cmds.warning("[control_always_on_top] Nothing selected.")
                self.append_log("[warn] Nothing selected.")
                return

            lines = []

            def _capture_print(*args, **kwargs):
                lines.append(" ".join(str(a) for a in args))

            real_print = builtins.print
            builtins.print = _capture_print
            try:
                set_always_on_top(objects=objects, color=color, verbose=True)
            finally:
                builtins.print = real_print

            self.append_log("\n".join(lines) if lines else "[warn] No shapes processed.")
        except Exception:
            print("[fail] Control Always On Top: error while applying.")
            traceback.print_exc()

    def append_log(self, text):
        self.log_field.append(text)


# ==========================================
# LAUNCH
# ==========================================
_control_always_on_top_window = None


def show():
    """Open the Control Always On Top window."""
    global _control_always_on_top_window
    try:
        if _control_always_on_top_window is not None:
            _control_always_on_top_window.close()
            _control_always_on_top_window.deleteLater()
    except RuntimeError:
        pass
    _control_always_on_top_window = ControlAlwaysOnTopUI(parent=get_maya_main_window())
    _control_always_on_top_window.show()
    return _control_always_on_top_window


# Backward compatible launcher name
show_control_always_on_top_ui = show


if __name__ == "__main__":
    show()
