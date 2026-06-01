import os
import sys

# Permet `import main` (et, par ricochet, l'UI) depuis backend/app/,
# quel que soit le répertoire d'où pytest est lancé.
_HERE = os.path.dirname(os.path.abspath(__file__))
_APP_DIR = os.path.abspath(os.path.join(_HERE, "..", "backend", "app"))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)
