#!/bin/bash

#/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
#/opt/homebrew/bin/brew install ffmpeg
# Check if Python is installed
if ! command -v python3 &>/dev/null; then
    echo "Python not found. Installing Python..."    
    # Install Python
    /bin/bash -c "$(curl -fsSL 
https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    brew install python
fi

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

python3 -m venv venv

source venv/bin/activate

pip install flask opencv-python requests

#killall Terminal