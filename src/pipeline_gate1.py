"""
关 1：主流媒体共识筛选
把所有采集器跑一遍，然后做跨源话题匹配，找到被多类源同时报道的热点。
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))
from config.settings import CANDIDATES_DIR, CONSENSUS_WEIGHTS, CONSENSUS_MIN_CATEGORIES

from collectors.arxiv_collector import collect_recent_papers as collect_arxiv
from collectors.hf_papers_collector import collect_daily_papers as collect_hf
from collectors.rss_collector import collect_all_feeds as collect_rss
from collectors.hackernews_collector import get_top_stories as collect_hn
from collectors.reddit_collector import collect_all_subreddits as collect_reddit
from collectors.github_trending_collector import collect_trending as collect_github


def run_all_collectors():
    """运行所有采集器，返回统一候选池"""
    all_items = []
    print("\n" + "=" * 60)
    print("关 1：运行全部采集器")
    print("=" * 60)

    # 1. RSS (量子位、Leiphone、MarkTechPost、VentureBeat)
    print("\n--- RSS 源 ---")
    rss_articles, _ = collect_rss()
    all_items.extend(rss_articles)

    # 2. HuggingFace Daily Papers
    print("\n--- HuggingFace Daily Papers ---")
    hf_papers = collect_hf(days_back=2)
    all_items.extend(hf_papers)

    # 3. arXiv
    print("\n--- arXiv ---")
    arxiv_papers = collect_arxiv(max_per_category=15)
    all_items.extend(arxiv_papers)

    # 4. Hacker News
    print("\n--- Hacker News ---")
    hn_stories = collect_hn(limit=80)
    all_items.extend(hn_stories)

    # 5. Reddit
    print("\n--- Reddit ---")
    reddit_posts = collect_reddit()
    all_items.extend(reddit_posts)

    # 6. GitHub Trending
    print("\n--- GitHub Trending ---")
    github_repos = collect_github("daily")
    all_items.extend(github_repos)

    print(f"\n{'=' * 60}")
    print(f"采集完成，总计 {len(all_items)} 条候选")
    return all_items


def extract_topic_key(item):
    """从候选条目提取话题关键标识（用于跨源匹配）"""
    title = item.get("title", "").lower()
    # 清理标题中的常见噪声
    title = re.sub(r'[^\w\s\-]', ' ', title)
    title = re.sub(r'\s+', ' ', title).strip()

    # 如果有 arxiv_id，用它做精确匹配
    arxiv_id = item.get("arxiv_id", "")
    if arxiv_id:
        return f"arxiv:{arxiv_id}"

    # 如果有 github repo，用它
    repo = item.get("repo", "")
    if repo:
        return f"github:{repo.lower()}"

    # 否则用标题的前8个词做模糊匹配
    words = title.split()[:8]
    return " ".join(words)


def compute_title_similarity(t1, t2):
    """简单的标题相似度（词重叠率）"""
    words1 = set(re.findall(r'\w+', t1.lower()))
    words2 = set(re.findall(r'\w+', t2.lower()))
    if not words1 or not words2:
        return 0.0
    intersection = words1 & words2
    return len(intersection) / min(len(words1), len(words2))


def find_consensus_topics(items, similarity_threshold=0.5):
    """
    跨源话题聚合：找到在多个不同类别源中出现的话题。
    使用简单的标题词重叠做聚类。
    """
    # 按 source_category 分组
    by_category = defaultdict(list)
    for item in items:
        cat = item.get("source_category", "unknown")
        by_category[cat].append(item)

    print(f"\n各类别候选数量:")
    for cat, cat_items in by_category.items():
        print(f"  {cat}: {len(cat_items)} 条")

    # 把所有 HF Papers（有高 upvotes 的）作为"锚点"去匹配其他源
    anchors = []

    # 锚点来源1：HF Papers 高票
    hf_items = [i for i in items if i.get("source") == "hf_daily_papers" and i.get("upvotes", 0) >= 20]
    anchors.extend(hf_items)

    # 锚点来源2：Reddit 高票帖
    reddit_items = [i for i in items if "reddit" in i.get("source", "") and i.get("score", 0) >= 100]
    anchors.extend(reddit_items)

    # 锚点来源3：GitHub Trending 今日高星
    github_items = [i for i in items if i.get("source") == "github_trending"]
    anchors.extend(github_items)

    # 对每个锚点，找它在其他源中的匹配
    consensus_topics = []
    seen_titles = set()

    for anchor in anchors:
        anchor_title = anchor.get("title", "")
        if not anchor_title or anchor_title in seen_titles:
            continue

        matches = {"anchor": anchor, "cross_matches": [], "categories_hit": set()}
        matches["categories_hit"].add(anchor.get("source_category", ""))

        for item in items:
            if item is anchor:
                continue
            item_title = item.get("title", "")
            sim = compute_title_similarity(anchor_title, item_title)
            if sim >= similarity_threshold:
                matches["cross_matches"].append(item)
                matches["categories_hit"].add(item.get("source_category", ""))

        # 计算共识分
        score = 0
        for cat in matches["categories_hit"]:
            score += CONSENSUS_WEIGHTS.get(cat, 0.5)

        matches["consensus_score"] = score
        matches["num_categories"] = len(matches["categories_hit"])

        if matches["num_categories"] >= CONSENSUS_MIN_CATEGORIES or score >= 3.0:
            consensus_topics.append(matches)
            seen_titles.add(anchor_title)

    # 即使没有跨源匹配，也把高信号的单源候选带上（HF 高票、Reddit 高票）
    # 因为有些工作可能刚出来、还没扩散到其他源
    high_signal_single = []
    for item in items:
        title = item.get("title", "")
        if title in seen_titles:
            continue
        # HF Papers 50+ upvotes
        if item.get("source") == "hf_daily_papers" and item.get("upvotes", 0) >= 50:
            high_signal_single.append({
                "anchor": item,
                "cross_matches": [],
                "categories_hit": {item.get("source_category", "")},
                "consensus_score": CONSENSUS_WEIGHTS.get("academic", 2.5),
                "num_categories": 1,
                "note": "单源高信号（HF 50+ upvotes）",
            })
            seen_titles.add(title)
        # Reddit 300+ score
        elif "reddit" in item.get("source", "") and item.get("score", 0) >= 300:
            high_signal_single.append({
                "anchor": item,
                "cross_matches": [],
                "categories_hit": {item.get("source_category", "")},
                "consensus_score": CONSENSUS_WEIGHTS.get("engineering", 1.0) * 2,
                "num_categories": 1,
                "note": "单源高信号（Reddit 300+ score）",
            })
            seen_titles.add(title)

    consensus_topics.extend(high_signal_single)
    consensus_topics.sort(key=lambda x: x["consensus_score"], reverse=True)
    return consensus_topics


def format_output(consensus_topics):
    """格式化输出"""
    output = []
    for topic in consensus_topics:
        anchor = topic["anchor"]
        entry = {
            "title": anchor.get("title", ""),
            "url": anchor.get("url", ""),
            "arxiv_id": anchor.get("arxiv_id", ""),
            "source": anchor.get("source", ""),
            "consensus_score": topic["consensus_score"],
            "num_categories": topic["num_categories"],
            "categories_hit": list(topic["categories_hit"]),
            "upvotes": anchor.get("upvotes", 0),
            "reddit_score": anchor.get("score", 0),
            "github_stars_today": anchor.get("stars_today", ""),
            "cross_match_count": len(topic["cross_matches"]),
            "note": topic.get("note", ""),
        }
        output.append(entry)
    return output


def run_gate1():
    """关 1 主流程"""
    # Step 1: 采集
    all_items = run_all_collectors()

    # Step 2: 共识分析
    print(f"\n{'=' * 60}")
    print("关 1：共识分析")
    print("=" * 60)
    consensus_topics = find_consensus_topics(all_items)

    # Step 3: 格式化输出
    output = format_output(consensus_topics)

    # Step 4: 保存
    output_file = CANDIDATES_DIR / f"gate1_consensus_{datetime.now().strftime('%Y%m%d')}.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # Step 5: 打印结果
    print(f"\n{'=' * 60}")
    print(f"关 1 结果：共 {len(output)} 个候选话题")
    print("=" * 60)
    for i, item in enumerate(output[:15], 1):
        categories = ", ".join(item["categories_hit"])
        extra = ""
        if item["upvotes"]:
            extra += f" HF:{item['upvotes']}票"
        if item["reddit_score"]:
            extra += f" Reddit:{item['reddit_score']}↑"
        if item["github_stars_today"]:
            extra += f" GitHub:{item['github_stars_today']}"
        note = f" [{item['note']}]" if item.get("note") else ""
        print(f"  {i:2d}. [{item['consensus_score']:.1f}分 | {categories}]{extra}{note}")
        print(f"      {item['title'][:70]}")
    print(f"\n  结果保存到: {output_file}")
    return output, output_file


if __name__ == "__main__":
    run_gate1()
