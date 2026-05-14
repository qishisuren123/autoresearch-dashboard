"""
生成 Idea Forge 可视化静态页面（按日期 timeline）
路径: ideas.html
"""

import json
import glob
import html
from pathlib import Path
from datetime import datetime
from collections import defaultdict

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
VERIFIED_DIR = DATA_DIR / "verified"
FORGE_DIR = DATA_DIR / "idea_forge"
KB_DIR = PROJECT_ROOT / "knowledge_base"


def esc(s):
    return html.escape(str(s))


# ============================================================
# 数据装载：按日期组织"种子 + idea/plan"
# ============================================================
def collect_by_date():
    """
    返回按日期降序排列的列表 [
       {date, seeds: [seed_card,...], plans: [plan_card,...], forge_files: [...]}
    ]
    每个 seed_card 含 title, conclusion, judgment, channel, url, comments, score
    每个 plan_card 含 seed_title, b_domain, source_model, idea_text, plan_text, validation, freshness, consensus, forge_file
    """
    # 1) 种子按日期归集（强推荐 + 值得深入 + 不适合 全部展示）
    seeds_by_date = defaultdict(list)
    seed_titles_by_date = defaultdict(set)
    for f in sorted(glob.glob(str(VERIFIED_DIR / "pipeline_v4_*.json"))):
        date = Path(f).stem.split("_")[-1]
        try:
            d = json.loads(Path(f).read_text(encoding="utf-8"))
        except Exception:
            continue
        for c in d.get("final_candidates", []):
            t = (c.get("title") or "").strip()
            if not t:
                continue
            seed_titles_by_date[date].add(t)
            seeds_by_date[date].append(c)

    # 2) 计划书按"产出日期"归集
    #    forge_YYYYMMDD_HHMM.json 的 YYYYMMDD 即 forge 跑的那一天
    plans_by_date = defaultdict(list)
    forge_files_by_date = defaultdict(list)
    for f in sorted(glob.glob(str(FORGE_DIR / "forge_*.json"))):
        stem = Path(f).stem  # forge_20260513_2228
        parts = stem.split("_")
        if len(parts) < 3:
            continue
        date = parts[1]
        forge_files_by_date[date].append(Path(f).name)
        try:
            d = json.loads(Path(f).read_text(encoding="utf-8"))
        except Exception:
            continue
        for r in d.get("results", []):
            seed_title = r.get("seed_title", "")
            for p in r.get("plans", []):
                p2 = dict(p)
                p2["__seed_title"] = seed_title
                p2["__forge_file"] = Path(f).name
                plans_by_date[date].append(p2)

    # 3) 合并所有日期，按降序
    all_dates = sorted(set(list(seeds_by_date.keys()) + list(plans_by_date.keys())), reverse=True)

    timeline = []
    for date in all_dates:
        timeline.append({
            "date": date,
            "seeds": seeds_by_date.get(date, []),
            "plans": plans_by_date.get(date, []),
            "forge_files": forge_files_by_date.get(date, []),
        })
    return timeline


def stats_global(timeline):
    """全局统计"""
    total_seeds = 0
    total_strong = 0
    total_plans = 0
    total_ideas = 0
    total_validated = 0
    seen_seed_titles = set()
    forge_seed_titles = set()

    for day in timeline:
        for s in day["seeds"]:
            t = (s.get("title") or "").strip()
            if t and t not in seen_seed_titles:
                seen_seed_titles.add(t)
                total_seeds += 1
                if "强推荐" in s.get("conclusion", ""):
                    total_strong += 1
        for p in day["plans"]:
            total_plans += 1
            forge_seed_titles.add(p.get("__seed_title", ""))

    # ideas / validated 累加从 forge summary
    for f in sorted(glob.glob(str(FORGE_DIR / "forge_*.json"))):
        try:
            d = json.loads(Path(f).read_text(encoding="utf-8"))
        except Exception:
            continue
        sm = d.get("summary", {})
        total_ideas += sm.get("total_ideas", 0)
        total_validated += sm.get("total_validated", 0)

    kb_n = len([f for f in glob.glob(str(KB_DIR / "*.md")) if not f.endswith("README.md")])

    return {
        "unique_seeds": total_seeds,
        "strong_seeds": total_strong,
        "kb_count": kb_n,
        "total_ideas": total_ideas,
        "total_validated": total_validated,
        "total_plans": total_plans,
        "forge_seeds": len(forge_seed_titles),
        "active_days": len(timeline),
    }


