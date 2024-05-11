from PyQt5.QtCore import QThread, pyqtSignal
from time import sleep
from .common import check_state, request_patch

POLLING_DELAY = 5

class ChangeMachineStatus(QThread):
    finished = pyqtSignal()
    status = pyqtSignal(str)

    def __init__(self, machine_id, api_key, action):
        super().__init__()
        self.machine_id = machine_id
        self.api_key = api_key
        self.action = "start"
        self.target_state = "ready"
        self.action = action
        if action == "start":
            self.target_state = "ready"
        else:
            self.target_state = "off"

    def check_state(self):
        return check_state(self.machine_id, self.api_key)

    def wait_for_state(self, target_state, status_callback):
        state = self.check_state()
        while state != target_state:
            sleep(POLLING_DELAY)
            state = self.check_state()
            status_callback(state)

    def run(self):
        def callback(state):
            self.status.emit(state)

        if self.check_state() != self.target_state:
            request_patch(f"{self.machine_id}/{self.action}", self.api_key)
            self.wait_for_state(self.target_state, callback)
        self.status.emit(self.target_state)
        self.finished.emit()
