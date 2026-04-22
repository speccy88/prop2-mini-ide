<#
.SYNOPSIS
    Sends a serial command to a COM port and captures the response.

.DESCRIPTION
    This script demonstrates how to use PowerShell to communicate with serial devices
    (USB-to-serial adapters, microcontrollers, embedded systems, etc.) via COM ports.
    
    It leverages the .NET Framework's System.IO.Ports.SerialPort class, which is
    fully accessible from PowerShell since PowerShell can instantiate and use any
    .NET class directly.

.CONTEXT - .NET System.IO.Ports.SerialPort
    The SerialPort class is part of the .NET Framework (System.IO.Ports namespace)
    and provides full serial communication capabilities:
    - Supports traditional RS-232 serial ports and USB-to-serial devices
    - Allows configuration of baud rate, parity, data bits, stop bits
    - Provides synchronous (blocking) and asynchronous read/write operations
    - Automatically handles serial protocol handshaking and buffering
    
    Key properties:
    - PortName: COM port identifier (e.g., "COM6")
    - BaudRate: Communication speed in bits per second (e.g., 115200)
    - Parity: Error detection (None, Even, Odd, Mark, Space)
    - DataBits: Usually 8 bits per character
    - StopBits: Usually 1 stop bit
    - ReadTimeout/WriteTimeout: Milliseconds to wait before timing out

.CONTEXT - PowerShell and .NET
    PowerShell has full access to the .NET Framework, meaning you can:
    - Instantiate any .NET class with New-Object
    - Call .NET methods and properties directly
    - Use LINQ, regular expressions, file I/O, networking, etc.
    - Leverage the entire .NET ecosystem without compiling C#
    
    This makes PowerShell a powerful automation language for system administration,
    hardware communication, and integration tasks.

.PARAMETERS
    None. Edit the $command variable in the script to change what gets sent.

.EXAMPLE
    .\send-serial-command.ps1
    
    This opens COM6 at 115200 baud, sends "> Prop_Chk 0 0 0 0", waits for
    a response, displays it, and closes the port.

.NOTES
    - The script uses WriteLine() which appends a newline character
    - It waits 100ms after sending to allow the device to respond
    - It reads multiple times with small delays to capture the full response
    - Error handling closes the port if something fails
    - The device must be connected to COM6 and responding at 115200 baud
#>

# Create a SerialPort object from the .NET System.IO.Ports namespace
# This is the primary class for serial communication in .NET
$port = New-Object System.IO.Ports.SerialPort

# Configure the serial port parameters
# These must match the device's expectations, or communication will fail
$port.PortName = "COM6"              # COM port identifier
$port.BaudRate = 115200             # Speed: 115200 bits per second
$port.Parity = "None"               # No parity bit (error detection off)
$port.DataBits = 8                  # 8 data bits per character
$port.StopBits = 1                  # 1 stop bit (standard)
$port.ReadTimeout = 2000            # 2-second timeout for read operations
$port.WriteTimeout = 2000           # 2-second timeout for write operations

# Function to send a command and read response
function Send-SerialCommand {
    param(
        [System.IO.Ports.SerialPort]$SerialPort,
        [string]$Command,
        [int]$WaitMs = 500
    )
    
    Write-Host "Sending: $Command"
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
    # Open the serial port
    $port.Open()
    Write-Host "Serial port COM6 opened successfully"
    
    # Reset the board by toggling DTR (Data Terminal Ready) line
    # This is the standard way to reset Propeller boards
    Write-Host "`nSending reset signal (DTR toggle)..."
    $port.DtrEnable = $true
    Start-Sleep -Milliseconds 100
    $port.DtrEnable = $false
    Start-Sleep -Milliseconds 500
    
    # Wait for board to boot and enter programming window (60 seconds available)
    Write-Host "Board reset. Waiting for boot..."
    Start-Sleep -Milliseconds 1000
    
    # Send Prop_Chk to verify the board is responding
    Write-Host "`nVerifying board is ready with Prop_Chk..."
    $checkResponse = Send-SerialCommand $port "> Prop_Chk 0 0 0 0"
    
    if ($checkResponse) {
        Write-Host "Board responded: $checkResponse"
        Write-Host "`nBoard is ready! Proceeding with command..."
        
        # Now send the actual command (modify as needed)
        $command = "> Prop_Chk 0 0 0 0"
        $response = Send-SerialCommand $port $command
        
        Write-Host "Response received:"
        Write-Host $response
    } else {
        Write-Host "ERROR: Board did not respond to Prop_Chk"
        Write-Host "Board may still be booting or not connected. Try pressing the reset button manually."
    }
    
    # Always close the port when done
    $port.Close()
} catch {
    # If an error occurs, display it and close the port
    Write-Host "Error: $_"
    if ($port.IsOpen) {
        $port.Close()
    }
}
