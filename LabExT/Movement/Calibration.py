#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LabExT  Copyright (C) 2021  ETH Zurich and Polariton Technologies AG
This program is free software and comes with ABSOLUTELY NO WARRANTY; for details see LICENSE file.
"""

import time
from enum import Enum
from typing import Type
from LabExT.Movement.Stage import StageError
from LabExT.Utils import CustomEnum
import numpy as np
import logging

def is_axis_calibration_valid(calibration: dict) -> bool:
    """
    Returns a decision whether a given mapping is valid.

    The criteria are: Every stage axis is mapped to a chip axis, no chip axis is assigned twice and
    all directions are valid.
    """
    chip_axes = calibration.keys()
    stage_axes = []
    directions = []
    for mapping in calibration.values():
        stage_axes.append(mapping[0])
        directions.append(mapping[1])

    # Check if direction are valid
    if not set(directions).issubset(set(Direction)):
        return False

    # Check if every stage axis and chip axis has an mapping
    return set(Axis) == set(chip_axes) and set(Axis) == set(stage_axes)


class Orientation(CustomEnum):
    """
    Enumerate different state orientations.
    """
    LEFT = 0
    RIGHT = 1
    TOP = 2
    BOTTOM = 3

    def __str__(self) -> str:
        return self.name.capitalize()


class DevicePosition(CustomEnum):
    """Enumerate different device coordinate positions."""
    INPUT = 0
    OUTPUT = 1

    def __str__(self) -> str:
        return self.name.capitalize()

class Axis(CustomEnum):
    """Enumerate different channels. Each channel represents one axis."""
    X = 0
    Y = 1
    Z = 2

    def __str__(self) -> str:
        return "{}-Axis".format(self.name)


class Direction(CustomEnum):
    """
    Enumerate different axis directions.
    """
    POSITIVE = 1
    NEGATIVE = -1

    def __str__(self) -> str:
        return self.name.capitalize()


class State(CustomEnum):
    """
    Enumerate different calibration states.
    """
    UNINITIALIZED = 0
    CONNECTED = 1
    COORDINATE_SYSTEM_FIXED = 2
    SINGLE_POINT_FIXED = 3
    FULLY_CALIBRATED = 4

    def __str__(self) -> str:
        return self.name.replace('_',' ').capitalize()



class Calibration:

    def __init__(self, mover, stage, orientation, device_position) -> None:
        self.logger = logging.getLogger()
        self.mover = mover
        self.stage = stage
        
        # TODO: Make check if (1) stage is connected, (2) stage is member of
        # mover.stages
        
        self.orientation = orientation
        self.device_position = device_position
        self.state = State.CONNECTED if stage.connected else State.UNINITIALIZED

        self._axes_calibration = {}
        self._axes_rotation_matrix = None

        self._single_point_transformation = None
        self.full_transformation = None

        self.set_coordinate_system_to_default()
    

    def __str__(self) -> str:
        return "{} Stage ({})".format(str(self.orientation), str(self.stage))


    def short_str(self) -> str:
        return "{} Stage ({})".format(str(self.orientation), str(self.device_position))


    #
    #   Properties
    #

    @property
    def state(self) -> State:
        return self._state


    @state.setter
    def state(self, state: State):
        self._state = state


    def connect_to_stage(self) -> bool:
        try:
            if self.stage.connect():
                self.state = State(max(self.state.value, State.CONNECTED.value))
                return True
        except StageError as e:
            self.state = State.UNINITIALIZED
            raise e
        
        return False
    

    def fix_coordinate_system(self, axes_calibration: dict) -> bool:
        if not is_axis_calibration_valid(axes_calibration):
            raise ValueError("The given axis calibration is invalid. ")

        self._axes_calibration = axes_calibration

        n = len(self._axes_calibration)
        self._axes_rotation_matrix = np.zeros((n,n))

        for chip_axis, mapping in self._axes_calibration.items():
            stage_axis, direction = mapping
            self._axes_rotation_matrix.itemset((stage_axis.value, chip_axis.value), direction.value)

        self.state = State(max(self.state.value, State.COORDINATE_SYSTEM_FIXED.value))


    def set_coordinate_system_to_default(self):
        self._axes_calibration = {
            Axis.X: (Axis.X, Direction.POSITIVE),
            Axis.Y: (Axis.Y, Direction.POSITIVE),
            Axis.Z: (Axis.Z, Direction.POSITIVE)
        }
        self._axes_rotation_matrix = np.identity(len(self._axes_calibration))


    def fix_single_point(self, single_point_transformation):
        self._single_point_transformation = single_point_transformation
        self.state = State(max(self.state.value, State.SINGLE_POINT_FIXED.value))


    @property
    def orientation(self) -> Orientation:
        return self._orientation


    @orientation.setter
    def orientation(self, orientation: Orientation):
        self._orientation = orientation


    @property
    def axes_calibration(self) -> dict:
        return self._axes_calibration


    @property
    def axes_rotation_matrix(self):
        return self._axes_rotation_matrix


    @property
    def single_point_transformation(self):
        return self._single_point_transformation


    @property
    def is_input_stage(self):
        return self.device_position == DevicePosition.INPUT

    #
    #   Movement Methods
    #

    def move_relative(self, x=0, y=0, z=0):
        """
        Moves the stage accoriding to the chip relative
        """
        x_stage, y_stage, z_stage = self.axes_rotation_matrix.dot(np.array([x, y, z]))
        print('Want to relative move {} to x = {} um, y = {} um and z = {} um'.format(str(self), x_stage, y_stage, z_stage))
        # self.stage.move_relative2(
        #     x_um=x_stage,
        #     y_um=y_stage,
        #     z_um=z_stage)

    def move_absolute(self, x, y):
        """
        Moves the stages absolute, needs transformation before
        """
        pass

    
    def wiggle_axis(self, axis: Axis, wiggle_distance=1e3, wiggle_speed=1e3):
        """
        Wiggles the requested axis positioner in order to enable the user to test the correct direction and axis mapping.
        """
        current_speed_xy = self.stage.get_speed_xy()
        current_speed_z = self.stage.get_speed_z()

        self.stage.set_speed_xy(wiggle_speed)
        self.stage.set_speed_z(wiggle_speed)

        self.move_relative(
            x=wiggle_distance if axis == Axis.X else 0,
            y=wiggle_distance if axis == Axis.Y else 0,
            z=wiggle_distance if axis == Axis.Z else 0,
        )

        time.sleep(2)

        self.move_relative(
            x=-wiggle_distance if axis == Axis.X else 0,
            y=-wiggle_distance if axis == Axis.Y else 0,
            z=-wiggle_distance if axis == Axis.Z else 0,
        )

        self.stage.set_speed_xy(current_speed_xy)
        self.stage.set_speed_z(current_speed_z)


    #
    #   Helpers
    #

    def _raise_error_if_orientation_invalid(self, orientation: Orientation):
        if orientation.value not in Orientation._value2member_map_:
            raise ValueError("Invalid orientation {}".format(str(orientation)))
