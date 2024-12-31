import os
import pytest
import socket
import paramiko
from unittest.mock import Mock, patch, call
from exceptions import SSHConnectionError, ValidationError, BackupError

from ssh import (
    connect_ssh, 
    execute_remote_command, 
    check_remote_file, 
    list_remote_backups
)

def test_ssh_connection_password(mock_ssh):
    """Test SSH connection with password authentication"""
    ssh_config = {
        'HOST': 'test-host',
        'USER': 'test-user',
        'PASSWORD': 'test-pass',
        'KEY_PATH': None
    }
    
    with patch('socket.gethostbyname', return_value='1.2.3.4'):
        result = connect_ssh(ssh_config, {})
        assert result is not None
        mock_ssh.connect.assert_called_once()

def test_ssh_connection_key_authentication(tmp_path):
    """Test SSH connection with key-based authentication"""
    key_path = tmp_path / "test_key"
    key_path.write_text("test key content")
    os.chmod(key_path, 0o600)
    
    ssh_config = {
        'HOST': 'test-host',
        'USER': 'test-user',
        'PASSWORD': None,
        'KEY_PATH': str(key_path)
    }
    
    with patch('socket.gethostbyname', return_value='1.2.3.4'), \
         patch('paramiko.SSHClient') as mock_ssh_class, \
         patch('paramiko.Ed25519Key.from_private_key_file', return_value=Mock()):
        
        # Create a mock SSH instance
        mock_ssh_instance = mock_ssh_class.return_value
        
        result = connect_ssh(ssh_config, {})
        
        assert result is not None
        # Verify SSH connection was attempted with correct parameters
        mock_ssh_instance.connect.assert_called_once_with(
            'test-host', 
            username='test-user', 
            pkey=mock_ssh_instance.connect.call_args[1]['pkey'],
            timeout=10
        )

def test_ssh_connection_validation_errors():
    """Test validation errors in SSH connection"""
    test_cases = [
        # Missing host
        ({'HOST': None, 'USER': 'user', 'PASSWORD': 'pass', 'KEY_PATH': None}, 
         "SSH host is required"),
        
        # Missing user
        ({'HOST': 'host', 'USER': None, 'PASSWORD': 'pass', 'KEY_PATH': None}, 
         "SSH user is required"),
        
        # Missing credentials
        ({'HOST': 'host', 'USER': 'user', 'PASSWORD': None, 'KEY_PATH': None}, 
         "Either password or key path is required")
    ]
    
    for config, expected_error in test_cases:
        with pytest.raises(ValidationError, match=expected_error):
            connect_ssh(config, {})

def test_remote_command_execution(mock_ssh):
    """Test remote command execution scenarios"""
    # Successful command
    mock_ssh.exec_command.return_value[1].channel.recv_exit_status.return_value = 0
    assert execute_remote_command(mock_ssh, "test command") == True
    
    # Failed command
    mock_ssh.exec_command.return_value[1].channel.recv_exit_status.return_value = 1
    assert execute_remote_command(mock_ssh, "test command") == False

def test_remote_file_check(mock_ssh):
    """Test remote file existence check"""
    # File exists
    mock_ssh.exec_command.return_value = (
        Mock(), 
        Mock(read=lambda: b"exists"), 
        Mock(read=lambda: b"")
    )
    assert check_remote_file(mock_ssh, "/path/to/file") == True
    
    # File not found
    mock_ssh.exec_command.return_value = (
        Mock(), 
        Mock(read=lambda: b"not found"), 
        Mock(read=lambda: b"")
    )
    assert check_remote_file(mock_ssh, "/path/to/file") == False

def test_list_remote_backups(mock_ssh):
    """Test listing remote backup files"""
    # Successful backup listing
    mock_ssh.exec_command.return_value = (
        Mock(), 
        Mock(read=lambda: b"-rw-r--r-- 1 user group 1024 Jan 1 12:00 /backup/test.sql.gz"), 
        Mock(read=lambda: b"")
    )
    
    backups = list_remote_backups(mock_ssh, '/backup')
    assert len(backups) == 1
    assert backups[0]['name'] == '/backup/test.sql.gz'


