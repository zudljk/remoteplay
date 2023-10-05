import argparse
import platform
from subprocess import Popen, run, PIPE
from json import dump, loads
from os.path import expanduser
from pathlib import Path
from sys import stderr

from paramiko import SSHClient, Transport, AutoAddPolicy, RSAKey
from paramiko.ssh_exception import AuthenticationException

from .forward import forward_tunnel


def create_ssh_client():
    client = SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(AutoAddPolicy)
    return client


def create_ssh_transport(host, port):
    transport = Transport(host, port)
    # transport.
    return transport


def open_tunnel(localport, host, port, transport):
    transport.connect()
    forward_tunnel(localport, host, port, transport)


def get_config():
    default_id = Path.home() / '.ssh' / 'id_rsa'
    parser = argparse.ArgumentParser(description="Run a remote game on a Paperspace instance",
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("-p", "--platform", required=True, choices=["steam", "gog", "origin"],
                        help="Platform (steam, gog, or origin)")
    parser.add_argument("-m", "--machine", required=True,
                        help="Paperspace Core machine (ID or name) to start the game on")
    parser.add_argument("-a", "--paperspace-apikey", help="Paperspace API key")
    parser.add_argument("--steam-apikey", help="Steam API key (required if starting a Steam game by name)")
    parser.add_argument("-i", "--identity", help="Override identity file for SSH", default=f"{default_id}")
    parser.add_argument("game", help="Game name or ID")
    args = parser.parse_args()
    return vars(args)


def exec_local_command(command, verbose=False, asynch=False):
    try:
        if asynch:
            Popen(str(command).split())
            return 0, "", ""
        else:
            a = run(str(command).split(), stdout=PIPE, stderr=PIPE, shell=True)
            rc = a.returncode
            out = a.stdout.decode('utf-8')
            err = a.stderr.decode('utf-8')
            if verbose:
                print(out)
                print(err, file=stderr)
            return rc, out, err
    except FileNotFoundError:
        return 1, None, "No such file"


def is_node_installed():
    rv, out, err = exec_local_command("npm -v")
    return rv == 0 and not err


def is_paperspace_installed():
    rv, out, err = exec_local_command("npm ls -g paperspace-node")
    return rv == 0 and not err


def install_paperspace():
    print("Installing paperspace-node ...")
    rv, out, err = exec_local_command("npm i -g paperspace-node")
    if rv != 0:
        print(err)
    return rv == 0 and not err


def fail(param):
    raise RuntimeError(param)


def ensure_paperspace_installed():
    if not is_node_installed():
        fail("NodeJS not installed")
    if not is_paperspace_installed():
        if not install_paperspace():
            fail("paperspace-node could not be installed")


def create(config_file, content):
    with open(config_file.absolute(), "w") as pconfig:
        dump(content, pconfig)


def ensure_paperspace_logged_in(api_key):
    ensure_paperspace_installed()
    config_file = Path.home() / '.paperspace' / 'config.json'
    if not config_file.is_file():
        if not api_key:
            fail("Not logged in to Paperspace and no API key given")
        create(config_file, {"apiKey": api_key, "name": "remoteplay"})
    print(f"Logged in to Paperspace")


def ensure_paperspace_started(api_key, machine_id):
    ensure_paperspace_logged_in(api_key)
    print(f"Starting machine {machine_id}")
    for cmd in "start", "waitfor":
        if not exec_local_command(f'paperspace machines {cmd} --machineId {machine_id} --state ready'):
            fail("Could not start Paperspace machine")


def build_command(game, ptf):
    if ptf == 'steam':
        return f'"C:\\Program Files (x86)\\Steam\\steam.exe" steam://rungameid/{game}'
    elif ptf == 'gog':
        return f"\"C:\\Program Files (x86)\\GOG Galaxy\\gog.exe\" /gameId={game} /command=runGame"
    elif ptf == 'origin':
        return f"\"C:\\Program Files (x86)\\Origin Games\\{game}\""
    else:
        fail(f"Platform {ptf} not supported")


def execute_remote_command(client, command, host, port=22, identity_file=None):
    key = RSAKey.from_private_key_file(identity_file)
    client.connect(host, port, pkey=key)
    print(f"Executing remote command: {command}")
    stdin, stdout, stderr = client.exec_command(command)
    return stdout.channel.recv_exit_status()


def get_paperspace_machine(api_key, machine):
    ensure_paperspace_logged_in(api_key)
    rv, out, err = exec_local_command("paperspace machines list")
    if rv != 0:
        fail(err)
    p = loads(out)
    m = next((x for x in p if x["id"] == machine or x["name"] == machine))
    return m["id"], m["publicIpAddress"]


def start_remote_desktop():
    cmd = "parsecd"
    if platform.system() == 'Darwin':
        cmd = Path("/Applications") / "Parsec.app" / "Contents" / "MacOS" / cmd
    elif platform.system() == 'Linux':
        fail("Platform Linux not supported yet")
    else:
        cmd = Path("C:/", "Program Files (x86)", "Parsec", cmd)
    rv, out, err = exec_local_command(cmd, asynch=True)
    if rv != 0:
        print(err, file=stderr)
        fail("Could not start Parsec client")


def run_remote_game(config):
    client = create_ssh_client()
    api_key = config["apikey"] if "apikey" in config else None
    machine_id, host = get_paperspace_machine(api_key, config["machine"])
    ensure_paperspace_started(api_key, machine_id)
    command = build_command(config['game'], config["platform"])
    # open_tunnel(7575, host, 7575, create_ssh_transport(host, ))
    try:
        execute_remote_command(client, command, host, identity_file=expanduser(config['identity']))
    except AuthenticationException:
        print("Login to remote machine failed: Not authorized", file=stderr)
    start_remote_desktop()


def main():
    run_remote_game(get_config())

if __name__ == '__main__':
    main()

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
