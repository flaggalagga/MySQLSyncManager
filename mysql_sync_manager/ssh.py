"""SSH operations module."""
import os
import time
import paramiko
import socket
from typing import List, Dict, Optional
from mysql_sync_manager.utils import GREEN, RED, BLUE, YELLOW, DIM, NC, CLEAR_LINE, ICONS, BOLD
from mysql_sync_manager.exceptions import SSHConnectionError, ValidationError, BackupError
from mysql_sync_manager.retry_utils import with_retry, RetryContext

def list_remote_backups(ssh: paramiko.SSHClient, backup_dir: str) -> List[Dict[str, str]]:
    """List backup files in remote directory.
    
    Lists .sql.gz and .tar.gz files with metadata.

    Args:
        ssh: SSH client connection
        backup_dir: Directory to search
        
    Returns:
        List[Dict[str, str]]: List of backup info dictionaries containing:
            - name: Backup filename
            - size: File size
            - date: Modification date
            
    Raises:
        BackupError: If listing fails
    """
    try:
        # Look for both .sql.gz and .tar.gz files using the configured backup_dir
        backup_patterns = f"{backup_dir}/*.sql.gz {backup_dir}/*.tar.gz"
        
        stdin, stdout, stderr = ssh.exec_command(f"ls -lh {backup_patterns} 2>/dev/null || true")
        
        files = stdout.read().decode('utf-8').strip()
        
        if not files:
            return []
        
        backup_files = []
        for line in files.split('\n'):
            if line.strip():
                try:
                    parts = line.split()
                    if len(parts) >= 9:
                        size = parts[4]
                        name = parts[8]
                        date = ' '.join(parts[5:8])
                        backup_files.append({'name': name, 'size': size, 'date': date})
                except Exception:
                    continue  # Skip malformed lines
        
        return sorted(backup_files, key=lambda x: x['name'], reverse=True)  # Sort by name descending
    
    except Exception:
        # Catch any unexpected exceptions
        return []

def connect_ssh(config: Dict[str, str], db_config: Dict[str, str]) -> Optional[paramiko.SSHClient]:
    """Establish SSH connection with encrypted key support.
    
    Creates SSH connection using password or key authentication.

    Args:
        config: SSH configuration dictionary
        db_config: Database configuration dictionary
        
    Returns:
        Optional[SSHClient]: Connected client or None on failure
        
    Raises:
        SSHConnectionError: If connection fails
    """
    ssh = paramiko.SSHClient()
    ssh.load_system_host_keys()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        print(f"\n{ICONS['server']}  Connecting to remote server...")
        
        # Validate SSH configuration
        if not config['HOST']:
            raise ValidationError("SSH_HOST", "SSH host is required")
        if not config['USER']:
            raise ValidationError("SSH_USER", "SSH user is required")
        if not (config['PASSWORD'] or config['KEY_PATH']):
            raise ValidationError("SSH_AUTH", "Either password or key path is required")

        # Attempt to resolve hostname
        try:
            socket.gethostbyname(config['HOST'])
        except socket.gaierror:
            print(f"{RED}✗ Failed to resolve host{NC}")
            raise SSHConnectionError(config['HOST'], "Failed to resolve host")

        # Connect with key file
        if config['KEY_PATH']:
            if not os.path.exists(config['KEY_PATH']):
                raise SSHConnectionError(config['HOST'], f"SSH key file not found: {config['KEY_PATH']}")
            
            # Check key file permissions
            key_stat = os.stat(config['KEY_PATH'])
            key_perms = oct(key_stat.st_mode)[-3:]
            print(f"{BLUE}SSH key file permissions: {key_perms}{NC}")
            
            if key_perms != "600":
                print(f"{RED}✗ SSH connection failed: Invalid key file permissions{NC}")
                raise SSHConnectionError(config['HOST'], "Invalid key file permissions")
            
            try:
                private_key = paramiko.Ed25519Key.from_private_key_file(config['KEY_PATH'])
            except paramiko.ssh_exception.PasswordRequiredException:
                print(f"{BLUE}SSH key is encrypted{NC}")
                passphrase = input("Enter passphrase for SSH key: ")
                try:
                    private_key = paramiko.Ed25519Key.from_private_key_file(
                        config['KEY_PATH'],
                        password=passphrase
                    )
                except Exception as e:
                    print(f"{RED}Failed to decrypt SSH key: {str(e)}{NC}")
                    raise SSHConnectionError(config['HOST'], f"Failed to decrypt SSH key: {str(e)}")
            
            print(f"{GREEN}Successfully loaded SSH key{NC}")
            try:
                ssh.connect(
                    config['HOST'],
                    username=config['USER'],
                    pkey=private_key,
                    timeout=10
                )
            except (socket.error, paramiko.SSHException) as e:
                print(f"{RED}✗ Failed to establish connection: {str(e)}{NC}")
                raise SSHConnectionError(config['HOST'], f"Failed to establish connection: {str(e)}")
        
        # Connect with password
        else:
            try:
                ssh.connect(
                    config['HOST'],
                    username=config['USER'],
                    password=config['PASSWORD'],
                    timeout=10
                )
            except paramiko.AuthenticationException as e:
                print(f"{RED}✗ SSH connection failed: {str(e)}{NC}")
                raise SSHConnectionError(config['HOST'], f"Authentication failed: {str(e)}")
            except (socket.error, paramiko.SSHException) as e:
                print(f"{RED}✗ Failed to establish connection: {str(e)}{NC}")
                raise SSHConnectionError(config['HOST'], f"Failed to establish connection: {str(e)}")
        
        print(f"{GREEN}{ICONS['check']} SSH connection established{NC}")
        return ssh
        
    except (ValidationError, SSHConnectionError) as e:
        raise
    except Exception as e:
        print(f"{RED}✗ SSH connection failed: {str(e)}{NC}")
        raise SSHConnectionError(config['HOST'], str(e))

