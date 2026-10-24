from app.stash.client import StashClient


def run(config):
    root = config["downloads"]["root"]
    job_id = StashClient.from_config(config).scan_path(root)
    print(f"Stash scan of {root} started (job {job_id})")
