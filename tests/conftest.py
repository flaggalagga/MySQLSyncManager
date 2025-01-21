# tests/conftest.py
import os
import glob
import pytest
from unittest.mock import Mock, patch

@pytest.fixture(autouse=True)
def cleanup_after_test():
    """Cleanup after each test."""
    yield
    # Clean up any files that might have been created
    try:
        for f in glob.glob('*.sql*'):
            os.remove(f)
    except Exception:
        pass

@pytest.fixture
def mock_ssh():
    """Provide a mock SSH client with basic responses."""
    with patch('paramiko.SSHClient') as mock_ssh:
        ssh_instance = Mock()
        mock_ssh.return_value = ssh_instance
        
        # Set up default responses
        stdin, stdout, stderr = Mock(), Mock(), Mock()
        stdout.channel.recv_exit_status.return_value = 0
        stdout.read.return_value = b"test"
        stderr.read.return_value = b""
        ssh_instance.exec_command.return_value = (stdin, stdout, stderr)
        
        yield ssh_instance

@pytest.fixture
def mock_config():
    """Provide standard mock configuration."""
    return {
        'MYSQL_EXPORT_HOST': 'test-host',
        'MYSQL_EXPORT_PORT': '3306',
        'MYSQL_EXPORT_USER': 'test-user',
        'MYSQL_EXPORT_PASSWORD': 'test-pass',
        'MYSQL_EXPORT_DATABASE': 'test_db',
        'MYSQL_EXPORT_BACKUP_DIR': '/backup',
        'MYSQL_IMPORT_HOST': 'localhost',
        'MYSQL_IMPORT_PORT': '3306',
        'MYSQL_IMPORT_DATABASE': 'test_db',
        'MYSQL_IMPORT_USER': 'test-user',
        'MYSQL_IMPORT_PASSWORD': 'test-pass',
        'HAS_PRIVILEGES': True
    }

@pytest.fixture(autouse=True)
def mock_print(monkeypatch):
    """Suppress print output during tests."""
    monkeypatch.setattr('builtins.print', lambda *args, **kwargs: None)

@pytest.fixture(autouse=True)
def mock_filesystem():
    """Mock filesystem operations for all tests."""
    with patch('os.stat') as mock_stat, \
         patch('os.path.exists', return_value=True), \
         patch('linecache.checkcache') as mock_checkcache:
        
        # Configure mock stat result
        mock_stat_result = Mock()
        mock_stat_result.st_mode = 0o100644
        mock_stat_result.st_size = 1024
        mock_stat_result.st_mtime = 1612345678
        mock_stat.return_value = mock_stat_result
        
        # Make checkcache a no-op
        mock_checkcache.return_value = None
        
        yield