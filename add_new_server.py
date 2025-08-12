#!/usr/bin/env python3
import json
import os

JSON_FILE = "./servers.json"

def load_servers():
    if not os.path.exists(JSON_FILE):
        return []
    with open(JSON_FILE, "r") as f:
        return json.load(f)

def save_servers(servers):
    with open(JSON_FILE, "w") as f:
        json.dump(servers, f, indent=2)

def get_unique_entry_name(servers):
    while True:
        entry_name = input("Enter entry-name (unique identifier): ").strip()
        if not entry_name:
            print("Entry-name cannot be empty.")
            continue
        if any(s.get("entry-name") == entry_name for s in servers):
            print(f"Error: entry-name '{entry_name}' already exists. Please choose a different one.")
        else:
            return entry_name

def main():
    servers = load_servers()

    entry_name = get_unique_entry_name(servers)
    ssh_username = input("Enter ssh-username: ").strip()
    ssh_ip = input("Enter ssh-ip: ").strip()
    bitwarden_name = input("Enter Bitwarden-Name (optional, press Enter to skip): ").strip()

    new_entry = {
        "entry-name": entry_name,
        "ssh-username": ssh_username,
        "ssh-ip": ssh_ip
    }
    if bitwarden_name:
        new_entry["Bitwarden-Name"] = bitwarden_name

    servers.append(new_entry)
    save_servers(servers)
    print(f"Entry '{entry_name}' added successfully.")

if __name__ == "__main__":
    main()