# ============================================================
# 渲染各 tab
# ============================================================
def render_stats_bar(s):
    return f"""
<div class="stats">
  <div class="stat"><div class="n">{s['active_days']}</div><div class="l">活跃天数</div></div>
  <div class="stat"><div class="n">{s['unique_seeds']}</div><div class="l">候选种子（去重）</div></div>
  <div class="stat"><div class="n">{s['strong_seeds']}</div><div class="l">强推荐 A 种子</div></div>
  <div class="stat"><div class="n">{s['kb_count']}</div><div class="l">B 方向知识库</div></div>
  <div class="stat"><div class="n">{s['total_ideas']}</div><div class="l">候选 Idea</div></div>
  <div class="stat"><div class="n">{s['total_validated']}</div><div class="l">通过严格验证</div></div>
  <div class="stat"><div class="n">{s['total_plans']}</div><div class="l">输出计划书</div></div>
</div>
"""


def render_seed_card(idx, c):
    title = esc(c.get("title", "")[:140])
    url = esc(c.get("reddit_url", c.get("hn_url", c.get("url", "#"))))
    conclusion = esc(c.get("conclusion", "")[:300])
    channel = esc(c.get("subreddit", c.get("source", c.get("channel", ""))))
    comments = c.get("num_comments", 0)
    score = c.get("score", 0)
    judgment = esc((c.get("llm_judgment") or "").replace("**", ""))

    if "强推荐" in c.get("conclusion", ""):
        tag_class, tag_text = "tag-strong", "强推荐做 A 种子"
    elif "值得" in c.get("conclusion", "") or "深入" in c.get("conclusion", ""):
        tag_class, tag_text = "tag-worth", "值得深入"
    elif "不适合" in c.get("conclusion", ""):
        tag_class, tag_text = "tag-skip", "不适合做 A 种子"
    else:
        tag_class, tag_text = "tag-skip", "待判断"

    meta_parts = []
    if channel:
        meta_parts.append(f'<span class="ch">{channel}</span>')
    if comments:
        meta_parts.append(f'<span class="hot">{comments} 评论</span>')
    if score:
        meta_parts.append(f'<span>{score} 分</span>')

    return f'''
<div class="card seed-card">
  <div class="card-top">
    <span class="rank">{idx}</span>
    <h4><a href="{url}" target="_blank">{title}</a></h4>
    <span class="tag {tag_class}">{tag_text}</span>
  </div>
  <div class="meta">{" ".join(meta_parts)}</div>
  <div class="conclusion"><b>判定：</b>{conclusion}</div>
  <details><summary>完整研判 (点击展开)</summary><pre>{judgment}</pre></details>
</div>'''


