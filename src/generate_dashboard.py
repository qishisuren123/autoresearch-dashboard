"""
生成静态 HTML Dashboard
- 支持历史日期切换
- 候选池/储备池折叠显示
- 每天结果独立存储
"""

import json
import glob
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
VERIFIED_DIR = DATA_DIR / "verified"
CANDIDATES_DIR = DATA_DIR / "candidates"


def get_available_dates():
    """获取所有有结果的日期"""
    dates = set()
    for f in glob.glob(str(VERIFIED_DIR / "*.json")):
        fname = Path(f).stem
        # 提取日期部分 (YYYYMMDD)
        parts = fname.split("_")
        for part in parts:
            if len(part) == 8 and part.isdigit():
                dates.add(part)
                break
    return sorted(dates, reverse=True)


def load_latest_result():
    """加载最新的 pipeline 结果"""
    # 优先 final_*, 其次 pipeline_v4_*, pipeline_v3_*
    for pattern in ["final_*.json", "pipeline_v4_*.json", "pipeline_v5_*.json", "pipeline_v3_*.json"]:
        files = sorted(glob.glob(str(VERIFIED_DIR / pattern)))
        if files:
            with open(files[-1]) as f:
                return json.load(f), Path(files[-1]).stem
    return None, None


def load_reserve_pool():
    """加载储备池"""
    reserve_file = CANDIDATES_DIR / "reserve_pool.json"
    if reserve_file.exists():
        with open(reserve_file) as f:
            return json.load(f)
    return []


