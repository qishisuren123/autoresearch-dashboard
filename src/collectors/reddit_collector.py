"""Reddit 采集器 - 白色/浅灰，使用公开 JSON API（不需要 OAuth 即可读）"""

import httpx
import json
from datetime import datetime
from pathlib import Path
import time
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config.settings import REDDIT_SUBREDDITS, REDDIT_USER_AGENT, CANDIDATES_DIR


def collect_subreddit(subreddit, sort="hot", limit=25):
    """采集单个 subreddit 的帖子（使用公开 .json 端点）"""
    posts = []
    url = f"https://www.reddit.com/r/{subreddit}/{sort}.json?limit={limit}"
    headers = {"User-Agent": REDDIT_USER_AGENT}

    try:
        resp = httpx.get(url, headers=headers, timeout=15, follow_redirects=True)
        if resp.status_code == 200:
            data = resp.json()
            children = data.get("data", {}).get("children", [])
            for child in children:
                post = child.get("data", {})
                posts.append({
                    "source": f"reddit_r/{subreddit}",
                    "source_category": "engineering",
                    "title": post.get("title", ""),
                    "url": post.get("url", ""),
                    "reddit_url": f"https://www.reddit.com{post.get('permalink', '')}",
                    "score": post.get("score", 0),
                    "upvote_ratio": post.get("upvote_ratio", 0),
                    "num_comments": post.get("num_comments", 0),
                    "author": post.get("author", ""),
                    "created": datetime.fromtimestamp(post.get("created_utc", 0)).isoformat(),
                    "selftext": post.get("selftext", "")[:300],
                    "flair": post.get("link_flair_text", ""),
                    "collected_at": datetime.now().isoformat(),
                })
        elif resp.status_code == 429:
            print(f"  [Reddit] r/{subreddit}: 被限流 (429)")
        else:
            print(f"  [Reddit] r/{subreddit}: HTTP {resp.status_code}")
    except Exception as e:
        print(f"  [Reddit] r/{subreddit} 失败: {e}")

    return posts


def collect_all_subreddits():
    """采集所有配置的 subreddits"""
    all_posts = []
    for sub in REDDIT_SUBREDDITS:
        posts = collect_subreddit(sub, sort="hot", limit=25)
        print(f"  [Reddit] r/{sub}: {len(posts)} 帖")
        all_posts.extend(posts)
        time.sleep(2)
    return all_posts


def save_results(posts):
    output_file = CANDIDATES_DIR / f"reddit_{datetime.now().strftime('%Y%m%d')}.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)
    print(f"  [Reddit] 保存 {len(posts)} 帖到 {output_file}")
    return output_file


if __name__ == "__main__":
    print("=" * 60)
    print("Reddit 采集器测试")
    print("=" * 60)
    posts = collect_all_subreddits()
    if posts:
        save_results(posts)
        top5 = sorted(posts, key=lambda x: x["score"], reverse=True)[:5]
        print(f"\n  Top-5 热帖:")
        for p in top5:
            print(f"    [{p['score']}↑ {p['num_comments']}评] {p['title'][:60]}")
    else:
        print("  未获取到帖子")
