from ..environment import Environment
from ..environment.VRMLLoader import VRMLLoader
from ..settings import Arguments
from core_thread_manager import ThreadableTestCase
from geometry import LocationTestCase
from settings import SettingsTestCase

class TestVRMLLoader(ThreadableTestCase, LocationTestCase, SettingsTestCase):
    def setUp(self):
        super(TestVRMLLoader, self).setUp()
        self.arguments = Arguments("settings.json", [
            "--vehicle-class", "Mock_Vehicle", "--no-infrared-sensor"
        ])
        self.environment = Environment.setup(self.arguments, simulated=True)

    def test_load(self):
        filename = "tests/vrml/castle.wrl"
        with self.assertRaises(ValueError):
            loader = VRMLLoader(self.environment, filename, translation=[1,2])

        loader = VRMLLoader(self.environment, filename, translation=[40.0, 3.14, 5.67])
        self.assertEqual(loader.filename, filename)
        self.assertEqual(loader.translation, (40.0, 3.14, 5.67))
        self.assertEqual(len(loader.get_objects()), 14)
