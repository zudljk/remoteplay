import sys
import requests
from json import loads
from time import sleep
from PyQt5.QtCore import pyqtSignal, QObject, QThread, QTimer, QRect, Qt
from PyQt5.QtWidgets import QMainWindow, QVBoxLayout, QLabel, QLineEdit, QPushButton, QApplication, QWidget, \
    QGridLayout, QGroupBox, QComboBox, QMessageBox, QMessageBox


PAPERSPACE_API = "https://api.paperspace.com/v1"
API_KEY = "6877b8e3692ea32bb20eb07cc3767a"


def check_state(machine_id, api_key):
    return request_get(machine_id, api_key)["state"] if machine_id else "unknown"


def request_get(path, api_key):
    response = requests.get(f"{PAPERSPACE_API}/machines/{path}", headers={
        "accept": "application/json",
        "authorization": f"Bearer {api_key}"
    })
    return loads(response.text)


def request_patch(path, api_key):
    response = requests.patch(f"{PAPERSPACE_API}/machines/{path}", headers={
        "accept": "application/json",
        "authorization": f"Bearer {api_key}"
    })
    return loads(response.text)


class ChangeMachineStatus(QObject):

    finished = pyqtSignal()
    status = pyqtSignal(str)

    def __init__(self, machine_id, api_key):
        super().__init__()
        self.machine_id = machine_id
        self.api_key = api_key
        self.action = "start"
        self.target_state = "ready"

    def stop(self):
        self.action = "stop"
        self.target_state = "off"

    def check_state(self):
        check_state(self.machine_id, self.api_key)

    def wait_for_state(self, target_state, status_callback):
        state = self.check_state()
        while state != target_state:
            sleep(5)
            state = self.check_state()
            status_callback(state)

    def run(self):
        def callback(state):
            self.status.emit(state)
        if self.check_state() != self.target_state:
            request_patch(f"{self.machine_id}/{self.action}", self.api_key)
            self.wait_for_state(self.target_state, callback)
        self.finished.emit()


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.machine_name = None
        self.machine_id = None
        self.public_ip = None
        self.connect_by = "machine_name"
        self.hostname = None
        self.machine_state = None
        #self.load_config()
        self.current_state = {
            "machine_id": (lambda: self.machine_id),
            "machine_name": (lambda: self.machine_name),
            "hostname": (lambda: self.hostname),
            "public_ip": (lambda: self.public_ip),
        #    "usb_server": (lambda: check_process("vhusb")),
            "machine_state": (lambda: self.machine_state),
        #    "ssh_tunnel": (lambda: tunnel("check", self.current_state[self.connect_by]()))
        }
        self.central_widget = QWidget()
        self.start_thread_button = QPushButton(self.central_widget)
        self.start_thread_button.clicked.connect(self.start_stop_machine)
        self.setCentralWidget(self.central_widget)
        self.start_thread_button.setText("Start Thread")

    def start_stop_machine(self):
        self.start_thread_button.setEnabled(False)
        self.thread = QThread()
        self.worker = ChangeMachineStatus("pskwujgcp", "6877b8e3692ea32bb20eb07cc3767a")
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.thread.finished.connect(self.thread.deleteLater)

        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.status_change_complete)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.start()

    def status_change_complete(self):
        state = self.current_state["machine_state"]()
        self.current_state["machine_state"] = (lambda: check_state(self.machine_id))
        #self.set_up_button()
        #self.start_updating()


def main():
    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
