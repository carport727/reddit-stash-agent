import os
import sys
import yaml

from app.commands import doctor
from app.commands import scan


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

print("reddit-stash-agent is running...")
