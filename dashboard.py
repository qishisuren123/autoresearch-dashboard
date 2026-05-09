"""AutoResearch 可视化仪表盘"""

import json
import glob
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template_string

app = Flask(__name__)

DATA_DIR = Path(__file__).parent / "data"
CANDIDATES_DIR = DATA_DIR / "candidates"
VERIFIED_DIR = DATA_DIR / "verified"

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AutoResearch Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0f1117;
            color: #e4e4e7;
            line-height: 1.6;
        }
        .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
        header {
            background: linear-gradient(135deg, #1a1b2e 0%, #16213e 100%);
            border: 1px solid #2a2d3e;
            border-radius: 12px;
            padding: 30px;
            margin-bottom: 24px;
        }
        header h1 {
            font-size: 28px;
            background: linear-gradient(90deg, #60a5fa, #a78bfa);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        header .subtitle { color: #9ca3af; margin-top: 8px; font-size: 14px; }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }
        .stat-card {
            background: #1a1b2e;
            border: 1px solid #2a2d3e;
            border-radius: 10px;
            padding: 20px;
            text-align: center;
        }
        .stat-card .number {
            font-size: 36px;
            font-weight: 700;
            color: #60a5fa;
        }
        .stat-card .label { color: #9ca3af; font-size: 13px; margin-top: 4px; }
        .section {
            background: #1a1b2e;
            border: 1px solid #2a2d3e;
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 24px;
        }
        .section h2 {
            font-size: 18px;
            margin-bottom: 16px;
            color: #f4f4f5;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .section h2 .badge {
            background: #3b82f6;
            color: white;
            font-size: 12px;
            padding: 2px 8px;
            border-radius: 10px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th {
            text-align: left;
            padding: 12px 16px;
            background: #111827;
            color: #9ca3af;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            border-bottom: 1px solid #2a2d3e;
        }
        td {
            padding: 12px 16px;
            border-bottom: 1px solid #1f2937;
            font-size: 14px;
        }
        tr:hover { background: #111827; }
        .verdict-genuine { color: #34d399; font-weight: 600; }
        .verdict-likely { color: #fbbf24; font-weight: 600; }
        .verdict-uncertain { color: #f97316; font-weight: 600; }
        .verdict-promoted { color: #ef4444; font-weight: 600; }
        .verdict-nodata { color: #6b7280; }
        .score-bar {
            display: inline-block;
            height: 6px;
            border-radius: 3px;
            background: #374151;
            width: 100px;
            position: relative;
        }
        .score-bar .fill {
            position: absolute;
            left: 0;
            top: 0;
            height: 100%;
            border-radius: 3px;
            background: linear-gradient(90deg, #3b82f6, #8b5cf6);
        }
        .tag {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 11px;
            margin: 1px;
        }
        .tag-academic { background: #1e3a5f; color: #60a5fa; }
        .tag-engineering { background: #1a3326; color: #34d399; }
        .tag-chinese { background: #3b2020; color: #fca5a5; }
        .tag-english { background: #2d2b1f; color: #fde047; }
        .signals {
            display: flex;
            flex-wrap: wrap;
            gap: 4px;
        }
        .signal {
            font-size: 11px;
            padding: 2px 6px;
            background: #1f2937;
            border-radius: 3px;
            color: #9ca3af;
        }
        a { color: #60a5fa; text-decoration: none; }
        a:hover { text-decoration: underline; }
        .channel-status {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 12px;
        }
        .channel {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 12px 16px;
            background: #111827;
            border-radius: 8px;
        }
        .channel .dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
        }
        .dot-green { background: #34d399; }
        .dot-red { background: #ef4444; }
        .dot-yellow { background: #fbbf24; }
        .channel .name { font-weight: 500; flex: 1; }
        .channel .count { color: #9ca3af; font-size: 13px; }
        .footer {
            text-align: center;
            padding: 20px;
            color: #6b7280;
            font-size: 12px;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>AutoResearch Dashboard</h1>
            <div class="subtitle">Idea 采集系统 - 关 1 (主流媒体共识) + 关 2 (社交舆情验证) | 更新时间: {{ update_time }}</div>
        </header>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="number">{{ total_collected }}</div>
                <div class="label">总采集量</div>
            </div>
            <div class="stat-card">
                <div class="number">{{ gate1_count }}</div>
                <div class="label">关 1 候选</div>
            </div>
            <div class="stat-card">
                <div class="number">{{ genuine_count }}</div>
                <div class="label">关 2 真火</div>
            </div>
            <div class="stat-card">
                <div class="number">{{ channels_ok }}</div>
                <div class="label">渠道在线</div>
            </div>
        </div>

        <div class="section">
            <h2>高置信 A 候选清单 <span class="badge">关 2 验证通过</span></h2>
            <table>
                <thead>
                    <tr>
                        <th>#</th>
                        <th>话题</th>
                        <th>判定</th>
                        <th>真实度</th>
                        <th>信号</th>
                        <th>跨源类别</th>
                    </tr>
                </thead>
                <tbody>
                {% for item in verified %}
                    <tr>
                        <td>{{ loop.index }}</td>
                        <td>
                            <a href="{{ item.url }}" target="_blank">{{ item.title[:70] }}{% if item.title|length > 70 %}...{% endif %}</a>
                            {% if item.arxiv_id %}<br><span style="color:#6b7280;font-size:11px;">arXiv:{{ item.arxiv_id }}</span>{% endif %}
                        </td>
                        <td>
                            {% if item.gate2_verdict == 'genuine_hot' %}<span class="verdict-genuine">真火</span>
                            {% elif item.gate2_verdict == 'likely_genuine' %}<span class="verdict-likely">大概率真</span>
                            {% elif item.gate2_verdict == 'uncertain' %}<span class="verdict-uncertain">不确定</span>
                            {% elif item.gate2_verdict == 'likely_promoted' %}<span class="verdict-promoted">疑似推广</span>
                            {% else %}<span class="verdict-nodata">无数据</span>{% endif %}
                        </td>
                        <td>
                            <div class="score-bar"><div class="fill" style="width:{{ (item.gate2_authenticity * 100)|int }}%"></div></div>
                            <span style="font-size:12px;color:#9ca3af;margin-left:8px;">{{ "%.2f"|format(item.gate2_authenticity) }}</span>
                        </td>
                        <td>
                            <div class="signals">
                            {% for sig in item.gate2_reddit.get('signals', []) %}
                                <span class="signal">{{ sig }}</span>
                            {% endfor %}
                            </div>
                        </td>
                        <td>
                            {% for cat in item.categories_hit %}
                                <span class="tag tag-{{ cat.split('_')[0] }}">{{ cat }}</span>
                            {% endfor %}
                        </td>
                    </tr>
                {% endfor %}
                </tbody>
            </table>
        </div>

        <div class="section">
            <h2>关 1 全部候选 <span class="badge">{{ gate1_count }} 个</span></h2>
            <table>
                <thead>
                    <tr>
                        <th>#</th>
                        <th>话题</th>
                        <th>共识分</th>
                        <th>跨源类别</th>
                        <th>社区信号</th>
                        <th>备注</th>
                    </tr>
                </thead>
                <tbody>
                {% for item in gate1 %}
                    <tr>
                        <td>{{ loop.index }}</td>
                        <td><a href="{{ item.url }}" target="_blank">{{ item.title[:65] }}{% if item.title|length > 65 %}...{% endif %}</a></td>
                        <td><strong>{{ "%.1f"|format(item.consensus_score) }}</strong></td>
                        <td>
                            {% for cat in item.categories_hit %}
                                <span class="tag tag-{{ cat.split('_')[0] }}">{{ cat }}</span>
                            {% endfor %}
                        </td>
                        <td>
                            {% if item.upvotes %}HF:{{ item.upvotes }}票 {% endif %}
                            {% if item.reddit_score %}Reddit:{{ item.reddit_score }}↑ {% endif %}
                            {% if item.github_stars_today %}GitHub:{{ item.github_stars_today }} {% endif %}
                        </td>
                        <td style="font-size:12px;color:#6b7280;">{{ item.note }}</td>
                    </tr>
                {% endfor %}
                </tbody>
            </table>
        </div>

        <div class="section">
            <h2>渠道状态</h2>
            <div class="channel-status">
                {% for ch in channels %}
                <div class="channel">
                    <div class="dot {{ ch.dot }}"></div>
                    <div class="name">{{ ch.name }}</div>
                    <div class="count">{{ ch.status }}</div>
                </div>
                {% endfor %}
            </div>
        </div>

        <div class="footer">
            AutoResearch Idea Collection System | {{ update_time }}
        </div>
    </div>
</body>
</html>
"""


def load_data():
    """加载最新数据"""
    gate1_files = sorted(glob.glob(str(CANDIDATES_DIR / "gate1_consensus_*.json")))
    verified_files = sorted(glob.glob(str(VERIFIED_DIR / "gate2_verified_*.json")))

    gate1 = []
    if gate1_files:
        with open(gate1_files[-1]) as f:
            gate1 = json.load(f)

    verified = []
    if verified_files:
        with open(verified_files[-1]) as f:
            verified = json.load(f)

    # 统计各渠道采集量
    total = 0
    channel_counts = {}
    for fpath in glob.glob(str(CANDIDATES_DIR / "*.json")):
        fname = Path(fpath).stem
        if fname.startswith("gate1"):
            continue
        with open(fpath) as f:
            data = json.load(f)
            count = len(data)
            total += count
            channel_counts[fname] = count

    return gate1, verified, total, channel_counts


@app.route("/")
def index():
    gate1, verified, total_collected, channel_counts = load_data()

    genuine_count = len([v for v in verified if v.get("gate2_verdict") in ("genuine_hot", "likely_genuine")])

    channels = [
        {"name": "arXiv", "status": f"{channel_counts.get('arxiv_20260509', 0)} 篇", "dot": "dot-green"},
        {"name": "HuggingFace Papers", "status": f"{channel_counts.get('hf_papers_20260508', 0)} 篇", "dot": "dot-green"},
        {"name": "量子位 RSS", "status": "10 篇", "dot": "dot-green"},
        {"name": "Leiphone RSS", "status": "20 篇", "dot": "dot-green"},
        {"name": "MarkTechPost RSS", "status": "10 篇", "dot": "dot-green"},
        {"name": "VentureBeat RSS", "status": "7 篇", "dot": "dot-green"},
        {"name": "Reddit", "status": f"{channel_counts.get('reddit_20260509', 0)} 帖", "dot": "dot-green"},
        {"name": "GitHub Trending", "status": f"{channel_counts.get('github_trending_20260509', 0)} 项目", "dot": "dot-green"},
        {"name": "Hacker News", "status": f"{channel_counts.get('hackernews_20260508', 0)} 条", "dot": "dot-green"},
        {"name": "机器之心", "status": "不可用 (反爬)", "dot": "dot-red"},
        {"name": "Twitter/X", "status": "待接入 ($200/月)", "dot": "dot-yellow"},
        {"name": "小红书", "status": "待接入 (深灰)", "dot": "dot-yellow"},
    ]

    return render_template_string(
        HTML_TEMPLATE,
        update_time=datetime.now().strftime("%Y-%m-%d %H:%M"),
        total_collected=total_collected,
        gate1_count=len(gate1),
        genuine_count=genuine_count,
        channels_ok=9,
        verified=verified,
        gate1=gate1,
        channels=channels,
    )


if __name__ == "__main__":
    print("\n  AutoResearch Dashboard 启动中...")
    print("  访问地址: http://0.0.0.0:5000")
    print("  按 Ctrl+C 停止\n")
    app.run(host="0.0.0.0", port=5000, debug=False)
