import os
import sys
from pathlib import Path

# Add the project directory to the path
project_dir = Path(__file__).parent.parent
if str(project_dir) not in sys.path:
    sys.path.append(str(project_dir))