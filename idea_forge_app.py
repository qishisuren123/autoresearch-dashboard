"""
Idea Forge Gradio 可视化界面
展示整个 A+B idea 生成流程:
1. 种子来源（大浪淘沙输出）
2. B 领域知识库
3. 生成-验证-共识检查的每一步
"""

import gradio as gr
import json
import glob
from pathlib import Path
from datetime import datetime

DATA_DIR = Path(__file__).parent / "data"
VERIFIED_DIR = DATA_DIR / "verified"
FORGE_DIR = DATA_DIR / "idea_forge"
KB_DIR = Path(__file__).parent / "knowledge_base"
SRC_DIR = Path(__file__).parent / "src"


def load_latest_forge():
    """加载最新的 forge 结果"""
    files = sorted(glob.glob(str(FORGE_DIR / "forge_*.json")))
    # 按实际种子数排序（空结果放后）
    good_files = []
    for f in files:
        try:
            with open(f) as fp:
                data = json.load(fp)
            if data.get("summary", {}).get("total_plans", 0) > 0:
                good_files.append((f, data))
        except:
            continue
    if good_files:
        return good_files[-1]
    if files:
        with open(files[-1]) as f:
            return files[-1], json.load(f)
    return None, None


def load_latest_seeds():
    """加载最新的强推荐种子"""
    files = sorted(
        glob.glob(str(VERIFIED_DIR / "final_*.json")) +
        glob.glob(str(VERIFIED_DIR / "pipeline_v5_*.json")) +
        glob.glob(str(VERIFIED_DIR / "pipeline_v4_*.json")),
        reverse=True,
    )
    all_seeds = {}
    for f in files[:10]:
        try:
            with open(f) as fp:
                data = json.load(fp)
            cands = data.get("final_candidates", data.get("top_candidates", []))
            for c in cands:
                if "强推荐" in c.get("conclusion", ""):
                    t = c.get("title", "")
                    if t and t not in all_seeds:
                        all_seeds[t] = c
        except:
            continue
    return list(all_seeds.values())


def render_seeds_tab():
    """种子池 - 显示当前所有强推荐的 A 种子"""
    seeds = load_latest_seeds()
    if not seeds:
        return "暂无强推荐种子"

    md = f"# 当前 A 种子池（{len(seeds)} 个）\n\n"
    md += "> 这些是大浪淘沙模块从社区讨论/博客/顶会筛出的「强推荐做 A 种子」的工作。\n"
    md += "> 筛选过程：18 渠道采集 → 规则初筛 → LLM(Flash) insight 过滤 → LLM(Pro) 研判\n\n"
    md += "---\n\n"

    for i, s in enumerate(seeds, 1):
        title = s.get("title", "")
        url = s.get("reddit_url", s.get("hn_url", s.get("url", "#")))
        conclusion = s.get("conclusion", "")
        channel = s.get("channel", s.get("source", ""))
        comments = s.get("num_comments", 0)
        score = s.get("score", 0)

        md += f"## {i}. [{title}]({url})\n\n"
        md += f"**来源**: `{channel}`"
        if comments:
            md += f" | **评论数**: {comments}"
        if score:
            md += f" | **点赞**: {score}"
        md += f"\n\n"
        md += f"**判定**: {conclusion[:200]}\n\n"

        # 显示完整 judgment
        jud = s.get("llm_judgment", "")
        if jud and jud != "调用失败":
            md += "<details><summary>完整研判</summary>\n\n"
            md += jud.replace("**", "") + "\n\n"
            md += "</details>\n\n"

        md += "---\n\n"

    return md


def render_b_library_tab():
    """B 领域知识库展示"""
    md = "# B 领域深度知识库\n\n"
    md += "> 每个 B 方向都有一份 Markdown 文件，包含：\n"
    md += "> - 公认痛点\n"
    md += "> - 社区共识 & 路线之争\n"
    md += "> - 常见错误直觉（避坑）\n"
    md += "> - 可行创新切入点\n\n"
    md += "**作用**：Idea Forge 生成 idea 时会把完整 MD 喂给 LLM，让它不能撞社区共识。\n\n"
    md += "**来源**：领域内专家手动维护（人为保证客观），AI 不自动修改。\n\n"
    md += "---\n\n"

    md_files = sorted(glob.glob(str(KB_DIR / "*.md")))
    md_files = [f for f in md_files if not f.endswith("README.md")]

    for f in md_files:
        name = Path(f).stem
        content = Path(f).read_text(encoding="utf-8")
        md += f"## 📘 {name}\n\n"
        md += f"<details><summary>点击展开完整知识（{len(content)} 字符）</summary>\n\n"
        md += content + "\n\n"
        md += "</details>\n\n---\n\n"

    return md


