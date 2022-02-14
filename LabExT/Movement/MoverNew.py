#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LabExT  Copyright (C) 2022  ETH Zurich and Polariton Technologies AG
This program is free software and comes with ABSOLUTELY NO WARRANTY; for details see LICENSE file.
"""

from bidict import bidict, ValueDuplicationError, KeyDuplicationError, OnDup, RAISE
from typing import Type, List
from functools import wraps

from LabExT.Movement.Stage import Stage
from LabExT.Movement.Calibration import Calibration, DevicePosition, Orientation


def assert_connected_stages(func):
    """
    Use this decorator to assert that the mover has at least one connected stage,
    when calling methods, which require connected stages.
    """

    @wraps(func)
    def wrapper(mover, *args, **kwargs):
        if not mover.has_connected_stages:
            raise MoverError(
                "Function {} needs at least one connected stage. Please use the connection functions beforehand".format(
                    func.__name__))

        return func(mover, *args, **kwargs)
    return wrapper


class MoverError(RuntimeError):
    pass


class MoverNew:
    """
    Entrypoint for all movement in LabExT.
    """

    # For range constants: See SmarAct Control Guide for more details.
    # Both ranges are inclusive, e.g speed in [SPEED_LOWER_BOUND,
    # SPEED_UPPER_BOUND]
    SPEED_LOWER_BOUND = 0
    SPEED_UPPER_BOUND = 1e5

    ACCELERATION_LOWER_BOUND = 0
    ACCELERATION_UPPER_BOUND = 1e7

    # Reasonable default values
    DEFAULT_SPEED_XY = 200.0
    DEFAULT_SPEED_Z = 20.0
    DEFAULT_ACCELERATION_XY = 0.0

    def __init__(self, experiment_manager):
        """Constructor.

        Parameters
        ----------
        experiment_manager : ExperimentManager
            Current instance of ExperimentManager.
        """
        self.experiment_manager = experiment_manager

        self._stage_classes: List[Stage] = []
        self._available_stages: List[Type[Stage]] = []

        # Mover state
        self._calibrations = bidict()
        self._position_by_orientation = bidict()
        self._speed_xy = None
        self._speed_z = None
        self._acceleration_xy = None

        self.reload_stages()
        self.reload_stage_classes()

    def reset(self):
        """
        Resets Mover state.
        """
        self._calibrations = bidict()
        self._position_by_orientation = bidict()
        self._speed_xy = None
        self._speed_z = None
        self._acceleration_xy = None

    #
    #   Reload properties
    #

    def reload_stages(self) -> None:
        """
        Loads all available stages.
        """
        self._available_stages = Stage.find_available_stages()

    def reload_stage_classes(self) -> None:
        """
        Loads all Stage classes.
        """
        self._stage_classes = Stage.find_stage_classes()

    #
    #   Properties
    #

    @property
    def stage_classes(self) -> List[Stage]:
        """
        Returns a list of all Stage classes.
        Read-only.
        """
        return self._stage_classes

    @property
    def available_stages(self) -> List[Type[Stage]]:
        """
        Returns a list of stages available to the computer (all possible connection types)
        For example: For SmarAct Stages, this function returns all USB-connected stages.
        Read-only.
        """
        return self._available_stages

    @property
    def calibrations(self):
        """
        Returns a mapping: Calibration -> (orientation, device_position) instance
        Read-only. Use add_stage_calibration to register a new stage.
        """

        return self._calibrations

    @property
    def active_stages(self) -> List[Type[Stage]]:
        """
        Returns a list of all active stages. A stage is called active if it has been assigned
        to an orientation and device position
        """
        return [c.stage for c in self._calibrations.values()]

    @property
    def connected_stages(self) -> List[Type[Stage]]:
        """
        Returns a list of all connected stages.
        """
        return [s for s in self.active_stages if s.connected]

    @property
    def has_connected_stages(self) -> bool:
        """
        Returns True if any of the connected stage is connected (opened a connection to the stage).
        """
        return len(self.connected_stages) > 0

    @property
    def left_calibration(self): return self._get_calibration(
        orientation=Orientation.LEFT)

    @property
    def right_calibration(self): return self._get_calibration(
        orientation=Orientation.RIGHT)

    @property
    def top_calibration(self): return self._get_calibration(
        orientation=Orientation.TOP)

    @property
    def bottom_calibration(self): return self._get_calibration(
        orientation=Orientation.BOTTOM)

    @property
    def input_calibration(self): return self._get_calibration(
        position=DevicePosition.INPUT)

    @property
    def output_calibration(self): return self._get_calibration(
        position=DevicePosition.OUTPUT)

    #
    #   Add new stage
    #

    def add_stage_calibration(
            self,
            stage: Type[Stage],
            orientation: Orientation,
            position: DevicePosition) -> Type[Calibration]:
        """
        Creates a new Calibration instance for a stage.
        Adds this instance to the list of connected stages.

        Raises ValueError, if orientation or device position is invalid.
        Raises MoverError, if Stage has been used before.

        Returns new calibration instance.
        """
        if not isinstance(position, DevicePosition):
            raise ValueError("{} is an invalid position".format(position))

        if not isinstance(orientation, Orientation):
            raise ValueError(
                "{} is an invalid orientation".format(orientation))

        try:
            self._position_by_orientation.put(
                orientation, position, OnDup(key=RAISE))
        except ValueDuplicationError:
            raise MoverError(
                "A stage has already been assigned for the {} position.".format(position))
        except KeyDuplicationError:
            raise MoverError(
                "A stage has already been assigned for {}.".format(orientation))

        calibration = Calibration(self, stage, orientation, position)

        if stage in self.active_stages:
            del self._position_by_orientation[orientation]
            raise MoverError(
                "Stage {} has already an assignment.".format(stage))

        self._calibrations.put(
            (orientation, position), calibration, OnDup(
                key=RAISE))
        return calibration

    #
    #   Stage Settings Methods
    #

    @property
    @assert_connected_stages
    def speed_xy(self) -> float:
        """
        Returns the XY speed of all connected stages.
        If a stage has a different speed than stored in the Mover object (self._speed_xy), it will be changed to the stored one.
        """
        if any(s.get_speed_xy() != self._speed_xy for s in self.connected_stages):
            self.speed_xy = self._speed_xy

        return self._speed_xy

    @speed_xy.setter
    @assert_connected_stages
    def speed_xy(self, umps: float):
        """
        Sets the XY speed for all connected stages to umps.
        Throws MoverError if a change of a stage fails. Stores the speed internally in the Mover object.
        """
        if umps < self.SPEED_LOWER_BOUND or umps > self.SPEED_UPPER_BOUND:
            raise ValueError("Speed for xy is out of valid range.")

        try:
            for stage in self.connected_stages:
                stage.set_speed_xy(umps)
        except RuntimeError as exec:
            raise MoverError("Setting xy speed failed: {}".format(exec))

        self._speed_xy = umps

    @property
    @assert_connected_stages
    def speed_z(self) -> float:
        """
        Returns the Z speed of all connected stages.
        If a stage has a different speed than stored in the Mover object (self._speed_z), it will be changed to the stored one.
        """
        if any(s.get_speed_z() != self._speed_z for s in self.connected_stages):
            self.speed_z = self._speed_z

        return self._speed_z

    @speed_z.setter
    @assert_connected_stages
    def speed_z(self, umps: float):
        """
        Sets the Z speed for all connected stages to umps.
        Throws MoverError if a change of a stage fails. Stores the speed internally in the Mover object.
        """
        if umps < self.SPEED_LOWER_BOUND or umps > self.SPEED_UPPER_BOUND:
            raise ValueError("Speed for z is out of valid range.")

        try:
            for stage in self.connected_stages:
                stage.set_speed_z(umps)
        except RuntimeError as exec:
            raise MoverError("Setting z speed failed: {}".format(exec))

        self._speed_z = umps

    @property
    @assert_connected_stages
    def acceleration_xy(self) -> float:
        """
        Returns the XY acceleration of all connected stages.
        If a stage has a different acceleration than stored in the Mover object (self._acceleration_xy), it will be changed to the stored one.
        """
        if any(s.get_acceleration_xy() !=
               self._acceleration_xy for s in self.connected_stages):
            self.acceleration_xy = self._acceleration_xy

        return self._acceleration_xy

    @acceleration_xy.setter
    @assert_connected_stages
    def acceleration_xy(self, umps2: float):
        """
        Sets the XY acceleration for all connected stages to umps.
        Throws MoverError if a change of a stage fails. Stores the acceleration internally in the Mover object.
        """
        if umps2 < self.ACCELERATION_LOWER_BOUND or umps2 > self.ACCELERATION_UPPER_BOUND:
            raise ValueError("Acceleration for xy is out of valid range.")

        try:
            for stage in self.connected_stages:
                stage.set_acceleration_xy(umps2)
        except RuntimeError as exec:
            raise MoverError("Acceleration xy speed failed: {}".format(exec))

        self._acceleration_xy = umps2

    #
    #   Helpers
    #

    def _get_calibration(self, position=None, orientation=None, default=None):
        """
        Get safely calibration by position and orientation.
        """
        orientation = orientation or self._position_by_orientation.inverse.get(
            position)
        position = position or self._position_by_orientation.get(orientation)
        return self.calibrations.get((orientation, position), default)