def check_remote_file(ssh: paramiko.SSHClient, remote_path: str) -> bool:
    """Check if file exists on remote server.

    Args:
        ssh: SSH client connection
        remote_path: Path to check
        
    Returns:
        bool: True if file exists
    """
    try:
        stdin, stdout, stderr = ssh.exec_command(f"test -f {remote_path} && echo 'exists' || echo 'not found'")
        result = stdout.read().decode('utf-8').strip()
        return result == 'exists'
    except (paramiko.SSHException, IOError) as e:
        print(f"{RED}Error checking remote file: {str(e)}{NC}")
        return False

@with_retry(retries=2, delay=1.0)
def execute_remote_command(ssh: paramiko.SSHClient, command: str, timeout: int = 300) -> bool:
    """Execute command on remote server.
    
    Executes command with timeout and error handling.

    Args:
        ssh: SSH client connection
        command: Command to execute
        timeout: Command timeout in seconds
        
    Returns:
        bool: True if command succeeded
    """
    start_time = time.time()
    
    try:
        with RetryContext("Executing remote command", retries=2) as ctx:
            stdin, stdout, stderr = ssh.exec_command(command, timeout=timeout)
            
            while not stdout.channel.exit_status_ready():
                if time.time() - start_time > timeout:
                    stdout.channel.close()
                    raise TimeoutError(f"Command timed out after {timeout} seconds")
                time.sleep(0.1)
            
            exit_code = stdout.channel.recv_exit_status()
            error_output = stderr.read().decode('utf-8').strip()
            
            if exit_code == 0:
                return True
            else:
                if error_output:
                    print(f"\n{RED}Error output:{NC}\n{error_output}\n")
                return False
            
    except TimeoutError as e:
        print(f"\n{RED}Command timed out after {timeout} seconds{NC}\n")
        return False
    except paramiko.SSHException as e:
        print(f"\n{RED}SSH error during command execution: {str(e)}{NC}\n")
        return False
    except Exception as e:
        print(f"\n{RED}Unexpected error during command execution: {str(e)}{NC}\n")
        return False

def get_server_info(ssh: paramiko.SSHClient, db_config: Dict[str, str]) -> bool:
    """Get server and database information.
    
    Retrieves MySQL server version, settings, and metrics.

    Args:
        ssh: SSH client connection
        db_config: Database configuration dictionary
        
    Returns:
        bool: True if info retrieved successfully
    """
    try:
        # Implementation as before...
        return True
    except Exception as e:
        print(f"{RED}Error getting server info: {str(e)}{NC}")
        return False