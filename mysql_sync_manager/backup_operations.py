"""Backup operations module."""
import os
import time
from scp import SCPClient
from paramiko import SSHClient, SSHException
from typing import Optional, Dict, List, Tuple
from mysql_sync_manager.utils import SpinnerProgress, GREEN, RED, YELLOW, BLUE, BOLD, NC, ICONS
from mysql_sync_manager.exceptions import BackupError
from mysql_sync_manager.retry_utils import RetryContext
from mysql_sync_manager.ssh import execute_remote_command
from mysql_sync_manager.db import get_mysql_info

def get_database_objects(ssh: SSHClient, db_config: Dict[str, str]) -> List[str]:
    """Get list of database objects from remote server.
    
    Retrieves list of tables and views through SSH connection.

    Args:
        ssh: SSH client connection
        db_config: Database configuration dictionary
        
    Returns:
        List[str]: List of database object names

    Raises:
        SSHException: If remote command execution fails
    """
    escaped_password = db_config['MYSQL_EXPORT_PASSWORD'].replace("'", "'\\''")
    
    objects_cmd = (
        f"mysql -h {db_config['MYSQL_EXPORT_HOST']} "
        f"-P {db_config['MYSQL_EXPORT_PORT']} "
        f"-u{db_config['MYSQL_EXPORT_USER']} -p'{escaped_password}' "
        f"-N -B -e 'SHOW FULL TABLES FROM `{db_config['MYSQL_EXPORT_DATABASE']}`'"
    )
    
    tables = []
    try:
        stdin, stdout, stderr = ssh.exec_command(objects_cmd)
        output = stdout.read().decode('utf-8').strip()
        error = stderr.read().decode('utf-8').strip()
        
        if error and 'Warning' not in error:
            print(f"{RED}Error getting database objects: {error}{NC}")
            return []
        
        for line in output.split('\n'):
            if line:
                parts = line.split('\t')
                if len(parts) == 2:
                    name, obj_type = parts
                    if obj_type == 'BASE TABLE':
                        tables.append(name)
    except SSHException as e:
        print(f"{RED}Error executing remote command: {str(e)}{NC}")
        return []
                
    return tables

def select_backup_options(ssh: SSHClient, db_config: Dict[str, str]) -> Tuple[List[str], bool]:
    """Select backup inclusion/exclusion options.
    
    Interactive menu for selecting backup components.

    Args:
        ssh: SSH client connection
        db_config: Database configuration dictionary
        
    Returns:
        Tuple containing:
            - List[str]: Excluded table names 
            - bool: Whether to skip routines
    """
    print(f"\n{ICONS['data_chart']}  {BOLD}Backup Options:{NC}")
    print(f"{'─'*50}")
    print(f"{BLUE}1.{NC} Export everything (tables + routines)")
    print(f"{BLUE}2.{NC} Customize export content")
    
    choice = input(f"\n{BOLD}Select option [{BLUE}1{NC}]: {NC}").strip()
    if choice != '2':
        return [], False
    
    try:
        tables = get_database_objects(ssh, db_config)
        if not tables:
            print(f"{YELLOW}No tables found in database{NC}")
            return [], False
    except SSHException as e:
        print(f"{RED}Error retrieving database objects: {str(e)}{NC}")
        return [], False
    
    # Print tables in columns
    num_columns = 3
    rows = (len(tables) + num_columns - 1) // num_columns
    max_width = max(len(table) for table in tables) + 6
    
    print(f"\n{BOLD}Available Tables:{NC}")
    print(f"{'─'*50}")
    for row in range(rows):
        line = ""
        for col in range(num_columns):
            idx = row + col * rows
            if idx < len(tables):
                line += f"{idx+1:2d}. {tables[idx]}".ljust(max_width)
        print(line)
    
    excluded_tables = []
    if input(f"\n{BOLD}Do you want to exclude any tables? (y/N): {NC}").lower().strip() == 'y':
        excluded = input(f"{BOLD}Tables to exclude (numbers or names): {NC}").strip()
        for part in excluded.split(','):
            part = part.strip()
            try:
                num = int(part)
                if 1 <= num <= len(tables):
                    excluded_tables.append(tables[num - 1])
            except ValueError:
                if part in tables:
                    excluded_tables.append(part)
    
    print(f"\n{BOLD}Additional Options:{NC}")
    print(f"{'─'*50}")
    skip_routines = input(f"{BOLD}Skip stored procedures and functions? (y/N): {NC}").lower().strip() == 'y'
    
    return excluded_tables, skip_routines

