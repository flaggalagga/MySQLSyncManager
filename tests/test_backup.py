import os
import gzip
import pytest
import paramiko
from unittest.mock import Mock, patch

from utils import SpinnerProgress
from exceptions import BackupError, ValidationError
from backup_operations import (
    get_database_objects,
    select_backup_options,
    create_new_backup,
    extract_backup,
    download_file
)
from menu import select_backup_option

def test_get_database_objects(mock_ssh, mock_config):
    """Test retrieving database objects (tables) from MySQL."""
    
    # Create new mocks for this specific test
    stdin, stdout, stderr = Mock(), Mock(), Mock()
    stdout.read.return_value = b"table1\tBASE TABLE\ntable2\tBASE TABLE\nview1\tVIEW"
    stderr.read.return_value = b""
    
    # Override the default mock behavior for this test
    mock_ssh.exec_command.side_effect = [(stdin, stdout, stderr)]
    
    tables = get_database_objects(mock_ssh, mock_config)
    assert len(tables) == 2
    assert 'table1' in tables
    assert 'table2' in tables
    assert 'view1' not in tables

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

def test_select_backup_options_full_backup(mock_ssh, mock_config, monkeypatch):  # Added mock_config parameter
    """Test selecting full backup option."""
   
    # Mock user choosing full backup (option 1)
    monkeypatch.setattr('builtins.input', lambda _: '1')
    
    excluded_tables, skip_routines = select_backup_options(mock_ssh, mock_config)
    assert excluded_tables == []
    assert skip_routines is False

def test_create_new_backup(mock_ssh, mock_config, monkeypatch):
    """Test creating a new backup."""
  
    with patch('backup_operations.execute_remote_command', return_value=True), \
         patch('backup_operations.select_backup_options', return_value=([], False)), \
         patch('backup_operations.get_mysql_info', return_value=('8', True)):
        
        # Mock the final verification check
        mock_ssh.exec_command.side_effect = [
            (Mock(), Mock(read=lambda: b"-rw-r--r-- 1 user user 1024 Jan 1 12:00 /backup/test_db-export-20240101-120000.sql.gz"), Mock(read=lambda: b""))
        ]
        
        backup_path = create_new_backup(mock_ssh, mock_config)
        assert backup_path is not None
        assert backup_path.endswith('.sql.gz')

def test_create_new_backup_error(mock_ssh, mock_config, monkeypatch):
    """Test backup creation with errors."""
 
    # Mock the backup process to fail at directory creation
    with patch('backup_operations.get_mysql_info', return_value=('8', True)), \
         patch('backup_operations.select_backup_options', return_value=([], False)), \
         patch('backup_operations.execute_remote_command') as mock_exec:
        
        # Make the first call (mkdir) return False to simulate failure
        mock_exec.return_value = False
        
        # Should fail with BackupError when directory creation fails
        backup_path = create_new_backup(mock_ssh, mock_config)
        assert backup_path is None  # Should return None on failure

def test_create_new_backup_with_mysql_error(mock_ssh, mock_config):
    """Test backup creation with MySQL error."""
  
    # Mock MySQL command to fail
    mock_ssh.exec_command.side_effect = Exception("MySQL connection failed")
    
    # Should handle MySQL error gracefully
    backup_path = create_new_backup(mock_ssh, mock_config)
    assert backup_path is None

def test_create_new_backup_with_dump_error(mock_ssh, mock_config):
    """Test backup creation failing at dump stage."""
    from backup_operations import create_new_backup
    import backup_operations
    
    # Make MySQL version check succeed but dump fail
    mock_ssh.exec_command.side_effect = [
        # MySQL version
        (Mock(), Mock(read=lambda: b"8.0.26"), Mock(read=lambda: b"")),
        # MySQL variables
        (Mock(), Mock(read=lambda: b""), Mock(read=lambda: b"")),
        # Grants check
        (Mock(), Mock(read=lambda: b"GRANT ALL"), Mock(read=lambda: b"")),
        # Directory creation (succeeds)
        (Mock(), Mock(read=lambda: b""), Mock(read=lambda: b"")),
        # Dump command (fails)
        (Mock(), Mock(read=lambda: b""), Mock(read=lambda: b"Dump failed"))
    ]
    
    # Mock commands to fail after initial checks
    with patch('backup_operations.execute_remote_command', side_effect=[True, False]):
        backup_path = create_new_backup(mock_ssh, mock_config)
        assert backup_path is None

