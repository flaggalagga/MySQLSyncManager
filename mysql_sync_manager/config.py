"""Configuration handling with YAML only."""
import os
import sys
from typing import Dict, List, Optional, Any
import yaml
from mysql_sync_manager.utils import GREEN, RED, YELLOW, BLUE, BOLD, NC, ICONS
from mysql_sync_manager.exceptions import ConfigurationError, ValidationError


def get_executable_dir():
    """Get the directory of the executable or script."""
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        return os.path.dirname(sys.executable)
    else:
        # Running as script
        return os.getcwd()

# Add debug output
executable_dir = get_executable_dir()
CONFIG_PATH = os.path.join(executable_dir, 'db_configs.yml')
print(f"Looking for config file at: {CONFIG_PATH}")

# Database Configuration - initial defaults
DB_CONFIG = {
    # Export (Remote) Configuration
    'MYSQL_EXPORT_HOST': None,
    'MYSQL_EXPORT_PORT': '3306',
    'MYSQL_EXPORT_DATABASE': None,
    'MYSQL_EXPORT_USER': None,
    'MYSQL_EXPORT_PASSWORD': None,
    'MYSQL_EXPORT_BACKUP_DIR': None,
    
    # Import (Local) Configuration
    'MYSQL_IMPORT_HOST': 'mysql',
    'MYSQL_IMPORT_PORT': '3306',
    'MYSQL_IMPORT_DATABASE': None,
    'MYSQL_IMPORT_USER': None,
    'MYSQL_IMPORT_PASSWORD': None
}

# SSH Configuration - initial defaults
SSH_CONFIG = {
    'HOST': None,
    'USER': None,
    'PASSWORD': None,
    'KEY_PATH': None
}

def load_yml_config() -> Optional[Dict[str, Any]]:
    """Load and parse YAML configuration file.
    
    Reads database and SSH configuration from db_configs.yml.
    Handles both configuration parsing and basic validation.

    Returns:
        Dict: Parsed configuration dictionary containing all settings

    Raises:
        ConfigurationError: If YAML file is missing or malformed
    """
    try:
        if not os.path.exists(CONFIG_PATH):
            raise ConfigurationError(
                "yaml",
                f"Configuration file not found: {CONFIG_PATH}"
            )
            
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            content = f.read()
            # Strip any BOM and ensure proper line endings
            content = content.replace('\r\n', '\n').strip()
            try:
                config = yaml.safe_load(content)
            except yaml.YAMLError as e:
                raise ConfigurationError(
                    "yaml",
                    f"Invalid YAML format: {str(e)}"
                )
                
            if not config:
                raise ConfigurationError(
                    "yaml",
                    "Empty configuration file"
                )

            if not isinstance(config, dict):
                raise ConfigurationError(
                    "yaml",
                    "Invalid YAML structure: root must be a dictionary"
                )
                
            if 'configurations' not in config:
                raise ConfigurationError(
                    "yaml",
                    "Missing 'configurations' key in YAML"
                )
                
            return config
                
    except ConfigurationError:
        raise
    except Exception as e:
        raise ConfigurationError(
            "yaml",
            f"Error reading config file: {str(e)}"
        )

def validate_config() -> List[str]:
    """Validate required configuration values.
    
    Checks that all required database and SSH configuration values are present 
    and non-empty.

    Returns:
        List[str]: List of missing required variable names

    Raises:
        ValidationError: If critical configurations are invalid
    """
    missing_vars = []
    
    # Validate export configuration
    if not DB_CONFIG['MYSQL_EXPORT_USER']:
        missing_vars.append('MYSQL_EXPORT_USER')
    if not DB_CONFIG['MYSQL_EXPORT_PASSWORD']:
        missing_vars.append('MYSQL_EXPORT_PASSWORD')
    if not DB_CONFIG['MYSQL_EXPORT_BACKUP_DIR']:
        missing_vars.append('MYSQL_EXPORT_BACKUP_DIR')
    if not DB_CONFIG['MYSQL_EXPORT_HOST']:
        missing_vars.append('MYSQL_EXPORT_HOST')
    if not DB_CONFIG['MYSQL_EXPORT_DATABASE']:
        missing_vars.append('MYSQL_EXPORT_DATABASE')
    
    # Validate import configuration
    if not DB_CONFIG['MYSQL_IMPORT_USER']:
        missing_vars.append('MYSQL_IMPORT_USER')
    if not DB_CONFIG['MYSQL_IMPORT_PASSWORD']:
        missing_vars.append('MYSQL_IMPORT_PASSWORD')
    if not DB_CONFIG['MYSQL_IMPORT_DATABASE']:
        missing_vars.append('MYSQL_IMPORT_DATABASE')
    
    # Validate SSH config
    if not SSH_CONFIG['HOST']:
        missing_vars.append('SSH_HOST')
    if not SSH_CONFIG['USER']:
        missing_vars.append('SSH_USER')
    if not (SSH_CONFIG['PASSWORD'] or 
            (SSH_CONFIG['KEY_PATH'] and os.path.exists(SSH_CONFIG['KEY_PATH']))):
        missing_vars.append('SSH_PASSWORD or valid SSH_KEY_PATH')
        
    return missing_vars

