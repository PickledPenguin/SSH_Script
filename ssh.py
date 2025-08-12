#!/usr/bin/env python3
import json
import sys
import subprocess
import os

JSON_FILE = "./servers.json"
JUMP_ENTRY_NAME = "your_jump_server"

def bw_login_and_unlock():
    """
    Log in to Bitwarden using API key from env and unlock vault.
    Returns session key string.
    """
    client_id = os.getenv("BW_CLIENTID")
    client_secret = os.getenv("BW_CLIENTSECRET")
    if not client_id or not client_secret:
        print("Error: BW_CLIENTID and BW_CLIENTSECRET must be set in environment.")
        sys.exit(1)

    # Check login status
    try:
        status_output = subprocess.check_output(["bw", "status"], universal_newlines=True)
        status = json.loads(status_output)
        if status.get("status") == "unauthenticated":
            subprocess.run(["bw", "login", "--apikey"], check=True)
    except subprocess.CalledProcessError:
        print("Error: Could not check Bitwarden login status.")
        sys.exit(1)

    # Unlock vault
    try:
        session_key = subprocess.check_output(["bw", "unlock", "--raw"], universal_newlines=True).strip()
        return session_key
    except subprocess.CalledProcessError:
        print("Error: Failed to unlock Bitwarden vault.")
        sys.exit(1)

def bw_lock():
    """Lock Bitwarden vault after use."""
    subprocess.run(["bw", "lock"], check=False)

def get_bw_credentials(bw_name, session_key):
    """
    Retrieve username and password from Bitwarden item by name.
    Returns (username, password) or (None, None) if not found or incomplete.
    """
    try:
        output = subprocess.check_output(
            ["bw", "get", "item", bw_name, "--session", session_key],
            universal_newlines=True
        )
        item = json.loads(output)
        username = item["login"].get("username")
        password = item["login"].get("password")
        return username, password
    except subprocess.CalledProcessError:
        print(f"Warning: Could not fetch Bitwarden item '{bw_name}'. Using JSON username only.")
        return None, None

def load_servers():
    if not os.path.exists(JSON_FILE):
        print(f"Error: {JSON_FILE} not found.")
        sys.exit(1)
    with open(JSON_FILE, "r") as f:
        return json.load(f)

def find_server(servers, name):
    for s in servers:
        if s.get("entry-name") == name:
            return s
    return None

def main():
    if "-c" not in sys.argv:
        print("Usage: ssh_jump.py -c <entry-name> [-j] [-f <local_file> <remote_file>]")
        sys.exit(1)

    try:
        entry_name = sys.argv[sys.argv.index("-c") + 1]
    except IndexError:
        print("Error: -c requires an entry-name.")
        sys.exit(1)

    use_jump = "-j" in sys.argv
    file_transfer = "-f" in sys.argv

    local_file = remote_dest = None
    if file_transfer:
        try:
            f_index = sys.argv.index("-f")
            local_file = sys.argv[f_index + 1]
            remote_dest = sys.argv[f_index + 2]
        except IndexError:
            print("Error: -f requires both <local_file> and <remote_file>.")
            sys.exit(1)

    servers = load_servers()
    target = find_server(servers, entry_name)
    if not target:
        print(f"Error: No entry found with name '{entry_name}'.")
        sys.exit(1)

    # Login/unlock Bitwarden once
    session_key = bw_login_and_unlock()

    # Target server creds
    if "Bitwarden-Name" in target:
        dest_user, dest_pass = get_bw_credentials(target["Bitwarden-Name"], session_key)
        # fallback username if bw username missing
        if not dest_user:
            dest_user = target["ssh-username"]
    else:
        dest_user = target["ssh-username"]
        dest_pass = None

    dest_ip = target["ssh-ip"]

    if use_jump:
        jump = find_server(servers, JUMP_ENTRY_NAME)
        if not jump:
            print(f"Error: Jump server entry '{JUMP_ENTRY_NAME}' not found.")
            sys.exit(1)

        if "Bitwarden-Name" in jump:
            jump_user, jump_pass = get_bw_credentials(jump["Bitwarden-Name"], session_key)
            if not jump_user:
                jump_user = jump["ssh-username"]
        else:
            jump_user = jump["ssh-username"]
            jump_pass = None

        jump_ip = jump["ssh-ip"]

        if file_transfer:
            print(f"Transferring file via jump server to {entry_name}...")
            if dest_pass:
                subprocess.run([
                    "sshpass", "-p", dest_pass,
                    "scp", "-o", f"ProxyJump={jump_user}@{jump_ip}",
                    local_file, f"{dest_user}@{dest_ip}:{remote_dest}"
                ], check=True)
            else:
                subprocess.run([
                    "scp", "-J", f"{jump_user}@{jump_ip}",
                    local_file, f"{dest_user}@{dest_ip}:{remote_dest}"
                ], check=True)

        print(f"Connecting via jump server to {entry_name}...")
        if dest_pass:
            subprocess.run([
                "sshpass", "-p", dest_pass,
                "ssh", "-J", f"{jump_user}@{jump_ip}", f"{dest_user}@{dest_ip}"
            ])
        else:
            subprocess.run([
                "ssh", "-J", f"{jump_user}@{jump_ip}", f"{dest_user}@{dest_ip}"
            ])

    else:
        if file_transfer:
            print(f"Transferring file directly to {entry_name}...")
            if dest_pass:
                subprocess.run([
                    "sshpass", "-p", dest_pass,
                    "scp", local_file, f"{dest_user}@{dest_ip}:{remote_dest}"
                ], check=True)
            else:
                subprocess.run([
                    "scp", local_file, f"{dest_user}@{dest_ip}:{remote_dest}"
                ], check=True)

        print(f"Connecting directly to {entry_name}...")
        if dest_pass:
            subprocess.run([
                "sshpass", "-p", dest_pass,
                "ssh", f"{dest_user}@{dest_ip}"
            ])
        else:
            subprocess.run([
                "ssh", f"{dest_user}@{dest_ip}"
            ])

    bw_lock()

if __name__ == "__main__":
    main()
