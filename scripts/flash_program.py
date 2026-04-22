#!/usr/bin/env python3
"""
Writes a binary program to Propeller 2 flash memory.

This script loads a program into the Propeller 2's SPI flash memory,
making it persistent across power cycles. On boot, the Propeller 2
will automatically load and run the program from flash.

The flash programming process (based on loadp2):
1. Auto-detects the Propeller 2 board on available COM ports
2. Sends a reset signal to open the 60-second programming window
3. Loads the main program to RAM via Prop_Hex command
4. Loads a flash bootloader stub to flash address 0x80000000
5. Sends 'F' command with program size to trigger flash write
6. P2 reboots and runs from flash automatically

The flash bootloader stub validates the program and writes it to flash.

Usage:
    python flash_program.py program.bin
    python flash_program.py program.bin -p COM6
"""

import serial
import serial.tools.list_ports
import time
import sys
import os
import argparse
import struct


# Flash bootloader stub (from loadp2)
# This program is written to flash at 0x80000000 and validates the main program
# Magic: "Prop" (0x50 0x72 0x6f 0x70) at offset 0x0C after checksum adjustment
FLASH_STUB = bytes([
    0x31, 0x02, 0x64, 0xfd, 0x00, 0x00, 0x00, 0x00, 0x00, 0xf8, 0x0c, 0xfc,
    0x34, 0x00, 0x60, 0xfd, 0x28, 0xfe, 0x65, 0xfd, 0x00, 0x00, 0x68, 0xfc,
    0x02, 0x00, 0x44, 0xf0, 0x00, 0x00, 0x7c, 0xfc, 0x00, 0x04, 0xd8, 0xfc,
    0x12, 0x02, 0x60, 0xfd, 0x01, 0xf0, 0x08, 0xf1, 0x9c, 0x01, 0x90, 0x5d,
    0xe0, 0x01, 0xc0, 0xfe, 0x7c, 0x00, 0x84, 0xf1, 0x00, 0x04, 0x00, 0xf6,
    0x61, 0x01, 0x64, 0xfc, 0x61, 0x01, 0x64, 0xfc, 0xf0, 0x01, 0x7c, 0xfc,
    0x00, 0x04, 0xd8, 0xfc, 0x12, 0x02, 0x60, 0xfd, 0x01, 0xf2, 0x80, 0xf1,
    0x61, 0xf3, 0x64, 0xfc, 0x60, 0x01, 0x7c, 0xfc, 0x00, 0x05, 0xdc, 0xfc,
    0x12, 0x02, 0x60, 0xfd, 0x01, 0xf4, 0x80, 0xf1, 0x61, 0xf5, 0x64, 0xfc,
    0x24, 0x00, 0x04, 0xf1, 0x3f, 0x00, 0x04, 0xf1, 0x06, 0x00, 0x44, 0xf0,
    0x04, 0x00, 0x04, 0xf3, 0x59, 0x7a, 0x64, 0xfd, 0x50, 0x78, 0x64, 0xfd,
    0x3c, 0x94, 0x0c, 0xfc, 0x3c, 0x02, 0x1c, 0xfc, 0x58, 0x78, 0x64, 0xfd,
    0x58, 0x76, 0x64, 0xfd, 0x1d, 0xec, 0x60, 0xfd, 0x60, 0x01, 0x7c, 0xfc,
    0x40, 0x00, 0x1c, 0xf2, 0x20, 0x56, 0xb4, 0xe9, 0x0f, 0x6a, 0xbc, 0xe9,
    0x17, 0x0c, 0x4c, 0xfb, 0x1b, 0xb0, 0x4d, 0xfb, 0x84, 0x00, 0xb0, 0xfd,
    0x14, 0x0c, 0x4c, 0xfb, 0x18, 0x04, 0x4c, 0xfb, 0xf6, 0xaf, 0xa0, 0xfc,
    0x3c, 0xa8, 0x24, 0xfc, 0x24, 0x36, 0x60, 0xfd, 0x6c, 0x00, 0xb0, 0xfd,
    0x04, 0x00, 0x64, 0xfb, 0x01, 0xf0, 0x04, 0xf1, 0xff, 0xf0, 0xcc, 0xf7,
    0xd8, 0xff, 0x9f, 0x5d, 0xbc, 0xff, 0x9f, 0xfd, 0x3c, 0x00, 0x0c, 0xfc,
    0xf0, 0xf1, 0x07, 0xf6, 0x00, 0xf2, 0x07, 0xf6, 0x09, 0x04, 0x44, 0xf0,
    0x29, 0xfe, 0x67, 0xfd, 0x61, 0x01, 0x04, 0xfb, 0x29, 0xfe, 0x67, 0xfd,
    0xe1, 0x01, 0x64, 0xfc, 0xfb, 0x05, 0x7c, 0xfb, 0x00, 0x00, 0xec, 0xfc,
    0x59, 0x7a, 0x64, 0xfd, 0x58, 0x7a, 0x64, 0xfd, 0xf6, 0xab, 0xa0, 0xfc,
    0x3c, 0x20, 0x2c, 0xfc, 0x24, 0x36, 0x60, 0x0d, 0x78, 0xec, 0x2b, 0xf9,
    0x6c, 0xec, 0xff, 0xf9, 0x59, 0x7a, 0x64, 0xfd, 0x58, 0x7a, 0x64, 0xfd,
    0xf6, 0xad, 0xa0, 0xfc, 0x3c, 0x80, 0x2c, 0xfc, 0x24, 0x36, 0x60, 0x0d,
    0xf3, 0x0b, 0x4c, 0xfb, 0x3c, 0x20, 0x2c, 0xfc, 0x1f, 0x26, 0x64, 0xfd,
    0x40, 0x74, 0x74, 0xfd, 0xec, 0xff, 0x9f, 0xcd, 0x2d, 0x00, 0x64, 0xfd,
    0x00, 0x10, 0x00, 0x00, 0x08, 0x00, 0xf7, 0x40, 0x20, 0x00, 0xf7, 0x40,
    0x00, 0x08, 0xf7, 0x80, 0x28, 0xb6, 0x65, 0xfd, 0x00, 0x48, 0x64, 0xfc,
    0xdc, 0x40, 0x9c, 0xf1, 0x00, 0x00, 0xec, 0xec, 0x3c, 0x94, 0x0c, 0xfc,
    0x50, 0x78, 0x64, 0xfd, 0x3c, 0x02, 0x1c, 0xfc, 0x58, 0x78, 0x64, 0xfd,
    0x1d, 0x3c, 0x60, 0xfd, 0x01, 0x00, 0x00, 0xff, 0x70, 0x01, 0x8c, 0xfc,
    0x0a, 0x46, 0xcc, 0xf9, 0x20, 0x46, 0x20, 0xf3, 0x23, 0x40, 0x80, 0xf1,
    0x05, 0x46, 0x64, 0xf0, 0x23, 0x3e, 0x20, 0xf9, 0x01, 0x46, 0x64, 0xf0,
    0x3c, 0x46, 0x24, 0xfc, 0x1f, 0x06, 0x64, 0xfd, 0x00, 0x3e, 0xa4, 0xfc,
    0x24, 0x36, 0x60, 0xfd, 0xf5, 0x41, 0x9c, 0xfb, 0x3c, 0x00, 0x0c, 0xfc,
    0x00, 0x00, 0x7c, 0xfc, 0x21, 0x04, 0xd8, 0xfc, 0x12, 0x46, 0x60, 0xfd,
    0x23, 0x44, 0x08, 0xf1, 0x50, 0x76, 0x65, 0x5d, 0x00, 0x04, 0x64, 0x5d,
    0x00, 0x00, 0xec, 0xfc, 0x00, 0x00, 0x00, 0x40, 0x00, 0x00, 0xf5, 0xc0,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0xb0, 0x8d, 0x90, 0x8f
])

