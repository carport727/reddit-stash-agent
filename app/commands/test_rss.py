from app.providers.reddit.rss import fetch_posts


def run(config):

    posts = fetch_posts(
        "user",
        "example_user"
    )

    print()
    print(f"Found {len(posts)} posts")
    print()

    for post in posts[:5]:
        print(post)
