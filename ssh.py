#!/usr/bin/env python3
import json
import sys
import subprocess
import os
import getpass

JSON_FILE = "./servers.json"
JUMP_ENTRY_NAME = "your_jump_server"

def bw_login_and_unlock():
    """Log in to Bitwarden if needed and unlock the vault."""
    client_id = os.getenv("BW_CLIENTID")
    client_secret = os.getenv("BW_CLIENTSECRET")
    if not client_id or not client_secret:
        print("[!] BW_CLIENTID and BW_CLIENTSECRET must be set in environment.")
        return None  # Skip Bitwarden if env vars are missing

    try:
        status_output = subprocess.check_output(["bw", "status"], universal_newlines=True)
        status = json.loads(status_output)
        if status.get("status") == "unauthenticated":
            print("[*] Logging into Bitwarden with API key...")
            subprocess.run(["bw", "login", "--apikey"], check=True)
    except subprocess.CalledProcessError:
        print("[!] Failed to check Bitwarden login status.")
        return None

    try:
        print("[*] Unlocking Bitwarden vault...")
        session_key = subprocess.check_output(
            ["bw", "unlock", "--raw", "--passwordenv", "BW_PASSWORD"],
            universal_newlines=True
        ).strip()
        return session_key
    except subprocess.CalledProcessError:
        print("[!] Failed to unlock Bitwarden vault.")
        return None

def bw_lock():
    """Lock Bitwarden vault."""
    print("[*] Locking Bitwarden vault...")
    subprocess.run(["bw", "lock"], check=False)

def get_bw_credentials(bw_name, session_key):
    """Fetch username/password from Bitwarden."""
    if not session_key:
        return None, None
    try:
        print(f"[*] Fetching credentials for '{bw_name}' from Bitwarden...")
        output = subprocess.check_output(
            ["bw", "get", "item", bw_name, "--session", session_key],
            universal_newlines=True
        )
        item = json.loads(output)
        username = item["login"].get("username")
        password = item["login"].get("password")
        if username and password:
            print("[+] Successfully fetched credentials from Bitwarden.")
        else:
            print("[!] Missing username or password in Bitwarden entry.")
        return username, password
    except subprocess.CalledProcessError:
        print(f"[!] Could not fetch Bitwarden item '{bw_name}'.")
        return None, None

def load_servers():
    if not os.path.exists(JSON_FILE):
        print(f"[!] JSON file '{JSON_FILE}' not found.")
        sys.exit(1)
    with open(JSON_FILE, "r") as f:
        return json.load(f)

def find_server(servers, name):
    for s in servers:
        if s.get("entry-name") == name:
            return s
    return None

def build_nested_command(first_user, first_ip, first_pass, nested_cmd):
    """Build SSH command to run another command from first host."""
    if first_pass:
        return ["sshpass", "-p", first_pass, "ssh", f"{first_user}@{first_ip}", nested_cmd]
    else:
        return ["ssh", f"{first_user}@{first_ip}", nested_cmd]

