"""
AutoResearch Pipeline v2
改进点:
1. 中文媒体不再需要跨源匹配才能上榜 - 独立评估
2. 学术相关性过滤（去掉纯产品/商业新闻）
3. 跨语言话题匹配（中文报道 ↔ 英文论文）
4. 最终 LLM 风格总结每个候选的核心内容 + 证据链
"""

import json
import re
import sys
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


# ============================================================
# 学术相关性关键词（只保留研究/技术类，过滤产品广告）
# ============================================================
ACADEMIC_KEYWORDS = [
    # 方法类
    "attention", "transformer", "diffusion", "reasoning", "inference",
    "fine-tun", "pretrain", "reinforcement", "reward", "alignment",
    "multimodal", "vision-language", "cross-modal", "embedding",
    "retrieval", "generation", "agent", "planning", "world model",
    "architecture", "scaling", "benchmark", "evaluation",
    "token", "context", "memory", "representation",
    "distill", "quantiz", "pruning", "efficient",
    "grounding", "hallucination", "safety", "robustness",
    # 中文
    "注意力", "多模态", "大模型", "推理", "强化学习", "微调",
    "扩散", "生成", "检索", "对齐", "幻觉", "思维链",
    "架构", "训练", "评估", "基准", "数据集",
    "视觉语言", "具身", "世界模型", "Agent",
]

COMMERCIAL_NOISE = [
    "招聘", "年薪", "融资", "市场", "梯队", "领跑", "发布会",
    "advertising", "hiring", "salary", "fundrais", "valuation",
    "广告", "促销", "优惠", "活动", "潮品", "创意风潮",
]


def is_academic_relevant(item):
    """判断是否学术/研究相关（而非纯商业新闻）"""
    text = (item.get("title", "") + " " + item.get("abstract", "") +
            " " + item.get("summary", "") + " " + item.get("selftext_preview", "")).lower()

    # 排除商业噪声
    for noise in COMMERCIAL_NOISE:
        if noise.lower() in text:
            return False

    # 包含学术关键词
    for kw in ACADEMIC_KEYWORDS:
        if kw.lower() in text:
            return True

    # arXiv 和 HF papers 默认学术相关
    if item.get("source") in ("arxiv", "hf_daily_papers"):
        return True

    return False


def extract_core_terms(title):
    """提取标题核心术语（用于跨语言匹配）"""
    # 英文专有名词（大写开头或全大写的缩写）
    eng_terms = re.findall(r'\b[A-Z][A-Za-z0-9\-]+\b', title)
    # 技术术语
    tech_terms = re.findall(r'\b(?:GPT|LLM|BERT|ViT|MoE|RL|RLHF|RAG|MTP|CoT|'
                            r'Transformer|Attention|Diffusion|Multimodal|Agent|'
                            r'DeepSeek|Claude|Anthropic|OpenAI|Meta|Google|'
                            r'Gemma|Llama|Qwen|Mistral)\b', title, re.IGNORECASE)
    return list(set([t.lower() for t in eng_terms + tech_terms if len(t) > 2]))


def cross_language_match(item_a, item_b, threshold=2):
    """跨语言匹配：看两个条目是否讨论同一话题"""
    terms_a = extract_core_terms(item_a.get("title", ""))
    terms_b = extract_core_terms(item_b.get("title", ""))
    if not terms_a or not terms_b:
        return 0
    overlap = set(terms_a) & set(terms_b)
    return len(overlap)


def run_collection():
    """运行全部采集器"""
    all_items = []
    print("\n" + "=" * 60)
    print("  采集阶段")
    print("=" * 60)

    print("\n--- RSS 源（量子位/Leiphone/MarkTechPost/VentureBeat）---")
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


def academic_filter(items):
    """过滤只保留学术/研究相关"""
    filtered = [item for item in items if is_academic_relevant(item)]
    dropped = len(items) - len(filtered)
    print(f"\n  学术相关性过滤: {len(items)} → {len(filtered)} (过滤掉 {dropped} 条商业/无关)")
    return filtered


