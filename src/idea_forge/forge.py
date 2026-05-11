"""
Idea Forge - 第二模块核心（重构版）
从 A 种子 × B 方向库 → 高质量 A+B idea → 严格交叉验证 → 计划书

核心改进:
- 不让模型自由发挥选 B，而是从 B_LIBRARY 中明确指定 B + 喂足上下文
- idea 生成 prompt 要求深度（必须说清机制同构性）
- 交叉验证保持严格（目标是顶会水平）
- 只有真正好的 idea 才能进入计划书阶段
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from llm_client import call_model
from idea_forge.b_library import get_b_library, format_b_context
from idea_forge.consensus_check import filter_by_consensus

# 三个模型各自独立思考
IDEA_MODELS = ["gemini-pro", "gpt-5.5", "claude-sonnet"]
PLAN_MODEL = "claude-sonnet"


def generate_deep_idea_prompt(seed, b_direction):
    """
    构造深度 idea 生成 prompt
    关键变化: 加入 B 方向的完整领域知识 MD，让模型不再"缺常识"
    """
    title = seed.get("title", "")
    judgment = seed.get("llm_judgment", "")

    core_insight = ""
    for line in judgment.split("\n"):
        if "核心insight" in line or "核心 insight" in line:
            core_insight = line.split(":", 1)[-1].strip().replace("**", "") if ":" in line else ""
            break
    if not core_insight:
        core_insight = title

    # 带完整知识 MD
    b_context = format_b_context(b_direction, include_full_knowledge=True)

    prompt = f"""你是一位在 B 领域深耕多年的顶级研究者，目标是产出能被 ICLR/NeurIPS/ICML 接收的论文。

【任务】
下面给你一个"A 种子"（近期被社区热议的技术 insight）和一个"B 方向"（你所在的研究领域）。
B 方向附带了**该领域的真实社区共识、路线之争、常见误区**——你必须严格遵守这些常识。

请思考：A 的核心机制能否真正解决 B 的本质问题？

【A 种子 - 核心 Insight】
标题: {title}
洞见: {core_insight}

【B 方向 - 包含社区真实共识】
{b_context}

【硬件约束】
- 8 张 L20 GPU（48GB 显存，无 NVLink）
- 4 周时间
- 只能用公开数据集

【核心要求 - 极其重要，必须严格遵守】

1. **必须尊重 B 领域的社区共识**：
   - 看"常见错误直觉"部分！如果你的 idea 撞到了这些错误直觉，直接放弃，输出 NO_MATCH
   - 例如：如果 B 是视觉 token 管理，不要说"按时间衰减"（因为视觉 token 没时间维度）
   - 例如：如果 B 是 Agent 记忆，不要说"直接套遗忘曲线"（社区不认同强行遗忘）

2. **必须从 B 领域"可行创新切入点"出发**：
   - 在 MD 的"值得做的方向"里找你要做的事
   - 如果 A 的机制能给这些方向带来新价值，那就是好 idea
   - 如果硬要在 MD 没提的方向做，大概率会踩坑

3. **机制映射必须有深层道理**（不是表面类比）：
   - A 的数学形式 vs B 的数学形式
   - 为什么这两者本质上是同一个问题

4. **方法必须简洁**：能用 1-2 句说清

5. **严禁硬凑**：如果 A 和 B 没有合理映射，直接输出 NO_MATCH，我宁可少一个 idea

【输出格式】

如果不匹配:
NO_MATCH: <为什么不匹配，参考 B 的常识说明>

如果有合理映射:
===
核心idea（一句话）: ...
为什么不撞社区共识: (明确说出你的 idea 避开了哪些错误直觉，符合哪些已知有价值的方向)
机制映射: A 的「...」机制 ←→ B 的「...」问题，数学上的同构性在于「...」
论文故事线: 从 B 领域自身出发的动机（不提 A）
方法描述（2-3句）: 具体怎么做
草拟标题: ...
关键实验:
  - 数据集: ...
  - 基线: ...
  - 指标: ...
  - 预期结果: ...