def main():
    # ----------------------
    # Argument parsing block
    # ----------------------
    use_jump = False
    entry_name = None

    # Support combined -jc or -cj syntax
    if any(arg.startswith("-jc") or arg.startswith("-cj") for arg in sys.argv):
        use_jump = True
        for arg in sys.argv:
            if arg.startswith("-jc") or arg.startswith("-cj"):
                try:
                    entry_name = arg[3:] if len(arg) > 3 else sys.argv[sys.argv.index(arg) + 1]
                except IndexError:
                    print("[!] -jc requires an entry-name.")
                    sys.exit(1)
                break
    else:
        if "-c" in sys.argv:
            try:
                entry_name = sys.argv[sys.argv.index("-c") + 1]
            except IndexError:
                print("[!] -c requires an entry-name.")
                sys.exit(1)
        if "-j" in sys.argv:
            use_jump = True

    if not entry_name:
        print("Usage: ssh.py [-j] -c <entry-name> [-f <local_file> <remote_file>]")
        sys.exit(1)

    file_transfer = "-f" in sys.argv
    local_file = remote_dest = None
    if file_transfer:
        try:
            f_index = sys.argv.index("-f")
            local_file = sys.argv[f_index + 1]
            remote_dest = sys.argv[f_index + 2]
        except IndexError:
            print("[!] -f requires both <local_file> and <remote_file>.")
            sys.exit(1)

    # ----------------------
    # Load server info
    # ----------------------
    servers = load_servers()
    target = find_server(servers, entry_name)
    if not target:
        print(f"[!] No entry found with name '{entry_name}'.")
        sys.exit(1)

    print("[*] Preparing to connect...")
    session_key = bw_login_and_unlock()

    # Destination credentials
    dest_user = target.get("ssh-username")
    dest_pass = None
    if "bitwarden-name" in target:
        bw_user, bw_pass = get_bw_credentials(target["bitwarden-name"], session_key)
        if bw_user: dest_user = bw_user
        if bw_pass: dest_pass = bw_pass
    if not dest_pass:
        dest_pass = getpass.getpass(f"Password for {dest_user}@{target['ssh-ip']} (leave blank for key auth): ") or None
    dest_ip = target["ssh-ip"]

    if use_jump:
        print("[*] Jump mode enabled.")
        jump = find_server(servers, JUMP_ENTRY_NAME)
        if not jump:
            print(f"[!] Jump server '{JUMP_ENTRY_NAME}' not found.")
            sys.exit(1)

        jump_user = jump.get("ssh-username")
        jump_pass = None
        if "bitwarden-name" in jump:
            bw_user, bw_pass = get_bw_credentials(jump["bitwarden-name"], session_key)
            if bw_user: jump_user = bw_user
            if bw_pass: jump_pass = bw_pass
        if not jump_pass:
            jump_pass = getpass.getpass(f"Password for {jump_user}@{jump['ssh-ip']} (leave blank for key auth): ") or None
        jump_ip = jump["ssh-ip"]

        # Decide connection method
        if not jump_pass and not dest_pass:
            print("[*] Using -J for key-based connection.")
            if file_transfer:
                subprocess.run([
                    "scp", "-J", f"{jump_user}@{jump_ip}",
                    local_file, f"{dest_user}@{dest_ip}:{remote_dest}"
                ], check=True)
            subprocess.run(["ssh", "-J", f"{jump_user}@{jump_ip}", f"{dest_user}@{dest_ip}"])
        else:
            print("[*] Using nested SSH for password-based connection.")
            if file_transfer:
                print(f"[*] Transferring file to {entry_name} via jump server...")
                if dest_pass:
                    scp_cmd = f"sshpass -p '{dest_pass}' scp {local_file} {dest_user}@{dest_ip}:{remote_dest}"
                else:
                    scp_cmd = f"scp {local_file} {dest_user}@{dest_ip}:{remote_dest}"
                subprocess.run(build_nested_command(jump_user, jump_ip, jump_pass, scp_cmd), check=True)

            print(f"[*] Connecting to {entry_name} via jump server...")
            if dest_pass:
                ssh_cmd = f"sshpass -p '{dest_pass}' ssh {dest_user}@{dest_ip}"
            else:
                ssh_cmd = f"ssh {dest_user}@{dest_ip}"
            subprocess.run(build_nested_command(jump_user, jump_ip, jump_pass, ssh_cmd))

    else:
        print("[*] Direct connection mode.")
        if file_transfer:
            print(f"[*] Transferring file to {entry_name}...")
            if dest_pass:
                subprocess.run([
                    "sshpass", "-p", dest_pass,
                    "scp", local_file, f"{dest_user}@{dest_ip}:{remote_dest}"
                ], check=True)
            else:
                subprocess.run([
                    "scp", local_file, f"{dest_user}@{dest_ip}:{remote_dest}"
                ], check=True)

        print(f"[*] Connecting directly to {entry_name}...")
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
