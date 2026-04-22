#!/bin/bash
# Propeller 2 Mini IDE Launcher

# Check if running from the correct directory
if [ ! -f "scripts/p2_loader.py" ]; then
    echo "Error: Please run this from the test_copilot directory"
    exit 1
fi

# Launch the IDE
./.venv/Scripts/python scripts/p2_loader.py
