# Propeller 2 Mini IDE - Quick Start Guide

## Overview
The Propeller 2 Mini IDE is an integrated development environment that lets you write, compile, and load SPIN2 programs to your Propeller 2 board.

## Launching the IDE
```bash
python scripts/p2_loader.py
```
Or with explicit GUI flag:
```bash
python scripts/p2_loader.py --gui
```

## Workflow

### Editor Tab - Main Development Interface

All the tools you need in one place!

**Toolbar Buttons** (left to right):
- **Open**: Open a SPIN2 file
- **Save**: Save current file (also: Ctrl+S)
- `|` *separator*
- **Compile**: Compile SPIN2 to binary (auto-saves first)
- **Compile & Run**: Compile and immediately load to RAM
- `|` *separator*
- **Reset Target**: Send reset signal to Propeller 2 board
- **Load to RAM**: Load binary to RAM for testing
- **Load to FLASH**: Load binary to FLASH for persistent storage
- **Erase FLASH**: Clear FLASH memory on board

**Editor Area**:
- Full SPIN2 code editor with syntax highlighting
- Keywords (PUB, PRI, VAR, IF, etc.) in blue
- Comments (starting with ') in gray
- Strings in red
- Undo/redo support

**Output Panel**:
- Shows compilation results
- Displays errors and warnings
- Shows program size after successful compile

### Keyboard Shortcuts

- **Ctrl+S**: Save current file
- **Ctrl+O**: Open file (from File menu)

### Loader Tab - Settings & Advanced Options

For advanced configuration:
- **Binary file**: Browse for custom binary (auto-populated after compile)
- **loadp2.exe**: Path to loader tool (auto-discovered)
- **COM port**: Select port or click "Refresh" to re-detect
- **Verbose**: Enable detailed output from loadp2

## Example Workflow

### Quick Test (Compile & Run)
1. **Open** `blink_test.spin2`
2. Click **"Compile & Run"** button
   - File auto-saves
   - Compiles in background
   - Automatically loads to RAM
   - Program runs immediately on board
3. Done! ⚡

### Traditional Workflow
1. **Open** a SPIN2 file
2. **Edit** the code (see syntax highlighting)
3. **Compile** - check output for errors
4. **Load to RAM** - test on board
5. **Load to FLASH** - store permanently (if working)

### Recovery
1. If program fails: Click **Reset Target** to recover
2. If stuck: Click **Erase FLASH** to clear bad code
3. Reprogram with fresh code

## Features

### Automatic COM Port Detection
- Automatically selects the highest numbered COM port
- Prefers COM6 if available
- Click "Refresh" to re-scan ports

### Syntax Highlighting
- **Blue**: SPIN2 keywords (pub, pri, var, dat, obj, con, if, etc.)
- **Gray**: Comments (lines starting with ')
- **Red**: Quoted strings

### Compilation Output
Shows:
- Compilation status (success/failure)
- Error messages (file, line, description)
- Program size in bytes
- Binary filename

### File Tracking
- Window title shows current filename (with * if modified)
- Unsaved changes prompt on close or open
- Auto-save before compilation

## Example Workflow

### Quick Test (Compile & Run)
1. **Open** `blink_test.spin2`
2. Click **"Compile & Run"** button
   - File auto-saves
   - Compiles in background
   - Automatically loads to RAM
   - Program runs immediately on board
3. Done! ⚡

### Traditional Workflow
1. **Open** a SPIN2 file
2. **Edit** the code (see syntax highlighting)
3. **Compile** - check output for errors
4. **Load to RAM** - test on board
5. **Load to FLASH** - store permanently (if working)

### Recovery
1. If program fails: Click **Reset Target** to recover
2. If stuck: Click **Erase FLASH** to clear bad code
3. Reprogram with fresh code

## Keyboard Shortcuts
- `Ctrl+S`: Save current file
- `Ctrl+O`: Open file

## Tips

- **Fastest Workflow**: Use "Compile & Run" button for quick test-debug cycles
- **Ctrl+S**: Save frequently while editing
- **Reset Target**: Use if your program crashes or hangs
- **Always Test in RAM First**: Before using "Load to FLASH"
- **Check Compilation Output**: Look for errors before trying to load
- **COM Port Auto-Detects**: On startup, prefers COM6 if available
- **Erase Flash**: If your program won't boot after flash, erase and reprogram

## Technical Details

- **Compiler**: flexspin v7.6.6+ (bin/flexspin.exe)
- **Loader**: loadp2 (bin/loadp2.exe)
- **Default Settings**:
  - Compilation: `-2 -O2` (SPIN2, level 2 optimization)
  - Flash mode: `-SINGLE -FLASH` (proven working sequence)
  - Baud rate: 115200

## Troubleshooting

### "flexspin not found"
- Ensure `bin/flexspin.exe` exists
- Use `File → Editor → Browse flexspin` if path is wrong

### "loadp2 not found"
- Ensure `bin/loadp2.exe` exists
- Click "Browse..." in Loader tab to select manually

### Board not detected
- Click "Refresh" in Loader tab
- Check USB connection
- Try different COM port if available

### Compilation errors
- Check Output panel for error details
- Common issue: Missing P_OE in pinstart() call
- Verify SPIN2 syntax (look at examples in documentation)

### Program doesn't run after flash
- Try "Erase Flash" then reprogram
- Make sure DIP switch is set for flash boot
- Test with RAM load first