def render_plan_card(idx, p):
    seed_title = esc(p.get("__seed_title", "")[:120])
    b_domain = esc(p.get("b_domain", ""))
    b_problem = esc(p.get("b_problem", ""))
    source_model = esc(p.get("source_model", ""))
    idea_text = esc((p.get("idea_text") or "").replace("**", ""))
    plan_text = esc((p.get("plan") or "").replace("**", ""))
    forge_file = esc(p.get("__forge_file", ""))

    # validation
    val = p.get("validation", {})
    val_html = ""
    if val:
        votes = val.get("votes", 0)
        total = val.get("total", 0)
        flags = val.get("freshness_flags", [])
        flag_html = ""
        if flags:
            flag_html = "<br><b>时新性警告（已自动刷新）：</b><br>" + "<br>".join(esc(f)[:200] for f in flags[:3])
        val_html = f'<div class="val-box">✅ 严格交叉验证通过 ({votes}/{total}){flag_html}</div>'

    # consensus
    cc = p.get("consensus_check", {})
    cc_html = ""
    if cc:
        ok = cc.get("passed", False)
        icon = "✅" if ok else "⚠️"
        reason = esc((cc.get("reason") or "")[:300])
        cc_html = f'<div class="cc-box"><b>共识检查 {icon}</b> {reason}</div>'

    # freshness refresh
    fr = p.get("freshness_refresh", {})
    fr_html = ""
    if fr:
        stale = fr.get("stale_detected", [])
        refresher = esc(fr.get("refresher", ""))
        b_used = "✓" if fr.get("b_library_used") else "✗"
        a_used = "✓" if fr.get("arxiv_used") else "✗"
        if stale:
            fr_html = f'<div class="fr-box">🔄 时新性已升级（用 {refresher} 改写；B库参考{b_used} arxiv参考{a_used}）<br><small>原文中过时项：{esc(", ".join(stale[:8]))}</small></div>'

    return f'''
<div class="card plan-card">
  <div class="plan-header">
    <span class="plan-rank">{idx}</span>
    <span class="model-tag">{source_model}</span>
    <span class="domain-tag">{b_domain}</span>
    <span class="seed-tag">来自种子：{seed_title}</span>
  </div>
  <div class="b-problem"><b>B 领域问题：</b>{b_problem}</div>
  {val_html}
  {fr_html}
  {cc_html}
  <details open><summary>📌 Idea 原文</summary><pre>{idea_text}</pre></details>
  <details><summary>📋 完整计划书（预实验 + 完整实验）</summary><pre>{plan_text}</pre></details>
  <div class="src-file"><small>来源：{forge_file}</small></div>
</div>'''


def render_timeline(timeline):
    """渲染按日期分组的 timeline"""
    if not timeline:
        return '<div class="tab-content active" id="tab-timeline"><p>暂无数据</p></div>'

    parts = ['<div class="tab-content active" id="tab-timeline">']
    parts.append('<h2>📅 按日期 Timeline（每日种子 + 通过的 Idea）</h2>')
    parts.append('<p>每个日期分组展示当天大浪淘沙的种子和当天 Forge 产出的计划书。</p>')

    for day in timeline:
        d = day["date"]
        d_fmt = f"{d[:4]}-{d[4:6]}-{d[6:]}"
        seeds = day["seeds"]
        plans = day["plans"]
        forge_files = day["forge_files"]

        strong_count = sum(1 for s in seeds if "强推荐" in s.get("conclusion", ""))

        parts.append(f'<div class="day-block">')
        parts.append(f'<div class="day-header">')
        parts.append(f'<h3>📅 {d_fmt}</h3>')
        parts.append(f'<div class="day-stats">')
        parts.append(f'<span class="badge badge-seed">{len(seeds)} 候选 / <b>{strong_count}</b> 强推荐</span> ')
        parts.append(f'<span class="badge badge-plan">{len(plans)} 计划书</span>')
        if forge_files:
            parts.append(f' <span class="badge badge-info">Forge 文件: {", ".join(forge_files)}</span>')
        parts.append(f'</div></div>')

        # 种子列表
        if seeds:
            parts.append('<div class="day-section"><h4>🌱 当天大浪淘沙候选种子</h4>')
            # 按 strong → worth → skip 排序
            def k(c):
                con = c.get("conclusion", "")
                if "强推荐" in con: return 0
                if "值得" in con or "深入" in con: return 1
                if "不适合" in con: return 2
                return 3
            seeds_sorted = sorted(seeds, key=k)
            for i, c in enumerate(seeds_sorted, 1):
                parts.append(render_seed_card(i, c))
            parts.append('</div>')

        # 通过验证的 idea / 计划书
        if plans:
            parts.append('<div class="day-section"><h4>💡 当天 Forge 通过验证 + 产出计划书</h4>')
            for i, p in enumerate(plans, 1):
                parts.append(render_plan_card(i, p))
            parts.append('</div>')

        if not seeds and not plans:
            parts.append('<p style="color:#6b7280;">这一天没有数据。</p>')

        parts.append('</div>')  # day-block

    parts.append('</div>')
    return "\n".join(parts)


