import os
import socket
import pytest
import paramiko
from unittest.mock import Mock, patch
from mysql_sync_manager.exceptions import SSHConnectionError, ValidationError
from mysql_sync_manager.utils import RED, BLUE, GREEN, NC, ICONS
from mysql_sync_manager.ssh import connect_ssh, check_remote_file, list_remote_backups

@pytest.fixture
def ssh_config():
    return {
        'HOST': 'test-host',
        'USER': 'test-user',
        'PASSWORD': 'test-pass',
        'KEY_PATH': None
    }

def test_password_auth(ssh_config):
    """Test basic password authentication"""
    with patch('socket.gethostbyname', return_value='1.2.3.4'), \
         patch('paramiko.SSHClient') as mock_ssh:
        
        ssh_client = mock_ssh.return_value
        result = connect_ssh(ssh_config, {})
        
        assert result is not None
        ssh_client.connect.assert_called_once_with(
            'test-host', 
            username='test-user',
            password='test-pass',
            timeout=10
        )

def test_key_auth(tmp_path, ssh_config):
    """Test key-based authentication"""
    key_path = tmp_path / "test_key"
    key_path.write_text("test key content")

    mock_stat = Mock(st_mode=0o100600)  # Simulate 600 permissions
    mock_key = Mock()
    ssh_config.update({'KEY_PATH': str(key_path), 'PASSWORD': None})

    with patch('os.stat', return_value=mock_stat), \
         patch('socket.gethostbyname', return_value='1.2.3.4'), \
         patch('paramiko.SSHClient') as mock_ssh, \
         patch('paramiko.Ed25519Key.from_private_key_file', return_value=mock_key):
        
        result = connect_ssh(ssh_config, {})
        assert result is not None

def test_validation_errors(ssh_config):
    """Test SSH validation errors"""
    test_cases = [
        ({'HOST': ''}, "SSH host is required"),
        ({'USER': ''}, "SSH user is required"),
        ({'PASSWORD': None, 'KEY_PATH': None}, "Either password or key path is required"),
    ]

    for invalid_fields, expected_error in test_cases:
        test_config = ssh_config.copy()
        test_config.update(invalid_fields)
        
        with pytest.raises(ValidationError, match=expected_error):
            connect_ssh(test_config, {})

def test_connection_errors(ssh_config):
    """Test SSH connection error handling"""
    with patch('socket.gethostbyname') as mock_dns, \
         patch('paramiko.SSHClient') as mock_ssh:
        
        # Test DNS resolution failure
        mock_dns.side_effect = socket.gaierror
        with pytest.raises(SSHConnectionError, match="Failed to resolve host"):
            connect_ssh(ssh_config, {})

        # Test authentication failure
        mock_dns.side_effect = None
        mock_ssh.return_value.connect.side_effect = paramiko.AuthenticationException
        with pytest.raises(SSHConnectionError, match="Authentication failed"):
            connect_ssh(ssh_config, {})

def test_list_remote_backups(mock_ssh):
    """Test listing remote backups"""
    mock_ssh.exec_command.return_value = (
        Mock(),
        Mock(read=lambda: b"-rw-r--r-- 1 user group 1024 Jan 1 12:00 /backup/test.sql.gz"),
        Mock(read=lambda: b"")
    )
    
    backups = list_remote_backups(mock_ssh, '/backup')
    assert len(backups) == 1
    assert backups[0]['name'] == '/backup/test.sql.gz'