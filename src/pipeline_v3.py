"""
AutoResearch Pipeline v3
核心改进:
1. 过滤: 规则初筛 + LLM(Flash)精筛 双重机制
2. HF Daily Papers 权重大幅降低（票数不可靠）
3. 重心放在"社区对技术的真实关注度"
4. 最终候选用 Gemini 3.1 Pro 做综合研判（是否真的有价值、是否可做）
"""

import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))
from config.settings import CANDIDATES_DIR, VERIFIED_DIR

from collectors.arxiv_collector import collect_recent_papers as collect_arxiv
from collectors.hf_papers_collector import collect_daily_papers as collect_hf
from collectors.rss_collector import collect_all_feeds as collect_rss
from collectors.hackernews_collector import get_top_stories as collect_hn
from collectors.reddit_collector import collect_all_subreddits as collect_reddit
from collectors.github_trending_collector import collect_trending as collect_github
from llm_client import call_flash, call_pro


# ============================================================
# Stage 1: 数据采集（同 v2，不变）
# ============================================================
def run_collection():
    all_items = []
    print("\n" + "=" * 60)
    print("  Stage 1: 数据采集")
    print("=" * 60)

    print("\n--- RSS 源 ---")
    rss_articles, _ = collect_rss()
    all_items.extend(rss_articles)

    print("\n--- HuggingFace Daily Papers ---")
    hf_papers = collect_hf(days_back=3)
    all_items.extend(hf_papers)

    print("\n--- arXiv ---")
    arxiv_papers = collect_arxiv(max_per_category=20)
    all_items.extend(arxiv_papers)

    print("\n--- Hacker News ---")
    hn_stories = collect_hn(limit=80)
    all_items.extend(hn_stories)

    print("\n--- Reddit ---")
    reddit_posts = collect_reddit()
    all_items.extend(reddit_posts)

    print("\n--- GitHub Trending ---")
    github_repos = collect_github("daily")
    all_items.extend(github_repos)

    print(f"\n  总采集: {len(all_items)} 条")
    return all_items


# ============================================================
# Stage 2: 规则初筛（宽松，只去明显的非学术内容）
# ============================================================
OBVIOUS_NOISE = [
    "招聘", "年薪", "融资", "发布会", "促销", "优惠", "潮品",
    "hiring", "salary", "fundrais", "valuation", "advertising",
    "周报", "日报", "self-promotion", "Self-Promotion",
]


def rule_based_prefilter(items):
    """规则初筛：只排除明显非学术内容（宽松）"""
    filtered = []
    for item in items:
        text = (item.get("title", "") + " " + item.get("summary", "")).lower()
        if any(noise.lower() in text for noise in OBVIOUS_NOISE):
            continue
        # Reddit 自我推广帖跳过
        if item.get("flair", "") == "Self-Promotion Thread":
            continue
        filtered.append(item)
    dropped = len(items) - len(filtered)
    print(f"\n  规则初筛: {len(items)} → {len(filtered)} (去掉 {dropped} 条明显噪声)")
    return filtered


