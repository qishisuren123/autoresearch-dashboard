"""
AutoResearch Pipeline v4 - 以社区真实讨论为核心

核心逻辑反转:
- 之前: 从论文库出发 → 看有没有人讨论 (大部分没有)
- 现在: 从社区讨论出发 → 找到被真实热议的工作 → LLM 判断是否有 insight

入口信号:
1. Reddit r/MachineLearning 近1个月 [Research] 高讨论帖
2. Reddit r/LocalLLaMA 近1个月技术向高讨论帖
3. Hacker News 近1个月 AI 高评论帖
4. 中文媒体最近报道中能找到对应社区讨论的

筛选标准:
- 必须有真实社区讨论（评论数 > 阈值，且评论内容是技术性的）
- 不要"又大又全的工程系统"，要有具体的 insight / 方法创新
- LLM(Pro) 最终判断是否真正有洞见
"""

import json
import re
import sys
import time
import httpx
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config.settings import CANDIDATES_DIR, VERIFIED_DIR, REDDIT_USER_AGENT
from llm_client import call_flash, call_pro
try:
    from idea_forge.influential_people import get_boost_score
except ImportError:
    def get_boost_score(text):
        return 1.0, []


def search_reddit_research(subreddit, query, time_filter="month", limit=50):
    """在 Reddit 搜索研究相关帖子（看近1个月）"""
    url = f"https://www.reddit.com/r/{subreddit}/search.json"
    params = {
        "q": query,
        "sort": "top",
        "t": time_filter,
        "limit": limit,
        "restrict_sr": "true",
    }
    headers = {"User-Agent": REDDIT_USER_AGENT}

    try:
        resp = httpx.get(url, params=params, headers=headers, timeout=15, follow_redirects=True)
        if resp.status_code == 200:
            data = resp.json()
            posts = []
            for child in data.get("data", {}).get("children", []):
                post = child.get("data", {})
                posts.append({
                    "title": post.get("title", ""),
                    "url": post.get("url", ""),
                    "reddit_url": f"https://www.reddit.com{post.get('permalink', '')}",
                    "score": post.get("score", 0),
                    "num_comments": post.get("num_comments", 0),
                    "upvote_ratio": post.get("upvote_ratio", 0),
                    "flair": post.get("link_flair_text", ""),
                    "created": datetime.fromtimestamp(post.get("created_utc", 0)).isoformat(),
                    "selftext": post.get("selftext", "")[:500],
                    "subreddit": subreddit,
                })
            return posts
        elif resp.status_code == 429:
            print(f"    r/{subreddit} 限流，等待...")
            time.sleep(10)
            return []
        else:
            print(f"    r/{subreddit} HTTP {resp.status_code}")
            return []
    except Exception as e:
        print(f"    r/{subreddit} 失败: {e}")
        return []


def get_reddit_hot_research(time_filter="month"):
    """
    获取近1个月内有真实技术讨论的研究帖
    重点: 评论数要高（说明真的有人在讨论）
    """
    print("\n" + "=" * 60)
    print("  Stage 1: 从社区真实讨论出发（Reddit 近1个月）")
    print("=" * 60)

    all_posts = []

    # r/MachineLearning - 研究标签
    queries_ml = [
        "flair:Research",
        "flair:Discussion",
        "paper OR method OR architecture OR training",
    ]
    for q in queries_ml:
        posts = search_reddit_research("MachineLearning", q, time_filter, limit=30)
        all_posts.extend(posts)
        print(f"    r/MachineLearning '{q[:30]}...': {len(posts)} 帖")
        time.sleep(3)

    # r/LocalLLaMA - 技术讨论
    queries_llama = [
        "paper OR research OR method OR architecture",
        "benchmark OR evaluation OR training trick",
    ]
    for q in queries_llama:
        posts = search_reddit_research("LocalLLaMA", q, time_filter, limit=30)
        all_posts.extend(posts)
        print(f"    r/LocalLLaMA '{q[:30]}...': {len(posts)} 帖")
        time.sleep(3)

    # 去重（按 reddit_url）
    seen = set()
    unique = []
    for p in all_posts:
        key = p.get("reddit_url", p.get("title", ""))
        if key not in seen:
            seen.add(key)
            unique.append(p)

    print(f"\n  去重后: {len(unique)} 帖")
    return unique


