import re


def parse_reddit_urls(urls):

    results = []

    for url in urls or []:

        url = url.lower()

        user = re.search(
            r"reddit\.com/user/([^/]+)",
            url
        )

        if user:
            results.append({
                "type": "user",
                "name": user.group(1)
            })

        subreddit = re.search(
            r"reddit\.com/r/([^/]+)",
            url
        )

        if subreddit:
            results.append({
                "type": "subreddit",
                "name": subreddit.group(1)
            })

    return results
