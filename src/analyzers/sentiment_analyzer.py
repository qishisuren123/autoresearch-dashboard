"""
舆情分析模块 - 关 2 核心

功能：
1. 对关 1 产出的候选话题，到社交平台搜索相关讨论
2. 分析评论情感 + 多样性
3. 判断是"真火"还是"买的推广"

当前实现：Reddit 舆情（白色，可直接用）
待扩展：Twitter/X（需付费或灰色方案）、小红书（深灰）、知乎（浅灰）
"""

import httpx
import json
import re
import time
from datetime import datetime
from collections import Counter
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config.settings import REDDIT_USER_AGENT, VERIFIED_DIR


def search_reddit_for_topic(topic_title, subreddits=None, limit=10):
    """在 Reddit 搜索某话题的讨论"""
    if subreddits is None:
        subreddits = ["MachineLearning", "LocalLLaMA", "singularity", "artificial"]

    all_results = []
    # 提取关键词（取标题中最有区分度的 3-5 个词）
    keywords = extract_search_keywords(topic_title)
    query = " ".join(keywords)

    for sub in subreddits:
        url = f"https://www.reddit.com/r/{sub}/search.json"
        params = {
            "q": query,
            "sort": "relevance",
            "t": "month",
            "limit": limit,
            "restrict_sr": "true",
        }
        headers = {"User-Agent": REDDIT_USER_AGENT}

        try:
            resp = httpx.get(url, params=params, headers=headers, timeout=15, follow_redirects=True)
            if resp.status_code == 200:
                data = resp.json()
                children = data.get("data", {}).get("children", [])
                for child in children:
                    post = child.get("data", {})
                    all_results.append({
                        "subreddit": sub,
                        "title": post.get("title", ""),
                        "score": post.get("score", 0),
                        "num_comments": post.get("num_comments", 0),
                        "upvote_ratio": post.get("upvote_ratio", 0),
                        "created": datetime.fromtimestamp(post.get("created_utc", 0)).isoformat(),
                        "url": f"https://www.reddit.com{post.get('permalink', '')}",
                        "selftext_preview": post.get("selftext", "")[:200],
                    })
            time.sleep(2)
        except Exception as e:
            print(f"    Reddit search r/{sub} failed: {e}")

    return all_results


def extract_search_keywords(title):
    """从标题提取搜索关键词"""
    # 去掉常见的无意义词
    stopwords = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been",
        "for", "of", "to", "in", "on", "at", "by", "with", "from",
        "and", "or", "but", "not", "this", "that", "it", "its",
        "how", "what", "when", "where", "which", "who", "why",
        "new", "novel", "towards", "via", "using", "based",
    }
    words = re.findall(r'[A-Za-z][A-Za-z0-9\-]+', title)
    keywords = [w for w in words if w.lower() not in stopwords and len(w) > 2]
    return keywords[:5]


def analyze_discussion_quality(reddit_results):
    """分析讨论质量，判断真实度"""
    if not reddit_results:
        return {
            "has_discussion": False,
            "verdict": "no_data",
            "confidence": 0.0,
            "details": "未在 Reddit 找到相关讨论",
        }

    total_score = sum(r["score"] for r in reddit_results)
    total_comments = sum(r["num_comments"] for r in reddit_results)
    avg_upvote_ratio = sum(r["upvote_ratio"] for r in reddit_results) / len(reddit_results)
    max_score = max(r["score"] for r in reddit_results)

    # 判断逻辑
    signals = []

    # Signal 1: 有高分帖子
    if max_score >= 200:
        signals.append(("high_engagement", 0.3))
    elif max_score >= 50:
        signals.append(("moderate_engagement", 0.15))
    else:
        signals.append(("low_engagement", -0.1))

    # Signal 2: 评论数/点赞比（健康帖子通常 1:3 到 1:10）
    if total_score > 0:
        comment_ratio = total_comments / total_score
        if 0.1 <= comment_ratio <= 0.5:
            signals.append(("healthy_discussion_ratio", 0.2))
        elif comment_ratio > 0.5:
            signals.append(("very_active_discussion", 0.25))

    # Signal 3: upvote_ratio（高比例 = 共识；低比例 = 争议）
    if avg_upvote_ratio >= 0.85:
        signals.append(("strong_consensus", 0.2))
    elif avg_upvote_ratio >= 0.7:
        signals.append(("moderate_consensus", 0.1))
    else:
        signals.append(("controversial", 0.05))

    # Signal 4: 多个 subreddit 都有讨论
    subs_with_results = set(r["subreddit"] for r in reddit_results if r["score"] > 0)
    if len(subs_with_results) >= 3:
        signals.append(("multi_community", 0.2))
    elif len(subs_with_results) >= 2:
        signals.append(("dual_community", 0.1))

    # 综合打分
    authenticity_score = 0.5 + sum(s[1] for s in signals)
    authenticity_score = max(0.0, min(1.0, authenticity_score))

    if authenticity_score >= 0.75:
        verdict = "genuine_hot"
    elif authenticity_score >= 0.55:
        verdict = "likely_genuine"
    elif authenticity_score >= 0.4:
        verdict = "uncertain"
    else:
        verdict = "likely_promoted"

    return {
        "has_discussion": True,
        "verdict": verdict,
        "authenticity_score": round(authenticity_score, 3),
        "signals": [s[0] for s in signals],
        "total_reddit_score": total_score,
        "total_comments": total_comments,
        "max_post_score": max_score,
        "avg_upvote_ratio": round(avg_upvote_ratio, 3),
        "subreddits_with_discussion": list(subs_with_results),
        "num_related_posts": len(reddit_results),
    }