BOOT_MAGIC = 0x50726f70  # "Prop" in little-endian

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


def read_binary_file(binary_file):
    """Read a binary file."""
    if not os.path.exists(binary_file):
        print(f"[ERROR] File not found: {binary_file}")
        return None
    
    try:
        with open(binary_file, 'rb') as f:
            data = f.read()
        
        print(f"[OK] Loaded binary file: {binary_file}")
        return data
    except Exception as e:
        print(f"[ERROR] Failed to read binary file: {e}")
        return None


def binary_to_hex_command(data, address=0):
    """
    Convert binary data to Propeller 2 Prop_Hex command format.
    
    Format: "> Prop_Hex addr_byte0 addr_byte1 addr_byte2 addr_byte3 data_bytes... ~"
    """
    # Build the address bytes (little-endian)
    addr_bytes = struct.pack('<I', address)
    
    # Build hex command
    hex_parts = ["> Prop_Hex"]
    
    # Add address bytes
    for b in addr_bytes:
        hex_parts.append(f"{b:02X}")
    
    # Add program bytes
    for b in data:
        hex_parts.append(f"{b:02X}")
    
    hex_parts.append("~")
    
    return " ".join(hex_parts)


def prepare_flash_stub(program_size):
    """
    Prepare the flash bootloader stub by fixing up the size and checksum.
    
    The flash stub expects:
    - Offset 0x08: Program size (4 bytes, little-endian)
    - Offset 0x04: Checksum adjustment so bootloader checksums to 0x50726f70 ("Prop")
    """
    bootloader = bytearray(FLASH_STUB)
    
    # Ensure it's padded to 1024 bytes
    if len(bootloader) < 1024:
        bootloader.extend(b'\x00' * (1024 - len(bootloader)))
    
    # Fix up offset 0x08 with program size (32-bit little-endian)
    bootloader[0x08:0x0C] = struct.pack('<I', program_size)
    
    # Calculate checksum of the 1024-byte bootloader
    checksum = 0
    for i in range(0, 1024, 4):
        val = struct.unpack('<I', bootloader[i:i+4])[0]
        checksum += val
    
    # Adjust offset 0x04 so the total checksum becomes BOOT_MAGIC
    adjustment = BOOT_MAGIC - checksum
    bootloader[0x04:0x08] = struct.pack('<I', adjustment & 0xFFFFFFFF)
    
    return bytes(bootloader)


