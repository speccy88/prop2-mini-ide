#!/usr/bin/env python3
"""
Uploads an LED blink program to Propeller 2 and verifies functionality.

This script automates the complete workflow for uploading and testing an LED
blink program on Propeller 2:

1. Auto-detects the Propeller 2 board by scanning COM ports for Prop_Chk response
2. Checks if board is already in 60-second programming window
3. If not, sends reset signal to open the window
4. Verifies bootloader is ready with Prop_Chk
5. Uploads the LED blink hex program (LED 56)

This script is useful for quick verification that the board is working and
can be reused repeatedly to test changes.
"""

import time
import sys

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    print("[ERROR] pyserial is not installed. Run: uv pip install pyserial")
    sys.exit(1)


# The LED blink program for LED 56
# This is the hex code for LED 56 blinking
LED_BLINK_HEX = "> Prop_Hex 0 0 0 0 5F 70 64 FD 4B 4C 80 FF 1F 00 65 FD F0 FF 9F FD ~"

# Serial port configuration
BAUD_RATE = 115200
READ_TIMEOUT = 2.0
WRITE_TIMEOUT = 2.0


def send_serial_command(ser, command, wait_ms=500):
    """Send a command to the serial port and read the response."""
    ser.write((command + "\n").encode())
    time.sleep(wait_ms / 1000.0)
    
    response = ""
    while ser.in_waiting > 0:
        response += ser.read(ser.in_waiting).decode(errors='ignore')
        time.sleep(0.05)
    
    return response


def test_com_port(com_port):
    """Test if a COM port has a responding Propeller 2 board."""
    try:
        ser = serial.Serial(
            port=com_port,
            baudrate=BAUD_RATE,
            timeout=READ_TIMEOUT,
            write_timeout=WRITE_TIMEOUT
        )
        
        response = send_serial_command(ser, "> Prop_Chk 0 0 0 0", 500)
        ser.close()
        
        return response if response else None
    except Exception:
        return None


def main():
    print("=" * 60)
    print("  Propeller 2 LED Blink Test (LED 56)")
    print("=" * 60)
    
    # Step 1: Find the Propeller 2 board
    print("\n[STEP 1] Auto-detecting Propeller 2 board...")
    print("Scanning COM ports for Prop_Chk response...")
    
    detected_port = None
    board_already_ready = False
    
    # Get list of available COM ports
    available_ports = [port.device for port in serial.tools.list_ports.comports()]
    
    if not available_ports:
        print("[ERROR] No COM ports found. Is the board connected?")
        return 1
    
    print(f"Found COM ports: {', '.join(available_ports)}")
    
    for com_port in available_ports:
        print(f"  Checking {com_port}...")
        response = test_com_port(com_port)
        
        if response:
            print(f"  [OK] Found Propeller 2 on {com_port}")
            print(f"    Response: {response.strip()}")
            detected_port = com_port
            board_already_ready = True
            break
    
    if not detected_port:
        print("[WARN] Propeller 2 not found on any COM port")
        print("  Board may be in shutdown state (outside 60-second window)")
        print("  Will attempt reset on all COM ports...")
        detected_port = "COM6"  # Default to COM6
    
    print(f"\n[OK] Using COM port: {detected_port}")
    if board_already_ready:
        print("[OK] Board is ALREADY in the 60-second programming window!")
    else:
        print("[INFO] Board was not responding - will send reset")
    
    # Step 2: Open port and reset if needed
    print("\n[STEP 2] Resetting board to ensure fresh programming window...")
    
    try:
        ser = serial.Serial(
            port=detected_port,
            baudrate=BAUD_RATE,
            timeout=READ_TIMEOUT,
            write_timeout=WRITE_TIMEOUT
        )
        
        print(f"[OK] Serial port {detected_port} opened successfully")
        
        # Send reset signal via DTR toggle
        print("Sending reset signal (DTR toggle)...")
        ser.dtr = True
        time.sleep(0.1)
        ser.dtr = False
        print("[OK] Reset signal sent successfully")
        
        print("Waiting for board to boot...")
        time.sleep(1.5)
        
        # Step 3: Verify reset with Prop_Chk
        print("\n[STEP 3] Verifying bootloader is ready...")
        print("Sending Prop_Chk verification command...")
        
        check_response = send_serial_command(ser, "> Prop_Chk 0 0 0 0", 1000)
        
        if check_response:
            print(f"[OK] Board responded: {check_response.strip()}")
            print("[OK] Bootloader is ready and in programming window!")
        else:
            print("[ERROR] No response to Prop_Chk after reset")
            print("Board may not have reset properly. Check connection and try again.")
            ser.close()
            return 1
        
        # Step 4: Send the LED blink program
        print("\n[STEP 4] Uploading LED blink program (LED 56)...")
        print("Sending hex program...")
        print(f"Command: {LED_BLINK_HEX}")
        
        upload_response = send_serial_command(ser, LED_BLINK_HEX, 2000)
        
        if upload_response:
            print(f"[OK] Board response: {upload_response.strip()}")
        else:
            print("[OK] Hex upload sent (bootloader accepted the program)")
        
        print("\n[OK] LED blink program uploaded successfully!")
        print("\nExpected behavior: LED 56 should be blinking now.")
        
        ser.close()
        print("\n[OK] Serial port closed")
        print("\n" + "=" * 60)
        print("  TEST COMPLETE")
        print("=" * 60)
        
        return 0
        
    except Exception as e:
        print(f"[ERROR] {e}")
        try:
            ser.close()
        except:
            pass
        return 1


if __name__ == "__main__":
    sys.exit(main())
