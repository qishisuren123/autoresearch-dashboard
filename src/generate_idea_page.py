"""
生成 Idea Forge 可视化静态页面
部署到 GitHub Pages，避免 Gradio 服务依赖
路径: ideas.html (和主 index.html 并存)
"""

import json
import glob
import html
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
VERIFIED_DIR = DATA_DIR / "verified"
FORGE_DIR = DATA_DIR / "idea_forge"
KB_DIR = PROJECT_ROOT / "knowledge_base"


def load_latest_forge():
    files = sorted(glob.glob(str(FORGE_DIR / "forge_*.json")))
    for f in reversed(files):
        try:
            with open(f) as fp:
                data = json.load(fp)
            if data.get("summary", {}).get("total_plans", 0) > 0:
                return f, data
        except:
            continue
    if files:
        with open(files[-1]) as f:
            return files[-1], json.load(f)
    return None, None


def load_latest_seeds():
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


def esc(s):
    return html.escape(str(s))


def gen_stats(seeds, forge_data):
    seeds_n = len(seeds)
    kb_n = len([f for f in glob.glob(str(KB_DIR / "*.md")) if not f.endswith("README.md")])
    plans_n = forge_data.get("summary", {}).get("total_plans", 0) if forge_data else 0
    ideas_n = forge_data.get("summary", {}).get("total_ideas", 0) if forge_data else 0
    validated_n = forge_data.get("summary", {}).get("total_validated", 0) if forge_data else 0

    return f"""
<div class="stats">
    <div class="stat"><div class="n">{seeds_n}</div><div class="l">A 种子</div></div>
    <div class="stat"><div class="n">{kb_n}</div><div class="l">B 方向知识库</div></div>
    <div class="stat"><div class="n">{ideas_n}</div><div class="l">Idea 生成</div></div>
    <div class="stat"><div class="n">{validated_n}</div><div class="l">通过验证</div></div>
    <div class="stat"><div class="n">{plans_n}</div><div class="l">计划书</div></div>
</div>
"""


def gen_pipeline_tab():
    return """
<div class="tab-content" id="tab-pipeline">
<h2>🔄 系统流程</h2>

<h3>模块一：大浪淘沙（信息聚合 + 热点筛选）</h3>

<div class="info-box">
<strong>18 个信号源：</strong>
<ul>
<li><b>社区讨论</b>(5): Reddit (r/ML, r/LocalLLaMA, r/singularity) + Hacker News + Emergent Mind</li>
<li><b>大佬/Lab博客</b>(8): OpenAI / DeepMind / Google Research / MSR / BAIR / Raschka / Karpathy / HF Blog</li>
<li><b>中文媒体</b>(5): 机器之心 / 新智元 / 智东西 + 量子位 RSS + Leiphone RSS</li>
<li><b>学术源</b>(3): arXiv / HuggingFace Daily Papers / Paper Digest</li>
<li><b>顶会</b>: ICLR / ICML / NeurIPS / CVPR / ACL / EMNLP / AAAI / ECCV / ICCV</li>
<li><b>工程源</b>: GitHub Trending / MarkTechPost / VentureBeat</li>
</ul>
</div>

<div class="flow">
<div class="flow-step">采集 (300+ 条)</div>
<div class="arrow">↓</div>
<div class="flow-step">规则初筛（去商业噪声）</div>
<div class="arrow">↓</div>
<div class="flow-step">LLM(Gemini Flash) 精筛：是否学术研究相关</div>
<div class="arrow">↓</div>
<div class="flow-step highlight">VIP 白名单：被大佬（Sam Altman / Yann LeCun / 马斯克 等 50+人）提及的直接放行</div>
<div class="arrow">↓</div>
<div class="flow-step">LLM(Gemini Pro) 深度研判：核心 insight / A+B 潜力 / 可行性 / 判定</div>
<div class="arrow">↓</div>
<div class="flow-step success">输出：强推荐做 A 种子（每天 2-5 个）</div>
</div>

<h3>模块二：Idea Forge（A+B 生成 + 验证 + 共识检查 + 计划书）</h3>

<div class="flow">
<div class="flow-step">A 种子 × B 方向库 × 3 模型</div>
<div class="arrow">↓</div>
<div class="flow-step">Step 1: 独立构思（gemini-pro / claude-sonnet / gpt-5.5 各自生成）<br>
  <small>每个模型都被喂入：A 的核心 insight + B 的完整知识 MD</small></div>
<div class="arrow">↓</div>
<div class="flow-step">Step 2: 严格交叉验证（其他 2 个模型审稿，&gt;50% 通过）</div>
<div class="arrow">↓</div>
<div class="flow-step highlight">Step 2.5: 共识检查（对照 B 领域 MD，避免撞社区错误直觉）</div>
<div class="arrow">↓</div>
<div class="flow-step">Step 3: 生成完整计划书（预实验 + 完整实验 + 命令级步骤）</div>
<div class="arrow">↓</div>
<div class="flow-step success">输出：可直接执行的研究方案</div>
</div>

<h3>B 方向库如何创建</h3>

<div class="info-box">
<p><strong>不是自动生成的，是领域内的人手工维护。</strong></p>
<p>每个 MD 文件包含 5 个部分：</p>
<ol>
<li><b>社区共识</b>：大家都认同什么</li>
<li><b>路线之争</b>：有争议的观点</li>
<li><b>常见错误直觉（避坑）</b>：看起来合理但其实错的想法</li>
<li><b>可行创新切入点</b>：真正值得做的方向</li>
<li><b>数据集和基线</b>：实验时用什么</li>
</ol>
</div>

<h3>如何保证客观性</h3>

<div class="info-box">
<ol>
<li><b>多源交叉验证</b>：18 个独立信号源，跨源匹配才加分。HuggingFace 票数刻意降权（票可能被刷）。</li>
<li><b>多模型独立判断</b>：不让同一个模型既生成又审核。生成：3 个不同厂商模型（gemini / claude / gpt）。审核：其他 2 个模型交叉审稿。</li>
<li><b>领域常识兜底</b>：即使 LLM 判断都通过，还要对照人工维护的 B 领域 MD 做共识检查。</li>
<li><b>大佬名单白名单（有意偏向）</b>：一线大佬提及的工作直接放行——这不是纯客观，是在数据极少时利用专家信号。</li>
</ol>
</div>

<h3>系统的局限（诚实说明）</h3>

<div class="warn-box">
<ol>
<li><b>B 方向库还不够全</b>：当前只有 4 个方向，很多 AI 子领域没覆盖</li>
<li><b>LLM 生成的 idea 仍有"聪明但不深"的问题</b>：尤其在 B 领域知识不够精确时</li>
<li><b>GPT-5.5 中转站偶尔超时</b>：已加 3 次重试，但仍可能丢 5-10% 调用</li>
<li><b>共识检查依赖 MD 质量</b>：MD 写得不够深，检查就抓不住</li>
</ol>
</div>
</div>
"""


