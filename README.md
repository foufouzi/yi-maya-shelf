# Maya Shelf Tools

A personal collection of animation-pipeline tools for **Autodesk Maya 2025**, written in Python 3 with `maya.cmds` and PySide6.

Every script is a standalone file with no dependencies beyond Maya itself. Each one is safe to import: nothing runs on import, and the actual work happens inside an explicit entry function or under `if __name__ == "__main__":`.

## Repository layout

Tools live flat in the repository root and are numbered:

```
NNN-tool_name.py      # first version of tool NNN
NNN.R-tool_name.py    # revision R of tool NNN (the highest revision is the current one)
ignore/               # superseded revisions, kept for reference only
```

For example, `009.6-locator_checker.py` is the sixth revision of tool 009; revisions `009` to `009.5` are archived in `ignore/`.

## Installation

Because the filenames start with a number and contain a hyphen, they cannot be imported by name as they are. There are two ways to use them.

### Option A: run the file directly (no renaming)

Running a file this way executes its `__main__` block, which opens the tool's UI (or performs its default action). Put this in a Python shelf button or run it in the Script Editor:

```python
import runpy
runpy.run_path(r"C:/path/to/yi-maya-shelf/012-merge_to_world.py", run_name="__main__")
```

### Option B: rename and import as a module

Copy a file into your Maya scripts folder and drop the number prefix, so `012-merge_to_world.py` becomes `merge_to_world.py`:

| OS      | Scripts folder                                        |
|---------|-------------------------------------------------------|
| Windows | `C:/Users/<you>/Documents/maya/2025/scripts/`          |
| macOS   | `~/Library/Preferences/Autodesk/maya/2025/scripts/`    |
| Linux   | `~/maya/2025/scripts/`                                 |

Then, in the Script Editor (Python tab):

```python
import merge_to_world as mtw
mtw.show_merge_to_world_ui()
```

This gives you access to each tool's headless functions (listed below) in addition to the UI.

### Shelf buttons

Paste either snippet into a Python-type shelf button. Note that Maya only writes shelves to disk on a clean quit, or when you use **Shelf Editor → Save All Shelves**.

## Tools

| #   | File | Entry point | Description |
|-----|------|-------------|-------------|
| 000 | `000-animbot_shelf_button.py` | `create_animbot_shelf_button()` | Adds an animBot launcher button to the active shelf. Safe to re-run: an existing button is reused instead of duplicated. Requires animBot to be installed. |
| 001 | `001.1-icon_generator.py` | `show()` | PySide6 UI for making 64×64 PNG shelf icons: text, background/text colours (palette grid or system picker), font size, margin, live preview, and saving straight into Maya's user icons folder. |
| 002 | `002-add_camera_gate.py` | — | See the note under [Known issues](#known-issues). |
| 003 | `003.2-curve_top_always.py` | `show()` / `set_always_on_top()` | Makes the shapes of selected controls always draw on top of geometry in Viewport 2.0, so controls inside a mesh (e.g. IK pole vectors) never get buried. Restores the override colour that `overrideEnabled` resets, either automatically from the name (`L` → sky blue, `R` → muted red, centre → pale yellow) or manually via palette, colour dialog or hex value. |
| 004 | `004-anti_clipping_cluster.py` | `toggle_anti_clipping_cluster()` | Select body vertices that poke through clothing and run it: builds a hidden cluster that scales them 30% inward. Run again (no selection needed) to remove it. |
| 005 | `005-clean_unknown_nodes.py` | `report_unknown()` / `clean_unknown()` / `optimize_scene()` | Finds and removes unknown nodes and unknown plugin requirements that prevent saving a scene as Maya ASCII (`.ma`). `report_unknown()` only inspects and changes nothing. |
| 006 | `006-copy_animation_key_to_json.py` | `show_anim_key_transfer_ui()` | Exports the keys selected in the Graph Editor to a JSON file and imports them into another scene. Frame numbers are preserved, namespaces are stripped when matching, and import is a single undo step. Options: clear existing keys within each imported range, and apply to selected nodes only. |
| 007 | `007-custom_axis_orient.py` | `show_custom_axis_ui()` / `orient_from()` / `reset_orient()` | Sets the Move (and optionally Rotate/Scale) manipulator to *Custom axis orientation*, aligned to the last-selected object's world rotation. Re-run whenever Maya drops back to Object mode. |
| 008 | `008-bake_to_selected.py` | `bake_to_selected()` | Select A (source), then B (target): bakes A's world-space animation onto B over the frame range via a temporary `parentConstraint`, then cleans up. Locked channels on B are skipped with a warning. |
| 009 | `009.6-locator_checker.py` | `show_locator_checker_ui()` / `fix_locator_visibility()` | Diagnoses and fixes locators (or any transform) that exist but don't show in the viewport: visibility, `localScale`, drawing overrides, template state, parent chain, display layers, isolate select, and *Show → Locators*. Also sets locator size and override colour (index 0–31 or exact RGB/hex). PySide6 UI. |
| 010 | `010-bake_locators_to_temp.py` | `show()` | UI tool that bakes the world-space transform of the selected locators, including constraint chains inherited from parent groups, onto a new `temp_locator`, with an adjustable frame range. |
| 011 | `011-camera_sequencer_builder.py` | `show_camera_sequencer_builder_ui()` | Builds Camera Sequencer shots from the selected cameras, using each camera's own key range (falls back to the playback range). Checks and fixes the non-unit scale that causes *"Cannot create ubercam. Transform … has been scaled"*, and can create the ubercam. Headless: `check_camera_scale()`, `fix_camera_scale()`, `build_shots_from_cameras()`. |
| 012 | `012-merge_to_world.py` | `show_merge_to_world_ui()` / `merge_to_world()` | Bakes an object's motion combined with all its animated parent groups into a single world-space animation on a new node parented to the world. Works on cameras, locators, joints, meshes, curves, groups, etc. Animated shape attributes (e.g. focal length) are baked too. Can optionally delete the source group. |

## Notes and caveats

- **Maya version.** Written and tested on Maya 2025 (Python 3, PySide6). The PySide6-based tools (`icon_generator`, `curve_top_always`, `locator_checker`) import `PySide6` / `shiboken6` and won't run on Maya 2023 or earlier unless the imports are changed to `PySide2` / `shiboken2`.
- **`anti_clipping_cluster`** only hides clipping visually; it does not touch skin weights. Use it for reviews and playblasts, not as a permanent rig fix.
- **`clean_unknown_nodes`** deletes data permanently. If an unknown node belongs to a plugin that *should* be present (e.g. a Redshift shader), load that plugin and re-save instead of cleaning. Run `report_unknown()` first.
- **`camera_sequencer_builder`**: *Fix Scale* hard-resets scale to 1. If the framing relied on scale, the composition will change, so run *Check Scale* first.
- **`bake_to_selected`**: if the target has an incoming `offsetParentMatrix` connection, the baked values are expressed in that parent space, so the position looks right but the numbers differ from the source's world translate.
- **`merge_to_world`** bakes transform animation only. Deforming geometry (skinCluster, blendShape, lattice) is not transferred.

## Known issues

- `002-add_camera_gate.py` currently contains an older copy of the Locator Checker rather than a camera-gate tool. Use `009.6-locator_checker.py` for locator work until this file is replaced.

## License

MIT. See [LICENSE](LICENSE).