def render_plans_tab():
    """最终生成的 idea + 计划书"""
    fpath, data = load_latest_forge()
    if not data:
        return "暂无 Forge 结果"

    md = f"# 最新 Forge 结果\n\n"
    md += f"**文件**: `{Path(fpath).name}` | **时间**: {data.get('generated_at', '')[:19]}\n\n"

    summary = data.get("summary", {})
    md += f"## 漏斗\n\n"
    md += f"- 处理种子: {summary.get('seeds_processed', 0)} 个\n"
    md += f"- 生成 idea: {summary.get('total_ideas', 0)} 个（种子 × B方向 × 3模型）\n"
    md += f"- 通过交叉验证: {summary.get('total_validated', 0)} 个\n"
    md += f"- 产出计划书: {summary.get('total_plans', 0)} 份\n\n"
    md += "---\n\n"

    for i, r in enumerate(data.get("results", []), 1):
        md += f"## 种子 {i}: {r['seed_title']}\n\n"
        md += f"- 生成: {r['total_ideas']}, 通过: {r['validated']}\n\n"

        for j, p in enumerate(r.get("plans", []), 1):
            md += f"### 方案 {i}.{j}\n\n"
            md += f"- **来源模型**: `{p.get('source_model', '')}`\n"
            md += f"- **B 方向**: {p.get('b_domain', '')}\n"
            md += f"- **B 问题**: {p.get('b_problem', '')}\n\n"

            # Idea 文本
            idea = p.get("idea_text", "")
            if idea:
                md += "#### Idea 原文\n\n"
                md += "<details><summary>点击展开 Idea 详情</summary>\n\n"
                md += idea.replace("**", "") + "\n\n"
                md += "</details>\n\n"

            # 共识检查
            cc = p.get("consensus_check", {})
            if cc:
                ok = cc.get("passed", False)
                md += f"#### 共识检查: {'✅ 通过' if ok else '❌ 未通过'}\n\n"
                md += f"> {cc.get('reason', '')[:300]}\n\n"

            # 计划书
            plan = p.get("plan", "")
            if plan:
                md += "#### 预实验 + 完整计划\n\n"
                md += "<details><summary>点击展开完整计划（{}字）</summary>\n\n".format(len(plan))
                md += plan.replace("**", "") + "\n\n"
                md += "</details>\n\n"

            md += "---\n\n"

    return md


