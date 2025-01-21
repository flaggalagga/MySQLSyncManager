"""Custom exceptions for the database local manager."""
from typing import Optional

class DatabaseManagerError(Exception):
    """Base exception for all database manager errors."""
    def __init__(self, message: str, cause: Optional[Exception] = None):
        super().__init__(message)
        self.message = message
        self.cause = cause


class ConfigurationError(DatabaseManagerError):
    """Raised when there's an issue with configuration."""
    def __init__(self, config_type: str, message: str):
        super().__init__(f"Configuration error ({config_type}): {message}")
        self.config_type = config_type


class ValidationError(DatabaseManagerError):
    """Raised when input validation fails."""
    def __init__(self, field: str, message: str):
        super().__init__(f"Validation error for {field}: {message}")
        self.field = field


class SSHConnectionError(DatabaseManagerError):
    """Raised when SSH connection fails."""
    def __init__(self, host: str, message: str):
        super().__init__(f"Failed to connect to {host}: {message}")
        self.host = host


class DatabaseConnectionError(DatabaseManagerError):
    """Raised when database connection fails."""
    def __init__(self, host: str, port: str, message: str):
        super().__init__(f"Failed to connect to database at {host}:{port}: {message}")
        self.host = host
        self.port = port


class BackupError(DatabaseManagerError):
    """Raised when backup operation fails."""
    def __init__(self, operation: str, message: str):
        super().__init__(f"Backup {operation} failed: {message}")
        self.operation = operation


class RestoreError(DatabaseManagerError):
    """Raised when restore operation fails."""
    def __init__(self, operation: str, message: str):
        super().__init__(f"Restore {operation} failed: {message}")
        self.operation = operation