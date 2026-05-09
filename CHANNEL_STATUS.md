# 渠道接入状态汇报

> 最后更新: 2026-05-09  
> 每个渠道经过实际测试，记录真实情况。

---

## 渠道状态总览

| 渠道 | 状态 | 今日采集量 | 接入方式 | 合规等级 |
|------|------|-----------|---------|---------|
| **arXiv** | ✅ 正常 | 50 篇 | 官方 `arxiv` Python 包 | 白色 |
| **HuggingFace Daily Papers** | ✅ 正常 | 58 篇 | 官方 JSON API | 白色 |
| **量子位 (QbitAI)** | ✅ 正常 | 10 篇 | RSS `qbitai.com/feed` | 白色 |
| **AI 科技评论 (Leiphone)** | ✅ 正常 | 20 篇 | RSS `leiphone.com/feed` | 白色 |
| **MarkTechPost** | ✅ 正常 | 10 篇 | RSS `marktechpost.com/feed/` | 白色 |
| **VentureBeat** | ✅ 正常 | 7 篇 | RSS `venturebeat.com/feed/` | 白色 |
| **Hacker News** | ✅ 正常 | 1 条(AI) | Firebase API（无鉴权） | 白色 |
| **Reddit** | ✅ 正常 | 75 帖 | 公开 `.json` 端点 + User-Agent | 白色 |
| **GitHub Trending** | ✅ 正常 | 9 个(AI) | HTML 解析 | 白色 |
| **机器之心** | ❌ 不可用 | 0 | 全站跳转付费"数据服务" | 需付费 |

---

## 详细记录

### ✅ 已通过测试、可直接生产使用

#### 1. arXiv（学术源）
- **接入方式**: `pip install arxiv`，官方 API
- **覆盖分类**: cs.AI, cs.LG, cs.CL, cs.CV, cs.MA
- **速率限制**: 建议 3 秒间隔
- **数据质量**: 高，含标题/摘要/作者/分类/PDF链接
- **代码**: `src/collectors/arxiv_collector.py`

#### 2. HuggingFace Daily Papers（学术源 + 社区信号）
- **接入方式**: `GET https://huggingface.co/api/daily_papers?date=YYYY-MM-DD`
- **数据质量**: 极高，含 upvotes、评论数、AI摘要、GitHub链接、stars
- **信号价值**: 这是 **信号最密集的单一源** — upvotes 直接反映社区认可度
- **代码**: `src/collectors/hf_papers_collector.py`

#### 3. 量子位 QbitAI（中文 AI 媒体）
- **接入方式**: RSS `https://www.qbitai.com/feed`
- **更新频率**: 日更 5-15 篇
- **特点**: 中文AI媒体中 RSS 最稳定的一个
- **代码**: `src/collectors/rss_collector.py`

#### 4. AI 科技评论 / Leiphone（中文 AI 媒体）
- **接入方式**: RSS `https://www.leiphone.com/feed`
- **更新频率**: 日更 10-20 篇
- **特点**: 覆盖 AI + 硬件 + 产业
- **代码**: `src/collectors/rss_collector.py`

#### 5. MarkTechPost（英文 AI 媒体）
- **接入方式**: RSS `https://www.marktechpost.com/feed/`
- **更新频率**: 日更 5-10 篇
- **特点**: 偏学术论文速报，对前沿工作覆盖好
- **代码**: `src/collectors/rss_collector.py`

#### 6. VentureBeat（英文科技媒体）
- **接入方式**: RSS `https://venturebeat.com/feed/`
- **更新频率**: 日更 5-10 篇
- **特点**: 偏产业/商业 AI 应用
- **代码**: `src/collectors/rss_collector.py`

#### 7. Hacker News（英文技术社区）
- **接入方式**: Firebase API `https://hacker-news.firebaseio.com/v0/topstories.json`
- **特点**: 无鉴权、无限流、响应快。按 AI 关键词 + 最低分数过滤
- **限制**: AI 热帖数量随当天而变，有时少
- **代码**: `src/collectors/hackernews_collector.py`

