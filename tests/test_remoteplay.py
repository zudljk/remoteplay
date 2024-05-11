import unittest
from unittest.mock import patch, Mock, MagicMock, call
import faulthandler
import platform

from PyQt5.QtWidgets import QApplication

from remoteplay.__main__ import MainWindow
from remoteplay.worker import ChangeMachineStatus
import remoteplay.worker

API_KEY = 'MOCK_KEY'
app = None

class TestMainWindow(MainWindow):
    mock_name = 'Arcturus'
    mock_api_key = 'MOCK_KEY'

    def __init__(self):
        super().__init__()

    def load_config(self):
        self.machine_name = self.mock_name
        self.api_key = self.mock_api_key


class SingleThreadStatusChanger(ChangeMachineStatus):
    def __init__(self, machine_id, api_key, action):
        super().__init__(machine_id, api_key, action)

    def start(self, priority=None):
        self.run()


class RemotePlayTest(unittest.TestCase):

    def _mock_usb_active(self, param):
        if self.usb_active:
            return [Mock(info={"name": 'vhusb'})]
        else:
            return []

    def _mock_request_get(self, path, api_key):
        if path == "":
            return self.sample_api_response()

    def _mock_request_patch(self, path, api_key):
        if "start" in path:
            startup_states = iter(["off", "off", "starting", "starting", "starting", "starting"])
            self.mock_state = (lambda: next(startup_states, "ready"))
        elif "stop" in path:
            shutdown_states = iter(["ready", "ready", "stopping", "stopping", "stopping", "stopping"])
            self.mock_state = (lambda: next(shutdown_states, "off"))

    def _mock_check_state(self, machine_id, api_key):
        return self.mock_state()

    def _mock_write(self):
        print("Mocking configparser to simulate writing config")
        self.config_write_patcher = patch("remoteplay.__main__.configparser.ConfigParser")
        self.mock_write = self.config_write_patcher.start()
        mock_configparser = Mock()
        mock_configparser.__setitem__ = Mock()
        self.mock_write.return_value = mock_configparser

    def _mock_main_popen(self):
        print("Mocking subprocess to simulate start of external commands")
        self.popen_main_patcher = patch("remoteplay.__main__.subprocess.Popen")
        self.mock_main_popen = self.popen_main_patcher.start()
        mock_process = Mock()
        mock_process.stdout = ["hostname: remoteplay.example.com"]
        mock_process.poll = (lambda: 0)
        self.mock_main_popen.return_value = mock_process

    def _mock_usbserver(self):
        print("Mocking psutil to simulate presence of USB server")
        self.psutil_patcher = patch("remoteplay.usbserver.psutil.process_iter")
        self.mock_process_iter = self.psutil_patcher.start()
        self.mock_process_iter.side_effect = self._mock_usb_active
        self.mock_usbserver_patcher = patch("remoteplay.usbserver.subprocess.Popen")
        self.mock_usbserver_popen = self.mock_usbserver_patcher.start()

    def _mock_common(self):
        print("Mocking the request_get and request_patch methods in the common module")
        self.request_get_patch = patch('remoteplay.__main__.request_get', autospec=True)
        self.mock_request_get = self.request_get_patch.start()
        self.mock_request_get.side_effect = self._mock_request_get
        self.request_patch_patch = patch('remoteplay.worker.request_patch', autospec=True)
        self.mock_request_patch = self.request_patch_patch.start()
        self.mock_request_patch.side_effect = self._mock_request_patch
        self.check_state_patch = patch('remoteplay.__main__.check_state', autospec=True)
        self.mock_check_state = self.check_state_patch.start()
        self.mock_check_state.side_effect = self._mock_check_state
        self.check_state_patch2 = patch('remoteplay.worker.check_state', autospec=True)
        self.mock_check_state2 = self.check_state_patch2.start()
        self.mock_check_state2.side_effect = self._mock_check_state

    def _mock_platform(self):
        self.platform_patch = patch("remoteplay.usbserver.system")
        self.mock_platform = self.platform_patch.start()
        self.mock_platform.return_value = 'Darwin'

    def _mock_status_change(self):
        print("Mocking the machine status change")
        self.change_status_patch = patch("remoteplay.__main__.ChangeMachineStatus")
        self.change_status_mock = self.change_status_patch.start()
        self.change_status_mock.side_effect = (
            lambda i, k, a: SingleThreadStatusChanger(i, k, a))

        print("Mocking the machine status change signals")
        self.change_status_emit_patch = patch("remoteplay.__main__.ChangeMachineStatus.status.emit")
        self.change_status_emit_mock = self.change_status_emit_patch.start()
        self.change_status_emit_mock.side_effect = (lambda x: self.mock_main_window.update_state(x))
        print("Mocking the machine finish signal")
        self.change_finished_emit_patch = patch("remoteplay.__main__.ChangeMachineStatus.finished.emit")
        self.change_finished_emit_mock = self.change_finished_emit_patch.start()
        self.change_finished_emit_mock.side_effect = (lambda x: self.mock_main_window.status_change_complete())

    @classmethod
    def setUpClass(cls):
        global app
        print("Creating the test application")
        app = QApplication([])

    @classmethod
    def tearDownClass(cls):
        global app
        app.quit()

    def setUp(self):
        print("Creating test setup ...")
        self.mock_state = (lambda: "off")
        TestMainWindow.mock_name = 'Arcturus'
        TestMainWindow.mock_api_key = 'MOCK_KEY'

        remoteplay.worker.POLLING_DELAY = 1
        self.usb_active = False
        self.sample_api_response = (lambda: {
            "hasMore": False,
            "items": [{
                "id": "pskwujgcp",
                "name": "Arcturus",
                "state": self.mock_state,
                "publicIp": "74.82.29.115"
            }]
        })

        self._mock_platform()
        self._mock_usbserver()
        self._mock_write()
        self._mock_main_popen()
        self._mock_status_change()
        self._mock_common()

        self.dumpfile = open("../test_remoteplay.dump", "a")
        faulthandler.enable(file=self.dumpfile)

    def tearDown(self):
        print("Cleaning up")
        self.config_write_patcher.stop()
        self.popen_main_patcher.stop()
        self.psutil_patcher.stop()
        self.mock_usbserver_patcher.stop()
        self.request_get_patch.stop()
        self.request_patch_patch.stop()
        self.check_state_patch.stop()
        self.check_state_patch2.stop()
        self.change_status_patch.stop()
        self.change_status_emit_patch.stop()
        self.change_finished_emit_patch.stop()
        self.platform_patch.stop()

    def test_startup(self):
        print("Creating the main window")
        self.mock_main_window = TestMainWindow()

        print("Checking if get_machines was called")
        self.mock_request_get.assert_called_with("", API_KEY)
        self.assertEqual(self.mock_main_window.button.text(), 'Start remote')

        self.mock_main_window.start_stop_machine("start")

        self.mock_request_patch.assert_called_with("pskwujgcp/start", API_KEY)
        if platform.system() == 'Darwin':
            self.mock_main_popen.assert_has_calls([
                call('/Applications/VirtualHereServerUniversal.app/Contents/MacOS/vhusbdosx'),
                call(['ssh', '-N', '-R', '7575:localhost:7575', '-o', 'StrictHostKeyChecking=no', 'Arcturus'])])
        elif platform.system() == 'Windows':
            self.mock_main_popen.assert_has_calls([
                call('/Applications\\VirtualHereServerUniversal.app\\Contents\\MacOS\\vhusbdosx'),
                call(['ssh', '-N', '-R', '7575:localhost:7575', '-o', 'StrictHostKeyChecking=no', 'Arcturus'])])
        self.assertEqual(self.mock_main_window.machine_state_bar.text(), 'ready')
        self.assertEqual(self.mock_main_window.button.text(), 'Stop remote')

    def test_shutdown(self):
        self.mock_state = (lambda: "ready")

        self.mock_main_window = TestMainWindow()

        self.mock_request_get.assert_called_with("", API_KEY)
        self.assertEqual(self.mock_main_window.button.text(), 'Stop remote')

        self.mock_main_popen.assert_called_with(
            ['ssh', '-N', '-R', '7575:localhost:7575', '-o', 'StrictHostKeyChecking=no', 'Arcturus'])

        self.mock_main_window.start_stop_machine("stop")

        self.mock_request_patch.assert_called_with("pskwujgcp/stop", API_KEY)
        self.mock_main_popen.assert_has_calls([
            # called to find the host name
            call(['ssh', '-G', 'Arcturus'], stdout=-1, stderr=-1, text=True),
            call(['ssh', '-N', '-R', '7575:localhost:7575', '-o', 'StrictHostKeyChecking=no', 'Arcturus']),
            call().terminate()
        ])

        self.assertEqual(self.mock_main_window.machine_state_bar.text(), 'off')
        self.assertEqual(self.mock_main_window.button.text(), 'Start remote')

    def test_external_shutdown(self):
        self.mock_state = (lambda: "ready")

        self.mock_main_window = TestMainWindow()

        shutdown_states = ["ready", "ready", "stopping", "stopping", "stopping"]
        shutdown_states_iter = iter(shutdown_states)
        self.mock_state = (lambda: next(shutdown_states_iter, "off"))

        for state in shutdown_states:
            self.mock_main_window.handle_timer()
            self.assertEqual(self.mock_main_window.machine_state, state)
        self.mock_main_window.handle_timer()

        self.mock_main_popen.assert_has_calls([
            # called to find the host name
            call(['ssh', '-G', 'Arcturus'], stdout=-1, stderr=-1, text=True),
            call(['ssh', '-N', '-R', '7575:localhost:7575', '-o', 'StrictHostKeyChecking=no', 'Arcturus']),
            call().terminate()
        ])

        self.assertEqual(self.mock_main_window.machine_state_bar.text(), 'off')
        self.assertEqual(self.mock_main_window.button.text(), 'Start remote')

    def test_external_startup(self):

        self.mock_main_window = TestMainWindow()

        self.assertEqual(self.mock_main_window.machine_state_bar.text(), 'off')
        self.assertEqual(self.mock_main_window.button.text(), 'Start remote')

        startup_states = ["ready", "ready", "stopping", "stopping", "stopping"]
        startup_states_iter = iter(startup_states)
        self.mock_state = (lambda: next(startup_states_iter, "ready"))

        for state in startup_states:
            self.mock_main_window.handle_timer()
            self.assertEqual(self.mock_main_window.machine_state, state)
        self.mock_main_window.handle_timer()

        self.mock_main_popen.assert_has_calls([
            # called to find the host name
            call(['ssh', '-G', 'Arcturus'], stdout=-1, stderr=-1, text=True),
            call(['ssh', '-N', '-R', '7575:localhost:7575', '-o', 'StrictHostKeyChecking=no', 'Arcturus'])
        ])

        self.assertEqual(self.mock_main_window.machine_state_bar.text(), 'ready')
        self.assertEqual(self.mock_main_window.button.text(), 'Stop remote')

    def test_change_api_key(self):
        TestMainWindow.mock_api_key = None
        TestMainWindow.mock_name = None

        self.mock_main_window = TestMainWindow()

        self.mock_main_window.paperspace_key_text.setText("MOCK_KEY")

        self.mock_main_window.init_paperspace_values()

        self.mock_request_get.assert_called_with("", "MOCK_KEY")
        self.assertEqual(self.mock_main_window.machine_name_text.currentText(), 'Arcturus')
        self.assertEqual(self.mock_main_window.machine_state_bar.text(), 'off')
        self.assertEqual(self.mock_main_window.button.text(), 'Start remote')

    def test_change_name(self):
        self.sample_api_response = (lambda: {
            "hasMore": False,
            "items": [{
                "id": "pskwujgcp",
                "name": "Arcturus",
                "state": "off",
                "publicIp": "74.82.29.115"
            }, {
                "id": "skwujgcpp",
                "name": "OtherServer",
                "state": "off",
                "publicIp": "74.82.29.116"
            }]
        })

        self.mock_main_window = TestMainWindow()

        self.mock_main_window.init_paperspace_values()

        self.mock_request_get.assert_called_with("", "MOCK_KEY")

        self.mock_main_window.machine_name_text.setCurrentText("OtherServer")

        self.mock_main_window.init_paperspace_values()

        self.assertEqual(self.mock_main_window.machine_id, "skwujgcpp")
        self.assertEqual(self.mock_main_window.public_ip, "74.82.29.116")

        self.assertEqual(self.mock_main_window.machine_name_text.currentText(), 'OtherServer')
        self.assertEqual(self.mock_main_window.machine_state_bar.text(), 'off')
        self.assertEqual(self.mock_main_window.button.text(), 'Start remote')

    if __name__ == '__main__':
        unittest.main()