def test_ssh_connection_encrypted_key_with_passphrase(tmp_path, monkeypatch):
    """Test SSH connection with an encrypted key requiring passphrase"""
    # Create a mock encrypted key file
    key_path = tmp_path / "encrypted_key"
    key_path.write_text("encrypted key content")
    os.chmod(key_path, 0o600)
    
    # Simulate user input for passphrase
    monkeypatch.setattr('builtins.input', lambda _: 'test_passphrase')
    
    ssh_config = {
        'HOST': 'test-host',
        'USER': 'test-user',
        'PASSWORD': None,
        'KEY_PATH': str(key_path)
    }
    
    with patch('socket.gethostbyname', return_value='1.2.3.4'), \
         patch('paramiko.SSHClient') as mock_ssh_class, \
         patch('paramiko.Ed25519Key.from_private_key_file') as mock_key:
        
        # Simulate encrypted key scenario
        mock_key.side_effect = [
            paramiko.ssh_exception.PasswordRequiredException("Encrypted key"),
            Mock()  # Successful key load after passphrase
        ]
        
        mock_ssh_instance = mock_ssh_class.return_value
        
        result = connect_ssh(ssh_config, {})
        
        assert result is not None
        # Verify key was loaded twice (once with exception, once with passphrase)
        assert mock_key.call_count == 2

def test_ssh_connection_key_decryption_failure(tmp_path, monkeypatch):
    """Test SSH connection with key decryption failure"""
    # Create a mock key file
    key_path = tmp_path / "test_key"
    key_path.write_text("test key content")
    os.chmod(key_path, 0o600)
    
    # Simulate user input for passphrase
    monkeypatch.setattr('builtins.input', lambda _: 'wrong_passphrase')
    
    ssh_config = {
        'HOST': 'test-host',
        'USER': 'test-user',
        'PASSWORD': None,
        'KEY_PATH': str(key_path)
    }
    
    with patch('socket.gethostbyname', return_value='1.2.3.4'), \
         patch('paramiko.SSHClient') as mock_ssh_class, \
         patch('paramiko.Ed25519Key.from_private_key_file') as mock_key, \
         pytest.raises(SSHConnectionError):
        
        # Simulate multiple decryption failures
        mock_key.side_effect = [
            paramiko.ssh_exception.PasswordRequiredException("Encrypted key"),
            paramiko.ssh_exception.SSHException("Decryption failed")
        ]
        
        mock_ssh_instance = mock_ssh_class.return_value
        
        connect_ssh(ssh_config, {})

def test_ssh_connection_network_errors():
    """Test SSH connection with various network errors"""
    test_cases = [
        # Connection timeout
        {
            'ssh_config': {
                'HOST': 'test-timeout-host',
                'USER': 'test-user',
                'PASSWORD': 'test-pass',
                'KEY_PATH': None
            },
            'side_effect': socket.timeout("Connection timed out"),
            'error_message': "Connection timed out"
        },
        # Connection refused
        {
            'ssh_config': {
                'HOST': 'test-refused-host',
                'USER': 'test-user',
                'PASSWORD': 'test-pass',
                'KEY_PATH': None
            },
            'side_effect': ConnectionRefusedError("Connection refused"),
            'error_message': "Connection refused"
        }
    ]
    
    for case in test_cases:
        with patch('socket.gethostbyname', return_value='1.2.3.4'), \
             patch('paramiko.SSHClient') as mock_ssh_class:
            
            mock_ssh_instance = mock_ssh_class.return_value
            mock_ssh_instance.connect.side_effect = case['side_effect']
            
            with pytest.raises(SSHConnectionError) as exc_info:
                connect_ssh(case['ssh_config'], {})
            
            assert case['error_message'] in str(exc_info.value)

