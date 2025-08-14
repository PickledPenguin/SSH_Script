#!/usr/bin/env python3
"""
ssh_jump.py

SSH into a specified server, optionally via a jump server, and optionally transfer a file.
- Jump server entry name is stored in .env (JUMP_SERVER_ENTRY).
- Bitwarden CLI login credentials are stored in .env (ID, Secret, and Password)
- All server details (including jump server) are in servers.json.
- If "bitwarden-name" is present for a server, fetch credentials from Bitwarden CLI.sad
- If Bitwarden is missing credentials or not available, prompt user for credentials interactively.

Usage:
    # Connect directly
    ./ssh_jump.py -c entry-name
    # Connect via Jump server
    ./ssh_jump.py -jc entry-name
    # Transfer file at local_path to remote_path and ssh afterward
    ./ssh_jump.py -c entry-name -f local_path remote_path
    # Transfer file at local_path to remote_path via Jump server and ssh afterward
    ./ssh_jump.py -jc entry-name -f local_path remote_path
"""

import os
import sys
import json
import subprocess
import argparse
import getpass
from dotenv import load_dotenv

SERVERS_FILE = "servers.json"
bw_cache = {}  # cache for bitwarden fetch results


# ------------------- Utility Functions -------------------

def load_servers():
    if os.path.exists(SERVERS_FILE):
        with open(SERVERS_FILE, "r") as f:
            return json.load(f)
    print(f"[ERROR] {SERVERS_FILE} not found.")
    sys.exit(1)


def find_entry(servers, name):
    for s in servers:
        if s["entry-name"] == name:
            return s
    return None


def bitwarden_fetch(item_name):
    """Fetch username & password from Bitwarden CLI (cached)."""
    if item_name in bw_cache:
        return bw_cache[item_name]

    print(f"[*] Fetching credentials from Bitwarden for '{item_name}'...")
    try:
        result = subprocess.run(
            ["bw", "get", "item", item_name],
            check=True, capture_output=True, text=True
        )
        data = json.loads(result.stdout)
        username = data.get("login", {}).get("username")
        password = data.get("login", {}).get("password")
        bw_cache[item_name] = (username, password)
        return username, password
    except subprocess.CalledProcessError:
        print(f"[WARNING] Could not fetch '{item_name}' from Bitwarden.")
        bw_cache[item_name] = (None, None)
        return None, None


def ensure_bitwarden_session():
    """Login/unlock Bitwarden and return session key."""
    if not os.getenv("BW_CLIENTID") or not os.getenv("BW_CLIENTSECRET") or not os.getenv("BW_PASSWORD"):
        print("[ERROR] Missing Bitwarden credentials in .env")
        sys.exit(1)

    print("[*] Logging into Bitwarden CLI...")
    subprocess.run(["bw", "login", "--apikey"], check=True)

    print("[*] Unlocking Bitwarden vault...")
    unlock = subprocess.run(
        ["bw", "unlock", "--raw", "--passwordenv", "BW_PASSWORD"],
        check=True, capture_output=True, text=True, universal_newlines=True
    )
    return unlock.stdout.strip()


# ------------------- Main Script -------------------

