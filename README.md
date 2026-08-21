# Maya Shelf Tools

Personal Maya 2025 animation-pipeline tools, written in Python 3 for `maya.cmds` / PySide6.
個人用的 Maya 2025 動畫 pipeline 工具集，Python 3，使用 `maya.cmds` / PySide6。

All scripts are standalone modules — no external dependencies beyond Maya itself.
所有腳本都是獨立模組，除了 Maya 本身之外沒有其他相依套件。

---

## Install · 安裝

1. Copy the folders (or the individual `.py` files) into your Maya scripts folder
   把資料夾（或個別 `.py` 檔）複製到 Maya 的 scripts 資料夾：

   - Windows: `C:/Users/<you>/Documents/maya/2025/scripts/`
   - macOS: `~/Library/Preferences/Autodesk/maya/2025/scripts/`
   - Linux: `~/maya/2025/scripts/`

2. In the Script Editor (Python tab), import and run the tool
   在 Script Editor 的 Python 分頁 import 並執行：

   ```python
   import merge_to_world as mtw
   mtw.show_merge_to_world_ui()
   ```

3. To make a shelf button, put that same snippet in a Python shelf button.
   要做 shelf 按鈕，把同一段程式碼放進 Python 類型的 shelf button 即可。

> Maya only writes shelves back to disk on a clean quit, or via Shelf Editor → Save All Shelves.
> Maya 只有在正常關閉時（或手動 Shelf Editor → Save All Shelves）才會把 shelf 寫回硬碟。

Every module is safe to `import` — nothing runs on import; UI/action code lives under
`if __name__ == "__main__":` or an explicit entry function.
每個模組都可以安全 `import`，import 時不會自動執行；實際動作放在 `if __name__ == "__main__":` 或明確的進入函式裡。

---

## Tools · 工具列表

### `animation/`

| Tool | Entry point | What it does · 功能 |
|---|---|---|
| `bake_to_selected.py` | `bake_to_selected()` | Select A then B; bakes A's world-space animation onto B via a temp parentConstraint, then cleans up. · 先選 A 再選 B，把 A 的世界空間動畫烘到 B 上再清除約束。 |
| `merge_to_world.py` | `show_merge_to_world_ui()` | Bakes an object's transform **plus every animated parent group** into one world-space animation on a new world-parented node. Optional source-group delete. · 把物件與上層所有有動畫的 group 疊合後烘成單一世界空間動畫，可選刪除原資料夾。 |
| `camera_sequencer_builder.py` | `show_camera_sequencer_builder_ui()` | Builds Camera Sequencer shots from selected cameras using each camera's own key range; checks/fixes the non-unit scale that blocks ubercam creation. · 依相機各自的 key 範圍建立 shot，並檢查修正擋住 ubercam 的 scale 問題。 |
| `custom_axis_orient.py` | `orient_from()` / `show_custom_axis_ui()` | Re-applies "Custom axis orientation" on the Move manipulator from the last-selected object — Maya keeps dropping it back to Object mode. · 一鍵把 Move 軸向重設成參考物件的 Custom axis，避免每次跳回 Object 模式都要重開 Tool Settings。 |

### `locator/`

| Tool | Entry point | What it does · 功能 |
|---|---|---|
| `bake_locators_to_temp.py` | `show()` | UI tool that bakes the world-space transform of selected locators (including inherited constraint chains) onto a new `temp_locator`, with an adjustable frame range. · 帶 UI，把選取 locator 的世界空間動畫（含繼承自父層的約束）烘到新的 `temp_locator`。 |

### `rigging/`

| Tool | Entry point | What it does · 功能 |
|---|---|---|
| `anti_clipping_cluster.py` | `toggle_anti_clipping_cluster()` | Toggles a corrective cluster that shrinks selected body vertices 30% inward to hide skin clipping through clothing. Run again to remove. · 開關式修正 cluster，把選取的身體頂點內縮 30% 遮住穿模，再執行一次即還原。 |

### `utility/`

| Tool | Entry point | What it does · 功能 |
|---|---|---|
| `locator_checker.py` | `show_locator_checker_ui()` | Diagnoses and auto-fixes locators that exist but don't render: visibility, `localScale`, overrides, template state, parent chain, display layers, isolate select, viewport Show Locators. Plus size and override-colour controls. · 診斷並自動修復「存在但看不到」的 locator，另含尺寸與顏色控制。 |
| `icon_generator.py` | `show()` | PySide6 UI for generating 64x64 PNG shelf-button icons: text, colours (palette or system picker), font size, margin, preview, save into Maya's icons folder. · 產生 64x64 shelf 按鈕圖示的 PySide6 介面，可預覽並直接存進 Maya icons 資料夾。 |
| `clean_unknown_nodes.py` | `report_unknown()` / `clean_unknown()` | Removes unknown nodes and unknown plugin requirements that block saving a scene as `.ma`. · 清除擋住存成 `.ma` 的 unknown node 與 plugin 需求。 |
| `animbot_shelf_button.py` | `create_animbot_shelf_button()` | Creates an animBot launcher button on the active shelf; safe to re-run (no duplicate buttons). · 在目前的 shelf 上建立 animBot 啟動鈕，重複執行不會長出第二顆。 |

---

## Notes · 注意事項

- **Maya version:** written and tested against Maya 2025 (Python 3, PySide6). `icon_generator.py` in particular depends on PySide6 / shiboken6 and will not run on Maya 2023 or earlier without changing the imports to PySide2.
  以 Maya 2025（Python 3、PySide6）撰寫測試。`icon_generator.py` 依賴 PySide6 / shiboken6，Maya 2023 以前要改成 PySide2 才能跑。
- **`anti_clipping_cluster.py`** only masks clipping visually; it does not fix skin weights. Use it for review, not as a permanent rig fix.
  只是視覺上遮住穿模，不會修正權重，請當審核用途。
- **`clean_unknown_nodes.py`** deletes data permanently. If the unknown nodes belong to a plugin that *should* be installed (e.g. a Redshift shader), load the plugin and re-save instead of cleaning.
  會永久刪除資料。若 unknown node 其實屬於本來就該裝的 plugin，正解是載入 plugin 後再存檔。
- **`camera_sequencer_builder.py`**'s Fix Scale hard-resets scale to 1 — if the framing relied on scale, the composition will change. Run Check Scale first.
  Fix Scale 是硬歸 1，若原本靠 scale 調過構圖會跑掉，建議先跑 Check Scale。

## License

MIT — see [LICENSE](LICENSE).
