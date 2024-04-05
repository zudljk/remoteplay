#!/bin/bash

# Function to retrieve the public IP of the Paperspace machine
get_public_ip() {
    machine_id=$1
    api_key=$2
    public_ip=$(curl -s \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $api_key" \
        https://api.paperspace.io/machines/$machine_id | jq -r '.ip')
    echo $public_ip
}

# Function to start the Paperspace machine
start_machine() {
    machine_id=$1
    api_key=$2
    curl -X POST \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $api_key" \
        -d '{"machineId": "'"$machine_id"'"}' \
        https://api.paperspace.io/machines/$machine_id/start

    # Wait until machine is ready
    while true; do
        state=$(check_state $1)
        if [ "$state" = "ready" ]; then
            break
        fi
        sleep 5
    done
}

# Function to check the state of the Paperspace machine
check_state() {
    machine_id=$1
    api_key=$2
    state=$(curl -s \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $ap_key" \
        https://api.paperspace.io/machines/$machine_id | jq -r '.state')
    echo $state
}

# Function to stop the Paperspace machine
stop_machine() {
    machine_id=$1
    api_key=$2
    curl -X POST \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $api_key" \
        -d '{"machineId": "'"$machine_id"'"}' \
        https://api.paperspace.io/machines/$machine_id/stop

    # Wait until machine is stopped
    while true; do
        state=$(check_state $1)
        if [ "$state" = "off" ]; then
            break
        fi
        sleep 5
    done
}

determine_host_name() {
    for id in $* ; do
        ssh -G $id | grep -i ^HostName | read key host
        if [ -n "$host" ] ; then
            echo $host
            break
        fi
    done
}

echo "Starting USB server ..."
/Applications/VirtualHereServerUniversal.app/Contents/MacOS/vhusbdosx || echo "Cannot start USB server; maybe already started?"

# Get the public IP of the machine
PUBLIC_IP=$(get_public_ip $1)

HOST=$(determine_host_name $PUBLIC_IP $1)

# Start the machine
start_machine $1

# Create SSH tunnel
echo "Creating SSH tunnel..."
ssh -N -R 7575:localhost:7575 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null $HOST &

# Trap Ctrl-C to stop the machine and close the SSH tunnel
trap 'stop_machine $1' INT

# Wait until user presses Ctrl-C
echo "Press Ctrl-C to stop the machine and close the SSH tunnel..."
while true; do
    sleep 1
done