def create_new_backup(ssh: SSHClient, db_config: Dict[str, str]) -> Optional[str]:
    """Create new database backup.
    
    Creates a new backup on remote server using mysqldump.

    Args:
        ssh: SSH client connection
        db_config: Database configuration dictionary
        
    Returns:
        Optional[str]: Path to created backup file or None if backup failed
        
    Raises:
        BackupError: If backup creation fails
    """
    print(f"\n{BOLD}Creating new backup...{NC}")

    # Get MySQL info and version using the consolidated function
    version, has_privileges = get_mysql_info(db_config, server_type='export', ssh=ssh)
    mysql_version = int(version) if version else None

    backup_dir = db_config['MYSQL_EXPORT_BACKUP_DIR']
    backup_name = (
        f"{db_config['MYSQL_EXPORT_DATABASE']}-export-"
        f"{time.strftime('%Y%m%d-%H%M%S')}.sql.gz"
    )
    remote_path = f"{backup_dir}/{backup_name}"
    
    try:
        # Ensure backup directory exists
        mkdir_cmd = f"mkdir -p {backup_dir}"
        if not execute_remote_command(ssh, mkdir_cmd):
            raise BackupError("initialization", "Failed to create backup directory")

        # Get backup options
        excluded_tables, skip_routines = select_backup_options(ssh, db_config)
        
        # Prepare mysqldump options
        mysqldump_options = [
            "--single-transaction",
            "--quick",
            "--opt",
            "--skip-lock-tables",
            "--set-charset",
            "--default-character-set=utf8mb4"
        ]

          # Add optimization options if we have privileges
        if has_privileges:
            mysqldump_options.extend([
                "--max-allowed-packet=512M",
                "--net-buffer-length=32768",
                "--set-variable=net_buffer_length=32768",
                "--init-command=\"SET SESSION FOREIGN_KEY_CHECKS=0; "
                "SET SESSION UNIQUE_CHECKS=0; "
                "SET SESSION SQL_MODE='NO_AUTO_VALUE_ON_ZERO'; "
                "SET SESSION sql_log_bin=0;\""
            ])

        # Add version-specific options
        if mysql_version and mysql_version >= 5:
            # For MySQL 8.0+, use different syntax for GTID purged
            mysqldump_options.append("--set-gtid-purged=OFF")
            # Also add master data option
            mysqldump_options.append("--master-data=2")
        
        if not skip_routines:
            mysqldump_options.append("--routines")
        
        # Add excluded tables
        for table in excluded_tables:
            mysqldump_options.append(
                f"--ignore-table={db_config['MYSQL_EXPORT_DATABASE']}.{table}"
            )
        
        # Convert options to string
        mysqldump_options_str = ' '.join(mysqldump_options)
        
        # Print backup configuration
        print(f"\n{BOLD}Backup Configuration:{NC}")
        if excluded_tables:
            print(f"{BLUE}Excluded Tables:{NC} {', '.join(excluded_tables)}")
        print(f"{BLUE}Include Routines:{NC} {'No' if skip_routines else 'Yes'}")
        print()
        
        # Escape password
        escaped_password = db_config['MYSQL_EXPORT_PASSWORD'].replace("'", "'\\''")
        
        # Construct the dump command
        dump_cmd = (
            f"mysqldump "
            f"-h {db_config['MYSQL_EXPORT_HOST']} "
            f"-P {db_config['MYSQL_EXPORT_PORT']} "
            f"-u{db_config['MYSQL_EXPORT_USER']} "
            f"-p'{escaped_password}' "
            f"--opt "
            f"--allow-keywords "
            f"--quote-names "
            f"--skip-set-charset "
            f"--single-transaction "
            f"--quick "
            f"--skip-lock-tables "
            f"--default-character-set=utf8mb4 "
            f"{' --routines' if not skip_routines else ''} "
            f"{db_config['MYSQL_EXPORT_DATABASE']} > /tmp/temp.sql"
        )
        
        # Execute backup steps with progress indicators
        with RetryContext("Creating MySQL dump", retries=2) as ctx:
            if not execute_remote_command(ssh, dump_cmd):
                raise BackupError("mysqldump", "Failed to create MySQL dump")
                
        with RetryContext("Compressing backup", retries=2) as ctx:
            compress_cmd = f"gzip -c /tmp/temp.sql > {remote_path}"
            if not execute_remote_command(ssh, compress_cmd):
                raise BackupError("compression", "Failed to compress backup")
                
        # Clean up and verify
        cleanup_cmd = "rm -f /tmp/temp.sql"
        verify_cmd = f"ls -lh {remote_path}"
        
        execute_remote_command(ssh, cleanup_cmd)
        stdin, stdout, stderr = ssh.exec_command(verify_cmd)
        file_info = stdout.read().decode('utf-8').strip()
        
        if not file_info:
            raise BackupError(
                "verification",
                f"Backup file not found at {remote_path}"
            )
            
        try:
            size = file_info.split()[4]
            print(f"\n{GREEN}{ICONS['check']} Backup created successfully "
                  f"at {ICONS['folder']} {remote_path} (Size: {size}){NC}\n")
            return remote_path
        except IndexError:
            raise BackupError(
                "verification",
                "Could not determine backup file size"
            )
            
    except Exception as e:
        print(f"{RED}Error during backup: {str(e)}{NC}")
        return None

