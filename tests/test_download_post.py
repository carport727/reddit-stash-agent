import json
import subprocess
import time

import pytest

from app.commands import download_post
from app.database.database import SessionLocal, init_db
from app.database.models import DownloadedFile, RedditPost, RedditSource
from app.reddit.parser import parse_post_url
from app.runtime import post_downloads


def test_parse_post_url_variants():
    expected = ("t3_abc123", "https://www.reddit.com/comments/abc123/")
    assert parse_post_url("https://www.reddit.com/r/Pics/comments/abc123/some_title/?utm=x") == expected
    assert parse_post_url("old.reddit.com/user/someone/comments/ABC123") == expected
    assert parse_post_url("https://reddit.com/gallery/abc123") == expected
    assert parse_post_url("https://redd.it/abc123") == expected
    assert parse_post_url("https://www.reddit.com/r/pics/s/AbCdE12345") == (
        None,
        "https://www.reddit.com/r/pics/s/AbCdE12345",
    )


@pytest.mark.parametrize(
    "url", ["", "https://www.reddit.com/r/pics/", "https://example.com/comments/abc", "https://i.redd.it/x.jpg"]
)
def test_parse_post_url_rejects(url):
    with pytest.raises(ValueError):
        parse_post_url(url)


class FakeStash:
    def __init__(self, root):
        self.root = root
        self.galleries = {}
        self.performer_links = []
        self.scans = []

    def get_reddit_performers(self):
        return [{"id": "7", "name": "Someone", "urls": ["https://www.reddit.com/user/Someone"]}]

    def scan_path(self, paths):
        self.scans.append(paths)
        return "1"

    def wait_for_job(self, job_id):
        return "FINISHED"

    def get_image_file_map(self, root):
        return {str(self.root / "reddit" / "pics" / f"abc123 {n}.jpg"): str(10 + n) for n in (1, 2)}

    def get_scene_file_map(self, root):
        return {}

    def generate_scene_media(self, ids):
        return None

    def find_gallery_by_url(self, url):
        return self.galleries.get(url)

    def create_gallery(self, title, url):
        self.galleries[url] = {"id": "99", "title": title, "urls": [url], "performers": []}
        return "99"

    def add_gallery_images(self, gallery_id, image_ids):
        self.gallery_images = (gallery_id, image_ids)

    def add_performer(self, kind, object_id, performer_id):
        self.performer_links.append((kind, str(object_id), performer_id))
        return "added"


@pytest.fixture()
def env(tmp_path, monkeypatch):
    init_db(str(tmp_path / "agent.db"))
    root = tmp_path / "dl"
    config = {
        "downloads": {"root": str(root), "gallery_dl_browser": ""},
        "reddit": {"cookies": str(tmp_path / "missing.json")},
        "stash": {"url": "http://stash", "api_key": ""},
    }
    stash = FakeStash(root)
    monkeypatch.setattr(download_post.StashClient, "from_config", classmethod(lambda cls, c: stash))
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        if "-j" in command:
            meta = {
                "id": "abc123",
                "title": "Two pics",
                "author": "Someone",
                "subreddit": "pics",
                "permalink": "/r/pics/comments/abc123/two_pics/",
            }
            return subprocess.CompletedProcess(command, 0, json.dumps([[2, meta], [3, "u1", meta]]), "")
        folder = root / "reddit" / "pics"
        folder.mkdir(parents=True, exist_ok=True)
        paths = []
        for n in (1, 2):
            path = folder / f"abc123 {n}.jpg"
            path.write_text("x")
            paths.append(str(path))
        return subprocess.CompletedProcess(command, 0, "\n".join(paths) + "\n", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    yield config, stash, calls

    db = SessionLocal()
    db.query(DownloadedFile).delete()
    db.query(RedditPost).delete()
    db.query(RedditSource).delete()
    db.commit()
    db.close()


def test_download_post_imports_and_links(env):
    config, stash, calls = env
    result = download_post.run(config, "https://www.reddit.com/r/pics/comments/abc123/two_pics/")

    assert result["already_downloaded"] is False
    assert result["image_ids"] == ["11", "12"]
    assert result["gallery_id"] == "99"
    assert result["performer_id"] == "7"
    assert stash.gallery_images == ("99", ["11", "12"])
    assert ("gallery", "99", "7") in stash.performer_links
    assert ("image", "11", "7") in stash.performer_links

    db = SessionLocal()
    post = db.query(RedditPost).filter_by(reddit_id="t3_abc123").one()
    assert post.downloaded is True
    assert post.url == "https://www.reddit.com/r/pics/comments/abc123/two_pics/"
    assert post.source == "someone"
    assert all(f.performer_linked and f.gallery_id == 99 for f in db.query(DownloadedFile).all())
    db.close()

    # Second request: no Reddit or gallery-dl call, same IDs.
    calls.clear()
    again = download_post.run(config, "https://redd.it/abc123")
    assert calls == []
    assert again["already_downloaded"] is True
    assert again["image_ids"] == ["11", "12"]
    assert again["gallery_id"] == "99"


def test_download_post_blocked_by_reddit(env, monkeypatch):
    config, _, _ = env

    def blocked(command, **kwargs):
        message = {"error": "HttpError", "message": "'403 Forbidden' for 'https://oauth.reddit.com/'"}
        return subprocess.CompletedProcess(command, 0, json.dumps([[-1, message]]), "")

    monkeypatch.setattr(subprocess, "run", blocked)
    with pytest.raises(download_post.PostDownloadError) as error:
        download_post.run(config, "https://redd.it/abc123")
    assert error.value.code == "cookies_missing"


def test_download_post_invalid_url(env):
    config, _, _ = env
    with pytest.raises(download_post.PostDownloadError) as error:
        download_post.run(config, "https://example.com/x")
    assert error.value.code == "invalid_url"


def _wait_done(job_id):
    for _ in range(100):
        job = post_downloads.get_job(job_id)
        if job["status"] not in post_downloads.ACTIVE:
            return job
        time.sleep(0.05)
    raise AssertionError("job did not finish")


@pytest.fixture()
def no_db_init(monkeypatch):
    monkeypatch.setattr(post_downloads, "_db_ready", True)


def test_job_records_result_and_log(no_db_init):
    def runner(config, url, on_step=None):
        on_step(1, "Check link")
        print("hello from the worker")
        return {"image_ids": ["1"]}

    job = post_downloads.submit({}, "https://redd.it/zzz", runner=runner)
    done = _wait_done(job["id"])
    assert done["status"] == "success"
    assert done["result"] == {"image_ids": ["1"]}
    assert "hello from the worker" in done["log"]
    assert post_downloads.last_job()["id"] == job["id"]


def test_job_records_error_code(no_db_init):
    def runner(config, url, on_step=None):
        raise download_post.PostDownloadError("cookies_expired", "expired")

    job = post_downloads.submit({}, "https://redd.it/yyy", runner=runner)
    done = _wait_done(job["id"])
    assert (done["status"], done["error_code"], done["error"]) == ("failed", "cookies_expired", "expired")


def test_share_link_to_non_post_is_not_found(env, monkeypatch):
    config, _, _ = env

    def redirect(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, json.dumps([[6, "https://www.reddit.com/r/pics/", {}]]), "")

    monkeypatch.setattr(subprocess, "run", redirect)
    with pytest.raises(download_post.PostDownloadError) as error:
        download_post.run(config, "https://www.reddit.com/r/pics/s/AbCdE12345")
    assert error.value.code == "not_found"
