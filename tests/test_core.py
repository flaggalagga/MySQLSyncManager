#!/usr/bin/env python3
import os
import sys
import pytest
from unittest.mock import Mock, patch, mock_open
import paramiko
from pathlib import Path

# Add the project directory to the path
project_dir = Path(__file__).parent.parent
if str(project_dir) not in sys.path:
    sys.path.append(str(project_dir))

@pytest.fixture
def mock_ssh():
    """
    Provide a mock SSH client for testing SSH operations.
    
    Returns:
        Mock: A mock SSH client with basic operations configured
    """
    with patch('paramiko.SSHClient') as mock_ssh:
        ssh_instance = Mock()
        mock_ssh.return_value = ssh_instance
        
        stdin, stdout, stderr = Mock(), Mock(), Mock()
        stdout.read.return_value = b"Test output"
        stderr.read.return_value = b""
        ssh_instance.exec_command.return_value = (stdin, stdout, stderr)
        
        yield ssh_instance

@pytest.fixture
def mock_config():
    return {
        'MYSQL_EXPORT_HOST': 'test-host',
        'MYSQL_EXPORT_PORT': '3306',
        'MYSQL_EXPORT_USER': 'test-user',
        'MYSQL_EXPORT_PASSWORD': 'test-pass',
        'MYSQL_EXPORT_DATABASE': 'test_db',
        'MYSQL_EXPORT_BACKUP_DIR': '/backup/dir',
        'MYSQL_IMPORT_HOST': 'localhost',
        'MYSQL_IMPORT_PORT': '3306',
        'MYSQL_IMPORT_DATABASE': 'test_db',
        'MYSQL_IMPORT_USER': 'test-user',
        'MYSQL_IMPORT_PASSWORD': 'test-pass',
        'HAS_PRIVILEGES': True
    }

@pytest.mark.timeout(5)
def test_ssh_operations(mock_ssh, tmp_path):
    from mysql_sync_manager.ssh import connect_ssh
    import socket
    
    with patch('socket.gethostbyname', return_value='1.2.3.4'):
        result = connect_ssh({
            'HOST': 'test-host',
            'USER': 'test-user',
            'PASSWORD': 'test-pass',
            'KEY_PATH': None
        }, {})
        
        mock_ssh.connect.assert_called_with(
            'test-host', 
            username='test-user', 
            password='test-pass', 
            timeout=10
        )

@pytest.mark.timeout(5)
def test_database_operations(mock_ssh, mock_config):
    """Test MySQL info and restore operations"""
    from mysql_sync_manager.db import get_mysql_info, restore_database
    
    # Set up mock responses for MySQL queries
    mysql_responses = [
        (Mock(), Mock(read=lambda: b"8.0.26"), Mock(read=lambda: b"")),  # Version
        (Mock(), Mock(read=lambda: b"character_set_server\tutf8mb4"), Mock(read=lambda: b"")),  # Variables
        (Mock(), Mock(read=lambda: b"GRANT ALL PRIVILEGES"), Mock(read=lambda: b"")),  # Grants
        (Mock(), Mock(read=lambda: b"1024"), Mock(read=lambda: b"")),  # Size
    ]
    mock_ssh.exec_command.side_effect = mysql_responses
    
    version, has_privileges = get_mysql_info(mock_config, 'export', mock_ssh)
    assert version == '8'
    assert isinstance(has_privileges, bool)
    
    # Test restore
    with patch('os.path.exists', return_value=True), \
         patch('subprocess.Popen') as mock_popen:
        mock_popen.return_value.communicate.return_value = (b"", b"")
        mock_popen.return_value.returncode = 0
        
        assert restore_database('test.sql', mock_config)

@pytest.mark.timeout(5)
def test_config_and_menu(mock_ssh):
    """Test configuration loading and menu navigation"""
    from mysql_sync_manager.config import load_yml_config
    from mysql_sync_manager.menu import select_backup_option
    
    # Test config loading
    test_yaml = """
        configurations:
          test_env:
            name: "Test Environment"
            config:
              MYSQL_EXPORT_HOST: "test-host"
              MYSQL_EXPORT_PORT: "3306"
              MYSQL_EXPORT_USER: "test-user"
              MYSQL_EXPORT_PASSWORD: "test-pass"
              MYSQL_EXPORT_DATABASE: "test_db"
              MYSQL_EXPORT_BACKUP_DIR: "/backup"
              MYSQL_IMPORT_HOST: "localhost"
              MYSQL_IMPORT_PORT: "3306"
              MYSQL_IMPORT_DATABASE: "local_db"
              MYSQL_IMPORT_USER: "local-user"
              MYSQL_IMPORT_PASSWORD: "local-pass"
              SSH_HOST: "test-host"
              SSH_USER: "test-user"
              SSH_PASSWORD: "test-pass"
    """
    
    with patch('builtins.open', mock_open(read_data=test_yaml)), \
         patch('os.path.exists', return_value=True):
        config = load_yml_config()
        assert 'configurations' in config
        assert 'test_env' in config['configurations']
    
    # Test menu navigation with mocked input and operations
    mock_config = {
        'MYSQL_EXPORT_HOST': 'test-host',
        'MYSQL_EXPORT_PORT': '3306',
        'MYSQL_EXPORT_USER': 'test-user',
        'MYSQL_EXPORT_PASSWORD': 'test-pass',
        'MYSQL_EXPORT_DATABASE': 'test_db',
        'MYSQL_EXPORT_BACKUP_DIR': '/backup',
        'HAS_PRIVILEGES': True
    }
    
    with patch('builtins.input', return_value='1'), \
         patch('mysql_sync_manager.menu.create_new_backup', return_value="/path/to/backup.sql.gz"), \
         patch('mysql_sync_manager.backup_operations.get_mysql_info', return_value=('8', True)):
        result = select_backup_option(mock_ssh, mock_config)
        assert result == "/path/to/backup.sql.gz"

