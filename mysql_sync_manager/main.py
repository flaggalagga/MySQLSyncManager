#!/usr/bin/env python3
"""MySQL Sync Manager - Main Module.

This module serves as the main entry point for the MySQL Sync Manager application.
It handles the core workflow for:
- Configuration setup and validation
- SSH connection establishment
- Backup selection and processing
- Error handling and cleanup

The application allows users to:
- Create new MySQL database backups
- Download existing backups
- Restore backups to local database
- Clean up temporary files
"""
import os
import sys
import atexit
from typing import Optional, Tuple

# Add the current directory to the Python path when running as a module
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

# To:
from mysql_sync_manager.config import DB_CONFIG, SSH_CONFIG, validate_config, select_configuration

# And similarly for other imports:
from mysql_sync_manager.utils import print_header, SpinnerProgress, GREEN, RED, YELLOW, BLUE, BOLD, DIM, NC, ICONS
from mysql_sync_manager.ssh import connect_ssh, execute_remote_command
from mysql_sync_manager.db import restore_database
from mysql_sync_manager.backup_operations import extract_backup, download_file
from mysql_sync_manager.menu import select_backup_option
from mysql_sync_manager.exceptions import DatabaseManagerError, SSHConnectionError

from paramiko import SSHClient

def cleanup():
    """Clean up temporary files created during backup operations.

    This function is registered with atexit to ensure cleanup happens even if the 
    program exits unexpectedly. It removes any temporary .tar.gz, .sql, or .sql.gz 
    files in the current directory.

    Note:
        Files are only removed from the current working directory
        Errors during cleanup are logged but won't stop the program
    
    Example:
        If during backup these files were created:
            - temp_backup.sql.gz
            - extracted.sql
            - partial.sql.gz
        They would all be removed during cleanup.
    """
    try:
        for file in os.listdir('.'):
            if file.endswith(('.tar.gz', '.sql', '.sql.gz')):
                try:
                    os.remove(file)
                    print(f"{DIM}Cleaned up: {file}{NC}")
                except Exception as e:
                    print(f"{RED}Failed to remove {file}: {str(e)}{NC}")
    except OSError as e:
        print(f"{RED}Failed to list directory: {str(e)}{NC}")

def setup_configuration() -> bool:
    """Set up and validate database configuration.

    Loads configuration from the YAML file and validates all required settings 
    for both database and SSH connections.

    Returns:
        bool: True if configuration is valid and complete, False otherwise

    Example:
        >>> success = setup_configuration()
        >>> if not success:
        ...     print("Configuration failed")
        ...     return

    Note:
        Required configuration includes:
        - MySQL export settings (host, user, password, database)
        - MySQL import settings (host, user, password, database)
        - SSH connection details (host, user, either password or key)
    """
    if not select_configuration():
        print(f"{RED}Configuration selection failed. Please try again.{NC}")
        return False
        
    missing_vars = validate_config()
    if missing_vars:
        print(f"{RED}Error: Required variables not set: {', '.join(missing_vars)}{NC}")
        return False
    
    return True

def establish_ssh_connection() -> Optional[SSHClient]:
    """Establish SSH connection using configuration settings.

    Creates and configures an SSH client connection using the settings from
    SSH_CONFIG. Handles both password and key-based authentication.

    Returns:
        Optional[SSHClient]: Connected SSH client if successful, None if connection fails

    Example:
        >>> ssh = establish_ssh_connection()
        >>> if ssh is None:
        ...     print("Failed to establish SSH connection")
        ...     return
    """
    try:
        ssh = connect_ssh(SSH_CONFIG, DB_CONFIG)
        print(f"{GREEN}{ICONS['check']} SSH connection established{NC}")
        return ssh
    except Exception as e:
        print(f"{RED}SSH connection failed: {str(e)}{NC}")
        return None

