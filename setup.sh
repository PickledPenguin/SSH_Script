#!/bin/bash
set -e


# ---------- CONSTANTS / FILENAMES ----------

# Directory to install wrapper scripts
INSTALL_DIR="$HOME/.local/bin"
# Current repo directory
REPO_DIR="$(pwd)"
# Path to the .env file
ENVPATH="$REPO_DIR/.env"
# Directory where the wrapper scripts can be found
WRAPPER_SCRIPT_DIRECTORY="$REPO_DIR/bash_scripts"

# Get an array of all wrapper scripts with the ARGCOMPLETE_SCRIPT tag
WRAPPER_SCRIPTS=()
for f in $(grep -rl "^# ARGCOMPLETE_SCRIPT" "$WRAPPER_SCRIPT_DIRECTORY"/*); do
    WRAPPER_SCRIPTS+=("$f")
done

# Const colors
RESET="\e[0m"
GREEN="\e[92m"
YELLOW="\e[93m"
RED="\e[91m"
BLUE="\e[94m"
MAGENTA="\e[95m"

# Const color mappings
declare -A COLORS
COLORS=(
        ["success"]=$GREEN
        ["info"]=$YELLOW
        ["error"]=$RED
        ["prompt"]=$MAGENTA
        ["confirm"]=$BLUE
)

# Const symbol mappings
declare -A SYMBOLS
SYMBOLS=(
        ["success"]="[+]"
        ["info"]="[*]"
        ["error"]="[!]"
        ["prompt"]="[?]"
        ["confirm"]="[✓]"
)

# ---------- MAKE DIRECTORY FOR INSTALLS ----------

mkdir -p $INSTALL_DIR

# ---------- HELPERS ----------

# Function to check command existence
check_cmd() {
    command -v "$1" >/dev/null 2>&1
}

print_status(){
    SYMBOL=${SYMBOLS[$2]}
    COLOR=${COLORS[$2]}
    echo -e "$COLOR$SYMBOL $1$RESET"
}

# ---------- CREATE SSH_SCRIPT_HOME ----------

if ! grep -q "SSH_SCRIPT_HOME" "$HOME/.bashrc"; then
    echo "export SSH_SCRIPT_HOME=\"$REPO_DIR\"" >> "$HOME/.bashrc"
    print_status "Added SSH_SCRIPT_HOME to ~/.bashrc" "success"
else
    print_status "SSH_SCRIPT_HOME already set to $SSH_SCRIPT_HOME" "confirm"
fi


# ---------- INSTALL WRAPPER SCRIPTS TO INSTALL_DIR----------

print_status "Installing wrapper scripts to $INSTALL_DIR..." "info"
for script in $(grep -rl "^# ARGCOMPLETE_SCRIPT" "$WRAPPER_SCRIPT_DIRECTORY"/*); do
    if [[ -f "$script" ]]; then
        BASENAME=$(basename "$script")
        cp "$script" "$INSTALL_DIR/"
        chmod +x "$INSTALL_DIR/$BASENAME"
        print_status "    Installed $BASENAME" "success"
    else
        echo "$script"
        echo "$BASENAME"
        print_status "$BASENAME not found in $WRAPPER_SCRIPT_DIRECTORY" "error"
    fi
done

# ---------- ADD INSTALL_DIR TO PATH ----------

if ! grep -q "export PATH=\"$INSTALL_DIR:\$PATH\"" "$HOME/.bashrc"; then
    # export for this session
    export PATH="$INSTALL_DIR:$PATH"
    # add to .bashrc for future sessions
    echo "export PATH=\"$INSTALL_DIR:\$PATH\"" >> "$HOME/.bashrc"
    print_status "Added $INSTALL_DIR to PATH in ~/.bashrc" "success"
fi

# ---------- INSTALL PYTHON-ARGCOMPLETE ----------

if ! check_cmd register-python-argcomplete; then
    print_status "Installing Python dependency: python-argcomplete..." "info"
    apt install --upgrade python3-argcomplete
else
    print_status "Python depenency python-argcomplete already installed" "confirm"
fi

# ---------- ENABLE GLOBAL ARGCOMPLETE ----------

if check_cmd activate-global-python-argcomplete; then
    # Candidate files for argcomplete
    COMPLETION_FILES=(
        "$HOME/.bash_completion"
        "$HOME/.bash_completion.d/python-argcomplete"
        "$HOME/.bash_completion.d/_python-argcomplete"
    )

    COMPLETION_FILE=""
    for f in "${COMPLETION_FILES[@]}"; do
        if [ -f "$f" ]; then
            COMPLETION_FILE="$f"
            break
        fi
    done

    if [ -z "$COMPLETION_FILE" ]; then
        print_status "Unknown completion file. Please source manually or restart your shell after setup." "error"
    else
        # Only add once
        if ! grep -q "Begin added by argcomplete" "$COMPLETION_FILE"; then
            print_status "Enabling global argcomplete..." "info"
            activate-global-python-argcomplete --user
            source "$COMPLETION_FILE"
        else
            print_status "Global argcomplete already enabled" "confirm"
        fi
    fi
else
    print_status "argcomplete not found. Please install it manually." "error"
fi

# ---------- REGISTER AUTOCOMPLETE FOR ARGCOMPLETE SCRIPTS ----------

# Register autocomplete for all scripts within WRAPPER_SCRIPT_DIRECTORY with the ARGCOMPLETE_SCRIPT tag
if check_cmd register-python-argcomplete; then
    for f in $(grep -rl "^# ARGCOMPLETE_SCRIPT" "$WRAPPER_SCRIPT_DIRECTORY"/*); do
        eval "$(register-python-argcomplete "$(basename "$f")")"

        # Add to ~/.bashrc if it isn't there already
        if ! grep -q "register-python-argcomplete $(basename "$f")" "$HOME/.bashrc"; then
            echo "eval \"\$(register-python-argcomplete $(basename "$f"))\"" >> "$HOME/.bashrc"
            print_status "register-python-argcomplete for $(basename "$f") set up in ~/.bashrc" "success"
        else
            print_status "register-python-argcomplete for $(basename "$f") already set up in ~/.bashrc" "confirm"
        fi
    done
fi

# ---------- INSTALL PYTHON-DOTENV ----------

OS_TYPE=$(uname -s)
if ! check_cmd python-dotenv; then
    print_status "Installing Python dependency: python-dotenv..." "info"
    apt install --upgrade python3-dotenv
else
    print_status "Python depenency python-dotenv already installed" "confirm"
fi

# ---------- SOURCE ENV ----------

source $ENVPATH
print_status "Sourced ENV file $ENVPATH" "success"

# ---------- INSTALL BITWARDEN CLI ----------

if ! check_cmd bw; then
    print_status "Bitwarden CLI (bw) not found. Installing..." "info"
    if [[ "$OS_TYPE" == "Linux" ]]; then
        # Check for package manager
        if check_cmd apt; then
            sudo apt update && sudo apt install -y snapd
            sudo snap install bw
        elif check_cmd dnf; then
            print_status "bw is not available via dnf/yum. Please install manually from:" "error"
            echo "    https://bitwarden.com/help/cli/"
        elif check_cmd yum; then
            print_status "bw is not available via dnf/yum. Please install manually from:" "error"
            echo "    https://bitwarden.com/help/cli/"
        else
            print_status "Unknown Linux distribution. Install Bitwarden CLI manually from:" "error"
            echo "    https://bitwarden.com/help/cli/"
        fi
    elif [[ "$OS_TYPE" == "Darwin" ]]; then
        if check_cmd brew; then
            brew install bitwarden-cli
        else
            print_status "Homebrew not found. Install it from https://brew.sh/ then run:" "error"
            echo "    brew install bitwarden-cli"
        fi
    else
        print_status "Unsupported OS. Please install Bitwarden CLI manually from:" "error"
        echo "    https://bitwarden.com/help/cli/"
    fi
else
    print_status "Bitwarden CLI already installed." "confirm"
fi

# ---------- SET BW_DOMAIN ----------

if [ -z "$BW_DOMAIN" ]; then
        print_status "BW_DOMAIN is not set in .env" "error"
        exit 1
fi
# Add https:// if BW_DOMAIN does not start with http:// or https://
if [[ "$BW_DOMAIN" =~ ^https?:// ]]; then
        SERVER_URL="$BW_DOMAIN"
else
        SERVER_URL="https://$BW_DOMAIN"
fi

print_status "Configured Bitwarden server to $SERVER_URL" "success"

# ---------- INSTALL EXPECT ----------

if ! check_cmd expect; then
    print_status "expect not found. Installing..." "info"
    if [[ "$OS_TYPE" == "Linux" ]]; then
        if check_cmd apt; then
            sudo apt update && sudo apt install -y expect
        elif check_cmd yum; then
            sudo yum install -y expect
        elif check_cmd dnf; then
            sudo dnf install -y expect
        else
            print_status "Unknown Linux distribution. Install expect manually." "error"
        fi
    elif [[ "$OS_TYPE" == "Darwin" ]]; then
        if check_cmd brew; then
            brew install expect
        else
            print_status "Homebrew not found. Install it from https://brew.sh/ then run:" "error"
            echo "    brew install expect"
        fi
    else
        print_status "Unsupported OS. Please install expect manually." "error"
    fi
else
    print_status "expect already installed." "confirm"
fi


print_status "All dependencies installed successfully." "confirm"
