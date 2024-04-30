from remoteplay.__main__ import main as remoteplay
from sys import argv, executable
from platform import system

if len(argv) > 1 and argv[1] == '--create-executable':
    import PyInstaller.__main__
    import subprocess

    subprocess.check_call([executable, "-m", "pip", "install", '.'])
    if system() == 'Darwin':  # Linux and macOS
        PyInstaller.__main__.run([__file__, '--windowed', '--name', 'remoteplay', '--exclude-module', 'PyInstaller'])
    elif system() == 'Windows':  # Windows
        PyInstaller.__main__.run([__file__, '--windowed', '--onefile', '--name', 'remoteplay', '--exclude-module', 'PyInstaller'])
    else:
        PyInstaller.__main__.run([__file__, '--onefile', '--name', 'remoteplay', '--exclude-module', 'PyInstaller'])
elif __name__ == '__main__':
    remoteplay()
