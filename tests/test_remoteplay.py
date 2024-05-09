import unittest
from unittest.mock import patch, Mock, MagicMock, call

from PyQt5.QtWidgets import QApplication

from remoteplay.__main__ import MainWindow
from remoteplay.worker import ChangeMachineStatus
import remoteplay.worker

API_KEY = 'MOCK_KEY'


class TestMainWindow(MainWindow):
    mock_name = 'Arcturus'

    def __init__(self):
        super().__init__()

    def load_config(self):
        self.machine_name = self.mock_name
        self.api_key = 'MOCK_KEY'


class SingleThreadStatusChanger(ChangeMachineStatus):
    def __init__(self, machine_id, api_key, action):
        super().__init__(machine_id, api_key, action)

    def start(self, priority=None):
        self.run()


class RemotePlayTest(unittest.TestCase):

    def _mock_restart_machine(self):
        yield "ready"
        yield "restarting"
        yield "restarting"
        yield "ready"

    def _mock_usb_active(self, param):
        if self.usb_active:
            return [Mock(info={"name": 'vhusb'})]
        else:
            return []

    def _mock_request_get(self, path, api_key):
        if path == "":
            return {
                "hasMore": False,
                "items": [{
                    "id": "pskwujgcp",
                    "name": "Arcturus",
                    "state": self.mock_state,
                    "publicIp": "74.82.29.115"
                }]
            }

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
        self.config_write_patcher = patch("remoteplay.__main__.configparser.ConfigParser")
        self.mock_write = self.config_write_patcher.start()
        mock_configparser = Mock()
        mock_configparser.__setitem__ = Mock()
        self.mock_write.return_value = mock_configparser

    def _mock_sshtunnel_popen(self):
        self.popen_patcher = patch("remoteplay.sshtunnel.subprocess.Popen")
        self.mock_popen = self.popen_patcher.start()
        mock_process = Mock()
        mock_process.poll = (lambda: 0)
        self.mock_popen.return_value = mock_process

    def _mock_main_popen(self):
        self.popen_main_patcher = patch("remoteplay.__main__.subprocess.Popen")
        self.mock_main_popen = self.popen_main_patcher.start()
        mock_process = Mock()
        mock_process.stdout = ["hostname: remoteplay.example.com"]
        mock_process.poll = (lambda: 0)
        self.mock_main_popen.return_value = mock_process

    def _mock_usbserver(self):
        self.psutil_patcher = patch("remoteplay.usbserver.psutil.process_iter")
        self.mock_process_iter = self.psutil_patcher.start()
        self.mock_process_iter.side_effect = self._mock_usb_active
        self.mock_usbserver_patcher = patch("remoteplay.usbserver.subprocess.Popen")
        self.mock_usbserver_popen = self.mock_usbserver_patcher.start()

    def setUp(self):
        self.mock_state = (lambda: "off")
        remoteplay.worker.POLLING_DELAY = 1
        self.usb_active = False
        # Mocking the request_get and request_patch methods in the common module
        self.request_get_patch = patch('remoteplay.__main__.request_get', autospec=True)
        self.check_state_patch = patch('remoteplay.__main__.check_state', autospec=True)
        self.check_state_patch2 = patch('remoteplay.worker.check_state', autospec=True)
        self.request_patch_patch = patch('remoteplay.worker.request_patch', autospec=True)
        # Start the patches
        self.mock_request_get = self.request_get_patch.start()
        self.mock_request_patch = self.request_patch_patch.start()
        self.mock_check_state = self.check_state_patch.start()
        self.mock_check_state2 = self.check_state_patch2.start()
        # Set up the return values or side effects for the mocked methods if needed
        self.mock_request_get.side_effect = self._mock_request_get
        self.mock_request_patch.side_effect = self._mock_request_patch
        self.mock_check_state.side_effect = self._mock_check_state
        self.mock_check_state2.side_effect = self._mock_check_state

        self.change_status_patch = patch("remoteplay.__main__.ChangeMachineStatus")
        self.change_status_mock = self.change_status_patch.start()
        self.change_status_mock.side_effect = (
            lambda i, k, a: SingleThreadStatusChanger(i, k, a))

        self.change_status_emit_patch = patch("remoteplay.__main__.ChangeMachineStatus.status.emit")
        self.change_status_emit_mock = self.change_status_emit_patch.start()
        self.change_status_emit_mock.side_effect = (lambda x: self.mock_main_window.update_state(x))
        self.change_finished_emit_patch = patch("remoteplay.__main__.ChangeMachineStatus.finished.emit")
        self.change_finished_emit_mock = self.change_finished_emit_patch.start()
        self.change_finished_emit_mock.side_effect = (lambda x: self.mock_main_window.status_change_complete())

    def tearDown(self):
        self.request_get_patch.stop()
        self.request_patch_patch.stop()
        self.config_write_patcher.stop()
        self.popen_patcher.stop()
        self.popen_main_patcher.stop()
        self.mock_usbserver_patcher.stop()
        self.change_status_patch.stop()
        self.change_finished_emit_patch.stop()
        self.change_status_emit_patch.stop()

    def test_startup(self):
        self._mock_usbserver()
        self._mock_write()
        self._mock_sshtunnel_popen()
        self._mock_main_popen()

        app = QApplication([])
        self.mock_main_window = TestMainWindow()

        self.mock_request_get.assert_called_with("", API_KEY)

        self.mock_main_window.start_stop_machine("start")

        self.mock_request_patch.assert_called_with("pskwujgcp/start", API_KEY)
        self.mock_main_popen.assert_has_calls([
            call('/Applications/VirtualHereServerUniversal.app/Contents/MacOS/vhusbdosx'),
            call(['ssh', '-N', '-R', '7575:localhost:7575', '-o', 'StrictHostKeyChecking=no', 'Arcturus'])])
        self.assertEqual(self.mock_main_window.machine_state_bar.text(), 'ready')
        self.assertEqual(self.mock_main_window.button.text(), 'Stop remote')
        app.quit()

    if __name__ == '__main__':
        unittest.main()