#### 8. Reddit（英文社区舆情）
- **接入方式**: 公开 `.json` 端点（不需要 OAuth）
- **覆盖**: r/MachineLearning, r/LocalLLaMA, r/singularity
- **信号**: score, upvote_ratio, num_comments, flair
- **限制**: 100 req/min（User-Agent 必须填）
- **双重用途**: 既是关 1 信号源，也是关 2 舆情验证源
- **代码**: `src/collectors/reddit_collector.py`, `src/analyzers/sentiment_analyzer.py`

#### 9. GitHub Trending（工程源）
- **接入方式**: HTML 解析 `github.com/trending`
- **过滤**: 按 AI 关键词匹配描述和 repo 名
- **信号**: 每日新增 stars 数
- **代码**: `src/collectors/github_trending_collector.py`

---

### ❌ 测试失败、不可用

#### 机器之心 (jiqizhixin.com)
- **测试时间**: 2026-05-09
- **失败原因**: 站点所有公开 URL（/articles, /daily, /feed, /rss, 首页）全部返回一个"机器之心·数据服务"的推广落地页，不提供任何文章内容
- **技术细节**: HTTP 200 但返回固定的 3251 字节 HTML，是一个营销页面
- **替代方案**:
  - WeRSS（几十到一两百元/年，把公众号转 RSS）
  - 新榜/清博大数据（年费数千到数万元）
  - 放弃，用量子位 + Leiphone 覆盖中文 AI 媒体

---

### 🟡 待实现（需要 API Key 或灰色方案）

#### Twitter/X
- **价值**: 高，意见领袖（AK, Karpathy, Jim Fan, Elon Musk）的即时反应
- **合规方案**: 官方 Basic API $200/月，10,000 tweets/月
- **灰色方案**: `twscrape` + 账号池（违反 ToS，账号易封）
- **状态**: 待决定是否掏 $200/月

#### 知乎
- **价值**: 中，中文长文技术讨论
- **方案**: MediaCrawler + Cookie 池
- **风险**: 反爬中等，需维护 Cookie
- **状态**: 待决定优先级

#### 微博
- **价值**: 中，中文即时反应 + KOL 转发
- **方案**: `dataabc/weibo-search` + Cookie
- **风险**: 浅灰，有一定限流
- **状态**: 待决定优先级

#### 小红书
- **价值**: 中高（能看到"通稿文案集群"和真实用户反馈的差异）
- **方案**: MediaCrawler（签名算法复杂，需账号池 + 代理）
- **风险**: 深灰，反爬最严，做好账号被封预期
- **状态**: 暂不实现

#### 新智元 / PaperWeekly / AI 前线（微信公众号源）
- **价值**: 高，中文 AI 深度报道
- **方案**: 只能通过商业服务（WeRSS/新榜）获取
- **原因**: 微信公众号生态完全封闭，无公开 API，搜狗微信已废，自建 mitmproxy 违反 ToS
- **状态**: 待决定是否付费

#### Semantic Scholar Recommendations API
- **价值**: 高，引用意图分类（Cites Methods vs Cites Background）
- **方案**: 官方 API，部分端点需 API Key
- **状态**: 基础搜索可用，Recommendations 端点待测

---

## 系统跑通验证

### 关 1 测试结果（2026-05-09）
- 总采集: **230 条**候选
- 共识分析后: **13 个**候选话题
- 最高分候选: "Continuous Latent Diffusion Language Model"（跨 engineering + academic 两类源）

### 关 2 测试结果（2026-05-09）
- 对 Top-5 候选做 Reddit 舆情验证
- 4/5 判定为 "✅ 真火"（genuine_hot）
- 1/5 判定为 "🟡 大概率真"（likely_genuine）
- 关 2 能有效区分"真实社区讨论"和"无讨论/冷淡"

---

## 下一步

1. **立刻可做**: 把此系统设为定时任务（cron），每日自动运行
2. **短期**: 决定是否付费接入 Twitter/X（$200/月）和公众号（WeRSS ~100元/年）
3. **中期**: 接入 Semantic Scholar 引用意图 API，强化学术源信号
4. **长期**: 根据需要接入知乎/微博/小红书灰色渠道
