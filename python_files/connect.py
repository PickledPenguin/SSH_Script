#!/usr/bin/env python3
# SSH_SCRIPT_TAG: connect_script_python_file
# !IMPORTANT! ^   DO NOT CHANGE

# The above SSH_SCRIPT_TAG identifies this script so that
# it can be identified irregardless of what its name is.

"""
connect.py

Connect to a specified server, optionally via a jump server, and optionally transfer/retrieve a file.
- Jump server entry name is stored in .env (JUMP_SERVER_ENTRY).
- Bitwarden CLI login credentials are stored in .env (ID, Secret, and Password)
- All server details (including jump server) are in servers.json.
- If the bitwarden name is present for a server, fetch credentials from Bitwarden CLI.
- If Bitwarden is missing credentials or not available, prompt user for credentials interactively.

Usage:
    # Connect directly
    python3 ./connect.py -c entry-name

    # Connect via Jump server
    python3 ./connect.py -jc entry-name
    OR
    python3 ./connect.py -c entry-name -j

    # Transfer file at local_path to remote_path and ssh afterward
    python3 ./connect.py -c [-j] entry-name -u local_path remote_path

    # Transfer file at remote_path to local_path
    python3 ./connect.py -c [-j] entry-name -d remote_path local_path
"""

import os
import json
import subprocess
import argparse
import argcomplete
import getpass
import re
import sys
from dotenv import load_dotenv
from utils import print_status, load_servers, load_server_names, sanitize, strip_http_prefix, strip_suffix, source_env_dict

# ---------- Load env variables ----------

SSH_SCRIPT_HOME = os.getenv("SSH_SCRIPT_HOME")

if not SSH_SCRIPT_HOME:
    print_status("SSH_SCRIPT_HOME environment variable not set. Please run setup.sh with sudo", status="error")
    sys.exit(1)

ENV_PATH = f"{SSH_SCRIPT_HOME}/.env"
# Provided to the subprocesses that we run so they have access to ENV variables
ENV_DICT = source_env_dict(ENV_PATH)

load_dotenv(dotenv_path=f"{ENV_PATH}", override=True)

# Get Bitwarden credentials from ENV
BW_PASSWORD = os.getenv("BW_PASSWORD")
BW_CLIENTID = os.getenv("BW_CLIENTID")
BW_CLIENTSECRET = os.getenv("BW_CLIENTSECRET")

# Get Jump server name from ENV
JUMP_ENTRY = os.getenv("JUMP_SERVER_ENTRY")  # Jump server entry name in servers.json

# Get the local file path for the json file storing server data from ENV
SERVERS_LOCAL_FILE = os.getenv("SERVERS_LOCAL_FILE")
# The absolute file path for the json file storing server data
SERVERS_FILE = f"{SSH_SCRIPT_HOME}/{SERVERS_LOCAL_FILE}"

# Get the key names for server data from ENV
NICKNAME = os.getenv("NICKNAME")
IP = os.getenv("IP")
USERNAME = os.getenv("USERNAME")
BW_NAME = os.getenv("BW_NAME")

# ---------- Local variables ----------

# Used to cache session key to reference throughout runtime
bw_cache = {}

# define optional flags
CONNECT_OPTS = ("-c", "--connect")
JUMP_FLAGS = ("-j", "--jump")
JUMP_CONNECT_OPTS = ("-jc","--jumpconnect") # Aliases for connect + jump
CONNECT_JUMP_OPTS = ("-cj","--connectjump") # Aliases for connect + jump
UPLOAD_OPTS = ("-u", "--upload")
DOWNLOAD_OPTS = ("-d", "--download")
PORT_OPTS = ("-p", "--port")

# ------------------- Utility Functions -------------------

def source_env(env_path) -> dict:
    """Returns a dictionary of the given ENV to provide to subprocesses."""
    env_vars = dotenv_values(env_path)
    for key, value in env_vars.items():
        if value is not None:
            os.environ[key] = value
    return dict(os.environ)

def servers_completer(prefix, parsed_args, **kwargs):
    """TAB Autocompletion, returns server names that have the given prefix"""
    return [name for name in load_server_names(SERVERS_FILE, NICKNAME) if name.lower().startswith(prefix.lower())]

def find_entry(servers, name):
    """Finds an server with the given name"""
    for s in servers:
        if s[NICKNAME] == name:
            return s
    return None