def get_file_extension(filename: str) -> str:
    """Get file extension(s).
    
    Extracts extension from filename, handling compound extensions like .sql.gz

    Args:
        filename: Name of file
        
    Returns:
        str: File extension(s)
    """
    if filename.endswith('.sql.gz'):
        return 'sql.gz'
    return filename.split('.')[-1] if '.' in filename else ''

def extract_backup(local_path: str) -> str:
    """Extract compressed backup file.
    
    Extracts .sql.gz backup files to .sql

    Args:
        local_path: Path to compressed backup
        
    Returns:
        str: Path to extracted SQL file
        
    Raises:
        BackupError: If extraction fails
    """
    extension = get_file_extension(local_path)
    
    try:
        if extension.endswith('sql.gz'):
            output_file = local_path.replace('.gz', '')
            if os.system(f"gunzip -c {local_path} > {output_file}") != 0:
                raise BackupError(
                    "extraction",
                    "Failed to extract sql.gz backup"
                )
            os.remove(local_path)  # Remove compressed file after extraction
            return output_file
        elif extension == 'sql':
            return local_path
        else:
            raise BackupError(
                "extraction",
                f"Unsupported file extension: {extension}"
            )
    except Exception as e:
        raise BackupError("extraction", str(e)) from e

def download_file(ssh: SSHClient, remote_path: str, progress) -> Optional[str]:
    """Download and prepare file for restoration.
    
    Downloads backup file from remote server.

    Args:
        ssh: SSH client connection
        remote_path: Path to remote backup file
        progress: Progress indicator object
        
    Returns:
        Optional[str]: Path to downloaded file or None if download fails
    """
    local_path = os.path.basename(remote_path)
    
    # Create a SpinnerProgress for download
    download_progress = SpinnerProgress("Downloading backup")
    
    try:
        download_progress.start()
        try:
            # Try to use scp if available
            with SCPClient(ssh.get_transport()) as scp:
                scp.get(remote_path, local_path)
        except ImportError:
            # Fallback to sftp if scp is not installed
            sftp = ssh.open_sftp()
            sftp.get(remote_path, local_path)
            sftp.close()
        
        download_progress.stop(True)
        return local_path
        
    except Exception as e:
        download_progress.stop(False)
        print(f"{RED}{ICONS['times']} Download failed: {str(e)}{NC}")
        return None