预实验（1周内）: 具体做什么，成功标准
风险: 最可能失败的原因
==="""
    return prompt


def step1_deep_ideation(seed, b_directions):
    """
    Step 1: 对每个 A×B 配对，让三个模型各自深度构思
    """
    print(f"\n{'─' * 60}")
    print(f"  Step 1: 深度构思 (A × {len(b_directions)} 个 B 方向 × 3 模型)")
    print(f"  A: {seed.get('title', '')[:50]}")
    print(f"{'─' * 60}")

    all_ideas = []

    for b in b_directions:
        print(f"\n  B方向: {b['domain']} - {b['problem'][:30]}...")
        prompt = generate_deep_idea_prompt(seed, b)

        for model in IDEA_MODELS:
            print(f"    [{model}] 构思中...", end="")
            result = call_model(model, prompt, temperature=0.5, max_tokens=2500)

            if not result:
                print(" 调用失败")
                continue

            # 检查是否 NO_MATCH
            if "NO_MATCH" in result[:100]:
                print(f" → 无合理映射")
                continue

            # 有 idea
            core_line = ""
            for line in result.split("\n"):
                if "核心idea" in line:
                    core_line = line.split(":", 1)[-1].strip()[:60] if ":" in line else ""
                    break
            print(f" → {core_line}")

            all_ideas.append({
                "source_model": model,
                "b_direction": b["id"],
                "b_domain": b["domain"],
                "b_problem": b["problem"],
                "idea_text": result,
            })
            time.sleep(3)

    print(f"\n  共产生 {len(all_ideas)} 个候选 idea")
    return all_ideas


def step2_strict_validation(ideas):
    """
    Step 2: 严格交叉验证（目标顶会水平）
    每个 idea 由生成它之外的两个模型评审
    标准: 能否产出顶会论文级别的贡献
    """
    print(f"\n{'─' * 60}")
    print(f"  Step 2: 严格交叉验证 ({len(ideas)} 个候选)")
    print(f"{'─' * 60}")

    validated = []

    for idx, item in enumerate(ideas):
        source = item["source_model"]
        idea_text = item["idea_text"]
        reviewers = [m for m in IDEA_MODELS if m != source]

        votes_pass = 0
        total_reviews = 0
        reviews = []

        for reviewer in reviewers:
            review_prompt = f"""你是一位顶级 AI 会议的审稿人。请评审以下研究方案。

注意：你不需要判断这个方向是否"热门"或"值得做"——它已经被社区验证过热度了。
你只需要判断：这个**具体的方法设计**是否有足够的技术深度。

=== 方案 ===
{idea_text}
=== 方案结束 ===

请只关注这几个核心问题:
1. 机制映射是否有深层道理（数学/直觉上是否说得通）？还是表面类比硬凑的？
2. 提出的方法是否足够简洁且有明确的技术贡献？
3. 实验设计是否能convincingly验证这个假设？

判定:
- 如果方法有深层道理 + 足够简洁 + 实验可验证 → 输出"通过"
- 如果机制映射牵强、或方法过于复杂、或实验无法验证 → 输出"不通过"

判定（一个词）: 通过 / 不通过
核心理由（一句话）:"""

            result = call_model(reviewer, review_prompt, temperature=0.2, max_tokens=500)
            total_reviews += 1

            if result:
                reviews.append(result)
                # 解析判定
                last_200 = result[-300:]
                if "通过" in last_200 and "不通过" not in last_200.split("判定")[-1][:30]:
                    votes_pass += 1
                    print(f"    [{reviewer}] → ✅ 通过")
                else:
                    # 提取理由
                    reason = ""
                    for line in result.split("\n")[-3:]:
                        if "理由" in line:
                            reason = line.split(":", 1)[-1].strip()[:40]
                    print(f"    [{reviewer}] → ❌ {reason}")
            else:
                total_reviews -= 1
                print(f"    [{reviewer}] → ⚠️ 调用失败")
            time.sleep(3)

        # 严格标准: 需要过半通过
        pass_rate = votes_pass / total_reviews if total_reviews > 0 else 0
        if pass_rate > 0.5:
            item["validation"] = {"votes": votes_pass, "total": total_reviews, "reviews": reviews}
            validated.append(item)
            print(f"  → ✅ 通过交叉验证 ({votes_pass}/{total_reviews})")
        else:
            print(f"  → ❌ 未通过 ({votes_pass}/{total_reviews})")

    print(f"\n  通过验证: {len(validated)}/{len(ideas)}")
    return validated


def step3_plan_generation(validated_ideas):
    """
    Step 3: 为通过验证的 idea 生成详细计划书（预实验 + 完整计划）
    """
    print(f"\n{'─' * 60}")
    print(f"  Step 3: 生成计划书 ({len(validated_ideas)} 个)")
    print(f"{'─' * 60}")

    for item in validated_ideas:
        prompt = f"""你是一位有丰富实验经验的 AI 研究者。请为以下通过同行评审的 idea 制定可执行计划书。

=== Idea ===
{item['idea_text']}
===

硬件: 8 张 L20 (48GB, 无NVLink)，3TB 存储，总计 4 周。

请输出极具执行力的计划（每一步都具体到可以直接执行）:

## 预实验计划（第 1 周）
目标: 用最小成本验证"这个 idea 有没有信号"。做完后能明确判断是否继续。

1. 环境搭建:（哪个代码库、什么 Python 环境、如何配置）
2. 数据准备:（数据集名称、下载命令、预处理步骤）
3. 基线运行:（先跑一个 vanilla baseline 确认环境 OK）
4. 核心验证实验:（最小改动实现核心 idea，跑一个小规模实验）
5. 成功标准:（什么指标达到多少，或什么现象出现，算"有信号"）
6. 预估资源:（用几张 GPU、跑多久）

