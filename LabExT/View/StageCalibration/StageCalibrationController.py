#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LabExT  Copyright (C) 2021  ETH Zurich and Polariton Technologies AG
This program is free software and comes with ABSOLUTELY NO WARRANTY; for details see LICENSE file.
"""

from LabExT.Movement.Calibration import Calibration, DevicePosition, Orientation, Axis
from LabExT.View.StageCalibration.StageCalibrationView import StageCalibrationView

class StageCalibrationController:
    def __init__(self, parent, experiment_manager) -> None:
        self.parent = parent
        self.experiment_manager = experiment_manager
        self.mover = experiment_manager.mover_new

        # # REMOVE ME
        # for idx, stage in enumerate(self.mover.available_stages):
        #     self.mover.add_stage_calibration(stage, Orientation(idx), DevicePosition(idx))
        #     stage.connect()

        self.view = StageCalibrationView(parent, self, self.mover)


        
    def save_coordinate_system_fixation(self, axes_calibration):
        """
        Saves axes calibration.
        """
        for calibration, axes_assignments in axes_calibration.items():
            try:
                calibration.fix_coordinate_system(axes_assignments)
            except Exception as e:
                calibration.set_coordinate_system_to_default()
                self.view.set_error("Calibration failed: {}".format(e))
                return False

        self.experiment_manager.main_window.refresh_context_menu()
        return True

    
    def save_single_point_calibration(self, single_point_transformations):
        """
        Saves single point transformations 
        """
        for calibration, transformation in single_point_transformations.items():
            calibration.fix_single_point(transformation)

        self.experiment_manager.main_window.refresh_context_menu()
        return True