def generate_html():
    data, source_name = load_latest_result()
    if not data:
        print("No data found")
        return

    candidates = data.get("final_candidates", data.get("top_candidates", []))
    stats = data.get("stats", {})
    reserve = load_reserve_pool()
    dates = get_available_dates()

    # 日期选择器 HTML
    date_options = ""
    for d in dates[:30]:
        formatted = f"{d[:4]}-{d[4:6]}-{d[6:8]}"
        date_options += f'<option value="{d}">{formatted}</option>\n'

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8"><title>大浪淘沙</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,sans-serif;background:#0f1117;color:#e4e4e7;line-height:1.7;padding:20px}}
.container{{max-width:1100px;margin:0 auto}}
header{{background:linear-gradient(135deg,#1a1b2e,#16213e);border:1px solid #2a2d3e;border-radius:12px;padding:28px;margin-bottom:20px;display:flex;justify-content:space-between;align-items:center}}
header h1{{font-size:22px;background:linear-gradient(90deg,#60a5fa,#a78bfa);-webkit-background-clip:text;-webkit-text-fill-color:transparent}}
.sub{{color:#9ca3af;font-size:12px;margin-top:4px}}
.date-nav{{display:flex;align-items:center;gap:8px}}
.date-nav select{{background:#111827;color:#e4e4e7;border:1px solid #2a2d3e;border-radius:6px;padding:6px 12px;font-size:13px}}
.info{{background:#111827;border:1px solid #2a2d3e;border-radius:8px;padding:12px 16px;margin-bottom:16px;font-size:12px;color:#9ca3af;line-height:1.8}}
.info strong{{color:#60a5fa}}
.stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:8px;margin-bottom:16px}}
.stat{{background:#1a1b2e;border:1px solid #2a2d3e;border-radius:8px;padding:10px;text-align:center}}
.stat .n{{font-size:22px;font-weight:700;color:#60a5fa}}
.stat .l{{color:#9ca3af;font-size:10px}}
.card{{background:#1a1b2e;border:1px solid #2a2d3e;border-radius:10px;padding:18px;margin-bottom:12px;transition:border-color .2s}}
.card:hover{{border-color:#3b82f6}}
.card-top{{display:flex;align-items:center;gap:8px;margin-bottom:6px}}
.rank{{background:#111827;color:#60a5fa;font-weight:700;font-size:12px;min-width:24px;height:24px;border-radius:5px;display:flex;align-items:center;justify-content:center}}
.card h3{{font-size:13px;color:#f4f4f5;line-height:1.4;flex:1}}
.card h3 a{{color:#f4f4f5;text-decoration:none}}.card h3 a:hover{{color:#60a5fa}}
.meta{{font-size:11px;color:#6b7280;margin-bottom:6px;display:flex;gap:10px;flex-wrap:wrap}}
.meta .ch{{color:#a78bfa;font-weight:500}}.meta .hot{{color:#f59e0b}}
.tag{{display:inline-block;padding:2px 8px;border-radius:4px;font-size:10px;font-weight:600;margin-bottom:8px}}
.tag-strong{{background:#064e3b;color:#34d399}}.tag-worth{{background:#422006;color:#fbbf24}}.tag-skip{{background:#1f2937;color:#6b7280}}
.judgment{{background:#111827;border-radius:6px;padding:12px;font-size:11.5px;line-height:1.8;color:#d1d5db}}
.judgment .jl{{color:#60a5fa;font-weight:600}}
a{{color:#60a5fa;text-decoration:none}}a:hover{{text-decoration:underline}}
.divider{{border-top:1px solid #2a2d3e;margin:20px 0 12px;padding-top:12px}}
.divider h2{{font-size:15px;color:#a78bfa;margin-bottom:2px}}.divider .desc{{font-size:11px;color:#6b7280}}
.collapsible{{margin-top:16px}}
.collapse-btn{{background:#111827;border:1px solid #2a2d3e;color:#9ca3af;padding:10px 16px;border-radius:8px;cursor:pointer;font-size:13px;width:100%;text-align:left;display:flex;justify-content:space-between;align-items:center}}
.collapse-btn:hover{{border-color:#3b82f6;color:#e4e4e7}}
.collapse-content{{display:none;padding:12px 0}}
.collapse-content.open{{display:block}}
.reserve-item{{background:#111827;border-radius:6px;padding:10px 14px;margin:6px 0;font-size:12px;display:flex;justify-content:space-between;align-items:center}}
.reserve-item .title{{color:#d1d5db;flex:1}}.reserve-item .date{{color:#6b7280;font-size:11px}}
</style>
</head>
<body><div class="container">
<header>
<div>
<h1>大浪淘沙 - 每日研究热点</h1>
<div class="sub">{datetime.now().strftime('%Y-%m-%d %H:%M')} | 数据源: {source_name}</div>
</div>
<div class="date-nav">
<select onchange="alert('历史查看功能: 请在 data/verified/ 目录下查找对应日期的 JSON 文件')">
<option value="">选择历史日期</option>
{date_options}
</select>
</div>
</header>

<div class="info">
<strong>信号源:</strong> Reddit/HN 社区讨论 · Emergent Mind 社交热度 · OpenAI/DeepMind/BAIR/Google Research 博客 · 机器之心/新智元/智东西 · Paper Digest 顶会<br>
<strong>顶会:</strong> ICLR / ICML / NeurIPS / CVPR / ACL / EMNLP / AAAI / ECCV / ICCV<br>
<strong>筛选:</strong> 规则初筛 → LLM(Flash) insight 过滤 → LLM(Pro) A+B 迁移研判
</div>

<div class="stats">
'''

    for key, label in [
        ("community_discussion", "社区讨论"),
        ("emergent_mind", "Emergent Mind"),
        ("research_blogs", "Lab 博客"),
        ("conference_highlights", "顶会"),
        ("total_final", "最终候选"),
    ]:
        val = stats.get(key, "—")
        html += f'<div class="stat"><div class="n">{val}</div><div class="l">{label}</div></div>\n'

    html += '</div>\n'

    # 候选卡片
    rank = 1
    for c in candidates:
        title = c.get('title', '')[:80]
        url = c.get('reddit_url', c.get('hn_url', c.get('url', '#')))
        comments = c.get('num_comments', 0)
        score = c.get('score', 0)
        channel = c.get('channel', c.get('blog_name', c.get('source', '')))
        conclusion = c.get('conclusion', '')
        judgment = c.get('llm_judgment', '')

        # 标签完全以 LLM 最终判定为准
        if '强推荐' in conclusion:
            tc, tt = 'tag-strong', '强推荐做 A 种子'
        elif '值得' in conclusion or '深入' in conclusion:
            tc, tt = 'tag-worth', '值得深入了解'
        elif '不适合' in conclusion:
            tc, tt = 'tag-skip', '不适合做 A 种子'
        elif conclusion:
            # 有判定但不匹配上面的，直接用原文
            tc, tt = 'tag-skip', conclusion[:20]
        else:
            tc, tt = 'tag-skip', '待判断'

        jhtml = ''
        if judgment and judgment != '调用失败':
            for line in judgment.split('\n'):
                line = line.strip()
                if not line:
                    continue
                line = line.replace('**', '')
                for lab in ['核心insight', '核心 insight', '社区热议原因', '方法简洁度',
                           'A+B潜力', 'A+B 潜力', '可行性', '最终判定']:
                    if lab in line:
                        line = line.replace(lab, f'<span class="jl">{lab}</span>', 1)
                        break
                jhtml += f'<div>{line}</div>'

        meta_parts = [f'<span class="ch">{channel}</span>']
        if comments:
            meta_parts.append(f'<span class="hot">{comments} 评论</span>')
        if score:
            meta_parts.append(f'<span>{score} 分</span>')

        html += f'''<div class="card">
<div class="card-top"><div class="rank">{rank}</div><h3><a href="{url}" target="_blank">{title}</a></h3></div>
<div class="meta">{' '.join(meta_parts)}</div>
<span class="tag {tc}">{tt}</span>
<div class="judgment">{jhtml}</div>
</div>\n'''
        rank += 1

    # 储备池（折叠）
    html += f'''
<div class="collapsible">
<button class="collapse-btn" onclick="this.nextElementSibling.classList.toggle('open')">
<span>📦 储备池（{len(reserve)} 条 | 15天内无起色自动移除）</span>
<span>▼</span>
</button>
<div class="collapse-content">
'''
    if reserve:
        for item in reserve[:30]:
            title = item.get("title", "")[:60]
            added = item.get("added_to_reserve", "")[:10]
            html += f'<div class="reserve-item"><span class="title">{title}</span><span class="date">{added}</span></div>\n'
    else:
        html += '<div class="reserve-item"><span class="title">储备池为空</span></div>\n'

    html += '</div></div>\n'

    html += '</div></body></html>'

    # 写入
    output_file = PROJECT_ROOT / "index.html"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Generated {output_file} ({len(html)} bytes)")


if __name__ == "__main__":
    generate_html()
