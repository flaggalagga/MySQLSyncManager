# tests/test_config.py
import pytest
from unittest.mock import patch, mock_open
from exceptions import ConfigurationError, ValidationError

def test_validate_config_success(mock_config):
    """Test successful configuration validation."""
    from config import validate_config, DB_CONFIG, SSH_CONFIG
    
    # Initialize DB_CONFIG with all required keys
    DB_CONFIG.clear()
    DB_CONFIG.update({
        'MYSQL_EXPORT_USER': 'test-user',
        'MYSQL_EXPORT_PASSWORD': 'test-pass',
        'MYSQL_EXPORT_HOST': 'test-host',
        'MYSQL_EXPORT_DATABASE': 'test_db',
        'MYSQL_EXPORT_BACKUP_DIR': '/backup',
        'MYSQL_IMPORT_USER': 'local-user',
        'MYSQL_IMPORT_PASSWORD': 'local-pass',
        'MYSQL_IMPORT_DATABASE': 'local_db'
    })
    
    # Initialize SSH_CONFIG with all required keys
    SSH_CONFIG.clear()
    SSH_CONFIG.update({
        'HOST': 'test-host',
        'USER': 'test-user',
        'PASSWORD': 'test-pass'
    })
    
    missing = validate_config()
    assert len(missing) == 0

def test_validate_config_missing_values():
    """Test configuration validation with missing values."""
    from config import validate_config, DB_CONFIG, SSH_CONFIG
    
    # Initialize with empty values
    DB_CONFIG.clear()
    DB_CONFIG.update({
        'MYSQL_EXPORT_USER': None,
        'MYSQL_EXPORT_PASSWORD': None,
        'MYSQL_EXPORT_HOST': None,
        'MYSQL_EXPORT_DATABASE': None,
        'MYSQL_EXPORT_BACKUP_DIR': None,
        'MYSQL_IMPORT_USER': None,
        'MYSQL_IMPORT_PASSWORD': None,
        'MYSQL_IMPORT_DATABASE': None
    })
    
    SSH_CONFIG.clear()
    SSH_CONFIG.update({
        'HOST': None,
        'USER': None,
        'PASSWORD': None,
        'KEY_PATH': None
    })
    
    missing = validate_config()
    assert 'MYSQL_EXPORT_USER' in missing
    assert 'MYSQL_EXPORT_PASSWORD' in missing
    assert 'SSH_HOST' in missing

def test_merge_config_validation():
    """Test configuration merging with validation."""
    from config import merge_config
    
    base = {'key1': 'value1', 'key2': None}
    updates = {'key2': 'value2', 'key3': 'value3'}
    
    result = merge_config(base, updates)
    assert result['key1'] == 'value1'
    assert result['key2'] == 'value2'
    assert result['key3'] == 'value3'

def test_merge_config_empty_value():
    """Test merging config with empty value."""
    from config import merge_config
    
    base = {'key1': 'value1'}
    updates = {'key1': ''}
    
    with pytest.raises(ValidationError) as exc:
        merge_config(base, updates)
    assert "Configuration value cannot be empty" in str(exc.value)

def test_select_configuration_success():
    """Test successful configuration selection."""
    from config import select_configuration
    
    yaml_content = """
    configurations:
      test:
        name: "Test Environment"
        config:
          MYSQL_EXPORT_HOST: "test-host"
          MYSQL_EXPORT_DATABASE: "test_db"
          MYSQL_EXPORT_USER: "test-user"
          MYSQL_EXPORT_PASSWORD: "test-pass"
          MYSQL_EXPORT_BACKUP_DIR: "/backup"
          MYSQL_IMPORT_USER: "local-user"
          MYSQL_IMPORT_PASSWORD: "local-pass"
          MYSQL_IMPORT_DATABASE: "local_db"
          SSH_HOST: "test-ssh"
          SSH_USER: "test-user"
    """
    
    with patch('builtins.open', mock_open(read_data=yaml_content)), \
         patch('os.path.exists', return_value=True), \
         patch('builtins.input', return_value='1'):
        
        result = select_configuration()
        assert result is True

def test_select_configuration_quit():
    """Test configuration selection with quit option."""
    from config import select_configuration
    import sys
    
    yaml_content = """
    configurations:
      test:
        name: "Test Environment"
        config:
          MYSQL_EXPORT_HOST: "test-host"
          MYSQL_EXPORT_DATABASE: "test_db"
    """
    
    with patch('builtins.open', mock_open(read_data=yaml_content)), \
         patch('os.path.exists', return_value=True), \
         patch('builtins.input', return_value='q'), \
         pytest.raises(SystemExit):
        
        select_configuration()