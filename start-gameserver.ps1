function Get-PublicIP {
    param(
        [string]$MachineId,
        [string]$ApiKey
    )

    $Headers = @{
        "Content-Type" = "application/json"
        "Authorization" = "Bearer $ApiKey"
    }

    $Response = Invoke-RestMethod -Uri "https://api.paperspace.io/machines/$MachineId" -Headers $Headers
    $PublicIP = $Response.ip
    return $PublicIP
}

function Start-Machine {
    param(
        [string]$MachineId,
        [string]$ApiKey
    )

    $Headers = @{
        "Content-Type" = "application/json"
        "Authorization" = "Bearer $ApiKey"
    }

    Invoke-RestMethod -Uri "https://api.paperspace.io/machines/$MachineId/start" -Headers $Headers

    # Wait until machine is ready
    while ($true) {
        $State = Check-State -MachineId $MachineId -ApiKey $ApiKey
        if ($State -eq "ready") {
            break
        }
        Start-Sleep -Seconds 5
    }
}

function Check-State {
    param(
        [string]$MachineId,
        [string]$ApiKey
    )

    $Headers = @{
        "Content-Type" = "application/json"
        "Authorization" = "Bearer $ApiKey"
    }

    $Response = Invoke-RestMethod -Uri "https://api.paperspace.io/machines/$MachineId" -Headers $Headers
    $State = $Response.state
    return $State
}

function Stop-Machine {
    param(
        [string]$MachineId,
        [string]$ApiKey
    )

    $Headers = @{
        "Content-Type" = "application/json"
        "Authorization" = "Bearer $ApiKey"
    }

    Invoke-RestMethod -Method Post -Uri "https://api.paperspace.io/machines/$MachineId/stop" -Headers $Headers

    # Wait until machine is stopped
    while ($true) {
        $State = Check-State -MachineId $MachineId -ApiKey $ApiKey
        if ($State -eq "off") {
            break
        }
        Start-Sleep -Seconds 5
    }
}

function Determine-HostName {
    param(
        [string[]]$Ids
    )

    foreach ($id in $Ids) {
        $sshOutput = ssh -G $id
        $hostLine = $sshOutput | Select-String -Pattern '^HostName' -IgnoreCase

        if ($hostLine) {
            $thehost = ($hostLine -split '\s+')[1]
            return $thehost
        }
    }
}

Write-Host "Starting USB server ..."
Start-Process "C:\Program Files\VirtualHere\vhusbdwin64.exe"

# Get the public IP of the machine
$PUBLIC_IP = Get-PublicIP -MachineId $args[0] -ApiKey $args[1]

$THE_HOST = Determine-HostName -Ids $args[0], $PUBLIC_IP

# Start the machine
Start-Machine -MachineId $args[0] -ApiKey $args[1]

# Create SSH tunnel
Write-Host "Creating SSH tunnel..."
Start-Process ssh -ArgumentList "-N -R 7575:localhost:7575 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null $THE_HOST" -NoNewWindow

# Trap Ctrl-C to stop the machine and close the SSH tunnel
Write-Host "Press Ctrl-C to stop the machine and close the SSH tunnel..."
$null = $host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
Stop-Machine -MachineId $args[0] -ApiKey $args[1]
Stop-Process -Name "ssh"
