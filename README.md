# AutoResearch - Idea 采集系统

## 系统全景

```
┌─────────────────────────────────────────────────────────────────────┐
│                     AutoResearch 系统流程                             │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ Stage 1: 数据采集（7 个采集器并行）                              │ │
│  │                                                                 │ │
│  │  arXiv ──┐                                                      │ │
│  │  HF Papers ──┐                                                  │ │
│  │  量子位 RSS ──┤                                                  │ │
│  │  Leiphone RSS ──┤──→ 原始候选池（今日 301 条）                   │ │
│  │  MarkTechPost RSS ──┤                                           │ │
│  │  VentureBeat RSS ──┤                                            │ │
│  │  Reddit ──┤                                                     │ │
│  │  Hacker News ──┤                                                │ │
│  │  GitHub Trending ──┘                                            │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                          ↓                                           │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ Stage 2: 学术相关性过滤                                         │ │
│  │                                                                 │ │
│  │  输入: 301 条 → 匹配学术关键词 + 排除商业噪声 → 输出: 184 条    │ │
│  │                                                                 │ │
│  │  过滤掉: 招聘、融资、产品发布会、广告、非技术内容               │ │
│  │  保留:   方法论、模型、架构、训练、评估、数据集相关             │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                          ↓                                           │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ Stage 3: 多维度候选构建 + 跨源匹配                              │ │
│  │                                                                 │ │
│  │  维度 1: HF Daily Papers 高票论文（社区直接投票认可）           │ │
│  │  维度 2: 中文AI媒体报道 ↔ 跨语言匹配到论文                     │ │
│  │  维度 3: 英文AI媒体报道 ↔ 跨语言匹配到论文                     │ │
│  │  维度 4: Reddit 学术讨论（[R]/[D] 标签，score≥100）            │ │
│  │  维度 5: arXiv 论文被多源提及                                   │ │
│  │                                                                 │ │
│  │  跨语言匹配方法: 提取专有名词/技术术语做桥梁                    │ │
│  │  （如 "Anthropic", "DeepSeek", "MoE", "Attention" 等）         │ │
│  │                                                                 │ │
│  │  输出: 58 个候选                                                │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                          ↓                                           │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ Stage 4: 综合打分（偏学术权重）                                 │ │
│  │                                                                 │ │
│  │  打分规则:                                                      │ │
│  │    HF upvotes ≥80 → +5分                                       │ │
│  │    HF upvotes ≥50 → +4分                                       │ │
│  │    HF upvotes ≥30 → +3分                                       │ │
│  │    HF upvotes ≥15 → +2分                                       │ │
│  │    跨源命中每个 → +1.5分                                        │ │
│  │    中文媒体报道 → +1.5分                                        │ │
│  │    英文媒体报道 → +1.0分                                        │ │
│  │    Reddit score≥300 → +2分                                      │ │
│  │    有 arxiv paper → +1分                                        │ │
│  │    GitHub stars≥100 → +1分                                      │ │
│  │                                                                 │ │
│  │  排序后取 Top-20                                                │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                          ↓                                           │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ Stage 5: 生成结构化总结                                         │ │
│  │                                                                 │ │
│  │  每个候选输出:                                                  │ │
│  │    - 标题                                                       │ │
│  │    - 在做什么（abstract 摘要）                                  │ │
│  │    - arXiv ID                                                   │ │
│  │    - 证据链（哪些来源证明了它）                                 │ │
│  │    - 推荐等级（强推荐/值得关注/参考）                           │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                          ↓                                           │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ Stage 6: 输出 + 可视化                                          │ │
│  │                                                                 │ │
│  │  → JSON 数据: data/verified/pipeline_v2_YYYYMMDD.json           │ │
│  │  → 静态 HTML: index.html → GitHub Pages 可视化                  │ │
│  │  → 每日报告: data/DAILY_REPORT_YYYYMMDD.md                     │ │
│  └────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 项目结构

```
AutoResearch/
├── run.py                          # v1 入口（关1+关2，含Reddit舆情验证）
├── dashboard.py                    # Flask 动态仪表盘（端口问题时不用）
├── index.html                      # 静态 HTML 仪表盘（GitHub Pages 部署）
├── CHANNEL_STATUS.md               # 各渠道接入状态详细记录
│
├── config/
│   └── settings.py                 # 全局配置（源地址、关键词、权重）
│
├── src/
│   ├── pipeline_gate1.py           # v1 关1: 共识筛选（旧版，基于标题词重叠）
│   ├── pipeline_v2.py              # v2 主流程（当前使用）
│   │
│   ├── collectors/                 # 各渠道采集器
│   │   ├── arxiv_collector.py      # arXiv 官方API（白色）
│   │   ├── hf_papers_collector.py  # HuggingFace Daily Papers API（白色）
│   │   ├── rss_collector.py        # RSS 聚合（量子位/Leiphone/MarkTechPost/VB）
│   │   ├── reddit_collector.py     # Reddit 公开 JSON 端点（白色）
│   │   ├── hackernews_collector.py # HN Firebase API（白色）
│   │   ├── github_trending_collector.py  # GitHub Trending HTML 解析（白色）
│   │   └── jiqizhixin_collector.py # 机器之心（❌ 不可用，已记录原因）
│   │
│   └── analyzers/
│       └── sentiment_analyzer.py   # 关2: Reddit 舆情验证（真火/推广判定）
│
└── data/
    ├── candidates/                 # 各采集器原始输出（每日 JSON）
    │   ├── arxiv_YYYYMMDD.json
    │   ├── hf_papers_YYYYMMDD.json
    │   ├── rss_YYYYMMDD.json
    │   ├── reddit_YYYYMMDD.json
    │   ├── hackernews_YYYYMMDD.json
    │   ├── github_trending_YYYYMMDD.json
    │   └── gate1_consensus_YYYYMMDD.json
    │
    ├── verified/                   # 验证后的结果
    │   ├── gate2_verified_YYYYMMDD.json   # v1 舆情验证结果
    │   └── pipeline_v2_YYYYMMDD.json      # v2 最终输出（当前使用）
    │
    └── DAILY_REPORT_YYYYMMDD.md    # 每日人工可读报告
