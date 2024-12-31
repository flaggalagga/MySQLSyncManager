# MySQL Sync Manager

A Python tool for managing MySQL database backups and restorations. This tool allows you to create backups from remote databases and restore them to local or other MySQL instances, with support for various configurations and selective restore options.

## Features

### Configuration Support
- Flexible configuration with `db_configs.yml`
- Support for multiple database configurations in YAML
- Automatic MySQL version detection (5.7 and 8.0 support)
- Support for SSH key authentication (including encrypted keys)

### Server Information
- Displays server hostname and OS version
- Shows disk space information for backup directory
- Displays disk usage warnings when space is low
- Shows MySQL server version and database size
- Works across different hosting providers and locales

### Backup Features
- Create new MySQL database backups on remote servers
- List and select from existing backup files
- Support for compressed SQL files (.sql.gz)
- Option to delete remote backup after download

### Restore Features
- Selective component restoration:
  - Table data (always included)
  - Stored procedures and functions (optional)
  - Triggers (optional)
  - Views (optional)
  - Events (optional)
- Performance-optimized import settings
- Progress indicators with colorful terminal output
- Clean menu navigation system

## Directory Structure

```
scripts/
└── python/
    └── db_local_man/
        ├── __init__.py         # Package initialization
        ├── main.py            # Main orchestration
        ├── config.py          # Configuration handling
        ├── utils.py           # Common utilities and progress indicators
        ├── ssh.py             # SSH operations
        ├── db.py             # Database operations
        ├── menu.py           # Menu and user input handling
        └── backup_operations.py # Backup file handling
```

## Requirements

- Python 3.x
- paramiko (SSH library)
- mysql-connector-python
- PyYAML

## Installation

1. Clone the repository or place the scripts in your project directory
2. Install required dependencies:
```bash
pip install paramiko mysql-connector-python PyYAML
```

## Configuration

### Environment Variables (.env)
```bash
MYSQL_HOST=mysql
MYSQL_HOST_EXTERNAL=external.mysql.host
MYSQL_PORT=3306
MYSQL_PORT_INTERNAL=3306
MYSQL_DATABASE=your_database
MYSQL_USER=your_user
MYSQL_PASSWORD=your_password
MYSQL_BACKUP_DIR=/path/to/backups
MYSQL_IMPORT_DATABASE=import_database  # Optional: different database for import
MYSQL_IMPORT_USER=import_user         # Optional: different user for import
MYSQL_IMPORT_PASSWORD=import_password  # Optional: different password for import
SSH_HOST=your.ssh.host
SSH_USER=ssh_user
SSH_KEY_PATH=/path/to/ssh/key
```

### YAML Configuration (db_configs.yml)
```yaml
configurations:
  production:
    name: "Production Database"
    env:
      MYSQL_HOST: "mysql"
      MYSQL_HOST_EXTERNAL: "external.mysql.host"
      MYSQL_PORT: "3306"
      MYSQL_PORT_INTERNAL: "3306"
      MYSQL_DATABASE: "your_database"
      MYSQL_USER: "your_user"
      MYSQL_PASSWORD: "your_password"
      MYSQL_BACKUP_DIR: "/path/to/backups"
      MYSQL_IMPORT_DATABASE: "import_database"  # Optional
      MYSQL_IMPORT_USER: "import_user"         # Optional
      MYSQL_IMPORT_PASSWORD: "import_password"  # Optional
      SSH_HOST: "your.ssh.host"
      SSH_USER: "ssh_user"
      SSH_KEY_PATH: "/path/to/ssh/key"
```

## Usage

1. Run the script:
```bash
python3 -m scripts.python.db_local_man.main
```

2. Select your configuration:
```
Available Configurations:
──────────────────────────────────────────────────
1. Environment variables (.env)
2. Production Database (production)
q. ❌ Quit
──────────────────────────────────────────────────
```

3. View server information:
```
Remote Server Information:
──────────────────────────────────────────────────
Hostname: web-server-01
OS: Ubuntu 20.04.6 LTS

Disk Space:
Total: 50G
Used: 35G (70%)
Available: 15G
──────────────────────────────────────────────────

MySQL Server Information:
──────────────────────────────────────────────────
Version: 8.0.32
Database: your_database
Size: 1250.5MB
──────────────────────────────────────────────────
```

4. Choose your backup operation:
```
Backup Options:
──────────────────────────────────────────────────
1. 💾 Create new backup from database
2. 🖥️ Use existing backup from server
3. ⬆️ Specify custom backup path
b. 🔄 Back to configuration selection
q. ❌ Quit
──────────────────────────────────────────────────
```

5. When restoring, select components to import:
```
Restore Options:
──────────────────────────────────────────────────
By default, only table data will be imported.
Select additional components to import:

1. Include stored procedures and functions
2. Include triggers
3. Include views
4. Include events
a. Include all
n. None (data only)
──────────────────────────────────────────────────
```

## Features in Detail

### MySQL Version Support
- Automatically detects MySQL version (5.7 or 8.0)
- Uses appropriate syntax for each version
- Optimizes import settings based on version

### Import Optimization
- Disables foreign key checks during import
- Disables unique checks for better performance
- Optimized packet and buffer sizes
- Progress indication during operations

### Error Handling
- Comprehensive error messages
- Fallback options for different server setups
- Safe cleanup of temporary files
- Proper handling of SSH key authentication

## Development

- Written in Python 3 with modular design
- Clean code structure with separate modules
- Extensive error handling and user feedback
- Support for different MySQL configurations

## Contributing

Feel free to submit issues, fork the repository, and create pull requests for any improvements.



## Testing

### Running Tests
Tests can be run using Docker:

```bash
# Run tests with coverage report
docker-compose -f docker-compose.test.yml up

# Run specific tests
docker-compose -f docker-compose.test.yml run test pytest tests/test_core.py -k "test_ssh"
```

### Test Coverage
The test suite includes coverage for:
- SSH connection handling
- MySQL server information retrieval
- Backup operations
- Database restoration
- Configuration management
- Menu navigation
- Retry mechanisms

### Development Setup
1. Clone the repository
2. Install development dependencies:
   ```bash
   pip install -r requirements-dev.txt
   ```
3. Run tests locally:
   ```bash
   pytest tests/test_core.py -v
   ```

### GitHub Actions
The project uses GitHub Actions for continuous integration:
- Runs on push to main branch
- Runs on pull requests
- Executes full test suite with coverage
- Reports coverage to Codecov

### Adding New Tests
When adding new functionality:
1. Create corresponding test functions in `tests/test_core.py`
2. Follow the existing pattern of using fixtures and mocks
3. Run tests to ensure nothing breaks
4. Add coverage for both success and failure cases# MySQLSyncManager
