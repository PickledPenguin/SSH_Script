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
