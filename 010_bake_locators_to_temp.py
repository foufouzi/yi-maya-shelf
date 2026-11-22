"""
bake_locators_to_temp.py

Maya 2025 / Python 3

Purpose
    UI tool that bakes the world-space transform of selected locators
    (including any constraint chains inherited from parent groups) into a
    new temp_locator, with an adjustable frame range.

Usage
    import bake_locators_to_temp as blt
    blt.show()
"""

import maya.cmds as cmds


class BakeLocatorUI:
    """UI tool to bake selected locators to a new temp_locator"""

    def __init__(self):
        self.window_name = "bakeLocatorWindow"
        self.temp_locator_name = "temp_locator"

    def show(self):
        """Show the UI window"""
        if cmds.window(self.window_name, exists=True):
            cmds.deleteUI(self.window_name)

        self.window = cmds.window(
            self.window_name,
            title="Bake Locators to Temp",
            widthHeight=(450, 350),
            resizeToFitChildren=True
        )

        main_layout = cmds.columnLayout(adjustableColumn=True, rowSpacing=12)

        cmds.text(
            label="Bake Locators to Temp Locator",
            height=30,
            font="boldLabelFont",
            align="center"
        )

        cmds.separator(height=15, style="single")

        cmds.text(
            label="Steps: Select locators -> Set frame range -> Execute",
            align="left",
            wordWrap=True,
            height=35
        )

        cmds.separator(height=15, style="single")

        frame_layout = cmds.frameLayout(
            label="Frame Range",
            collapsable=False,
            marginHeight=10,
            marginWidth=10
        )

        frame_column = cmds.columnLayout(adjustableColumn=True, rowSpacing=10)

        cmds.rowLayout(numberOfColumns=2, columnWidth2=(120, 250), columnAlign2=("left", "left"))
        cmds.text(label="Start Frame:", width=120)
        self.start_field = cmds.intField(value=1, minValue=0, width=100)
        cmds.setParent("..")

        cmds.rowLayout(numberOfColumns=2, columnWidth2=(120, 250), columnAlign2=("left", "left"))
        cmds.text(label="End Frame:", width=120)
        self.end_field = cmds.intField(value=100, minValue=0, width=100)
        cmds.setParent("..")

        cmds.separator(height=10, style="none")

        cmds.text(label="Quick Set:", height=20)

        button_layout = cmds.rowLayout(numberOfColumns=2, columnWidth2=(210, 210), columnAlign2=("left", "left"))
        cmds.button(
            label="Timeline Range",
            command=self.set_timeline_range,
            height=25,
            backgroundColor=(0.4, 0.6, 0.8)
        )
        cmds.button(
            label="Playback Range",
            command=self.set_current_range,
            height=25,
            backgroundColor=(0.4, 0.6, 0.8)
        )
        cmds.setParent("..")

        cmds.setParent("..")
        cmds.setParent("..")

        cmds.separator(height=15, style="single")

        name_layout = cmds.frameLayout(
            label="Locator Settings",
            collapsable=False,
            marginHeight=10,
            marginWidth=10
        )

        name_column = cmds.columnLayout(adjustableColumn=True, rowSpacing=8)

        cmds.rowLayout(numberOfColumns=2, columnWidth2=(120, 250), columnAlign2=("left", "left"))
        cmds.text(label="Locator Name:", width=120)
        self.name_field = cmds.textField(text=self.temp_locator_name, width=200)
        cmds.setParent("..")

        cmds.text(
            label="(If a locator with this name exists, it will be auto-renamed)",
            height=18,
            align="left",
            font="smallBoldLabelFont"
        )

        cmds.setParent("..")
        cmds.setParent("..")

        cmds.separator(height=15, style="single")

        button_layout = cmds.rowLayout(numberOfColumns=2, columnWidth2=(215, 215))

        cmds.button(
            label="Reset",
            command=self.reset_fields,
            height=35,
            backgroundColor=(0.7, 0.7, 0.7)
        )

        cmds.button(
            label="Bake Locators",
            command=self.execute_bake,
            height=35,
            backgroundColor=(0.2, 0.6, 0.2)
        )

        cmds.setParent("..")

        cmds.setParent(main_layout)
        cmds.showWindow(self.window)

        print("\n" + "=" * 50)
        print("Bake Locator UI opened")
        print("=" * 50)

    def set_timeline_range(self, *args):
        """Set frame range to the timeline range"""
        try:
            start = int(cmds.playbackOptions(query=True, minTime=True))
            end = int(cmds.playbackOptions(query=True, maxTime=True))
            cmds.intField(self.start_field, edit=True, value=start)
            cmds.intField(self.end_field, edit=True, value=end)
            print(f"Set to timeline range: {start} - {end} frames")
        except Exception as e:
            cmds.warning(f"Failed to set range: {str(e)}")

    def set_current_range(self, *args):
        """Set frame range to the current playback range"""
        try:
            start = int(cmds.playbackOptions(query=True, ast=True))
            end = int(cmds.playbackOptions(query=True, aet=True))
            cmds.intField(self.start_field, edit=True, value=start)
            cmds.intField(self.end_field, edit=True, value=end)
            print(f"Set to playback range: {start} - {end} frames")
        except Exception as e:
            cmds.warning(f"Failed to set range: {str(e)}")

    def reset_fields(self, *args):
        """Reset all fields to default"""
        cmds.intField(self.start_field, edit=True, value=1)
        cmds.intField(self.end_field, edit=True, value=100)
        cmds.textField(self.name_field, edit=True, text=self.temp_locator_name)
        print("All fields reset")

    def execute_bake(self, *args):
        """Execute the bake process"""
        start_frame = cmds.intField(self.start_field, query=True, value=True)
        end_frame = cmds.intField(self.end_field, query=True, value=True)
        locator_name = cmds.textField(self.name_field, query=True, text=True)

        if start_frame >= end_frame:
            cmds.warning("Start frame must be less than end frame")
            return

        try:
            self.bake_locators(start_frame, end_frame, locator_name)
        except Exception as e:
            cmds.warning(f"Error occurred: {str(e)}")
            import traceback
            traceback.print_exc()

    def is_locator(self, obj):
        """
        Correctly determine whether a node is a locator.

        Note: cmds.objectType(transform_node) returns "transform",
        not "locator". The "locator" type only exists on the shape node.
        So we must get the shape first, then check the shape's type.
        """
        if cmds.objectType(obj) == "locator":
            return True

        shapes = cmds.listRelatives(obj, shapes=True, fullPath=True) or []
        for shape in shapes:
            if cmds.objectType(shape) == "locator":
                return True

        return False

    def bake_locators(self, start_frame, end_frame, locator_name):
        """Core bake functionality"""

        print("\n" + "=" * 50)
        print("Starting bake process...")
        print("=" * 50)

        selected = cmds.ls(selection=True)
        if not selected:
            cmds.warning("Please select at least one locator")
            return

        print(f"Selected {len(selected)} object(s)")

        final_locator_name = locator_name
        counter = 1
        while cmds.objExists(final_locator_name):
            final_locator_name = f"{locator_name}_{counter}"
            counter += 1

        temp_locator = cmds.spaceLocator(n=final_locator_name)[0]
        cmds.xform(temp_locator, worldSpace=True, translation=[0, 0, 0])
        print(f"Created locator: {temp_locator}")

        constraints = []
        baked_count = 0

        for obj in selected:
            if not self.is_locator(obj):
                print(f"Skipped: {obj} is not a locator (or no locator shape found)")
                continue

            try:
                constraint = cmds.parentConstraint(obj, temp_locator,
                                                    maintainOffset=False)[0]
                constraints.append(constraint)
                baked_count += 1
                print(f"Constrained: {obj}")
            except Exception as e:
                print(f"Failed to constrain {obj}: {str(e)}")

        if not constraints:
            cmds.delete(temp_locator)
            cmds.warning("No valid locators found")
            return

        print(f"\nBaking {baked_count} locator(s)...")
        print(f"Frame range: {start_frame} - {end_frame} ({end_frame - start_frame + 1} frames)")

        try:
            cmds.bakeResults(
                temp_locator,
                simulation=True,
                time=(start_frame, end_frame),
                sampleBy=1,
                oversamplingRate=1,
                disableImplicitControl=True,
                preserveOutsideKeys=True,
                removeBakedAttributeFromLayer=False
            )
            print("Bake complete")
        except Exception as e:
            cmds.warning(f"Bake failed: {str(e)}")
            cmds.delete(temp_locator)
            return

        try:
            cmds.delete(constraints)
            print("Deleted all constraints")
        except Exception as e:
            print(f"Failed to delete constraints: {str(e)}")

        cmds.select(temp_locator)

        print("\n" + "=" * 50)
        print("Bake process complete!")
        print("=" * 50)
        print(f"Created: {temp_locator}")
        print(f"Baked: {baked_count} locator(s)")
        print(f"Frame range: {start_frame} - {end_frame}")
        print("=" * 50 + "\n")


def show():
    """Open the Bake Locators UI."""
    ui = BakeLocatorUI()
    ui.show()
    return ui


if __name__ == "__main__":
    show()
