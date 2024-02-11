# Remoteplay


A program that runs Steam, GOG and Origin games on a remote Paperspace machine.

## Prerequisites

To make this work you need:

* A Parsec account (https://parsec.app).
* A Paperspace account (https://www.paperspace.com)

On your paperspace account you need

* A virtual machine running Windows
* An API key. If you don't have one, use the following steps to create one:
  * Log in to Paperspace
  * Go to "Core"
  * Click on your avatar on the top right
  * Select "Team Settings"
  * Select "API Keys"
  * Enter a name for the key and click "Create"

On your Paperspace machine, you need:
* Windows 10 or higher
* An SSH server (e.g. BitVise SSH)
* The Parsec app, logged in to your Parsec account
* A game client - Steam, GOG Galaxy, and EA (formerly Origin) are supported
* The game you want to run must already be installed.
* VirtualHere Remote USB client (optional) 

On your local machine you need

* The Parsec app, logged in to your Parsec account
* VirtualHere Remote USB server (optional)

## Third-party software

* Paperspace is a cloud service offering virtual machines for many purposes, mainly for AI applications but they can also be used for gaming.

* Parsec is a super-fast remote desktop application optimized for gaming.

* VirtualHere is a client-server software for sharing USB devices over a network.

* Steam, GOG Galaxy and EA (formerly Origin) are game store clients supplied by the games' distributors.


## Usage

To run `remoteplay`, you start the executable from the command line:

```
remoteplay.exe [options] GAME_ID
```

The following options are supported:

| Short option | Long option | Description |
| -- | -- | -- |
| -h  | --help | Show a help message and exit |
|  | --version | Print the version and exit |
| -p PLATFORM| | Try to start the game via the given PLATFORM. Supported values are `steam`, `gog` and `origin`. If not given, try to guess the option from the given game ID (like `steam://rungameid/..`). If that fails, use `steam`. |
| -m MACHINE | --machine MACHINE | Use the given MACHINE name; must be a valid Paperspace machine name or ID |
| -a PAPERSPACE_APIKEY | | Use the given PAPERSPACE_APIKEY as the API key to access your Paperspace account (see above) |
| | --steam-apikey | (currently not used) |

The GAME_ID is the platform-specific ID of the game.

* For Steam games, the ID can be found when you right-click the game in your Steam library and selecting "Properties", then "Updates". The long number under "App-ID" is the game ID. `remoteplay` both supports the plain number and the Steam URL in this form: `steam://rungameid/12345`
* For GOG games, go to the GOG Galaxy installation folder, and there into "Games". In every game's folder, GOG will create a file that contains the game's GOG ID.

Consult the documentation for other platforms on how to find the game ID.

## How it works

Remoteplay uses the Paperspace API to boot up your remote machine.

Then, it will open an SSH connection to run the game on the remote machine.

After that, it will start the Parsec client so you can connect to the desktop of your remote machine.

Once you close the running `remoteplay` instance by pressing Ctrl+C in the application window, the application will close the SSH connection and shut down the remote machine.

## USB redirection

In order to use USB devices other than keyboard and mouse on the remote machine (e.g. HOTAS for simulation games), you can use the VirtualHere Remote USB software. It can be downloaded from https://virtualhere.com. The client is free to use, the server comes with an unlimited evaluation license that allows you to share one (1) device over the network.

Remoteplay will open an SSH tunnel, forwarding port 7575 (the port where the VirtualHere server is listening) to the remote machine.

On the remote machine, you'll have to download and install the VirtualHere client and connect it to "localhost".

Then you will be able to use your local USB device on the remote machine.

_Note that this is not necessary for mouse and keyboard, since they are supported by Parsec out of the box._

## Further notes

* After booting up the remote machine, the program will wait for 15 seconds to give the remote Steam instance time to start up. Without that, Steam sometimes locks up until the next restart of the remote machine.