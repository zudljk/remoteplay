import subprocess
import os
import configparser
import sys
from json import loads
from time import sleep
from re import compile
from platform import system

import psutil
import requests
from PyQt5.QtCore import pyqtSignal, QObject, QThread, QTimer, QRect, Qt
from PyQt5.QtWidgets import QMainWindow, QVBoxLayout, QLabel, QLineEdit, QPushButton, QApplication, QWidget, \
    QGridLayout, QGroupBox, QComboBox, QMessageBox, QMessageBox

BACKGROUND_GRAY = "background-color: darkgray;"
BACKGROUND_GREEN = "background-color: green;"

PAPERSPACE_API = "https://api.paperspace.com/v1"
API_KEY = None
SSH_PROCESS = None
MACHINES = None
VHUSB_PATH = None

VERSION = '0.2.5'

# Function to retrieve the public IP of the Paperspace machine
def get_machine(machine):
    try:
        m = next((x for x in MACHINES if x["id"] == machine or x["name"] == machine))
        return m["id"], m["publicIp"]
    except StopIteration:
        return None, None


def get_machines():
    global MACHINES
    if MACHINES is None:
        MACHINES = request_get("")["items"]


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
    tunnel("close")
    status_callback("shutdown requested")
    change_machine_status(machine_id, "stop", "off", status_callback)


def tunnel(action, host_id=None):
    global SSH_PROCESS
    if action == "open" and host_id and not isinstance(SSH_PROCESS, subprocess.Popen):
        SSH_PROCESS = subprocess.Popen(
            ["ssh", "-N", "-R", "7575:localhost:7575", "-o", "StrictHostKeyChecking=no", host_id])
    elif action == "close" and isinstance(SSH_PROCESS, subprocess.Popen):
        SSH_PROCESS.terminate()
    elif action == "check":
        if not SSH_PROCESS:
            return "closed"
        returncode = SSH_PROCESS.poll()
        if returncode is None:
            return "open"
        elif returncode > 0:
            return "error"
        else:
            return "closed"


def start_usbserver():
    if check_process("vhusb") != "active":
        path = VHUSB_PATH
        if path is None:
            if system() == 'Darwin':
                subprocess.Popen(os.path.join("/", "Applications", "VirtualHereServerUniversal.app", "Contents", "MacOS", "vhusbdosx"))
            elif system() == 'Windows':
                import ctypes
                #ctypes.windll.shell32.ShellExecuteW(None, "runas", 
                #                                    os.path.join("C:\\", "Program Files", "VirtualHere", "vhusbdwin64.exe"),
                #                                    "",
                #                                    None, 1)             
            else:
                subprocess.Popen('vhuit64')
        else:
            subprocess.Popen(path)


