import json
import os

# ======= Colored Status Printing =======
RESET = "\033[0m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"

def print_status(message, status="info"):
    """
    Print a colored status message.
    status: "success", "info", "error", "debug", "prompt"
    """
    colors = {
        "success": GREEN,
        "info": YELLOW,
        "error": RED,
        "debug": BLUE,
        "prompt": MAGENTA
    }
    symbols = {
        "success": "[+]",
        "info": "[*]",
        "error": "[!]",
        "debug": "[#]",
        "prompt": "[?]"
    }
    color = colors.get(status, YELLOW)
    symbol = symbols.get(status, "[*]")
    print(f"{color}{symbol} {message}{RESET}")

# ======= JSON Helpers =======
def load_json(file_path):
    """
    Load JSON data from a file. Returns {} if file does not exist.
    """
    if not os.path.isfile(file_path):
        return {}
    with open(file_path, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            print_status(f"Failed to decode JSON file: {file_path}", "error")
            return {}

def save_json(file_path, data):
    """
    Save data (dict/list) to JSON file.
    """
    with open(file_path, "w") as f:
        json.dump(data, f, indent=4)
    print_status(f"Saved data to {file_path}", "success")

# ======= Password / String Helpers =======
def sanitize_password(password):
    """
    Escape characters in a password that might break shell commands (expect, etc).
    """
    if password is None:
        return ""
    # Escape $, `, ", \ and backslashes
    for char in ['$', '`', '"', '\\']:
        password = password.replace(char, f"\\{char}")
    return password

def strip_http_prefix(url):
    """
    Remove http:// or https:// from a URL if present
    """
    if url.startswith("http://"):
        return url[len("http://"):]
    elif url.startswith("https://"):
        return url[len("https://"):]
    return url

# ======= Other Utilities =======
def prompt_yes_no(question, default="no"):
    """
    Ask a yes/no question in terminal.
    Returns True for yes, False for no.
    """
    yes = {"yes", "y"}
    no = {"no", "n"}
    default_prompt = " [y/N] " if default.lower() in ["no", "n"] else " [Y/n] "
    while True:
        choice = input(f"{question}{default_prompt}").strip().lower()
        if not choice:
            choice = default.lower()
        if choice in yes:
            return True
        elif choice in no:
            return False
        else:
            print_status("Please respond with yes or no (y/n).", "prompt")
