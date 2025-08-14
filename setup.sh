#!/bin/bash
set -e

echo "[*] Installing Python dependency: python-dotenv..."
pip3 install --upgrade python-dotenv

# Function to check command existence
check_cmd() {
    command -v "$1" >/dev/null 2>&1
}

# Detect OS type
OS_TYPE=$(uname -s)

# Install Bitwarden CLI if missing
if ! check_cmd bw; then
    echo "[*] Bitwarden CLI (bw) not found. Installing..."
    if [[ "$OS_TYPE" == "Linux" ]]; then
        # Check for package manager
        if check_cmd apt; then
            sudo apt update && sudo apt install -y snapd
            sudo snap install bw
        elif check_cmd dnf; then
            echo "[!] bw is not available via dnf/yum. Please install manually from:"
            echo "    https://bitwarden.com/help/cli/"
        elif check_cmd yum; then
            echo "[!] bw is not available via dnf/yum. Please install manually from:"
            echo "    https://bitwarden.com/help/cli/"
        else
            echo "[!] Unknown Linux distribution. Install Bitwarden CLI manually from:"
            echo "    https://bitwarden.com/help/cli/"
        fi
    elif [[ "$OS_TYPE" == "Darwin" ]]; then
        if check_cmd brew; then
            brew install bitwarden-cli
        else
            echo "[!] Homebrew not found. Install it from https://brew.sh/ then run:"
            echo "    brew install bitwarden-cli"
        fi
    else
        echo "[!] Unsupported OS. Please install Bitwarden CLI manually from:"
        echo "    https://bitwarden.com/help/cli/"
    fi
else
    echo "[*] Bitwarden CLI already installed."
fi

# Install sshpass if missing
if ! check_cmd sshpass; then
    echo "[*] sshpass not found. Installing..."
    if [[ "$OS_TYPE" == "Linux" ]]; then
        if check_cmd apt; then
            sudo apt update && sudo apt install -y sshpass
        elif check_cmd dnf; then
            sudo dnf install -y sshpass
        elif check_cmd yum; then
            sudo yum install -y sshpass
        else
            echo "[!] Unknown Linux distribution. Install sshpass manually."
        fi
    elif [[ "$OS_TYPE" == "Darwin" ]]; then
        if check_cmd brew; then
            brew install hudochenkov/sshpass/sshpass
        else
            echo "[!] Homebrew not found. Install it from https://brew.sh/ then run:"
            echo "    brew install hudochenkov/sshpass/sshpass"
        fi
    else
        echo "[!] Unsupported OS. Please install sshpass manually."
    fi
else
    echo "[*] sshpass already installed."
fi

echo "[*] All dependencies installed successfully."
