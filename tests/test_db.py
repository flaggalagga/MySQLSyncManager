#!/usr/bin/env python3
import pytest
from unittest.mock import Mock, patch

@pytest.fixture
def db_mock_config():
    """Provide standard test database configuration."""
    return {
        'MYSQL_IMPORT_HOST': 'localhost',
        'MYSQL_IMPORT_PORT': '3306',
        'MYSQL_IMPORT_USER': 'test-user',
        'MYSQL_IMPORT_PASSWORD': 'test-pass',
        'MYSQL_IMPORT_DATABASE': 'test_db',
        'HAS_PRIVILEGES': True
    }

def test_mysql_info(mock_ssh):
    """Test getting MySQL server information."""
    from db import get_mysql_info
    
    # Create basic test config
    db_config = {
        'MYSQL_EXPORT_HOST': 'test-host',
        'MYSQL_EXPORT_PORT': '3306',
        'MYSQL_EXPORT_USER': 'test-user',
        'MYSQL_EXPORT_PASSWORD': 'test-pass',
        'MYSQL_EXPORT_DATABASE': 'test_db'
    }

    # Set up all mock responses at once
    responses = [
        b"8.0.26",  # Version
        b"character_set_server\tutf8mb4",  # Variables
        b"GRANT ALL",  # Grants
        b"1024"  # Size
    ]
    mock_ssh.exec_command.return_value = (
        Mock(),
        Mock(read=lambda: responses.pop(0) if responses else b""),
        Mock(read=lambda: b"")
    )
    
    # Simple quick test
    version, has_privileges = get_mysql_info(db_config, 'export', mock_ssh)
    assert version == '8'
    assert isinstance(has_privileges, bool)

@patch('subprocess.Popen')
@patch('os.path.exists')
def test_restore_database(mock_exists, mock_popen, db_mock_config):
    """Test database restore operation."""
    from db import restore_database

    # Configure all mocks upfront
    mock_exists.return_value = True
    mock_process = Mock()
    mock_process.communicate.return_value = (b"", b"")
    mock_process.returncode = 0
    mock_popen.return_value = mock_process

    # Run test
    result = restore_database('test.sql', db_mock_config)
    assert result is True