def test_create_new_backup_validation_error(mock_ssh, mock_config):
    """Test backup creation with validation error."""
   
    # Test with invalid config
    invalid_config = mock_config.copy()
    invalid_config['MYSQL_EXPORT_BACKUP_DIR'] = None
    
    # Override default mocks with proper sequence
    mock_ssh.exec_command.side_effect = [
        # MySQL version
        (Mock(), Mock(read=lambda: b"8.0.26"), Mock(read=lambda: b"")),
        # MySQL variables
        (Mock(), Mock(read=lambda: b"character_set_server\tutf8mb4"), Mock(read=lambda: b"")),
        # Grants check
        (Mock(), Mock(read=lambda: b"GRANT ALL"), Mock(read=lambda: b""))
    ]
    
    with patch('backup_operations.execute_remote_command', return_value=False):
        backup_path = create_new_backup(mock_ssh, invalid_config)
        assert backup_path is None

def test_create_new_backup_mysql_error(mock_ssh, mock_config):
    """Test backup creation with MySQL error."""
    
    # Mock MySQL command to fail
    stdin, stdout, stderr = Mock(), Mock(), Mock()
    stdout.read.return_value = b""
    stderr.read.return_value = b"MySQL Error"
    mock_ssh.exec_command.side_effect = [(stdin, stdout, stderr)]
    
    backup_path = create_new_backup(mock_ssh, mock_config)
    assert backup_path is None


def test_select_backup_option_new_backup(mock_ssh, mock_config, monkeypatch):
    """Test selecting new backup option."""
 
    # Mock user selecting "Create new backup" (option 1)
    monkeypatch.setattr('builtins.input', lambda _: '1')
    
    with patch('menu.create_new_backup', return_value='/path/to/new/backup.sql.gz'):
        result = select_backup_option(mock_ssh, mock_config)
        assert result == '/path/to/new/backup.sql.gz'

def test_select_backup_option_existing_backup(mock_ssh, mock_config, monkeypatch):
    """Test selecting existing backup."""
      
    # Mock user selecting "Use existing backup" (option 2) then selecting first backup
    inputs = iter(['2', '1'])
    monkeypatch.setattr('builtins.input', lambda _: next(inputs))
    
    # Mock listing existing backups
    backups = [
        {'name': '/backup/test1.sql.gz', 'size': '1.2M', 'date': '2024-01-01'},
        {'name': '/backup/test2.sql.gz', 'size': '1.5M', 'date': '2024-01-02'}
    ]
    
    with patch('menu.list_remote_backups', return_value=backups):
        result = select_backup_option(mock_ssh, mock_config)
        assert result == '/backup/test1.sql.gz'

def test_select_backup_option_custom_path(mock_ssh, mock_config, monkeypatch):
    """Test selecting custom backup path."""
 
    # Mock user selecting "Custom path" (option 3) then entering path
    inputs = iter(['3', '/custom/path/backup.sql.gz'])
    monkeypatch.setattr('builtins.input', lambda _: next(inputs))
    
    with patch('menu.check_remote_file', return_value=True):
        result = select_backup_option(mock_ssh, mock_config)
        assert result == '/custom/path/backup.sql.gz'

def test_select_backup_option_back(mock_ssh, mock_config, monkeypatch):
    """Test selecting back option."""
  
    monkeypatch.setattr('builtins.input', lambda _: 'b')
    result = select_backup_option(mock_ssh, mock_config)
    assert result == 'back'

def test_select_backup_option_quit(mock_ssh, mock_config, monkeypatch):
    """Test selecting quit option."""
  
    monkeypatch.setattr('builtins.input', lambda _: 'q')
    with pytest.raises(SystemExit):
        select_backup_option(mock_ssh, mock_config)

def test_create_new_backup_invalid_mysql(mock_ssh, mock_config):
    """Test backup creation with invalid MySQL version."""
  
    with patch('backup_operations.get_mysql_info', return_value=(None, False)):
        # Should fail gracefully when MySQL version check fails
        backup_path = create_new_backup(mock_ssh, mock_config)
        assert backup_path is None


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


