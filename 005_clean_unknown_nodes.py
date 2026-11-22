"""
clean_unknown_nodes.py - Maya 2025

Removes unknown nodes / unknown plugin data that block saving a scene
as .ma (Maya ASCII).

Typical error:
    // Error: This file contains unknown data which is preventing Maya
    // from changing the file format.

Warning
    If an unknown node actually belongs to a plugin that SHOULD be there but
    is not installed on this machine (e.g. a Redshift shader), deleting it
    loses that data permanently. The correct fix in that case is to load the
    plugin and save again.

Usage (Script Editor, Python tab):
    import clean_unknown_nodes as cun
    cun.report_unknown()          # inspect only, changes nothing
    cun.clean_unknown()           # remove unknown nodes + unknown plugins
    cun.optimize_scene()          # optional
"""

import maya.cmds as cmds
import maya.mel as mel


def _unknown_nodes():
    nodes = cmds.ls(type="unknown", long=True) or []
    nodes += cmds.ls(type="unknownDag", long=True) or []
    nodes += cmds.ls(type="unknownTransform", long=True) or []
    return sorted(set(nodes))


def report_unknown(verbose=True):
    """Print what is currently blocking the .ma save. Read-only."""
    nodes = _unknown_nodes()
    plugins = cmds.unknownPlugin(query=True, list=True) or []

    if verbose:
        print("[info] unknown nodes   : %d" % len(nodes))
        for n in nodes:
            print("    [node] %s" % n)
        print("[info] unknown plugins : %d" % len(plugins))
        for p in plugins:
            print("    [plugin] %s" % p)
        if not nodes and not plugins:
            print("[ok] scene is clean, .ma save should work")
    return nodes, plugins


def clean_unknown(remove_plugins=True, verbose=True):
    """Delete unknown nodes and unregister unknown plugin requirements."""
    nodes, plugins = report_unknown(verbose=False)

    deleted, skipped = [], []
    for node in nodes:
        if not cmds.objExists(node):
            continue
        try:
            if cmds.lockNode(node, query=True, lock=True)[0]:
                cmds.lockNode(node, lock=False)
            cmds.delete(node)
            deleted.append(node)
        except Exception as exc:
            skipped.append((node, str(exc)))
            cmds.warning("[warn] could not delete %s : %s" % (node, exc))

    removed_plugins = []
    if remove_plugins:
        for plug in plugins:
            try:
                cmds.unknownPlugin(plug, remove=True)
                removed_plugins.append(plug)
            except Exception as exc:
                cmds.warning("[warn] could not remove plugin %s : %s" % (plug, exc))

    if verbose:
        print("[ok]   deleted nodes    : %d" % len(deleted))
        print("[ok]   removed plugins  : %d" % len(removed_plugins))
        if skipped:
            print("[fail] skipped nodes    : %d" % len(skipped))
            for node, err in skipped:
                print("    [skip] %s : %s" % (node, err))
        print("[info] now try: File > Save Scene As ... (.ma)")
    return deleted, removed_plugins, skipped


def optimize_scene(verbose=True):
    """Run Maya's Optimize Scene Size (cleans stale/empty leftovers)."""
    try:
        mel.eval("cleanUpScene 3;")
        if verbose:
            print("[ok] optimize scene size done")
    except Exception as exc:
        cmds.warning("[warn] optimize scene failed : %s" % exc)


if __name__ == "__main__":
    report_unknown()
