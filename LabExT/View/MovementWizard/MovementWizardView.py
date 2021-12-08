#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LabExT  Copyright (C) 2022  ETH Zurich and Polariton Technologies AG
This program is free software and comes with ABSOLUTELY NO WARRANTY; for details see LICENSE file.
"""

from functools import partial
from tkinter import Label, Button, Entry, ttk, messagebox, StringVar, OptionMenu, DISABLED, NORMAL, VERTICAL, Frame, Button, Label, DISABLED, NORMAL, LEFT, RIGHT, TOP, X
from typing import Type

from LabExT.Movement.MoverNew import MoverNew, is_stage_assignment_valid
from LabExT.Movement.Calibration import DevicePosition, Orientation
from LabExT.Utils import run_with_wait_window

from LabExT.View.Controls.CustomFrame import CustomFrame
from LabExT.View.Controls.CustomTable import CustomTable
from LabExT.View.Controls.Wizard import Wizard


class MovementWizardView(Wizard):
    """
    Implements a Wizard for set up the stages.
    """

    ASSIGNMENT_MENU_PLACEHOLDER = "-- unused --"

    def __init__(self, parent, controller, mover):
        super().__init__(
            parent,
            width=800,
            height=600,
            on_finish=self._save, 
            cancel_button_label="Cancel and Close",
            finish_button_label="Finish and Save"
        )
        self.title("Stage Setup Wizard")

        self.controller = controller
        self.mover: Type[MoverNew] = mover

        # Current wizard state
        self._current_stage_assignment = {}
        self._current_stage_positions = {}
        self._entry_xy_speed = None
        self._entry_z_speed = None
        self._entry_xy_acceleration = None
        self._entry_z_speed = None

        # Add Wizard Steps
        self.driver_step = self.add_step(self._driver_step_builder, title="Driver Settings")
        self.connection_step = self.add_step(self._connection_step_builder,
            title="Stage Connection",
            on_reload=self._check_assignment
        )
        self.configuration_step = self.add_step(self._configuration_step_builder,
            title="Stage Configuration",
            finish_step_enabled=True
        )

        # Connect Steps
        self.driver_step.next_step = self.connection_step
        self.connection_step.previous_step = self.driver_step
        self.connection_step.next_step = self.configuration_step
        self.configuration_step.previous_step = self.connection_step

        # Define start step
        self.current_step = self.driver_step

    #
    #   Step Builder
    #

    def _driver_step_builder(self, frame: Type[CustomFrame]):
        frame.title = "Load Stage Drivers"

        step_description = Label(
            frame,
            text="Below you can see all Stage classes available in LabExT.\nSo that all stages can be found correctly in the following step, make sure that the drivers for each class are loaded."
        )
        step_description.pack(side=TOP, fill=X)

        ttk.Separator(
            frame,
            orient=VERTICAL).pack(
            side=TOP,
            fill=X,
            pady=10)

        for stage_class in self.mover.stage_classes:
            stage_driver_frame = Frame(frame)
            stage_driver_frame.pack(side=TOP, fill=X, pady=2)

            stage_driver_label = Label(
                stage_driver_frame,
                text="[{}] {}".format(
                    stage_class.__name__,
                    stage_class.description))
            stage_driver_label.pack(side=LEFT, fill=X)

            stage_driver_load = Button(
                stage_driver_frame,
                text="Load Driver",
                state=NORMAL if stage_class.driver_specifiable else DISABLED,
                command=partial(self.controller.load_driver, stage_class)
            )
            stage_driver_load.pack(side=RIGHT)

            stage_driver_status = Label(
                stage_driver_frame,
                text="Loaded" if stage_class.driver_loaded else "Not Loaded",
                foreground='#4BB543' if stage_class.driver_loaded else "#FF3333",
            )
            stage_driver_status.pack(side=RIGHT, padx=10)


    def _connection_step_builder(self, frame: Type[CustomFrame]):
        frame.title = "Manage Stage Connections"

        step_description = Label(
            frame,
            text="Below you can see all the stages found by LabExT.\nIf stages are missing, go back one step and check if all drivers are loaded."
        )
        step_description.pack(side=TOP, fill=X)

        available_stages_frame = CustomFrame(frame)
        available_stages_frame.title = "Available Stages"
        available_stages_frame.pack(side=TOP, fill=X)

        CustomTable(
            parent=available_stages_frame,
            selectmode='none',
            columns=(
                'ID',
                'Stage Description',
                'Stage Class',
                'Connection Type',
                'Connection Address',
                'Connected'),
            rows=[
                (idx,
                 s.__class__.description,
                 s.__class__.__name__,
                 s.__class__.connection_type,
                 s.address_string,
                 s.connected) for idx,
                s in enumerate(
                    self.mover.available_stages)])

        stage_assignment_frame = CustomFrame(frame)
        stage_assignment_frame.title = "Assign Stages"
        stage_assignment_frame.pack(side=TOP, fill=X)

        for available_stage in self.mover.available_stages:
            available_stage_frame =  Frame(stage_assignment_frame)
            available_stage_frame.pack(side=TOP, fill=X, pady=2)

            Label(
                available_stage_frame, text=str(available_stage), anchor="w"
            ).pack(side=LEFT, fill=X, padx=(0, 10))

            position = StringVar(self.parent)
            position.set(self._current_stage_positions.get(available_stage, DevicePosition.INPUT))
            position_menu = OptionMenu(
                available_stage_frame,
                position,
                *(list(DevicePosition)),
                command=partial(self._on_stage_position, available_stage)
            )
            position_menu.pack(side=RIGHT, padx=5)

            orientation = StringVar(self.parent)
            orientation.set(self._current_stage_assignment.get(available_stage, self.ASSIGNMENT_MENU_PLACEHOLDER))
            orientation_menu = OptionMenu(
                available_stage_frame,
                orientation,
                *([self.ASSIGNMENT_MENU_PLACEHOLDER] + list(Orientation)),
                command=partial(self._on_stage_assignment, available_stage)
            )
            orientation_menu.pack(side=RIGHT, padx=5) 


    def _configuration_step_builder(self, frame: Type[CustomFrame]):
        frame.title = "Configure Connected Stages"

        step_description = Label(
            frame,
            text="Configure the selected stages.\nThese settings are applied globally to all selected stages."
        )
        step_description.pack(side=TOP, fill=X)

        stage_properties_frame = CustomFrame(frame)
        stage_properties_frame.title = "Speed and Acceleration Settings"
        stage_properties_frame.pack(side=TOP, fill=X)

        Label(
            stage_properties_frame,
            anchor="w",
            text="Speed Hint: A value of 0 (default) deactivates the speed control feature. The stage will move as fast as possible!"
        ).pack(side=TOP, fill=X)
        Label(
            stage_properties_frame,
            anchor="w",
            text="Acceleration Hint: A value of 0 (default) deactivates the acceleration control feature."
        ).pack(side=TOP, fill=X)

        ttk.Separator(
            stage_properties_frame,
            orient=VERTICAL
        ).pack(side=TOP, fill=X, pady=10)

        self._entry_xy_speed = self._build_entry_with_label(
            stage_properties_frame,
            label="Movement speed xy direction (valid range: {}...{:.0e}um/s):".format(
                self.mover.SPEED_LOWER_BOUND,
                self.mover.SPEED_UPPER_BOUND),
            unit="[um/s]",
            value=self.mover.DEFAULT_SPEED_XY)

        self._entry_z_speed = self._build_entry_with_label(
            stage_properties_frame,
            label="Movement speed z direction (valid range: {}...{:.0e}um/s):".format(
                self.mover.SPEED_LOWER_BOUND,
                self.mover.SPEED_UPPER_BOUND),
            unit="[um/s]",
            value=self.mover.DEFAULT_SPEED_Z)

        self._entry_xy_acceleration = self._build_entry_with_label(
            stage_properties_frame,
            label="Movement acceleration xy direction (valid range: {}...{:.0e}um/s^2):".format(
                self.mover.ACCELERATION_LOWER_BOUND,
                self.mover.ACCELERATION_UPPER_BOUND),
            unit="[um/s^2]",
            value=self.mover.DEFAULT_ACCELERATION_XY)

    #
    #   Callbacks
    #

    def _save(self):
        speed_xy = self._get_entry_value(
            self._entry_xy_speed,
            to_type=float,
            default=self.mover.DEFAULT_SPEED_XY)
        speed_z = self._get_entry_value(
            self._entry_z_speed,
            to_type=float,
            default=self.mover.DEFAULT_SPEED_Z)
        acceleration_xy = self._get_entry_value(
            self._entry_xy_acceleration,
            to_type=float,
            default=self.mover.DEFAULT_ACCELERATION_XY)

        if self._warn_user_about_zero_speed(speed_xy) and self._warn_user_about_zero_speed(speed_z):
            try:
                self.controller.save(
                    stage_assignment=self._current_stage_assignment,
                    stage_positions=self._current_stage_positions,
                    speed_xy=speed_xy,
                    speed_z=speed_z,
                    acceleration_xy=acceleration_xy
                )
                messagebox.showinfo(message="Successfully connected to {} stages.".format(len(self.mover.connected_stages)))
                return True
            except Exception as e:
                messagebox.showerror(message="Could not setup stages. Reason: {}".format(e))
                self.current_step = self.configuration_step
                return False


    def _on_stage_assignment(self, stage, selected_orientation: Orientation):
        if not stage in self.mover.available_stages:
            return

        if selected_orientation == self.ASSIGNMENT_MENU_PLACEHOLDER:
            del self._current_stage_assignment[stage]
        else:
            if selected_orientation in Orientation:
                self._current_stage_assignment[stage] = selected_orientation
        
        self.__reload__()


    def _on_stage_position(self, stage, selected_position: DevicePosition):
        if not stage in self.mover.available_stages:
            return

        if selected_position in DevicePosition:
            self._current_stage_positions[stage] = selected_position

        self.__reload__()
        

    def _check_assignment(self):
        if is_stage_assignment_valid(self._current_stage_assignment):
            self.current_step.next_step_enabled = True
            self.set_error("")
        else:
            self.current_step.next_step_enabled = False
            self.set_error("Please assign at least one stage and do not select a stage twice.")

    #
    #   Frame Helpers
    #

    def _build_entry_with_label(
            self,
            parent,
            label: str = None,
            unit: str = None,
            value=None) -> Entry:
        entry_frame = Frame(parent)
        entry_frame.pack(side=TOP, fill=X, pady=2)

        Label(entry_frame, text=label).pack(side=LEFT)
        Label(entry_frame, text=unit).pack(side=RIGHT)
        entry = Entry(entry_frame)
        entry.pack(side=RIGHT, padx=10)

        if value:
            entry.delete(0, 'end')
            entry.insert(0, value)

        return entry

    #
    #   Helpers
    #

    def _get_entry_value(self, entry: Type[Entry], to_type=str, default=None):
        try:
            return to_type(entry.get())
        except (ValueError, TypeError):
            return default

    def _warn_user_about_zero_speed(self, speed) -> bool:
        if speed == 0:
            return messagebox.askokcancel(
                message="Setting speed to 0 will turn the speed control OFF! \n"
                "The stage will now move as fast as possible. Set a different speed if "
                "this is not intended. Do you want still to proceed?")

        return True
