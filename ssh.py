#!/usr/bin/env python3
"""
ssh_jump.py

SSH or SCP into a server, optionally via a jump server, using credentials
from a JSON file and Bitwarden CLI. If Bitwarden credentials are not available,
prompt for them interactively at runtime.

Requirements:
- python-dotenv
- Bitwarden CLI (`bw`)
- sshpass (for password-based SSH/SCP)
- OpenSSH client tools (ssh, scp)

Usage:
    python ssh_jump.py -c <entry_name> [-j] [-f <local_file> <remote_dest>]
    python ssh_jump.py -jc <entry_name> [-f <local_file> <remote_dest>]

Arguments:
    -c <entry_name>     Connect directly to server from JSON file.
    -j                  Use jump server ("your_jump_server" entry in JSON).
    -jc <entry_name>    Shortcut for using jump server and connecting to server.
    -f <local> <remote> Transfer file before SSH session.
"""

import os
import sys
import json
import subprocess
import getpass
from dotenv import load_dotenv

# --------------------
# Helper Functions
# --------------------

def load_servers(json_path="servers.json"):
    """Load server entries from the JSON file."""
    if not os.path.exists(json_path):
        print(f"[ERROR] Could not find {json_path}")
        sys.exit(1)
    with open(json_path, "r") as f:
        return json.load(f)

def bw_login_and_unlock():
    """Log in and unlock Bitwarden CLI using environment variables."""
    load_dotenv()
    client_id = os.getenv("BW_CLIENTID")
    client_secret = os.getenv("BW_CLIENTSECRET")
    bw_password = os.getenv("BW_PASSWORD")

    if not all([client_id, client_secret, bw_password]):
        print("[ERROR] Missing BW_CLIENTID, BW_CLIENTSECRET, or BW_PASSWORD in .env")
        sys.exit(1)

    print("[*] Logging in to Bitwarden CLI...")
    subprocess.run(["bw", "login", "--apikey"], check=True)

    print("[*] Unlocking Bitwarden vault...")
    session_key = subprocess.check_output(
        ["bw", "unlock", "--raw", "--passwordenv", "BW_PASSWORD"],
        universal_newlines=True
    ).strip()

    if not session_key:
        print("[ERROR] Failed to unlock Bitwarden vault.")
        sys.exit(1)

    return session_key

def bw_get_credentials(item_name, session_key):
    """Retrieve username and password from Bitwarden for a given item name."""
    try:
        item_json = subprocess.check_output(
            ["bw", "get", "item", item_name, "--session", session_key],
            universal_newlines=True
        )
        item = json.loads(item_json)
        username = None
        password = None

        for field in item.get("login", {}).get("uris", []):
            pass  # We don't need URIs here, only username/password

        username = item.get("login", {}).get("username")
        password = item.get("login", {}).get("password")
        return username, password
    except subprocess.CalledProcessError:
        print(f"[!] Could not fetch credentials for '{item_name}' from Bitwarden.")
        return None, None

def get_server_credentials(entry, session_key):
    """
    Resolve username and password for a given server entry.
    Uses Bitwarden if 'bitwarden-name' is provided, otherwise prompts if needed.
    """
    user = entry.get("ssh-username")
    password = None

    if "bitwarden-name" in entry:
        print(f"[*] Fetching Bitwarden credentials for '{entry['bitwarden-name']}'...")
        bw_user, bw_pass = bw_get_credentials(entry["bitwarden-name"], session_key)
        if not user and bw_user:
            user = bw_user
        if bw_pass:
            password = bw_pass

    if not password:
        password = getpass.getpass(f"Password for {user}@{entry['ssh-ip']} (leave blank for key auth): ") or None

    return user, password

# --------------------
# Main Functionality
# --------------------

def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)

    use_jump = False
    entry_name = None
    file_transfer = False
    local_file = None
    remote_dest = None

    # Parse args
    if args[0] == "-jc":
        use_jump = True
        entry_name = args[1]
        args = args[2:]
    elif args[0] == "-c":
        entry_name = args[1]
        args = args[2:]
    elif args[0] == "-j":
        use_jump = True
        entry_name = args[1]
        args = args[2:]

    if args and args[0] == "-f":
        if len(args) < 3:
            print("[ERROR] -f requires <local_file> and <remote_destination>")
            sys.exit(1)
        file_transfer = True
        local_file = args[1]
        remote_dest = args[2]

    # Load servers.json
    servers = load_servers()

    target_entry = next((e for e in servers if e["entry-name"] == entry_name), None)
    if not target_entry:
        print(f"[ERROR] No entry named '{entry_name}' found in servers.json")
        sys.exit(1)

    jump_entry = None
    if use_jump:
        jump_entry = next((e for e in servers if e["entry-name"] == "your_jump_server"), None)
        if not jump_entry:
            print("[ERROR] No jump server entry ('your_jump_server') found in servers.json")
            sys.exit(1)

    # Bitwarden login/unlock only if needed
    session_key = None
    if ("bitwarden-name" in target_entry) or (jump_entry and "bitwarden-name" in jump_entry):
        session_key = bw_login_and_unlock()

    # Get credentials
    dest_user, dest_pass = get_server_credentials(target_entry, session_key) if target_entry else (None, None)
    jump_user, jump_pass = (None, None)
    if jump_entry:
        jump_user, jump_pass = get_server_credentials(jump_entry, session_key)

    # --------------------
    # File Transfer
    # --------------------
    if file_transfer:
        print(f"[*] Starting file transfer to {entry_name}...")
        if use_jump:
            if dest_pass:
                subprocess.run([
                    "sshpass", "-p", dest_pass,
                    "scp", "-o", f"ProxyJump={jump_user}@{jump_entry['ssh-ip']}",
                    local_file, f"{dest_user}@{target_entry['ssh-ip']}:{remote_dest}"
                ], check=True)
            else:
                subprocess.run([
                    "scp", "-o", f"ProxyJump={jump_user}@{jump_entry['ssh-ip']}",
                    local_file, f"{dest_user}@{target_entry['ssh-ip']}:{remote_dest}"
                ], check=True)
        else:
            if dest_pass:
                subprocess.run([
                    "sshpass", "-p", dest_pass,
                    "scp", local_file, f"{dest_user}@{target_entry['ssh-ip']}:{remote_dest}"
                ], check=True)
            else:
                subprocess.run([
                    "scp", local_file, f"{dest_user}@{target_entry['ssh-ip']}:{remote_dest}"
                ], check=True)

    # --------------------
    # SSH Connection
    # --------------------
    print(f"[*] Connecting to {entry_name}...")
    if use_jump:
        if dest_pass:
            subprocess.run([
                "sshpass", "-p", dest_pass,
                "ssh", "-o", f"ProxyJump={jump_user}@{jump_entry['ssh-ip']}",
                f"{dest_user}@{target_entry['ssh-ip']}"
            ], check=True)
        else:
            subprocess.run([
                "ssh", "-o", f"ProxyJump={jump_user}@{jump_entry['ssh-ip']}",
                f"{dest_user}@{target_entry['ssh-ip']}"
            ], check=True)
    else:
        if dest_pass:
            subprocess.run([
                "sshpass", "-p", dest_pass,
                "ssh", f"{dest_user}@{target_entry['ssh-ip']}"
            ], check=True)
        else:
            subprocess.run([
                "ssh", f"{dest_user}@{target_entry['ssh-ip']}"
            ], check=True)

    # Lock Bitwarden vault after use
    if session_key:
        print("[*] Locking Bitwarden vault...")
        subprocess.run(["bw", "lock"], check=True)

if __name__ == "__main__":
    main()
