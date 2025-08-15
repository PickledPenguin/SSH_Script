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
import json
import subprocess
import argparse
import getpass
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
load_dotenv()
BW_PASSWORD = os.getenv("BW_PASSWORD")
BW_CLIENTID = os.getenv("BW_CLIENTID")
BW_CLIENTSECRET = os.getenv("BW_CLIENTSECRET")
BW_DOMAIN = os.getenv("BW_DOMAIN")
JUMP_ENTRY = os.getenv("JUMP_ENTRY")  # Jump server entry name from servers.json

SERVERS_FILE = Path("servers.json")


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

def bitwarden_fetch(item_name, session_key):
    """Fetch username and password from Bitwarden CLI (cached)."""
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


def run_expect_scp(dest_user, dest_ip, dest_pass, local_file, remote_dest, jump_server=None):
    """Automates scp password entry using expect."""
    expect_script = f'''
    spawn scp {'-o ProxyJump=' + jump_server if jump_server else ''} {local_file} {dest_user}@{dest_ip}:{remote_dest}
    expect {{
        "*yes/no*" {{
            send "yes\\r"
            exp_continue
        }}
        "*assword:*" {{
            send "{dest_pass}\\r"
        }}
    }}
    interact
    '''
    subprocess.run(["expect", "-c", expect_script], check=True)

def run_expect_ssh(dest_user, dest_ip, dest_pass, jump_server=None):
    """Automates ssh password entry using expect."""
    expect_script = f'''
    spawn ssh {'-o ProxyJump=' + jump_server if jump_server else ''} {dest_user}@{dest_ip}
    expect {{
        "*yes/no*" {{
            send "yes\\r"
            exp_continue
        }}
        "*assword:*" {{
            send "{dest_pass}\\r"
        }}
    }}
    interact
    '''
    subprocess.run(["expect", "-c", expect_script], check=True)


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

    # Get server information from servers.json
    servers = load_servers()
    
    use_jump = args.jc or args.cj
    entry_name = args.entry
    if entry_name not in servers:
        print(f"[!] Entry '{entry_name}' not found in servers.json")
        return
    
    # Get target server
    target_server = servers[entry_name]

    # Get jump server information
    jump_server_data = None
    if use_jump:
        if not JUMP_ENTRY or JUMP_ENTRY not in servers:
            print("[!] Jump server entry missing or invalid in .env or servers.json")
            return
        jump_server_data = servers[JUMP_ENTRY]

    # Jump server credentials (username comes from json, password skipped because key auth)
    jump_user = None
    jump_ip = None
    if jump_server_data:
        jump_user = jump_server_data.get("ssh-username") or jump_server_data.get("user")
        jump_ip = jump_server_data["ip"]

    # Get session key from logging in / unlocking bitwarden
    session_key = ensure_bitwarden_session()
    
    # Get target server credentials
    dest_user = target_server.get("ssh-username")
    dest_pass = None
    if "bitwarden-name" in target_server and session_key:
        bw_user, bw_pass = bitwarden_fetch(session_key, target_server["bitwarden-name"])
        if bw_user:
            dest_user = bw_user
        if bw_pass:
            dest_pass = bw_pass
    # If we don't have a password from bitwarden, manually enter it
    if not dest_pass:
        dest_pass = getpass.getpass(f"Enter SSH password for {dest_user}@{target_server['ip']}: ")


    # Lock Bitwarden if it was used
    if session_key:
        print("[*] Locking Bitwarden...")
        subprocess.run(["bw", "lock"], check=True)


    # ------------------- Execute action -------------------
    if args.f:
        local_file, remote_dest = args.f
        print("[*] File transfer requested.")

        if use_jump:
            print(f"[*] Transferring file to {entry_name} via jump server {jump_ip}...")
            run_expect_scp(dest_user, target_server["ip"], dest_pass, local_file, remote_dest,
                           jump_server=f"{jump_user}@{jump_ip}")
        else:
            print(f"[*] Transferring file directly to {entry_name}...")
            run_expect_scp(dest_user, target_server["ip"], dest_pass, local_file, remote_dest)

    print("[*] Opening SSH session...")
    if use_jump:
        run_expect_ssh(dest_user, target_server["ip"], dest_pass, jump_server=f"{jump_user}@{jump_ip}")
    else:
        run_expect_ssh(dest_user, target_server["ip"], dest_pass)


if __name__ == "__main__":
    main()