# ============================================================
# Stage 3: LLM 学术相关性精筛（用 Flash，批量判断）
# ============================================================
def llm_academic_filter(items, batch_size=20):
    """
    用 LLM(Flash) 批量判断哪些是有学术/研究价值的内容。
    比关键词匹配准确得多——能识别新出现的方法名和新概念。
    """
    print(f"\n{'=' * 60}")
    print(f"  Stage 3: LLM 学术相关性精筛")
    print(f"{'=' * 60}")

    academic_items = []
    total_batches = (len(items) + batch_size - 1) // batch_size

    for batch_idx in range(total_batches):
        batch = items[batch_idx * batch_size: (batch_idx + 1) * batch_size]
        titles_text = "\n".join(
            f"{i+1}. [{item.get('source','')}] {item.get('title','')}"
            for i, item in enumerate(batch)
        )

        prompt = f"""你是一个AI研究方向筛选器。下面是今天从各渠道采集的文章/论文标题列表。
请判断每一条是否与"AI/ML学术研究方法"相关。

判断标准：
- ✅ 保留：提出新方法、新架构、新训练策略、新评估框架、新数据集、对现有方法的改进、重要的实证分析
- ❌ 去掉：纯产品发布（无方法创新）、商业新闻、人事变动、行业八卦、硬件评测、教程、招聘、融资

请只输出保留项的编号，用逗号分隔。例如: 1,3,5,7

标题列表:
{titles_text}

保留项编号:"""

        result = call_flash(prompt, temperature=0.1, max_tokens=500)
        if result:
            try:
                kept_ids = [int(x.strip()) for x in result.split(",") if x.strip().isdigit()]
                for kid in kept_ids:
                    if 1 <= kid <= len(batch):
                        academic_items.append(batch[kid - 1])
            except Exception:
                # 解析失败则保留整个 batch（宁多勿少）
                academic_items.extend(batch)
        else:
            # LLM 调用失败则保留整个 batch
            academic_items.extend(batch)

        print(f"    Batch {batch_idx+1}/{total_batches}: {len(batch)} 条 → 保留 {len(kept_ids) if result else len(batch)} 条")
        time.sleep(1)

    print(f"\n  LLM 精筛结果: {len(items)} → {len(academic_items)}")
    return academic_items


# ============================================================
# Stage 4: 多维度候选构建（降低 HF 权重，提升社区讨论权重）
# ============================================================
def extract_core_terms(title):
    """提取标题核心术语"""
    terms = re.findall(r'\b[A-Z][A-Za-z0-9\-]{2,}\b', title)
    tech = re.findall(r'\b(?:GPT|LLM|BERT|ViT|MoE|RL|RLHF|RAG|MTP|CoT|GRPO|DPO|'
                      r'Transformer|Attention|Diffusion|Multimodal|Agent|'
                      r'DeepSeek|Claude|Anthropic|OpenAI|Meta|Google|Gemini|'
                      r'Gemma|Llama|Qwen|Mistral|Mamba|SSM|KV|RoPE)\b', title, re.IGNORECASE)
    return list(set([t.lower() for t in terms + tech if len(t) > 2]))


def cross_match(item_a, item_b):
    terms_a = extract_core_terms(item_a.get("title", ""))
    terms_b = extract_core_terms(item_b.get("title", ""))
    if not terms_a or not terms_b:
        return 0
    return len(set(terms_a) & set(terms_b))


def build_candidates(items):
    """构建候选，所有来源平等参与"""
    candidates = []
    seen = set()

    # 按来源分组
    by_source = defaultdict(list)
    for item in items:
        by_source[item.get("source", "unknown")].append(item)

    # 对每个 item，计算它在其他源中被提及了几次
    for item in items:
        title = item.get("title", "")
        if not title or title in seen:
            continue

        cross_sources = []
        for other in items:
            if other is item:
                continue
            if cross_match(item, other) >= 2:
                src = other.get("source", "")
                if src != item.get("source", ""):
                    cross_sources.append(src)

        # 只保留有一定信号的
        hf_votes = item.get("upvotes", 0)
        reddit_score = item.get("score", 0) if "reddit" in item.get("source", "") else 0
        hn_score = item.get("score", 0) if item.get("source") == "hackernews" else 0
        is_media = item.get("source_category") in ("chinese_media", "english_media")
        has_cross = len(cross_sources) > 0

        # 准入条件（满足任一）
        should_include = (
            hf_votes >= 15 or
            reddit_score >= 80 or
            hn_score >= 50 or
            is_media or
            has_cross or
            item.get("source") == "arxiv"  # arXiv 全量进入（后面 LLM 会筛）
        )
        if not should_include:
            continue

        seen.add(title)
        candidates.append({
            "title": title,
            "url": item.get("url", ""),
            "arxiv_id": item.get("arxiv_id", ""),
            "abstract": item.get("abstract", "") or item.get("summary", "") or item.get("selftext_preview", ""),
            "primary_source": item.get("source", ""),
            "source_category": item.get("source_category", ""),
            "hf_upvotes": hf_votes,
            "reddit_score": reddit_score,
            "hn_score": hn_score,
            "cross_sources": list(set(cross_sources)),
            "github_stars": item.get("github_stars", 0) or item.get("stars_today", ""),
        })

    return candidates


