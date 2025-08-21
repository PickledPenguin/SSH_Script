#!/usr/bin/env python3
import argparse
import json
import os
import sys

SERVERS_FILE = "servers.json"

def print_servers(servers: list[dict]) -> None:
    """
    Print server entries in a compact table-like format.
    Shows only: entry-name, server-ip, bitwarden-name, ssh-username
    """
    if not servers:
        print("[-] No servers found.")
        return

    # Header
    print(f"{'Name':20} {'IP':20} {'User':15} {'Bitwarden':20}")
    print("-" * 75)

    # Rows
    for srv in servers:
        name = srv.get("entry-name", "-")
        ip = srv.get("server-ip", "-")
        user = srv.get("ssh-username", "-")
        bw = srv.get("bitwarden-name", "-")
        print(f"{name:20} {ip:20} {user:15} {bw:20}")


# ---------- data utils ----------

def load_servers():
    if not os.path.exists(SERVERS_FILE):
        return []
    try:
        with open(SERVERS_FILE, "r") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            return []
    except json.JSONDecodeError:
        return []

def save_servers(servers):
    with open(SERVERS_FILE, "w") as f:
        json.dump(servers, f, indent=4)

def load_entry_names():
    return [s.get("entry-name", "") for s in load_servers() if s.get("entry-name")]

# ---------- completers ----------

def entry_name_completer(prefix, parsed_args, **kwargs):
    """
    Return only entry-names (no file fallback). Shows all if no prefix.
    Case-insensitive startswith filtering.
    """
    names = load_entry_names()
    if prefix:
        pref = prefix.lower()
        return [n for n in names if n.lower().startswith(pref)]
    return names

def entry_name_contains_completer(prefix, parsed_args, **kwargs):
    """
    Useful for -l filter: suggest names containing the substring.
    """
    names = load_entry_names()
    if prefix:
        pref = prefix.lower()
        return [n for n in names if pref in n.lower()]
    return names

# ---------- actions ----------

def add_server():
    print("[*] Adding a new server entry...")
    servers = load_servers()
    existing = {s["entry-name"].lower() for s in servers if "entry-name" in s}

    # Ensure unique entry-name (case-insensitive)
    while True:
        entry_name = input("Entry name: ").strip()
        if not entry_name:
            print("[!] Entry name cannot be empty.")
            continue
        if entry_name.lower() in existing:
            print(f"[!] An entry named '{entry_name}' already exists. Please choose another.")
            continue
        break

    bitwarden_name = input("Bitwarden name (leave empty if none): ").strip()
    ssh_username = ""
    if not bitwarden_name:
        while True:
            ssh_username = input("SSH username: ").strip()
            if ssh_username:
                break
            print("[!] SSH username is required when no Bitwarden entry is provided.")

    ip = input("Server IP/Hostname: ").strip()

    new_entry = {"entry-name": entry_name, "ip": ip}
    if ssh_username:
        new_entry["ssh-username"] = ssh_username
    if bitwarden_name:
        new_entry["bitwarden-name"] = bitwarden_name

    servers.append(new_entry)
    save_servers(servers)
    print(f"[+] Added server '{entry_name}'")

def list_servers(filter_substr=None):
    servers = load_servers()
    if not servers:
        print("[!] No servers found.")
        return

    flt = (filter_substr or "").lower()
    for s in servers:
        name = s.get("entry-name", "")
        if flt and flt not in name.lower():
            continue
        print(json.dumps(s, indent=4))

def edit_server(entry_name):
    servers = load_servers()
    idx = next((i for i, s in enumerate(servers)
                if s.get("entry-name", "").lower() == entry_name.lower()), None)
    if idx is None:
        print(f"[!] Server '{entry_name}' not found.")
        return

    s = servers[idx]
    print(f"[*] Editing '{s.get('entry-name','')}'. Press Enter to keep current value.")

    cur_ip = s.get("ip", "")
    new_ip = input(f"IP/Hostname [{cur_ip}]: ").strip()
    if new_ip:
        s["ip"] = new_ip

    # If entry has bitwarden-name, prefer editing that; otherwise edit ssh-username
    if "bitwarden-name" in s:
        cur_bw = s.get("bitwarden-name", "")
        new_bw = input(f"Bitwarden name [{cur_bw}]: ").strip()
        if new_bw:
            s["bitwarden-name"] = new_bw
        # Optional: allow switching away from BW by clearing value
        # If user enters a single dash '-', clear BW and prompt for ssh user
        if new_bw == "-":
            s.pop("bitwarden-name", None)
            su = input(f"SSH username [{s.get('ssh-username','')}]: ").strip()
            if su:
                s["ssh-username"] = su
    else:
        cur_user = s.get("ssh-username", "")
        new_user = input(f"SSH username [{cur_user}]: ").strip()
        if new_user:
            s["ssh-username"] = new_user
        # Optional: allow switching to BW by entering a value here prefixed with 'bw:'
        # e.g., 'bw:MyVaultItem'
        if new_user.startswith("bw:"):
            s.pop("ssh-username", None)
            s["bitwarden-name"] = new_user[3:].strip()

    servers[idx] = s
    save_servers(servers)
    print(f"[+] Server '{s.get('entry-name','')}' updated.")

def remove_server(entry_name):
    servers = load_servers()
    idx = next((i for i, s in enumerate(servers)
                if s.get("entry-name", "").lower() == entry_name.lower()), None)
    if idx is None:
        print(f"[!] Server '{entry_name}' not found.")
        return

    confirm = input(f"Are you sure you want to remove '{entry_name}'? This cannot be undone (y/N): ").strip().lower()
    if confirm == "y":
        del servers[idx]
        save_servers(servers)
        print(f"[+] Removed '{entry_name}'.")
    else:
        print("[*] Cancelled.")

# ---------- CLI ----------

def build_parser():
    parser = argparse.ArgumentParser(description="Manage servers.json entries")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-a", "--add", action="store_true",
                       help="Add a new server entry")
    group.add_argument("-l", "--list", nargs="?", const="",
                       metavar="FILTER",
                       help="List servers (optionally filter by substring)")
    group.add_argument("-e", "--edit", metavar="ENTRY",
                       help="Edit an existing server (autocomplete)")
    group.add_argument("-r", "--remove", metavar="ENTRY",
                       help="Remove a server entry (autocomplete)")

    # Attach completers if argcomplete is available
    try:
        import argcomplete
        from argcomplete.completers import SuppressCompleter  # not used, but here if needed

        # autocomplete on entry names for -e/-r
        parser.add_argument("--_dummy", help=argparse.SUPPRESS)  # placeholder if needed
        # Assign completers directly on the existing actions:
        for action in parser._actions:
            if action.dest == "edit":
                action.completer = entry_name_completer
            if action.dest == "remove":
                action.completer = entry_name_completer
            if action.dest == "list":
                action.completer = entry_name_contains_completer

        argcomplete.autocomplete(parser)
    except Exception:
        # argcomplete not installed; proceed without completion
        pass

    return parser

def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.add:
        add_server()
    elif args.list is not None:
        list_servers(args.list if args.list != "" else None)
    elif args.edit:
        edit_server(args.edit)
    elif args.remove:
        remove_server(args.remove)

if __name__ == "__main__":
    main()