def gen_seeds_tab(seeds):
    if not seeds:
        return '<div class="tab-content" id="tab-seeds"><p>暂无强推荐种子</p></div>'

    content = f'<div class="tab-content" id="tab-seeds"><h2>🌱 A 种子池（{len(seeds)} 个强推荐）</h2>'
    content += '<p>这些是大浪淘沙筛出的「强推荐做 A 种子」的工作。</p>'

    for i, s in enumerate(seeds, 1):
        title = esc(s.get("title", ""))
        url = esc(s.get("reddit_url", s.get("hn_url", s.get("url", "#"))))
        conclusion = esc(s.get("conclusion", ""))[:300]
        channel = esc(s.get("channel", s.get("source", "")))
        comments = s.get("num_comments", 0)
        score = s.get("score", 0)
        jud = esc(s.get("llm_judgment", "").replace("**", ""))

        meta_parts = [f'<span class="ch">{channel}</span>']
        if comments:
            meta_parts.append(f'<span class="hot">{comments} 评论</span>')
        if score:
            meta_parts.append(f'<span>{score} 分</span>')

        content += f'''
<div class="card">
<div class="card-top">
<span class="rank">{i}</span>
<h4><a href="{url}" target="_blank">{title}</a></h4>
</div>
<div class="meta">{" ".join(meta_parts)}</div>
<div class="conclusion"><b>判定：</b>{conclusion}</div>
<details><summary>完整研判</summary><pre>{jud}</pre></details>
</div>
'''
    content += '</div>'
    return content


def gen_kb_tab():
    content = '<div class="tab-content" id="tab-kb"><h2>📘 B 领域深度知识库</h2>'
    content += '<p>由领域内专家手动维护（人为保证客观），AI 不自动修改。</p>'

    md_files = sorted(glob.glob(str(KB_DIR / "*.md")))
    md_files = [f for f in md_files if not f.endswith("README.md")]

    for f in md_files:
        name = Path(f).stem
        md_content = Path(f).read_text(encoding="utf-8")
        # 简单 md → html
        html_content = esc(md_content).replace("\n", "<br>")
        content += f'''
<div class="card">
<h4>📄 {name} <small>({len(md_content)} 字符)</small></h4>
<details><summary>展开查看完整知识</summary><pre class="kb-content">{esc(md_content)}</pre></details>
</div>
'''
    content += '</div>'
    return content