def build_candidates(items):
    """
    构建候选列表 - 多维度打分：
    1. HF 高票论文（学术社区直接认可）
    2. 中文AI媒体报道的研究工作
    3. 英文AI媒体报道的研究工作
    4. 跨源命中（同一工作被多个渠道提及）
    5. Reddit 学术讨论（r/MachineLearning [Research] 标签）
    """
    candidates = []
    seen_titles = set()

    # --- 维度 1: HF Daily Papers 高票 ---
    hf_items = sorted(
        [i for i in items if i.get("source") == "hf_daily_papers"],
        key=lambda x: x.get("upvotes", 0), reverse=True
    )
    for item in hf_items[:15]:
        if item.get("upvotes", 0) < 15:
            break
        title = item["title"]
        if title in seen_titles:
            continue
        seen_titles.add(title)

        # 看它是否被其他源提及
        cross_sources = []
        for other in items:
            if other is item:
                continue
            if cross_language_match(item, other) >= 2:
                cross_sources.append(other.get("source", ""))

        candidates.append({
            "title": title,
            "url": item.get("url", ""),
            "arxiv_id": item.get("arxiv_id", ""),
            "abstract": item.get("abstract", ""),
            "primary_source": "hf_daily_papers",
            "hf_upvotes": item.get("upvotes", 0),
            "hf_comments": item.get("num_comments", 0),
            "github_repo": item.get("github_repo", ""),
            "github_stars": item.get("github_stars", 0),
            "cross_sources": list(set(cross_sources)),
            "evidence": [f"HuggingFace Daily Papers {item.get('upvotes',0)} upvotes"],
        })

    # --- 维度 2: 中文AI媒体报道的研究工作 ---
    chinese_items = [i for i in items if i.get("source_category") == "chinese_media"]
    for item in chinese_items:
        title = item["title"]
        if title in seen_titles:
            continue

        # 尝试跨语言匹配到 HF/arXiv
        cross_sources = []
        matched_paper = None
        for other in items:
            if other.get("source") in ("hf_daily_papers", "arxiv"):
                overlap = cross_language_match(item, other)
                if overlap >= 2:
                    cross_sources.append(other.get("source", ""))
                    if not matched_paper:
                        matched_paper = other

        seen_titles.add(title)
        entry = {
            "title": title,
            "url": item.get("url", ""),
            "arxiv_id": matched_paper.get("arxiv_id", "") if matched_paper else "",
            "abstract": matched_paper.get("abstract", "") if matched_paper else item.get("summary", ""),
            "primary_source": item.get("source", ""),
            "hf_upvotes": matched_paper.get("upvotes", 0) if matched_paper else 0,
            "cross_sources": list(set(cross_sources)),
            "evidence": [f"中文AI媒体报道: {item.get('source', '')}"],
        }
        if matched_paper:
            entry["evidence"].append(f"对应论文: {matched_paper.get('title', '')[:50]}")
        candidates.append(entry)

    # --- 维度 3: 英文AI媒体报道 ---
    english_media = [i for i in items if i.get("source_category") == "english_media"]
    for item in english_media:
        title = item["title"]
        if title in seen_titles:
            continue

        cross_sources = []
        matched_paper = None
        for other in items:
            if other.get("source") in ("hf_daily_papers", "arxiv"):
                overlap = cross_language_match(item, other)
                if overlap >= 2:
                    cross_sources.append(other.get("source", ""))
                    if not matched_paper:
                        matched_paper = other

        seen_titles.add(title)
        entry = {
            "title": title,
            "url": item.get("url", ""),
            "arxiv_id": matched_paper.get("arxiv_id", "") if matched_paper else "",
            "abstract": matched_paper.get("abstract", "") if matched_paper else item.get("summary", ""),
            "primary_source": item.get("source", ""),
            "hf_upvotes": matched_paper.get("upvotes", 0) if matched_paper else 0,
            "cross_sources": list(set(cross_sources)),
            "evidence": [f"英文AI媒体报道: {item.get('source', '')}"],
        }
        if matched_paper:
            entry["evidence"].append(f"对应论文: {matched_paper.get('title', '')[:50]}")
        candidates.append(entry)

    # --- 维度 4: Reddit 高质量学术讨论 ---
    reddit_academic = [
        i for i in items
        if "reddit" in i.get("source", "")
        and i.get("score", 0) >= 100
        and i.get("flair", "") in ("[R]", "[Research]", "[D]", "[Discussion]", "Research", "")
        and is_academic_relevant(i)
    ]
    for item in sorted(reddit_academic, key=lambda x: x.get("score", 0), reverse=True)[:10]:
        title = item["title"]
        if title in seen_titles:
            continue
        seen_titles.add(title)
        candidates.append({
            "title": title,
            "url": item.get("reddit_url", item.get("url", "")),
            "arxiv_id": "",
            "abstract": item.get("selftext_preview", ""),
            "primary_source": item.get("source", ""),
            "reddit_score": item.get("score", 0),
            "reddit_comments": item.get("num_comments", 0),
            "cross_sources": [],
            "evidence": [f"Reddit r/{item.get('source','').split('/')[-1]} score={item.get('score',0)}, {item.get('num_comments',0)} comments"],
        })

    # --- 维度 5: arXiv 但被多源提及 ---
    arxiv_items = [i for i in items if i.get("source") == "arxiv"]
    for item in arxiv_items:
        title = item["title"]
        if title in seen_titles:
            continue
        cross_sources = []
        for other in items:
            if other is item or other.get("source") == "arxiv":
                continue
            if cross_language_match(item, other) >= 2:
                cross_sources.append(other.get("source", ""))
        if cross_sources:
            seen_titles.add(title)
            candidates.append({
                "title": title,
                "url": item.get("url", ""),
                "arxiv_id": item.get("arxiv_id", ""),
                "abstract": item.get("abstract", ""),
                "primary_source": "arxiv",
                "cross_sources": list(set(cross_sources)),
                "evidence": [f"arXiv + 跨源命中: {', '.join(set(cross_sources))}"],
            })

    return candidates