def determine_host_name(**args):
    # try to find a "Host" entry in ~/.ssh/config to determine the host name
    for type, id in args.items():
        process = subprocess.Popen(["ssh", "-G", id], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        for line in process.stdout:
            l = line.strip()
            if l.lower().startswith('hostname'):
                return type, l.split()[1]
    # if not found, return the first argument that looks like an IPv4 or IPv6 address
    ip = compile("([0-2][0-9][0-9]\\.?){4}|[0-9:]+")
    for id in args.values():
        if ip.match(id):
            return id
    # if none found, return none
    return None


def check_process(process_name):
    for proc in psutil.process_iter(['name']):
        if process_name in proc.info['name']:
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
        self.machine_name = None
        self.machine_id = None
        self.public_ip = None
        self.connect_by = "machine_name"
        self.hostname = None
        self.machine_state = None
        self.load_config()
        self.current_state = {
            "machine_id": (lambda: self.machine_id),
            "machine_name": (lambda: self.machine_name),
            "hostname": (lambda: self.hostname),
            "public_ip": (lambda: self.public_ip),
            "usb_server": (lambda: check_process("vhusb")),
            "machine_state": (lambda: self.machine_state),
            "ssh_tunnel": (lambda: tunnel("check", self.current_state[self.connect_by]()))
        }

        self.resize(420, 600)
        self.centralwidget = QWidget()
        self.verticalLayoutWidget = QWidget(self.centralwidget)
        self.verticalLayoutWidget.setGeometry(QRect(10, 10, 400, 550))

        self.all_layout = QVBoxLayout(self.verticalLayoutWidget)
        self.all_layout.setContentsMargins(0, 0, 0, 0)

        # ------- Box for API key and machine name -----
        self.top = QGroupBox(self.verticalLayoutWidget)
        self.top_layout_widget = QWidget(self.top)
        self.top_grid_layout = QGridLayout(self.top_layout_widget)
        self.top_grid_layout.setContentsMargins(0, 0, 0, 0)
        self.paperspace_key_label = QLabel(self.top_layout_widget)
        self.top_grid_layout.addWidget(self.paperspace_key_label, 0, 0, 1, 1)
        self.paperspace_key_text = QLineEdit(self.top_layout_widget)
        self.paperspace_key_text.setText(API_KEY)
        self.paperspace_key_text.editingFinished.connect(self.init_paperspace_values)
        self.top_grid_layout.addWidget(self.paperspace_key_text, 0, 2, 1, 1)
        self.machine_name_label = QLabel(self.top_layout_widget)
        self.top_grid_layout.addWidget(self.machine_name_label, 2, 0, 1, 1)
        self.machine_name_text = QComboBox(self.top_layout_widget)
        self.machine_name_text.setEditable(False)
        self.machine_name_text.setCurrentText(self.machine_name)
        self.machine_name_text.currentIndexChanged.connect(self.init_paperspace_values)
        self.top_grid_layout.addWidget(self.machine_name_text, 2, 2, 1, 1)
        self.top_grid_layout.setColumnMinimumWidth(0, 100)
        self.top_layout_widget.setGeometry(QRect(20, 40, 360, 120))
        self.top.setFixedHeight(160)

        self.upper = QGroupBox(self.verticalLayoutWidget)
        self.gridLayoutWidget = QWidget(self.upper)
        self.upper_grid_layout = QGridLayout(self.gridLayoutWidget)
        self.upper_grid_layout.setContentsMargins(0, 0, 0, 0)
        self.machine_id_label = QLabel(self.gridLayoutWidget)
        self.upper_grid_layout.addWidget(self.machine_id_label, 0, 0, 1, 1)
        self.machine_id_text = QLineEdit(self.gridLayoutWidget)
        self.machine_id_text.setReadOnly(True)
        self.upper_grid_layout.addWidget(self.machine_id_text, 0, 2, 1, 1)
        self.host_name_label = QLabel(self.gridLayoutWidget)
        self.upper_grid_layout.addWidget(self.host_name_label, 2, 0, 1, 1)
        self.host_name_text = QLineEdit(self.gridLayoutWidget)
        self.host_name_text.setReadOnly(True)
        self.upper_grid_layout.addWidget(self.host_name_text, 2, 2, 1, 1)
        self.public_ip_label = QLabel(self.gridLayoutWidget)
        self.upper_grid_layout.addWidget(self.public_ip_label, 3, 0, 1, 1)
        self.public_ip_text = QLineEdit(self.gridLayoutWidget)
        self.public_ip_text.setReadOnly(True)
        self.upper_grid_layout.addWidget(self.public_ip_text, 3, 2, 1, 1)
        self.upper_grid_layout.setColumnMinimumWidth(0, 120)
        self.gridLayoutWidget.setGeometry(QRect(20, 40, 360, 120))

        self.lower = QGroupBox(self.verticalLayoutWidget)
        self.gridLayoutWidget_2 = QWidget(self.lower)
        self.lower_grid_layout = QGridLayout(self.gridLayoutWidget_2)
        self.lower_grid_layout.setContentsMargins(0, 0, 0, 0)
        self.gridLayoutWidget_2.setGeometry(QRect(20, 40, 360, 120))

        self.usb_server_bar = QLineEdit(self.gridLayoutWidget_2)
        self.usb_server_bar.setStyleSheet(BACKGROUND_GRAY)
        self.usb_server_bar.setAlignment(Qt.AlignCenter)
        self.usb_server_bar.setReadOnly(True)
        self.lower_grid_layout.addWidget(self.usb_server_bar, 0, 1, 1, 1)

        self.machine_state_bar = QLineEdit(self.gridLayoutWidget_2)
        self.machine_state_bar.setStyleSheet(BACKGROUND_GRAY)
        self.machine_state_bar.setAlignment(Qt.AlignCenter)
        self.machine_state_bar.setReadOnly(True)
        self.lower_grid_layout.addWidget(self.machine_state_bar, 2, 1, 1, 1)

        self.usb_server_label = QLabel(self.gridLayoutWidget_2)
        self.lower_grid_layout.addWidget(self.usb_server_label, 0, 0, 1, 1)
        self.machine_state_label = QLabel(self.gridLayoutWidget_2)
        self.lower_grid_layout.addWidget(self.machine_state_label, 2, 0, 1, 1)
        self.ssh_tunnel_label = QLabel(self.gridLayoutWidget_2)
        self.lower_grid_layout.addWidget(self.ssh_tunnel_label, 3, 0, 1, 1)

        self.ssh_tunnel_bar = QLineEdit(self.gridLayoutWidget_2)
        self.ssh_tunnel_bar.setAlignment(Qt.AlignCenter)
        self.ssh_tunnel_bar.setStyleSheet(BACKGROUND_GRAY)
        self.ssh_tunnel_bar.setReadOnly(True)
        self.lower_grid_layout.addWidget(self.ssh_tunnel_bar, 3, 1, 1, 1)
        self.lower_grid_layout.setColumnMinimumWidth(0, 120)

        self.all_layout.addWidget(self.top)
        self.all_layout.addWidget(self.upper)
        self.all_layout.addWidget(self.lower)
        self.button = QPushButton(self.verticalLayoutWidget)
        self.all_layout.addWidget(self.button)
        self.setCentralWidget(self.centralwidget)
        self.retranslate_ui()
        self.init_paperspace_values()

        if self.current_state["machine_state"]() == 'ready':
            tunnel("open", self.current_state[self.connect_by]())

    def retranslate_ui(self):
        global VERSION
        self.setWindowTitle(u"RemotePlay v"+VERSION)
        self.top.setTitle(u"Paperspace parameters")
        self.paperspace_key_label.setText(u"Paperspace API key")
        self.machine_name_label.setText(u"Machine name")
        self.upper.setTitle(u"Paperspace machine info")
        self.host_name_label.setText(u"Host name")
        self.machine_id_label.setText(u"Machine ID")
        self.public_ip_label.setText(u"Public IP")
        self.lower.setTitle(u"Service status")
        self.usb_server_label.setText(u"USB Server")
        self.machine_state_label.setText(u"Machine state")
        self.ssh_tunnel_label.setText(u"SSH Tunnel")
        self.button.setText(u"Start remote")

    def init_paperspace_values(self):
        global API_KEY
        API_KEY = self.paperspace_key_text.text()
        if API_KEY is not None and len(API_KEY) > 0 and self.machine_name_text.count() == 0:
            get_machines()
            self.machine_name_text.currentIndexChanged.disconnect()
            self.machine_name_text.addItems([m["name"] for m in MACHINES])
            self.machine_name_text.setCurrentText(self.machine_name)
            self.machine_name_text.currentIndexChanged.connect(self.init_paperspace_values)
        self.machine_name = self.machine_name_text.currentText()
        if self.machine_name is not None and len(self.machine_name) > 0 and API_KEY is not None and len(API_KEY) > 0:
            self.machine_id, self.public_ip = get_machine(self.machine_name)
            if self.machine_id:
                self.connect_by, self.hostname = determine_host_name(
                    machine_name=self.machine_name, machine_id=self.machine_id, public_ip=self.public_ip)
                self.machine_state = check_state(self.machine_id)
                self.save_config()
                self.update_data()
                self.set_up_button()
                self.start_updating()

    def save_config(self):
        global API_KEY
        home_dir = os.path.expanduser("~")
        if os.name == 'posix':  # Linux and macOS
            config_dir = os.path.join(home_dir, ".remoteplay")
        elif os.name == 'nt':  # Windows
            config_dir = os.path.join(os.getenv('APPDATA'), 'remoteplay')
        else:
            raise OSError("Unsupported operating system")
        if not os.path.exists(config_dir):
            os.makedirs(config_dir)
        config = configparser.ConfigParser()
        config['REMOTE_PLAY'] = {'machine_name': self.machine_name, 'api_key': API_KEY}
        with open(os.path.join(config_dir, 'config.ini'), 'w') as configfile:
            config.write(configfile)

    def load_config(self):
        global API_KEY, VHUSB_PATH
        home_dir = os.path.expanduser("~")
        if os.name == 'posix':  # Linux and macOS
            config_dir = os.path.join(home_dir, ".remoteplay")
        elif os.name == 'nt':  # Windows
            config_dir = os.path.join(os.getenv('APPDATA'), 'remoteplay')
        else:
            raise OSError("Unsupported operating system")
        if os.path.exists(config_dir):
            config_file_path = os.path.join(config_dir, 'config.ini')
            if os.path.exists(config_file_path):
                config = configparser.ConfigParser()
                config.read(config_file_path)
                if 'REMOTE_PLAY' in config:
                    self.machine_name = config['REMOTE_PLAY'].get('machine_name')
                    API_KEY = config['REMOTE_PLAY'].get('api_key')
                    VHUSB_PATH = config['REMOTE_PLAY'].get('vhusb_path')

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
        try:
            self.stop_updating()
            self.button.setEnabled(False)
            self.thread = QThread()
            self.worker = ChangeMachineStatus(self.machine_id)
            if action == "stop":
                self.worker.stop()
                tunnel("close")
            else:
                start_usbserver()
            self.worker.moveToThread(self.thread)

            self.thread.started.connect(self.worker.run)
            self.thread.finished.connect(self.thread.deleteLater)

            self.worker.finished.connect(self.thread.quit)
            self.worker.finished.connect(self.status_change_complete)
            self.worker.finished.connect(self.worker.deleteLater)
            self.worker.status.connect(self.update_state)
            self.thread.start()
        except Exception as e:
            handle_error(e)

    def status_change_complete(self):
        state = self.current_state["machine_state"]()
        self.current_state["machine_state"] = (lambda: check_state(self.machine_id))
        self.set_up_button()
        self.start_updating()
        if state == 'ready':
            tunnel("open", self.current_state[self.connect_by]())

    def update_state(self, state):
        self.machine_state = state
        self.update_data()

    def start_updating(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_data)
        self.timer.start(5000)  # Update every 5 seconds
        self.update_data()

    def update_data(self):
        self.machine_id_text.setText(self.current_state.get("machine_id", (lambda: None))())
        self.machine_name_text.setCurrentText(self.current_state.get("machine_name", (lambda: None))())
        self.host_name_text.setText(self.current_state.get("hostname", (lambda: None))())
        self.public_ip_text.setText(self.current_state.get("public_ip", (lambda: None))())
        lmd = self.current_state.get("usb_server")
        self.usb_server_bar.setText(lmd())
        match lmd():
            case "inactive":
                self.usb_server_bar.setStyleSheet(BACKGROUND_GRAY)
            case "active":
                self.usb_server_bar.setStyleSheet(BACKGROUND_GREEN)
        lmd = self.current_state.get("ssh_tunnel")
        self.ssh_tunnel_bar.setText(lmd())
        match lmd():
            case "closed":
                self.ssh_tunnel_bar.setStyleSheet(BACKGROUND_GRAY)
            case "error":
                self.ssh_tunnel_bar.setStyleSheet("background-color: red;")
            case "open":
                self.ssh_tunnel_bar.setStyleSheet(BACKGROUND_GREEN)
        lmd = self.current_state.get("machine_state")
        self.machine_state_bar.setText(lmd())
        match lmd():
            case "off":
                self.machine_state_bar.setStyleSheet(BACKGROUND_GRAY)
            case "starting":
                self.machine_state_bar.setStyleSheet("background-color: yellow;")
            case "stopping":
                self.machine_state_bar.setStyleSheet("background-color: yellow;")
            case "ready":
                self.machine_state_bar.setStyleSheet(BACKGROUND_GREEN)

    def stop_updating(self):
        self.timer.stop()


def handle_error(e):
    msg = QMessageBox() 
    msg.setIcon(QMessageBox.Critical)
    if hasattr(e, 'message'):
        msg.setText(e.message)
    elif hasattr(e, 'strerror'): 
        msg.setText(e.strerror)       
    else:
        msg.setText(repr(e))
    msg.setWindowTitle("RemotePlay Error") 
    msg.setStandardButtons(QMessageBox.Ok) 
    msg.exec_()
    raise e


def main():
    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