def test_get_database_objects_advanced_scenarios(mock_ssh, mock_config):
    """Test advanced scenarios for get_database_objects"""
    # Scenario 1: Mixed object types with complex output
    test_cases = [
        # Output with mixed object types
        {
            'output': b"table1\tBASE TABLE\ntable2\tVIEW\nsp1\tPROCEDURE\ntable3\tBASE TABLE",
            'expected_tables': ['table1', 'table3']
        },
        # Output with special characters and spaces
        {
            'output': b"my_table\tBASE TABLE\n'special-table'\tBASE TABLE\nview1\tVIEW",
            'expected_tables': ['my_table', "'special-table'"]
        },
        # Empty or malformed output
        {
            'output': b"",
            'expected_tables': []
        }
    ]
    
    for case in test_cases:
        # Create mocks for SSH command
        stdin, stdout, stderr = Mock(), Mock(), Mock()
        stdout.read.return_value = case['output']
        stderr.read.return_value = b""
        
        # Override the default mock behavior for this test
        mock_ssh.exec_command.side_effect = [(stdin, stdout, stderr)]
        
        tables = get_database_objects(mock_ssh, mock_config)
        assert tables == case['expected_tables']

def test_select_backup_options_advanced_scenarios(mock_ssh, mock_config, monkeypatch):
    """Test advanced scenarios for backup option selection"""
    # Scenario to mock database objects
    def mock_get_database_objects(*args, **kwargs):
        return ['table1', 'table2', 'table3']
    
    # Scenario 1: Exclude some tables, keep routines
    with patch('backup_operations.get_database_objects', side_effect=mock_get_database_objects), \
         patch('builtins.input', side_effect=['2', 'y', '1,3', 'n']):
    
        # Call the function
        excluded_tables, skip_routines = select_backup_options(mock_ssh, mock_config)
    
        assert excluded_tables == ['table1', 'table3']
        assert skip_routines is False

    # Scenario 2: Exclude all tables
    with patch('backup_operations.get_database_objects', side_effect=mock_get_database_objects), \
         patch('builtins.input', side_effect=['2', 'y', '1,2,3', 'n']):
    
        # Call the function
        excluded_tables, skip_routines = select_backup_options(mock_ssh, mock_config)
    
        assert excluded_tables == ['table1', 'table2', 'table3']
        assert skip_routines is False

    # Scenario 3: Full backup (default)
    with patch('backup_operations.get_database_objects', side_effect=mock_get_database_objects), \
         patch('builtins.input', side_effect=['1']):
    
        # Call the function
        excluded_tables, skip_routines = select_backup_options(mock_ssh, mock_config)
    
        assert excluded_tables == []
        assert skip_routines is False

def test_create_new_backup_advanced_error_scenarios(mock_ssh, mock_config):
    """Test advanced error scenarios for create_new_backup"""
    # Scenario 1: MySQL version detection failure
    with patch('backup_operations.get_mysql_info', return_value=(None, False)), \
         patch('backup_operations.select_backup_options', return_value=([], False)):
        
        backup_path = create_new_backup(mock_ssh, mock_config)
        assert backup_path is None

    # Scenario 2: Backup directory creation failure
    with patch('backup_operations.get_mysql_info', return_value=('8', True)), \
         patch('backup_operations.select_backup_options', return_value=([], False)), \
         patch('backup_operations.execute_remote_command', side_effect=[False]):
        
        backup_path = create_new_backup(mock_ssh, mock_config)
        assert backup_path is None

def test_extract_backup_complex_scenarios(tmp_path):
    """Test advanced scenarios for backup extraction"""
    # Scenario 1: Large gzipped file
    large_content = "CREATE TABLE large_table (\n" + "id INT PRIMARY KEY,\n" * 1000 + ");"
    
    # Create a large gzipped SQL file
    gz_path = tmp_path / "large_backup.sql.gz"
    with gzip.open(gz_path, 'wt') as f:
        f.write(large_content)
    
    # Extract the backup
    extracted_path = extract_backup(str(gz_path))
    
    # Verify extraction
    assert os.path.exists(extracted_path)
    with open(extracted_path, 'r') as f:
        extracted_content = f.read()
    
    assert extracted_content == large_content
    os.remove(extracted_path)  # Clean up

    # Scenario 2: Unsupported file extension
    unsupported_path = tmp_path / "backup.txt"
    unsupported_path.write_text("Some content")
    
    with pytest.raises(BackupError, match="Unsupported file extension"):
        extract_backup(str(unsupported_path))



def test_select_backup_options_empty_objects(mock_ssh, mock_config, monkeypatch):
    """Test select_backup_options when get_database_objects returns an empty list"""
    def mock_get_database_objects(*args, **kwargs):
        return []
    
    with patch('backup_operations.get_database_objects', side_effect=mock_get_database_objects), \
         patch('builtins.input', side_effect=['2']):
        
        excluded_tables, skip_routines = select_backup_options(mock_ssh, mock_config)
        
        assert excluded_tables == []
        assert skip_routines is False

