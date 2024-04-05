# Remoteplay


A helper script for launching remote Paperspace machines and forwarding USB devices to them.

## Prerequisites

You need a Paperspace account (https://www.paperspace.com)

On your paperspace account you need

* A virtual machine running Windows
* An API key. If you don't have one, use the following steps to create one:
  * Log in to Paperspace
  * Go to "Core"
  * Click on your avatar on the top right
  * Select "Team Settings"
  * Select "API Keys"
  * Enter a name for the key and click "Create"
* A public IP address for your machine.

On your Paperspace machine, you need:
* Windows 10 or higher
* An SSH server (e.g. BitVise SSH)
* The Steam game client (https://www.steampowered.com), preferably started automatically at system startup.
* The game you want to run must already be installed.
* VirtualHere Remote USB client. Preferably the client should be started automatically at system startup (put it in the Windows autoruns).

On your local machine you need

* VirtualHere Remote USB server (optional)
* Python 3.10 or higher (only on macOS and Linux)
* The Steam client

## Third-party software

* Paperspace is a cloud service offering virtual machines for many purposes, mainly for AI applications but they can also be used for gaming.

* VirtualHere is a client-server software for sharing USB devices over a network.

* Steam is a game store client provided by Valve Inc.

## Installation

### Windows

Download the latest .exe file from https://github.com/zudljk/remoteplay/releases and save it in a convenient location.
To run the application from the command line, that location needs to be in your PATH environment variable.

### MacOS / Linux

Install the script using `pip`:

```
python -m pip install git+https://github.com/zudljk/remoteplay.git
```

You may need to replace `python` with the name of the executable on your system; sometimes it's called `python3`.

## Usage

To run `remoteplay`, you start the executable from the command line:

```
remoteplay.exe [options] GAME_ID
```

The following options are supported:

| Short option | Long option | Required | Description |
| -- | -- | -- | -- |
| -h  | --help | no | Show a help message and exit |
|  | --version | no | Print the version and exit |
| -m MACHINE | --machine MACHINE | yes | Use the given MACHINE name; must be a valid Paperspace machine name or ID |
| -a PAPERSPACE_APIKEY | | yes | Use the given PAPERSPACE_APIKEY as the API key to access your Paperspace account (see above). |
| | --log-level | no | Output detailed logging messages. Supported values: `debug`, `info` (default), `warn`, `error` |

## How it works

Remoteplay uses the Paperspace API to boot up your remote machine.

Then, it will open an SSH tunnel to forward the USB server port to the remote machine.

Now you can open Steam locally. When you are logged in to Steam on your local machine with the same account as on the remote machine, Steam will offer you
to run the game on the remote machine and stream it to your local machine.

Once you close the running `remoteplay` instance by pressing Ctrl+C in the application window, the application will close the SSH connection and shut down the remote machine.

## SSH connection

For the SSH connection, `remoteplay` respects the settings in `{user home}/.ssh/config`.

If you want to connect to your remote machine with a different username than your local username, or use a special identity file, you can specify it in this file. Example:

```
Host remote-gaming
   HostName 10.11.12.13
   User remoteuser
   IdentityFile C:\\Users\\me\\.ssh\\id_remotegaming
```

**Note: The name after `Host` must be the name or the ID of your Paperspace machine, not any actual host- and domain name you may have given your remote machine. This has to do with the way `remoteplay` finds the entry in the config file. Ideally, you set here the same name that you give to the `-m` parameter. To make the connection possible, you have to specify the actual DNS hostname or public IP as the `HostName` entry. **

## USB redirection

In order to use USB devices other than keyboard and mouse on the remote machine (e.g. HOTAS for simulation games), you can use the VirtualHere Remote USB software. It can be downloaded from https://virtualhere.com. The client is free to use, the server comes with an unlimited evaluation license that allows you to share one (1) device over the network.

Remoteplay will open an SSH tunnel, forwarding port 7575 (the port where the VirtualHere server is listening) to the remote machine.

On the remote machine, you'll have to download and install the VirtualHere client and connect it to "localhost".

Then you will be able to use your local USB device on the remote machine.

_Note that this is not necessary for mouse and keyboard, since they are supported by Steam Link out of the box._

_Note also that the remote VirtualHere USB client will show a confirmation dialog before connecting to your local server, which means you will have to remote-desktop into the remote host and click on confirm to be able to use USB redirection. You can avoid this by using the Windows service version of the USB client, but this won't work with
the free version of the server._ 