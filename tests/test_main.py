import os
import pytest
import sys
from unittest.mock import patch, Mock, MagicMock, call

# Import the functions we want to test
from main import (
    setup_configuration,
    process_backup,
    run_backup_workflow,
    main,
    establish_ssh_connection,
    cleanup,
)

def test_main_keyboard_interrupt():
    """Test main function handling keyboard interrupt."""
    with patch('main.select_configuration', side_effect=KeyboardInterrupt()), \
         pytest.raises(SystemExit) as exc_info:
        main()
    
    # Verify the exit code is 0 for keyboard interrupt
    assert exc_info.value.code == 0

def test_setup_configuration():
    """Test configuration setup"""
    with patch('main.select_configuration') as mock_select, \
         patch('main.validate_config') as mock_validate:
        
        # Test successful setup
        mock_select.return_value = True
        mock_validate.return_value = []
        assert setup_configuration() is True
        
        # Test failed selection
        mock_select.return_value = False
        assert setup_configuration() is False
        
        # Test missing variables
        mock_select.return_value = True
        mock_validate.return_value = ['MYSQL_EXPORT_USER']
        assert setup_configuration() is False

def test_process_backup():
    """Test backup processing"""
    ssh_mock = Mock()
    with patch('main.download_file') as mock_download, \
         patch('main.extract_backup') as mock_extract, \
         patch('main.restore_database') as mock_restore, \
         patch('builtins.input', return_value='n'):
        
        mock_download.return_value = 'local.sql.gz'
        mock_extract.return_value = 'local.sql'
        mock_restore.return_value = True
        
        assert process_backup(ssh_mock, 'remote.sql.gz') is True

def test_process_backup_download_failure():
    """Test backup processing with download failure"""
    ssh_mock = Mock()
    with patch('main.download_file') as mock_download, \
         patch('builtins.input', return_value='n'):
        
        mock_download.return_value = None
        assert process_backup(ssh_mock, 'remote.sql.gz') is False

def test_run_backup_workflow():
    """Test backup workflow"""
    ssh_mock = Mock()
    with patch('main.select_backup_option') as mock_select, \
         patch('main.process_backup') as mock_process:
        
        # Test back navigation
        mock_select.return_value = 'back'
        continue_outer, continue_inner = run_backup_workflow(ssh_mock)
        assert continue_outer is True
        assert continue_inner is False
        
        # Test successful backup
        mock_select.return_value = 'remote.sql.gz'
        mock_process.return_value = True
        continue_outer, continue_inner = run_backup_workflow(ssh_mock)
        assert continue_outer is False
        assert continue_inner is False
        
        # Test failed backup
        mock_select.return_value = 'remote.sql.gz'
        mock_process.return_value = False
        continue_outer, continue_inner = run_backup_workflow(ssh_mock)
        assert continue_outer is False
        assert continue_inner is True
        
        # Test no backup selected
        mock_select.return_value = None
        continue_outer, continue_inner = run_backup_workflow(ssh_mock)
        assert continue_outer is False
        assert continue_inner is True

def test_run_backup_workflow_error():
    """Test backup workflow with error"""
    ssh_mock = Mock()
    with patch('main.select_backup_option', side_effect=Exception("Test error")):
        continue_outer, continue_inner = run_backup_workflow(ssh_mock)
        assert continue_outer is False
        assert continue_inner is True

# More test cases for main.py
def test_establish_ssh_connection():
    """Test SSH connection establishment"""
    with patch('main.connect_ssh') as mock_connect:
        # Test successful connection
        mock_ssh = Mock()
        mock_connect.return_value = mock_ssh
        assert establish_ssh_connection() == mock_ssh
        
        # Test failed connection
        mock_connect.side_effect = Exception("Connection failed")
        assert establish_ssh_connection() is None

