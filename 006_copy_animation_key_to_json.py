"""Transfer selected Maya animation keys through a JSON file.

Run this file in Maya 2025's Script Editor or source it from a shelf button.
"""

import json
import os

import maya.cmds as cmds

TOOL_NAME = "Anim Key Transfer"
FILE_VERSION = 1
_UI_WINDOW = "animKeyTransferWin"
_UI_PATH_FIELD = "animKeyTransferPathField"
_UI_CLEAR_CHECK = "animKeyTransferClearCheck"
_UI_SEL_CHECK = "animKeyTransferSelOnlyCheck"


def _log(verbose, message):
    if verbose:
        print(message)


def _selected_anim_curves():
    """Return animation curves that have at least one selected key."""
    curves = cmds.keyframe(query=True, selected=True, name=True) or []
    return [curve for curve in curves if cmds.objExists(curve)]


def _curve_target_plug(curve):
    """Return the destination node.attribute driven by an animation curve."""
    plugs = cmds.listConnections(
        curve + ".output",
        plugs=True,
        source=False,
        destination=True,
    ) or []

    for plug in plugs:
        node = plug.split(".", 1)[0]
        if not cmds.objExists(node):
            continue
        if cmds.objectType(node, isAType="animCurve"):
            continue

        if cmds.objectType(node) == "pairBlend":
            downstream = cmds.listConnections(
                plug,
                plugs=True,
                source=False,
                destination=True,
            ) or []
            if downstream:
                return downstream[0]
            continue
        return plug

    return None


def _strip_namespace(name):
    return name.rsplit(":", 1)[-1]


def _resolve_plug(plug, strip_namespace=True, allowed_nodes=None):
    """Resolve a stored plug in the current scene, optionally by short name."""
    if "." not in plug:
        return None

    node, attribute = plug.split(".", 1)
    candidates = []

    if cmds.objExists(plug):
        candidates.append(node)

    if strip_namespace:
        short_name = _strip_namespace(node)
        matches = cmds.ls(short_name, "*:" + short_name, long=True) or []
        for match in matches:
            if match not in candidates:
                candidates.append(match)

    allowed_long = None
    allowed_short = None
    if allowed_nodes is not None:
        allowed_long = set(cmds.ls(list(allowed_nodes), long=True) or [])
        allowed_short = set(allowed_nodes)

    for candidate in candidates:
        target = candidate + "." + attribute
        if not cmds.objExists(target):
            continue

        if allowed_nodes is not None:
            long_names = cmds.ls(candidate, long=True) or []
            short_candidate = candidate.rsplit("|", 1)[-1]
            if not any(name in allowed_long for name in long_names):
                if short_candidate not in allowed_short:
                    continue

        return target

    return None


def _plug_is_writable(plug, verbose=True):
    """Reject locked plugs and plugs driven by unsupported node types."""
    try:
        if cmds.getAttr(plug, lock=True):
            _log(verbose, "[skip] locked plug: %s" % plug)
            return False
    except Exception:
        _log(verbose, "[skip] cannot query plug lock state: %s" % plug)
        return False

    sources = cmds.listConnections(
        plug,
        source=True,
        destination=False,
        plugs=False,
    ) or []
    for source in sources:
        if not cmds.objExists(source):
            continue
        if cmds.objectType(source, isAType="animCurve"):
            continue
        if cmds.objectType(source) in ("pairBlend", "character"):
            continue
        _log(
            verbose,
            "[skip] plug has unsupported driver %s: %s"
            % (cmds.objectType(source), plug),
        )
        return False

    return True


def collect_selected_keys(verbose=True):
    """Build a dictionary containing the currently selected keyframes."""
    curves = _selected_anim_curves()
    if not curves:
        cmds.warning("No keys selected. Select keys in the Graph Editor first.")
        return None

    data = {
        "version": FILE_VERSION,
        "tool": TOOL_NAME,
        "source_scene": cmds.file(query=True, sceneName=True) or "untitled",
        "curves": [],
    }
    key_total = 0

    for curve in curves:
        plug = _curve_target_plug(curve)
        if not plug:
            _log(verbose, "[warn] could not resolve target plug for curve: %s" % curve)
            continue

        times = cmds.keyframe(curve, query=True, selected=True, timeChange=True) or []
        values = cmds.keyframe(curve, query=True, selected=True, valueChange=True) or []
        if not times or len(times) != len(values):
            _log(verbose, "[warn] key data is incomplete for curve: %s" % curve)
            continue

        tangent_weights = cmds.keyTangent(
            curve,
            query=True,
            weightedTangents=True,
        ) or [False]
        weighted = bool(tangent_weights[0])
        keys = []

        for index, time_value in enumerate(times):
            key_time = (time_value, time_value)

            def tangent_value(**kwargs):
                result = cmds.keyTangent(
                    curve,
                    query=True,
                    time=key_time,
                    **kwargs
                ) or []
                return result[0] if result else None

            keys.append({
                "time": float(time_value),
                "value": float(values[index]),
                "itt": tangent_value(inTangentType=True) or "auto",
                "ott": tangent_value(outTangentType=True) or "auto",
                "ia": tangent_value(inAngle=True),
                "oa": tangent_value(outAngle=True),
                "iw": tangent_value(inWeight=True) if weighted else None,
                "ow": tangent_value(outWeight=True) if weighted else None,
                "lock": bool(tangent_value(lock=True)),
                "wlock": bool(tangent_value(weightLock=True)),
            })

        data["curves"].append({
            "plug": plug,
            "curve_type": cmds.objectType(curve),
            "weighted": weighted,
            "keys": keys,
        })
        key_total += len(keys)

    if not data["curves"]:
        cmds.warning("Selected keys could not be resolved to target attributes.")
        return None

    _log(verbose, "[ok] collected %d keys on %d curves" % (key_total, len(data["curves"])))
    return data


