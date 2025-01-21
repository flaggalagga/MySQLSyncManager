import pytest
from unittest.mock import Mock, patch
from mysql_sync_manager.exceptions import SSHConnectionError

def test_main_basic_workflow():
    """Test main function with basic successful workflow"""
    ssh_mock = Mock()
    with patch('mysql_sync_manager.main.print_header'), \
         patch('mysql_sync_manager.main.setup_configuration') as mock_setup, \
         patch('mysql_sync_manager.main.establish_ssh_connection') as mock_ssh, \
         patch('mysql_sync_manager.main.run_backup_workflow') as mock_workflow, \
         patch('mysql_sync_manager.main.atexit.register'):
        
        # Setup mocks
        mock_setup.side_effect = [True, KeyboardInterrupt()]  # Success then exit
        mock_ssh.return_value = ssh_mock
        mock_workflow.return_value = (False, False)  # Complete workflow
        
        # Run test
        with pytest.raises(SystemExit) as exc_info:
            from mysql_sync_manager.main import main
            main()
        
        # Verify behavior
        assert exc_info.value.code == 0
        mock_setup.assert_called()
        mock_ssh.assert_called_once()
        mock_workflow.assert_called_once_with(ssh_mock)
        ssh_mock.close.assert_called_once()

def test_main_error_handling():
    """Test main function error handling"""
    with patch('mysql_sync_manager.main.print_header'), \
         patch('mysql_sync_manager.main.setup_configuration') as mock_setup, \
         patch('mysql_sync_manager.main.atexit.register'):
        
        # Test various error conditions
        mock_setup.side_effect = [
            Exception("Test error"),    # First attempt fails
            ValueError("Value error"),  # Second attempt fails differently
            KeyboardInterrupt()         # Exit
        ]
        
        with pytest.raises(SystemExit) as exc_info:
            from mysql_sync_manager.main import main
            main()
        
        assert exc_info.value.code == 0
        assert mock_setup.call_count == 3

def test_main_ssh_handling():
    """Test SSH connection handling in main"""
    ssh_mock = Mock()
    with patch('mysql_sync_manager.main.print_header'), \
         patch('mysql_sync_manager.main.setup_configuration') as mock_setup, \
         patch('mysql_sync_manager.main.establish_ssh_connection') as mock_ssh, \
         patch('mysql_sync_manager.main.atexit.register'):
        
        # Test SSH failure then success
        mock_setup.side_effect = [True, KeyboardInterrupt()]
        mock_ssh.side_effect = [None, ssh_mock]  # First fails, then succeeds
        
        with pytest.raises(SystemExit):
            from mysql_sync_manager.main import main
            main()
        
        mock_ssh.assert_called()

def test_backup_workflow():
    """Test backup workflow process"""
    ssh_mock = Mock()
    with patch('mysql_sync_manager.main.select_backup_option') as mock_select, \
         patch('mysql_sync_manager.main.process_backup') as mock_process:
        
        # Test successful backup
        mock_select.return_value = 'test.sql.gz'
        mock_process.return_value = True
        
        from mysql_sync_manager.main import run_backup_workflow
        continue_outer, continue_inner = run_backup_workflow(ssh_mock)
        
        assert not continue_outer
        assert not continue_inner
        mock_process.assert_called_once_with(ssh_mock, 'test.sql.gz')