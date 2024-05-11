import subprocess
from platform import system



class SshTunnel:
    def __init__(self):
        self.host_provider = lambda: None
        self.process = None

    def open(self):
        if self.host_provider() is not None and self.process is None:
            command = [
                "ssh",
                "-N",
                "-R",
                "7575:localhost:7575",
                "-o",
                "StrictHostKeyChecking=no",
                self.host_provider(),
            ]
            if system() == 'Windows':
                self.process = subprocess.Popen(command, creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                self.process = subprocess.Popen(command)

    def close(self):
        if self.process:
            self.process.terminate()

    def check(self):
        if not self.process:
            return "closed"
        return_code = self.process.poll()
        if return_code is None:
            return "open"
        elif return_code > 0:
            return "error"
        else:
            return "closed"
