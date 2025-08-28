#!/usr/bin/env python3
# SSH_SCRIPT_TAG: manage_servers_script_python_file
# !IMPORTANT! ^   DO NOT CHANGE

# The above SSH_SCRIPT_TAG identifies this script so that
# it can be run irregardless of what its name is.

import argparse
import argcomplete
import json
import os
import sys
from dotenv import load_dotenv
from utils import *

# ---------- Load env variables ----------

SSH_SCRIPT_HOME = os.getenv("SSH_SCRIPT_HOME")

if not SSH_SCRIPT_HOME:
    print_status("SSH_SCRIPT_HOME environment variable not set. Please run setup.sh", status="error")
    sys.exit(1)

ENV_PATH = f"{SSH_SCRIPT_HOME}/.env"

load_dotenv(dotenv_path=f"{ENV_PATH}", override=True)

SERVERS_LOCAL_FILE = os.getenv("SERVERS_LOCAL_FILE")
SERVERS_FILE = f"{SSH_SCRIPT_HOME}/{SERVERS_LOCAL_FILE}"

NICKNAME = os.getenv("NICKNAME")
IP = os.getenv("IP")
USERNAME = os.getenv("USERNAME")
BW_NAME = os.getenv("BW_NAME")
DEFAULT_USERNAME = os.getenv("DEFAULT_USERNAME")


# ---------- Helpers ----------

def get_entry_name() -> str:
    # Ensure unique entry-name (case-insensitive)

    print_status("Adding a new server entry...", status="info")
    while True:
        entry_name = input("Entry name: ").strip()
        if not entry_name:
            print_status("Entry name cannot be empty.", status="error")
            continue
        if entry_name.lower() in existing:
            print_status(f"An entry named '{entry_name}' already exists. Please choose another.", status="error")
            continue
        return entry_name

def get_ssh_username() -> str:
    while True:
        ssh_username = input("SSH username: ").strip()
        if ssh_username:
            return ssh_username
        print_status("SSH username is required when no Bitwarden entry is provided.", status="error")

def get_ip_hostname() -> str:
    while True:
        ssh_username = input("Server IP/Hostname: ").strip()
        if ssh_username:
            return ssh_username
        print_status("Server IP/Hostname is required.", status="error")

def print_servers(servers: list[dict]) -> None:
    """
    Print server entries in a compact, auto-formatted table.
    """
    if not servers:
        print("[-] No servers found.")
        return

    # Extract rows with safe defaults
    rows = []
    for srv in servers:
        rows.append([
            str(srv.get(NICKNAME) or "-"),
            str(srv.get(IP) or "-"),
            str(srv.get(USERNAME) or "-"),
            str(srv.get(BW_NAME) or "-"),
        ])

    headers = ["Entry name", "IP/Hostname", "User", "Bitwarden name"]

    # Compute column widths
    cols = list(zip(*([headers] + rows)))
    col_widths = [max(len(str(item)) for item in col) + 2 for col in cols]

    # Format string based on column widths
    fmt = "".join("{:<" + str(width) + "}" for width in col_widths)

    # Print header
    print(fmt.format(*headers))
    print("-" * (sum(col_widths)))

    # Print rows
    for row in rows:
        print(fmt.format(*row))


# ---------- completers ----------

def entry_name_completer(prefix, parsed_args, **kwargs):
    """
    Return only entry-names. Shows all if no prefix.
    Case-insensitive startswith filtering.
    """
    names = load_server_names(SERVERS_FILE, NICKNAME)
    if prefix:
        pref = prefix.lower()
        return [n for n in names if n.lower().startswith(pref)]
    return names

# ---------- actions ----------

