"""
icon_generator.py

Maya 2025 / Python 3 / PySide6

Purpose
    Generate custom Maya shelf button icons (64x64 PNG). Type the icon text,
    set a file name, pick background / text colors from a palette grid or the
    system color dialog, adjust font size and margin, preview, then save the
    PNG straight into Maya's user icons folder.

Usage
    import icon_generator as ig
    ig.show()
"""

import os
import traceback
import maya.cmds as cmds
import maya.OpenMayaUI as omui
from shiboken6 import wrapInstance
from PySide6.QtGui import QImage, QPainter, QFont, QColor, QTextOption, QPixmap
from PySide6.QtCore import Qt, QRectF
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QLineEdit, QTextEdit, QSpinBox, QColorDialog, QFrame, QGroupBox
)


def get_maya_main_window():
    """Returns Maya's main window as a QWidget, so our dialogs can be
    properly parented instead of floating as detached top-level windows."""
    main_window_ptr = omui.MQtUtil.mainWindow()
    if main_window_ptr is None:
        return None
    return wrapInstance(int(main_window_ptr), QDialog).window()


# ==========================================
# COLOR PALETTE
# ==========================================
COLOR_PALETTE = [
    ("Dark Charcoal Gray", "#3A3A3A"),
    ("Very Dark Gray", "#2D2D2D"),
    ("Off-Black", "#222222"),
    ("Light Salmon Pink", "#EFA1A4"),
    ("Muted Red", "#C65A5C"),
    ("Deep Terracotta", "#893B3E"),
    ("Peach / Apricot", "#F5B28F"),
    ("Burnt Orange", "#DE7443"),
    ("Brown", "#7E4421"),
    ("Pale Yellow", "#F1EA7E"),
    ("Olive / Mustard Yellow", "#C5BA3E"),
    ("Dark Olive Green", "#7C801B"),
    ("Mint / Light Green", "#83E693"),
    ("Medium Green", "#4EAC61"),
    ("Forest Green", "#367943"),
    ("Pale Ice Blue", "#A0ECFA"),
    ("Teal", "#45A5B8"),
    ("Deep Teal / Slate", "#387B8D"),
    ("Light Sky Blue", "#BCE0F7"),
    ("Sky Blue", "#59A2D6"),
    ("Steel Blue", "#33638B"),
    ("Pale Lavender", "#DECFF6"),
    ("Lavender", "#A795DC"),
    ("Muted Purple", "#665B86"),
    ("Light Pink", "#F7C4EB"),
    ("Orchid Pink", "#D586CE"),
    ("Plum / Dark Purple", "#81457A"),
]


class MayaIconPreviewDialog(QDialog):
    """Renders the icon at 64x64 and lets the user save it or go back."""

    def __init__(self, text, bg_color, text_color, font_size, margin_px, file_name, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Icon Preview")
        self.resize(200, 220)

        self.text = text
        self.bg_color = bg_color
        self.text_color = text_color
        self.font_size = font_size
        self.margin_px = margin_px
        self.file_name = file_name

        self.image = self.generate_image()

        layout = QVBoxLayout(self)

        self.preview_label = QLabel()
        pixmap = QPixmap.fromImage(self.image)
        self.preview_label.setPixmap(pixmap.scaled(128, 128, Qt.KeepAspectRatio, Qt.FastTransformation))
        self.preview_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.preview_label)

        info_label = QLabel(f"Size: 64x64 | Margin: {margin_px}px")
        info_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(info_label)

        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Save Icon")
        save_btn.clicked.connect(self.save_and_close)
        back_btn = QPushButton("Back")
        back_btn.clicked.connect(self.reject)

        btn_layout.addWidget(back_btn)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)

    def generate_image(self):
        canvas_size = 64
        image = QImage(canvas_size, canvas_size, QImage.Format_ARGB32)
        image.fill(QColor(self.bg_color))

        painter = QPainter(image)
        painter.setRenderHint(QPainter.TextAntialiasing)

        font = QFont("Arial", self.font_size, QFont.Bold)
        painter.setFont(font)
        painter.setPen(QColor(self.text_color))

        text_option = QTextOption()
        text_option.setAlignment(Qt.AlignCenter)
        text_option.setWrapMode(QTextOption.WordWrap)

        safe_width = canvas_size - (self.margin_px * 2)
        safe_height = canvas_size - (self.margin_px * 2)
        margin_rect = QRectF(self.margin_px, self.margin_px, safe_width, safe_height)

        painter.drawText(margin_rect, self.text, text_option)
        painter.end()
        return image

    def save_and_close(self):
        pref_dir = cmds.internalVar(userPrefDir=True)
        icons_dir = os.path.join(pref_dir, "icons")
        if not os.path.exists(icons_dir):
            os.makedirs(icons_dir)

        save_path = os.path.join(icons_dir, self.file_name)
        self.image.save(save_path, "PNG")
        print(f"// High-Res Icon Saved! Path: {save_path} //")
        self.accept()


class ColorSwatchButton(QPushButton):
    """A small square button showing a color, used for both palette swatches
    and the current-color indicator next to each color field."""

    def __init__(self, hex_color, size=22, tooltip=None):
        super().__init__()
        self.setFixedSize(size, size)
        self.set_color(hex_color)
        if tooltip:
            self.setToolTip(tooltip)

    def set_color(self, hex_color):
        self.hex_color = hex_color
        self.setStyleSheet(
            f"background-color: {hex_color}; border: 1px solid #111111; border-radius: 3px;"
        )


