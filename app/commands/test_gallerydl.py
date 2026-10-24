from app.commands.download import extract_downloaded_paths, run_gallery_dl


def run(config, url):
    root = config["downloads"]["root"]
    output = run_gallery_dl(url, root)
    print(f"gallery-dl exit code: {output.returncode}")
    if output.stderr.strip():
        print(output.stderr.strip())
    for path in extract_downloaded_paths(output.stdout, root):
        print(path)