def test_execute_remote_command_with_ssh_exception(mock_ssh):
    """Test execute_remote_command with various SSH exceptions"""
    # Simulate SSH command raising an exception
    mock_ssh.exec_command.side_effect = [
        paramiko.SSHException("SSH command failed"),
        IOError("IO Error during command"),
    ]
    
    # Test SSH Exception
    result = execute_remote_command(mock_ssh, "test_command1")
    assert result is False
    
    # Test IO Error
    result = execute_remote_command(mock_ssh, "test_command2")
    assert result is False


def test_list_remote_backups_error_handling(mock_ssh):
    """Test list_remote_backups with error scenarios"""
    # Scenario 1: Empty listing
    mock_ssh.exec_command.return_value = (
        Mock(), 
        Mock(read=lambda: b""),  # Empty output
        Mock(read=lambda: b"")
    )
    
    backup_files = list_remote_backups(mock_ssh, '/backup')
    assert backup_files == []
    
    # Scenario 2: Partial or malformed output
    mock_ssh.exec_command.return_value = (
        Mock(), 
        Mock(read=lambda: b"-rw-r--r-- 1 user group invalid_malformed_line"),
        Mock(read=lambda: b"")
    )
    
    backup_files = list_remote_backups(mock_ssh, '/backup')
    assert backup_files == []
    
    # Scenario 3: Partially valid output with some invalid lines
    mock_ssh.exec_command.return_value = (
        Mock(), 
        Mock(read=lambda: (
            b"-rw-r--r-- 1 user group 1024 Jan 1 12:00 /backup/valid1.sql.gz\n"
            b"invalid line\n"
            b"-rw-r--r-- 1 user group 2048 Jan 2 13:00 /backup/valid2.sql.gz"
        )),
        Mock(read=lambda: b"")
    )
    
    backup_files = list_remote_backups(mock_ssh, '/backup')
    assert len(backup_files) == 2
    assert all('name' in f and 'size' in f and 'date' in f for f in backup_files)
    
    # Scenario 4: Simulating SSH exception during exec_command
    mock_ssh.exec_command.side_effect = paramiko.SSHException("SSH error during command")
    
    backup_files = list_remote_backups(mock_ssh, '/backup')
    assert backup_files == []
    
    # Scenario 5: Simulating SSH exception during read
    mock_ssh.exec_command.side_effect = None  # Reset side_effect
    mock_stdout = Mock()
    mock_stdout.read.side_effect = paramiko.SSHException("SSH error during read")
    mock_ssh.exec_command.return_value = (
        Mock(),  # stdin
        mock_stdout,  # stdout
        Mock()  # stderr
    )
    
    backup_files = list_remote_backups(mock_ssh, '/backup')
    assert backup_files == []

def test_check_remote_file_ssh_errors(mock_ssh):
    """Test check_remote_file with various SSH errors"""
    # Scenario 1: SSH Exception
    mock_ssh.exec_command.side_effect = paramiko.SSHException("SSH error")
    
    result = check_remote_file(mock_ssh, "/path/to/file")
    assert result is False
    
    # Scenario 2: IO Error
    mock_ssh.exec_command.side_effect = IOError("IO Error")
    
    result = check_remote_file(mock_ssh, "/path/to/file")
    assert result is False

def test_ssh_key_decryption_scenarios(tmp_path, monkeypatch):
    """Test various key decryption scenarios"""
    # Create a mock encrypted key file
    key_path = tmp_path / "encrypted_key"
    key_path.write_text("encrypted key content")
    os.chmod(key_path, 0o600)
    
    ssh_config = {
        'HOST': 'test-host',
        'USER': 'test-user',
        'PASSWORD': None,
        'KEY_PATH': str(key_path)
    }
    
    # Scenario 1: Successful decryption with first passphrase
    with patch('socket.gethostbyname', return_value='1.2.3.4'), \
         patch('paramiko.SSHClient') as mock_ssh_class, \
         patch('paramiko.Ed25519Key.from_private_key_file') as mock_key:
        
        # Simulate encrypted key scenario with successful first passphrase
        monkeypatch.setattr('builtins.input', lambda _: 'correct_passphrase')
        
        mock_key.side_effect = [
            paramiko.ssh_exception.PasswordRequiredException("Encrypted key"),
            Mock()  # Successful key load
        ]
        
        mock_ssh_instance = mock_ssh_class.return_value
        
        result = connect_ssh(ssh_config, {})
        assert result is not None

    # Scenario 2: Multiple passphrase attempts
    with patch('socket.gethostbyname', return_value='1.2.3.4'), \
         patch('paramiko.SSHClient') as mock_ssh_class, \
         patch('paramiko.Ed25519Key.from_private_key_file') as mock_key, \
         pytest.raises(SSHConnectionError):
        
        # Simulate failed passphrase attempts
        inputs = iter(['wrong_passphrase1', 'wrong_passphrase2'])
        monkeypatch.setattr('builtins.input', lambda _: next(inputs))
        
        mock_key.side_effect = [
            paramiko.ssh_exception.PasswordRequiredException("Encrypted key"),
            paramiko.ssh_exception.PasswordRequiredException("Still encrypted"),
            paramiko.ssh_exception.SSHException("Decryption failed")
        ]
        
        mock_ssh_instance = mock_ssh_class.return_value
        
        connect_ssh(ssh_config, {})

