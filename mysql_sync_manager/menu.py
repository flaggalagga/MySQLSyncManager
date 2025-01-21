"""Menu system with correct variable names."""
import os
import sys
from typing import Optional, Dict
from mysql_sync_manager.utils import RED, YELLOW, BLUE, NC, BOLD, ICONS
from mysql_sync_manager.ssh import list_remote_backups, check_remote_file
from mysql_sync_manager.backup_operations import create_new_backup
from mysql_sync_manager.exceptions import ValidationError, BackupError

def select_backup_option(ssh, db_config: Dict[str, str]) -> Optional[str]:
    """Handle backup file selection.
    
    Presents menu for backup selection:
    - Create new backup
    - Select existing backup
    - Specify custom backup path

    Args:
        ssh: SSH client connection
        db_config: Database configuration dictionary
        
    Returns:
        Optional[str]: Selected backup path or None if cancelled
        
    Raises:
        ValidationError: If user input is invalid
        BackupError: If backup operations fail
    """
    backup_dir = db_config.get('MYSQL_EXPORT_BACKUP_DIR')  # Updated variable name
    if not backup_dir:
        raise ValidationError(
            "MYSQL_EXPORT_BACKUP_DIR",  # Updated error message
            "Export backup directory not configured"
        )
    
    while True:
        try:
            print(f"\n{ICONS['folder']}  {BOLD}Backup Options:{NC}")
            print(f"{'─'*50}")
            print(f"{BLUE}1.{NC} {ICONS['database']}\tCreate new backup from database\n")
            print(f"{BLUE}2.{NC} {ICONS['server']}\tUse existing backup from server\n")
            print(f"{BLUE}3.{NC} {ICONS['upload']}\tSpecify custom backup path\n")
            print(f"{BLUE}b.{NC} {ICONS['refresh']}\tBack to configuration selection\n")
            print(f"{BLUE}q.{NC} {ICONS['times']}\tQuit")
            print(f"{'─'*50}")

            choice = input(f"\n{BOLD}Select option [{BLUE}1{NC}]: {NC}").strip().lower()
            
            if choice == 'q':
                print(f"\n{YELLOW}{ICONS['info']} Exiting...{NC}")
                sys.exit(0)
            elif choice == 'b':
                return 'back'
            elif choice == '' or choice == '1':
                backup_path = create_new_backup(ssh, db_config)
                if backup_path is None:
                    sys.exit(0)
                return backup_path
            elif choice == '2':
                return select_existing_backup(ssh, backup_dir)
            elif choice == '3':
                return select_custom_backup(ssh)
            else:
                print(f"{YELLOW}Please enter a valid option (1-3), 'b' for back, or 'q' to quit{NC}")
                
        except (ValidationError, BackupError) as e:
            print(f"{RED}Error: {str(e)}{NC}")
            if hasattr(e, 'cause') and e.cause:
                print(f"{YELLOW}Caused by: {str(e.cause)}{NC}")
            continue
        except Exception as e:
            print(f"{RED}Unexpected error: {str(e)}{NC}")
            continue

def select_existing_backup(ssh, backup_dir: str) -> Optional[str]:
    """Select existing backup from server.
    
    Lists and allows selection of existing backups.

    Args:
        ssh: SSH client connection 
        backup_dir: Remote backup directory
        
    Returns:
        Optional[str]: Selected backup path or None if cancelled
        
    Raises:
        BackupError: If backup listing fails
    """
    try:
        backup_files = list_remote_backups(ssh, backup_dir)
        if not backup_files:
            print(f"{YELLOW}{ICONS['warning']} No backup files found in {backup_dir}{NC}")
            return None
            
        while True:
            print(f"\n{ICONS['info']}  {BOLD}Available backup files:{NC}")
            print(f"{'─'*80}")
            print(f"{BOLD}{BLUE}{'#':3} {'Filename':40} {'Size':8} {'Date':20}{NC}")
            print(f"{'─'*80}")
            
            for i, file in enumerate(backup_files, 1):
                print(
                    f"{BLUE}{i:3}{NC} "
                    f"{os.path.basename(file['name']):40} "
                    f"{file['size']:8} "
                    f"{file['date']:20}"
                )
            print(f"{'─'*80}")
            print(f"{BLUE}b.{NC} {ICONS['refresh']} Back to backup options\n")
            print(f"{BLUE}q.{NC} {ICONS['times']} Quit")
            
            file_choice = input(
                f"\n{BOLD}Select a file number (b to go back, q to quit): {NC}"
            ).strip().lower()
            
            if file_choice == 'q':
                print(f"\n{YELLOW}{ICONS['info']} Exiting...{NC}")
                sys.exit(0)
            if file_choice == 'b':
                return None
                
            try:
                file_num = int(file_choice)
                if 1 <= file_num <= len(backup_files):
                    return backup_files[file_num - 1]['name']
                raise ValidationError(
                    "file_choice",
                    f"Please enter a number between 1 and {len(backup_files)}"
                )
            except ValueError:
                print(f"{YELLOW}Please enter a valid number{NC}")
                
    except Exception as e:
        raise BackupError("listing", str(e)) from e

def select_custom_backup(ssh) -> Optional[str]:
    """Select custom backup path.
    
    Allows user to specify arbitrary backup path.

    Args:
        ssh: SSH client connection
        
    Returns:
        Optional[str]: Specified backup path or None if cancelled
        
    Raises:
        ValidationError: If path is invalid
    """
    while True:
        path = input(f"\n{BOLD}Enter the full path to the backup file (b to go back, q to quit): {NC}").strip()
        
        if path.lower() == 'q':
            print(f"\n{YELLOW}{ICONS['info']} Exiting...{NC}")
            sys.exit(0)
        if path.lower() == 'b':
            return None
            
        if not path:
            print(f"{YELLOW}Please enter a valid path{NC}")
            continue
            
        if check_remote_file(ssh, path):
            return path
            
        print(f"{RED}{ICONS['warning']} File not found: {path}{NC}")
        
    return None