import sys
from PyQt5.QtCore import QObject, QThread
from PyQt5.QtWidgets import QMainWindow, QPushButton, QApplication, QWidget

class LongRunningThread(QObject):
    def __init__(self, name):
        super().__init__()
        self.name = name
    def run(self):
        while True:
            print(f"Waiting for {self.name} ...")
            QThread.sleep(5)
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.central_widget = QWidget()
        self.start_thread_button = QPushButton(self.central_widget)
        self.start_thread_button.clicked.connect(self.start_thread)
        self.setCentralWidget(self.central_widget)
        self.start_thread_button.setText("Start Thread")
    def start_thread(self):
        self.start_thread_button.setEnabled(False)
        self.thread = QThread()
        self.worker = LongRunningThread("Godot")
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.thread.start()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec_())
