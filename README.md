# SSH Jump + Server Manager with Bitwarden Integration

This project provides two main utilities for managing SSH server connections, including optional **jump server** support and **Bitwarden password manager** integration for securely retrieving credentials.

---

## Features
- Store and manage a list of SSH server entries in a `servers.json` file.
- Optionally associate servers with Bitwarden entries to fetch usernames and passwords automatically.
- Support for SSH **jump server** connections (`ProxyJump`).
- Optional file transfer (`scp`) before SSH connection.
- Interactive prompts for credentials if Bitwarden does not provide them.
- Simple Bash wrapper scripts for easy execution.

---

## File Structure
```
.
├── add_server        # Bash wrapper to run add_server.py
├── add_server.py     # Python script to add servers to servers.json
├── ssh               # Bash wrapper to run ssh.py
├── ssh.py            # Python script to connect to servers (with jump server and Bitwarden support)
├── servers.json      # JSON file storing all server entries
├── setup.sh          # Setup script to install dependencies and CLI tools
└── .env              # Stores Bitwarden credentials & jump server entry name
```

---

## Installation & Setup

### 1.) Clone the Repository
```bash
git clone <your_repo_url>
cd <your_repo_name>
```

### 2.) Configure `.env`
Configure the `.env` file in the project root:
```env
# Bitwarden credentials
BW_CLIENTID=your_client_id
BW_CLIENTSECRET=your_client_secret
BW_PASSWORD=your_master_password

# Jump server entry name (must exist in servers.json)
JUMP_SERVER_ENTRY_NAME=your_jump_server_entry
```

> The `JUMP_SERVER_ENTRY_NAME` **must** match the `"entry-name"` of the jump server entry inside `servers.json`.

### 3.) Run Setup Script
The `setup.sh` script installs:
- Python dependencies
- Bitwarden CLI (`bw`)
- `sshpass` (for non-key-based logins)

Run:
```bash
chmod +x setup.sh
./setup.sh
```

---

## Adding Servers

To add a new server entry:
```bash
./add_server
```

You’ll be prompted for:
- **entry-name** (unique identifier)
- **bitwarden-name** (press Enter to skip)
- **ssh-username** (only required if `bitwarden-name` is skipped)
- **ssh-ip**

Entries are stored in `servers.json` as:
```json
{
    "entry-name": "myserver",
    "ssh-username": "myuser",
    "ssh-ip": "192.168.1.10",
    "bitwarden-name": null
}
```

---

## Connecting to a Server

### Direct Connection (no jump server)
```bash
./ssh -c entry-name
```

### Via Jump Server
```bash
./ssh -jc entry-name
# or
./ssh -cj entry-name
```

The jump server to use is pulled from `.env` via `JUMP_SERVER_ENTRY_NAME`.

---

## File Transfer + SSH
To transfer a file **and then SSH in**:
```bash
./ssh -jc entry-name -f <local_file> <remote_path>
```
Example:
```bash
./ssh -jc myserver -f ./script.sh /home/user/
```

---

## Bitwarden Integration

- If a server entry has `"bitwarden-name"`, `ssh.py` will try to fetch its credentials from Bitwarden.
- If the entry has no `"bitwarden-name"`, or Bitwarden fails, you’ll be prompted for credentials manually.
- Bitwarden is unlocked once per run and then locked again after the script completes.

---

## Commands Summary

| Command | Description |
|---------|-------------|
| `./add_server` | Add a new server entry interactively |
| `./ssh -c entry` | SSH directly to `entry` |
| `./ssh -jc entry` | SSH to `entry` via jump server |
| `./ssh -cj entry` | Alias for `-jc` |
| `./ssh -jc entry -f local remote` | Copy file to `entry` via jump server, then SSH |

---

## Notes
- Make sure your `servers.json` is valid JSON at all times.
- If using `sshpass`, you may need to ensure it's installed via `setup.sh`.
- Bitwarden CLI requires an internet connection.

---

## Example Workflow

1. **Add a jump server entry**:
```bash
./add_server
# Entry name: myjump
# Bitwarden name: jump_server_credentials
# SSH IP: 203.0.113.10
```

2. **Set `JUMP_SERVER_ENTRY_NAME` in `.env`**:
```env
JUMP_SERVER_ENTRY_NAME=myjump
```

3. **Add a destination server**:
```bash
./add_server
# Entry name: prodserver
# Bitwarden name: prod_server_credentials
# SSH IP: 192.168.50.5
```

4. **Connect via jump server**:
```bash
./ssh -jc prodserver
```

5. **Copy a file via jump server and SSH in**:
```bash
./ssh -jc prodserver -f ./deploy.sh /home/deploy/
```
