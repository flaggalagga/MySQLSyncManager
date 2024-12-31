import pytest
from unittest.mock import Mock, patch
import signal

# Set up a timeout for all tests
@pytest.fixture(autouse=True)
def timeout():
    def handler(signum, frame):
        raise Exception("Test timeout!")
    # Set the signal handler and a 5-second alarm
    signal.signal(signal.SIGALRM, handler)
    signal.alarm(5)
    yield
    signal.alarm(0)  # Disable the alarm

@pytest.fixture
def mock_ssh():
    """Provide a mock SSH client with basic responses."""
    with patch('paramiko.SSHClient') as mock_ssh:
        ssh_instance = Mock()
        mock_ssh.return_value = ssh_instance
        
        # Set up default responses
        stdin, stdout, stderr = Mock(), Mock(), Mock()
        stdout.read.return_value = b"test"
        stderr.read.return_value = b""
        ssh_instance.exec_command.return_value = (stdin, stdout, stderr)
        
        yield ssh_instance

@pytest.fixture
def mock_config():
    """Provide basic mock configuration."""
    return {
        'MYSQL_EXPORT_HOST': 'test-host',
        'MYSQL_EXPORT_PORT': '3306',
        'MYSQL_EXPORT_USER': 'test-user',
        'MYSQL_EXPORT_PASSWORD': 'test-pass',
        'MYSQL_EXPORT_DATABASE': 'test_db',
        'MYSQL_EXPORT_BACKUP_DIR': '/backup'
    }