def merge_config(base: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    """Merge two configuration dictionaries.

    Updates base configuration with new values, validating the result.

    Args:
        base: Base configuration dictionary
        updates: Dictionary with values to update/override

    Returns:
        Dict: Merged configuration dictionary

    Raises:
        ValidationError: If any merged values are empty or invalid
    """
    for key, value in updates.items():
        if value is not None:
            if isinstance(value, str) and not value.strip():
                raise ValidationError(
                    key,
                    "Configuration value cannot be empty"
                )
            base[key] = value
    return base

def select_configuration() -> bool:
    """Interactive configuration selection.
    
    Presents available configurations to user and loads selected configuration.
    
    Returns:
        bool: True if configuration was successfully selected and loaded
    """
    try:
        configs = load_yml_config()
        configurations = configs['configurations']
        
        if not configurations:
            print(f"{RED}No configurations found{NC}")
            return False

        while True:
            # ... rest of the code ...
            print(f"\n{ICONS['info']}{BOLD}  Available Configurations:{NC}")
            print(f"{'─'*50}")
            
            for i, (key, config) in enumerate(configurations.items(), 1):
                print(f"{BLUE}{i}.{NC} {config.get('name', key)} ({key})\n")
            
            print(f"{BLUE}q.{NC} {ICONS['times']} Quit")
            print(f"{'─'*50}")
            
            choice = input(f"\n{BOLD}Select configuration: {NC}").strip().lower()
            
            if choice == 'q':
                print(f"\n{YELLOW}{ICONS['info']}  Exiting...{NC}")
                sys.exit(0)
                
            try:
                choice = int(choice)
                if 1 <= choice <= len(configurations):
                    config_name = list(configurations.keys())[choice-1]
                    selected_config = configurations[config_name]
                    
                    if 'config' not in selected_config:
                        raise ConfigurationError(
                            "yaml",
                            f"Missing 'config' section in configuration: {config_name}"
                        )
                    
                    # Update database config
                    db_updates = {
                        'MYSQL_EXPORT_HOST': selected_config['config'].get('MYSQL_EXPORT_HOST'),
                        'MYSQL_EXPORT_PORT': selected_config['config'].get('MYSQL_EXPORT_PORT', '3306'),
                        'MYSQL_EXPORT_DATABASE': selected_config['config'].get('MYSQL_EXPORT_DATABASE'),
                        'MYSQL_EXPORT_USER': selected_config['config'].get('MYSQL_EXPORT_USER'),
                        'MYSQL_EXPORT_PASSWORD': selected_config['config'].get('MYSQL_EXPORT_PASSWORD'),
                        'MYSQL_EXPORT_BACKUP_DIR': selected_config['config'].get('MYSQL_EXPORT_BACKUP_DIR'),
                        'MYSQL_IMPORT_HOST': selected_config['config'].get('MYSQL_IMPORT_HOST', 'mysql'),
                        'MYSQL_IMPORT_PORT': selected_config['config'].get('MYSQL_IMPORT_PORT', '3306'),
                        'MYSQL_IMPORT_DATABASE': selected_config['config'].get('MYSQL_IMPORT_DATABASE'),
                        'MYSQL_IMPORT_USER': selected_config['config'].get('MYSQL_IMPORT_USER'),
                        'MYSQL_IMPORT_PASSWORD': selected_config['config'].get('MYSQL_IMPORT_PASSWORD')
                    }
                    
                    # Update SSH config
                    ssh_updates = {
                        'HOST': selected_config['config'].get('SSH_HOST'),
                        'USER': selected_config['config'].get('SSH_USER'),
                        'PASSWORD': selected_config['config'].get('SSH_PASSWORD'),
                        'KEY_PATH': selected_config['config'].get('SSH_KEY_PATH')
                    }
                    
                    global DB_CONFIG, SSH_CONFIG
                    DB_CONFIG = merge_config(DB_CONFIG, db_updates)
                    SSH_CONFIG = merge_config(SSH_CONFIG, ssh_updates)
                    
                    return True
                else:
                    print(f"{YELLOW}Please enter a valid option number{NC}")
                    
            except ValueError:
                print(f"{YELLOW}Please enter a valid option number{NC}")
                
    except Exception as e:
        raise ConfigurationError(
            "selection",
            f"Configuration selection failed: {str(e)}"
        ) from e
    
    return False