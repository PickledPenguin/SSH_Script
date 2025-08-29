import json
import os
import re
from dotenv import dotenv_values

ENV_PATH = ""

# ---------- Colored Status Printing ----------
RESET = "\033[0m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"

colors = {
    "success": GREEN,
    "info": YELLOW,
    "error": RED,
    "confirm": BLUE,
    "prompt": MAGENTA
}
symbols = {
    "success": "[+]",
    "info": "[*]",
    "error": "[!]",
    "confirm": "[✓]",
    "prompt": "[?]"
}

def print_status(message, status="info"):
    """
    Print a colored status message.
    status: "success", "info", "error", "debug", "prompt"
    """
    color = colors.get(status, YELLOW)
    symbol = symbols.get(status, "[*]")
    print(f"{color}{symbol} {message}{RESET}")

# ---------- ENV Helpers ----------

def source_env_dict(env_path) -> dict:

    env_vars = dotenv_values(env_path)

    for key, value in env_vars.items():
        if value is not None:
            os.environ[key] = value

    return dict(os.environ)

# ---------- JSON Helpers ----------
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

def load_servers(servers_file):
    """
    Performs load_json on servers_file
    """
    servers = load_json(servers_file)
    if servers == {}:
        return None
    return servers

def save_servers(servers_file, data):
    """
    Saves data to servers_file
    """
    save_json(servers_file, data)

def load_entry(identifier):
    return [s.get(identifier, "") for s in load_servers() if s.get(identifier)]

def load_server_names(servers_file, identifier):
    servers = load_servers(servers_file)
    return [srv.get(identifier, "") for srv in servers if identifier in srv]

# ---------- Password / String Helpers ----------
def sanitize(input_str):
    """
    Escape characters in a password that might break shell commands (expect, etc).
    """
    if input_str is None:
        return ""
    # Escape $, `, ", etc.
    for char in ['$', '`', '"', '[', ']', '{', '}', ';', '\n', '\r']:
        pattern = rf'(?<!\\){re.escape(char)}'
        replacement = rf'\{char}'
        input_str = re.sub(pattern, replacement, input_str)
    return input_str

def strip_http_prefix(url):
    """
    Remove http:// or https:// from a URL if present
    """
    if url.startswith("http://"):
        return url[len("http://"):]
    elif url.startswith("https://"):
        return url[len("https://"):]
    return url

def strip_suffix(input_str, suffix):
    """
    Remove a given suffix from a string if present
    """
    if input_str.endswith(suffix):
        return input_str[:-len(suffix)]
    return input_str


# ---------- Other Utilities ----------
def prompt_yes_no(question, default="no"):
    """
    Ask a yes/no question in terminal.
    Returns True for yes, False for no.
    """
    yes = {"yes", "y"}
    no = {"no", "n"}
    default_prompt = " [y/N] " if default.lower() in ["no", "n"] else " [Y/n] "
    while True:
        color = colors.get("prompt", MAGENTA)
        symbol = symbols.get("prompt", "[?]")

        choice = input(f"{color}{symbol} {question}{default_prompt}{RESET}").strip().lower()
        if not choice:
            choice = default.lower()
        if choice in "yes":
            return True
        elif choice in "no":
            return False
        else:
            print_status("Please respond with yes or no (y/n).", "prompt")