def test_cleanup():
    """Test cleanup functionality"""
    with patch('os.listdir') as mock_listdir, \
         patch('os.remove') as mock_remove:
        
        # Test successful cleanup
        mock_listdir.return_value = ['test.sql.gz', 'test.sql', 'other.txt']
        cleanup()
        assert mock_remove.call_count == 2
        
        # Test cleanup with errors
        mock_remove.side_effect = Exception("Remove failed")
        cleanup()
        # Should not raise exception but print error

def test_process_backup_with_delete():
    """Test backup processing with remote file deletion"""
    ssh_mock = Mock()
    with patch('main.download_file') as mock_download, \
         patch('main.extract_backup') as mock_extract, \
         patch('main.restore_database') as mock_restore, \
         patch('main.execute_remote_command') as mock_execute, \
         patch('builtins.input', return_value='y'):
        
        mock_download.return_value = 'local.sql.gz'
        mock_extract.return_value = 'local.sql'
        mock_restore.return_value = True
        mock_execute.return_value = True
        
        assert process_backup(ssh_mock, 'remote.sql.gz') is True

def test_process_backup_extraction_error():
    """Test backup processing with extraction failure"""
    ssh_mock = Mock()
    with patch('main.download_file') as mock_download, \
         patch('main.extract_backup') as mock_extract, \
         patch('builtins.input', return_value='n'):
        
        mock_download.return_value = 'local.sql.gz'
        mock_extract.side_effect = Exception("Extraction failed")
        
        assert process_backup(ssh_mock, 'remote.sql.gz') is False

def test_main_full_cycle():
    """Test main function with a full successful cycle"""
    with patch('main.setup_configuration') as mock_setup, \
         patch('main.establish_ssh_connection') as mock_ssh, \
         patch('main.run_backup_workflow') as mock_workflow, \
         patch('main.print_header') as mock_header, \
         patch('main.atexit.register') as mock_register:
        
        # First iteration - successful
        mock_setup.side_effect = [True, KeyboardInterrupt()]
        mock_ssh.return_value = Mock()
        mock_workflow.return_value = (False, False)
        
        with pytest.raises(SystemExit) as exc_info:
            main()
        
        assert exc_info.value.code == 0
        mock_setup.assert_called()
        mock_ssh.assert_called()
        mock_workflow.assert_called()

def test_main_configuration_failure():
    """Test main function with configuration failure"""
    with patch('main.setup_configuration') as mock_setup, \
         patch('main.print_header') as mock_header, \
         patch('main.atexit.register') as mock_register:
        
        # First attempt fails, second raises KeyboardInterrupt
        mock_setup.side_effect = [False, KeyboardInterrupt()]
        
        with pytest.raises(SystemExit) as exc_info:
            main()
        
        assert exc_info.value.code == 0
        assert mock_setup.call_count == 2

def test_main_ssh_failure():
    """Test main function with SSH connection failure"""
    with patch('main.setup_configuration') as mock_setup, \
         patch('main.establish_ssh_connection') as mock_ssh, \
         patch('main.print_header') as mock_header, \
         patch('main.atexit.register') as mock_register:
        
        mock_setup.side_effect = [True, KeyboardInterrupt()]
        mock_ssh.return_value = None
        
        with pytest.raises(SystemExit) as exc_info:
            main()
        
        assert exc_info.value.code == 0
        mock_setup.assert_called()
        mock_ssh.assert_called()

import pytest
import sys
from unittest.mock import patch, Mock, MagicMock, call

from main import (
    setup_configuration,
    process_backup,
    run_backup_workflow,
    main,
    establish_ssh_connection,
    cleanup,
)

# Add these new test cases

def test_cleanup_with_no_files():
    """Test cleanup with no matching files"""
    with patch('os.listdir') as mock_listdir:
        mock_listdir.return_value = ['test.txt', 'other.log']
        cleanup()
        # Should complete without any removes

def test_cleanup_with_permission_error():
    """Test cleanup when permission denied"""
    with patch('os.listdir') as mock_listdir, \
         patch('os.remove') as mock_remove:
        mock_listdir.return_value = ['test.sql.gz']
        mock_remove.side_effect = PermissionError("Permission denied")
        cleanup()
        # Should handle error and continue

