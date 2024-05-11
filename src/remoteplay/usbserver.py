from platform import system
import os
import subprocess
import psutil


class UsbServer:

    def __init__(self, path):
        self.vhusb_path = path

    def start(self):
        if self.get_status() != "active":
            if self.vhusb_path is None:
                if system() == 'Darwin':
                    self.vhusb_path = os.path.join("/", "Applications", "VirtualHereServerUniversal.app", "Contents",
                                                   "MacOS",
                                                   "vhusbdosx")
                    subprocess.Popen(self.vhusb_path)
                elif system() == 'Windows':
                    from ctypes import windll
                    self.vhusb_path = os.path.join("C:\\", "Program Files", "VirtualHere", "vhusbdwin64.exe")
                    windll.shell32.ShellExecuteW(None, "runas", self.vhusb_path, "", None, 1)
                else:
                    subprocess.Popen('vhuit64')
            else:
                subprocess.Popen(self.vhusb_path)

    @staticmethod
    def get_status():
        for proc in psutil.process_iter(['name']):
            if "vhusb" in proc.info['name']:
                return "active"
        return "inactive"
