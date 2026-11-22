# Maya Shelf Tools

A collection of standalone tools for animation and rigging workflows in **Autodesk Maya 2025**. The tools are written in Python 3 and use Maya's `maya.cmds` API; selected tools also use PySide6 for their interfaces.

Each script is designed to be run independently. Importing a tool does not execute its main action; run its documented entry point or execute the file as a script.

## Requirements

- Autodesk Maya 2025
- Python 3 included with Maya
- PySide6 for tools that provide a PySide6 interface (included with Maya 2025)
- animBot installed to use the animBot shelf launcher (`000-animbot_shelf_button.py`)

## Repository layout

Tool scripts are stored in the repository root and use numbered filenames:

```text
NNN-tool_name.py       # Initial version of tool NNN
NNN.R-tool_name.py     # Revision R of tool NNN
ignore/                # Superseded revisions kept for reference
```

When multiple revisions exist, the highest revision number is the current version. For example, `009.6-locator_checker.py` is the current revision of tool 009; earlier revisions are archived in `ignore/`.

## Installation and use

The numbered, hyphenated filenames are not directly importable as regular Python module names. You can run a script in place, or copy and rename it before importing.

### Run a script in place

In Maya's Python Script Editor or a Python shelf button, use `runpy` and the full path to the script. Replace the example path with the location of your local checkout:

```python
import runpy
runpy.run_path(r"C:/path/to/yi-maya-shelf/012-merge_to_world.py", run_name="__main__")
```

This runs the script's `__main__` block, which typically opens its UI or runs its default action.

### Import a renamed script

Copy a script into your Maya scripts directory and remove the numeric prefix and hyphen from its filename. For example, rename `012-merge_to_world.py` to `merge_to_world.py`.

| Operating system | Maya scripts directory |
| --- | --- |
| Windows | `C:/Users/<you>/Documents/maya/2025/scripts/` |
| macOS | `~/Library/Preferences/Autodesk/maya/2025/scripts/` |
| Linux | `~/maya/2025/scripts/` |

Then import the module and call its UI or other entry point from Maya's Python Script Editor:

```python
import merge_to_world as mtw
mtw.show_merge_to_world_ui()
```

Importing the module also lets you call its non-UI functions. Refer to the tool catalog below for available entry points.

### Add a shelf button

The run-in-place snippet above can be used in a Python-type Maya shelf button. Maya saves shelf changes when you quit cleanly or use **Shelf Editor → Save All Shelves**.

## Tool catalog

| ID | Script | Entry point(s) | Description |
| --- | --- | --- | --- |
| 000 | [`000-animbot_shelf_button.py`](https://github.com/foufouzi/yi-maya-shelf/blob/main/000-animbot_shelf_button.py) | `create_animbot_shelf_button()` | Adds an animBot launcher to the active shelf. Re-running the function reuses an existing button rather than creating duplicates. Requires animBot. |
| 001 | `001.1-icon_generator.py` | `show()` | Creates 64 × 64 PNG shelf icons with text, customizable colours, font size, margins, and a live preview. Can save icons directly to Maya's user icons folder. |
| 002 | `002-add_camera_gate.py` | — | See [Known issues](#known-issues). |
| 003 | `003.2-curve_top_always.py` | `show()` / `set_always_on_top()` | Keeps selected control curves visible over geometry in Viewport 2.0. Supports automatic or manual override colours and restores the prior override colour after enabling the draw-on-top setting. |
| 004 | `004-anti_clipping_cluster.py` | `toggle_anti_clipping_cluster()` | Creates a hidden cluster that scales selected body vertices inward to reduce visible clothing intersections. Run again to remove the cluster. This is a visual adjustment, not a skinning fix. |
| 005 | `005-clean_unknown_nodes.py` | `report_unknown()` / `clean_unknown()` / `optimize_scene()` | Inspects and removes unknown nodes and unknown plug-in requirements that can prevent saving Maya ASCII (`.ma`) files. `report_unknown()` is inspection-only. |
| 006 | `006-copy_animation_key_to_json.py` | `show_anim_key_transfer_ui()` | Exports Graph Editor-selected keys to JSON and imports them into another scene. Preserves frame numbers, strips namespaces when matching, and performs the import as one undo step. Can clear existing keys in imported ranges or limit the operation to selected nodes. |
| 007 | `007-custom_axis_orient.py` | `show_custom_axis_ui()` / `orient_from()` / `reset_orient()` | Aligns the Move manipulator, and optionally Rotate and Scale, to the world rotation of the last-selected object using Custom axis orientation. |
| 008 | `008-bake_to_selected.py` | `bake_to_selected()` | Bakes source object A's world-space animation onto target B over the playback range using a temporary parent constraint. Locked target channels are skipped with a warning. |
| 009 | `009.6-locator_checker.py` | `show_locator_checker_ui()` / `fix_locator_visibility()` | Diagnoses and fixes locators or other transforms that are not visible in the viewport. Checks visibility, local scale, drawing overrides, template state, parent chains, display layers, isolate select, and the viewport's Locators display setting. Also adjusts locator size and colour. |
| 010 | `010-bake_locators_to_temp.py` | `show()` | Bakes selected locators' world-space transforms—including animation inherited through constrained parent groups—onto new `temp_locator` nodes over a chosen frame range. |
| 011 | `011-camera_sequencer_builder.py` | `show_camera_sequencer_builder_ui()` | Builds Camera Sequencer shots from selected cameras using each camera's keyed range, with playback range as a fallback. Checks and fixes non-unit camera scale and can create an ubercam. Headless functions: `check_camera_scale()`, `fix_camera_scale()`, and `build_shots_from_cameras()`. |
| 012 | `012-merge_to_world.py` | `show_merge_to_world_ui()` / `merge_to_world()` | Bakes an object's animation together with animated parent-group motion onto a new world-parented node. Supports cameras, locators, joints, meshes, curves, and groups; also bakes animated shape attributes such as focal length. Can optionally delete the source group. |

## Important notes

- **Maya compatibility:** These tools are written for Maya 2025 with Python 3. The PySide6-based tools (`icon_generator`, `curve_top_always`, and `locator_checker`) are not expected to run unchanged in Maya 2023 or earlier, which use PySide2 / shiboken2 instead.
- **Anti-clipping cluster:** This changes the visible result only and does not modify skin weights. Use it for reviews or playblasts, not as a permanent rig correction.
- **Unknown nodes:** `clean_unknown()` can permanently delete data. If an unknown node belongs to a plug-in that should be available (for example, a renderer), load that plug-in and save the scene again instead. Run `report_unknown()` before cleaning.
- **Camera scale:** `fix_camera_scale()` resets scale to 1.0. If the camera's framing depends on its existing scale, the composition will change; run the scale check first.
- **Bake to selected:** If the target has an incoming `offsetParentMatrix` connection, baked values are expressed in that parent space. The world-space position can be correct even though the translate values differ from the source's world translate.
- **Merge to world:** Transform animation and animated shape attributes are baked, but deforming geometry (such as skinCluster, blendShape, or lattice deformation) is not transferred.

## Known issues

`002-add_camera_gate.py` currently contains an older copy of the Locator Checker rather than a camera-gate tool. Use `009.6-locator_checker.py` for locator visibility work until script 002 is replaced.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