## 完整实验计划（第 2-4 周，仅预实验通过后执行）
1. 完整实验矩阵
2. 所有对比基线（方法名 + 来源）
3. 评估指标列表
4. 消融实验设计
5. 图表规划（论文需要哪些图/表）
6. 论文结构草案
7. 风险点和 Plan B"""

        print(f"\n  生成计划: {item['b_domain']} [{item['source_model']}]...")
        result = call_model(PLAN_MODEL, prompt, temperature=0.3, max_tokens=4000)
        if result:
            item["plan"] = result
            print(f"    ✅ ({len(result)} 字)")
        else:
            # 换一个模型试
            result = call_model("gemini-pro", prompt, temperature=0.3, max_tokens=4000)
            item["plan"] = result if result else "生成失败"
            print(f"    {'✅' if result else '❌'} (fallback)")
        time.sleep(3)

    return validated_ideas


def run_idea_forge(seeds, b_ids=None):
    """
    Idea Forge 主流程
    seeds: 大浪淘沙输出的强推荐种子
    b_ids: 指定用哪些 B 方向（None = 全部）
    """
    b_library = get_b_library()
    if b_ids:
        b_library = [b for b in b_library if b["id"] in b_ids]

    print(f"\n{'═' * 60}")
    print(f"  Idea Forge - 研究方案锻造")
    print(f"{'═' * 60}")
    print(f"  A 种子: {len(seeds)} 个")
    print(f"  B 方向: {len(b_library)} 个")
    print(f"  模型: {', '.join(IDEA_MODELS)}")
    print(f"  目标: 顶会级别论文")

    all_results = []

    for i, seed in enumerate(seeds, 1):
        print(f"\n{'━' * 60}")
        print(f"  [{i}/{len(seeds)}] A: {seed.get('title', '')[:55]}")
        print(f"{'━' * 60}")

        # Step 1: 深度构思
        ideas = step1_deep_ideation(seed, b_library)
        if not ideas:
            print("  无有效 idea，跳过")
            continue

        # Step 2: 严格验证
        validated = step2_strict_validation(ideas)
        if not validated:
            print("  无 idea 通过验证")
            continue

        # Step 2.5: 社区共识检查（新增：避免撞 B 领域常识）
        consensus_passed = filter_by_consensus(validated)
        if not consensus_passed:
            print("  无 idea 通过共识检查")
            continue

        # Step 3: 生成计划书
        with_plans = step3_plan_generation(consensus_passed)

        all_results.append({
            "seed_title": seed.get("title", ""),
            "seed_url": seed.get("reddit_url", seed.get("url", "")),
            "total_ideas": len(ideas),
            "validated": len(validated),
            "plans": with_plans,
        })

    # 保存
    output = {
        "generated_at": datetime.now().isoformat(),
        "module": "idea_forge",
        "config": {
            "models": IDEA_MODELS,
            "plan_model": PLAN_MODEL,
            "b_directions": [b["id"] for b in b_library],
            "validation": "strict (顶会标准, >50% 通过)",
        },
        "results": all_results,
        "summary": {
            "seeds_processed": len(seeds),
            "total_ideas": sum(r["total_ideas"] for r in all_results),
            "total_validated": sum(r["validated"] for r in all_results),
            "total_plans": sum(len(r["plans"]) for r in all_results),
        },
    }

    output_dir = Path(__file__).parent.parent.parent / "data" / "idea_forge"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"forge_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n{'═' * 60}")
    print(f"  Forge 完成")
    print(f"  生成 idea: {output['summary']['total_ideas']}")
    print(f"  通过验证: {output['summary']['total_validated']}")
    print(f"  产出计划: {output['summary']['total_plans']}")
    print(f"  保存: {output_file}")
    print(f"{'═' * 60}")

    return output


if __name__ == "__main__":
    import glob

    # 加载强推荐种子
    verified_dir = Path(__file__).parent.parent.parent / "data" / "verified"
    files = sorted(glob.glob(str(verified_dir / "final_*.json")) +
                   glob.glob(str(verified_dir / "pipeline_v4_*.json")))

    if not files:
        print("请先运行大浪淘沙 pipeline")
        sys.exit(1)

    with open(files[-1]) as f:
        data = json.load(f)

    candidates = data.get("final_candidates", [])
    seeds = [c for c in candidates if "强推荐" in c.get("conclusion", "")]

    if not seeds:
        print("没有强推荐种子")
        sys.exit(1)

    print(f"强推荐种子 ({len(seeds)} 个):")
    for s in seeds:
        print(f"  - {s['title'][:60]}")

    # 全量运行：所有种子 × 所有 B 方向
    run_idea_forge(seeds)
