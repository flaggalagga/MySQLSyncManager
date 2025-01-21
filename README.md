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

## Build

### Prerequisites
- Docker
- Docker Compose

### Building the Application
```bash
# Build the executable
docker-compose -f docker-compose.build.yml up --build
```

This will create an executable in the `dist` directory along with a configuration file.

### Running Tests
```bash
# Run test suite
docker-compose -f docker-compose.test.yml up --build
```

## Configuration

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
- Docker installed
- Linux environment (for running the executable)
- SSH access to remote server
- MySQL client installed on the system running the executable

### Docker Requirements
- Docker version 20.10 or higher
- Docker Compose version 2.0 or higher

## Project Structure
```
mysql_sync_manager/
├── main.py               # Application entry point
├── config.py            # Configuration handling
├── ssh.py               # SSH operations
├── db.py                # Database operations
├── backup_operations.py # Backup file handling
└── menu.py              # User interaction menu
```

## Development

### Building for Development
```bash
# Build the application
docker-compose -f docker-compose.build.yml up --build

# Run tests
docker-compose -f docker-compose.test.yml up --build
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