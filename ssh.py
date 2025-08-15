    session_key = ensure_bitwarden_session()

    # Get target server credentials
    dest_user = target_server.get("ssh-username")
    dest_pass = None
    if "bitwarden-name" in target_server and session_key:
        bw_user, bw_pass = bitwarden_fetch(target_server["bitwarden-name"], session_key)
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

    # Get a variable with "https://" or "http://" removed from the target server's ssh-ip, in case its there
    target_server_ip = re.sub(r'^https?://', '', target_server.get("ssh-ip"))

    if args.file:
        local_file, remote_dest = args.file
        print("[*] File transfer requested.")

        if use_jump:
            print(f"[*] Transferring file to {entry_name} via jump server {jump_ip}...")
            run_expect_scp(dest_user, target_server_ip, dest_pass, local_file, remote_dest,
                           jump_server=f"{jump_user}@{jump_ip}")
        else:
            print(f"[*] Transferring file directly to {entry_name}...")
            run_expect_scp(dest_user, target_server_ip, dest_pass, local_file, remote_dest)

    print("[*] Opening SSH session...")
    if use_jump:
        run_expect_ssh(dest_user, target_server_ip, dest_pass, jump_server=f"{jump_user}@{jump_ip}")
    else:
        run_expect_ssh(dest_user, target_server_ip, dest_pass)


if __name__ == "__main__":
    main()
