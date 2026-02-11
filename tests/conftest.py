import sys
from pathlib import Path
from unittest.mock import MagicMock

# Ensure script directories are importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

# ──────────────────────────────────────────────
# Mock heavy optional dependencies that aren't needed for unit tests.
# These must be set before any test module imports the source modules.
# ──────────────────────────────────────────────

# pytidycensus — only needed for Census API calls, not metric math
if "pytidycensus" not in sys.modules:
    _mock_tc = MagicMock()
    sys.modules["pytidycensus"] = _mock_tc

# osmnx — only needed for network download/simplification, not compare_networks math
if "osmnx" not in sys.modules:
    _mock_ox = MagicMock()
    # compare_networks reads ox.settings, set reasonable defaults
    _mock_ox.settings.use_cache = True
    _mock_ox.settings.log_console = True
    sys.modules["osmnx"] = _mock_ox

# pytesseract, pdf2image, rapidocr_onnxruntime — OCR engines not needed for parser tests
for mod_name in ["pytesseract", "pdf2image", "rapidocr_onnxruntime"]:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()

# sentence_transformers — not needed for pure ZoningMapper method tests
if "sentence_transformers" not in sys.modules:
    sys.modules["sentence_transformers"] = MagicMock()
