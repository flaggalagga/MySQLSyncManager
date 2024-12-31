#!/usr/bin/env python3
import os
import sys
import atexit
from typing import Optional, Tuple

# Add the current directory to the Python path when running as a module
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)
    
from config import DB_CONFIG, SSH_CONFIG, validate_config, select_configuration
from utils import print_header, SpinnerProgress, GREEN, RED, YELLOW, BLUE, BOLD, DIM, NC, ICONS
from ssh import connect_ssh, execute_remote_command
from db import restore_database
from backup_operations import extract_backup, download_file
from menu import select_backup_option
from exceptions import DatabaseManagerError, SSHConnectionError
from paramiko import SSHClient

def cleanup():
    """Clean up temporary files"""
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
    """Setup and validate configuration"""
    if not select_configuration():
        print(f"{RED}Configuration selection failed. Please try again.{NC}")
        return False
        
    missing_vars = validate_config()
    if missing_vars:
        print(f"{RED}Error: Required variables not set: {', '.join(missing_vars)}{NC}")
        return False
    
    return True

def establish_ssh_connection() -> Optional[SSHClient]:
    """Establish SSH connection"""
    try:
        ssh = connect_ssh(SSH_CONFIG, DB_CONFIG)
        print(f"{GREEN}{ICONS['check']} SSH connection established{NC}")
        return ssh
    except Exception as e:
        print(f"{RED}SSH connection failed: {str(e)}{NC}")
        return None

def process_backup(ssh: SSHClient, remote_path: str) -> bool:
    """Process backup download and restore"""
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
    """Run the backup selection and processing workflow"""
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
    """Main application entry point"""
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