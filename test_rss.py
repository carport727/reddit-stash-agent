from app.providers.reddit.rss import fetch_posts


posts = fetch_posts(
    "user",
    "example_user"
)


for post in posts[:5]:
    print(post)