def export_selected_keys(file_path, verbose=True):
    """Export selected keys to a JSON file. Return the file path or None."""
    if not file_path:
        cmds.warning("Set an output file path first.")
        return None

    data = collect_selected_keys(verbose=verbose)
    if not data:
        return None

    folder = os.path.dirname(os.path.abspath(file_path))
    if folder and not os.path.isdir(folder):
        os.makedirs(folder)

    with open(file_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)

    _log(verbose, "[ok] exported to %s" % file_path)
    return file_path


def apply_key_data(
    data,
    strip_namespace=True,
    selected_only=False,
    clear_range=False,
    verbose=True,
):
    """Apply stored keys to matching attributes in the current scene.

    Original frame numbers are preserved. Existing keys at matching frames are
    replaced by setKeyframe. With clear_range enabled, all keys in each stored
    curve's time span are removed before the imported keys are created.
    """
    if not isinstance(data, dict) or not isinstance(data.get("curves"), list):
        cmds.warning("Invalid key data.")
        return 0

    allowed = None
    if selected_only:
        selection = cmds.ls(selection=True, long=True) or []
        if not selection:
            cmds.warning("Selected-only mode is enabled, but nothing is selected.")
            return 0
        allowed = set(selection)
        allowed.update(name.rsplit("|", 1)[-1] for name in selection)

    applied_keys = 0
    applied_curves = 0
    skipped = 0

    for entry in data["curves"]:
        plug = _resolve_plug(
            entry.get("plug", ""),
            strip_namespace=strip_namespace,
            allowed_nodes=allowed,
        )
        if not plug:
            _log(verbose, "[skip] target not found or not selected: %s" % entry.get("plug", ""))
            skipped += 1
            continue
        if not _plug_is_writable(plug, verbose=verbose):
            skipped += 1
            continue

        keys = entry.get("keys") or []
        if not keys:
            continue

        times = [float(key["time"]) for key in keys]
        if clear_range:
            cmds.cutKey(plug, time=(min(times), max(times)), clear=True)

        for key in keys:
            cmds.setKeyframe(
                plug,
                time=(float(key["time"]), float(key["time"])),
                value=float(key["value"]),
            )

        curves = cmds.keyframe(plug, query=True, name=True) or []
        if not curves:
            _log(verbose, "[warn] key was created but animation curve was not found: %s" % plug)
            skipped += 1
            continue

        curve = curves[0]
        weighted = bool(entry.get("weighted", False))
        if weighted:
            try:
                cmds.keyTangent(curve, edit=True, weightedTangents=True)
            except Exception as error:
                _log(verbose, "[warn] could not enable weighted tangents on %s: %s" % (plug, error))

        for key in keys:
            key_time = (float(key["time"]), float(key["time"]))
            try:
                cmds.keyTangent(curve, edit=True, time=key_time, lock=False)
                cmds.keyTangent(
                    curve,
                    edit=True,
                    time=key_time,
                    inTangentType=key.get("itt", "auto"),
                    outTangentType=key.get("ott", "auto"),
                )

                if key.get("itt") == "fixed" and key.get("ia") is not None:
                    cmds.keyTangent(
                        curve,
                        edit=True,
                        time=key_time,
                        inAngle=float(key["ia"]),
                    )
                if key.get("ott") == "fixed" and key.get("oa") is not None:
                    cmds.keyTangent(
                        curve,
                        edit=True,
                        time=key_time,
                        outAngle=float(key["oa"]),
                    )

                if weighted:
                    cmds.keyTangent(curve, edit=True, time=key_time, weightLock=False)
                    if key.get("iw") is not None:
                        cmds.keyTangent(
                            curve,
                            edit=True,
                            time=key_time,
                            inWeight=float(key["iw"]),
                        )
                    if key.get("ow") is not None:
                        cmds.keyTangent(
                            curve,
                            edit=True,
                            time=key_time,
                            outWeight=float(key["ow"]),
                        )
                    cmds.keyTangent(
                        curve,
                        edit=True,
                        time=key_time,
                        weightLock=bool(key.get("wlock", False)),
                    )

                cmds.keyTangent(
                    curve,
                    edit=True,
                    time=key_time,
                    lock=bool(key.get("lock", True)),
                )
            except Exception as error:
                _log(
                    verbose,
                    "[warn] tangent issue on %s at %s: %s"
                    % (plug, key.get("time"), error),
                )

        applied_curves += 1
        applied_keys += len(keys)
        _log(verbose, "[ok] %s: %d keys" % (plug, len(keys)))

    _log(
        verbose,
        "[info] done - %d keys on %d attributes, %d skipped"
        % (applied_keys, applied_curves, skipped),
    )
    return applied_keys