def run_gate2_for_topic(topic):
    """对单个候选话题跑关 2 舆情验证"""
    title = topic.get("title", "")
    print(f"\n  分析: {title[:60]}...")

    # 1. Reddit 舆情
    reddit_results = search_reddit_for_topic(title)
    analysis = analyze_discussion_quality(reddit_results)

    result = {
        **topic,
        "gate2_reddit": analysis,
        "gate2_verdict": analysis["verdict"],
        "gate2_authenticity": analysis.get("authenticity_score", 0),
        "verified_at": datetime.now().isoformat(),
    }

    verdict_emoji = {
        "genuine_hot": "✅",
        "likely_genuine": "🟡",
        "uncertain": "⚠️",
        "likely_promoted": "❌",
        "no_data": "❓",
    }
    v = analysis["verdict"]
    print(f"    {verdict_emoji.get(v, '?')} {v} (score={analysis.get('authenticity_score', 0):.2f})")
    if analysis.get("signals"):
        print(f"    信号: {', '.join(analysis['signals'])}")

    return result


def run_gate2(gate1_candidates, top_k=10):
    """对关 1 的 top-K 候选运行关 2 舆情验证"""
    print("\n" + "=" * 60)
    print(f"关 2：社交舆情验证（Top-{top_k} 候选）")
    print("=" * 60)

    verified = []
    for topic in gate1_candidates[:top_k]:
        result = run_gate2_for_topic(topic)
        verified.append(result)
        time.sleep(3)  # 控频，避免 Reddit 限流

    # 按 authenticity 排序
    verified.sort(key=lambda x: x.get("gate2_authenticity", 0), reverse=True)

    # 保存
    output_file = VERIFIED_DIR / f"gate2_verified_{datetime.now().strftime('%Y%m%d')}.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(verified, f, ensure_ascii=False, indent=2)

    # 汇总
    print(f"\n{'=' * 60}")
    print(f"关 2 结果汇总")
    print("=" * 60)
    for i, item in enumerate(verified, 1):
        v = item["gate2_verdict"]
        score = item.get("gate2_authenticity", 0)
        verdict_label = {
            "genuine_hot": "✅ 真火",
            "likely_genuine": "🟡 大概率真",
            "uncertain": "⚠️ 不确定",
            "likely_promoted": "❌ 疑似推广",
            "no_data": "❓ 无数据",
        }
        print(f"  {i:2d}. {verdict_label.get(v, v)} [{score:.2f}] {item['title'][:55]}")

    print(f"\n  结果保存到: {output_file}")
    return verified


if __name__ == "__main__":
    # 测试：加载关 1 结果做关 2
    import glob
    gate1_files = sorted(glob.glob(str(VERIFIED_DIR.parent / "candidates" / "gate1_consensus_*.json")))
    if gate1_files:
        with open(gate1_files[-1]) as f:
            candidates = json.load(f)
        run_gate2(candidates, top_k=5)
    else:
        print("需要先运行 pipeline_gate1.py 生成候选")
