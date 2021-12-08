#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LabExT  Copyright (C) 2022  ETH Zurich and Polariton Technologies AG
This program is free software and comes with ABSOLUTELY NO WARRANTY; for details see LICENSE file.
"""

from textwrap import fill
from tkinter import BOTH, VERTICAL, Button, Frame, Checkbutton, BooleanVar, Toplevel, messagebox, ttk
from tkinter.constants import LEFT, RIGHT, TOP, X
from typing import List, Type

from LabExT.View.Controls.CustomTable import CustomTable
from LabExT.View.Controls.CustomFrame import CustomFrame
from LabExT.View.Movement.CoordinatePairingWindow import CoordinatePairingWindow

from LabExT.Movement.MoverNew import MoverNew
from LabExT.Movement.Calibration import Calibration

class KabschRotationWindow(Toplevel):

    def __init__(self, parent, mover, calibration):
        self.mover: Type[MoverNew] = mover
        self.calibration: Type[Calibration] = calibration
        self.parent = parent

        # TODO: Check connedted
        # if not self.mover.experiment_manager.chip:
        #     raise RuntimeError("You must import a chip, before doing a single point fixation. ")

        super(KabschRotationWindow, self).__init__(self.parent)
        self.title("Make Full Transformation")
        self.wm_geometry("{width:d}x{height:d}".format(width=600, height=400))
        self.protocol('WM_DELETE_WINDOW', self.destroy)

        # Wizard State
        self._pairings: list = []
        self.make_2D_transformation = False

        # supplementary frames
        self._pairings_table = None
        self._2d_transformation_variable = BooleanVar(parent.parent, False)

        self.__setup__()


    @property
    def pairings(self):
        return self._pairings


    @property
    def is_2d_transformation(self):
        return self._2d_transformation_variable.get()


    def __setup__(self):
        self.main_frame = Frame(self)
        self.main_frame.pack(side=TOP, expand=True, fill=BOTH)

        self._pairing_overview_frame()
        self._transformation_type_frame()

        Button(
            self,
            text="Make Transformation",
            command=self._on_finish,
            width=15
        ).pack(side=TOP, anchor='e', pady=2, padx=5)

    def _transformation_type_frame(self):
        transformation_type_frame = Frame(self.main_frame)
        transformation_type_frame.pack(side=TOP, fill=X, padx=5)

        ttk.Separator(
            transformation_type_frame,
            orient=VERTICAL
        ).pack(side=TOP, fill=X, pady=10)

        transformation_2D_checkbutton = Checkbutton(
            transformation_type_frame,
            text="Make 2D Transformation",
            variable=self._2d_transformation_variable
        )
        transformation_2D_checkbutton.pack(side=TOP, anchor='w')

        ttk.Separator(
            transformation_type_frame,
            orient=VERTICAL
        ).pack(side=TOP, fill=X, pady=10)


    def _pairing_overview_frame(self):
        pairing_overview_frame = Frame(self.main_frame)
        pairing_overview_frame.pack(side=TOP, fill=X, pady=2, padx=5)

        current_pairings_frame = CustomFrame(pairing_overview_frame)
        current_pairings_frame.title = "Current Pairings"
        current_pairings_frame.pack(side=TOP, fill=X, pady=2)

        self._pairings_table = CustomTable(
            parent=current_pairings_frame,
            selectmode='browse',
            columns=('#', 'Stage', 'Stage Coordinate', 'Device', 'Chip Coordinate'),
            rows=[(idx, p.calibration.short_str(), p.stage_coordinate, "ID: {}".format(p.device._id), p.chip_coordinate) for idx, p in enumerate(self.pairings)])

        Button(
            pairing_overview_frame,
            text="Remove marked pairings",
            command=self._on_delete_marked_pairings
        ).pack(side=LEFT)

        Button(
            pairing_overview_frame,
            text="New Pairing",
            command=self._on_new_pairing,
            width=15
        ).pack(side=LEFT)

    def __reload__(self):
        for child in self.winfo_children():
            child.forget()

        self.__setup__()
        self.update_idletasks()


    def _on_finish(self):
        if not self.is_2d_transformation and len(self.pairings) < 3:
            messagebox.showerror("Not enough pairings", "Please create at least 3 pairings to perform a 3D transformation.")
            return

        if self.is_2d_transformation and len(self.pairings) < 2:
            messagebox.showerror("Not enough pairings", "Please create at least 2 pairings to perform a 2D transformation.")
            return

        self.destroy()


    def _on_new_pairing(self):
        pairing_window = CoordinatePairingWindow(self, self.mover, self.calibration)
        pairing_window.grab_set()
        self.parent.wait_window(pairing_window)
        pairing_window.grab_release()

        pairing = pairing_window.pairing
        if not pairing:
            return

        if any(p.device == pairing.device for p in self.pairings):
            messagebox.showerror("Double Selection", "You already defined this pairing.")
            return
       
        self._pairings.append(pairing)
        self.__reload__()


    def _on_delete_marked_pairings(self):
        selected_iid = self._pairings_table.get_tree().focus()
        if not selected_iid:
            return
        selected_idx = int(self._pairings_table.get_tree().set(selected_iid, 0))

        try:
            del self._pairings[selected_idx]
            self.__reload__()
        except IndexError:
            pass