def gen_plans_tab(fpath, data):
    content = '<div class="tab-content" id="tab-plans"><h2>💡 最新方案（Idea + 计划书）</h2>'

    if not data:
        content += '<p>暂无 Forge 结果</p></div>'
        return content

    summary = data.get("summary", {})
    content += f'''
<div class="info-box">
<b>文件：</b>{esc(Path(fpath).name if fpath else "")}<br>
<b>时间：</b>{esc(data.get("generated_at", "")[:19])}<br>
<b>处理种子：</b>{summary.get("seeds_processed", 0)}
&nbsp;|&nbsp;<b>生成 idea：</b>{summary.get("total_ideas", 0)}
&nbsp;|&nbsp;<b>通过验证：</b>{summary.get("total_validated", 0)}
&nbsp;|&nbsp;<b>计划书：</b>{summary.get("total_plans", 0)}
</div>
'''

    for i, r in enumerate(data.get("results", []), 1):
        content += f'<h3>种子 {i}: {esc(r["seed_title"])}</h3>'
        content += f'<p>生成 {r["total_ideas"]} idea，通过 {r["validated"]} 个</p>'

        for j, p in enumerate(r.get("plans", []), 1):
            model = esc(p.get("source_model", ""))
            b_domain = esc(p.get("b_domain", ""))
            b_problem = esc(p.get("b_problem", ""))
            idea_text = esc(p.get("idea_text", "").replace("**", ""))
            plan_text = esc(p.get("plan", "").replace("**", ""))
            cc = p.get("consensus_check", {})

            cc_html = ""
            if cc:
                ok = cc.get("passed", False)
                icon = "✅" if ok else "❌"
                reason = esc(cc.get("reason", "")[:300])
                cc_html = f'<div class="cc"><b>共识检查：{icon}</b> {reason}</div>'

            content += f'''
<div class="card plan-card">
<div class="plan-header">
<span class="plan-rank">方案 {i}.{j}</span>
<span class="model-tag">{model}</span>
<span class="domain-tag">{b_domain}</span>
</div>
<div class="b-problem"><b>B 问题：</b>{b_problem}</div>
{cc_html}
<details><summary>📌 Idea 原文</summary><pre>{idea_text}</pre></details>
<details><summary>📋 完整计划书（预实验 + 完整实验）</summary><pre>{plan_text}</pre></details>
</div>
'''
    content += '</div>'
    return content


