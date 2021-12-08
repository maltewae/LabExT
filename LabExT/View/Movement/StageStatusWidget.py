#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LabExT  Copyright (C) 2022  ETH Zurich and Polariton Technologies AG
This program is free software and comes with ABSOLUTELY NO WARRANTY; for details see LICENSE file.
"""

from tkinter import Frame, Label
from tkinter.constants import LEFT
from typing import Type

from LabExT.Movement.Stage import Stage
from LabExT.Movement.Calibration import Axis

class StageStatusWidget(Frame):
    """
    Widget to display the status of a stage for each channel. Updates automatically.
    """


    REFRESHING_RATE = 1000 # [ms]

    def __init__(self, parent, stage: Type[Stage]):
        super(StageStatusWidget, self).__init__(parent)
        self.stage = stage

        # Status Labels
        self._status_labels = []

        for idx, status in enumerate(self.stage.get_status()):
            Label(self, text=str(Axis(idx))).pack(side=LEFT)
            status_label= Label(self, text=status, borderwidth=2, width=15, relief='sunken')
            status_label.pack(side=LEFT, padx=(2,10))
            self._status_labels.append(status_label)

        # Update job
        self._update_status_job = self.after(self.REFRESHING_RATE, self._refresh_status_labels)


    def __del__(self):
        if self._update_status_job:
            self.after_cancel(self._update_status_job)

    #
    #   Stage Status Routine
    #

    def _refresh_status_labels(self):
        """
        Refreshes Stage status.

        Kills update job, if an error occurred.
        """
        try:
            status_tuple = self.stage.get_status()
        except Exception as exc:
            self.after_cancel(self._update_status_job)
            raise RuntimeError(exc)
        
        for idx, status in enumerate(status_tuple):
            self._status_labels[idx].config(text=status)
