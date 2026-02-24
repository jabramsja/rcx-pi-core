# Ensure repo root is in sys.path for tools imports
# This must run before test modules try to import from tools
import sys
from pathlib import Path

from tests.repo_root import REPO_ROOT
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
