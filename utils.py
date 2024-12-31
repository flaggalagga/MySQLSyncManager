#!/usr/bin/env python3
import threading
import time
import shutil
from datetime import datetime, timedelta

# ANSI Colors and Styles
BLUE = '\033[0;34m'
GREEN = '\033[0;32m'
RED = '\033[0;31m'
YELLOW = '\033[1;33m'
CYAN = '\033[0;36m'
BOLD = '\033[1m'
DIM = '\033[2m'
NC = '\033[0m'  # No Color
CLEAR_LINE = '\033[K'

# UI Icons
ICONS = {
    'check': '✅',    # Green check mark
    'times': '❌',    # Red X
    'warning': '⚠️',  # Warning triangle
    'info': 'ℹ️',    # Information symbol
    'download': '⬇️', # Down arrow
    'upload': '⬆️',   # Up arrow
    'database': '💾', # Floppy disk
    'server': '🖥️',   # Desktop computer
    'trash': '🗑️',    # Trash can
    'refresh': '🔄',  # Refresh arrows
    'backup': '📦',  # Refresh arrows
    'folder': '📁',  # Folder
    'data_chart': '📊',   # Data chart
    'spinner': ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']  # Spinner animation
}

class SpinnerProgress:
    """Docker-style spinner progress indicator"""
    def __init__(self, message):
        self.message = message
        self.spinner = ICONS['spinner']
        self._active = True
        self.start_time = time.time()
        self.thread = None

    def _get_time_string(self):
        elapsed = int(time.time() - self.start_time)
        return str(timedelta(seconds=elapsed))

    def spin(self):
        idx = 0
        while self._active:
            time_str = self._get_time_string()
            print(f"\r{BLUE}{self.spinner[idx]}{NC} {self.message} ({time_str})", end='', flush=True)  # Removed ... and fixed spacing
            idx = (idx + 1) % len(self.spinner)
            time.sleep(0.1)

    def start(self):
        self._active = True
        self.start_time = time.time()
        self.thread = threading.Thread(target=self.spin)
        self.thread.start()

    def stop(self, success=True):
        self._active = False
        if self.thread:
            self.thread.join()
        time_str = self._get_time_string()
        if success:
            print(f"\r{GREEN}{ICONS['check']}{NC} {self.message} ({time_str})", end='\n\n', flush=True)  # Added double newline
        else:
            print(f"\r{RED}{ICONS['times']}{NC} {self.message} ({time_str})", end='\n\n', flush=True)  # Added double newline

def print_header():
    """Print the application header"""
    terminal_width = shutil.get_terminal_size().columns
    print(f"{CYAN}{'='*terminal_width}{NC}")
    print(f"{BOLD}Database Local Manager{NC}".center(terminal_width))
    print(f"{DIM}{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{NC}".center(terminal_width))
    print(f"{CYAN}{'='*terminal_width}{NC}\n")