def test_main_unexpected_error():
    """Test main function handling unexpected error"""
    with patch('main.setup_configuration') as mock_setup, \
         patch('main.print_header') as mock_header, \
         patch('main.atexit.register') as mock_register:
        
        # First raise unexpected error, then KeyboardInterrupt to exit
        mock_setup.side_effect = [ValueError("Unexpected error"), KeyboardInterrupt()]
        
        with pytest.raises(SystemExit) as exc_info:
            main()
        
        assert exc_info.value.code == 0
        assert mock_setup.call_count == 2

def test_main_multiple_retry_then_success():
    """Test main function with multiple retries then success"""
    with patch('main.setup_configuration') as mock_setup, \
         patch('main.establish_ssh_connection') as mock_ssh, \
         patch('main.run_backup_workflow') as mock_workflow, \
         patch('main.print_header') as mock_header, \
         patch('main.atexit.register') as mock_register:
        
        # Setup fails twice, succeeds, then KeyboardInterrupt
        mock_setup.side_effect = [False, False, True, KeyboardInterrupt()]
        mock_ssh.return_value = Mock()
        mock_workflow.return_value = (False, True)  # Continue both loops
        
        with pytest.raises(SystemExit) as exc_info:
            main()
        
        assert exc_info.value.code == 0
        assert mock_setup.call_count == 4

def test_main_ssh_close_after_error():
    """Test SSH connection is properly closed after error"""
    ssh_mock = Mock()
    with patch('main.setup_configuration') as mock_setup, \
         patch('main.establish_ssh_connection') as mock_ssh, \
         patch('main.run_backup_workflow') as mock_workflow, \
         patch('main.print_header') as mock_header, \
         patch('main.atexit.register') as mock_register:
        
        mock_setup.side_effect = [True, KeyboardInterrupt()]
        mock_ssh.return_value = ssh_mock
        mock_workflow.side_effect = Exception("Workflow error")
        
        with pytest.raises(SystemExit):
            main()
        
        ssh_mock.close.assert_called_once()

def test_process_backup_with_delete_failure():
    """Test backup processing with failed remote file deletion"""
    ssh_mock = Mock()
    with patch('main.download_file') as mock_download, \
         patch('main.extract_backup') as mock_extract, \
         patch('main.restore_database') as mock_restore, \
         patch('main.execute_remote_command') as mock_execute, \
         patch('builtins.input', return_value='y'):
        
        mock_download.return_value = 'local.sql.gz'
        mock_extract.return_value = 'local.sql'
        mock_restore.return_value = True
        mock_execute.return_value = False  # Delete fails
        
        assert process_backup(ssh_mock, 'remote.sql.gz') is True

def test_run_backup_workflow_complete_cycle():
    """Test backup workflow with a complete cycle"""
    ssh_mock = Mock()
    with patch('main.select_backup_option') as mock_select, \
         patch('main.process_backup') as mock_process:
        
        # First attempt fails, second succeeds
        mock_select.side_effect = ['remote1.sql.gz', 'remote2.sql.gz']
        mock_process.side_effect = [False, True]
        
        # First run - continue both loops
        continue_outer, continue_inner = run_backup_workflow(ssh_mock)
        assert continue_outer is False
        assert continue_inner is True
        
        # Second run - success, break both loops
        continue_outer, continue_inner = run_backup_workflow(ssh_mock)
        assert continue_outer is False
        assert continue_inner is False

def test_cleanup_with_listdir_error():
    """Test cleanup when os.listdir fails"""
    with patch('os.listdir') as mock_listdir:
        mock_listdir.side_effect = OSError("Permission denied")
        cleanup()  # Should handle error gracefully and not raise

def test_main_system_exit():
    """Test main function with SystemExit exception"""
    with patch('main.setup_configuration') as mock_setup, \
         patch('main.print_header'), \
         patch('main.atexit.register'):
        mock_setup.side_effect = SystemExit(1)
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1