def render_pipeline_tab():
    return """
<div class="tab-content" id="tab-pipeline">
<h2>🔄 系统流程</h2>

<h3>模块一：大浪淘沙（信息聚合 + 热点筛选）</h3>

<div class="info-box">
<strong>14 个白色合规渠道：</strong>
<ul>
<li><b>社区讨论</b>: Reddit (r/MachineLearning, r/LocalLLaMA, r/singularity) + Hacker News</li>
<li><b>研究者博客</b>: OpenAI / DeepMind / Google Research / MSR / BAIR / Sebastian Raschka / Karpathy / Simon Willison / HF Blog</li>
<li><b>媒体源</b>: 量子位 RSS / Leiphone RSS / MarkTechPost / VentureBeat / Paper Digest</li>
<li><b>学术源</b>: arXiv / HuggingFace Daily Papers</li>
<li><b>工程源</b>: GitHub Trending</li>
</ul>
</div>

<div class="flow">
<div class="flow-step">采集（每日 ~150-300 条原始信息）</div>
<div class="arrow">↓</div>
<div class="flow-step highlight">跨天去重（剔除月度热帖反复研判，节省 70%+ token）</div>
<div class="arrow">↓</div>
<div class="flow-step">规则初筛（去商业噪声 / 招聘 / 融资）</div>
<div class="arrow">↓</div>
<div class="flow-step">LLM(Gemini Flash) 精筛 insight 质量</div>
<div class="arrow">↓</div>
<div class="flow-step highlight">VIP 白名单：Sam Altman / Yann LeCun / Karpathy 等 50+ 大佬提及直接放行</div>
<div class="arrow">↓</div>
<div class="flow-step">LLM(Gemini Pro) 深度研判：核心 insight / A+B 潜力 / 可行性 / 强推荐判定</div>
<div class="arrow">↓</div>
<div class="flow-step success">输出：强推荐做 A 种子（每天平均 1-3 个）</div>
</div>

<h3>模块二：Idea Forge（A+B 锻造 → 计划书）</h3>

<div class="flow">
<div class="flow-step">A 种子 × B 方向库（4 个领域）× 3 模型并行</div>
<div class="arrow">↓</div>
<div class="flow-step">Step 1: 深度构思（gemini-pro / gpt-5.5 / claude-opus 各自独立生成）<br>
  <small>每个模型获得 A 的核心 insight + B 的完整知识 MD（90-120 行）</small></div>
<div class="arrow">↓</div>
<div class="flow-step">Step 2: 全员交叉验证（3 模型互相评审，含生成者本人 — 消除单一模型主导否决偏差）<br>
  <small>四维度评分：D1 机制深度 · D2 方法简洁 · D3 实验充分 · D4 时新性</small></div>
<div class="arrow">↓</div>
<div class="flow-step highlight">Step 2.5: 时新性刷新（B 库 + arxiv 双渠道升级旧模型/数据/benchmark）<br>
  <small>不击杀好方案，仅就地升级到 2025+ 最新基线</small></div>
<div class="arrow">↓</div>
<div class="flow-step">Step 2.6: 共识检查（对照 B 领域 MD，避免撞社区错误直觉）</div>
<div class="arrow">↓</div>
<div class="flow-step success">Step 3: 生成完整计划书（预实验 + 完整实验 + 命令级步骤）</div>
</div>

<h3>关键设计</h3>

<div class="info-box">
<ol>
<li><b>跨天去重</b>：扫描历史 verified/* 提取 url + 归一化 title 黑名单，避免同一篇帖子月度重复研判</li>
<li><b>多模型交叉</b>：3 个不同厂商（Google / OpenAI / Anthropic）独立生成 + 全员评审，消除单模型偏差</li>
<li><b>时新性自动刷新</b>：旧基线不再一票否决，而是用 B 库 + arxiv 双渠道升级，保留好方案</li>
<li><b>领域常识兜底</b>：B 领域 MD 包含社区共识 / 路线之争 / 常见错误直觉 / 可行创新切入点</li>
<li><b>路由与降级</b>：GPT 优先免费 anyrouter（24h 可用）；Claude 免费窗口走 CLI；代理失效自动降级走收费直连</li>
</ol>
</div>

<h3>系统当前局限（诚实说明）</h3>

<div class="warn-box">
<ol>
<li>B 方向库只有 4 个领域，下一步要扩展到 8-10 个</li>
<li>信息源全部为免费白色渠道，可加入 Twitter Basic API / 微信公众号 RSS 等付费源提升前沿度</li>
<li>知识库 baseline / dataset 字段仍需人工维护，下一步加入月度自动扫描 arxiv 补全</li>
</ol>
</div>
</div>
"""


