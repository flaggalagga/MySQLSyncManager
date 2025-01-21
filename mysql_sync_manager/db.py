#!/usr/bin/env python3
"""Database operations module."""
import os
import subprocess
from typing import Optional, Dict, Tuple
from paramiko import SSHClient
from mysql_sync_manager.utils import GREEN, RED, YELLOW, BLUE, BOLD, NC, ICONS, SpinnerProgress
from mysql_sync_manager.exceptions import (
    DatabaseConnectionError,
    ValidationError,
    RestoreError
)
from mysql_sync_manager.retry_utils import with_retry, RetryContext

@with_retry(retries=2, delay=1.0)
def get_mysql_info(db_config: Dict[str, str], server_type: str = 'import', ssh: Optional[SSHClient] = None) -> Tuple[Optional[str], bool]:
    """Get MySQL server information and check privileges.
    
    Gets server version and checks user privileges.

    Args:
        db_config: Database configuration dictionary
        server_type: Either 'import' or 'export'
        ssh: SSH client for export server queries
        
    Returns:
        Tuple of:
            - Optional[str]: MySQL major version or None
            - bool: Whether user has required privileges
    """
    try:
        # Determine which credentials to use
        prefix = f"MYSQL_{server_type.upper()}_"
        host = db_config[f'{prefix}HOST']
        port = db_config[f'{prefix}PORT']
        user = db_config[f'{prefix}USER']
        password = db_config[f'{prefix}PASSWORD'].replace("'", "'\\''")  # Escape password
        database = db_config[f'{prefix}DATABASE']

        # Initialize vars_dict with default values
        vars_dict = {
            'character_set_server': 'Unknown',
            'collation_server': 'Unknown',
            'max_allowed_packet': '0',
            'wait_timeout': 'Unknown'
        }

        if server_type == 'export' and ssh:
            # Execute on remote server via SSH
            mysql_cmd = f"mysql -h {host} -u{user} -p'{password}' {database}"
            
            # Get version
            stdin, stdout, stderr = ssh.exec_command(f"{mysql_cmd} -e 'SELECT VERSION()'")
            version_output = stdout.read().decode('utf-8').strip()
            version = version_output.split('\n')[-1].strip()

            # Get variables
            stdin, stdout, stderr = ssh.exec_command(
                f"{mysql_cmd} -e 'SHOW VARIABLES WHERE Variable_name IN "
                f"(\"max_allowed_packet\", \"wait_timeout\", "
                f"\"character_set_server\", \"collation_server\")'"
            )
            vars_output = stdout.read().decode('utf-8').strip()
            for line in vars_output.split('\n')[1:]:  # Skip header
                if '\t' in line:
                    var_name, var_value = line.split('\t')
                    vars_dict[var_name] = var_value

            # Get grants
            stdin, stdout, stderr = ssh.exec_command(f"{mysql_cmd} -e 'SHOW GRANTS'")
            grants = stdout.read().decode('utf-8').strip().upper()
            has_privileges = any(priv in grants for priv in [
                'SUPER', 'SYSTEM_VARIABLES_ADMIN', 'SESSION_VARIABLES_ADMIN', 
                'ALL PRIVILEGES', 'GRANT ALL', 'GRANT ALL PRIVILEGES', 
                'ALL ON *.*', 'GRANT ALL ON *.*'
            ])

            # Get database size
            stdin, stdout, stderr = ssh.exec_command(
                f"{mysql_cmd} -e 'SELECT ROUND(SUM(data_length + index_length) / 1024 / 1024, 1) "
                f"AS size FROM information_schema.tables WHERE table_schema = \"{database}\"'"
            )
            db_size_output = stdout.read().decode('utf-8').strip()
            db_size = db_size_output.split('\n')[-1].strip() if db_size_output else "Unknown"

        else:
            # Execute locally for import server
            mysql_cmd = (
                f"mysql -h {host} "
                f"-P {port} "
                f"-u{user} "
                f"-p'{password}' "
                f"-N -B"  # No headers, tab-separated
            )

            # Get version
            process = subprocess.Popen(
                f"{mysql_cmd} -e 'SELECT VERSION()'",
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = process.communicate()
            version = stdout.decode('utf-8').strip()

            # Get variables
            process = subprocess.Popen(
                f"{mysql_cmd} -e 'SHOW VARIABLES WHERE Variable_name IN "
                f"(\"max_allowed_packet\", \"wait_timeout\", "
                f"\"character_set_server\", \"collation_server\")'",
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = process.communicate()
            vars_output = stdout.decode('utf-8').strip()
            for line in vars_output.split('\n'):
                if '\t' in line:
                    var_name, var_value = line.split('\t')
                    vars_dict[var_name] = var_value

            # Get grants
            process = subprocess.Popen(
                f"{mysql_cmd} -e 'SHOW GRANTS'",
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = process.communicate()
            grants = stdout.decode('utf-8').strip().upper()
            has_privileges = any(priv in grants for priv in [
                'SUPER', 'SYSTEM_VARIABLES_ADMIN', 'SESSION_VARIABLES_ADMIN', 
                'ALL PRIVILEGES', 'GRANT ALL', 'GRANT ALL PRIVILEGES', 
                'ALL ON *.*', 'GRANT ALL ON *.*'
            ])

            # Get database size
            process = subprocess.Popen(
                f"{mysql_cmd} -e 'SELECT ROUND(SUM(data_length + index_length) / 1024 / 1024, 1) "
                f"AS size FROM information_schema.tables WHERE table_schema = \"{database}\"'",
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = process.communicate()
            db_size = stdout.decode('utf-8').strip() if stdout else "Unknown"

        # Check if privileges are explicitly disabled in config
        if db_config.get('HAS_PRIVILEGES') is False:
            has_privileges = False

        # Only display if not retrying with basic privileges
        if not db_config.get('RETRY_ATTEMPTED'):
            print(f"\n{ICONS['server']}{BOLD}  MySQL {server_type.capitalize()} Server Configuration:{NC}")
            print(f"{'─'*50}")
            
            # Server details
            print(f"{BLUE}Version:{NC} {version}")
            print(f"{BLUE}Character Set:{NC} {vars_dict['character_set_server']}")
            print(f"{BLUE}Collation:{NC} {vars_dict['collation_server']}")
            print(f"{BLUE}Max Packet Size:{NC} {int(vars_dict['max_allowed_packet']) // (1024*1024)}MB")
            print(f"{BLUE}Wait Timeout:{NC} {vars_dict['wait_timeout']}s")
            print(f"{BLUE}Database Size:{NC} {db_size}MB")
            
            # Connection details
            print(f"\n{BLUE}Host:{NC} {host}")
            print(f"{BLUE}Port:{NC} {port}")
            print(f"{BLUE}Database:{NC} {database}")
            print(f"{BLUE}User:{NC} {user}")
            
            # Add backup directory for export
            if server_type == 'export' and 'MYSQL_EXPORT_BACKUP_DIR' in db_config:
                print(f"{BLUE}{ICONS['folder']} Backup Directory:{NC} {db_config['MYSQL_EXPORT_BACKUP_DIR']}")
            
            # Show privileges status
            if db_config.get('HAS_PRIVILEGES') is False:
                print(f"\n{YELLOW}Using basic privileges for {server_type}{NC}")
            elif has_privileges:
                print(f"\n{GREEN}User has required privileges - using optimized {server_type}{NC}")
            else:
                print(f"\n{YELLOW}User has basic privileges - using standard {server_type}{NC}")
                
            print(f"{'─'*50}\n")

        return version.split('.')[0], has_privileges
        
    except Exception as e:
        print(f"{RED}Error getting MySQL information: {str(e)}{NC}")
        return None, False

@with_retry(retries=2, delay=1.0)
def restore_database(sql_file: str, db_config: Dict[str, str]) -> bool:
    """Restore database from SQL file.
    
    Restores backup using mysql client.

    Args:
        sql_file: Path to SQL file
        db_config: Database configuration dictionary
        
    Returns:
        bool: True if restore succeeded
        
    Raises:
        ValidationError: If inputs invalid
        RestoreError: If restore fails
    """
    import_progress = SpinnerProgress("Importing database")
    
    try:
        # Validate inputs
        if not sql_file or not os.path.exists(sql_file):
            raise ValidationError("sql_file", f"SQL file not found: {sql_file}")
            
        import_user = db_config.get('MYSQL_IMPORT_USER')
        import_password = db_config.get('MYSQL_IMPORT_PASSWORD')
        import_database = db_config.get('MYSQL_IMPORT_DATABASE')
        
        if not all([import_user, import_password, import_database]):
            raise ValidationError(
                "import_config",
                "Missing import configuration values"
            )

        # Get MySQL server info and check privileges
        _, has_privileges = get_mysql_info(db_config, 'import')

        # Escape password
        password = import_password.replace("'", "'\\''")
        
        # Base command options
        cmd_options = [
            f"-h {db_config['MYSQL_IMPORT_HOST']}",
            f"-P {db_config['MYSQL_IMPORT_PORT']}",
            f"-u{import_user}",
            f"-p'{password}'",
            "--max_allowed_packet=512M",
            "--default-character-set=utf8mb4",
            "--force"
        ]
        
        # Add optimization options if we have privileges
        if has_privileges and db_config.get('HAS_PRIVILEGES') is not False:
            cmd_options.extend([
                "--net_buffer_length=16384",
                "--init-command=\"SET SESSION FOREIGN_KEY_CHECKS=0; "
                "SET SESSION UNIQUE_CHECKS=0; "
                "SET SESSION SQL_MODE='NO_AUTO_VALUE_ON_ZERO'; "
                "SET SESSION sql_log_bin=0;\""
            ])
        
        # Construct the final command
        mysql_cmd = (
            f"mysql {' '.join(cmd_options)} "
            f"{import_database} "
            f"< {sql_file}"
        )
        
        # Execute restore
        import_progress.start()
        process = subprocess.Popen(
            mysql_cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = process.communicate()
        
        success = process.returncode == 0
        import_progress.stop(success)
        
        if success:
            print(f"\n{GREEN}{ICONS['check']} Database restore completed successfully!{NC}\n")
            db_config.pop('HAS_PRIVILEGES', None)
            db_config.pop('RETRY_ATTEMPTED', None)
            return True
        else:
            error_msg = stderr.decode('utf-8')
            
            # If privileged import fails, try without privileges but only once
            if has_privileges and not db_config.get('RETRY_ATTEMPTED'):
                print(f"{YELLOW}Retrying with basic privileges...{NC}")
                db_config['HAS_PRIVILEGES'] = False
                db_config['RETRY_ATTEMPTED'] = True
                return restore_database(sql_file, db_config)
                
            raise RestoreError("import", f"MySQL import failed: {error_msg}")
            
    except Exception as e:
        import_progress.stop(False)
        print(f"\n{RED}Error during restore: {str(e)}{NC}\n")
        return False