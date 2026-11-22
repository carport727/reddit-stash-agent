import subprocess

from app.commands import fix_gallery_order
from app.database.database import SessionLocal, init_db
from app.database.models import DownloadedFile, RedditPost


def gallery_messages(*filenames):
    messages = [[2, {"id": "gal123"}]]
    for num, filename in enumerate(filenames, start=1):
        messages.append(
            [3, f"https://i.redd.it/{filename}.jpg", {"filename": filename, "num": num, "extension": "jpeg"}]
        )
    return messages


def test_numbered_path():
    positions = {"zzz": 1, "aaa": 2}
    assert fix_gallery_order.numbered_path("/d/gal123 aaa.jpg", positions) == "/d/gal123 02 aaa.jpg"
    assert fix_gallery_order.numbered_path("/d/gal123 zzz.jpg", positions) == "/d/gal123 01 zzz.jpg"
    assert fix_gallery_order.numbered_path("/d/gal123 01 zzz.jpg", positions) is None  # already numbered
    assert fix_gallery_order.numbered_path("/d/gal123 other.jpg", positions) is None  # not in the gallery


def test_gallery_positions_ignores_single_media():
    assert fix_gallery_order.gallery_positions([[3, "u", {"filename": "x", "num": 0}]]) == {}
    assert fix_gallery_order.gallery_positions(gallery_messages("b", "a")) == {"b": 1, "a": 2}


class FakeStash:
    def __init__(self):
        self.scans = []

    def scan_path(self, paths):
        self.scans.append(paths)
        return "1"

    def wait_for_job(self, job_id):
        return "FINISHED"


def test_run_renames_gallery_files_in_reddit_order(tmp_path, monkeypatch):
    init_db(str(tmp_path / "agent.db"))
    folder = tmp_path / "reddit" / "pics"
    folder.mkdir(parents=True)
    names = ["zzz", "mmm", "aaa"]  # Reddit order; alphabetically the reverse
    for name in names:
        (folder / f"gal123 {name}.jpg").write_text(name)

    db = SessionLocal()
    post = RedditPost(reddit_id="t3_gal123", url="https://www.reddit.com/comments/gal123/", downloaded=True)
    db.add(post)
    db.flush()
    for name in names:
        db.add(DownloadedFile(reddit_post_id=post.id, path=str(folder / f"gal123 {name}.jpg"), image_id=1))
    db.commit()
    db.close()

    stash = FakeStash()
    monkeypatch.setattr(fix_gallery_order.StashClient, "from_config", classmethod(lambda cls, config: stash))
    monkeypatch.setattr(fix_gallery_order, "gallery_dl_options", lambda config: [])
    ok = subprocess.CompletedProcess([], 0, "", "")
    monkeypatch.setattr(fix_gallery_order, "_gallery_dl_json", lambda url, options: (ok, gallery_messages(*names)))

    config = {"reddit": {"request_delay_seconds": 0}}
    result = fix_gallery_order.run(config)

    assert result["renamed"] == 3
    assert sorted(p.name for p in folder.iterdir()) == ["gal123 01 zzz.jpg", "gal123 02 mmm.jpg", "gal123 03 aaa.jpg"]
    assert stash.scans == [[str(folder)]]

    db = SessionLocal()
    assert sorted(r.path.rsplit("/", 1)[1] for r in db.query(DownloadedFile).all() if "gal123" in r.path) == [
        "gal123 01 zzz.jpg",
        "gal123 02 mmm.jpg",
        "gal123 03 aaa.jpg",
    ]
    db.close()

    # Second run: nothing left to do.
    assert fix_gallery_order.run(config)["renamed"] == 0


def test_gallery_dl_options_block_linked_profiles(monkeypatch):
    from app.commands import download

    monkeypatch.setattr(download, "gallery_dl_cookie_file", lambda *a: None)
    options = download.gallery_dl_options({"reddit": {"cookies": "x"}, "downloads": {}})
    assert "blacklist=" + download.CHILD_BLACKLIST in options
    assert "*:user" in download.CHILD_BLACKLIST