def filter_by_discussion_quality(posts, min_comments=15, min_score=50):
    """
    只保留有真实讨论的帖子:
    - 评论数 >= 15（有人真的在讨论）
    - score >= 50（社区认可）
    - 排除纯 meme / 纯问答
    """
    quality_posts = []
    for p in posts:
        if p["num_comments"] < min_comments:
            continue
        if p["score"] < min_score:
            continue
        # 排除明显非研究内容
        title_lower = p["title"].lower()
        if any(noise in title_lower for noise in [
            "hiring", "salary", "career", "job",
            "what laptop", "which gpu", "recommend me",
            "eli5", "meme", "funny",
        ]):
            continue
        quality_posts.append(p)

    quality_posts.sort(key=lambda x: x["num_comments"], reverse=True)
    print(f"\n  讨论质量过滤: {len(posts)} → {len(quality_posts)} (评论≥{min_comments}, score≥{min_score})")
    return quality_posts


def get_hn_discussed(time_filter_days=30):
    """获取 HN 近1个月高评论 AI 帖"""
    print("\n  --- Hacker News 近1个月高讨论 ---")
    # HN search API (Algolia)
    url = "https://hn.algolia.com/api/v1/search"
    ai_queries = ["LLM", "transformer attention", "diffusion model", "multimodal AI", "reasoning AI"]
    all_stories = []

    for query in ai_queries:
        try:
            params = {
                "query": query,
                "tags": "story",
                "numericFilters": f"num_comments>20,created_at_i>{int((datetime.now().timestamp()) - time_filter_days*86400)}",
                "hitsPerPage": 20,
            }
            resp = httpx.get(url, params=params, timeout=15)
            if resp.status_code == 200:
                hits = resp.json().get("hits", [])
                for hit in hits:
                    all_stories.append({
                        "title": hit.get("title", ""),
                        "url": hit.get("url", ""),
                        "hn_url": f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}",
                        "score": hit.get("points", 0),
                        "num_comments": hit.get("num_comments", 0),
                        "created": hit.get("created_at", ""),
                        "source": "hackernews",
                    })
            time.sleep(1)
        except Exception as e:
            print(f"    HN search '{query}' 失败: {e}")

    # 去重
    seen = set()
    unique = []
    for s in all_stories:
        if s["title"] not in seen:
            seen.add(s["title"])
            unique.append(s)

    # 只要高讨论的
    quality = [s for s in unique if s["num_comments"] >= 30 and s["score"] >= 50]
    quality.sort(key=lambda x: x["num_comments"], reverse=True)
    print(f"    HN: {len(unique)} 去重 → {len(quality)} 高讨论帖（评论≥30）")
    return quality


