#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LabExT  Copyright (C) 2022  ETH Zurich and Polariton Technologies AG
This program is free software and comes with ABSOLUTELY NO WARRANTY; for details see LICENSE file.
"""

import re
from tkinter import Frame, IntVar, TclError, Toplevel, Label, OptionMenu, StringVar, Button, messagebox, Checkbutton, NORMAL, DISABLED, ttk
from functools import partial
from itertools import product
from tkinter.constants import ACTIVE, BOTH, LEFT, RIGHT, TOP, VERTICAL, X, Y
from typing import Type

from LabExT.Movement.Calibration import Calibration, Axis, DevicePosition, Direction, is_axis_calibration_valid
from LabExT.Utils import run_with_wait_window
from LabExT.View.Controls.CustomFrame import CustomFrame
from LabExT.View.Controls.Wizard import Wizard

from LabExT.Movement.Transformations import SinglePointFixation, KabschRotation


class StageCalibrationView(Wizard):
    def __init__(self, parent, controller, mover) -> None:
        super().__init__(
            parent,
            width=1000,
            height=700,
            cancel_button_label="Cancel and Close",
            finish_button_label="Finish and Save",
            on_finish=self._save
        )
        self.title("Stage Calibration Wizard")

        self.controller = controller
        self.experiment_manager = self.controller.experiment_manager
        self.mover = mover

        # -- 1. STEP: FIX COORDINATE SYSTEM --
        self.fix_coordinate_system_step = self.add_step(self._fix_coordinate_system_step_builder,
            title="Fix Coordinate System",
            on_reload=self._check_axis_calibration,
            on_next=lambda: self.controller.save_coordinate_system_fixation(self._current_axis_calibration))
        # Step state and variables
        self._axis_calibration_options = { self._axis_calibration_option_key(c): c for c in list(product(Axis, Direction)) }
        self._performing_wiggle = False
        self._current_axis_calibration = {
            c: c._axes_calibration.copy() for c in self.mover.calibrations.values()}

        # -- 2. STEP: FIX SINGLE POINT --
        self.fix_single_point = self.add_step(self._fix_single_point_step_builder,
            title="Fix Single Point",
            on_reload=self._check_single_point_transformations,
            on_next=lambda: self.controller.save_single_point_calibration(self._current_single_point_transformations))
        # Step state and variables
        self._current_single_point_transformations = {}

        # -- 3. STEP: FULLY CALIBRATION
        self.fully_calibrate = self.add_step(self._fully_calibration_step_builder,
            title="Fully calibrate",
            finish_step_enabled=True)
        # Step state and variables
        self._current_full_transformations = {}

        # Connect Steps
        self.fix_coordinate_system_step.next_step = self.fix_single_point
        self.fix_single_point.previous_step = self.fix_coordinate_system_step
        self.fix_single_point.next_step = self.fully_calibrate
        self.fully_calibrate.previous_step = self.fix_single_point

        # Start Wizard by setting the current step
        self.current_step = self.fix_coordinate_system_step

    def _fix_coordinate_system_step_builder(self, frame: Type[CustomFrame]):
        frame.title = "Fix Coordinate System"

        step_description = Label(
            frame,
            text="In order for each stage to move relative to the chip coordinates, the direction of each axis of each stage must be defined. \n Postive Y-Axis: North of chip, Positive X-Axis: East of chip, Positive Z-Axis: Lift stage")
        step_description.pack(side=TOP, fill=X)

        for calibration in self.mover.calibrations.values():
            stage_calibration_frame = CustomFrame(frame)
            stage_calibration_frame.title = str(calibration)
            stage_calibration_frame.pack(side=TOP, fill=X, pady=2)

            current_calibration = self._current_axis_calibration.get(calibration, {})

            for chip_axis in Axis:
                chip_axis_frame = Frame(stage_calibration_frame)
                chip_axis_frame.pack(side=TOP, fill=X)

                Label(
                    chip_axis_frame,
                    text="Positive {}-Chip-axis points to ".format(chip_axis.name)
                ).pack(side=LEFT)

                axis_mapping = StringVar(self.parent, self._axis_calibration_option_key(current_calibration.get(chip_axis, (chip_axis, Direction.POSITIVE))))
                axis_option_menu = OptionMenu(
                    chip_axis_frame,
                    axis_mapping,
                    *self._axis_calibration_options.keys(),
                    command=partial(
                        self._on_axis_calibrate,
                        calibration,
                        chip_axis))
                axis_option_menu.pack(side=LEFT)

                Label(chip_axis_frame, text="of Stage").pack(side=LEFT)

                Button(
                    chip_axis_frame,
                    text="Wiggle {}-Axis".format(chip_axis.name),
                    command=partial(self._on_wiggle_axis, calibration, chip_axis),
                    state=NORMAL if is_axis_calibration_valid(self._current_axis_calibration[calibration]) else DISABLED
                ).pack(side=RIGHT)


    def _fix_single_point_step_builder(self, frame: Type[CustomFrame]):
        frame.title = "Fix Single Point"

        step_description = Label(
            frame,
            text="To move the stage absolute to chip coordinates, a stage coordinate is fixed with a chip coordinate and the translation of the two coordinate systems is calculated. \n" \
                  + "Note: It is assumed that the chip and stage coordinate axes are parallel, which is not necessarily the case. Therefore this is only an approximation.")
        step_description.pack(side=TOP, fill=X)

        ttk.Separator(
            frame,
            orient=VERTICAL
        ).pack(side=TOP, fill=X, pady=10)

        for calibration in self.mover.calibrations.values():
            fix_point_calibration_frame = Frame(frame)
            fix_point_calibration_frame.pack(side=TOP, fill=X, pady=2)

            Label(
                fix_point_calibration_frame,
                text=str(calibration),
                font='Helvetica 12 bold'
            ).pack(side=LEFT)

            Button(
                fix_point_calibration_frame,
                text="New Single Point Calibration",
                command=partial(self._on_new_single_point_transformation, calibration)
            ).pack(side=RIGHT)

            current_single_point_transformation = self._current_single_point_transformations.get(calibration)
            if current_single_point_transformation:
                Label(
                    fix_point_calibration_frame,
                    text=str(current_single_point_transformation),
                    foreground="#4BB543",
                ).pack(side=RIGHT)
            else:
                Label(
                    fix_point_calibration_frame,
                    text="Single Point not fixed",
                    foreground="#FF3333",
                ).pack(side=RIGHT)

        ttk.Separator(
            frame,
            orient=VERTICAL
        ).pack(side=TOP, fill=X, pady=10)


    def _fully_calibration_step_builder(self, frame):
        frame.title = "Fully calibrate mover stages"

        step_description = Label(
            frame,
            text="To fully calibrate the stages globally, define at least 2 or 3 stage to chip parings."
        )
        step_description.pack(side=TOP, fill=X)

        ttk.Separator(
            frame,
            orient=VERTICAL
        ).pack(side=TOP, fill=X, pady=10)

        for calibration in self.mover.calibrations.values():
            fully_calibration_frame = Frame(frame)
            fully_calibration_frame.pack(side=TOP, fill=X, pady=2)

            Label(
                fully_calibration_frame,
                text=str(calibration),
                font='Helvetica 12 bold'
            ).pack(side=LEFT)

            Button(
                fully_calibration_frame,
                text="New Fully Calibration",
                command=partial(self._on_new_full_transformation, calibration)
            ).pack(side=RIGHT)

            current_full_transformation = self._current_full_transformations.get(calibration)
            if current_full_transformation:
                Label(
                    fully_calibration_frame,
                    text=str(current_full_transformation),
                    foreground="#4BB543",
                ).pack(side=RIGHT)
            else:
                Label(
                    fully_calibration_frame,
                    text="Not fully calibrated",
                    foreground="#FF3333",
                ).pack(side=RIGHT)

        ttk.Separator(
            frame,
            orient=VERTICAL
        ).pack(side=TOP, fill=X, pady=10)

    #
    #   Callback
    #

    def _save(self):
        pass
        # for calibration in self.mover.calibrations.values():
        #     calibration.axes_calibration = self._current_axis_calibration[calibration]
        #     print(calibration.axes_calibration_matrix)


    def _on_axis_calibrate(
            self,
            calibration: Type[Calibration],
            chip_axis: Axis,
            selection: str):
        """
        Callback, when user changes stage to chip axis mapping.

        Updates current axis calibration.
        """
        axis_calibration = self._current_axis_calibration.setdefault(calibration, {})
        axis_calibration[chip_axis] = self._axis_calibration_options.get(selection, (chip_axis, Direction.POSITIVE))
        self.__reload__()


    def _on_new_single_point_transformation(self, calibration: Type[Calibration]):
        """
        Callback, when user wants to create a new single point transformation.
        """
        current_transformation = self._current_single_point_transformations.get(calibration)
        if current_transformation:
            message = "There is already a single-point transformation for the stage." \
                    + "If you continue, the current one will be deleted and replaced by the new one. Do you want to continue?"
            if not messagebox.askyesno("New Transformation", message):
                return

        new_transformation = SinglePointFixation.setup(self, self.mover, calibration)
        if new_transformation:
            self._current_single_point_transformations[calibration] = new_transformation

        self.__reload__()


    def _on_new_full_transformation(self, calibration: Type[Calibration]):
        """
        Callback, when user wants to create a new transformation based on Kabsch Algorithm.
        """
        current_transformation = self._current_full_transformations.get(calibration)
        if current_transformation:
            message = "There is already a transformation for the stage." \
                    + "If you continue, the current one will be deleted and replaced by the new one. Do you want to continue?"
            if not messagebox.askyesno("New Transformation", message):
                return

        new_transformation = KabschRotation.setup(self, self.mover, calibration)
        if new_transformation:
            self._current_full_transformations[calibration] = new_transformation

        self.__reload__()


    def _check_axis_calibration(self):
        """
        Callback, when coordinate system fixation step gets reloaded.

        Checks, if the current assignment is valid.
        """
        if all(map(is_axis_calibration_valid,
                   self._current_axis_calibration.values())):
            self.current_step.next_step_enabled = True
            self.set_error("")
        else:
            self.current_step.next_step_enabled = False
            self.set_error("Please do not assign a stage axis twice. ")


    def _check_single_point_transformations(self):
        if all(self._current_single_point_transformations.get(c) for c in self.mover.calibrations.values()):
            self.current_step.next_step_enabled = True
            self.set_error("")
        else:
            self.current_step.next_step_enabled = False
            self.set_error("Please do a single point transformation for each stage.")


    def _on_wiggle_axis(self, calibration: Type[Calibration], chip_axis: Axis):
        """
        Callback, when user what to wiggle a requested axis.

        Will save the current axis calibration and ask user before proceeding.
        """
        if self._performing_wiggle:
            messagebox.showerror("Error", "Stage cannot wiggle because another stage is being wiggled. ")
            return

        message = 'By proceeding this button will move the {} along the {} direction. \n\n'.format(calibration, chip_axis) \
                  + 'Please make sure it has enough travel range(+-5mm) to avoid collision. \n\n' \
                  + 'For correct operation the stage should: \n' \
                  + 'First: Move in positive {}-Chip-Axis direction \n'.format(chip_axis) \
                  + 'Second: Move in negative {}-Chip-Axis direction \n\n'.format(chip_axis) \
                  + 'If not, please check your assignments.\n Do you want to proceed with wiggling?'

        if messagebox.askokcancel("Warning", message):
            try:
                calibration.fix_coordinate_system(self._current_axis_calibration[calibration])
                self._performing_wiggle = True
                run_with_wait_window(self, "Wiggling {} of {}".format(chip_axis, calibration),
                    lambda: calibration.wiggle_axis(chip_axis)
                )
            except Exception as e:
                messagebox.showerror("Error", "Could not wiggle {}! Reason: {}".format(calibration, e))
            finally:
                self._performing_wiggle = False

        self.lift()

    #
    #   Helper
    #

    def _axis_calibration_option_key(self, axis_mapping):
        return "{} {}".format(axis_mapping[1], axis_mapping[0])

