# Copilot Instructions

## Repository Overview

This repository contains Propeller 2 tooling and scripts for compiling, loading, and flashing firmware from Windows. New automation should be written in Python.

## Project Structure

```
bin/              - toolchain binaries (loadp2, flexspin, etc.)
scripts/          - Python and legacy PowerShell helper scripts
```

## Building and Running Programs

### Compiling SPIN2 Code

Use `flexspin` to compile Propeller 2 SPIN2 code:

```bash
bin/flexspin.exe -2 -O2 program.spin2
```

This produces a `.binary` file ready for loading.

### Loading to RAM (Immediate Execution)

Load and run a program immediately in RAM:

```bash
bin/loadp2.exe -p COM6 program.binary
```

The program runs until power cycle or reset.

### Flashing to Persistent Storage

Use this command sequence:

```bash
bin/loadp2.exe -p COM6 -SINGLE -FLASH program.binary
```

This `-SINGLE -FLASH` path is the proven working method in this project for writing blink firmware to flash.
The plain `-FLASH` path (without `-SINGLE`) can timeout when writing the flash stub on this setup.

### Python Wrapper (CLI + GUI)

Use the wrapper script for both terminal and GUI workflows:

```bash
python scripts/p2_loader.py --binary blink.binary --mode flash --port COM6 --verbose
python scripts/p2_loader.py --binary blink.binary --mode ram --port COM6 --verbose
python scripts/p2_loader.py --gui
```

## Key Conventions

### Python Scripts

- Prefer wrapping `bin/loadp2.exe` and `bin/flexspin.exe` instead of reimplementing the serial protocol
- For flash programming, prefer `loadp2 -SINGLE -FLASH`
- GUI tools should use built-in `tkinter` unless there is a strong reason otherwise
- If `pyserial` is present, use it for COM port discovery in GUI/CLI helpers

### PowerShell Scripts (Legacy)

- PowerShell scripts use .NET Framework's `System.IO.Ports.SerialPort` class
- Should only be maintained for reference; new scripts use Python

## Adding New Scripts

When creating new hardware communication scripts in Python:
1. Use `pyserial` for serial communication
2. Auto-detect the COM port by testing all available ports with `Prop_Chk`
3. Send reset via DTR toggle before programming
4. Verify bootloader is ready before uploading programs
5. Include detailed step-by-step terminal output with status indicators
6. Always close the serial port in finally blocks
7. Use meaningful variable names and docstrings

## Testing

- No formal test framework is currently in place
- Manual testing: Connect devices via COM port and run scripts directly
- Verify serial port connectivity with `[System.IO.Ports.SerialPort]::GetPortNames()` before running scripts

## Python Development

When writing Python scripts or tools for this project:
- Use [UV](https://github.com/astral-sh/uv) for all package management and virtual environment management
- Create virtual environments with `uv venv`
- Install dependencies with `uv pip install` or define a `pyproject.toml` and use `uv sync`
- UV is fast, reliable, and handles both dependency resolution and environment isolation

## Dependencies

- PowerShell 5.0 or later (for PowerShell scripts)
- Python 3.8+ with UV (for Python scripts)
- Windows OS (uses .NET Framework System.IO.Ports for serial communication)
- Physical serial device or COM port adapter connected to the specified port
- No external package dependencies for existing scripts

## Platform Notes

This repository is currently Windows-focused due to reliance on COM port naming (`COM1`, `COM6`, etc.). Cross-platform serial communication would require changes to port naming and driver support.
