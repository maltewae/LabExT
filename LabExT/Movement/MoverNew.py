#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LabExT  Copyright (C) 2021  ETH Zurich and Polariton Technologies AG
This program is free software and comes with ABSOLUTELY NO WARRANTY; for details see LICENSE file.
"""

from enum import Enum
import logging
from typing import Dict, Tuple, Type, List
from functools import wraps

from LabExT.Movement.Stage import Stage
from LabExT.Movement.Calibration import Calibration, DevicePosition, Orientation, State


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


def is_stage_assignment_valid(assignment) -> bool:
    """
    Returns a decision whether a given mapping is valid.
    """
    # At least one mapping
    if len(assignment) == 0:
        return False

    # No double assignments
    return len(assignment.values()) == len(set(assignment.values()))


class MoverError(RuntimeError):
    pass


class MoverNew:

    # For range constants: See SmarAct Control Guide for more details.
    # Both ranges are inclusive, e.g speed in [SPEED_LOWER_BOUND, SPEED_UPPER_BOUND]
    SPEED_LOWER_BOUND = 0
    SPEED_UPPER_BOUND = 1e5

    ACCELERATION_LOWER_BOUND = 0
    ACCELERATION_UPPER_BOUND = 1e7

    # Reasonable default values
    DEFAULT_SPEED_XY = 200
    DEFAULT_SPEED_Z = 20
    DEFAULT_ACCELERATION_XY = 0

    def __init__(self, experiment_manager):
        """Constructor.

        Parameters
        ----------
        experiment_manager : ExperimentManager
            Current instance of ExperimentManager.
        """
        self.experiment_manager = experiment_manager
        self.logger = logging.getLogger()

        self._stage_classes: List[Stage] = []
        self._available_stages: List[Type[Stage]] = []
        self._calibrations: Dict[Orientation, Type[Calibration]] = {}

        self._speed_xy = self.DEFAULT_SPEED_XY
        self._speed_z = self.DEFAULT_SPEED_Z
        self._acceleration_xy = self.DEFAULT_ACCELERATION_XY

        self.reload_stages()
        self.reload_stage_classes()


    def __del__(self):
        """Collects all settings and stores them in a file"""
        pass

    
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

    
    @property
    def state(self) -> State:
        if not self.calibrations:
            return State.UNINITIALIZED

        calibration_states = set([c.state.value for c in self.calibrations.values()])
        return State(min(calibration_states))


    @property
    def stage_classes(self) -> List[Stage]:
        """
        Returns a list of all Stage classes.
        Simply put, this function returns all subclasses of the Stage class in LabExT.

        Read-only.
        """
        return self._stage_classes


    @property
    def available_stages(self) -> List[Type[Stage]]:
        """
        Returns a list of stages connected to the computer (all possible connection types)
        For example: For SmarAct Stages, this function returns all USB-connected stages. 

        Note: A connection may or may not be established to the stages.

        Read-only.
        """
        return self._available_stages
 
    
    @property
    def calibrations(self) -> Dict[Orientation, Type[Calibration]]:
        """
        Returns a mapping between orientation (right, left, top, bottom) and an calibration object.
        """
        return self._calibrations


    @property
    def stages(self) -> List[Type[Stage]]:
        """
        Returns a list of all active stages.

        A stage is active when it was assigned to an orientation.
        """
        return [c.stage for c in self._calibrations.values()]


    @property
    def connected_stages(self) -> List[Type[Stage]]:
        """
        Returns a list of all active and connected stages.

        A stage is active when it has been assigned to an orientation.
        A stage is connected when the connect()-function has been successfully applied to it.
        """
        return list(filter(lambda s: s.connected, self.stages))

    
    @property
    def has_connected_stages(self) -> bool:
        """
        Returns a decision if the mover has any connected and assigned stages
        """
        return len(self.connected_stages) != 0

    
    def add_stage_calibration(self, stage: Type[Stage], orientation: Type[Orientation], position: Type[DevicePosition]) -> Type[Calibration]:
        """
        Creates a new Calibration instance for stage.
        Adds this instance to the list of connected stages.

        Raises MoverError, if orientation, position is invalid or if Stage has been used before.

        Returns new calibration instance.
        """
        if orientation not in Orientation:
            raise MoverError("{} is an invalid stage orientation".format(orientation))

        if position not in DevicePosition:
            raise MoverError("{} is an invalid device position".format(position))

        if stage in self.stages:
            raise MoverError("{} has already been assigned.".format(str(stage)))

        calibration = Calibration(self, stage, orientation=orientation, device_position=position)
        self._calibrations[orientation] = calibration
        return calibration

    #
    #   Settings methods
    #

    @property
    @assert_connected_stages
    def speed_xy(self) -> float:
        """
        Returns the XY speed of all connected stages. 
        If a stage has a different speed than stored in the Mover object (self._speed_xy), it will be changed to the stored one. 
        """
        speed_vector = self._call_on_connected_stages("get_speed_xy")
        if not self._check_stage_consistency(speed_vector, self._speed_xy):
            self.logger.info("Mover and Stage acceleration differ! Setting stage to stored one")
            self.speed_xy = self._speed_xy
        
        return self._speed_xy

    @speed_xy.setter
    @assert_connected_stages
    def speed_xy(self, umps: float):
        """
        Sets the XY speed for all connected stages to umps.

        Throws MoverError if a change of a stage does not work.
        Stores the speed internally in the Mover object.
        """
        if umps < self.SPEED_LOWER_BOUND or umps > self.SPEED_UPPER_BOUND:
            raise ValueError("Speed for xy is out of valid range.")

        for stage in self.connected_stages:
            try:
                stage.set_speed_xy(umps)
            except RuntimeError as exec:
                raise MoverError("Setting xy speed for {} failed: {}".format(stage, exec))
        self._speed_xy = umps


    @property
    @assert_connected_stages
    def speed_z(self) -> float:
        """
        Returns the Z speed of all connected stages. 
        If a stage has a different speed than stored in the Mover object (self._speed_z), it will be changed to the stored one. 
        """
        speed_vector = self._call_on_connected_stages("get_speed_z")
        if not self._check_stage_consistency(speed_vector, self._speed_z):
            self.logger.info("Mover and Stage speed differ! Setting stage to stored one")
            self.speed_z = self._speed_z

        return self._speed_z


    @speed_z.setter
    @assert_connected_stages
    def speed_z(self, umps: float):
        """
        Sets the Z speed for all connected stages to umps.

        Throws MoverError if a change of a stage does not work.
        Stores the speed internally in the Mover object.
        """
        if umps < self.SPEED_LOWER_BOUND or umps > self.SPEED_UPPER_BOUND:
            raise ValueError("Speed for xy is out of valid range.")
        
        for stage in self.connected_stages:
            try:
                stage.set_speed_z(umps)
            except RuntimeError as exec:
                raise MoverError("Setting z speed for {} failed: {}".format(stage, exec))
        self._speed_z = umps


    @property
    @assert_connected_stages
    def acceleration_xy(self) -> float:
        """
        Returns the XY acceleration of all connected stages. 
        If a stage has a different acceleration than stored in the Mover object (self._acceleration_xy), it will be changed to the stored one. 
        """
        acceleration_vector = self._call_on_connected_stages("get_acceleration_xy")
        if not self._check_stage_consistency(acceleration_vector, self._acceleration_xy):
            self.logger.info("Mover and Stage acceleration differ! Setting stage to stored one")
            self.acceleration_xy = self._acceleration_xy

        return self._acceleration_xy


    @acceleration_xy.setter
    @assert_connected_stages
    def acceleration_xy(self, umps2: float):
        """
        Sets the XY acceleration for all connected stages to umps2.

        Throws MoverError if a change of a stage does not work.
        Stores the speed internally in the Mover object.
        """
        if umps2 < self.ACCELERATION_LOWER_BOUND or umps2 > self.ACCELERATION_LOWER_BOUND:
            raise ValueError("Acceleration for xy is out of valid range.")
        
        for stage in self.connected_stages:
            try:
                stage.set_acceleration_xy(umps2)
            except RuntimeError as exec:
                raise MoverError("Setting xy acceleration for {} failed: {}".format(stage, exec))
        self._acceleration_xy = umps2


    #
    #   Helpers
    #

    def _call_on_connected_stages(self, func: str) -> list:
        """
        Applies the function given by func to all connected stages and returns the results as a List.

        Throws AttributeError if func is not defined on stage object.
        """
        return [getattr(s.stage, func) for s in self.connected_stages]

    def _check_stage_consistency(self, vector: list, default_value: float) -> bool:
        """
        Returns a decision, if all values in a list are the same as a given default value.
        """
        return all(default_value == speed for speed in vector)
