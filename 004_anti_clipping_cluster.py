"""
anti_clipping_cluster.py

Maya 2025 / Python 3

Purpose
    One-shot toggle for the classic "skin poking through clothes" problem.
    Select the clipping body vertices and run it: it builds a cluster named
    anti_clipping_cluster, scales it inward by 30% to tuck the skin under the
    clothing silhouette, and hides the cluster handle. Run it again (no
    selection needed) to delete the cluster and restore the original mesh.

Note
    This only masks clipping visually by moving the skin's cluster
    deformation, not the base mesh weights. Treat it as a review / reference
    aid, not a permanent fix for the rig or the garment.

Usage
    import anti_clipping_cluster as acc
    acc.toggle_anti_clipping_cluster()
"""

import maya.cmds as cmds


def toggle_anti_clipping_cluster():
    """
    Toggles a corrective cluster to shrink selected body vertices inward.
    Perfect for fixing mesh clipping without altering the rig or clothing silhouette.
    Includes viewport status messages for workflow clarity.
    """
    cluster_name = "anti_clipping_cluster"

    # Check if the corrective cluster already exists in the scene
    if cmds.objExists(cluster_name):
        # Toggle OFF: Delete the cluster and restore original mesh state
        cmds.delete(cluster_name)

        # Display OFF status in the viewport
        off_msg = '<span style="color:#ff4444; font-weight:bold;">Clipping Fix Status: OFF (Cluster Removed)</span>'
        cmds.inViewMessage(amg=off_msg, pos='topCenter', fade=True, bck=0x000000, alpha=0.7)
        cmds.select(clear=True)
        return

    # Toggle ON: Require vertex selection to create the cluster
    sel = cmds.ls(selection=True, flatten=True)
    verts = cmds.filterExpand(sel, selectionMask=31)  # 31 indicates Polygon Vertices

    if not verts:
        warn_msg = '<span style="color:#ffaa00; font-weight:bold;">Warning: Please select the body vertices that are clipping</span>'
        cmds.inViewMessage(amg=warn_msg, pos='topCenter', fade=True, bck=0x000000, alpha=0.7)
        return

    try:
        # Create the cluster on selected vertices
        cluster_result = cmds.cluster(verts, name=cluster_name)
        cluster_handle = cluster_result[1]

        # Scale the cluster inward by 30 percent to hide the skin under the clothes
        cmds.scale(0.7, 0.7, 0.7, cluster_handle, relative=True)

        # Hide the cluster handle from the viewport to keep the workspace clean
        cmds.setAttr("{0}.visibility".format(cluster_handle), 0)

        # Display ON status in the viewport
        on_msg = '<span style="color:#44ff44; font-weight:bold;">Clipping Fix Status: ON (Vertices Shrinked)</span>'
        cmds.inViewMessage(amg=on_msg, pos='topCenter', fade=True, bck=0x000000, alpha=0.7)

        cmds.select(clear=True)

    except Exception:
        error_msg = '<span style="color:#ff4444; font-weight:bold;">Status: ERROR (Failed to create cluster)</span>'
        cmds.inViewMessage(amg=error_msg, pos='topCenter', fade=True)


if __name__ == "__main__":
    toggle_anti_clipping_cluster()