```

---

## 运行方式

### 一键运行 v2 流水线（推荐）

```bash
cd /data/renyiming/AutoResearch
python3 src/pipeline_v2.py
```

输出:
- 终端打印 Top-20 候选 + 证据链
- `data/verified/pipeline_v2_YYYYMMDD.json` 完整数据

### 运行 v1（含 Reddit 舆情二次验证）

```bash
python3 run.py
```

### 更新 GitHub Pages 仪表盘

```bash
# 跑完 pipeline_v2 后，重新生成 index.html 并推送
python3 -c "... (见 dashboard 生成脚本)"
git add index.html && git commit -m "Daily update" && git push origin gh-pages
```

### 单独测试某个采集器

```bash
python3 src/collectors/arxiv_collector.py
python3 src/collectors/hf_papers_collector.py
python3 src/collectors/rss_collector.py
python3 src/collectors/reddit_collector.py
python3 src/collectors/hackernews_collector.py
python3 src/collectors/github_trending_collector.py
```

---

## 各采集器详细说明

### 1. arXiv (`arxiv_collector.py`)
- **接入**: 官方 `arxiv` Python 包
- **覆盖**: cs.AI, cs.LG, cs.CL, cs.CV, cs.MA
- **产出**: 标题、摘要、作者、分类、PDF链接
- **频率**: 每次拉最新 20 篇/分类 = 100 篇
- **合规**: 白色，官方 API，建议 3 秒间隔

### 2. HuggingFace Daily Papers (`hf_papers_collector.py`)
- **接入**: `GET https://huggingface.co/api/daily_papers?date=YYYY-MM-DD`
- **产出**: 标题、摘要、upvotes、评论数、GitHub repo/stars、提交者
- **价值**: **信号最密集的单一源** — upvotes 直接反映研究社区认可度
- **频率**: 拉最近 3 天
- **合规**: 白色

