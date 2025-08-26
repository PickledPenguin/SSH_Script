

# Directory to install wrapper scripts
INSTALL_DIR="$HOME/bin"

# Ensure the directory exists
mkdir -p "$INSTALL_DIR"

# List of wrapper scripts (Python scripts with no extension or with .py wrapper)
WRAPPER_SCRIPTS=("connect" "manage_servers" "ssh" "add_server")

echo "[+] Installing wrapper scripts to $INSTALL_DIR..."

for script in "${WRAPPER_SCRIPTS[@]}"; do
    if [[ -f "./$script" ]]; then
        cp "./$script" "$INSTALL_DIR/"
        chmod +x "$INSTALL_DIR/$script"
        echo "    Installed $script"
    else
        echo "[!] Warning: $script not found in current directory"
    fi
done

# Add INSTALL_DIR to PATH if not already
if ! echo "$PATH" | grep -q "$INSTALL_DIR"; then
    echo "export PATH=\"$INSTALL_DIR:\$PATH\"" >> "$HOME/.bashrc"
    echo "[+] Added $INSTALL_DIR to PATH in ~/.bashrc"
fi

# Enable global argcomplete
if command -v activate-global-python-argcomplete >/dev/null 2>&1; then
    echo "[+] Enabling global argcomplete..."
    activate-global-python-argcomplete --user
else
    echo "[!] argcomplete not found. Please install it: pip install argcomplete"
fi



if [ -f .env ]; then
        export $(grep -v '^#' .env | xargs)
fi

# Check if BW_DOMAIN is set
if [ -z "$BW_DOMAIN" ]; then
        echo "[!] BW_DOMAIN is not set in .env"
        exit 1
fi

# Add https:// if BW_DOMAIN does not start with http:// or https://
if [[ "$BW_DOMAIN" =~ ^https?:// ]]; then
        SERVER_URL="$BW_DOMAIN"
else
        SERVER_URL="https://$BW_DOMAIN"
fi

echo "[*] Configuring Bitwarden server to $SERVER_URL"

# Install expect if missing
if ! check_cmd expect; then
    echo "[*] expect not found. Installing..."
    if [[ "$OS_TYPE" == "Linux" ]]; then
        if check_cmd apt; then
            sudo apt update && sudo apt install -y expect
        elif check_cmd yum; then
            sudo yum install -y expect
        elif check_cmd dnf; then
            sudo dnf install -y expect
        else
            echo "[!] Unknown Linux distribution. Install expect manually."
        fi
    elif [[ "$OS_TYPE" == "Darwin" ]]; then
        if check_cmd brew; then
            brew install expect
        else
            echo "[!] Homebrew not found. Install it from https://brew.sh/ then run:"
            echo "    brew install expect"
        fi
    else
        echo "[!] Unsupported OS. Please install expect manually."
    fi
else
    echo "[*] expect already installed."
fi


echo "[*] All dependencies installed successfully."
