#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LabExT  Copyright (C) 2021  ETH Zurich and Polariton Technologies AG
This program is free software and comes with ABSOLUTELY NO WARRANTY; for details see LICENSE file.
"""

import importlib
import sys
from typing import Type
from tkinter import Tk
from LabExT.Movement.Calibration import DevicePosition

from LabExT.Movement.Stage import StageError, Stage
from LabExT.View.MovementWizard.MovementWizardView import MovementWizardView
from LabExT.Movement.MoverNew import MoverNew, MoverError

class MovementWizardController:
    def __init__(self, parent: Type[Tk], experiment_manager) -> None:
        self.parent = parent
        self.experiment_manager = experiment_manager
        self.mover: Type[MoverNew] = experiment_manager.mover_new
        self.view = MovementWizardView(parent, self, self.mover)


    def save(
        self,
        stage_assignment={},
        stage_positions={},
        speed_xy=None,
        speed_z=None,
        acceleration_xy=None,
    ):
        """
        Saves mover configuration. 

        Throws ValueError if speed or acceleration is not in the valid range.
        Throws MoverError and/or StageError if stage assignment or stage connection did not work.
        """
        # Tell mover to use the assigned stage. Can throw MoverError or StageError
        for stage, orientation in stage_assignment.items():
            stage_position = stage_positions.get(stage, DevicePosition.INPUT)
            calibration = self.mover.add_stage_calibration(stage, orientation=orientation, position=stage_position)
            calibration.connect_to_stage()

        # Setting speed and acceleration values. Can throw StageError and ValueError.
        self.mover.speed_xy = speed_xy
        self.mover.speed_z = speed_z
        self.mover.acceleration_xy = acceleration_xy

        self.close()
    

    def load_driver(self, stage_class: Type[Stage]):
        """
        Invokes the load_driver function of some Stage class.

        If successful, it reloads the Stage module and the wizard.
        """
        if not stage_class.driver_specifiable:
            return

        if stage_class.load_driver(parent=self.view):
            importlib.reload(sys.modules.get(stage_class.__module__))
            self.mover.reload_stages()
            self.view.__reload__()


    def close(self):
        self.experiment_manager.main_window.refresh_context_menu()