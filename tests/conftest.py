import os
import sys

# Allows `import main` (and, by extension, the UI) from backend/app/,
# regardless of the directory pytest is launched from.
_HERE = os.path.dirname(os.path.abspath(__file__))
_APP_DIR = os.path.abspath(os.path.join(_HERE, "..", "backend", "app"))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)
