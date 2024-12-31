# MySQL Sync Manager

A comprehensive Python tool for managing MySQL database backups and synchronization across remote and local servers.

## Features

### Configuration
- YAML-based configuration with flexible database profiles
- Supports multiple database environments
- Advanced SSH authentication with key-based access

### Database Management Capabilities
- Create comprehensive MySQL database backups
- Selective backup options
- Remote server backup creation
- Local database restoration

## Configuration Example

Create a `db_configs.yml` file with your database configurations:

```yaml
configurations:
  example_config:
    name: "Example Database"
    config:
      MYSQL_EXPORT_HOST: "your.remote.host"
      MYSQL_EXPORT_PORT: "3306"
      MYSQL_EXPORT_DATABASE: "your_database"
      MYSQL_EXPORT_USER: "export_user"
      MYSQL_EXPORT_PASSWORD: "secure_password"
      MYSQL_EXPORT_BACKUP_DIR: "/path/to/backup/directory"
      MYSQL_IMPORT_HOST: "localhost"
      MYSQL_IMPORT_PORT: "3306"
      MYSQL_IMPORT_DATABASE: "local_database"
      MYSQL_IMPORT_USER: "import_user"
      MYSQL_IMPORT_PASSWORD: "local_password"
      SSH_HOST: "ssh.your.host"
      SSH_USER: "ssh_user"
      SSH_KEY_PATH: "/path/to/ssh/key"
```

## Key Features

### Backup Capabilities
- Create compressed MySQL database backups
- Selective backup options
  - Table data
  - Stored procedures
  - Triggers
  - Views
  - Events
- Supports compressed SQL files (.sql.gz)
- Option to delete remote backup after download

### Restoration Features
- Selective component restoration
- Performance-optimized import settings
- Intuitive menu navigation
- Comprehensive error handling

### Server Information
- Displays server hostname and OS details
- Shows backup directory disk space
- Provides MySQL server version information
- Displays database size
- Disk usage warnings

## Prerequisites

### System Requirements
- Python 3.10+
- Linux/macOS environment

### Dependencies
- paramiko
- mysql-connector-python
- PyYAML
- scp

## Installation

1. Clone the repository:
```bash
git clone https://github.com/flaggalagga/MySQLSyncManager.git
cd MySQLSyncManager
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

1. Configure your `db_configs.yml`
2. Run the application:
```bash
python3 -m main
```
3. Select your configuration profile
4. Choose backup or restoration options

## Development

### Project Structure
```
mysql_sync_manager/
├── main.py               # Application entry point
├── config.py             # Configuration handling
├── ssh.py                # SSH operations
├── db.py                 # Database operations
├── backup_operations.py  # Backup file handling
└── menu.py               # User interaction menu
```

### Testing
```bash
# Run tests with coverage
docker-compose -f docker-compose.test.yml up
```

## Security Considerations
- SSH key-based authentication
- Configurable authentication methods
- Minimal password exposure
- Comprehensive error handling

## Contributing
1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## Disclaimer
This tool is provided as-is. Always ensure you have proper backups before database operations.