"""
时新性刷新模块（Freshness Refresh）
========================================
设计哲学：当 idea/plan 中提及过时模型/数据集/benchmark 时，**不要击杀好计划**，
而是从两个维度获取最新版本并就地替换：
  1) B 方向库（b_library）—— 用户主动维护的权威最新基线
  2) arxiv 实时搜索 —— 兜底，覆盖 B 库未及时更新的情况

输出：
  - 把识别到的过时项映射成最新替代项
  - 用 LLM 改写 idea_text，使所有引用的模型/数据/benchmark 全部为 2025+ 最新
"""

import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from llm_client import call_model
from idea_forge.b_library import get_b_by_id


# 已知"明显过时"模式（写宽松一些，只用作粗筛触发器）
STALE_PATTERNS = [
    r"LLaVA-1\.[56]",
    r"LLaVA(?!\s*-?\s*OneVision|\s*-?\s*Critic|\s*-?\s*Mini)\b",  # 裸 "LLaVA" 不带子型号
    r"Qwen2-VL",
    r"InternVL2(?!\.\d|\s*-?\s*Plus)",
    r"Vicuna",
    r"Llama-?2\b",
    r"Llama-?3(?!\.\d)",
    r"GPT-3\.5",
    r"DeepSeek-V[12]",
    r"DeepSeek-R1-7B",
    r"Qwen2\.5(?!-VL)",  # Qwen2.5（非VL系列）作为通用 LLM 已被 Qwen3 取代
    r"\bGSM8K\b(?!.*已被刷爆)",
    r"\bVQAv?2\b",
    r"老 ?MMBench\b",
]

STALE_REGEX = re.compile("|".join(STALE_PATTERNS), re.IGNORECASE)


def quick_detect_stale_mentions(text):
    """正则粗筛 + 去重，返回检测到的过时项字符串列表"""
    hits = STALE_REGEX.findall(text)
    if not hits:
        return []
    # findall 返回 list of group 或 list of str，统一处理
    flat = []
    for h in hits:
        if isinstance(h, tuple):
            flat.extend([x for x in h if x])
        elif h:
            flat.append(h.strip())
    return list(dict.fromkeys(flat))  # 保序去重


# ============================================================
# arxiv 实时检索（兜底）
# ============================================================
def search_arxiv_latest(query, max_results=5, days_back=540):
    """
    在 arxiv 上搜索 query 相关的最新论文（默认 18 个月内）。
    返回 [{title, abstract, published, arxiv_id, url}]
    用于发现 B 库尚未收录的 2025-2026 新模型/数据集/benchmark。
    """
    try:
        import arxiv
    except ImportError:
        return []

    cutoff = datetime.now() - timedelta(days=days_back)
    try:
        client = arxiv.Client(page_size=max_results, delay_seconds=3, num_retries=2)
        search = arxiv.Search(
            query=query,
            max_results=max_results * 2,
            sort_by=arxiv.SortCriterion.Relevance,
        )
        results = []
        for paper in client.results(search):
            if paper.published.replace(tzinfo=None) < cutoff:
                continue
            results.append({
                "title": paper.title,
                "abstract": paper.summary[:300].replace("\n", " "),
                "published": paper.published.strftime("%Y-%m"),
                "arxiv_id": paper.entry_id.split("/")[-1],
                "url": paper.entry_id,
            })
            if len(results) >= max_results:
                break
        return results
    except Exception as e:
        print(f"  [freshness/arxiv] 搜索失败: {e}")
        return []


def build_b_library_reference(b_id):
    """从 B 库取出权威最新基线 + 数据集"""
    b = get_b_by_id(b_id) if b_id else None
    if not b:
        return ""
    return f"""【B 库权威最新基线（必须优先采用）】
领域: {b['domain']}
最新主基线: {', '.join(b.get('baselines', []))}
最新数据集/Benchmark: {', '.join(b.get('datasets', []))}
"""


def build_arxiv_reference(stale_items, max_per_item=2):
    """对每个检测到的过时项，搜 arxiv 找最新替代物"""
    if not stale_items:
        return ""
    parts = ["【arxiv 实时搜索 - 最新替代候选】"]
    for item in stale_items[:6]:  # 限制查询数避免太慢
        # 把"过时模型名"转换为搜索意图："X 的最新替代 / 2025/2026 SOTA"
        query = f"{item} 2025 OR 2026 successor OR replacement OR latest"
        hits = search_arxiv_latest(query, max_results=max_per_item, days_back=540)
        if hits:
            parts.append(f"\n● {item} 的可能替代候选:")
            for h in hits:
                parts.append(f"  - [{h['published']}] {h['title']}")
                parts.append(f"    {h['abstract'][:160]}...")
    return "\n".join(parts) if len(parts) > 1 else ""