def test_main_nested_exception():
    """Test main function with nested exception handling"""
    ssh_mock = Mock()
    with patch('main.setup_configuration') as mock_setup, \
         patch('main.establish_ssh_connection') as mock_ssh, \
         patch('main.run_backup_workflow') as mock_workflow, \
         patch('main.print_header'), \
         patch('main.atexit.register'):
        
        # First setup succeeds, then raises nested exception, then KeyboardInterrupt
        mock_setup.side_effect = [True, True, KeyboardInterrupt()]
        mock_ssh.return_value = ssh_mock
        mock_workflow.side_effect = [RuntimeError("Nested error")]
        
        with pytest.raises(SystemExit):
            main()
        
        assert mock_setup.call_count == 3
        ssh_mock.close.assert_called()

def test_main_double_error():
    """Test main function with consecutive errors"""
    with patch('main.setup_configuration') as mock_setup, \
         patch('main.print_header'), \
         patch('main.atexit.register'):
        
        # Two different errors before KeyboardInterrupt
        mock_setup.side_effect = [
            ValueError("First error"),
            RuntimeError("Second error"),
            KeyboardInterrupt()
        ]
        
        with pytest.raises(SystemExit):
            main()
        
        assert mock_setup.call_count == 3

def test_main_with_deep_exception_handling():
    """Test main's deep exception handling and recovery"""
    with patch('main.setup_configuration') as mock_setup, \
         patch('main.establish_ssh_connection') as mock_ssh, \
         patch('main.print_header'), \
         patch('main.atexit.register'):
        
        # Create a sequence of increasingly complex errors
        class CustomError(Exception):
            pass
        
        mock_setup.side_effect = [
            CustomError("Custom error"),  # First error
            True,                        # Success
            True,                        # Success again
            KeyboardInterrupt()          # Final exit
        ]
        
        mock_ssh.side_effect = [
            Mock(),                      # Success
            Exception("SSH Error")       # Failure
        ]
        
        with pytest.raises(SystemExit) as exc_info:
            main()
        
        assert exc_info.value.code == 0
        assert mock_setup.call_count >= 3

def test_main_with_nested_exception_handling():
    """Test main's nested exception handling"""
    ssh_mock = Mock()
    with patch('main.setup_configuration') as mock_setup, \
         patch('main.establish_ssh_connection') as mock_ssh, \
         patch('main.run_backup_workflow') as mock_workflow, \
         patch('main.print_header'), \
         patch('main.atexit.register'):
        
        class ComplexError(Exception):
            pass
        
        def raise_error(*args, **kwargs):
            try:
                raise ComplexError("Inner error")
            except ComplexError as e:
                raise RuntimeError("Outer error") from e
        
        mock_setup.side_effect = [True, True, KeyboardInterrupt()]
        mock_ssh.return_value = ssh_mock
        mock_workflow.side_effect = raise_error
        
        with pytest.raises(SystemExit):
            main()
        
        assert mock_setup.call_count == 3
        ssh_mock.close.assert_called()

def test_main_with_critical_errors():
    """Test main with errors that should trigger deep error handling"""
    with patch('main.setup_configuration') as mock_setup, \
         patch('main.establish_ssh_connection') as mock_ssh, \
         patch('main.print_header'), \
         patch('main.atexit.register'):
        
        # Create a sequence that hits different error handling paths
        mock_setup.side_effect = [
            MemoryError("Out of memory"),       # Critical system error
            RuntimeError("Runtime error"),       # Standard error
            True,                               # Success
            KeyboardInterrupt()                 # Exit
        ]
        
        with pytest.raises(SystemExit):
            main()
        
        assert mock_setup.call_count == 4

def test_main_with_recursive_error():
    """Test main function with error that causes recursive retry"""
    with patch('main.setup_configuration') as mock_setup, \
         patch('main.print_header') as mock_header, \
         patch('main.atexit.register') as mock_register:
        
        # Set up a sequence: error, another error, then KeyboardInterrupt
        mock_setup.side_effect = [
            Exception("First error"),
            Exception("Second error"),
            KeyboardInterrupt()
        ]
        
        with pytest.raises(SystemExit) as exc_info:
            main()
        
        assert exc_info.value.code == 0
        assert mock_setup.call_count == 3