def score_candidates(candidates):
    """综合打分 - 偏学术"""
    for c in candidates:
        score = 0.0

        # HF upvotes 高权重
        hf = c.get("hf_upvotes", 0)
        if hf >= 80:
            score += 5.0
        elif hf >= 50:
            score += 4.0
        elif hf >= 30:
            score += 3.0
        elif hf >= 15:
            score += 2.0

        # 跨源命中
        cross = len(c.get("cross_sources", []))
        score += cross * 1.5

        # 中文媒体报道（说明在中文社区有传播）
        if "chinese_media" in c.get("primary_source", "") or \
           any("rss_qbitai" in s or "rss_leiphone" in s for s in c.get("cross_sources", [])):
            score += 1.5

        # 英文媒体报道
        if "english_media" in c.get("primary_source", "") or \
           any("marktechpost" in s or "venturebeat" in s for s in c.get("cross_sources", [])):
            score += 1.0

        # Reddit 学术讨论
        reddit_score = c.get("reddit_score", 0)
        if reddit_score >= 300:
            score += 2.0
        elif reddit_score >= 100:
            score += 1.0

        # GitHub stars
        if c.get("github_stars", 0) >= 100:
            score += 1.0

        # 有对应 arxiv paper 加分
        if c.get("arxiv_id"):
            score += 1.0

        c["final_score"] = round(score, 1)

    candidates.sort(key=lambda x: x["final_score"], reverse=True)
    return candidates


def generate_summary(candidate):
    """为每个候选生成结构化总结"""
    title = candidate.get("title", "")
    abstract = candidate.get("abstract", "")
    evidence = candidate.get("evidence", [])
    arxiv_id = candidate.get("arxiv_id", "")
    hf_votes = candidate.get("hf_upvotes", 0)
    cross = candidate.get("cross_sources", [])

    # 生成"在做什么"的简要描述
    what = abstract[:200] if abstract else "（需进一步查看论文）"

    # 生成证据链
    evidence_lines = []
    if hf_votes:
        evidence_lines.append(f"HuggingFace 社区 {hf_votes} 票认可")
    if cross:
        evidence_lines.append(f"跨源出现: {', '.join(set(cross))}")
    evidence_lines.extend(evidence)

    summary = {
        "title": title,
        "what_it_does": what,
        "arxiv_id": arxiv_id,
        "evidence_chain": evidence_lines,
        "score": candidate.get("final_score", 0),
        "recommendation": "",
    }

    # 推荐等级
    score = candidate.get("final_score", 0)
    if score >= 5.0:
        summary["recommendation"] = "强推荐作为 A 种子"
    elif score >= 3.0:
        summary["recommendation"] = "值得关注，可作为 A 候选"
    else:
        summary["recommendation"] = "参考"

    return summary


def run_pipeline_v2():
    """v2 主流程"""
    # 1. 采集
    all_items = run_collection()

    # 2. 学术相关性过滤
    print(f"\n{'=' * 60}")
    print("  学术相关性过滤")
    print("=" * 60)
    filtered = academic_filter(all_items)

    # 3. 构建候选
    print(f"\n{'=' * 60}")
    print("  构建候选列表")
    print("=" * 60)
    candidates = build_candidates(filtered)
    print(f"  生成 {len(candidates)} 个候选")

    # 4. 打分排序
    candidates = score_candidates(candidates)

    # 5. 生成总结
    print(f"\n{'=' * 60}")
    print("  最终结果（按学术相关度排序）")
    print("=" * 60)

    summaries = []
    for i, c in enumerate(candidates[:20], 1):
        s = generate_summary(c)
        summaries.append(s)

        # 打印
        rec_icon = {"强推荐作为 A 种子": "🔥", "值得关注，可作为 A 候选": "📌", "参考": "📎"}.get(s["recommendation"], "")
        print(f"\n  {'─' * 56}")
        print(f"  #{i} [{s['score']}分] {rec_icon} {s['recommendation']}")
        print(f"  标题: {s['title'][:70]}")
        if s["arxiv_id"]:
            print(f"  arXiv: {s['arxiv_id']}")
        print(f"  内容: {s['what_it_does'][:120]}...")
        print(f"  证据链:")
        for ev in s["evidence_chain"]:
            print(f"    - {ev}")

    # 6. 保存
    output = {
        "generated_at": datetime.now().isoformat(),
        "total_collected": len(all_items),
        "after_filter": len(filtered),
        "candidates_count": len(candidates),
        "top_candidates": candidates[:20],
        "summaries": summaries,
    }
    output_file = VERIFIED_DIR / f"pipeline_v2_{datetime.now().strftime('%Y%m%d')}.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 60}")
    print(f"  完成! 保存到 {output_file}")
    print(f"  总采集 {len(all_items)} → 学术过滤 {len(filtered)} → 候选 {len(candidates)} → Top-20 展示")
    print(f"{'=' * 60}")

    return output


if __name__ == "__main__":
    run_pipeline_v2()
