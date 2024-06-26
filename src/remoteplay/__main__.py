import subprocess
import os
import configparser
import sys
import logging
from pkg_resources import get_distribution
from re import compile
from .common import check_state, request_get
from .usbserver import UsbServer
from .sshtunnel import SshTunnel
from .worker import ChangeMachineStatus

from PyQt5.QtCore import QTimer, QRect, Qt
from PyQt5.QtWidgets import QMainWindow, QVBoxLayout, QLabel, QLineEdit, QPushButton, QApplication, QWidget, \
    QGridLayout, QGroupBox, QComboBox, QMessageBox

BACKGROUND_GRAY = "background-color: darkgray;"
BACKGROUND_GREEN = "background-color: green;"

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

VERSION = get_distribution('remoteplay').version


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.machines = None
        self.machine_name = None
        self.machine_id = None
        self.public_ip = None
        self.connect_by = "machine_name"
        self.hostname = None
        self.machine_state = None
        self.api_key = None
        self.vhusb_path = None

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.handle_timer)

        self.load_config()

        self.usb_server = UsbServer(self.vhusb_path)
        self.current_state = {
            "machine_id": (lambda: self.machine_id),
            "machine_name": (lambda: self.machine_name),
            "hostname": (lambda: self.hostname),
            "public_ip": (lambda: self.public_ip)
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
        self.paperspace_key_text.setText(self.api_key)
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
        self.ssh_tunnel = SshTunnel()
        self.init_paperspace_values()
        self.ssh_tunnel.host_provider = self.current_state[self.connect_by]
        self.status_change_complete()

    def retranslate_ui(self):
        global VERSION
        self.setWindowTitle(u"RemotePlay v" + VERSION)
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
        logger.info("Initializing ...")
        self.api_key = self.paperspace_key_text.text()
        if self.api_key is not None and len(self.api_key) > 0 and self.machine_name_text.count() == 0:
            self.machine_name_text.currentIndexChanged.disconnect()
            self.machine_name_text.addItems([m["name"] for m in self.get_machines()])
            self.machine_name_text.setCurrentText(self.machine_name)
            self.machine_name_text.currentIndexChanged.connect(self.init_paperspace_values)
        self.machine_name = self.machine_name_text.currentText()
        if self.machine_name is not None and len(self.machine_name) > 0 and self.api_key is not None and len(
                self.api_key) > 0:
            self.machine_id, self.public_ip = self.get_machine(self.machine_name)
            if self.machine_id:
                self.connect_by, self.hostname = self.determine_host_name()
                self.machine_state = check_state(self.machine_id, self.api_key)
                self.save_config()
                self.set_up_button()

    def determine_host_name(self):
        connectors = {"machine_name": self.machine_name, "machine_id": self.machine_id, "public_ip": self.public_ip}
        # try to find a "Host" entry in ~/.ssh/config to determine the host name
        for type, id in connectors.items():
            process = subprocess.Popen(["ssh", "-G", id], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            for line in process.stdout:
                l = line.strip()
                if l.lower().startswith('hostname'):
                    return type, l.split()[1]
        # if not found, return the first argument that looks like an IPv4 or IPv6 address
        ip = compile("([0-2][0-9][0-9]\\.?){4}|[0-9:]+")
        for id in connectors.values():
            if ip.match(id):
                return id
        # if none found, return none
        return None

    def get_machine(self, machine):
        try:
            m = next((x for x in self.get_machines() if x["id"] == machine or x["name"] == machine))
            return m["id"], m["publicIp"]
        except StopIteration:
            return None, None

    def get_machines(self):
        if self.machines is None:
            self.machines = request_get("", self.api_key)["items"]
        return self.machines

    def save_config(self):
        logger.info("Saving configuration ...")
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
        config['REMOTE_PLAY'] = {
            'machine_name': self.machine_name,
            'api_key': self.api_key
        }
        if self.vhusb_path:
            config["REMOTE_PLAY"]['vhusb_path'] = self.vhusb_path
        with open(os.path.join(config_dir, 'config.ini'), 'w') as configfile:
            config.write(configfile)

    def load_config(self):
        logger.info("Loading configuration ...")
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
                    self.api_key = config['REMOTE_PLAY'].get('api_key')
                    self.vhusb_path = config['REMOTE_PLAY'].get('vhusb_path')

    def set_up_button(self):

        try:
            self.button.clicked.disconnect()
        except TypeError:
            pass

        if self.machine_state == "ready":
            self.button.setText("Stop remote")
            self.button.clicked.connect((lambda: self.start_stop_machine("stop")))
            self.button.setEnabled(True)
            self.paperspace_key_text.setReadOnly(False)
        elif self.machine_state == "off":
            self.button.setText("Start remote")
            self.button.clicked.connect((lambda: self.start_stop_machine("start")))
            self.button.setEnabled(True)
            self.paperspace_key_text.setReadOnly(False)
        elif self.machine_state is None:
            self.button.setText("Please enter API key first")
            self.button.setEnabled(False)
            self.paperspace_key_text.setReadOnly(False)
        else:
            self.button.setText("Please wait")
            self.button.setEnabled(False)
            self.paperspace_key_text.setReadOnly(True)

    def start_stop_machine(self, action):
        try:
            logger.info(f"{action} requested")
            self.stop_updating()
            try:
                self.paperspace_key_text.editingFinished.disconnect()
            except TypeError:
                pass
            if action == "stop":
                self.ssh_tunnel.close()
                self.machine_state = "stopping"
            else:
                self.usb_server.start()
                self.machine_state = "starting"
            self.set_up_button()
            self.update_data()
            self.thread = ChangeMachineStatus(self.machine_id, self.api_key, action)
            self.thread.finished.connect(self.status_change_complete)
            self.thread.finished.connect(self.thread.quit)
            self.thread.finished.connect(self.thread.deleteLater)
            self.thread.status.connect(self.update_state)
            self.thread.start()
        except Exception as e:
            handle_error(e)

    def status_change_complete(self):
        logger.info(f"Target state {self.machine_state} reached")
        self.thread = None
        try:
            self.paperspace_key_text.editingFinished.connect(self.init_paperspace_values)
        except TypeError:
            pass
        self.start_updating()
        if self.machine_state == 'ready':
            self.ssh_tunnel.open()
        self.set_up_button()
        self.update_data()

    def update_state(self, state):
        self.machine_state = state
        self.update_data()

    def handle_timer(self):
        old_state = self.machine_state
        self.update_data()
        if old_state != self.machine_state:
            self.set_up_button()
            # if the remote machine has been started up by someone else, open the tunnel
            if self.machine_state == "ready":
                self.ssh_tunnel.open()
            # if the remote machine has been shutdown by someone else, close the tunnel
            else:
                self.ssh_tunnel.close()

    def update_data(self):
        logger.info(f"Machine state is {self.machine_state}")
        self.machine_id_text.setText(self.machine_id)
        self.machine_name_text.setCurrentText(self.machine_name)
        self.host_name_text.setText(self.hostname)
        self.public_ip_text.setText(self.public_ip)
        lmd = self.usb_server.get_status()
        self.usb_server_bar.setText(lmd)
        match lmd:
            case "inactive":
                self.usb_server_bar.setStyleSheet(BACKGROUND_GRAY)
            case "active":
                self.usb_server_bar.setStyleSheet(BACKGROUND_GREEN)
        lmd = self.ssh_tunnel.check()
        self.ssh_tunnel_bar.setText(lmd)
        match lmd:
            case "closed":
                self.ssh_tunnel_bar.setStyleSheet(BACKGROUND_GRAY)
            case "error":
                self.ssh_tunnel_bar.setStyleSheet("background-color: red;")
            case "open":
                self.ssh_tunnel_bar.setStyleSheet(BACKGROUND_GREEN)
        self.machine_state = check_state(self.machine_id, self.api_key)
        self.machine_state_bar.setText(self.machine_state)
        match self.machine_state:
            case "off":
                self.machine_state_bar.setStyleSheet(BACKGROUND_GRAY)
            case "ready":
                self.machine_state_bar.setStyleSheet(BACKGROUND_GREEN)
            case _:
                self.machine_state_bar.setStyleSheet("background-color: yellow;")

    def start_updating(self):
        logger.info("Starting background updates")
        self.timer.start(5000)

    def stop_updating(self):
        logger.info("Stopping background updates")
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