# ============================================================
# Stage 5: 打分（降低HF权重，加重跨源+社区讨论）
# ============================================================
def score_candidates(candidates):
    for c in candidates:
        score = 0.0

        # HF upvotes（降权：票数不可靠，仅作为辅助信号）
        hf = c.get("hf_upvotes", 0)
        if hf >= 80:
            score += 2.0  # 之前是 5.0
        elif hf >= 50:
            score += 1.5
        elif hf >= 30:
            score += 1.0
        elif hf >= 15:
            score += 0.5

        # 跨源命中（最重要的信号：多个独立源都在讨论）
        cross = len(c.get("cross_sources", []))
        score += cross * 2.5  # 提高权重

        # 中文媒体报道（说明在中文社区有传播力）
        if c.get("source_category") == "chinese_media":
            score += 2.0
        if any("qbitai" in s or "leiphone" in s for s in c.get("cross_sources", [])):
            score += 1.5

        # 英文媒体报道
        if c.get("source_category") == "english_media":
            score += 1.5
        if any("marktechpost" in s or "venturebeat" in s for s in c.get("cross_sources", [])):
            score += 1.0

        # Reddit 学术讨论（真实社区反应）
        rs = c.get("reddit_score", 0)
        if rs >= 500:
            score += 3.0
        elif rs >= 200:
            score += 2.0
        elif rs >= 80:
            score += 1.0

        # Hacker News
        hn = c.get("hn_score", 0)
        if hn >= 200:
            score += 2.0
        elif hn >= 50:
            score += 1.0

        # 有 arXiv paper
        if c.get("arxiv_id"):
            score += 0.5

        c["score"] = round(score, 1)

    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates


# ============================================================
# Stage 6: LLM 综合研判（Pro 模型，对 Top-K 做深度判断）
# ============================================================
def llm_final_judgment(candidates, top_k=8):
    """
    用 Gemini 3.1 Pro 对最终候选做综合研判:
    1. 这个工作到底在做什么（一句话总结）
    2. 核心技术贡献是什么
    3. 是否适合作为 A+B 迁移的 "A"
    4. 最适合迁移到哪些方向的 "B"
    """
    print(f"\n{'=' * 60}")
    print(f"  Stage 6: LLM 综合研判 (Gemini 3.1 Pro, Top-{top_k})")
    print(f"{'=' * 60}")

    judged = []
    for i, c in enumerate(candidates[:top_k], 1):
        title = c["title"]
        abstract = c.get("abstract", "")[:400]
        sources = [c["primary_source"]] + c.get("cross_sources", [])

        prompt = f"""你是一位AI研究顾问。请对以下工作做综合研判。

标题: {title}
摘要: {abstract}
被以下渠道关注: {', '.join(sources)}

请回答以下问题（每个回答 1-2 句话即可，简洁精炼）:

1. 一句话总结: 这个工作在做什么？
2. 核心技术贡献: 它的方法论创新点是什么？
3. A+B 潜力: 它是否适合作为"方法 A"迁移到别的领域？如果适合，最可能迁移到哪些方向？
4. 可行性: 用 8 张 L20 GPU (48GB each)，4 周时间，是否能复现或基于它做衍生实验？
5. 研判结论: 【强推荐做A种子 / 值得深入了解 / 暂时观望 / 不适合】

请用以下格式回答:
一句话总结: ...
核心贡献: ...
A+B潜力: ...
可行性: ...
研判结论: ...
"""

        print(f"\n  [{i}/{top_k}] {title[:55]}...")
        result = call_pro(prompt)

        if result:
            c["llm_judgment"] = result
            # 解析结论
            conclusion = ""
            for line in result.split("\n"):
                if "研判结论" in line:
                    conclusion = line.split(":")[-1].strip() if ":" in line else line
                    break
            c["conclusion"] = conclusion
            print(f"    → {conclusion}")
        else:
            c["llm_judgment"] = "调用失败"
            c["conclusion"] = "待判断"
            print(f"    → LLM 调用失败")

        judged.append(c)
        time.sleep(2)

    return judged


