#!/usr/bin/env python3
import pytest
from unittest.mock import Mock, patch

from mysql_sync_manager.db import restore_database

@pytest.fixture
def mock_config():
    """Provide standard test database configuration."""
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
        'HAS_PRIVILEGES': True  # Add this
    }

def test_mysql_info(mock_ssh):
    """Test getting MySQL server information."""
    from mysql_sync_manager.db import get_mysql_info
    
    # Create test config with all required fields
    db_config = {
        'MYSQL_EXPORT_HOST': 'test-host',
        'MYSQL_EXPORT_PORT': '3306',
        'MYSQL_EXPORT_USER': 'test-user',
        'MYSQL_EXPORT_PASSWORD': 'test-pass',
        'MYSQL_EXPORT_DATABASE': 'test_db',
        'MYSQL_EXPORT_BACKUP_DIR': '/backup',
        'HAS_PRIVILEGES': True  # Add this
    }

    # Set up the mock responses in correct order
    responses = [
        b"8.0.26\n",  # Version query
        b"character_set_server\tutf8mb4\n", # Variables
        b"GRANT ALL PRIVILEGES\n",  # Grants
        b"1024\n"  # Size
    ]
    
    def mock_read():
        return responses.pop(0) if responses else b""
    
    mock_ssh.exec_command.return_value = (
        Mock(),
        Mock(read=mock_read),
        Mock(read=lambda: b"")
    )
    
    version, has_privileges = get_mysql_info(db_config, 'export', mock_ssh)
    assert version == '8'
    assert has_privileges is True

@patch('subprocess.Popen')
@patch('os.path.exists')
def test_restore_database(mock_exists, mock_popen, mock_config):  # Changed from db_mock_config to mock_config
    """Test database restore operation."""
    mock_exists.return_value = True
    mock_process = Mock()
    mock_process.communicate.return_value = (b"", b"")
    mock_process.returncode = 0
    mock_popen.return_value = mock_process

    result = restore_database('test.sql', mock_config)
    assert result is True