import os
import sys
import yaml

from app.commands import doctor
from app.commands import scan
from app.commands import test_rss
from app.commands import rss_scan
from app.commands import test_gallerydl
from app.database.database import init_db

init_db()

CONFIG = os.environ.get(
    "CONFIG_FILE",
    "/config/config.yaml"
)


with open(CONFIG) as f:
    config = yaml.safe_load(f)


print("✓ Configuration loaded")
print(config)


if len(sys.argv) > 1:

    command = sys.argv[1]

    if command == "doctor":
        doctor.run(config)
        sys.exit(0)

    if command == "scan":
        scan.run(config)
        sys.exit(0)

    if command == "test_rss":
        test_rss.run(config)
        sys.exit(0)

    if command == "rss_scan":
        rss_scan.run(config)
        sys.exit(0)

    if command == "test_gallerydl":
        test_gallerydl.run(config)
        sys.exit(0)

print("reddit-stash-agent is running...")
