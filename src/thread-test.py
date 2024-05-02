import os
import configparser
import sys
from json import loads
from time import sleep

import requests
from PyQt5.QtCore import pyqtSignal, QObject, QThread, QRect, Qt
from PyQt5.QtWidgets import QMainWindow, QVBoxLayout, QLabel, QLineEdit, QPushButton, QApplication, QWidget, \
    QGridLayout, QGroupBox, QComboBox, QMessageBox, QMessageBox

BACKGROUND_GRAY = "background-color: darkgray;"
BACKGROUND_GREEN = "background-color: green;"

PAPERSPACE_API = "https://api.paperspace.com/v1"

VERSION = '0.2.5'


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
        self.machines = None
        self.machine_name = None
        self.machine_id = None
        self.public_ip = None
        self.connect_by = "machine_name"
        self.hostname = None
        self.machine_state = None
        self.api_key = None

        self.load_config()
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
        self.top_grid_layout.setColumnMinimumWidth(0, 100)
        self.top_layout_widget.setGeometry(QRect(20, 40, 360, 120))
        self.top.setFixedHeight(160)

        self.all_layout.addWidget(self.top)
        self.button = QPushButton(self.verticalLayoutWidget)
        self.all_layout.addWidget(self.button)
        self.setCentralWidget(self.centralwidget)
        self.retranslate_ui()
        self.init_paperspace_values()

    def retranslate_ui(self):
        global VERSION
        self.setWindowTitle(u"RemotePlay v"+VERSION)
        self.top.setTitle(u"Paperspace parameters")
        self.paperspace_key_label.setText(u"Paperspace API key")
        self.machine_name_label.setText(u"Machine name")
        self.button.setText(u"Start remote")

    def init_paperspace_values(self):
        self.api_key = self.paperspace_key_text.text()
        self.machine_name = "Arcturus"
        if self.machine_name is not None and len(self.machine_name) > 0 and self.api_key is not None and len(self.api_key) > 0:
            self.machine_id, self.public_ip = self.get_machine(self.machine_name)
            if self.machine_id:
                self.connect_by, self.hostname = self.determine_host_name()
                self.update_data()
                self.set_up_button()

    def determine_host_name(self):
        return "machine_name", "arcturus.zudljk.dynv6.net"

    def get_machine(self, machine):
        return "pskwujgcp", "74.82.29.115"

    def load_config(self):
        self.machine_name = "Arcturus"
        self.api_key = "6877b8e3692ea32bb20eb07cc3767a"

    def set_up_button(self):
        self.button.setText("Start remote")
        self.button.clicked.connect(self.start_stop_machine)
        self.button.setEnabled(True)

    def start_stop_machine(self):
        self.button.setEnabled(False)
        self.thread = QThread()
        self.worker = ChangeMachineStatus(self.machine_id, self.api_key)
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.thread.finished.connect(self.thread.deleteLater)
        self.worker.finished.connect(self.thread.quit)
        self.thread.start()

    def update_data(self):
        self.machine_state = check_state(self.machine_id, self.api_key)


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
