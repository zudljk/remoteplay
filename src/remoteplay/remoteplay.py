import subprocess
import sys
from json import loads
from sys import argv
from time import sleep
from re import compile

import psutil
import requests
from PyQt5.QtCore import pyqtSignal, QObject, QThread, QTimer
from PyQt5.QtWidgets import QMainWindow, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QApplication, \
    QWidget, QGridLayout

PAPERSPACE_API = "https://api.paperspace.com/v1"
MACHINE_NAME = argv[1]
API_KEY = argv[2]
SSH_PROCESS = None


# Function to retrieve the public IP of the Paperspace machine
def get_machine(machine):
    m = next((x for x in request_get("")["items"] if x["id"] == machine or x["name"] == machine))
    return m["id"], m["publicIp"]


def request_get(path):
    response = requests.get(f"{PAPERSPACE_API}/machines/{path}", headers={
        "accept": "application/json",
        "authorization": f"Bearer {API_KEY}"
    })
    return loads(response.text)


def request_patch(path):
    response = requests.patch(f"{PAPERSPACE_API}/machines/{path}", headers={
        "accept": "application/json",
        "authorization": f"Bearer {API_KEY}"
    })
    return loads(response.text)


def change_machine_status(machine_id, command, target_state, status_callback):
    state = check_state(machine_id)
    if state != target_state:
        request_patch(f"{machine_id}/{command}")
        wait_for_state(machine_id, target_state, status_callback)


def wait_for_state(machine_id, target_state, status_callback):
    state = check_state(machine_id)
    while state != target_state:
        sleep(5)
        state = check_state(machine_id)
        status_callback(state)


# Function to stop the Paperspace machine
def stop_machine(machine_id, status_callback):
    tunnel("close", status_callback)
    status_callback("shutdown requested")
    change_machine_status(machine_id, "stop", "off", status_callback)


def tunnel(action, hostname):
    global SSH_PROCESS
    if not hostname:
        return "closed"
    if action == "open":
        SSH_PROCESS = subprocess.Popen(
            ["ssh", "-N", "-R", "7575:localhost:7575", "-o", "StrictHostKeyChecking=no", hostname])
    elif action == "close":
        SSH_PROCESS.terminate()
    elif action == "check":
        if not SSH_PROCESS:
            return "closed"
        returncode = SSH_PROCESS.poll()
        if returncode:
            return "closed"
        else:
            return "open"


def start_usbserver(status_callback):
    if check_process("vhusb") != "active":
        subprocess.Popen("/Applications/VirtualHereServerUniversal.app/Contents/MacOS/vhusbdosx")


def determine_host_name(*args):
    # try to find a "Host" entry in ~/.ssh/config to determine the host name
    for id in args:
        process = subprocess.Popen(["ssh", "-G", id], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        for line in process.stdout:
            l = line.strip()
            if l.lower().startswith('hostname'):
                return l.split()[1]
    # if not found, return the first argument that looks like an IPv4 or IPv6 address
    ip = compile("([0-2][0-9][0-9]\\.?){4}|[0-9:]+")
    for id in args:
        if ip.match(id):
            return id
    # if none found, return none
    return None


def check_process(process_name):
    for proc in psutil.process_iter(['name']):
        if proc.info['name'] == process_name:
            return "active"
    return "inactive"


# Function to check the state of the Paperspace machine
def check_state(machine_id):
    return request_get(machine_id)["state"] if machine_id else "unknown"


class ChangeMachineStatus(QObject):
    finished = pyqtSignal()
    status = pyqtSignal(str)

    def __init__(self, machine_id):
        super().__init__()
        self.machine_id = machine_id
        self.action = "start"
        self.target_state = "ready"

    def stop(self):
        self.action = "stop"
        self.target_state = "off"

    def run(self):
        def callback(state):
            self.status.emit(state)

        change_machine_status(self.machine_id, self.action, self.target_state, callback)
        self.finished.emit()


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.machine_name = MACHINE_NAME
        self.machine_id, self.public_ip = get_machine(self.machine_name)
        self.hostname = determine_host_name(self.machine_name, self.machine_id, self.public_ip)
        self.machine_state = check_state(self.machine_id)
        self.current_state = {
            "Machine ID": (lambda: self.machine_id),
            "Machine Name": (lambda: self.machine_name),
            "Hostname": (lambda: self.hostname),
            "Public IP": (lambda: self.public_ip),
            "USB Server": (lambda: check_process("vhusb")),
            "Machine state": (lambda: self.machine_state),
            "SSH Tunnel": (lambda: tunnel("check", self.hostname))
        }

        self.setWindowTitle('Remote machine')
        self.setGeometry(100, 100, 300, 400)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        self.layout = QVBoxLayout()
        self.central_widget.setLayout(self.layout)

        self.grid_layout = QGridLayout()
        self.layout.addLayout(self.grid_layout)

        self.text_fields = {}

        row = 0
        for key, value in self.current_state.items():
            label = QLabel(key)
            self.grid_layout.addWidget(label, row, 0)
            text_field = QLineEdit()
            text_field.setReadOnly(True)
            self.grid_layout.addWidget(text_field, row, 1)
            self.text_fields[key] = text_field
            row += 1

        self.button = QPushButton("Start remote")
        self.layout.addWidget(self.button)
        self.set_up_button()
        self.start_updating()

    def set_up_button(self):
        if self.machine_state == "ready":
            self.button.setText("Stop remote")
            self.button.clicked.connect((lambda: self.start_stop_machine("stop")))
            self.button.setEnabled(True)
        elif self.machine_state == "off":
            self.button.setText("Start remote")
            self.button.clicked.connect((lambda: self.start_stop_machine("start")))
            self.button.setEnabled(True)
        else:
            self.button.setText("Please wait")
            self.button.setEnabled(False)

    def start_stop_machine(self, action):
        self.stop_updating()
        self.button.setEnabled(False)
        self.thread = QThread()
        self.worker = ChangeMachineStatus(self.machine_id)
        if action == "stop":
            self.worker.stop()
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.thread.finished.connect(self.thread.deleteLater)

        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.status_change_complete)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.status.connect(self.update_state)
        self.thread.start()

    def status_change_complete(self):
        self.current_state["Machine state"] = (lambda: check_state(self.machine_id))
        self.set_up_button()
        self.start_updating()

    def update_state(self, state):
        self.machine_state = state
        self.update_data()

    def start_updating(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_data)
        self.timer.start(5000)  # Update every 5 seconds
        self.update_data()

    def update_data(self):
        for label in self.current_state:
            getter = self.current_state.get(label, "unknown")
            if getter:
                value = getter()
                field = self.text_fields[label]
                field.setText(value)
                if value in ["ready", "open", "active"]:
                    field.setStyleSheet("color: green;")
                elif value in ["starting", "stopping"]:
                    field.setStyleSheet("color: yellow;")
                else:
                    field.setStyleSheet("color: lightgray;")

    def stop_updating(self):
        self.timer.stop()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    mainWindow = MainWindow()
    mainWindow.show()
    sys.exit(app.exec_())
