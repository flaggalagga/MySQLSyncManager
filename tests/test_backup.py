import os
import gzip
import pytest
import paramiko
from unittest.mock import Mock, patch

from mysql_sync_manager.utils import SpinnerProgress
from mysql_sync_manager.exceptions import BackupError, ValidationError
from mysql_sync_manager.backup_operations import (
    get_database_objects,
    select_backup_options,
    create_new_backup,
    extract_backup,
    download_file
)
from mysql_sync_manager.menu import select_backup_option

from mysql_sync_manager.utils import RED, NC

def test_get_database_objects(mock_ssh, mock_config):
    """Test retrieving database objects (tables) from MySQL."""
    stdin, stdout, stderr = Mock(), Mock(), Mock()
    stdout.read.return_value = b"table1\tBASE TABLE\ntable2\tBASE TABLE\nview1\tVIEW"
    stderr.read.return_value = b""
    
    mock_ssh.exec_command.side_effect = [(stdin, stdout, stderr)]
    
    tables = get_database_objects(mock_ssh, mock_config)
    assert len(tables) == 2
    assert 'table1' in tables
    assert 'table2' in tables

def test_get_database_objects_error(mock_ssh, mock_config):
    """Test error handling in database objects retrieval."""
  
    # Create new mocks with error response
    stdin, stdout, stderr = Mock(), Mock(), Mock()
    stdout.read.return_value = b""
    stderr.read.return_value = b"Access denied"
    
    # Override the default mock behavior
    mock_ssh.exec_command.side_effect = [(stdin, stdout, stderr)]
    
    tables = get_database_objects(mock_ssh, mock_config)
    assert tables == []  # Should return empty list on error

def test_select_backup_options_full_backup(mock_ssh, mock_config, monkeypatch):
    """Test selecting full backup option."""
   
    # Mock user choosing full backup (option 1)
    monkeypatch.setattr('builtins.input', lambda _: '1')
    
    excluded_tables, skip_routines = select_backup_options(mock_ssh, mock_config)
    assert excluded_tables == []
    assert skip_routines is False

def test_create_new_backup(mock_ssh, mock_config, monkeypatch):
    """Test creating a new backup."""
    # Set up mock responses for MySQL queries
    version_stdout = Mock()
    version_stdout.read.return_value = b"8.0.26\n"
    version_stderr = Mock()
    version_stderr.read.return_value = b""
    
    # Mock variables output
    vars_stdout = Mock()
    vars_stdout.read.return_value = b"character_set_server\tutf8mb4\ncollation_server\tutf8mb4_general_ci\n"
    vars_stderr = Mock()
    vars_stderr.read.return_value = b""
    
    # Mock grants output
    grants_stdout = Mock()
    grants_stdout.read.return_value = b"GRANT ALL PRIVILEGES ON *.* TO 'test'@'%'\n"
    grants_stderr = Mock()
    grants_stderr.read.return_value = b""
    
    # Mock size output
    size_stdout = Mock()
    size_stdout.read.return_value = b"1024\n"
    size_stderr = Mock()
    size_stderr.read.return_value = b""
    
    # Set up exec_command to return different responses in sequence
    mock_ssh.exec_command.side_effect = [
        (Mock(), version_stdout, version_stderr),  # Version query
        (Mock(), vars_stdout, vars_stderr),      # Variables query
        (Mock(), grants_stdout, grants_stderr),   # Grants query
        (Mock(), size_stdout, size_stderr),      # Size query
        # Add backup verification response
        (Mock(), 
         Mock(read=lambda: b"-rw-r--r-- 1 user user 1024 Jan 1 12:00 /backup/test_db-export-20240101-120000.sql.gz"),
         Mock(read=lambda: b""))
    ]
    
    with patch('mysql_sync_manager.backup_operations.execute_remote_command', return_value=True), \
         patch('mysql_sync_manager.backup_operations.select_backup_options', return_value=([], False)):
        
        backup_path = create_new_backup(mock_ssh, mock_config)
        assert backup_path is not None
        assert backup_path.endswith('.sql.gz')

def test_select_backup_option_custom_path(mock_ssh, mock_config, monkeypatch):
    """Test selecting custom backup path."""
    with pytest.raises(SystemExit):
        input_responses = iter(['3', '/custom/path/backup.sql.gz', 'q'])
        monkeypatch.setattr('builtins.input', lambda _: next(input_responses))
        
        with patch('mysql_sync_manager.ssh.check_remote_file', return_value=True):
            select_backup_option(mock_ssh, mock_config)

@pytest.mark.timeout(5)  # Set explicit timeout for this test
def test_select_backup_option_custom_path_cancel(mock_ssh, mock_config, monkeypatch):
    """Test canceling custom backup path selection."""
    monkeypatch.setattr('builtins.input', lambda _: 'b')  # Select back option
    
    result = select_backup_option(mock_ssh, mock_config)
    assert result == 'back'

