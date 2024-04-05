#!/bin/bash

PAPERSPACE_API=https://api.paperspace.com/v1
MACHINE_NAME=$1
API_KEY=$2

# Function to retrieve the public IP of the Paperspace machine
get_machine_id() {
    echo $(curl -s -H "Authorization: Bearer $API_KEY" $PAPERSPACE_API/machines | jq -r ".items[] | select(.name == \"$1\") | .id")
}

get_public_ip() {
    echo $(curl -s -H "Authorization: Bearer $API_KEY" $PAPERSPACE_API/machines/$1 | jq -r '.publicIp')
}

# Function to start the Paperspace machine
start_machine() {
    curl -X PATCH -H "Authorization: Bearer $API_KEY" $PAPERSPACE_API/machines/$1/start

    # Wait until machine is ready
    state=off
    while [ "$state" != "ready" ]; do
        sleep 5
        state=$(check_state $1)
    done
}

# Function to check the state of the Paperspace machine
check_state() {
    echo $(curl -s -H "Authorization: Bearer $API_KEY" $PAPERSPACE_API/machines/$1 | jq -r '.state')
}

# Function to stop the Paperspace machine
stop_machine() {
    curl -X PATCH -H "Authorization: Bearer $API_KEY" $PAPERSPACE_API/machines/$1/stop

    # Wait until machine is stopped
    state=ready
    while [ "$state" != "off" ]; do
        sleep 5
        state=$(check_state $1)
    done
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

echo "Starting USB server ..."
/Applications/VirtualHereServerUniversal.app/Contents/MacOS/vhusbdosx || echo "Cannot start USB server; maybe already started?"

# Get the Paperspace ID by name
MACHINE_ID=$(get_machine_id $MACHINE_NAME)

# Get the public IP of the machine
PUBLIC_IP=$(get_public_ip $MACHINE_ID)

HOST=$(determine_host_name $MACHINE_NAME $MACHINE_ID $PUBLIC_IP)

# Start the machine
start_machine $MACHINE_ID

# Create SSH tunnel
echo "Creating SSH tunnel..."
ssh -N -R 7575:localhost:7575 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null $HOST &

# Trap Ctrl-C to stop the machine and close the SSH tunnel
trap 'stop_machine $MACHINE_ID ; exit' INT

# Wait until user presses Ctrl-C
echo "Press Ctrl-C to stop the machine and close the SSH tunnel..."
while true; do
    sleep 1
done
