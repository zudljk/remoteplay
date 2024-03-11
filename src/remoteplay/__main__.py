import argparse
import socket
import select
import sys
import platform
from subprocess import Popen, run, PIPE
from json import dump
from os.path import expanduser
from getpass import getuser
from os import path
from pathlib import Path
from sys import stderr
from sys import executable
from re import search
from logging import getLogger, error, ERROR, warn, WARNING, debug, DEBUG, info, INFO
from time import sleep
import signal

from threading import Thread

from paramiko import SSHClient, Transport, AutoAddPolicy, RSAKey
from paramiko.ssh_exception import AuthenticationException
from paramiko.config import SSHConfig

from remoteplay.paperspace import list_machines, start_machine, stop_machine

VERSION = '0.0.24'

log = getLogger("root")

loglevels = {
    "error": ERROR,
    "warn": WARNING,
    "warning": WARNING,
    "info": INFO,
    "debug": DEBUG
}

commands = {
    "Windows": {
        "parsecd": Path("C:/", "Program Files", "Parsec", "parsecd.exe")
    },
    "Darwin": {
        "parsecd": Path("/Applications") / "Parsec.app" / "Contents" / "MacOS" / "parsecd"
    },
    "Linux": {
        "parsecd": Path("parsecd")
    }
}



def create_ssh_client():
    client = SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(AutoAddPolicy)
    return client


def create_ssh_transport(host, port):
    transport = Transport((host, port))
    return transport


def open_tunnel(localport, host, port, client):
    def handler(chan, host, port):
        sock = socket.socket()
        try:
            sock.connect((host, port))
        except Exception as e:
            print("Forwarding request to %s:%d failed: %r" % (host, port, e))
            return

        while True:
            r, w, x = select.select([sock, chan], [], [])
            if sock in r:
                data = sock.recv(1024)
                if len(data) == 0:
                    break
                chan.send(data)
            if chan in r:
                data = chan.recv(1024)
                if len(data) == 0:
                    break
                sock.send(data)
        chan.close()
        sock.close()

    def accept_connections(localport, host, port, client):
        transport = client.get_transport()
        transport.request_port_forward("", localport)
        while True:
            chan = transport.accept(1000)
            if chan is None:
                continue
            thr = Thread(target=handler, args=(chan, host, port))
            thr.daemon = True
            thr.start()
    
    acceptor = Thread(target=accept_connections, args=(localport, host, port, client))
    acceptor.daemon = True
    acceptor.start()