def test_select_backup_option_custom_path_quit(mock_ssh, mock_config, monkeypatch):
    """Test quitting when selecting custom path"""
    # Create mock responses: first select custom path option (3), then quit
    input_responses = iter(['3', 'q'])
    monkeypatch.setattr('builtins.input', lambda _: next(input_responses))
    
    # Test that it raises SystemExit(0)
    with pytest.raises(SystemExit) as excinfo:
        select_backup_option(mock_ssh, mock_config)
    assert excinfo.value.code == 0

@pytest.mark.timeout(5)  # Set explicit timeout for this test
def test_select_backup_option_custom_path_file_not_found(mock_ssh, mock_config, monkeypatch):
    """Test selecting custom path when file doesn't exist."""
    # Mock inputs: first select custom path option, then provide path, then quit
    input_responses = iter(['3', '/nonexistent/path.sql.gz', 'q'])
    def mock_input(_):
        try:
            return next(input_responses)
        except StopIteration:
            return 'q'
            
    monkeypatch.setattr('builtins.input', mock_input)
    
    # Mock file check to return False (file not found)
    with patch('mysql_sync_manager.ssh.check_remote_file', return_value=False):
        with pytest.raises(SystemExit):
            select_backup_option(mock_ssh, mock_config)

def test_extract_backup(tmp_path):
    """Test backup extraction."""
    
    # Create a test gzipped SQL file
    test_sql = "CREATE TABLE test (id INT);"
    gz_path = tmp_path / "test.sql.gz"
    with gzip.open(gz_path, 'wt') as f:
        f.write(test_sql)
    
    # Extract the backup
    result_path = extract_backup(str(gz_path))
    assert result_path.endswith('.sql')
    assert os.path.exists(result_path)
    
    # Verify content
    with open(result_path) as f:
        content = f.read()
    assert content == test_sql
    
    # Cleanup
    os.remove(result_path)

def test_extract_backup_unsupported_extension(tmp_path):
    """Test extract_backup with an unsupported file extension"""
    unsupported_file = tmp_path / "backup.unsupported"
    unsupported_file.write_text("Unsupported content")
    
    with pytest.raises(BackupError, match="Unsupported file extension"):
        extract_backup(str(unsupported_file))

def test_download_file_failure(mock_ssh):
    """Test download_file when SCPClient or ssh.open_sftp() fails"""
    mock_progress = Mock()
    
    with patch('mysql_sync_manager.backup_operations.SCPClient', side_effect=Exception("SCP failed")), \
         patch('paramiko.SSHClient.open_sftp', side_effect=Exception("SFTP failed")):
        
        result = download_file(mock_ssh, '/path/to/backup.sql.gz', mock_progress)
        assert result is None

def test_get_database_objects_ssh_error(mock_ssh, mock_config, capsys):
    """Test get_database_objects when SSH exception occurs"""
    from mysql_sync_manager.utils import RED, NC
    
    # We need to patch any print function being used in the code
    with patch('mysql_sync_manager.backup_operations.print') as mock_print:
        mock_ssh.exec_command.side_effect = paramiko.SSHException("SSH error")
        objects = get_database_objects(mock_ssh, mock_config)
        
        assert objects == []
        mock_print.assert_any_call(f"{RED}Error executing remote command: SSH error{NC}")

def test_select_backup_options_ssh_error(mock_ssh, mock_config, monkeypatch, capsys):
    """Test select_backup_options when get_database_objects raises an SSHException"""
    with patch('mysql_sync_manager.backup_operations.print') as mock_print:
        def mock_get_database_objects(*args, **kwargs):
            raise paramiko.SSHException("SSH error")
        
        with patch('mysql_sync_manager.backup_operations.get_database_objects', 
                  side_effect=mock_get_database_objects), \
             patch('builtins.input', side_effect=['2']):
            
            excluded_tables, skip_routines = select_backup_options(mock_ssh, mock_config)
            
            assert excluded_tables == []
            assert skip_routines is False
            mock_print.assert_any_call(f"{RED}Error retrieving database objects: SSH error{NC}")

def test_create_new_backup_invalid_mysql(mock_ssh, mock_config):
    """Test create_new_backup with an invalid MySQL version"""
    with patch('mysql_sync_manager.backup_operations.get_mysql_info', return_value=(None, False)), \
         patch('mysql_sync_manager.backup_operations.select_backup_options', return_value=([], False)):
        
        backup_path = create_new_backup(mock_ssh, mock_config)
        assert backup_path is None

def test_extract_backup_large_file(tmp_path):
    """Test extract_backup with a large gzipped SQL file"""
    large_content = "-- Large SQL file content --\n" * 10000
    gz_path = tmp_path / "large_backup.sql.gz"
    
    with gzip.open(gz_path, 'wt') as f:
        f.write(large_content)
    
    extracted_path = extract_backup(str(gz_path))
    
    assert os.path.exists(extracted_path)
    with open(extracted_path, 'r') as f:
        extracted_content = f.read()
    
    assert extracted_content == large_content
    os.remove(extracted_path)  # Clean up