# ============================================================
# 主流程
# ============================================================
def run_pipeline_v3():
    """v3 完整流水线"""

    # Stage 1: 采集
    all_items = run_collection()

    # Stage 2: 规则初筛
    print(f"\n{'=' * 60}")
    print("  Stage 2: 规则初筛")
    print("=" * 60)
    prefiltered = rule_based_prefilter(all_items)

    # Stage 3: LLM 学术相关性精筛
    academic_items = llm_academic_filter(prefiltered)

    # Stage 4: 构建候选
    print(f"\n{'=' * 60}")
    print("  Stage 4: 构建候选")
    print("=" * 60)
    candidates = build_candidates(academic_items)
    print(f"  候选数: {len(candidates)}")

    # Stage 5: 打分
    print(f"\n{'=' * 60}")
    print("  Stage 5: 打分排序")
    print("=" * 60)
    candidates = score_candidates(candidates)
    print(f"  Top-10 预览:")
    for i, c in enumerate(candidates[:10], 1):
        cross_info = f" +跨源:{','.join(c['cross_sources'][:3])}" if c["cross_sources"] else ""
        print(f"    {i:2d}. [{c['score']}分] [{c['primary_source']}]{cross_info} {c['title'][:50]}")

    # Stage 6: LLM 综合研判
    judged = llm_final_judgment(candidates, top_k=8)

    # 保存
    output = {
        "generated_at": datetime.now().isoformat(),
        "pipeline_version": "v3",
        "stats": {
            "total_collected": len(all_items),
            "after_rule_filter": len(prefiltered),
            "after_llm_filter": len(academic_items),
            "candidates_built": len(candidates),
            "final_judged": len(judged),
        },
        "final_candidates": judged,
        "all_scored": candidates[:30],
    }

    output_file = VERIFIED_DIR / f"pipeline_v3_{datetime.now().strftime('%Y%m%d')}.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # 最终打印
    print(f"\n{'═' * 60}")
    print(f"  最终研判结果")
    print(f"{'═' * 60}")
    for i, c in enumerate(judged, 1):
        print(f"\n  {'─' * 56}")
        print(f"  #{i} [{c['score']}分] {c.get('conclusion', '待判断')}")
        print(f"  {c['title'][:70]}")
        if c.get("arxiv_id"):
            print(f"  arXiv: {c['arxiv_id']}")
        sources = [c["primary_source"]] + c.get("cross_sources", [])
        print(f"  来源: {', '.join(sources)}")
        if c.get("llm_judgment") and c["llm_judgment"] != "调用失败":
            print(f"  ───")
            for line in c["llm_judgment"].split("\n"):
                if line.strip():
                    print(f"  {line.strip()}")

    print(f"\n{'═' * 60}")
    print(f"  保存到: {output_file}")
    print(f"  流水线: {len(all_items)} 采集 → {len(prefiltered)} 规则筛 → {len(academic_items)} LLM筛")
    print(f"          → {len(candidates)} 候选 → Top-{len(judged)} LLM研判")
    print(f"{'═' * 60}")

    return output


if __name__ == "__main__":
    run_pipeline_v3()