def get_config():
    default_id = Path.home() / '.ssh' / 'id_rsa'
    parser = argparse.ArgumentParser(description="Run a remote game on a Paperspace instance",
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--version", action="version", version=VERSION)
    parser.add_argument("--log-level", help="Set log level", default="info")
    parser.add_argument("-p", "--platform", choices=["steam", "gog", "origin"], default="steam",
                        help="Platform (steam (default), gog, or origin)")
    parser.add_argument("-m", "--machine", required=True,
                        help="Paperspace Core machine (ID or name) to start the game on")
    parser.add_argument("-a", "--paperspace-apikey", required=True, help="Paperspace API key")
    parser.add_argument("--steam-apikey", help="Steam API key (required if starting a Steam game by name)")
    parser.add_argument("game", help="Game name or ID")
    args = parser.parse_args()
    return vars(args)


def exec_local_command(command, asynch=False):
    debug(f"Running command: {command}")
    try:
        if asynch:
            Popen(str(command).split())
            return 0, "", ""
        a = run(str(command).split(), stdout=PIPE, stderr=PIPE)
        rc = a.returncode
        out = a.stdout.decode('utf-8')
        err = a.stderr.decode('utf-8')
        debug(out)
        if err and log.getEffectiveLevel() == DEBUG:
            error(err)
        return rc, out, err
    except FileNotFoundError:
        return 1, None, "No such file"


def fail(param):
    raise RuntimeError(param)


def create(config_file, content):
    config_file.parent.mkdir(parents=True, exist_ok=True)
    with open(config_file.absolute(), "w", encoding='utf8') as pconfig:
        dump(content, pconfig)


def ensure_paperspace_started(api_key, machine_id):
    info(f"Starting machine {machine_id}")
    start_machine(api_key, machine_id)
    # give Steam time to start up, otherwise starting the steam app will block indefinitely
    sleep(15)


def ensure_paperspace_stopped(api_key, machine_id):
    info(f"Stopping machine {machine_id}")
    stop_machine(api_key, machine_id)


def build_command(game, ptf):
    if game.startswith("steam://"):
        return f'C:\\Progra~2\\Steam\\steam.exe {game}'
    elif ptf == 'steam':
        return f'C:\\Progra~2\\Steam\\steam.exe steam://rungameid/{game}'
    elif ptf == 'gog':
        return f"\"C:\\Program Files (x86)\\GOG Galaxy\\gog.exe\" /gameId={game} /command=runGame"
    elif ptf == 'origin':
        return f"\"C:\\Program Files (x86)\\Origin Games\\{game}\""
    else:
        fail(f"Platform {ptf} not supported")


def execute_remote_command(client, command, host, user, port=22, identity_file=None):
    key = RSAKey.from_private_key_file(identity_file)    
    client.connect(hostname=host, port=port, username=user, pkey=key)
    debug(f"Executing remote command: {command}")
    stdin, stdout, stderr = client.exec_command(command)
    return stdout.channel.recv_exit_status()


def get_paperspace_machine(api_key, machine):
    p = list_machines(api_key)
    m = next((x for x in p if x["id"] == machine or x["name"] == machine))
    return m["id"], m["publicIp"]


def get_platform_command(command):
    if platform.system() in commands:
        return commands.get(platform.system()).get(command, command)
    fail(f"Platform {platform.system()} not supported yet")


def start_remote_desktop():
    rv, out, err = exec_local_command(get_platform_command("parsecd"), asynch=True)
    if rv != 0:
        error(err)
        fail("Could not start Parsec client")


def get_credentials(ssh_config, host):
    if host in ssh_config.get_hostnames():
        host_config = ssh_config.lookup(host)
        identity_file = [ expanduser(x) for x in host_config.get("identityfile")][0]
        user = host_config.get("user")
        return user, identity_file
    return None, None

# Steam game ID is in STEAM_ROOT/steamapps/appmanifest_ID.acf
# GOG game ID can be fetched via API: https://embed.gog.com/games/ajax/filtered?mediaType=game&search=Witcher%203
def run_remote_game(config):
    log.setLevel(loglevels.get(config["log_level"], INFO))
    client = create_ssh_client()
    api_key = config["paperspace_apikey"] 
    machine_id, host = get_paperspace_machine(api_key, config["machine"])
    ensure_paperspace_started(api_key, machine_id)
    command = build_command(config['game'], config["platform"])

    def clean_up(sig, frame):
        info('Exiting ...')
        ensure_paperspace_stopped(api_key, machine_id)
        sys.exit(0)

    signal.signal(signal.SIGINT, clean_up)
    signal.signal(signal.SIGTERM, clean_up)

    user = getuser()
    ssh_config_file = Path.home() / '.ssh' / 'config'
    if path.exists(ssh_config_file):
        ssh_config = SSHConfig.from_path(ssh_config_file)
        if ssh_config:
            user, identity_file = get_credentials(ssh_config, config['machine'])
            if user is None and identity_file is None:
                user, identity_file = get_credentials(ssh_config, host)
            if user is None:
                user = getuser()
            if identity_file is None:
                identity_file = config.get("identity")

    try:
        execute_remote_command(client, command, host, user, identity_file=identity_file)
        start_remote_desktop()
        print("Press Ctrl+C to close SSH tunnel")
        open_tunnel(7575, "localhost", 7575, client)
        while True:
            sleep(0.1)
    except AuthenticationException:
        error("Login to remote machine failed: Not authorized")
    except KeyboardInterrupt:
        clean_up(None, None)


def main():
    run_remote_game(get_config())


if __name__ == '__main__':
    main()

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
