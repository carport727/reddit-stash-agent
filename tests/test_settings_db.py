import sqlite3

from app.settings import load_config


def test_env_overrides_file(tmp_path, monkeypatch):
    path = tmp_path / "c.yaml"
    path.write_text("stash:\n  url: http://file:9999/\n  api_key: from-file\ndownloads:\n  root: /x/y/\n")
    monkeypatch.setenv("STASH_API_KEY", "from-env")

    config = load_config(str(path))
    assert config["stash"]["url"] == "http://file:9999"
    assert config["stash"]["api_key"] == "from-env"
    assert config["downloads"]["root"] == "/x/y"
    assert config["downloads"]["max_attempts"] == 5


def test_init_db_adds_missing_columns(tmp_path):
    from app.database import database

    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE reddit_posts (id INTEGER PRIMARY KEY, reddit_id VARCHAR NOT NULL UNIQUE, downloaded BOOLEAN)"
    )
    conn.execute("INSERT INTO reddit_posts (reddit_id, downloaded) VALUES ('t3_a', 0)")
    conn.commit()
    conn.close()

    added = database.init_db(str(path))
    assert "reddit_posts.download_attempts" in added
    assert "reddit_posts.last_error" in added
    assert database.init_db(str(path)) == []

    conn = sqlite3.connect(path)
    assert conn.execute("SELECT download_attempts FROM reddit_posts").fetchone() == (0,)
    conn.close()