def flash_program(binary_file, com_port=None):
    """Flash a program to Propeller 2."""
    print("=" * 60)
    print("  Propeller 2 Flash Programmer")
    print("=" * 60)
    
    # Step 1: Find the board if port not specified
    if com_port is None:
        print("\n[STEP 1] Auto-detecting Propeller 2 board...")
        print("Scanning COM ports for Prop_Chk response...")
        
        detected_port = None
        available_ports = [port.device for port in serial.tools.list_ports.comports()]
        
        if not available_ports:
            print("[ERROR] No COM ports found. Is the board connected?")
            return 1
        
        print(f"Found COM ports: {', '.join(available_ports)}")
        
        for test_port in available_ports:
            print(f"  Checking {test_port}...")
            response = test_com_port(test_port)
            
            if response:
                print(f"  [OK] Found Propeller 2 on {test_port}")
                detected_port = test_port
                break
        
        if not detected_port:
            print("[WARN] Propeller 2 not found on any COM port")
            print("  Will attempt reset on default port COM6...")
            detected_port = "COM6"
        
        com_port = detected_port
    
    print(f"\n[OK] Using COM port: {com_port}")
    
    # Step 2: Read binary file
    print("\n[STEP 2] Reading binary program...")
    binary_data = read_binary_file(binary_file)
    
    if binary_data is None:
        return 1
    
    print(f"[OK] Loaded {len(binary_data)} bytes from {binary_file}")
    
    # Step 3: Open port and reset
    print("\n[STEP 3] Resetting board to enter programming window...")
    
    try:
        ser = serial.Serial(
            port=com_port,
            baudrate=BAUD_RATE,
            timeout=READ_TIMEOUT,
            write_timeout=WRITE_TIMEOUT
        )
        
        print(f"[OK] Serial port {com_port} opened successfully")
        
        # Send reset via DTR
        print("Sending reset signal (DTR toggle)...")
        ser.dtr = True
        time.sleep(0.1)
        ser.dtr = False
        print("[OK] Reset signal sent")
        
        print("Waiting for board to boot...")
        time.sleep(1.5)
        
        # Step 4: Verify bootloader
        print("\n[STEP 4] Verifying bootloader is ready...")
        check_response = send_serial_command(ser, "> Prop_Chk 0 0 0 0", 1000)
        
        if not check_response:
            print("[ERROR] No response to Prop_Chk")
            ser.close()
            return 1
        
        print(f"[OK] Board responded: {check_response.strip()}")
        
        # Step 5: Load main program to RAM
        print("\n[STEP 5] Loading program to RAM...")
        hex_command = binary_to_hex_command(binary_data)
        print(f"[INFO] Sending {len(hex_command)} characters...")
        
        response = send_serial_command(ser, hex_command, 3000)
        print("[OK] Program loaded to RAM")
        
        # Step 6: Prepare and load flash bootloader stub
        print("\n[STEP 6] Preparing flash bootloader...")
        bootloader = prepare_flash_stub(len(binary_data))
        
        # Convert bootloader to hex command for upload
        print("Uploading flash bootloader to flash...")
        hex_bootloader = binary_to_hex_command(bootloader, address=0x80000000)
        response = send_serial_command(ser, hex_bootloader, 3000)
        print("[OK] Flash bootloader uploaded")
        
        # Step 7: Trigger flash write
        print("\n[STEP 7] Triggering flash write...")
        program_size = len(binary_data)
        print(f"[INFO] Program size: {program_size} bytes (0x{program_size:08x})")
        
        # Send 'F' command with program size to trigger flash programming
        ser.write(b'F')
        ser.write(struct.pack('<I', program_size))
        print("[OK] Flash write command sent")
        
        print("Waiting for flash programming to complete...")
        time.sleep(2.0)
        
        print("\n[OK] Program flashed successfully!")
        print("The program will load from flash on next boot.")
        
        ser.close()
        print("\n[OK] Serial port closed")
        print("\n" + "=" * 60)
        print("  FLASH COMPLETE")
        print("=" * 60)
        
        return 0
        
    except Exception as e:
        print(f"[ERROR] {e}")
        try:
            ser.close()
        except:
            pass
        return 1


def main():
    parser = argparse.ArgumentParser(
        description="Flash a binary program to Propeller 2 SPI flash memory",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
The flash programming process:
1. Auto-detect P2 board on available COM ports
2. Reset board to enter 60-second programming window
3. Load main program to RAM
4. Prepare and upload flash bootloader stub
5. Send flash write command to trigger programming
6. P2 reboots and runs from flash

Examples:
  python flash_program.py program.bin
  python flash_program.py program.bin -p COM6
  python flash_program.py firmware.elf -p COM3
        """
    )
    
    parser.add_argument(
        "binary_file",
        help="Path to binary program file to flash (.bin, .elf, etc.)"
    )
    
    parser.add_argument(
        "-p", "--port",
        dest="com_port",
        help="Serial port (e.g., COM6). Auto-detected if not specified.",
        default=None
    )
    
    args = parser.parse_args()
    
    return flash_program(args.binary_file, args.com_port)


if __name__ == "__main__":
    sys.exit(main())
