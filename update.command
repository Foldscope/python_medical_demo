#!/bin/bash

# Install python (and brew if needed)
if ! command -v python3 &> /dev/null; then
    if ! command -v brew &> /dev/null; then
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    fi
    brew install python
fi

# Verify installation
if ! command -v python3 &> /dev/null; then
    echo "Python installation failed. Please check your system."
    exit 1
fi

# Create venv if necessary and install requirements
if [ ! -d "venv" ]; then
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

# Update from github
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"
git pull

if [ $? -eq 0 ]; then
    echo "Updates found."
    pip install -r requirements.txt
fi

# Run the demo
python3 main.py
wait