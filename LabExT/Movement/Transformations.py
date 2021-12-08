#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LabExT  Copyright (C) 2022  ETH Zurich and Polariton Technologies AG
This program is free software and comes with ABSOLUTELY NO WARRANTY; for details see LICENSE file.
"""

from abc import ABC, abstractclassmethod, abstractmethod
from tkinter import messagebox
from tkinter.constants import TOP, X
from typing import NamedTuple, Type
import numpy as np
from LabExT import rmsd

from LabExT.Movement.Calibration import Calibration
from LabExT.Wafer.Device import Device

from LabExT.View.Movement.CoordinatePairingWindow import CoordinatePairingWindow
from LabExT.View.Movement.KabschRotationWindow import KabschRotationWindow

class Transformation(ABC):
    """
    Abstract interface for transformations.
    """

    @abstractclassmethod
    def setup(cls):
        """
        Set up the transformation.

        Returns transformation object on success.
        """
        pass


    @abstractmethod
    def __init__(self) -> None:
        pass


    @abstractmethod
    def chip_to_stage(self, chip_coordinate):
        """
        Transforms a coordinate in chip space to stage space.
        """
        pass


    @abstractmethod
    def stage_to_chip(self, stage_coordinate):
        """
        Transforms a coordinate in stage space to chip space.
        """
        pass


    def mean_error(self, stage_coordinate=None, chip_coordinate=None):
        pass


class CoordinatePairing(NamedTuple):
    calibration: Type[Calibration]
    stage_coordinate: list
    device: Type[Device]
    chip_coordinate: list


class SinglePointFixation(Transformation):
    """
    Performs a transformation based on a fixed single point.
    """

    @classmethod
    def setup(self, parent, mover, calibration) -> Type[Transformation]:
        """
        Setup routine for single point transformation.
        """
        setup_window = CoordinatePairingWindow(parent, mover, calibration)
        parent.wait_window(setup_window)

        pairing = setup_window.pairing
        if pairing:
            return SinglePointFixation(pairing.chip_coordinate, pairing.stage_coordinate)
        else:
            messagebox.showerror("Error", "Single Point Transformation failed: No Single Point defined.")


    def __init__(self, chip_coordinate, stage_coordinate) -> None:
        self.chip_coordinate = np.array(chip_coordinate)
        self.stage_coordinate = np.array(stage_coordinate)
        self.offset = self.stage_coordinate - self.chip_coordinate


    def __str__(self) -> str:
        return "Chip-Coord: {} mapped to Stage-Coord: {}".format(self.chip_coordinate, self.stage_coordinate)


    def chip_to_stage(self, chip_coordinate):
        return np.array(chip_coordinate) + self.offset


    def stage_to_chip(self, stage_coordinate):
        return np.array(stage_coordinate) + self.offset


class KabschRotation(Transformation):
    """
    Performs a transformation based on Kabsch Algorithmus.
    """
    
    @classmethod
    def setup(self, parent, mover, calibration) -> Type[Calibration]:
        """
        Setup routine for kabsch transformation.
        """
        setup_window = KabschRotationWindow(parent, mover, calibration)
        parent.wait_window(setup_window)

        pairings = setup_window.pairings
        if pairings:
            return KabschRotation(
                chip_coordinates=[p.chip_coordinate for p in pairings],
                stage_coordinates=[p.stage_coordinate for p in pairings],
                is_2d_transformation=setup_window.is_2d_transformation
            )
        else:
            pass


    def __init__(self, chip_coordinates, stage_coordinates, is_2d_transformation=False) -> None:
        self._chip_coordinates = np.array(chip_coordinates)
        self._stage_coordinates = np.array(stage_coordinates)

        # translate coordinates to origin
        self.chip_offset = rmsd.centroid(self._chip_coordinates)
        self._chip_coordinates = self._chip_coordinates - self.chip_offset

        self.stage_offset = rmsd.centroid(self._stage_coordinates)
        self._stage_coordinates = self._stage_coordinates - self.stage_offset

        # calculate rotation matrix using kabsch algorithm
        self.matrix = rmsd.kabsch(self._chip_coordinates, self._stage_coordinates)
        self.matrix_inverse = np.linalg.inv(self.matrix)


    def chip_to_stage(self, chip_coordinate):
        """
        Transforms a position in chip coordinates to stage coordinates
        """
        chip_coordinate = np.array(chip_coordinate)
        return np.dot(chip_coordinate - self.chip_offset, self.matrix) + self.stage_offset


    def stage_to_chip(self, stage_coordinate):
        """
        Transforms a position in stage coordinates to chip coordinates
        """
        stage_coordinate = np.array(stage_coordinate)
        return np.dot(stage_coordinate - self.stage_offset, self.matrix_inverse) + self.chip_offset