def generate():
    seeds = load_latest_seeds()
    fpath, forge_data = load_latest_forge()

    stats = gen_stats(seeds, forge_data)
    pipeline = gen_pipeline_tab()
    seeds_tab = gen_seeds_tab(seeds)
    kb_tab = gen_kb_tab()
    plans_tab = gen_plans_tab(fpath, forge_data)

    html_page = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>大浪淘沙 - Idea Forge</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
  font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif;
  background: #0f1117; color: #e4e4e7; line-height: 1.6; padding: 20px;
}}
.container {{ max-width: 1200px; margin: 0 auto; }}
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
.nav-link {{ display: inline-block; margin-top: 10px; color: #60a5fa; text-decoration: none; }}

.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 10px; margin-bottom: 20px; }}
.stat {{ background: #1a1b2e; border: 1px solid #2a2d3e; border-radius: 10px; padding: 14px; text-align: center; }}
.stat .n {{ font-size: 28px; font-weight: 700; color: #60a5fa; }}
.stat .l {{ color: #9ca3af; font-size: 11px; margin-top: 2px; }}

.tabs {{ display: flex; gap: 0; border-bottom: 1px solid #2a2d3e; margin-bottom: 20px; }}
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
.tab-content p {{ color: #d1d5db; margin-bottom: 10px; }}

.card {{
  background: #1a1b2e; border: 1px solid #2a2d3e; border-radius: 12px;
  padding: 18px; margin-bottom: 14px; transition: border-color 0.2s;
}}
.card:hover {{ border-color: #3b82f6; }}
.card-top {{ display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }}
.rank {{
  background: #111827; color: #60a5fa; font-weight: 700; font-size: 13px;
  width: 30px; height: 30px; border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
}}
.card h4 {{ font-size: 14px; color: #f4f4f5; line-height: 1.4; flex: 1; }}
.card h4 a {{ color: #f4f4f5; text-decoration: none; }}
.card h4 a:hover {{ color: #60a5fa; }}
.meta {{ font-size: 11px; color: #6b7280; margin-bottom: 8px; display: flex; gap: 10px; flex-wrap: wrap; }}
.meta .ch {{ color: #a78bfa; font-weight: 500; }}
.meta .hot {{ color: #f59e0b; }}
.conclusion {{ font-size: 12.5px; color: #d1d5db; margin: 8px 0; padding: 8px 12px; background: #111827; border-left: 3px solid #60a5fa; border-radius: 4px; }}

.info-box {{
  background: #111827; border-left: 3px solid #60a5fa; border-radius: 4px;
  padding: 14px 18px; margin: 14px 0; font-size: 13px; color: #d1d5db;
}}
.info-box ul, .info-box ol {{ margin: 8px 0 0 20px; }}
.info-box li {{ margin: 5px 0; }}
.warn-box {{
  background: #1f1a11; border-left: 3px solid #f59e0b; border-radius: 4px;
  padding: 14px 18px; margin: 14px 0; font-size: 13px; color: #d1d5db;
}}

.flow {{ padding: 14px 0; }}
.flow-step {{
  background: #111827; border: 1px solid #2a2d3e; border-radius: 8px;
  padding: 10px 16px; margin: 6px 0; font-size: 13px; color: #d1d5db;
}}
.flow-step.highlight {{ border-left: 3px solid #f59e0b; }}
.flow-step.success {{ border-left: 3px solid #34d399; background: #0f1f16; }}
.flow-step small {{ color: #6b7280; }}
.arrow {{ text-align: center; color: #4b5563; font-size: 18px; margin: 2px 0; }}

details {{ margin: 10px 0; background: #111827; border-radius: 6px; }}
details summary {{ padding: 10px 14px; cursor: pointer; color: #60a5fa; font-size: 12.5px; user-select: none; }}
details summary:hover {{ background: #1a1b2e; }}
details[open] summary {{ border-bottom: 1px solid #2a2d3e; }}
details pre {{
  padding: 14px 18px; white-space: pre-wrap; word-break: break-word;
  font-size: 12px; color: #d1d5db; line-height: 1.7;
  font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", monospace;
  max-height: 600px; overflow-y: auto;
}}

.kb-content {{ max-height: 500px !important; }}

.plan-card {{ border-left: 3px solid #34d399; }}
.plan-header {{ display: flex; gap: 10px; margin-bottom: 8px; align-items: center; flex-wrap: wrap; }}
.plan-rank {{ background: #064e3b; color: #34d399; padding: 3px 10px; border-radius: 5px; font-size: 12px; font-weight: 600; }}
.model-tag {{ background: #1e3a5f; color: #60a5fa; padding: 3px 10px; border-radius: 5px; font-size: 11px; }}
.domain-tag {{ background: #3b2b5f; color: #a78bfa; padding: 3px 10px; border-radius: 5px; font-size: 11px; }}
.b-problem {{ font-size: 12.5px; color: #d1d5db; margin: 8px 0; padding: 8px; background: #111827; border-radius: 4px; }}
.cc {{ font-size: 12px; color: #fbbf24; margin: 8px 0; padding: 8px 12px; background: #1a1b2e; border-radius: 4px; }}
</style>
</head>
<body><div class="container">

<header>
<h1>🌊 大浪淘沙 - AI 研究方案锻造</h1>
<div class="sub">每日自动运行 · 更新于 {datetime.now().strftime("%Y-%m-%d %H:%M")}</div>
<a class="nav-link" href="./index.html">← 返回信息聚合主页</a>
</header>

{stats}

<div class="tabs">
<button class="tab-btn active" onclick="showTab('pipeline')">📋 流程说明</button>
<button class="tab-btn" onclick="showTab('seeds')">🌱 A 种子池</button>
<button class="tab-btn" onclick="showTab('kb')">📘 B 领域知识库</button>
<button class="tab-btn" onclick="showTab('plans')">💡 最新方案</button>
</div>

{pipeline}
{seeds_tab}
{kb_tab}
{plans_tab}

</div>
<script>
function showTab(name) {{
  document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  event.target.classList.add('active');
}}
// 默认显示第一个
document.getElementById('tab-pipeline').classList.add('active');
</script>
</body></html>
'''

    output = PROJECT_ROOT / "ideas.html"
    output.write_text(html_page, encoding="utf-8")
    print(f"生成 {output} ({len(html_page)} 字节)")


if __name__ == "__main__":
    generate()