def test_ssh_connection_host_validation():
    """Test various host validation scenarios"""
    test_cases = [
        # Completely missing host
        ({
            'HOST': None,
            'USER': 'test-user',
            'PASSWORD': 'test-pass',
            'KEY_PATH': None
        }, "SSH host is required"),
        
        # Missing user
        ({
            'HOST': 'test-host',
            'USER': None,
            'PASSWORD': 'test-pass',
            'KEY_PATH': None
        }, "SSH user is required"),
        
        # No authentication method
        ({
            'HOST': 'test-host',
            'USER': 'test-user',
            'PASSWORD': None,
            'KEY_PATH': None
        }, "Either password or key path is required")
    ]
    
    for config, expected_error in test_cases:
        with pytest.raises(ValidationError, match=expected_error):
            connect_ssh(config, {})

def test_ssh_connection_authentication_failure_scenarios():
    """Test various authentication failure scenarios"""
    ssh_config = {
        'HOST': 'test-host',
        'USER': 'test-user',
        'PASSWORD': 'test-pass',
        'KEY_PATH': None
    }
    
    test_cases = [
        # Authentication Exception
        {
            'side_effect': paramiko.AuthenticationException("Invalid credentials"),
            'error_type': SSHConnectionError,
            'error_message': "Authentication failed"
        },
        # Generic SSH Exception
        {
            'side_effect': paramiko.SSHException("Generic SSH error"),
            'error_type': SSHConnectionError,
            'error_message': "Failed to establish connection"
        }
    ]
    
    for case in test_cases:
        with patch('socket.gethostbyname', return_value='1.2.3.4'), \
             patch('paramiko.SSHClient') as mock_ssh_class:
            
            mock_ssh_instance = mock_ssh_class.return_value
            mock_ssh_instance.connect.side_effect = case['side_effect']
            
            with pytest.raises(case['error_type']) as exc_info:
                connect_ssh(ssh_config, {})
            
            assert case['error_message'] in str(exc_info.value)

def test_check_remote_file_complex_scenarios(mock_ssh):
    """Test complex scenarios for check_remote_file"""
    # Scenario 1: Exact match scenarios
    test_cases = [
        # Test cases based on the actual implementation's likely behavior
        ("/path/to/file", b"exists", True),
        ("/path/to/file", b"not found", False),
        ("/path/to/file", b"", False)
    ]
    
    for remote_path, output, expected_result in test_cases:
        mock_ssh.exec_command.return_value = (
            Mock(), 
            Mock(read=lambda: output), 
            Mock(read=lambda: b"")
        )
        
        result = check_remote_file(mock_ssh, remote_path)
        assert result == expected_result, f"Failed for output: {output}"

    # Scenario 2: Error handling
    error_cases = [
        paramiko.SSHException("SSH error"),
        IOError("IO Error")
    ]
    
    for error in error_cases:
        mock_ssh.exec_command.side_effect = error
        
        result = check_remote_file(mock_ssh, "/path/to/file")
        assert result is False, f"Failed to handle {type(error).__name__}"