### 3. RSS 聚合 (`rss_collector.py`)
- **覆盖源**:
  - 量子位: `qbitai.com/feed` （中文AI媒体）
  - Leiphone: `leiphone.com/feed` （中文AI媒体）
  - MarkTechPost: `marktechpost.com/feed/` （英文，偏论文速报）
  - VentureBeat: `venturebeat.com/feed/` （英文，偏产业）
- **产出**: 标题、链接、发布时间、摘要
- **合规**: 白色

### 4. Reddit (`reddit_collector.py`)
- **接入**: 公开 `.json` 端点（无需 OAuth）
- **覆盖**: r/MachineLearning, r/LocalLLaMA, r/singularity
- **产出**: 标题、score、upvote_ratio、评论数、flair、selftext
- **合规**: 白色，需 User-Agent，100 req/min 限流

### 5. Hacker News (`hackernews_collector.py`)
- **接入**: Firebase API `hacker-news.firebaseio.com/v0/topstories.json`
- **过滤**: AI 关键词 + score≥50
- **产出**: 标题、URL、score、评论数
- **合规**: 白色，无鉴权

### 6. GitHub Trending (`github_trending_collector.py`)
- **接入**: HTML 解析 `github.com/trending`
- **过滤**: 描述/名称含 AI 关键词
- **产出**: repo 路径、描述、今日 star 数
- **合规**: 白色

### 7. 机器之心 (`jiqizhixin_collector.py`)
- **状态**: ❌ 不可用
- **原因**: 全站重定向到付费"数据服务"页，反爬彻底
- **替代**: WeRSS（~100元/年）或新榜（数千元/年）

---

## 核心算法说明

### 学术相关性过滤

用两个词表做布尔过滤:
- **保留词表** (ACADEMIC_KEYWORDS): attention, transformer, diffusion, multimodal, 多模态, 大模型, 推理... 等 ~50 个中英文学术术语
- **排除词表** (COMMERCIAL_NOISE): 招聘, 融资, 市场, advertising, hiring... 等商业噪声词

规则: 含排除词 → 直接丢弃；含保留词 → 保留；来自 arXiv/HF → 默认保留

### 跨语言匹配

中文标题和英文标题无法直接做词重叠匹配。但中文AI媒体报道通常会保留英文专有名词（如 "Anthropic", "DeepSeek", "MoE"）。

方法: 从两个标题中提取大写开头词 + 已知技术术语列表，看重叠数 ≥ 2 则认为讨论同一话题。

### 打分权重

设计原则: **学术社区直接认可 > 跨源验证 > 中文传播 > 工程热度**

```
HF upvotes ≥80     → +5.0
HF upvotes ≥50     → +4.0
HF upvotes ≥30     → +3.0
HF upvotes ≥15     → +2.0
每个跨源命中        → +1.5
中文媒体报道        → +1.5
英文媒体报道        → +1.0
Reddit score≥300   → +2.0
有 arXiv paper     → +1.0
GitHub stars≥100   → +1.0
```

---

## 待改进 / 待接入

| 项目 | 状态 | 备注 |
|------|------|------|
| LLM 深度筛选 | 待接入 | 等 API 渠道，用模型判断"是否适合做 A+B 迁移" |
| Twitter/X | 待决定 | 官方 Basic $200/月，或 twscrape 灰色方案 |
| 微信公众号 | 待决定 | WeRSS ~100元/年 或新榜 |
| 知乎/微博 | 待决定 | MediaCrawler + Cookie 池 |
| 小红书 | 暂不实现 | 反爬最严，合规风险高 |
| Semantic Scholar 引用意图 | 待实现 | 判断 Cites Methods vs Cites Background |
| 定时任务 | 待配置 | cron 每日自动运行 + 自动更新 GitHub Pages |
| B 方向库 | 待人工构建 | 各子领域的公认本质问题清单 |

---

## 可视化

GitHub Pages: https://qishisuren123.github.io/autoresearch-dashboard/

每次运行 pipeline 后手动更新:
```bash
python3 generate_dashboard.py  # 或内联脚本
git add index.html && git commit -m "Daily update" && git push origin gh-pages
```
