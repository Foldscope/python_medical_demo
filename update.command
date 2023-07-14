#!/bin/bash

# Update from github
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"
git reset --hard
git pull