def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="SSH/SCP into servers via optional jump server.")
    parser.add_argument("-c", "--connect", help="Entry name to connect to directly.")
    parser.add_argument("-jc", "--jumpconnect", help="Entry name to connect to via jump server.")
    parser.add_argument("-cj", "--connectjump", help="Entry name to connect to via jump server.")
    parser.add_argument("-f", "--file", nargs=2, metavar=("LOCAL", "REMOTE"),
                        help="Transfer file before connecting (used with -jc or -c)")
    args = parser.parse_args()

    servers = load_servers()

    # Determine target entry & jump usage
    if args.connect:
        target_name = args.connect
        use_jump = False
    elif args.jumpconnect or args.connectjump:
        target_name = args.jumpconnect or args.connectjump
        use_jump = True
    else:
        print("[ERROR] Must specify -c, -jc, or -cj")
        sys.exit(1)

    target_entry = find_entry(servers, target_name)
    if not target_entry:
        print(f"[ERROR] No server entry found for '{target_name}'")
        sys.exit(1)

    jump_entry = None
    if use_jump:
        jump_name = os.getenv("JUMP_SERVER_ENTRY")
        if not jump_name:
            print("[ERROR] No JUMP_SERVER_ENTRY in .env")
            sys.exit(1)
        jump_entry = find_entry(servers, jump_name)
        if not jump_entry:
            print(f"[ERROR] Jump server entry '{jump_name}' not found in {SERVERS_FILE}")
            sys.exit(1)

    # Start Bitwarden session if needed
    session_key = None
    if ("bitwarden-name" in target_entry) or (jump_entry and "bitwarden-name" in jump_entry):
        session_key = ensure_bitwarden_session()

    # Fetch target server credentials
    if "ssh-username" in target_entry:
        dest_user = target_entry["ssh-username"]
    elif "bitwarden-name" in target_entry:
        u, _ = bitwarden_fetch(target_entry["bitwarden-name"])
        dest_user = u or input(f"Username for {target_name}: ")
    else:
        dest_user = input(f"Username for {target_name}: ")

    if "bitwarden-name" in target_entry:
        _, p = bitwarden_fetch(target_entry["bitwarden-name"])
        dest_pass = p or getpass.getpass(f"Password for {dest_user}@{target_entry['ssh-ip']}: ")
    else:
        dest_pass = getpass.getpass(f"Password for {dest_user}@{target_entry['ssh-ip']}: ")

    # Fetch jump server credentials if applicable
    if jump_entry:
        if "ssh-username" in jump_entry:
            jump_user = jump_entry["ssh-username"]
        elif "bitwarden-name" in jump_entry:
            u, _ = bitwarden_fetch(jump_entry["bitwarden-name"])
            jump_user = u or input(f"Username for jump server {jump_entry['entry-name']}: ")
        else:
            jump_user = input(f"Username for jump server {jump_entry['entry-name']}: ")

        if "bitwarden-name" in jump_entry:
            _, p = bitwarden_fetch(jump_entry["bitwarden-name"])
            jump_pass = p or getpass.getpass(f"Password for {jump_user}@{jump_entry['ssh-ip']}: ")
        else:
            jump_pass = getpass.getpass(f"Password for {jump_user}@{jump_entry['ssh-ip']}: ")

    # ------------------- Execute action -------------------
    if args.file:
        local_file, remote_path = args.file
        print(f"[*] Transferring {local_file} to {target_name} via jump server...")
        subprocess.run([
            "sshpass", "-p", dest_pass,
            "scp", "-o", f"ProxyJump={jump_user}@{jump_entry['ssh-ip']}",
            local_file, f"{dest_user}@{target_entry['ssh-ip']}:{remote_path}"
        ], check=True)

        print(f"[*] Now connecting to {target_name} via jump server...")
        subprocess.run([
            "sshpass", "-p", dest_pass,
            "ssh", "-o", f"ProxyJump={jump_user}@{jump_entry['ssh-ip']}",
            f"{dest_user}@{target_entry['ssh-ip']}"
        ], check=True)

    else:
        if use_jump:
            print(f"[*] Connecting to {target_name} via jump server {jump_entry['entry-name']}...")
            subprocess.run([
                "sshpass", "-p", dest_pass,
                "ssh", "-o", f"ProxyJump={jump_user}@{jump_entry['ssh-ip']}",
                f"{dest_user}@{target_entry['ssh-ip']}"
            ], check=True)
        else:
            print(f"[*] Connecting directly to {target_name}...")
            subprocess.run([
                "sshpass", "-p", dest_pass,
                "ssh", f"{dest_user}@{target_entry['ssh-ip']}"
            ], check=True)

    # Lock Bitwarden if it was used
    if session_key:
        print("[*] Locking Bitwarden...")
        subprocess.run(["bw", "lock"], check=True)


if __name__ == "__main__":
    main()