def process_backup(ssh: SSHClient, remote_path: str) -> bool:
    """Process remote backup file download and restoration.

   Downloads a backup file from remote server, optionally deletes remote copy,
   extracts the backup if compressed, and restores it to local database.

   Args:
       ssh: Connected SSH client to use for operations
       remote_path: Path to backup file on remote server

   Returns:
       bool: True if backup was successfully processed and restored, False otherwise
    """
    try:
        # Ask about deletion
        delete_remote = input(f"\n{ICONS['trash']}  Delete remote file after downloading? [n]: ").lower().strip()
        delete_remote = delete_remote in ['y', 'yes']
        print()

        # Download backup file
        progress = SpinnerProgress("Downloading backup")
        local_path = download_file(ssh, remote_path, progress)
        
        if not local_path:
            print(f"{RED}Failed to download backup file{NC}")
            return False

        if delete_remote:
            delete_progress = SpinnerProgress("Deleting remote file")
            delete_progress.start()
            success = execute_remote_command(ssh, f"rm {remote_path}")
            delete_progress.stop(success)

        # Extract backup
        extract_progress = SpinnerProgress("Extracting backup")
        extract_progress.start()
        try:
            sql_file = extract_backup(local_path)
            extract_progress.stop(True)

            # Restore database
            if restore_database(sql_file, DB_CONFIG):
                print(f"{GREEN}{ICONS['check']} Database restore completed!{NC}")
                return True
            else:
                print(f"{RED}Database restore failed. Please try again.{NC}")
                return False
        except Exception as e:
            extract_progress.stop(False)
            print(f"{RED}Error during extraction: {str(e)}{NC}")
            return False
            
    except Exception as e:
        print(f"{RED}Error processing backup: {str(e)}{NC}")
        return False

def run_backup_workflow(ssh: SSHClient) -> Tuple[bool, bool]:
    """Run the backup selection and processing workflow.

    Manages the backup selection menu and processing flow, handling both user navigation 
    and error conditions.

    Args:
        ssh: Connected SSH client for remote operations

    Returns:
        Tuple[bool, bool]: A tuple of (continue_outer, continue_inner) flags where:
            - continue_outer: True to continue main program loop
            - continue_inner: True to continue backup selection loop

    Example:
        continue_outer = True
        while continue_outer:
            continue_outer, continue_inner = run_backup_workflow(ssh)
            if not continue_inner:
                break
    """
    try:
        remote_path = select_backup_option(ssh, DB_CONFIG)
        
        if remote_path == 'back':
            return True, False  # Continue outer loop, but break inner loop
            
        if not remote_path:
            print(f"{YELLOW}No backup file selected. Please try again.{NC}")
            return False, True  # Continue both loops
        
        success = process_backup(ssh, remote_path)
        return False, not success  # If success, break both loops
        
    except Exception as e:
        print(f"{RED}Error in backup workflow: {str(e)}{NC}")
        return False, True  # Continue both loops

def main():
    """Main entry point for MySQL Sync Manager.

    Controls the main application flow:
    1. Prints header information
    2. Sets up cleanup handler
    3. Establishes configuration
    4. Creates SSH connection
    5. Runs backup workflow
    6. Handles errors and cleanup

    The function implements a retry mechanism for configuration and connection issues,
    allowing users to correct problems without restarting the application.

    Example:
        To run the application:
        >>> if __name__ == '__main__':
        ...     main()

    Note:
        - Exits gracefully on KeyboardInterrupt (Ctrl+C)
        - Ensures SSH connections are properly closed
        - Runs cleanup on exit through atexit handler
    """
    try:
        print_header()
        atexit.register(cleanup)
        
        while True:  # Main program loop
            if not setup_configuration():
                continue
                
            ssh = establish_ssh_connection()
            if not ssh:
                continue

            try:
                continue_outer = True
                while continue_outer:
                    continue_outer, continue_inner = run_backup_workflow(ssh)
                    if not continue_inner:
                        break
            finally:
                ssh.close()
                print(f"{DIM}SSH connection closed{NC}")

    except KeyboardInterrupt:
        print(f"\n\n{YELLOW}Operation cancelled by user{NC}")
        sys.exit(0)
    except Exception as e:
        print(f"\n{RED}An unexpected error occurred:{NC}")
        print(f"{RED}{str(e)}{NC}")
        print(f"{YELLOW}Please try again.{NC}")
        return main()

if __name__ == '__main__':
    main()