def bitwarden_fetch(item_name, session_key):
    """Fetch username and password from Bitwarden CLI."""
    if item_name in bw_cache:
        return bw_cache[item_name]

    print_status(f"Fetching credentials from Bitwarden for '{item_name}'...", status="info")
    try:
        result = subprocess.run(
            ["bw", "get", "item", f"{sanitize(item_name)}", "--session", sanitize(session_key)],
            check=True, capture_output=True, text=True, env=ENV_DICT
        )
        data = json.loads(result.stdout)
        username = data.get("login", {}).get("username")
        password = data.get("login", {}).get("password")
        bw_cache[item_name] = (username, password)

        print_status("Credentials retrieved", status="success")
        return username, password
    except subprocess.CalledProcessError:
        print_status(f"Could not fetch '{item_name}' from Bitwarden.", status="warn")
        bw_cache[item_name] = (None, None)
        return None, None

def sync_bitwarden():
    """Synchronize Bitwarden CLI to pull in any updates since last login"""
    print_status("Synchronizing Bitwarden", status="info")
    try:
        subprocess.run(["bw", "sync"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=ENV_DICT)
        print_status("Bitwarden Synchonized", status="success")
    except subprocess.CalledProcessError:
        print_status("Bitwarden could not be synced", status="error")

def ensure_bitwarden_session():
    """Login/unlock Bitwarden and return session key."""
    if not os.getenv("BW_CLIENTID") or not os.getenv("BW_CLIENTSECRET") or not os.getenv("BW_PASSWORD"):
        print_status("Missing Bitwarden credentials in .env", status="error")
        sys.exit(1)

    print_status("Checking login status", status="info")
    try:
        subprocess.run(["bw", "login", "--check"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=ENV_DICT)
        print_status("Already logged in", status="confirm")
    except subprocess.CalledProcessError:
        print_status("Logging into Bitwarden CLI...", status="info")
        subprocess.run(["bw", "login", "--apikey", "--quiet"], check=True, env=ENV_DICT)
        print_status("Logged in to Bitwarden", status="success")

    # Make sure any updates after previous login are pulled
    sync_bitwarden()

    print_status("Unlocking Bitwarden vault...", status="info")
    unlock = subprocess.run(
        ["bw", "unlock", "--raw", "--passwordenv", "BW_PASSWORD"],
        check=True, stdout=subprocess.PIPE, text=True, universal_newlines=True, env=ENV_DICT
    )
    print_status("Bitwarden vault unlocked", status="success")
    # Return the session key
    return unlock.stdout.strip()


def run_expect_scp(dest_user, dest_ip, dest_pass, local, remote, method="upload", jump_server=None, port=None):
    """Automates scp password entry using expect."""
    from_dest = f"{local}" if method=="upload" else f"{dest_user}@{dest_ip}:{remote}"
    to_dest = f"{dest_user}@{dest_ip}:{remote}" if method=="upload" else f"{local}"

    expect_script = f'''
    spawn scp {'-P ' + port if port else ''} {'-J ' + jump_server if jump_server else ''} {from_dest} {to_dest}
    expect {{
        "*yes/no*" {{
            send "yes\\r"
            exp_continue
        }}
        "*assword:*" {{
            send "{sanitize(dest_pass)}\\r"
        }}
    }}
    interact
    '''
    subprocess.run(["expect", "-c", expect_script], check=True, env=ENV_DICT)

def run_expect_ssh(dest_user, dest_ip, dest_pass, jump_server=None, port=None):
    """Automates ssh password entry using expect."""
    expect_script = f'''
    spawn ssh {'-p ' + port if port else ''} {'-J ' + jump_server if jump_server else ''} {dest_user}@{dest_ip}
    expect {{
        "*yes/no*" {{
            send "yes\\r"
            exp_continue
        }}
        "*assword:*" {{
            send "{sanitize(dest_pass)}\\r"
        }}
    }}
    interact
    '''
    subprocess.run(["expect", "-c", expect_script], check=True, env=ENV_DICT)


def build_parser():
    """Builds the parser with the given options and assigns automplete function to relevant arguments"""
    parser = argparse.ArgumentParser(description="SSH/File transfer helper")
    parser.add_argument(*CONNECT_OPTS, help="Connect directly to a server").completer = servers_completer
    parser.add_argument(*JUMP_FLAGS, action="store_true", help="Use jump server when connecting")
    parser.add_argument(*JUMP_CONNECT_OPTS, help="Connect via jump server (shortcut for -c <server> -j)").completer = servers_completer
    parser.add_argument(*CONNECT_JUMP_OPTS, help="Connect via jump server (shortcut for -c <server> -j)").completer = servers_completer
    parser.add_argument(*UPLOAD_OPTS, nargs=2, metavar=("LOCAL", "REMOTE"),
                        help="Upload file to remote")
    parser.add_argument(*DOWNLOAD_OPTS, nargs=2, metavar=("REMOTE", "LOCAL"),
                        help="Download file from remote")
    parser.add_argument(*PORT_OPTS, help="Connect via the specified port")
    argcomplete.autocomplete(parser)
    return parser


def main():
    """Main"""

    # ---------- GET PARSER AND SERVER DATA ----------

    parser = build_parser()
    args = parser.parse_args()
    # Get server information from the server file
    servers = load_servers(SERVERS_FILE)

    # ---------- PARSE ARGUMENTS ----------

    use_jump = False
    port = None

    # Target entry information
    if args.connect:
        entry_name = args.connect
    elif args.jumpconnect or args.connectjump:
        entry_name = args.jumpconnect or args.connectjump
        use_jump = True
    else:
        print_status("Must specify -c or -jc", status="error")
        sys.exit(1)

    if args.jump:
        use_jump = True

    if args.port:
        port = args.port

    # Jump server information
    jump_user = None
    jump_ip = None

    if use_jump:
        # Get jump server information
        jump_server_data = None
        if not JUMP_ENTRY or not find_entry(servers, JUMP_ENTRY):
            print_status("Jump server entry missing or invalid in .env or servers.json", status="error")
            return
        jump_server_data = find_entry(servers, JUMP_ENTRY)

        # Jump server credentials (username comes from server file, password not needed because of key auth)
        if jump_server_data:
            jump_user = jump_server_data.get(USERNAME)
            # Get jump server's IP with "https://", "http://", and/or "/App-Role/baseLogin" removed
            # in case it has been copied from Bitwarden directly or from the CRM
            jump_ip = strip_http_prefix(jump_server_data.get(IP))
            jump_ip = strip_suffix(jump_ip, '/App-Role/baseLogin')


    # ---------- GET TARGET SERVER CREDENTIALS ----------

    # Get target server
    target_server = find_entry(servers, entry_name)
    if target_server == None:
        print_status("Destination server missing or invalid in server.json", status="error")
        return

    # Get target server username
    dest_user = target_server.get(USERNAME)
    # Get target server's IP with "https://", "http://", and/or "/App-Role/baseLogin" removed
    # in case it has been copied from Bitwarden directly or from the CRM
    target_server_ip = strip_http_prefix(target_server.get(IP))
    target_server_ip = strip_suffix(target_server_ip, '/App-Role/baseLogin')

    # Target server credentials
    dest_user = target_server.get(USERNAME)
    dest_pass = None


    # ---------- GET PASSWORD FROM BITWARDEN IF POSSIBLE ----------

    # If the target server has bitwarden information, get the password from bitwarden
    session_key = None
    if BW_NAME in target_server:
        # Get session key from logging in / unlocking bitwarden
        session_key = ensure_bitwarden_session()
        if session_key:
            bw_user, bw_pass = bitwarden_fetch(target_server[BW_NAME], session_key)
            if bw_user:
                dest_user = bw_user
            if bw_pass:
                dest_pass = bw_pass
            # Lock Bitwarden after we're done
            print_status("Locking Bitwarden...", status="info")
            subprocess.run(["bw", "lock"], check=True, env=ENV_DICT)

    # ---------- FALLBACK FOR MANUAL PASSWORD ENTRY ----------

    # If we don't have a password from bitwarden, manually enter it
    if not dest_pass:
        dest_pass = getpass.getpass(f"Enter SSH password for {dest_user}@{target_server_ip}: ")


    # ------------------- EXECUTE ACTION -------------------

    if args.upload:
        local_file, remote_dest = args.upload
        print_status("Upload file requested.", status="info")

        jump = None
        if use_jump:
            print_status(f"Uploading file to {entry_name} via jump server {jump_ip}...", status="info")
            jump=f"{jump_user}@{jump_ip}"
        else:
            print_status(f"Uploading file directly to {entry_name}...", status="info")

        # SCP
        run_expect_scp(dest_user, target_server_ip, dest_pass, local_file, remote_dest, method="upload", jump_server=jump, port=port)

    if args.download:
        remote_file, local_dest = args.download
        print_status("Download file requested.", status="info")

        jump = None
        if use_jump:
            print_status(f"Downloading file from {entry_name} via jump server {jump_ip}...", status="info")
            jump=f"{jump_user}@{jump_ip}"
        else:
            print_status(f"Downloading file directly from {entry_name}...", status="info")

        # SCP
        run_expect_scp(dest_user, target_server_ip, dest_pass, local_dest, remote_file, method="download", jump_server=jump, port=port)

    # We don't want to open a SSH session if we downloaded a file, we assume the user wants to
    # stay on their machine to do whatever they need to do with the file they just downloaded
    if not args.download:
        print_status("Opening SSH session...", status="info")

        jump = None
        if use_jump:
            jump=f"{jump_user}@{jump_ip}"

        # SSH
        run_expect_ssh(dest_user, target_server_ip, dest_pass, jump_server=jump, port=port)


if __name__ == "__main__":
    main()
