from rich import print
import yaml
import os
import time

CONFIG = os.environ.get("CONFIG_FILE", "/config/config.yaml")

with open(CONFIG) as f:
    cfg = yaml.safe_load(f)

print("[green]✓ Configuration loaded[/green]")
print(cfg)

print("[cyan]reddit-stash-agent is running...[/cyan]")

while True:
    time.sleep(60)
