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
        'MYSQL_EXPORT_BACKUP_DIR': '/backup/dir'
    }

def test_ssh_operations(mock_ssh, tmp_path):
    from ssh import connect_ssh
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
def test_database_operations(mock_ssh, mock_config):
    """Test MySQL info and restore operations"""
    from db import get_mysql_info, restore_database
    
    # Set up mock to return a proper MySQL version string
    mock_stdout = Mock()
    mock_stdout.read.return_value = b"8.0.26"
    mock_ssh.exec_command.return_value = (
        Mock(),  # stdin
        mock_stdout,  # stdout
        Mock()  # stderr
    )
    
    version, has_privileges = get_mysql_info(mock_config, 'export', mock_ssh)
    assert version == '8'
    assert isinstance(has_privileges, bool)
    
    # Test restore
    with patch('os.path.exists', return_value=True), \
         patch('subprocess.Popen') as mock_popen:
        mock_popen.return_value.communicate.return_value = (b"", b"")
        mock_popen.return_value.returncode = 0
        
        assert restore_database('test.sql', {
            'MYSQL_IMPORT_HOST': 'localhost',
            'MYSQL_IMPORT_PORT': '3306',
            'MYSQL_IMPORT_USER': 'test-user',
            'MYSQL_IMPORT_PASSWORD': 'test-pass',
            'MYSQL_IMPORT_DATABASE': 'test_db'
        })

def test_config_and_menu(mock_ssh):
    """Test configuration loading and menu navigation"""
    from config import load_yml_config
    from menu import select_backup_option
    
    # Test config loading
    with patch('builtins.open', mock_open(read_data="""
        configurations:
          test_env:
            name: "Test Environment"
            config:
              MYSQL_EXPORT_HOST: "test-host"
    """)), patch('os.path.exists', return_value=True):
        config = load_yml_config()
        assert 'configurations' in config
        assert 'test_env' in config['configurations']
    
    # Test menu navigation
    with patch('menu.create_new_backup', return_value="/path/to/backup.sql.gz"), \
         patch('menu.list_remote_backups', return_value=[]), \
         patch('builtins.input', side_effect=["1"]), \
         patch('menu.check_remote_file', return_value=True):
        
        result = select_backup_option(mock_ssh, {'MYSQL_EXPORT_BACKUP_DIR': '/backup'})
        assert result == "/path/to/backup.sql.gz"

def test_retry_mechanisms():
    """Test retry utilities and error handling"""
    from retry_utils import with_retry, RetryContext, collect_errors
    from exceptions import DatabaseManagerError
    
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
        except Exception:
            continue
    
    assert attempts == 2
    
    # Test error collection
    success_op = lambda: None
    fail_op = lambda: exec('raise ValueError("Test")')
    errors = collect_errors([success_op, fail_op])
    assert len(errors) == 1
    assert isinstance(errors[0], ValueError)

def test_exceptions():
    """Test exception properties and chaining"""
    from exceptions import (
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
    
    # Test error chaining
    cause = ValueError("Original")
    error = DatabaseManagerError("Failed", cause)
    assert error.cause == cause

def test_exceptions_full_coverage():
    """Test complete exception paths"""
    from exceptions import RestoreError, DatabaseManagerError
    original = ValueError("Original")
    restore_error = RestoreError("operation", "message", original)
    assert restore_error.cause == original
    assert restore_error.operation == "operation"

def test_retry_decorator_coverage():
    """Test retry decorator initialization"""
    from retry_utils import with_retry
    from exceptions import DatabaseManagerError
    import pytest
    
    attempts = []
    
    @with_retry(retries=2, delay=0.1)
    def failing_operation():
        attempts.append(1)
        raise ValueError("Expected")
        
    with pytest.raises(DatabaseManagerError):
        failing_operation()
    assert len(attempts) == 3

def test_backup_operations_coverage():
    """Test backup operations edge cases"""
    from backup_operations import download_file, extract_backup
    import pytest
    
    # Test download failure
    ssh_mock = Mock()
    ssh_mock.get_transport.side_effect = Exception("Transport error")
    result = download_file(ssh_mock, "/path", Mock())
    assert result is None
    
    # Test extraction error
    with pytest.raises(Exception):
        extract_backup("nonexistent.sql.gz")

def test_retry_utils_full_coverage():
    """Test comprehensive retry utility scenarios"""
    from retry_utils import RetryContext
    from exceptions import DatabaseManagerError

    # Test RetryContext with multiple exception handling
    class ContextTestState:
        attempts = 0

    def complex_retry_operation():
        ContextTestState.attempts += 1
        if ContextTestState.attempts < 3:
            raise RuntimeError(f"Attempt {ContextTestState.attempts}")
        return "Completed"

    # Reset attempt counter
    ContextTestState.attempts = 0
    
    # We need to loop until either success or max retries
    completed = False
    while not completed and ContextTestState.attempts < 3:
        try:
            with RetryContext("Complex Retry", retries=2, exceptions=(RuntimeError,)) as ctx:
                result = complex_retry_operation()
                completed = True
        except RuntimeError:
            if ContextTestState.attempts >= 3:
                break
            continue

    assert ContextTestState.attempts == 3
    assert completed == True  # Verify we actually completed successfully