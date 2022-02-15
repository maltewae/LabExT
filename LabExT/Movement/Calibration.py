#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LabExT  Copyright (C) 2022  ETH Zurich and Polariton Technologies AG
This program is free software and comes with ABSOLUTELY NO WARRANTY; for details see LICENSE file.
"""
import time
import numpy as np

from enum import Enum, auto
from LabExT.Movement.Stage import StageError


def is_axis_calibration_valid(calibration: dict) -> bool:
    """
    Returns a decision whether a given mapping is valid.
    The criteria are: Every stage axis is mapped to a chip axis, no chip axis is assigned twice and
    all directions are valid.
    """
    chip_axes = calibration.keys()
    directions, stage_axes = zip(*calibration.values())

    # Check if direction are valid
    if not set(directions).issubset(set(Direction)):
        return False

    # Check if every stage axis and chip axis has an mapping
    return set(Axis) == set(chip_axes) and set(Axis) == set(stage_axes)


def calculate_matrix_by_calibration(calibration: dict):
    """
    Calculates the rotation matrix (Signed permutation matrix) induced by the axes calibration.
    """
    n = len(calibration)
    matrix = np.zeros((n, n))

    for chip_axis, mapping in calibration.items():
        direction, stage_axis = mapping
        matrix.itemset((stage_axis.value, chip_axis.value), direction.value)

    return matrix


class Orientation(Enum):
    """
    Enumerate different state orientations.
    """
    LEFT = auto()
    RIGHT = auto()
    TOP = auto()
    BOTTOM = auto()

    def __str__(self) -> str:
        return self.name.capitalize()


class DevicePosition(Enum):
    """Enumerate different device coordinate positions."""
    INPUT = auto()
    OUTPUT = auto()

    def __str__(self) -> str:
        return self.name.capitalize()


class Axis(Enum):
    """Enumerate different channels. Each channel represents one axis."""
    X = 0
    Y = 1
    Z = 2

    def __str__(self) -> str:
        return "{}-Axis".format(self.name)


class Direction(Enum):
    """
    Enumerate different axis directions.
    """
    POSITIVE = 1
    NEGATIVE = -1

    def __str__(self) -> str:
        return self.name.capitalize()


class State(Enum):
    """
    Enumerate different calibration states.
    """
    UNINITIALIZED = 0
    CONNECTED = 1
    COORDINATE_SYSTEM_FIXED = 2
    SINGLE_POINT_FIXED = 3
    FULLY_CALIBRATED = 4

    def __str__(self) -> str:
        return self.name.replace('_', ' ').capitalize()


class Calibration:
    """
    Represents a calibration of one stage.
    """

    # Will result in a identity matrix
    DEFAULT_AXES_CALIBRATION = {
        Axis.X: (Direction.POSITIVE, Axis.X),
        Axis.Y: (Direction.POSITIVE, Axis.Y),
        Axis.Z: (Direction.POSITIVE, Axis.Z)
    }

    def __init__(self, mover, stage, orientation, device_position) -> None:
        self.mover = mover
        self.stage = stage

        self._state = State.CONNECTED if stage.connected else State.UNINITIALIZED
        self._orientation = orientation
        self._device_position = device_position

        self._axes_calibration = {}
        self._axes_rotation_matrix = None

    #
    #   Representation
    #

    def __str__(self) -> str:
        return "{} Stage ({})".format(str(self.orientation), str(self.stage))

    @property
    def short_str(self) -> str:
        return "{} Stage ({})".format(
            str(self.orientation), str(self._device_position))

    #
    #   Properties
    #

    @property
    def state(self) -> State:
        """
        Returns the current calibration state.
        """
        return self._state

    @property
    def orientation(self) -> Orientation:
        """
        Returns the orientation of the stage: Left, Right, Top or Bottom
        """
        return self._orientation

    @property
    def is_input_stage(self):
        """
        Returns True if the stage will move to the input of a device.
        """
        return self._device_position == DevicePosition.INPUT

    @property
    def is_output_stage(self):
        """
        Returns True if the stage will move to the output of a device.
        """
        return self._device_position == DevicePosition.OUTPUT

    @property
    def axes_calibration(self) -> dict:
        """
        Returns a mapping between the positive chip axis and a stage axis with direction.
        Stage-Axis -> (Chip-Axis, Axis-Direction)
        Read-only.
        """
        return self._axes_calibration

    @property
    def axes_rotation_matrix(self):
        """
        Returns the rotation matrix (Signed permutation matrix) induced by the axes calibration.
        Read-only.
        """
        return self._axes_rotation_matrix

    #
    #   Calibration Setup Methods
    #

    def connect_to_stage(self) -> bool:
        """
        Opens a connections to the stage.
        """
        try:
            if self.stage.connect():
                self._state = State.CONNECTED
                return True
        except StageError as e:
            self._state = State.UNINITIALIZED
            raise e

        return False

    def fix_coordinate_system(self, axes_calibration: dict) -> bool:
        if not is_axis_calibration_valid(axes_calibration):
            raise ValueError("The given axis calibration is invalid. ")

        self._axes_calibration = axes_calibration
        self._axes_rotation_matrix = calculate_matrix_by_calibration(
            axes_calibration)

    #
    #   Movement Methods
    #

    def wiggle_axis(
            self,
            axis: Axis,
            matrix,
            wiggle_distance=1e3,
            wiggle_speed=1e3):
        """
        Wiggles the requested axis positioner in order to enable the user to test the correct direction and axis mapping.
        """
        current_speed_xy = self.stage.get_speed_xy()
        current_speed_z = self.stage.get_speed_z()

        self.stage.set_speed_xy(wiggle_speed)
        self.stage.set_speed_z(wiggle_speed)

        x_stage, y_stage, z_stage = matrix.dot(np.array([
            wiggle_distance if axis == Axis.X else 0,
            wiggle_distance if axis == Axis.Y else 0,
            wiggle_distance if axis == Axis.Z else 0
        ]))

        print(
            'Want to relative move {} to x = {} um, y = {} um and z = {} um'.format(
                str(self),
                x_stage,
                y_stage,
                z_stage))
        # self.stage.move_relative(x_stage, y_stage, z_stage)

        time.sleep(2)

        print(
            'Want to relative move {} to x = {} um, y = {} um and z = {} um'.format(
                str(self), -x_stage, -y_stage, -z_stage))
        # self.stage.move_relative(-x_stage, -y_stage, -z_stage)

        self.stage.set_speed_xy(current_speed_xy)
        self.stage.set_speed_z(current_speed_z)