def test_main_exception_in_workflow():
    """Test main function with exception in backup workflow"""
    ssh_mock = Mock()
    with patch('main.setup_configuration') as mock_setup, \
         patch('main.establish_ssh_connection') as mock_ssh, \
         patch('main.run_backup_workflow') as mock_workflow, \
         patch('main.print_header') as mock_header, \
         patch('main.atexit.register') as mock_register:
        
        mock_setup.side_effect = [True, KeyboardInterrupt()]
        mock_ssh.return_value = ssh_mock
        # Raise an exception during workflow
        mock_workflow.side_effect = Exception("Workflow failed")
        
        with pytest.raises(SystemExit):
            main()
        
        ssh_mock.close.assert_called_once()
        mock_setup.assert_called()

def test_main_if_name_eq_main():
    """Test main function execution through __main__ block"""
    with patch('main.main') as mock_main:
        # Execute the module's __main__ block
        exec(compile('if __name__ == "__main__": main()', 'main.py', 'exec'))
        mock_main.assert_not_called()  # Because __name__ won't be "__main__" in test

@pytest.mark.skipif("__name__ == '__main__'")
def test_main_module_run():
    """Test main module direct execution"""
    with patch('main.main') as mock_main:
        import main
        assert hasattr(main, '__file__')


def test_main_with_recursive_retry():
    """Test main's recursive retry mechanism"""
    with patch('main.setup_configuration') as mock_setup, \
         patch('main.establish_ssh_connection') as mock_ssh, \
         patch('main.run_backup_workflow') as mock_workflow, \
         patch('main.print_header'), \
         patch('main.atexit.register'):
        
        # First raise an error that triggers recursive call
        mock_setup.side_effect = [
            RuntimeError("Runtime error"),  # First call fails
            True,                          # Second call succeeds
            KeyboardInterrupt()            # End test
        ]
        
        with pytest.raises(SystemExit):
            main()
        
        assert mock_setup.call_count == 3

def test_main_all_exception_paths():
    """Test all exception paths in main"""
    with patch('main.setup_configuration') as mock_setup, \
         patch('main.establish_ssh_connection') as mock_ssh, \
         patch('main.run_backup_workflow') as mock_workflow, \
         patch('main.print_header'), \
         patch('main.atexit.register'):
        
        # Create a sequence of errors that hit all exception handlers
        mock_setup.side_effect = [
            Exception("First error"),      # Triggers main exception handler
            ValueError("Value error"),     # Triggers another path
            KeyboardInterrupt()            # Ends test
        ]
        
        with pytest.raises(SystemExit):
            main()
        
        assert mock_setup.call_count == 3  # Fixed assertion count

def test_main_system_exit_path():
    """Test SystemExit handling in main"""
    with patch('main.setup_configuration') as mock_setup, \
         patch('main.print_header'), \
         patch('main.atexit.register'):
        
        mock_setup.side_effect = SystemExit(1)
        
        with pytest.raises(SystemExit) as exc_info:
            main()
        
        assert exc_info.value.code == 1

def test_main_execution_paths():
    """Test different main execution paths"""
    from utils import RED, NC  
    
    with patch('main.setup_configuration') as mock_setup, \
         patch('main.establish_ssh_connection') as mock_ssh, \
         patch('main.run_backup_workflow') as mock_workflow, \
         patch('main.print_header'), \
         patch('main.atexit.register'), \
         patch('builtins.print') as mock_print:

        # Create a sequence that hits different execution paths
        mock_setup.side_effect = [
            True,                          # First call succeeds
            Exception("Expected error"),    # Triggers retry
            KeyboardInterrupt()            # Ends test
        ]
        mock_ssh.side_effect = [None, Exception("SSH Error")]
        
        with pytest.raises(SystemExit):
            main()
        
        assert mock_setup.call_count == 3
        
        # Check for error message in any of the print calls
        error_msg_found = False
        for call_args in mock_print.call_args_list:
            args, _ = call_args
            if args and 'unexpected error occurred' in args[0]:
                error_msg_found = True
                break
        assert error_msg_found, "Error message not found in print calls"