class IconGeneratorUI(QDialog):
    """Settings window for the Maya shelf icon generator.

    Lets you set the icon text, file name, colors (via palette or color
    picker), font size, and margin, then opens the preview/save dialog.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Maya Shelf Icon Generator")
        self.resize(360, 520)

        self.bg_color = "#202020"
        self.text_color = "#EFA1A4"

        main_layout = QVBoxLayout(self)

        main_layout.addWidget(QLabel("Icon Text (Enter for line break):"))
        self.text_edit = QTextEdit()
        self.text_edit.setPlainText("fix\nholes")
        self.text_edit.setFixedHeight(60)
        main_layout.addWidget(self.text_edit)

        main_layout.addWidget(QLabel("File Name:"))
        self.file_name_field = QLineEdit("fix_hole.png")
        main_layout.addWidget(self.file_name_field)

        bg_group = QGroupBox("Background Color")
        bg_layout = QVBoxLayout(bg_group)

        bg_current_row = QHBoxLayout()
        self.bg_current_swatch = ColorSwatchButton(self.bg_color, size=28)
        self.bg_current_swatch.clicked.connect(lambda: self.pick_color("bg"))
        self.bg_hex_field = QLineEdit(self.bg_color)
        self.bg_hex_field.editingFinished.connect(self.on_bg_hex_edited)
        bg_current_row.addWidget(self.bg_current_swatch)
        bg_current_row.addWidget(self.bg_hex_field)
        bg_layout.addLayout(bg_current_row)

        bg_layout.addWidget(self.build_palette_grid("bg"))
        main_layout.addWidget(bg_group)

        text_group = QGroupBox("Text Color")
        text_layout = QVBoxLayout(text_group)

        text_current_row = QHBoxLayout()
        self.text_current_swatch = ColorSwatchButton(self.text_color, size=28)
        self.text_current_swatch.clicked.connect(lambda: self.pick_color("text"))
        self.text_hex_field = QLineEdit(self.text_color)
        self.text_hex_field.editingFinished.connect(self.on_text_hex_edited)
        text_current_row.addWidget(self.text_current_swatch)
        text_current_row.addWidget(self.text_hex_field)
        text_layout.addLayout(text_current_row)

        text_layout.addWidget(self.build_palette_grid("text"))
        main_layout.addWidget(text_group)

        size_row = QHBoxLayout()

        size_row.addWidget(QLabel("Font Size:"))
        self.font_size_field = QSpinBox()
        self.font_size_field.setRange(1, 64)
        self.font_size_field.setValue(15)
        size_row.addWidget(self.font_size_field)

        size_row.addWidget(QLabel("Margin (px):"))
        self.margin_field = QSpinBox()
        self.margin_field.setRange(0, 32)
        self.margin_field.setValue(2)
        size_row.addWidget(self.margin_field)

        main_layout.addLayout(size_row)

        preview_btn = QPushButton("Preview Icon")
        preview_btn.setStyleSheet("font-weight: bold; padding: 6px;")
        preview_btn.clicked.connect(self.open_preview)
        main_layout.addWidget(preview_btn)

    def build_palette_grid(self, target):
        """Builds a grid of clickable palette swatches for 'bg' or 'text'."""
        frame = QFrame()
        grid = QGridLayout(frame)
        grid.setSpacing(4)
        grid.setContentsMargins(0, 4, 0, 4)

        columns = 9
        for index, (name, hex_color) in enumerate(COLOR_PALETTE):
            row = index // columns
            col = index % columns
            swatch = ColorSwatchButton(hex_color, size=20, tooltip=f"{name}\n{hex_color}")
            swatch.clicked.connect(lambda checked=False, c=hex_color, t=target: self.set_color(t, c))
            grid.addWidget(swatch, row, col)

        return frame

    def pick_color(self, target):
        current = self.bg_color if target == "bg" else self.text_color
        color = QColorDialog.getColor(QColor(current), self, "Choose Color")
        if color.isValid():
            self.set_color(target, color.name())

    def set_color(self, target, hex_color):
        if target == "bg":
            self.bg_color = hex_color
            self.bg_current_swatch.set_color(hex_color)
            self.bg_hex_field.setText(hex_color)
        else:
            self.text_color = hex_color
            self.text_current_swatch.set_color(hex_color)
            self.text_hex_field.setText(hex_color)

    def on_bg_hex_edited(self):
        hex_color = self.bg_hex_field.text().strip()
        if QColor(hex_color).isValid():
            self.set_color("bg", hex_color)
        else:
            self.bg_hex_field.setText(self.bg_color)

    def on_text_hex_edited(self):
        hex_color = self.text_hex_field.text().strip()
        if QColor(hex_color).isValid():
            self.set_color("text", hex_color)
        else:
            self.text_hex_field.setText(self.text_color)

    def open_preview(self):
        try:
            text = self.text_edit.toPlainText()
            file_name = self.file_name_field.text().strip()

            if not text:
                cmds.warning("Icon text cannot be empty")
                return
            if not file_name:
                cmds.warning("File name cannot be empty")
                return
            if not file_name.lower().endswith(".png"):
                file_name += ".png"

            preview_dialog = MayaIconPreviewDialog(
                text=text,
                bg_color=self.bg_color,
                text_color=self.text_color,
                font_size=self.font_size_field.value(),
                margin_px=self.margin_field.value(),
                file_name=file_name,
                parent=self
            )
            preview_dialog.raise_()
            preview_dialog.activateWindow()
            preview_dialog.exec_()
        except Exception:
            print("// Icon Generator: error while opening preview //")
            traceback.print_exc()


# ==========================================
# LAUNCH
# ==========================================
_icon_generator_window = None


def show():
    """Open the Icon Generator settings window."""
    global _icon_generator_window
    _icon_generator_window = IconGeneratorUI(parent=get_maya_main_window())
    _icon_generator_window.show()
    return _icon_generator_window


if __name__ == "__main__":
    show()