def add_server(provided_entry_name=None):
    servers = load_servers(SERVERS_FILE)
    existing = {s[NICKNAME] for s in servers if NICKNAME in s}

    # ----- Get entry name -----
    # If there is a provided name and it hasn't been taken
    if provided_entry_name and provided_entry_name not in existing:
        print_status("Adding a new server entry...", status="info")
        entry_name = provided_entry_name
        print_status(f"Entry name: {entry_name}", status="success")

    # If there is a provided name and it is already taken
    elif provided_entry_name and provided_entry_name in existing:
        print_status(f"An entry named '{provided_entry_name}' already exists. Please choose another.", status="error")
        entry_name = get_entry_name()

    # If there is not a provided name
    else:
        entry_name = get_entry_name()

    # ----- Get bitwarden name -----
    bitwarden_name = input("Bitwarden name (leave empty if none): ").strip()


    # ----- Get ssh username -----
    ssh_username = ""
    if not bitwarden_name:
        ssh_username = get_ssh_username()
    else:
        ssh_username = DEFAULT_USERNAME

    # ----- Get IP / Hostname -----
    ip = get_ip_hostname()

    # ----- Create new entry -----
    new_entry = {NICKNAME: entry_name, IP: ip}
    if ssh_username:
        new_entry[USERNAME] = ssh_username
    if bitwarden_name:
        new_entry[BW_NAME] = bitwarden_name

    servers.append(new_entry)
    save_servers(SERVERS_FILE, servers)
    print_status(f"Added server '{entry_name}'", status="success")

def list_servers(filter_substr=None):
    servers = load_servers(SERVERS_FILE)
    if not servers:
        print_status("No servers found.", status="error")
        return

    flt = (filter_substr or "").lower()
    matching_servers = []
    for s in servers:
        name = s.get(NICKNAME, "")
        if flt and flt not in name.lower():
            continue
        matching_servers.append(s)
    print_servers(matching_servers)

def edit_server(entry_name):
    servers = load_servers(SERVERS_FILE)
    idx = next((i for i, s in enumerate(servers)
                if s.get(NICKNAME, "") == entry_name), None)
    if idx is None:
        print_status(f"Server '{entry_name}' not found.", status="error")
        return

    s = servers[idx]
    cur_entry_name = s.get(NICKNAME, "")
    print_status(f"Editing \'{cur_entry_name}\'. Press Enter to keep current value.", status="info")

    while True:
        new_entry_name = input(f"Entry name [{cur_entry_name}]: ").strip()
        if new_entry_name:
            if any(srv.get(NICKNAME, "") == new_entry_name for srv in servers):
                print_status(f"Entry name '{new_entry_name}' already exists. Please enter a unique name.", status="error")
                continue
            s[NICKNAME] = new_entry_name
            break
        else:
            break

    cur_ip = s.get(IP, "")
    new_ip = input(f"Ip/Hostname [{cur_ip}]: ").strip()
    if new_ip:
        s[IP] = new_ip

    s[USERNAME] = None
    cur_bw = s.get(BW_NAME, "")
    new_bw = input(f"Bitwarden Name [{cur_bw}]: ").strip()
    if new_bw:
        s[BW_NAME] = new_bw
    else: # If no Bitwarden Name was provided, ask for a username
        cur_user = s.get(USERNAME, "")
        new_user = input(f"SSH username [{cur_user}]: ").strip()
        if new_user:
            s[USERNAME] = new_user

    servers[idx] = s
    save_servers(SERVERS_FILE, servers)
    print_status(f"Server '{cur_entry_name}' updated.", status="success")

def remove_server(entry_name):
    servers = load_servers(SERVERS_FILE)
    idx = next((i for i, s in enumerate(servers)
                if s.get(NICKNAME, "") == entry_name), None)
    if idx is None:
        print_status(f"Server '{entry_name}' not found.", status="error")
        return

    confirm = prompt_yes_no(f"Are you sure you want to remove '{entry_name}'? This cannot be undone", default="no")
    if confirm:
        del servers[idx]
        save_servers(SERVERS_FILE, servers)
        print_status(f"Removed '{entry_name}'", status="success")
    else:
        print_status("Cancelled.", status="info")

# ---------- CLI ----------

def build_parser():
    parser = argparse.ArgumentParser(description="Manager server entries for connect script")

    parser.add_argument("-a","--add", nargs="?", metavar="ENTRY", help="Add a new server entry")
    parser.add_argument("-l","--list", nargs="?", const="", help="List existing servers (optionally filter by substring)").completer = entry_name_completer
    parser.add_argument("-e","--edit", metavar="ENTRY", help="Edit an existing server entry").completer = entry_name_completer
    parser.add_argument("-r","--remove", metavar="ENTRY", help="Remove an existing server entry").completer = entry_name_completer

    # IMPORTANT: Enable autocomplete
    argcomplete.autocomplete(parser)

    return parser

def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.add:
        add_server(args.add)
    elif args.list is not None:
        list_servers(args.list if args.list != "" else None)
    elif args.edit:
        edit_server(args.edit)
    elif args.remove:
        remove_server(args.remove)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
