import os
import subprocess

from app.commands.download import extract_downloaded_paths, is_blocked, short_error
from app.commands.import_reddit import media_kind
from app.providers.reddit.rss import reddit_id_from_link
from app.reddit.parser import parse_reddit_url, parse_reddit_urls


def test_parse_reddit_url_variants():
    assert parse_reddit_url("https://www.reddit.com/user/Some_Name/") == ("user", "some_name")
    assert parse_reddit_url("https://reddit.com/u/Some-Name?x=1") == ("user", "some-name")
    assert parse_reddit_url("https://old.reddit.com/r/Pics/top") == ("subreddit", "pics")
    assert parse_reddit_url("https://example.com/r/pics") is None
    assert parse_reddit_url(None) is None


def test_parse_reddit_urls_deduplicates():
    urls = ["https://reddit.com/user/A", "https://www.reddit.com/user/a/", "https://x.com/a"]
    assert parse_reddit_urls(urls) == [("user", "a")]


def test_reddit_id_from_link():
    assert reddit_id_from_link("https://www.reddit.com/r/x/comments/abc123/title/") == "t3_abc123"
    assert reddit_id_from_link("https://www.reddit.com/user/x/") is None
    assert reddit_id_from_link("https://example.com/comments/abc") is None


def test_extract_downloaded_paths(tmp_path):
    root = tmp_path / "root"
    (root / "reddit").mkdir(parents=True)
    existing = root / "reddit" / "abc a.jpg"
    existing.write_text("x")
    outside = tmp_path / "other.jpg"
    outside.write_text("x")

    stdout = f"{existing}\n# {existing}\n{outside}\n{root}/missing.jpg\n\n"
    assert extract_downloaded_paths(stdout, str(root)) == [os.path.abspath(existing)]


def test_media_kind():
    assert media_kind("/a/b.MP4") == "video"
    assert media_kind("/a/b.mkv") == "video"
    assert media_kind("/a/b.jpeg") == "image"
    assert media_kind("/a/b.json") is None


def test_block_detection():
    blocked = subprocess.CompletedProcess([], 4, "", '[reddit][error] "You\'ve been blocked by network security."\n')
    rate = subprocess.CompletedProcess([], 4, "", "[reddit][error] Too Many Requests body { font: small }")
    other = subprocess.CompletedProcess([], 8, "", "[reddit][error] NotFoundError: post\n")
    assert is_blocked(blocked) and is_blocked(rate)
    assert not is_blocked(other)
    assert short_error(other) == "[reddit][error] NotFoundError: post"


def test_cookie_files(tmp_path):
    import json

    from app.providers.reddit.rss import gallery_dl_cookie_file, load_cookie_header

    source = tmp_path / "c.json"
    source.write_text(json.dumps([{"name": "reddit_session", "value": "abc", "domain": ".reddit.com"}]))
    target = tmp_path / "data" / "c.txt"

    assert gallery_dl_cookie_file(str(source), str(target)) == str(target)
    assert (target.stat().st_mode & 0o777) == 0o600
    assert load_cookie_header(str(source)) == "reddit_session=abc"
    assert load_cookie_header(str(target)) == "reddit_session=abc"
    assert gallery_dl_cookie_file(str(target), "unused") == str(target)
    assert gallery_dl_cookie_file(str(tmp_path / "missing.json"), str(target)) is None


def test_login_cookie_status(tmp_path):
    import json

    from app.providers.reddit.rss import login_cookie_status

    path = tmp_path / "c.json"
    now = 1_800_000_000
    path.write_text(json.dumps([{"name": "reddit_session", "value": "x", "expirationDate": now + 3 * 86400 + 5}]))
    status = login_cookie_status(str(path), now=now)
    assert status["present"] and not status["expired"] and status["days_left"] == 3

    path.write_text(json.dumps([{"name": "reddit_session", "value": "x", "expirationDate": now - 1}]))
    assert login_cookie_status(str(path), now=now)["expired"]

    path.write_text(json.dumps([{"name": "other", "value": "x"}]))
    assert not login_cookie_status(str(path))["present"]
    assert not login_cookie_status(str(tmp_path / "missing.json"))["present"]
