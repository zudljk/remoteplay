from remoteplay.__main__ import main as remoteplay
from sys import argv

if len(argv) > 1 and argv[1] == '--create-executable':
    import PyInstaller.__main__
    PyInstaller.__main__.run([ __file__, '--onefile', '--name', 'remoteplay', '--exclude-module', 'PyInstaller' ])
elif __name__ == '__main__':
    remoteplay()
