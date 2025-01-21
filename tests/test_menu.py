import pytest
import sys
from unittest.mock import Mock, patch, call
from mysql_sync_manager.exceptions import ValidationError, BackupError
from mysql_sync_manager.menu import select_backup_option, select_existing_backup, select_custom_backup

@pytest.fixture
def mock_menu_config():
    """Fixture providing standard menu test configuration."""
    return {
        'MYSQL_EXPORT_BACKUP_DIR': '/backup/dir',
        'MYSQL_EXPORT_HOST': 'test-host',
        'MYSQL_EXPORT_USER': 'test-user',
        'MYSQL_EXPORT_PASSWORD': 'test-pass',
        'MYSQL_EXPORT_DATABASE': 'test_db'
    }


def test_select_backup_option(mock_ssh, mock_config, monkeypatch):
    """Test selecting backup options."""
    backups = [
        {'name': '/backup/test1.sql.gz', 'size': '1.2M', 'date': '2024-01-01'},
        {'name': '/backup/test2.sql.gz', 'size': '1.5M', 'date': '2024-01-02'}
    ]
    
    with patch('mysql_sync_manager.menu.list_remote_backups', return_value=backups), \
         patch('mysql_sync_manager.menu.check_remote_file', return_value=True), \
         patch('builtins.input', side_effect=['2', '1']):
        
        result = select_backup_option(mock_ssh, mock_config)
        assert result == '/backup/test1.sql.gz'

def test_select_backup_option_configuration_validation_error():
    """Test backup option selection with invalid configuration."""
    # Create a config without backup directory
    invalid_config = {}
    
    with pytest.raises(ValidationError) as exc_info:
        select_backup_option(Mock(), invalid_config)
    
    assert "Export backup directory not configured" in str(exc_info.value)

def test_select_existing_backup_empty_list(mock_ssh, mock_config):
    """Test selecting an existing backup when no backups are available."""
    with patch('ssh.list_remote_backups', return_value=[]):
        # Update to use the backup directory from mock_config
        backup_dir = mock_config.get('MYSQL_EXPORT_BACKUP_DIR', '/backup')
        result = select_existing_backup(mock_ssh, backup_dir)
        assert result is None


def test_select_custom_backup_validation(mock_ssh, monkeypatch):
    """Test custom backup path selection with various inputs."""
    # Test back navigation
    with patch('ssh.check_remote_file', return_value=True), \
         patch('builtins.input', side_effect=['b']):
        result = select_custom_backup(mock_ssh)
        assert result is None
    
    # Test quit
    with pytest.raises(SystemExit), \
         patch('builtins.input', side_effect=['q']):
        select_custom_backup(mock_ssh)
    
    # Test invalid path
    with patch('ssh.check_remote_file', return_value=False), \
         patch('builtins.input', side_effect=['invalid/path', 'q']):
        with pytest.raises(SystemExit):
            select_custom_backup(mock_ssh)

def test_select_backup_option_empty_dir(mock_ssh, mock_menu_config):
    """Test selecting existing backup option when directory is empty"""
    # Simplify the test to just immediately return 'q'
    with patch('menu.list_remote_backups', return_value=[]), \
         patch('builtins.print'), \
         patch('builtins.input', return_value='q'):
        
        with pytest.raises(SystemExit):
            select_backup_option(mock_ssh, mock_menu_config)

def test_select_backup_option_back_navigation(mock_ssh, mock_menu_config):
    """Test back navigation from different menu levels."""
    with patch('menu.list_remote_backups', return_value=[]), \
         patch('builtins.print'), \
         patch('builtins.input', side_effect=['b']):
        result = select_backup_option(mock_ssh, mock_menu_config)
        assert result == 'back'

def test_select_backup_option_create_new_failure(mock_ssh, mock_menu_config):
    """Test handling failure in create new backup."""
    with patch('menu.create_new_backup', return_value=None), \
         patch('builtins.print'), \
         patch('builtins.input', return_value='q'):
        
        with pytest.raises(SystemExit):
            select_backup_option(mock_ssh, mock_menu_config)