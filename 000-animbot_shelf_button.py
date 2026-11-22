"""
animbot_shelf_button.py

Maya 2025 / Python 3

Purpose
    Create a shelf button that launches animBot on the currently active shelf.
    Safe to re-run: an existing animBot button on that shelf is reused.

Notes
    - animBot must already be installed and importable.
    - The button lands on the ACTIVE shelf tab, so switch to the shelf you
      want first.
    - Maya only saves shelves on a clean quit (or Shelf Editor > Save All
      Shelves).
    - imageOverlayLabel is capped at around 6 characters.

Usage
    Paste into the Script Editor (Python tab) and execute.
"""

from maya import cmds, mel

BUTTON_LABEL = "animBot"
BUTTON_COMMAND = "import animBot; animBot.launch()"
BUTTON_IMAGE = "pythonFamily.png"   # replace with your own 32x32 icon name


def create_animbot_shelf_button():
    """Add (or refresh) an animBot launcher button on the active shelf."""
    shelf_top = mel.eval('$tmp = $gShelfTopLevel')
    current = cmds.tabLayout(shelf_top, query=True, selectTab=True)

    # --- reuse the button if it already exists on this shelf ---------------
    for child in cmds.shelfLayout(current, query=True, childArray=True) or []:
        if not cmds.shelfButton(child, exists=True):
            continue
        if cmds.shelfButton(child, query=True, label=True) == BUTTON_LABEL:
            cmds.shelfButton(child, edit=True, command=BUTTON_COMMAND)
            print("[ok] animBot button already on '{0}', refreshed.".format(
                current))
            return child

    button = cmds.shelfButton(
        parent=current,
        label=BUTTON_LABEL,
        annotation="Launch animBot",
        imageOverlayLabel="aBot",
        image=BUTTON_IMAGE,
        sourceType="python",
        command=BUTTON_COMMAND,
    )
    print("[ok] animBot button created on shelf '{0}'.".format(current))
    return button


if __name__ == "__main__":
    create_animbot_shelf_button()
