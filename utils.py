import json
import os
import re

SERVERS_FILE = "servers.json"
ENV_PATH = "./.env"

# ---------- Colored Status Printing ----------
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
    print_status(f"Saved data to {file_path}", "success")


def load_servers():
    """
    Performs load_json on SERVERS_FILE
    """
    servers = load_json(SERVERS_FILE)
    if servers == {}:
        return None
    return servers

def save_servers(data):
    """
    Saves data to SERVERS_FILE
    """
    save_json(SERVERS_FILE, data)

def load_entry(identifier):
    return [s.get(identifier, "") for s in load_servers() if s.get(identifier)]

# ---------- Password / String Helpers ----------
def sanitize(input_str, prefix="\\"):
    """
    Escape characters in a password that might break shell commands (expect, etc).
    """
    if input_str is None:
        return ""
    # Escape $, `, ", \ and backslashes
    for char in ['$', '`', '"', '\\', '[', ']', '{', '}', ';', '\n', '\r']:
        input_str = input_str.replace(char, f"{prefix}{char}")
    return input_str

import re
from utils import sanitize_password  # assuming sanitize_password exists in utils.py

def sanitize_env_quotes(env_path: str) -> None:
    """
    Goes through an .env file and sanitizes any quoted values
    using sanitize(). This ensures passwords or other
    values with special characters won't break expect scripts
    or other usage.

    Example:
        PASSWORD="p@$$word!"  -> PASSWORD="p@\$\$word!"
    """
    sanitized_lines = []

    with open(ENV_PATH, "r", encoding="utf-8") as f:
        for line in f:
            raw = line.strip()

            # Skip comments and empty lines
            if not raw or raw.startswith("#"):
                sanitized_lines.append(line.rstrip())
                continue

            match = re.match(r"^([\w\-\.]+)\s*=\s*(.*)$", raw)
            if not match:
                sanitized_lines.append(line.rstrip())
                continue

            key, value = match.groups()

            # If value is quoted, sanitize inside
            if (value.startswith('"') and value.endswith('"')) or \
               (value.startswith("'") and value.endswith("'")):
                quote_char = value[0]
                inner_value = value[1:-1]

                # Sanitize the inner value
                sanitized_inner = sanitize(inner_value)

                # Re-wrap in the same type of quotes
                new_value = f"{quote_char}{sanitized_inner}{quote_char}"
                sanitized_lines.append(f"{key}={new_value}")
            else:
                sanitized_lines.append(raw)

    # Write back sanitized file
    with open(env_path, "w", encoding="utf-8") as f:
        f.write("\n".join(sanitized_lines) + "\n")

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
        choice = input(f"{question}{default_prompt}").strip().lower()
        if not choice:
            choice = default.lower()
        if choice in "yes":
            return True
        elif choice in "no":
            return False
        else:
            print_status("Please respond with yes or no (y/n).", "prompt")