def render_kb_tab():
    parts = ['<div class="tab-content" id="tab-kb"><h2>📘 B 领域深度知识库</h2>']
    parts.append('<p>由领域内人手动维护（保证客观），AI 不自动修改基线 / dataset 等关键字段。</p>')

    md_files = sorted(glob.glob(str(KB_DIR / "*.md")))
    md_files = [f for f in md_files if not f.endswith("README.md")]

    for f in md_files:
        name = Path(f).stem
        md_content = Path(f).read_text(encoding="utf-8")
        parts.append(f'''
<div class="card kb-card">
<h4>📄 {name} <small>({len(md_content)} 字符 · {md_content.count(chr(10))+1} 行)</small></h4>
<details><summary>展开查看完整知识 MD</summary><pre class="kb-content">{esc(md_content)}</pre></details>
</div>''')

    parts.append('</div>')
    return "\n".join(parts)


# ============================================================
# 主入口
# ============================================================
def generate():
    timeline = collect_by_date()
    s = stats_global(timeline)
    stats_html = render_stats_bar(s)
    timeline_html = render_timeline(timeline)
    pipeline_html = render_pipeline_tab()
    kb_html = render_kb_tab()

    page = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>AutoResearch · Idea Forge Timeline</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
  font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif;
  background: #0f1117; color: #e4e4e7; line-height: 1.6; padding: 20px;
}}
.container {{ max-width: 1280px; margin: 0 auto; }}
header {{
  background: linear-gradient(135deg, #1a1b2e, #16213e);
  border: 1px solid #2a2d3e; border-radius: 14px;
  padding: 30px; margin-bottom: 20px;
}}
header h1 {{
  font-size: 28px;
  background: linear-gradient(90deg, #60a5fa, #a78bfa);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}}
header .sub {{ color: #9ca3af; font-size: 13px; margin-top: 8px; }}
.nav-link {{ display: inline-block; margin-top: 10px; color: #60a5fa; text-decoration: none; margin-right: 16px; }}

.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 10px; margin-bottom: 20px; }}
.stat {{ background: #1a1b2e; border: 1px solid #2a2d3e; border-radius: 10px; padding: 14px; text-align: center; }}
.stat .n {{ font-size: 28px; font-weight: 700; color: #60a5fa; }}
.stat .l {{ color: #9ca3af; font-size: 11px; margin-top: 2px; }}

.tabs {{ display: flex; gap: 0; border-bottom: 1px solid #2a2d3e; margin-bottom: 20px; flex-wrap: wrap; }}
.tab-btn {{
  background: transparent; color: #9ca3af; border: none; padding: 12px 22px;
  font-size: 14px; cursor: pointer; border-bottom: 2px solid transparent;
  transition: all 0.2s; font-family: inherit;
}}
.tab-btn:hover {{ color: #e4e4e7; }}
.tab-btn.active {{ color: #60a5fa; border-bottom-color: #60a5fa; font-weight: 600; }}
.tab-content {{ display: none; }}
.tab-content.active {{ display: block; }}
.tab-content h2 {{ font-size: 22px; margin-bottom: 14px; color: #f4f4f5; }}
.tab-content h3 {{ font-size: 17px; margin: 22px 0 10px; color: #a78bfa; }}
.tab-content h4 {{ font-size: 14px; color: #f4f4f5; margin-bottom: 8px; }}
.tab-content p {{ color: #d1d5db; margin-bottom: 10px; font-size: 13px; }}

.day-block {{ margin-bottom: 36px; }}
.day-header {{
  background: linear-gradient(135deg, #1a1b2e, #16213e);
  border: 1px solid #2a2d3e; border-radius: 10px;
  padding: 18px 22px; margin-bottom: 14px;
  display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;
}}
.day-header h3 {{ font-size: 20px; color: #60a5fa; margin: 0; }}
.day-stats {{ display: flex; gap: 8px; flex-wrap: wrap; }}
.badge {{ padding: 4px 12px; border-radius: 14px; font-size: 12px; font-weight: 500; }}
.badge-seed {{ background: #1e293b; color: #60a5fa; }}
.badge-plan {{ background: #064e3b; color: #34d399; }}
.badge-info {{ background: #1f2937; color: #9ca3af; font-size: 11px; }}

.day-section {{ margin-left: 14px; padding-left: 14px; border-left: 2px solid #2a2d3e; margin-bottom: 18px; }}
.day-section h4 {{ font-size: 15px; color: #a78bfa; margin-bottom: 12px; }}

.card {{
  background: #1a1b2e; border: 1px solid #2a2d3e; border-radius: 12px;
  padding: 16px 18px; margin-bottom: 12px; transition: border-color 0.2s;
}}
.card:hover {{ border-color: #3b82f6; }}
.card-top {{ display: flex; align-items: center; gap: 10px; margin-bottom: 8px; flex-wrap: wrap; }}
.rank {{
  background: #111827; color: #60a5fa; font-weight: 700; font-size: 13px;
  width: 30px; height: 30px; border-radius: 8px;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}}
.card h4 {{ font-size: 14px; color: #f4f4f5; line-height: 1.4; flex: 1; min-width: 200px; }}
.card h4 a {{ color: #f4f4f5; text-decoration: none; }}
.card h4 a:hover {{ color: #60a5fa; }}
.meta {{ font-size: 11px; color: #6b7280; margin-bottom: 8px; display: flex; gap: 10px; flex-wrap: wrap; }}
.meta .ch {{ color: #a78bfa; font-weight: 500; }}
.meta .hot {{ color: #f59e0b; }}

.tag {{ display: inline-block; padding: 3px 10px; border-radius: 4px; font-size: 11px; font-weight: 600; }}
.tag-strong {{ background: #064e3b; color: #34d399; }}
.tag-worth {{ background: #422006; color: #fbbf24; }}
.tag-skip {{ background: #1f2937; color: #6b7280; }}

.conclusion {{ font-size: 12.5px; color: #d1d5db; margin: 8px 0; padding: 8px 12px; background: #111827; border-left: 3px solid #60a5fa; border-radius: 4px; }}

.plan-card {{ border-left: 3px solid #34d399; }}
.plan-header {{ display: flex; gap: 8px; margin-bottom: 10px; align-items: center; flex-wrap: wrap; }}
.plan-rank {{ background: #064e3b; color: #34d399; padding: 4px 12px; border-radius: 5px; font-size: 12px; font-weight: 700; }}
.model-tag {{ background: #1e3a5f; color: #60a5fa; padding: 3px 10px; border-radius: 5px; font-size: 11px; }}
.domain-tag {{ background: #3b2b5f; color: #a78bfa; padding: 3px 10px; border-radius: 5px; font-size: 11px; }}
.seed-tag {{ background: #1f2937; color: #9ca3af; padding: 3px 10px; border-radius: 5px; font-size: 11px; flex: 1; min-width: 200px; }}
.b-problem {{ font-size: 12.5px; color: #d1d5db; margin: 8px 0; padding: 8px 12px; background: #111827; border-radius: 4px; }}
.val-box {{ font-size: 12px; color: #34d399; margin: 8px 0; padding: 8px 12px; background: #0f1f16; border-radius: 4px; }}
.fr-box {{ font-size: 12px; color: #60a5fa; margin: 8px 0; padding: 8px 12px; background: #0f1a2a; border-radius: 4px; }}
.cc-box {{ font-size: 12px; color: #fbbf24; margin: 8px 0; padding: 8px 12px; background: #1f1a11; border-radius: 4px; }}
.src-file {{ color: #6b7280; font-size: 10px; text-align: right; margin-top: 6px; }}

.info-box {{ background: #111827; border-left: 3px solid #60a5fa; border-radius: 4px;
  padding: 14px 18px; margin: 14px 0; font-size: 13px; color: #d1d5db; }}
.info-box ul, .info-box ol {{ margin: 8px 0 0 20px; }}
.info-box li {{ margin: 5px 0; }}
.warn-box {{ background: #1f1a11; border-left: 3px solid #f59e0b; border-radius: 4px;
  padding: 14px 18px; margin: 14px 0; font-size: 13px; color: #d1d5db; }}
.warn-box ol {{ margin-left: 20px; }}
.warn-box li {{ margin: 5px 0; }}

.flow {{ padding: 14px 0; }}
.flow-step {{
  background: #111827; border: 1px solid #2a2d3e; border-radius: 8px;
  padding: 10px 16px; margin: 6px 0; font-size: 13px; color: #d1d5db;
}}
.flow-step.highlight {{ border-left: 3px solid #f59e0b; }}
.flow-step.success {{ border-left: 3px solid #34d399; background: #0f1f16; }}
.flow-step small {{ color: #6b7280; }}
.arrow {{ text-align: center; color: #4b5563; font-size: 18px; margin: 2px 0; }}

details {{ margin: 8px 0; background: #111827; border-radius: 6px; }}
details summary {{ padding: 8px 14px; cursor: pointer; color: #60a5fa; font-size: 12px; user-select: none; }}
details summary:hover {{ background: #1a1b2e; }}
details[open] summary {{ border-bottom: 1px solid #2a2d3e; }}
details pre {{
  padding: 14px 18px; white-space: pre-wrap; word-break: break-word;
  font-size: 12px; color: #d1d5db; line-height: 1.7;
  font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", monospace;
  max-height: 700px; overflow-y: auto;
}}
.kb-content {{ max-height: 500px !important; }}
</style>
</head>
<body><div class="container">

<header>
<h1>🌊 AutoResearch · Idea Forge Timeline</h1>
<div class="sub">每日 cron 自动运行 · 更新于 {datetime.now().strftime("%Y-%m-%d %H:%M")} (UTC+8)</div>
<a class="nav-link" href="./index.html">← 信息聚合主页</a>
</header>

{stats_html}

<div class="tabs">
<button class="tab-btn active" onclick="showTab(event, 'timeline')">📅 每日 Timeline（种子 + 计划书）</button>
<button class="tab-btn" onclick="showTab(event, 'pipeline')">🔄 系统流程</button>
<button class="tab-btn" onclick="showTab(event, 'kb')">📘 B 领域知识库</button>
</div>

{timeline_html}
{pipeline_html}
{kb_html}

</div>
<script>
function showTab(ev, name) {{
  document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  ev.currentTarget.classList.add('active');
}}
</script>
</body></html>
'''

    output = PROJECT_ROOT / "ideas.html"
    output.write_text(page, encoding="utf-8")
    print(f"生成 {output} ({len(page)} 字节)")


if __name__ == "__main__":
    generate()
