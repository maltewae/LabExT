from unittest import TestCase

from LabExT.Movement.MoverNew import MoverNew
from LabExT.Movement.Stages.DummyStage import DummyStage
from LabExT.Movement.Calibration import Calibration, Axis

class CalibrationTest(TestCase):

    def setUp(self) -> None:
        self.mover = MoverNew(None)
        self.stage = DummyStage('1234')
        self.calibration = Calibration(self.mover, self.stage)

    def test_foo(self):
        self.calibration.x_axis = Axis.Z
        self.calibration.y_axis = Axis.X
        self.calibration.z_axis = Axis.Y

        self.calibration.z_axis_direction = -1

        matrix = self.calibration.axes_mapping_matrix

        