def test_main_deep_error_handling():
    """Test the deepest error handling paths in main"""
    with patch('main.setup_configuration') as mock_setup, \
         patch('main.establish_ssh_connection') as mock_ssh, \
         patch('main.print_header'), \
         patch('main.atexit.register'), \
         patch('builtins.print'):
        
        def raise_complex_error(*args, **kwargs):
            try:
                raise ValueError("Inner error")
            except ValueError as e:
                raise RuntimeError("Outer error") from e

        # Set up a sequence that forces both error handling paths
        mock_setup.side_effect = [
            raise_complex_error,  # Complex nested error
            True,                 # Success on retry
            KeyboardInterrupt()   # End test
        ]

        with pytest.raises(SystemExit):
            main()
        
        assert mock_setup.call_count == 3

def test_main_extreme_error_case():
    """Test extreme error cases in main"""
    with patch('main.setup_configuration') as mock_setup, \
         patch('main.establish_ssh_connection') as mock_ssh, \
         patch('main.run_backup_workflow') as mock_workflow, \
         patch('main.print_header'), \
         patch('main.atexit.register'), \
         patch('builtins.print'):

        # Create a chain of errors that should hit all error handlers
        class ComplexError(Exception):
            pass

        def chain_error(*args, **kwargs):
            try:
                try:
                    raise ComplexError("Deep error")
                except ComplexError:
                    raise ValueError("Mid error")
            except ValueError:
                raise RuntimeError("Top error")

        mock_setup.side_effect = [
            chain_error,         # Complex error chain
            True,                # Success
            KeyboardInterrupt()  # End test
        ]

        with pytest.raises(SystemExit):
            main()

        assert mock_setup.call_count == 3

def test_main_with_chain_exceptions():
    """Test main function with chained exceptions"""
    with patch('main.setup_configuration') as mock_setup, \
         patch('main.establish_ssh_connection') as mock_ssh, \
         patch('main.run_backup_workflow') as mock_workflow, \
         patch('main.print_header'), \
         patch('main.atexit.register'), \
         patch('builtins.print'):

        # Create a sequence of errors that should hit error handlers
        def raise_error(*args, **kwargs):
            try:
                raise ValueError("Inner error")
            except ValueError:
                raise RuntimeError("Outer error")

        mock_setup.side_effect = [
            raise_error,
            True,
            KeyboardInterrupt()
        ]
        mock_ssh.return_value = Mock()

        with pytest.raises(SystemExit):
            main()

        assert mock_setup.call_count == 3

def test_main_error_handling_paths():
    """Test main's error handling paths"""
    with patch('main.setup_configuration') as mock_setup, \
         patch('main.establish_ssh_connection') as mock_ssh, \
         patch('main.run_backup_workflow') as mock_workflow, \
         patch('main.print_header'), \
         patch('main.atexit.register'), \
         patch('builtins.print'):
        
        class TestError(Exception):
            pass

        mock_setup.side_effect = [
            TestError("Test error"),
            Exception("Another error"),
            KeyboardInterrupt()
        ]

        with pytest.raises(SystemExit):
            main()

        assert mock_setup.call_count == 3

def test_main_error_with_ssh():
    """Test main's error handling with SSH"""
    ssh_mock = Mock()
    with patch('main.setup_configuration') as mock_setup, \
         patch('main.establish_ssh_connection') as mock_ssh, \
         patch('main.run_backup_workflow') as mock_workflow, \
         patch('main.print_header'), \
         patch('main.atexit.register'), \
         patch('builtins.print'):

        mock_setup.side_effect = [True, KeyboardInterrupt()]  # End test sooner
        mock_ssh.return_value = ssh_mock
        mock_workflow.side_effect = Exception("Workflow error")

        with pytest.raises(SystemExit):
            main()

        ssh_mock.close.assert_called_once()