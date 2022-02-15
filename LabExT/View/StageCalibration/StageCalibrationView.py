#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LabExT  Copyright (C) 2022  ETH Zurich and Polariton Technologies AG
This program is free software and comes with ABSOLUTELY NO WARRANTY; for details see LICENSE file.
"""

from tkinter import W, Frame, Label, OptionMenu, StringVar, Button, messagebox, NORMAL, DISABLED
from functools import partial
from itertools import product
from tkinter.constants import LEFT, RIGHT, TOP, X
from typing import Type

from LabExT.Movement.Calibration import Calibration, Axis, Direction, is_axis_calibration_valid, calculate_matrix_by_calibration
from LabExT.Utils import run_with_wait_window
from LabExT.View.Controls.CustomFrame import CustomFrame
from LabExT.View.Controls.Wizard import Wizard


class StageCalibrationView(Wizard):

    STAGE_AXIS_OPTIONS = {
        " ".join(map(str, o)): o for o in product(Direction, Axis)}

    def __init__(self, parent, experiment_manager, controller, mover) -> None:
        super().__init__(
            parent,
            width=1000,
            height=700,
            cancel_button_label="Cancel and Close",
            finish_button_label="Finish and Save"
        )
        self.title("Stage Calibration Wizard")

        self.controller = controller
        self.experiment_manager = experiment_manager
        self.mover = mover

        # -- 1. STEP: FIX COORDINATE SYSTEM --
        self.fix_coordinate_system_step = self.add_step(
            self._fix_coordinate_system_step_builder,
            title="Fix Coordinate System",
            on_reload=self._check_axis_calibration,
            on_next=lambda: self.controller.save_coordinate_system(
                self._current_axis_calibration))
        # Step state and variables
        self._performing_wiggle = False
        self._current_axis_calibration = {}
        self._axis_calibration_vars = {}

        for calibration in self.mover.calibrations.values():
            self._current_axis_calibration[calibration] = Calibration.DEFAULT_AXES_CALIBRATION

            axes_vars = {}
            for chip_axis in Axis:
                axes_vars[chip_axis] = StringVar(self.parent, " ".join(
                    map(str, Calibration.DEFAULT_AXES_CALIBRATION[chip_axis])))
                axes_vars[chip_axis].trace(
                    W,
                    lambda *_,
                    calibration=calibration,
                    chip_axis=chip_axis: self._on_axis_calibrate(
                        calibration,
                        chip_axis))

            self._axis_calibration_vars[calibration] = axes_vars

        # Start Wizard by setting the current step
        self.current_step = self.fix_coordinate_system_step

    def _fix_coordinate_system_step_builder(self, frame: Type[CustomFrame]):
        """
        Step builder to fix the coordinate system.
        """
        frame.title = "Fix Coordinate System"

        step_description = Label(
            frame,
            text="In order for each stage to move relative to the chip coordinates, the direction of each axis of each stage must be defined. \n Postive Y-Axis: North of chip, Positive X-Axis: East of chip, Positive Z-Axis: Lift stage")
        step_description.pack(side=TOP, fill=X)

        for calibration in self.mover.calibrations.values():
            stage_calibration_frame = CustomFrame(frame)
            stage_calibration_frame.title = str(calibration)
            stage_calibration_frame.pack(side=TOP, fill=X, pady=2)

            for chip_axis in Axis:
                chip_axis_frame = Frame(stage_calibration_frame)
                chip_axis_frame.pack(side=TOP, fill=X)

                Label(
                    chip_axis_frame,
                    text="Positive {}-Chip-axis points to ".format(chip_axis.name)
                ).pack(side=LEFT)

                OptionMenu(
                    chip_axis_frame,
                    self._axis_calibration_vars[calibration][chip_axis],
                    *self.STAGE_AXIS_OPTIONS.keys(),
                ).pack(side=LEFT)

                Label(chip_axis_frame, text="of Stage").pack(side=LEFT)

                Button(
                    chip_axis_frame,
                    text="Wiggle {}-Axis".format(
                        chip_axis.name),
                    command=partial(
                        self._on_wiggle_axis,
                        calibration,
                        chip_axis),
                    state=NORMAL if is_axis_calibration_valid(
                        self._current_axis_calibration[calibration]) else DISABLED).pack(
                    side=RIGHT)

    #
    #   Callback
    #

    def _on_axis_calibrate(
            self,
            calibration: Type[Calibration],
            chip_axis: Axis):
        """
        Callback, when user changes stage to chip axis mapping.

        Updates current axis calibration.
        """
        selection = self._axis_calibration_vars.get(
            calibration, {}).get(
            chip_axis, StringVar()).get()
        current_calibration = self._current_axis_calibration.setdefault(
            calibration, {})
        current_calibration[chip_axis] = self.STAGE_AXIS_OPTIONS.get(
            selection, (chip_axis, Direction.POSITIVE))
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
            self.set_error("Please do not assign a stage axis twice.")

    def _on_wiggle_axis(self, calibration: Type[Calibration], chip_axis: Axis):
        """
        Callback, when user what to wiggle a requested axis.
        """
        if self._performing_wiggle:
            messagebox.showerror(
                "Error", "Stage cannot wiggle because another stage is being wiggled. ")
            return

        if not is_axis_calibration_valid(
                self._current_axis_calibration[calibration]):
            messagebox.showerror(
                "Error", "Stage cannot wiggle because calibration is invalid. ")
            return

        message = 'By proceeding this button will move the {} along the {} direction. \n\n'.format(calibration, chip_axis) \
                  + 'Please make sure it has enough travel range(+-5mm) to avoid collision. \n\n' \
                  + 'For correct operation the stage should: \n' \
                  + 'First: Move in positive {}-Chip-Axis direction \n'.format(chip_axis) \
                  + 'Second: Move in negative {}-Chip-Axis direction \n\n'.format(chip_axis) \
                  + 'If not, please check your assignments.\n Do you want to proceed with wiggling?'

        if not messagebox.askokcancel("Warning", message):
            return

        try:
            self._performing_wiggle = True
            run_with_wait_window(
                self, description="Wiggling {} of {}".format(
                    chip_axis, calibration), function=lambda: calibration.wiggle_axis(
                    chip_axis, calculate_matrix_by_calibration(
                        self._current_axis_calibration[calibration])))
        except Exception as e:
            messagebox.showerror(
                "Error", "Could not wiggle {}! Reason: {}".format(
                    calibration, e))
        finally:
            self._performing_wiggle = False

        self.lift()
