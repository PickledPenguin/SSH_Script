def save_servers(servers):
    with open(JSON_FILE, "w") as f:
        json.dump(servers, f, indent=4)

def add_server():
    servers = load_servers()

    while True:
        entry_name = input("Entry name (nickname): ").strip()
        if any(s['entry-name'] == entry_name for s in servers):
            print(f"[ERROR] Entry name '{entry_name}' already exists. Please enter a unique name.")
        elif entry_name == "":
            print("[ERROR] Entry name cannot be empty.")
        else:
            break

    bitwarden_name = input("Bitwarden name (press enter to skip): ").strip()

    ssh_username = ""
    if not bitwarden_name:
        while True:
            ssh_username = input("SSH username: ").strip()
            if ssh_username == "":
                print("[ERROR] SSH username is required if Bitwarden name is not provided.")
            else:
                break

    ssh_ip = ""
    while True:
        ssh_ip = input("SSH IP: ").strip()
        if ssh_ip == "":
            print("[ERROR] SSH IP cannot be empty.")
        else:
            break

    new_entry = {
        "entry-name": entry_name,
        "ssh-username": ssh_username if ssh_username else None,
        "ssh-ip": ssh_ip,
        "bitwarden-name": bitwarden_name if bitwarden_name else None
    }

    servers.append(new_entry)
    save_servers(servers)
    print(f"[*] Server '{entry_name}' added successfully.")

if __name__ == "__main__":
    add_server()