def render_pipeline_tab():
    """流程说明 - 讲清楚整个系统是怎么工作的"""
    return """
# 整个系统如何工作

## 模块一：大浪淘沙（信息聚合 + 热点筛选）

### 18 个信号源
```
社区讨论（5）:    Reddit(r/ML, r/LocalLLaMA, r/singularity) + Hacker News + Emergent Mind
大佬/Lab博客(8):  OpenAI / DeepMind / Google Research / MSR / BAIR / Raschka / Karpathy / HF Blog
中文媒体(5):     机器之心 / 新智元 / 智东西 + 量子位RSS + Leiphone RSS
学术源(3):       arXiv / HuggingFace Daily Papers / Paper Digest（含顶会汇总）
顶会覆盖:        ICLR / ICML / NeurIPS / CVPR / ACL / EMNLP / AAAI / ECCV / ICCV
工程源:          GitHub Trending / MarkTechPost / VentureBeat
```

### 筛选漏斗
```
采集 (300+条)
  ↓
规则初筛：去掉招聘、融资、发布会、周报等商业噪声
  ↓
LLM(Gemini Flash) 精筛：判断是否学术/研究相关
  ↓
VIP 白名单：被大佬（Sam Altman / Yann LeCun / 马斯克 / 翁家翌 等 50+人）提及的直接放行
  ↓
LLM(Gemini Pro) 深度研判：核心 insight / A+B 迁移潜力 / 可行性 / 最终判定
  ↓
输出：强推荐做 A 种子（每天 2-5 个）
```

---

## 模块二：Idea Forge（A+B 生成 + 验证 + 共识检查 + 计划书）

### 流程
```
A 种子 × B 方向库 × 3 个模型
        ↓
Step 1: 独立构思（gemini-pro, claude-sonnet, gpt-5.5 各自生成，互不干扰）
        ↓
        每个模型都被喂入：A 的核心 insight + B 的完整知识 MD
        ↓
Step 2: 严格交叉验证（其他 2 个模型当审稿人，>50% 通过）
        ↓
Step 2.5: 社区共识检查（Gemini Pro 对照 B 领域 MD 检查是否撞错误直觉）
        ↓
Step 3: 生成完整计划书（预实验 + 完整实验 + 命令级步骤）
        ↓
输出：可直接执行的研究方案
```

### B 方向库如何创建

**不是自动生成的，是领域内的人手工维护**：

```
knowledge_base/
├── mllm_fusion.md          多模态融合
├── mllm_visual_tokens.md   视觉 token 管理
├── llm_reasoning.md        LLM 推理
└── agent_memory.md         Agent 记忆
```

每个 MD 包含 5 个部分：
1. **社区共识**：大家都认同什么
2. **路线之争**：有争议的观点
3. **常见错误直觉（避坑）**：看起来合理但其实错的想法
4. **可行创新切入点**：真正值得做的方向
5. **数据集和基线**：实验时用什么

---

## 如何保证客观性

### 1. 多源交叉验证
单一渠道的信号（比如 HuggingFace 点赞）容易被刷，所以：
- 18 个独立信号源
- 跨源匹配：同一话题在多类源出现才加分
- HuggingFace 票数刻意降权（票可能被刷）

### 2. 多模型独立判断
不让同一个模型既生成又审核：
- 生成：3 个不同厂商模型（gemini / claude / gpt）
- 审核：其他 2 个模型交叉审稿
- 最终共识检查用 Gemini Pro（与生成用的模型不同轮次、不共享上下文）

### 3. 领域常识兜底
即使 LLM 的判断都通过了，还要对照人工维护的 B 领域 MD 做共识检查。
这是避免"看起来合理但业内人不会认可"的最后一道关。

### 4. 大佬名单白名单（有意偏向）
Sam Altman / Yann LeCun / 翁家翌 / 马斯克 等一线大佬提及的工作直接放行。
这**不是纯客观**——这是在数据极少时利用专家信号做的 informed prior。

---

## 系统的局限（诚实说明）

1. **B 方向库还不够全**：当前只有 4 个方向，很多 AI 子领域没覆盖
2. **LLM 生成的 idea 仍有"聪明但不深"的问题**：尤其在 B 领域知识不够精确时
3. **GPT-5.5 中转站偶尔超时**：已加 3 次重试，但仍可能丢 5-10% 调用
4. **共识检查依赖 MD 质量**：MD 写得不够深，检查就抓不住
"""


def get_stats():
    """系统当前状态统计"""
    seeds = load_latest_seeds()
    fpath, forge = load_latest_forge()
    forge_plans = 0
    if forge:
        forge_plans = forge.get("summary", {}).get("total_plans", 0)

    kb_files = len([f for f in glob.glob(str(KB_DIR / "*.md")) if not f.endswith("README.md")])

    latest_seed_file = ""
    vfiles = sorted(glob.glob(str(VERIFIED_DIR / "*.json")))
    if vfiles:
        latest_seed_file = Path(vfiles[-1]).name

    return (
        f"**A 种子池**: {len(seeds)} 个强推荐\n\n"
        f"**B 方向库**: {kb_files} 个知识 MD\n\n"
        f"**最新计划书**: {forge_plans} 份\n\n"
        f"**最新种子来源**: `{latest_seed_file}`\n\n"
        f"**最新 Forge 文件**: `{Path(fpath).name if fpath else '无'}`\n\n"
        f"**页面更新时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )


# === Gradio 界面 ===
with gr.Blocks(title="大浪淘沙 - Idea Forge", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 🌊 大浪淘沙 - AI 研究方案锻造系统")

    with gr.Row():
        stats = gr.Markdown(get_stats())
        refresh_btn = gr.Button("🔄 刷新", scale=0)

    with gr.Tabs():
        with gr.TabItem("📋 流程说明"):
            gr.Markdown(render_pipeline_tab())

        with gr.TabItem("🌱 A 种子池"):
            seeds_display = gr.Markdown(render_seeds_tab())

        with gr.TabItem("📘 B 领域知识库"):
            kb_display = gr.Markdown(render_b_library_tab())

        with gr.TabItem("💡 最新方案（Idea + 计划书）"):
            plans_display = gr.Markdown(render_plans_tab())

    def refresh_all():
        return (
            get_stats(),
            render_seeds_tab(),
            render_b_library_tab(),
            render_plans_tab(),
        )

    refresh_btn.click(
        refresh_all,
        outputs=[stats, seeds_display, kb_display, plans_display],
    )


if __name__ == "__main__":
    import os
    os.environ["NO_PROXY"] = "*"
    os.environ["no_proxy"] = "*"
    for k in ["http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"]:
        os.environ.pop(k, None)
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=True,  # 用 Gradio 公开隧道绕过本地代理问题
        prevent_thread_lock=False,
    )
