import os
import sys
import tempfile

# Settings read these at import time, so set them before any app module loads.
_tmp = tempfile.mkdtemp(prefix="rsa-test-")
os.environ["DATA_DIR"] = os.path.join(_tmp, "data")
os.environ["LOG_DIR"] = os.path.join(_tmp, "logs")
os.environ["CONFIG_FILE"] = os.path.join(_tmp, "config.yaml")
os.environ["AGENT_TOKEN"] = "test-token"

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
