from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="mysql_sync_manager",
    version="1.0.0",
    author="Lars Fornell",
    description="A tool for managing MySQL database backups and restoration",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/MySQLSyncManager",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Topic :: Database",
        "Topic :: System :: Archiving :: Backup",
    ],
    python_requires=">=3.8",
    install_requires=[
        "cryptography>=44.0.0",
        "paramiko>=3.5.0",
        "PyYAML>=6.0.2",
        "scp>=0.15.0",
    ],
    entry_points={
        'console_scripts': [
            'mysql-sync-manager=mysql_sync_manager.main:main',
        ],
    },
    package_data={
        'mysql_sync_manager': ['db_configs.yml'],
    }
)