def llm_insight_filter(posts, source_label="Reddit"):
    """
    用 LLM(Flash) 判断哪些帖子讨论的是有 genuine insight 的研究
    改进: 如果帖子提到了大佬（Sam Altman、Yann LeCun、马斯克等），直接跳过 LLM 筛选放行
    """
    print(f"\n{'=' * 60}")
    print(f"  Stage 2: LLM 判断 insight 质量 ({source_label})")
    print(f"{'=' * 60}")

    if not posts:
        return []

    # 优先通过: 被大佬提及的工作
    mentioned_by_vip = []
    remaining = []
    for p in posts:
        full_text = p.get("title", "") + " " + p.get("selftext", "")[:500]
        score, mentions = get_boost_score(full_text)
        if mentions:
            p["vip_mentions"] = [m["person"] for m in mentions]
            p["vip_boost"] = score
            mentioned_by_vip.append(p)
        else:
            remaining.append(p)

    if mentioned_by_vip:
        print(f"  🌟 {len(mentioned_by_vip)} 帖提及大佬，直接放行")
        for p in mentioned_by_vip[:5]:
            print(f"     [{','.join(p['vip_mentions'])}] {p['title'][:50]}")

    # 对剩余的跑正常 LLM 筛选
    posts = remaining

    # 分批处理
    batch_size = 15
    insightful = mentioned_by_vip[:]  # VIP 提及的直接进入

    for batch_idx in range(0, len(posts), batch_size):
        batch = posts[batch_idx:batch_idx + batch_size]
        titles_text = "\n".join(
            f"{i+1}. [{p.get('num_comments',0)}评论, {p.get('score',0)}分] {p['title']}"
            for i, p in enumerate(batch)
        )

        prompt = f"""你是一位资深AI研究者。下面是近1个月在{source_label}社区引发真实讨论的帖子。

请判断哪些讨论的是**有 genuine insight 的研究方法/发现**，而不是：
- 又大又全的工程系统（如"我们发布了一个新平台"）
- 纯产品发布（如"GPT-X 发布了"）
- 排行榜刷分（如"我们在 X benchmark 上达到了 SOTA"）
- 纯应用展示（如"用 AI 做了 XXX"）
- 行业新闻/八卦

我要的是：
- 提出了一个新颖的、具体的技术 insight（如"发现 attention 在某种条件下可以被简化"）
- 对现有方法有深刻的改进思路（不是简单的 scale up）
- 揭示了某个反直觉的现象或规律
- 提出了一个简洁但有效的新方法

请只输出保留项编号，逗号分隔。如果一个都没有，输出"无"。

帖子列表:
{titles_text}

保留项编号:"""

        result = call_flash(prompt, temperature=0.1, max_tokens=300)
        if result and result.strip() != "无":
            try:
                kept_ids = [int(x.strip()) for x in result.split(",") if x.strip().isdigit()]
                for kid in kept_ids:
                    if 1 <= kid <= len(batch):
                        insightful.append(batch[kid - 1])
            except Exception:
                pass

        kept_count = len(kept_ids) if result and result.strip() != "无" else 0
        print(f"    Batch {batch_idx//batch_size + 1}: {len(batch)} → {kept_count} 有insight")
        time.sleep(1)

    print(f"\n  Insight 过滤: {len(posts)} → {len(insightful)}")
    return insightful


def final_pro_judgment(candidates, top_k=10):
    """Gemini 3.1 Pro 最终研判"""
    print(f"\n{'=' * 60}")
    print(f"  Stage 3: Gemini Pro 深度研判 (Top-{min(top_k, len(candidates))})")
    print(f"{'=' * 60}")

    judged = []
    for i, c in enumerate(candidates[:top_k], 1):
        title = c["title"]
        selftext = c.get("selftext", "")[:300]
        comments = c.get("num_comments", 0)
        score = c.get("score", 0)
        url = c.get("url", "")
        source = c.get("subreddit", c.get("source", ""))

        prompt = f"""你是一位AI研究顾问。以下是一个在社区被真实热议的研究工作（{comments}条评论，{score}分）。

标题: {title}
来源: {source}
链接: {url}
帖子摘要: {selftext if selftext else '(无正文，标题即全部信息)'}

请做以下研判（每项 1-2 句话，务必精炼）：

1. 核心 insight: 这个工作的关键洞见/发现是什么？（如果从标题无法判断，请根据你的知识推断）
2. 为什么社区在讨论它: 它触动了什么痛点或争议点？
3. 方法简洁度: 它的核心思路是否简洁优雅？（简洁的方法更适合做 A+B 迁移）
4. A+B 迁移潜力: 如果作为"方法A"，最适合迁移到哪 2-3 个方向？
5. 资源可行性: 8张L20 + 4周能否复现或做衍生？
6. 最终判定: 【强推荐 / 值得深入 / 不适合做A种子】+ 一句话理由

格式:
核心insight: ...
社区热议原因: ...
方法简洁度: ...
A+B潜力: ...
可行性: ...
最终判定: ...
"""

        print(f"\n  [{i}] ({comments}评论) {title[:55]}...")
        result = call_pro(prompt)

        if result:
            c["llm_judgment"] = result
            # 提取最终判定
            for line in result.split("\n"):
                if "最终判定" in line:
                    c["conclusion"] = line.split(":", 1)[-1].strip() if ":" in line else ""
                    break
            print(f"      → {c.get('conclusion', '...')[:60]}")
        else:
            c["llm_judgment"] = "调用失败"
            c["conclusion"] = "待判断"
            print(f"      → 调用失败")

        judged.append(c)
        time.sleep(3)

    return judged


