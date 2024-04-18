#!/bin/bash

PAPERSPACE_API=https://api.paperspace.com/v1
MACHINE_NAME=$1
API_KEY=$2

# Function to retrieve the public IP of the Paperspace machine
get_machine_id() {
    echo $(request GET | jq -r ".items[] | select(.name == \"$1\") | .id")
}

get_public_ip() {
    echo $(request GET $1 | jq -r '.publicIp')
}

request() {
    curl -s -X $1 -H "Authorization: Bearer $API_KEY" $PAPERSPACE_API/machines/$2
}

# Function to start/stop the Paperspace machine
# $1: Machine ID
# $2: Command
# $3: Expected final status
change_machine_status() {
    state=$(check_state $1)
    print_status $state

    if [ "$state" != "$3" ] ; then
        request PATCH $1/$2 > /dev/null
        wait_for_state $1 $3
    fi
    echo
}

# $1: machine ID
# $2: expected state
# $3: command
wait_for_state() {
    state=$(check_state $1)
    while [ "$state" != "$2" ]; do
        sleep 5
        state=$(check_state $1)
        print_status $state
    done
}

color() {
    case $1 in
    off|stopped)
        echo -e "\033[37m$1\033[39m      "
        ;;
    starting|stopping|shutdown*)
        echo -e "\033[33m$1\033[39m      "
        ;;
    ready|active)
        echo -e "\033[32m$1\033[39m      "
        ;;
    failed|inactive|unknown)
        echo -e "\033[31m$1\033[39m      "
        ;;        
    *)
        echo -e "$1                  "‚
        ;;
    esac
}

# Function to check the state of the Paperspace machine
check_state() {
    echo $(request GET $1 | jq -r '.state')
}

start_machine() {
    change_machine_status $1 start ready
}

# Function to stop the Paperspace machine
stop_machine() {
    tunnel close
    print_status "shutdown requested"
    change_machine_status $1 stop off
}

tunnel() {
    case $1 in
    open)
        ssh -N -R 7575:localhost:7575 -o StrictHostKeyChecking=no $2 &
        ;;
    close)
        ps -o pid,command | grep -v grep | grep "7575:localhost:7575" | while read pid rest ; do kill $pid ; done
        ;;
    esac
}

determine_host_name() {
    for id in "$@" ; do
        host=$(ssh -G $id | grep -i ^HostName | cut -f 2 -d " ")
        if [ -n "$host" ] ; then
            echo $host
            break
        fi
    done
}

checkprocess() {
    ps | grep -v grep | grep -q $1 && echo "active" || echo "inactive"
}

print_status() {
    tput cup 0 0
    echo "Machine name:  $MACHINE_NAME"
    echo "Machine ID:    $MACHINE_ID"
    echo "Hostname:      $HOST"
    echo -n "USB server:    "
    color $(checkprocess vhusb)
    echo -n "Machine state: "
    color $1
    echo -n "SSH Tunnel:    "
    color $(checkprocess 7575:localhost:7575)
    echo
    case $1 in
    starting)
        echo "Remote server starting up ..."
        ;;
    stopping)
        echo "Remote server shutting down ..."
        ;;
    ready)
        echo "Press Ctrl-C to stop the machine and close the SSH tunnel."
        ;;
    esac
}


# Get the Paperspace ID by name
MACHINE_ID=$(get_machine_id $MACHINE_NAME)

# Trap Ctrl-C to stop the machine and close the SSH tunnel
trap 'stop_machine $MACHINE_ID ; exit' INT

# Get the public IP of the machine
PUBLIC_IP=$(get_public_ip $MACHINE_ID)
HOST=$(determine_host_name $MACHINE_NAME $MACHINE_ID $PUBLIC_IP)

tput clear
print_status unkown

if [ $(checkprocess vhusb) != "active" ] ; then
    /Applications/VirtualHereServerUniversal.app/Contents/MacOS/vhusbdosx
fi

print_status unknown

# Start the machine
start_machine $MACHINE_ID

tunnel open $HOST

state=ready

while [ "$state" == "ready" ]; do
    print_status $state
    sleep 10
    state=$(check_state $MACHINE_ID)
done
wait_for_state $MACHINE_ID off stop
tunnel close