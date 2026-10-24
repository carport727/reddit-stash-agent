import os

from app.commands.download import extract_downloaded_paths
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
