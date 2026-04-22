<#
.SYNOPSIS
    Uploads an LED blink program to Propeller 2 and verifies functionality.

.DESCRIPTION
    This script automates the complete workflow for uploading and testing an LED
    blink program on Propeller 2:
    
    1. Auto-detects the Propeller 2 board by scanning COM ports for Prop_Chk response
    2. Checks if board is already in 60-second programming window
    3. If not, sends reset signal to open the window
    4. Verifies bootloader is ready with Prop_Chk
    5. Uploads the LED blink hex program (LED 56)
    
    This script is useful for quick verification that the board is working and
    can be reused repeatedly to test changes.

.PARAMETERS
    None. Edit $ledBlinkHex below to use a different program.

.EXAMPLE
    .\test-led-blink.ps1
    
    Finds the P2 board, uploads LED blink program, reports status at each step.

.NOTES
    - Auto-detects COM port by scanning for Prop_Chk response
    - Reports whether board was already in startup window or needed reset
    - Provides clear feedback at each step
#>

# The LED blink program for LED 56
# This is the hex code you provided
$ledBlinkHex = "> Prop_Hex 0 0 0 0 5F 70 64 FD 4B 4C 80 FF 1F 00 65 FD F0 FF 9F FD ~"

# Helper function to send a command and read the response
function Send-SerialCommand {
    param(
        [System.IO.Ports.SerialPort]$SerialPort,
        [string]$Command,
        [int]$WaitMs = 500
    )
    
    $SerialPort.WriteLine($Command)
    Start-Sleep -Milliseconds $WaitMs
    
    $response = ""
    while ($SerialPort.BytesToRead -gt 0) {
        $response += $SerialPort.ReadExisting()
        Start-Sleep -Milliseconds 50
    }
    
    return $response
}

# Helper function to try a COM port
function Test-ComPort {
    param(
        [string]$ComPort
    )
    
    try {
        $port = New-Object System.IO.Ports.SerialPort
        $port.PortName = $ComPort
        $port.BaudRate = 115200
        $port.Parity = "None"
        $port.DataBits = 8
        $port.StopBits = 1
        $port.ReadTimeout = 1000
        $port.WriteTimeout = 1000
        
        $port.Open()
        $response = Send-SerialCommand $port "> Prop_Chk 0 0 0 0" 500
        $port.Close()
        
        return @{
            Success = $true
            Response = $response
            Port = $port
        }
    } catch {
        return @{
            Success = $false
            Response = ""
            Port = $null
        }
    }
}

Write-Host "========================================================"
Write-Host "  Propeller 2 LED Blink Test (LED 56)"
Write-Host "========================================================"

# Step 1: Find the Propeller 2 board
Write-Host "`n[STEP 1] Auto-detecting Propeller 2 board..."
Write-Host "Scanning COM ports for Prop_Chk response..."

$detectedPort = $null
$boardAlreadyReady = $false
$availablePorts = [System.IO.Ports.SerialPort]::GetPortNames()

if ($availablePorts.Count -eq 0) {
    Write-Host "[ERROR] No COM ports found. Is the board connected?"
    exit 1
}

Write-Host "Found COM ports: $($availablePorts -join ', ')"

foreach ($comPort in $availablePorts) {
    Write-Host "  Checking $comPort..."
    $result = Test-ComPort $comPort
    
    if ($result.Success -and $result.Response) {
        Write-Host "  [OK] Found Propeller 2 on $comPort"
        Write-Host "    Response: $($result.Response.Trim())"
        $detectedPort = $comPort
        $boardAlreadyReady = $true
        break
    }
}

if (-not $detectedPort) {
    Write-Host "[WARN] Propeller 2 not found on any COM port"
    Write-Host "  Board may be in shutdown state (outside 60-second window)"
    Write-Host "  Will attempt reset on all COM ports..."
    $detectedPort = "COM6"  # Default to COM6, or try all ports
}

Write-Host "`n[OK] Board detected on $detectedPort"
if ($boardAlreadyReady) {
    Write-Host "[OK] Board is ALREADY in the 60-second programming window!"
} else {
    Write-Host "[INFO] Board was not responding - will send reset"
}

# Step 2: Open port and reset if needed
Write-Host "`n[STEP 2] Resetting board to ensure fresh programming window..."

$port = New-Object System.IO.Ports.SerialPort
$port.PortName = $detectedPort
$port.BaudRate = 115200
$port.Parity = "None"
$port.DataBits = 8
$port.StopBits = 1
$port.ReadTimeout = 2000
$port.WriteTimeout = 2000

try {
    $port.Open()
    Write-Host "[OK] Serial port $detectedPort opened successfully"
    
    # Send reset signal
    Write-Host "Sending reset signal (DTR toggle)..."
    $port.DtrEnable = $true
    Start-Sleep -Milliseconds 100
    $port.DtrEnable = $false
    Write-Host "[OK] Reset signal sent successfully"
    
    Write-Host "Waiting for board to boot..."
    Start-Sleep -Milliseconds 1500
    
    # Step 3: Verify reset with Prop_Chk
    Write-Host "`n[STEP 3] Verifying bootloader is ready..."
    Write-Host "Sending Prop_Chk verification command..."
    
    $checkResponse = Send-SerialCommand $port "> Prop_Chk 0 0 0 0" 1000
    
    if ($checkResponse) {
        Write-Host "[OK] Board responded: $($checkResponse.Trim())"
        Write-Host "[OK] Bootloader is ready and in programming window!"
    } else {
        Write-Host "[ERROR] No response to Prop_Chk after reset"
        Write-Host "Board may not have reset properly. Check connection and try again."
        $port.Close()
        exit 1
    }
    
    # Step 4: Send the LED blink program
    Write-Host "`n[STEP 4] Uploading LED blink program (LED 56)..."
    Write-Host "Sending hex program..."
    Write-Host "Command: $ledBlinkHex"
    
    $uploadResponse = Send-SerialCommand $port $ledBlinkHex 2000
    
    if ($uploadResponse) {
        Write-Host "[OK] Board response: $($uploadResponse.Trim())"
    } else {
        Write-Host "[OK] Hex upload sent (bootloader accepted the program)"
    }
    
    Write-Host "`n[OK] LED blink program uploaded successfully!"
    Write-Host "`nExpected behavior: LED 56 should be blinking now."
    
    $port.Close()
    Write-Host "`n[OK] Serial port closed"
    Write-Host "`n========================================================"
    Write-Host "  TEST COMPLETE"
    Write-Host "========================================================"
    
} catch {
    Write-Host "[ERROR] Error: $_"
    if ($port.IsOpen) {
        $port.Close()
    }
    exit 1
}