# ============================================================
# 核心：刷新单条 idea 的时新性
# ============================================================
def refresh_idea_freshness(item, enable_arxiv=True, refresher_model="claude-opus"):
    """
    对一条已通过验证的 idea 做时新性刷新：
      1) 正则粗筛过时项
      2) 取 B 库权威基线
      3) 可选 arxiv 实时搜索
      4) LLM 改写 idea_text，用最新模型/数据替换过时项

    成功返回 True 并就地修改 item['idea_text']；失败返回 False（保留原文）。
    """
    original_text = item.get("idea_text", "")
    if not original_text:
        return False

    stale = quick_detect_stale_mentions(original_text)
    # 也把验证阶段记录的 D4 警告作为信号
    flags = item.get("validation", {}).get("freshness_flags", [])
    if not stale and not flags:
        # 完全没过时迹象，跳过
        return False

    print(f"    检测到过时迹象: {stale[:5]}{' (+D4警告)' if flags else ''}")

    # 收集参考资料
    b_ref = build_b_library_reference(item.get("b_direction"))
    arxiv_ref = build_arxiv_reference(stale) if enable_arxiv and stale else ""

    flags_text = "\n".join(f"  - {f}" for f in flags[:5]) if flags else "（无）"

    prompt = f"""你是科研论文打磨专家。下面这条研究方案已经通过同行评审，技术构思良好，
但其中提及的模型/数据集/benchmark 部分**版本偏旧**，会被 ICLR/NeurIPS 2026 审稿人质疑。
请在**完全保留原方案核心机制、故事线、方法描述**的前提下，**只升级**模型/数据/benchmark 引用。

【原方案】
{original_text}

【检测到的过时项】
{', '.join(stale) if stale else '（粗筛未命中，但 D4 评审有时新性警告，见下）'}

【D4 评审员的时新性警告】
{flags_text}

{b_ref}

{arxiv_ref}

【任务要求】
1. **保留**：核心 idea 一句话、机制映射、论文故事线、方法描述（这些都是好的，不要动）。
2. **升级**：仅替换"关键实验"段中的"基线 / 数据集 / benchmark / 评估方法"为 2025-2026 最新版本。
   - 优先采用上面 B 库给出的权威最新基线
   - 如果 B 库缺失某类，参考 arxiv 搜索结果或你自己知道的 2025+ 模型
   - 老模型可以保留作为"过时对比"消融，但不能作为主基线
3. **删除**：明显过时的禁用项（LLaVA-1.5/1.6、Qwen2-VL、InternVL2、Llama-2、Vicuna、GPT-3.5 作主基线等）。
4. **不要**：改变核心方法、不要重新设计实验、不要膨胀篇幅。
5. **格式**：与原方案完全一致（保留 ===、各段标题），只动具体的模型/数据名。

【输出】
请直接输出**完整改写后的方案**（保留所有原段落结构），不要写"修改说明"开头。
"""

    print(f"    [{refresher_model}] 调用刷新...", end="", flush=True)
    refreshed = call_model(refresher_model, prompt, temperature=0.2, max_tokens=3000)

    if not refreshed or len(refreshed) < len(original_text) * 0.4:
        # 刷新失败或大幅缩水，回落到 gpt-5.5
        print(" 失败，回落 gpt-5.5...", end="", flush=True)
        refreshed = call_model("gpt-5.5", prompt, temperature=0.2, max_tokens=3000)

    if not refreshed or len(refreshed) < len(original_text) * 0.4:
        print(" ❌ 刷新失败，保留原文")
        return False

    # 保存原文 + 替换
    item["idea_text_original"] = original_text
    item["idea_text"] = refreshed.strip()
    item["freshness_refresh"] = {
        "stale_detected": stale,
        "validation_flags": flags,
        "refresher": refresher_model,
        "b_library_used": bool(b_ref),
        "arxiv_used": bool(arxiv_ref),
        "refreshed_at": datetime.now().isoformat(),
    }
    print(" ✅")
    return True


def step2_5_freshness_refresh(validated_ideas, enable_arxiv=True):
    """
    Step 2.5: 对所有通过严格验证的 idea 做时新性刷新
    返回的列表与输入同长（不会击杀任何 idea，只可能就地升级）
    """
    if not validated_ideas:
        return validated_ideas

    print(f"\n{'─' * 60}")
    print(f"  Step 2.5: 时新性刷新 ({len(validated_ideas)} 个)")
    print(f"  规则：B 库 + arxiv 双渠道；只升级模型/数据，不击杀")
    print(f"{'─' * 60}")

    refreshed_count = 0
    for i, item in enumerate(validated_ideas, 1):
        b_dom = item.get("b_domain", "?")
        src = item.get("source_model", "?")
        print(f"\n  [{i}/{len(validated_ideas)}] {b_dom} (源: {src})")
        if refresh_idea_freshness(item, enable_arxiv=enable_arxiv):
            refreshed_count += 1
        else:
            print(f"    无需刷新或刷新失败，保留原文")
        time.sleep(2)

    print(f"\n  刷新完成: {refreshed_count}/{len(validated_ideas)} 个 idea 升级了模型/数据")
    return validated_ideas


if __name__ == "__main__":
    test_text = """
    草拟标题: Vision-X
    关键实验:
    - 数据集: VQAv2, GQA, 老 MMBench
    - 基线: LLaVA-1.6-7B, Qwen2-VL-7B, InternVL2-8B, Vicuna
    - 指标: F1
    """
    print("过时项检测:", quick_detect_stale_mentions(test_text))
    print("\narxiv 搜索 'LLaVA 2025 successor':")
    for r in search_arxiv_latest("LLaVA 2025 successor", max_results=3):
        print(f"  - [{r['published']}] {r['title']}")
