

from unittest import TestCase
import tkinter
from tkinter import Tk

from LabExT.ExperimentManager import ExperimentManager
from LabExT.View.StageCalibration.StageCalibrationController import StageCalibrationController

class StageCalibrationControllerTest(TestCase):
    def setUp(self) -> None:
        self.root = Tk()
        self.experiment_manager = ExperimentManager(self.root, '')
        self.mover = self.experiment_manager.mover_new

        self.mover.connect()
        self.controller = StageCalibrationController(self.root, self.experiment_manager)

    
    def teardown(self):
        if self.root:
            self.root.destroy()
            self.pump_events()

    def pump_events(self):
        while self.root.dooneevent(tkinter.ALL_EVENTS | tkinter.DONT_WAIT):
            pass

    def test_foo(self):
        self.controller.new()
        breakpoint()