def test_select_backup_options_invalid_input(mock_ssh, mock_config, monkeypatch):
    """Test select_backup_options with invalid user input for excluding tables"""
    def mock_get_database_objects(*args, **kwargs):
        return ['table1', 'table2', 'table3']
    
    with patch('backup_operations.get_database_objects', side_effect=mock_get_database_objects), \
         patch('builtins.input', side_effect=['2', 'y', 'invalid,table4', 'n']):
        
        excluded_tables, skip_routines = select_backup_options(mock_ssh, mock_config)
        
        assert 'invalid' not in excluded_tables
        assert 'table4' not in excluded_tables

def test_download_file_failure(mock_ssh, monkeypatch):
    """Test download_file when SCPClient or ssh.open_sftp() fails"""
    mock_progress = Mock()
    
    with patch('backup_operations.SCPClient', side_effect=Exception("SCP failed")), \
         patch('paramiko.SSHClient.open_sftp', side_effect=Exception("SFTP failed")):
        
        result = download_file(mock_ssh, '/path/to/backup.sql.gz', mock_progress)
        
        assert result is None

def test_extract_backup_unsupported_extension(tmp_path):
    """Test extract_backup with an unsupported file extension"""
    unsupported_file = tmp_path / "backup.unsupported"
    unsupported_file.write_text("Unsupported content")
    
    with pytest.raises(BackupError, match="Unsupported file extension"):
        extract_backup(str(unsupported_file))

def test_create_new_backup_directory_failure(mock_ssh, mock_config):
    """Test create_new_backup when creating the backup directory fails"""
    with patch('backup_operations.execute_remote_command', return_value=False), \
         patch('backup_operations.get_mysql_info', return_value=('8', True)):
        
        backup_path = create_new_backup(mock_ssh, mock_config)
        
        assert backup_path is None

def test_create_new_backup_dump_failure(mock_ssh, mock_config):
    """Test create_new_backup when mysqldump fails"""
    with patch('backup_operations.execute_remote_command', side_effect=[True, False]), \
         patch('backup_operations.get_mysql_info', return_value=('8', True)), \
         patch('backup_operations.select_backup_options', return_value=([], False)):
        
        backup_path = create_new_backup(mock_ssh, mock_config)
        assert backup_path is None

def test_create_new_backup_compression_failure(mock_ssh, mock_config):
    """Test create_new_backup when backup compression fails"""
    with patch('backup_operations.execute_remote_command', side_effect=[True, True, False]), \
         patch('backup_operations.get_mysql_info', return_value=('8', True)), \
         patch('backup_operations.select_backup_options', return_value=([], False)):
        
        backup_path = create_new_backup(mock_ssh, mock_config)
        assert backup_path is None

def test_create_new_backup_verification_failure(mock_ssh, mock_config):
    """Test create_new_backup when backup verification fails"""
    mock_ssh.exec_command.side_effect = [
        (Mock(), Mock(read=lambda: b""), Mock(read=lambda: b""))
    ]
    
    with patch('backup_operations.execute_remote_command', return_value=True), \
         patch('backup_operations.get_mysql_info', return_value=('8', True)), \
         patch('backup_operations.select_backup_options', return_value=([], False)):
        
        backup_path = create_new_backup(mock_ssh, mock_config)
        assert backup_path is None

def test_get_database_objects_ssh_error(mock_ssh, mock_config, capsys):
    """Test get_database_objects when an SSH exception occurs"""
    mock_ssh.exec_command.side_effect = paramiko.SSHException("SSH error")

    objects = get_database_objects(mock_ssh, mock_config)

    assert objects == []
    captured = capsys.readouterr()
    assert "Error executing remote command: SSH error" in captured.out

def test_select_backup_options_ssh_error(mock_ssh, mock_config, monkeypatch, capsys):
    """Test select_backup_options when get_database_objects raises an SSHException"""
    def mock_get_database_objects(*args, **kwargs):
        raise paramiko.SSHException("SSH error")

    with patch('backup_operations.get_database_objects', side_effect=mock_get_database_objects), \
         patch('builtins.input', side_effect=['2']):

        excluded_tables, skip_routines = select_backup_options(mock_ssh, mock_config)

        assert excluded_tables == []
        assert skip_routines is False
        captured = capsys.readouterr()
        assert "Error retrieving database objects: SSH error" in captured.out

def test_create_new_backup_invalid_mysql(mock_ssh, mock_config):
    """Test create_new_backup with an invalid MySQL version"""
    with patch('backup_operations.get_mysql_info', return_value=(None, False)), \
         patch('backup_operations.select_backup_options', return_value=([], False)):
        
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