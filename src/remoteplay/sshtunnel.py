import subprocess


class SshTunnel:

    def __init__(self):
        self.host_provider = (lambda: None)
        self.process = None

    def open(self):
        if self.host_provider() is not None and self.process is None:
            self.process = subprocess.Popen(["ssh", "-N", "-R", "7575:localhost:7575",
                                             "-o", "StrictHostKeyChecking=no", self.host_provider()])

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

    @staticmethod
    def get_ssh_config(machine_id):
        process = subprocess.Popen(["ssh", "-G", machine_id], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        for line in process.stdout:
            l = line.strip()
            if l.lower().startswith('hostname'):
                return l.split()[1]
        return None