@pytest.mark.timeout(5)
def test_retry_mechanisms():
    """Test retry utilities and error handling"""
    from mysql_sync_manager.retry_utils import with_retry, RetryContext
    from mysql_sync_manager.exceptions import DatabaseManagerError
    
    # Test retry decorator
    retry_count = 0
    @with_retry(retries=2, delay=0)
    def retry_operation():
        nonlocal retry_count
        retry_count += 1
        if retry_count < 2:
            raise ValueError("Test error")
        return "success"
    
    assert retry_operation() == "success"
    assert retry_count == 2
    
    # Test RetryContext
    attempts = 0
    ctx = RetryContext("Test", retries=2, delay=0)
    
    while attempts < 2:
        try:
            with ctx:
                attempts += 1
                if attempts == 1:
                    raise Exception("First attempt")
                break
        except Exception:
            continue
    
    assert attempts == 2

@pytest.mark.timeout(5)
def test_exceptions():
    """Test exception properties and chaining"""
    from mysql_sync_manager.exceptions import (
        DatabaseManagerError, SSHConnectionError, 
        DatabaseConnectionError, BackupError, 
        ConfigurationError, ValidationError
    )
    
    # Test basic error properties
    ssh_error = SSHConnectionError("test-host", "Connection failed")
    assert ssh_error.host == "test-host"
    assert "Connection failed" in str(ssh_error)
    
    db_error = DatabaseConnectionError("localhost", "3306", "Access denied")
    assert db_error.host == "localhost"
    assert db_error.port == "3306"
    
    backup_error = BackupError("compression", "Failed")
    assert backup_error.operation == "compression"
    
    config_error = ConfigurationError("yaml", "Invalid syntax")
    assert config_error.config_type == "yaml"
    
    validation_error = ValidationError("field", "Invalid")
    assert validation_error.field == "field"

@pytest.mark.timeout(5)
def test_main_nested_exception_handling():
    """Test main's nested exception handling"""
    from mysql_sync_manager.main import main
    ssh_mock = Mock()
    
    with patch('mysql_sync_manager.main.setup_configuration') as mock_setup, \
         patch('mysql_sync_manager.main.establish_ssh_connection') as mock_ssh, \
         patch('mysql_sync_manager.main.run_backup_workflow') as mock_workflow, \
         patch('mysql_sync_manager.main.print_header'), \
         patch('mysql_sync_manager.main.atexit.register'):
        
        class ComplexError(Exception):
            pass
        
        def raise_error(*args, **kwargs):
            try:
                raise ComplexError("Inner error")
            except ComplexError as e:
                raise RuntimeError("Outer error") from e
        
        mock_setup.side_effect = [True, True, KeyboardInterrupt()]
        mock_ssh.return_value = ssh_mock
        mock_workflow.side_effect = raise_error
        
        with pytest.raises(SystemExit):
            main()
        
        assert mock_setup.call_count == 3
        ssh_mock.close.assert_called()

@pytest.mark.timeout(5)
def test_main_error_handling():
    """Test main function error handling"""
    from mysql_sync_manager.main import main
    
    with patch('mysql_sync_manager.main.setup_configuration') as mock_setup, \
         patch('mysql_sync_manager.main.print_header'), \
         patch('mysql_sync_manager.main.atexit.register'):
        
        # Create sequence that hits different error paths
        mock_setup.side_effect = [
            Exception("First error"),      # Triggers main exception handler
            ValueError("Value error"),     # Triggers another path
            KeyboardInterrupt()            # Ends test
        ]
        
        with pytest.raises(SystemExit):
            main()
        
        assert mock_setup.call_count == 3

@pytest.mark.timeout(5)
def test_main_system_exit():
    """Test main function with SystemExit exception"""
    from mysql_sync_manager.main import main
    
    with patch('mysql_sync_manager.main.setup_configuration') as mock_setup, \
         patch('mysql_sync_manager.main.print_header'), \
         patch('mysql_sync_manager.main.atexit.register'):
        
        mock_setup.side_effect = SystemExit(1)
        
        with pytest.raises(SystemExit) as exc_info:
            main()
        
        assert exc_info.value.code == 1