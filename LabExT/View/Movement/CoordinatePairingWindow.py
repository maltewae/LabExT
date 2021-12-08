#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LabExT  Copyright (C) 2022  ETH Zurich and Polariton Technologies AG
This program is free software and comes with ABSOLUTELY NO WARRANTY; for details see LICENSE file.
"""

from tkinter import Toplevel, Button, Label, OptionMenu, StringVar, messagebox
from tkinter.constants import LEFT, OUTSIDE, RIGHT, TOP, X
from typing import List, Type
from LabExT.Movement.Calibration import Calibration, DevicePosition
from LabExT.Movement.MoverNew import MoverNew
from LabExT.View.Controls.CustomFrame import CustomFrame
from LabExT.View.Controls.DeviceTable import DeviceTable

import LabExT.Movement.Transformations as Transformations

class CoordinatePairingWindow(Toplevel):

    STAGE_MENU_PLACEHOLDER = "-- select a stage --"

    def __init__(self, parent, mover, calibration):
        self.parent = parent
        self.mover: Type[MoverNew] = mover
        self.calibration: Type[Calibration] = calibration

        super(CoordinatePairingWindow, self).__init__(parent)
        self.title("Create Chip-Stage-Coordinate Pairing")
        self.wm_geometry("{width:d}x{height:d}".format(width=600, height=400))
        self.protocol('WM_DELETE_WINDOW', self.destroy)

        # Intermediate states
        self._device = None
        self._stage_coordinate = None

        self.__setup__()


    @property
    def pairing(self):
        """
        Returns a coordinate pairing if device and stage coordinate is defined, otherwise None. 
        """
        if not self._device or not self._stage_coordinate:
            return None

        return Transformations.CoordinatePairing(
            self.calibration,
            self._stage_coordinate,
            self._device,
            self._device.in_position if self.calibration.is_input_stage else self._device.out_position
        )


    def __setup__(self):
        """
        Builds all widgets based on current state.
        """
        description = Label(
            self,
            text="In the following, create a matching between a stage and chip coordinate.")
        description.pack(side=TOP, fill=X)

        self._select_device_step()
        if not self._device:
            return

        self._move_stage_to_device_position_step()

        Button(
            self,
            text="Save Coordinate Paring",
            command=self._on_finish,
            width=15
        ).pack(side=TOP, anchor='nw')


    def __reload__(self):
        for child in self.winfo_children():
            child.forget()

        self.__setup__()
        self.update_idletasks()


    def _select_device_step(self):
        """
        Renders a frame to select a device.
        """
        frame = CustomFrame(self)
        frame.title = "1. Select a device to fix a chip coordinate"
        frame.pack(side=TOP, fill=X, pady=2, padx=5)

        hint = Label(
            frame,
            text="The selected stage uses the {} position of the device. Therefore, the {} position of the selected device is taken as the chip coordinate.".format(
                self.calibration.device_position,
                self.calibration.device_position
            )
        )
        hint.pack(side=TOP, fill=X)

        if not self._device:
            self._device_table = DeviceTable(frame, self.mover.experiment_manager)
            self._device_table.pack(side=TOP, fill=X, expand=True)

            Button(
                frame,
                text="Select marked device",
                command=self._on_device_selection
            ).pack(side=LEFT, pady=2)
        else:
            Label(
                frame,
                text="Device ID: {}, {}-Coordinate: {}".format(self._device._id, self.calibration.device_position, self._chip_coordinate),
                font='Helvetica 12 bold'
            ).pack(side=LEFT, fill=X)
            
            Button(
                frame,
                text="Clear selection",
                command=self._on_device_selection_clear
            ).pack(side=LEFT, padx=5)


    def _move_stage_to_device_position_step(self):
        """
        Renders a frame that prompts the user to move the stage to the device.
        """
        frame = CustomFrame(self)
        frame.title = "2. Move Stage to selected Chip-Coordinate"
        frame.pack(side=TOP, fill=X, pady=2, padx=5)

        step_description = Label(
            frame,
            text="Please move the stage to the selected chip point. When you have achieved an optimal coupling, click Finish.")
        step_description.pack(side=TOP, fill=X)


    #
    #   Callbacks
    #

    def _on_finish(self):
        """
        Callback, when user wants to finish paring.

        Calls Stage to get current position and destroys window.
        """
        self._stage_coordinate = self.calibration.stage.get_current_position()
        self.destroy()


    def _on_device_selection(self):
        """
        Callback, when user hits "Select marked device" button.
        """
        self._device = self._device_table.get_selected_device()
        if self._device is None:
            messagebox.showwarning('Selection Needed', 'Please select one device.', parent=self)
            return
        
        if self.calibration.device_position == DevicePosition.INPUT:
            self._chip_coordinate = self._device._in_position
        elif self.calibration.device_position == DevicePosition.OUTPUT:
            self._chip_coordinate = self._device._out_position

        self.__reload__()


    def _on_device_selection_clear(self):
        """
        Callback, when user wants to clear the current device selection.
        """
        self._device = None
        self._chip_coordinate = None
        self.__reload__()
