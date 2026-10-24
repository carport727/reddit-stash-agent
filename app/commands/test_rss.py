from app.providers.reddit.rss import fetch_posts, load_cookie_header


def run(config, source_type, source_name):
    posts = fetch_posts(source_type, source_name, load_cookie_header(config["reddit"]["cookies"]))
    print(f"Found {len(posts)} posts")
    for post in posts[:5]:
        print(f"  {post['reddit_id']}  {post['title']}")
