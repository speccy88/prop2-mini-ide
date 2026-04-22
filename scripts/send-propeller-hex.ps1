<#
.SYNOPSIS
    Uploads a hex program to a Propeller 2 board via serial connection.

.DESCRIPTION
    This script handles the complete workflow for uploading compiled hex programs
    to a Propeller 2 microcontroller over a serial connection (COM port).
    
    The Propeller 2 has a 60-second programming window after startup. If the board
    is in shutdown state, this script automatically sends a reset signal via the
    DTR (Data Terminal Ready) line to restart the boot sequence and re-open the
    programming window.

.CONTEXT - Propeller 2 Programming
    The Propeller 2 bootloader listens on the serial port for a limited time after
    power-on or reset. Commands include:
    - Prop_Chk: Verify bootloader is ready (returns "Prop_Ver G")
    - Prop_Hex: Upload hex program data to RAM/ROM
    
    The DTR line toggle is the standard way to trigger a software reset without
    physical button press.

.PARAMETERS
    None. Edit the hex data and port settings below to customize.

.EXAMPLE
    .\send-propeller-hex.ps1
    
    Resets the P2 board, verifies it's ready, then uploads the hex program.

.NOTES
    - Requires the board to be connected to COM6 at 115200 baud
    - The 60-second programming window resets after DTR toggle
    - If upload fails, press the physical reset button and try again
    - The hex data format matches the bootloader's Prop_Hex command
#>

# Serial port configuration
$portName = "COM6"
$baudRate = 115200
$readTimeout = 2000
$writeTimeout = 2000

# Hex program to upload
# Format: "> Prop_Hex <hex_bytes_space_separated> ~"
# This is a sample program - replace with your actual hex data
$hexProgram = "> Prop_Hex 0 0 0 0 5F 70 64 FD 4B 4C 80 FF 1F 00 65 FD F0 FF 9F FD ~"

# Create and configure the SerialPort object
$port = New-Object System.IO.Ports.SerialPort
$port.PortName = $portName
$port.BaudRate = $baudRate
$port.Parity = "None"
$port.DataBits = 8
$port.StopBits = 1
$port.ReadTimeout = $readTimeout
$port.WriteTimeout = $writeTimeout

# Helper function to send a command and read the response
function Send-SerialCommand {
    param(
        [System.IO.Ports.SerialPort]$SerialPort,
        [string]$Command,
        [int]$WaitMs = 500
    )
    
    Write-Host ">>> $Command"
    $SerialPort.WriteLine($Command)
    
    Start-Sleep -Milliseconds $WaitMs
    
    $response = ""
    while ($SerialPort.BytesToRead -gt 0) {
        $response += $SerialPort.ReadExisting()
        Start-Sleep -Milliseconds 50
    }
    
    return $response
}

try {
    # Open the serial port connection to the Propeller 2
    $port.Open()
    Write-Host "✓ Serial port $portName opened at $baudRate baud"
    
    # Reset the Propeller 2 board using DTR line toggle
    # DTR (Data Terminal Ready) is used as a reset signal by the bootloader
    Write-Host "`n--- Resetting Propeller 2 ---"
    $port.DtrEnable = $true
    Start-Sleep -Milliseconds 100
    $port.DtrEnable = $false
    Write-Host "✓ Reset signal sent (DTR toggled)"
    
    # Wait for the board to boot and enter programming window
    # The 60-second programming window opens after reset
    Write-Host "✓ Waiting for board to boot..."
    Start-Sleep -Milliseconds 1500
    
    # Verify the bootloader is ready and responding
    Write-Host "`n--- Verifying Board ---"
    $checkResponse = Send-SerialCommand $port "> Prop_Chk 0 0 0 0" 1000
    
    if ($checkResponse) {
        Write-Host "✓ Board responded: $checkResponse"
        Write-Host "✓ Bootloader is ready!"
        
        # Send the hex program to the board
        Write-Host "`n--- Uploading Hex Program ---"
        $uploadResponse = Send-SerialCommand $port $hexProgram 2000
        
        if ($uploadResponse) {
            Write-Host "✓ Board response: $uploadResponse"
        } else {
            Write-Host "✓ Hex upload sent (no response expected)"
        }
        
        Write-Host "`n✓ Upload complete!"
        
    } else {
        Write-Host "✗ ERROR: Board did not respond to Prop_Chk"
        Write-Host "  Possible causes:"
        Write-Host "  - Board is not connected to $portName"
        Write-Host "  - Board is in shutdown state (60-second window expired)"
        Write-Host "  - Baud rate mismatch (check it's 115200)"
        Write-Host "`nSolution: Press the physical RESET button on the board and try again."
    }
    
    $port.Close()
    Write-Host "`n✓ Serial port closed"
    
} catch {
    Write-Host "✗ Error: $_"
    if ($port.IsOpen) {
        $port.Close()
    }
    exit 1
}
