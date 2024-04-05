$PAPERSPACE_API = "https://api.paperspace.com/v1"
$MACHINE_NAME = $args[0]
$API_KEY = $args[1]

# Function to retrieve the public IP of the Paperspace machine
function Get-MachineId {
    $response = Invoke-RestMethod -Uri "$PAPERSPACE_API/machines" -Headers @{"Authorization" = "Bearer $API_KEY"}
    $response.items | Where-Object {$_.name -eq $MACHINE_NAME} | Select-Object -ExpandProperty id
}

function Get-PublicIP {
    $machineId = $args[0]
    $response = Invoke-RestMethod -Uri "$PAPERSPACE_API/machines/$machineId" -Headers @{"Authorization" = "Bearer $API_KEY"}
    $response.publicIp
}

# Function to start the Paperspace machine
function Start-Machine {
    param($machineId)
    Invoke-RestMethod -Method PATCH -Uri "$PAPERSPACE_API/machines/$machineId/start" -Headers @{"Authorization" = "Bearer $API_KEY"}

    # Wait until machine is ready
    $state = "off"
    while ($state -ne "ready") {
        Start-Sleep -Seconds 5
        $state = Check-State $machineId
    }
}

# Function to check the state of the Paperspace machine
function Check-State {
    param($machineId)
    $response = Invoke-RestMethod -Uri "$PAPERSPACE_API/machines/$machineId" -Headers @{"Authorization" = "Bearer $API_KEY"}
    $response.state
}

# Function to stop the Paperspace machine
function Stop-Machine {
    param($machineId)
    Invoke-RestMethod -Method PATCH -Uri "$PAPERSPACE_API/machines/$machineId/stop" -Headers @{"Authorization" = "Bearer $API_KEY"}

    # Wait until machine is stopped
    $state = "ready"
    while ($state -ne "off") {
        Start-Sleep -Seconds 5
        $state = Check-State $machineId
    }
}

function Determine-HostName {
    param($ids)
    foreach ($id in $ids) {
        $the_host = ssh -G $id | Select-String -Pattern "^HostName" | ForEach-Object { $_.ToString().Split(' ')[-1] }
        if ($the_host -ne "") {
            return $the_host
        }
    }
}

Write-Output "Starting USB server ..."
Start-Process -FilePath "C:\Program Files\VirtualHere\vhusbdwin64.exe" -NoNewWindow -Wait

# Get the Paperspace ID by name
$MACHINE_ID = Get-MachineId

# Get the public IP of the machine
$PUBLIC_IP = Get-PublicIP $MACHINE_ID

$REALHOST = Determine-HostName $MACHINE_NAME, $MACHINE_ID, $PUBLIC_IP

# Start the machine
Start-Machine -machineId $MACHINE_ID

# Create SSH tunnel
Write-Output "Creating SSH tunnel..."
Start-Process -FilePath "ssh" -ArgumentList "-N -R 7575:localhost:7575 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null $REALHOST" -NoNewWindow

# Trap Ctrl-C to stop the machine and close the SSH tunnel
$null = Read-Host "Press Enter to stop the machine and close the SSH tunnel..."
Stop-Machine -machineId $MACHINE_ID