def run_pipeline_v4():
    """v4 主流程：以社区讨论为入口"""

    # Stage 1: 获取社区真实讨论
    reddit_posts = get_reddit_hot_research(time_filter="month")
    hn_posts = get_hn_discussed(time_filter_days=30)

    # 讨论质量过滤
    reddit_quality = filter_by_discussion_quality(reddit_posts, min_comments=15, min_score=50)
    hn_quality = [h for h in hn_posts if h["num_comments"] >= 30]

    print(f"\n  Reddit 高质量讨论: {len(reddit_quality)} 帖")
    print(f"  HN 高质量讨论: {len(hn_quality)} 帖")

    # Stage 2: LLM 判断 insight
    reddit_insightful = llm_insight_filter(reddit_quality, "Reddit")
    hn_insightful = llm_insight_filter(hn_quality, "Hacker News")

    # 合并
    all_insightful = reddit_insightful + hn_insightful
    # 按讨论热度排序（评论数为主）
    all_insightful.sort(key=lambda x: x.get("num_comments", 0), reverse=True)

    print(f"\n{'=' * 60}")
    print(f"  经 insight 过滤后: {len(all_insightful)} 个有价值的研究讨论")
    print(f"{'=' * 60}")
    for i, p in enumerate(all_insightful[:15], 1):
        src = p.get("subreddit", p.get("source", ""))
        print(f"  {i:2d}. [{p.get('num_comments',0)}评 {p.get('score',0)}↑ r/{src}] {p['title'][:55]}")

    # Stage 3: Pro 研判
    judged = final_pro_judgment(all_insightful, top_k=10)

    # 保存
    output = {
        "generated_at": datetime.now().isoformat(),
        "pipeline_version": "v4",
        "approach": "社区真实讨论为入口 → LLM insight过滤 → Pro深度研判",
        "stats": {
            "reddit_raw": len(reddit_posts),
            "reddit_quality": len(reddit_quality),
            "hn_raw": len(hn_posts),
            "hn_quality": len(hn_quality),
            "after_insight_filter": len(all_insightful),
            "final_judged": len(judged),
        },
        "final_candidates": judged,
    }

    output_file = VERIFIED_DIR / f"pipeline_v4_{datetime.now().strftime('%Y%m%d')}.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # 最终打印
    print(f"\n{'═' * 60}")
    print(f"  最终研判结果（社区真实热议 + insight 验证）")
    print(f"{'═' * 60}")
    for i, c in enumerate(judged, 1):
        print(f"\n  {'─' * 56}")
        print(f"  #{i} [{c.get('num_comments',0)}评论 {c.get('score',0)}分] r/{c.get('subreddit', c.get('source',''))}")
        print(f"  {c['title'][:70]}")
        print(f"  讨论链接: {c.get('reddit_url', c.get('hn_url', c.get('url','')))}")
        if c.get("llm_judgment") and c["llm_judgment"] != "调用失败":
            print(f"  ───")
            for line in c["llm_judgment"].split("\n"):
                if line.strip():
                    print(f"  {line.strip()}")

    print(f"\n{'═' * 60}")
    print(f"  保存: {output_file}")
    print(f"{'═' * 60}")
    return output


if __name__ == "__main__":
    run_pipeline_v4()
