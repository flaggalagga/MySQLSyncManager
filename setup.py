from setuptools import setup, find_packages

setup(
    name="db_local_man",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        'paramiko>=3.3.1',
        'PyYAML>=6.0.1',
        'scp>=0.14.5',
    ],
)