def import_selected_keys(
    file_path,
    strip_namespace=True,
    selected_only=False,
    clear_range=False,
    verbose=True,
):
    """Import a JSON file created by export_selected_keys."""
    if not file_path or not os.path.isfile(file_path):
        cmds.warning("File not found: %s" % (file_path or ""))
        return 0

    try:
        with open(file_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (IOError, OSError, ValueError) as error:
        cmds.warning("Could not read key data: %s" % error)
        return 0

    if data.get("version") != FILE_VERSION:
        _log(
            verbose,
            "[warn] file version %s differs from tool version %d"
            % (data.get("version"), FILE_VERSION),
        )

    cmds.undoInfo(openChunk=True, chunkName="importSelectedKeys")
    try:
        return apply_key_data(
            data,
            strip_namespace=strip_namespace,
            selected_only=selected_only,
            clear_range=clear_range,
            verbose=verbose,
        )
    finally:
        cmds.undoInfo(closeChunk=True)


def _ui_default_path():
    workspace = cmds.workspace(query=True, rootDirectory=True) or ""
    return os.path.join(workspace, "data", "anim_key_transfer.json").replace("\\", "/")


def _ui_browse(save):
    mode = 0 if save else 1
    result = cmds.fileDialog2(
        fileMode=mode,
        fileFilter="JSON Files (*.json)",
        caption="Key Transfer File",
    )
    if result:
        cmds.textFieldGrp(_UI_PATH_FIELD, edit=True, text=result[0])


def _ui_export(*_args):
    path = cmds.textFieldGrp(_UI_PATH_FIELD, query=True, text=True).strip()
    if not path:
        cmds.warning("Set an output file path first.")
        return None
    return export_selected_keys(path)


def _ui_import(*_args):
    path = cmds.textFieldGrp(_UI_PATH_FIELD, query=True, text=True).strip()
    if not path:
        cmds.warning("Set an input file path first.")
        return 0

    clear_range = cmds.checkBox(_UI_CLEAR_CHECK, query=True, value=True)
    selected_only = cmds.checkBox(_UI_SEL_CHECK, query=True, value=True)
    return import_selected_keys(
        path,
        selected_only=selected_only,
        clear_range=clear_range,
    )


def show_anim_key_transfer_ui():
    """Create and show the key transfer window."""
    if cmds.window(_UI_WINDOW, exists=True):
        cmds.deleteUI(_UI_WINDOW)

    cmds.window(
        _UI_WINDOW,
        title=TOOL_NAME,
        sizeable=True,
        widthHeight=(480, 235),
    )
    main = cmds.columnLayout(
        adjustableColumn=True,
        rowSpacing=7,
        columnAttach=("both", 10),
    )

    cmds.text(
        label="Transfer selected Graph Editor keys between scenes using JSON.",
        align="left",
        height=24,
    )
    cmds.separator(style="in", height=6)

    cmds.rowLayout(
        numberOfColumns=2,
        adjustableColumn=1,
        columnAttach=[(1, "both", 0), (2, "both", 4)],
    )
    cmds.textFieldGrp(
        _UI_PATH_FIELD,
        label="JSON File",
        columnWidth2=(60, 340),
        adjustableColumn=2,
        text=_ui_default_path(),
    )
    cmds.button(
        label="Browse...",
        width=90,
        command=lambda *_: _ui_browse(save=True),
        annotation="Choose the JSON file path.",
    )
    cmds.setParent(main)

    cmds.separator(style="none", height=2)
    cmds.checkBox(
        _UI_CLEAR_CHECK,
        label="Clear existing keys inside each imported time range",
        value=False,
        annotation="Off: replace keys at matching frames and keep all other keys.",
    )
    cmds.checkBox(
        _UI_SEL_CHECK,
        label="Apply to selected nodes only",
        value=False,
        annotation="Only import attributes whose target nodes are selected.",
    )

    cmds.separator(style="in", height=8)
    cmds.rowLayout(
        numberOfColumns=2,
        columnWidth2=(225, 225),
        columnAttach=[(1, "both", 2), (2, "both", 2)],
    )
    cmds.button(
        label="Export Selected Keys",
        height=36,
        command=_ui_export,
        annotation="Write currently selected Graph Editor keys to JSON.",
    )
    cmds.button(
        label="Import Keys",
        height=36,
        command=_ui_import,
        annotation="Read JSON and recreate the stored animation keys.",
    )
    cmds.setParent(main)

    cmds.separator(style="none", height=4)
    cmds.text(
        label="Frame numbers are preserved. Import is one undo step.",
        align="left",
        height=20,
    )

    cmds.showWindow(_UI_WINDOW)
    return _UI_WINDOW


if __name__ == "__main__":
    show_anim_key_transfer_ui()