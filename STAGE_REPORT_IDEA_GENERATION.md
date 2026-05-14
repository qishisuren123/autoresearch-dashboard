# AutoResearch · Idea 生成阶段 · 阶段性汇报

> **报告日期**：2026-05-14  
> **覆盖周期**：2026-05-09 → 2026-05-14（6 天）  
> **当前阶段**：Idea 生成框架已搭通，端到端跑通并稳定产出  
> **核心结论**：从原始信息 → 计划书共 **6 道关卡**全部贯通，6 天累计驱动 **8 个 A 种子**产出 **13 份顶会级别计划书**

---

## 一、当前管线总览（已稳定运行）

```
原始网络信息 (~518 条 / 6 天)
        │
        ▼
┌──────────────────────────────────────────┐
│ 模块一：大浪淘沙 (pipeline_v4 + 跨天去重)  │  保留 ~15 条不同候选
│   · Reddit / HN 真实讨论入口              │  6 强推荐 / 5 值得深入
│   · LLM Flash 粗筛 → Pro 深度研判         │  
│   · 跨天去重（去除月度热帖反复研判）       │  
└──────────────────────────────────────────┘
        │
        ▼ (强推荐 → A 种子)
┌──────────────────────────────────────────┐
│ 模块二：Idea Forge - A+B 锻造               │  61 候选 idea
│   Step 1  深度构思 (3 模型 × 4 B 方向)     │   ↓ 严格验证
│   Step 2  全员交叉评审 (D1-D4 四维度)      │  17 通过验证
│   Step 2.5 时新性刷新 (B 库 + arxiv 双渠道) │   ↓ 共识检查
│   Step 2.6 社区共识检查（避免撞 B 库常识）  │   ↓
│   Step 3  生成可执行计划书                  │  13 份计划书 ✅
└──────────────────────────────────────────┘
        │
        ▼
   index.html / ideas.html → GitHub Pages 自动 push
```

**运行模式**：cron 每日 01:00 自动跑全流程 + 01:30 补跑历史积压种子。

---

## 二、版本演进与试错记录（共 8 个主要里程碑）

### 阶段 A：信息聚合（Pipeline）— 4 个里程碑

#### 🔹 v1 · 基础采集 + 关 1/关 2 双关
- **思路**：白色合规渠道全量采集 + 共识筛选 + Reddit 舆情二次验证
- **覆盖**：arXiv / HF Daily Papers / 量子位 / Leiphone / MarkTechPost / VentureBeat / HN / Reddit / GitHub Trending（**9 个白色渠道**）
- **遇到的问题**：
  - HF upvotes 容易刷分，权重过高时大量"被刷出来的论文"占据榜单
  - 单源信号易被噪声淹没（机器之心反爬不通，灰色渠道合规风险高）
- **修正**：放弃机器之心，跨源命中加权，Reddit 评论数作为"真讨论"二次过滤

#### 🔹 v2 · 跨语言匹配 + 学术相关性过滤
- **思路**：中文 AI 媒体报道 ↔ 跨语言匹配到论文，提升中英对齐能力
- **遇到的问题**：
  - 中文标题与英文论文标题词重叠困难
  - 大量"产品发布会 / 融资 / 招聘"商业噪声混入
- **修正**：
  - 提取专有名词（Anthropic、DeepSeek、MoE 等）做桥梁
  - 引入 ACADEMIC_KEYWORDS（保留词表）+ COMMERCIAL_NOISE（排除词表）
  - 共 ~50 个学术术语 + 商业噪声词典

#### 🔹 v3 · 规则初筛 + LLM(Flash) 精筛 + Pro 综合研判
- **思路**：双层 LLM 筛选，Flash 廉价拦截 + Pro 深度判断
- **遇到的问题**：
  - 仍然"以论文库为出发点"，大量论文根本没有社区讨论 → 命中率低
  - HF Daily Papers 权重失衡，"刷分论文"挤掉真实热议工作
- **修正**：意识到必须**反转逻辑** → 进入 v4

#### 🔹 v4 · 核心逻辑反转：以社区讨论为入口 ⭐
- **新思路**：不再"从论文库出发看有没有人讨论"，而是"**从社区真实热议出发，再判断有没有 insight**"
- **入口信号**：
  - Reddit r/MachineLearning 近 1 个月 [Research] 高讨论帖
  - r/LocalLLaMA 技术向高讨论帖
  - HN 近 1 个月 AI 高评论帖（评论数 ≥ 30）
- **遇到的问题**：
  - 每天用 `time_filter="month"` 抓近 30 天热帖 → **同一篇帖子被反复研判**
  - 实测：Karpathy LLM wiki 这一篇被 Pro 模型研判了 **4 次**（5/11、5/12、5/13、5/14）
- **修正（今日上线）**：加跨天去重 `load_processed_keys()` —— 扫描所有历史 `verified/*` 提取 url + 归一化 title 作为黑名单，进入 LLM 之前直接剔除
- **效果**：6 天 518 条原始信息中，去重后真正研判 **15 条不同候选**，节省约 70% 的研判 token

---

### 阶段 B：Idea Forge（A+B 锻造）— 4 个里程碑

#### 🔸 forge v0 · 自由发挥版（5/9 19:12 – 19:22）
- **思路**：让模型自己想出 A+B 的组合
- **遇到的问题**：
  - 模型经常硬凑（如视觉 token 套"按时间衰减"，但视觉 token 没有时间维度）
  - 撞 B 领域社区常识（如对 Agent 记忆套"遗忘曲线"，社区不认同强行遗忘）
  - 19:12 那次跑出 **0 个 idea**，全员 NO_MATCH
- **修正**：意识到必须给模型喂"B 领域真实知识"

#### 🔸 forge v1 · B_LIBRARY + 知识 MD 注入（5/9 19:31 起）
- **思路**：建立结构化 **B 方向库**（4 个领域）+ 每个领域配 90-120 行的 `knowledge_base/*.md`（含社区共识、路线之争、常见误区、可行创新切入点）
- **配置**：3 模型独立构思（gemini-pro / gpt-5.5 / claude-sonnet），交叉验证由"另外 2 个模型"评审
- **遇到的问题**：
  - **Claude Sonnet 评审过于严苛**，主导否决率高
  - 实证：所有通过验证的 idea 都来自 claude-sonnet（因为 sonnet idea 不被 sonnet 本人评审，而其他模型的 idea 都要被 sonnet 评审一次）
  - 这是结构性偏差，不是巧合
- **修正**：升级到 forge v2

#### 🔸 forge v2 · 评审机制升级（5/13 下午）
- **改动 1**：`claude-sonnet` → `claude-opus`（最强 Claude）
- **改动 2**：交叉验证改为**全员评审**（包括生成者本人也评审自己），消除"生成者豁免"偏差
- **改动 3**：评审 prompt 拆为四维度 D1-D4：
  - D1 机制深度
  - D2 方法简洁
  - D3 实验充分
  - D4 时新性（最初为硬约束）
- **遇到的问题**：
  - **D4 时新性"一票否决"过于激进** —— 好的 idea 仅因为引用了 LLaVA-1.6 / Qwen2-VL（2024 老模型）就被全部击杀
  - 实证：5/13 18:28 跑出的 8 候选 idea，机制都不错但全部因 D4 不及格被毙掉

#### 🔸 forge v3 · 击杀 → 刷新（5/13 晚）⭐
- **新设计哲学**：**别击杀好计划**，而是把过时模型/数据/benchmark **就地升级**
- **新增 Step 2.5 时新性刷新模块** `freshness.py`：
  ```
  Step 2 验证   → 仅 D1/D2/D3 决定通过；D4 仅作软警告
  Step 2.5 刷新 → 用 B 库 + arxiv 实时搜索 → LLM 改写 idea
  Step 2.6 共识 → consensus_check 防撞 B 领域常识
  Step 3 计划书
  ```
- **双渠道时新性来源**：
  1. B 方向库（用户主动维护的权威最新基线）
  2. arxiv 实时搜索（兜底，覆盖 B 库未及时更新的情况）
- **效果**：5/13 22:28 重跑，**4 种子 → 10 idea → 6 验证通过 → 6 计划书**（验证通过率从 12.5% 提升到 60%）

---

### 基建层：API 与代理排查（穿插贯穿，3 个独立里程碑）

#### ⚙️ 基建-1 · API 通道排查
- **对比测试**：evomap.ai（付费）/ anyrouter.top（免费窗口）/ 35.220.164.252:3888（付费中转）
- **关键发现**：
  - anyrouter Claude **直接 HTTP API 有 bug**（panic / 误报 1m 错误），但通过 Claude Code CLI + `--betas context-1m-2025-08-07` 可正常调用
  - anyrouter GPT-5.5 **必须走 OpenAI Responses API**（`/v1/responses`，参数用 `input` 不是 `messages`），Chat Completions 端点返回 404
  - anyrouter Gemini 不支持，Gemini 全部走官方 API
- **修正**：编写 `call_linghuo_claude` 用 `subprocess.run` 启动 CLI；编写 `call_linghuo_gpt` 走 Responses API + 5 key 轮换

#### ⚙️ 基建-2 · 免费窗口路由
- **设计**：北京时间 00:00-08:00 自动走免费渠道，失败自动回落收费版本
- **实测发现（今日）**：anyrouter GPT-5.5 **24 小时全天可用**（4 秒响应），不只是免费窗口
- **优化**：`call_gpt` 改为**始终优先**走灵活渠道，失败才走收费 → GPT 调用近乎完全免费

#### ⚙️ 基建-3 · 代理稳定性兜底
- **背景**：服务器在受限网络环境，部分 API（Gemini / anyrouter）必须经 SSH 反向隧道代理
- **遇到的问题**：用户断开 SSH → 隧道死亡 → 整个 pipeline 崩溃
- **修正**：
  - 启动前 TCP 探测代理（`proxy_alive()`，结果缓存 20 秒）
  - 代理死了 → 自动降级到能直连的 evomap + 收费中转站
  - `trust_env=False` 强制不依赖环境变量，避免 cron 环境污染
- **效果**：SSH 断开后系统不崩溃，仅丢失 Gemini + 灵活渠道，Claude/GPT 收费版本仍可用

---

## 三、整体数据汇总（6 天）

| 指标 | 数值 | 备注 |
|---|---|---|
| 原始信息（含跨天重复） | 518 条 | reddit + HN |
| 去重后不同候选 | **15 条** | 经 Pro 研判 |
| 强推荐 A 种子 | **6 条** | 进入 Forge |
| 值得深入 | 5 条 | 备选池 |
| 不适合做 A 种子 | 2 条 | |
| Forge 候选 idea | **61 个** | 累计 |
| 通过严格验证 | **17 个** | 验证率 27.9% |
| 输出计划书 | **13 份** | ⭐ 最终成果 |
| 实际驱动 Forge 的种子 | 8 个 | 含早期"值得深入"也跑过 |

---

## 四、当前现状与优化方向

### 4.1 信息渠道

#### 现状
- **目前所有渠道均为免费白色渠道**：
  - 学术：arXiv 官方 API、HuggingFace Daily Papers
  - 社区：Reddit（r/MachineLearning、r/LocalLLaMA、r/singularity）、Hacker News Firebase API
  - 媒体：量子位、AI 科技评论（Leiphone）、MarkTechPost、VentureBeat（RSS）
  - 工程：GitHub Trending
  - 增强：Paper Digest（影响力排名）、Simon Willison / OpenAI Research / DeepMind / BAIR 等研究者博客
- **共 14 个渠道**，全部白色合规、零成本

#### 优化方向
- **付费高质量知识库（建议引入）**：
  - **Twitter/X 官方 Basic API**（$200/月）：意见领袖（Karpathy、Jim Fan、Elon Musk 等）的即时反应，比 Reddit 更前沿 1-2 天
  - **微信公众号 RSS（WeRSS ~100 元/年 或新榜数千元/年）**：覆盖新智元、PaperWeekly、AI 前线等中文深度报道源
  - **Semantic Scholar Recommendations API**：引用意图分类（Cites Methods vs Cites Background），过滤"被引用但实际没人用"的工作
- **可探索的灰色渠道**：
  - 知乎 / 微博：MediaCrawler + Cookie 池（中等反爬难度）
  - 小红书：反爬最严，账号易封，性价比低
- **高质量学术增量**：
  - OpenReview API（已写但未启用）：拿到 ICLR / NeurIPS 评审意见
  - bioRxiv / medRxiv：跨学科 AI 应用源

---

### 4.2 知识库建设（B 方向库 + 知识 MD）

#### 现状
- **当前覆盖 4 个领域**：
  | 领域 | 文件 | 规模 | 基线数 | 数据集数 |
  |---|---|---|---|---|
  | 多模态大模型 - 模态融合 | `mllm_fusion.md` | 121 行 | 6 | 6 |
  | 多模态大模型 - 视觉 Token 管理 | `mllm_visual_tokens.md` | 106 行 | 6 | 6 |
  | LLM 推理与测试时计算 | `llm_reasoning.md` | 91 行 | 6 | 6 |
  | LLM Agent 长期记忆 | `agent_memory.md` | 92 行 | 6 | 5 |
- **每份 MD 包含**：本质问题、社区共识、路线之争、常见误区、可行创新切入点、最新基线 / 数据集 / benchmark 列表
- **配套的 freshness.py 自动刷新**：每条 idea 生成后扫描过时项，从 B 库 + arxiv 双渠道获取最新版本就地替换

#### 优化方向
- **横向扩展（更多领域）**：
  - 扩散模型 / 流匹配（Flow Matching）
  - 强化学习与对齐（RLHF / DPO / SimPO 系）
  - 视频理解与生成（World Models）
  - 具身智能 / VLA（视觉-语言-行动模型）
  - AI for Science（蛋白质 / 材料 / 数学定理证明）
  - Agent 工具使用与规划（含 ReAct / Reflexion 类）
- **纵向加深（每个领域更专业）**：
  - 增加"近 6 个月顶会接收论文"动态切入点
  - 引入"反向案例库"：哪些方向已被刷爆 / 哪些方向被宣告失败
  - 标注"硬件友好度"：每个方向所需算力等级（让 idea 在 8×L20 约束下更可执行）
- **知识时效性自动维护**：
  - 当前 B 库 baseline / dataset 字段需手动维护
  - 可定期（每月）用 LLM 自动扫描最新 arxiv 论文，提示需要更新的字段
  - 或基于已有 idea 生成历史，反向回填 B 库（如某 idea 提到 Qwen3 但 B 库还没列入，自动补）

---

## 五、下一阶段规划

| 序号 | 工作项 | 优先级 | 预期产出 |
|---|---|---|---|
| 1 | 接入 Twitter/X Basic API | 🔴 高 | KOL 即时反应，提前 1-2 天发现热点 |
| 2 | 扩展 B 方向库到 8-10 个领域 | 🔴 高 | 每天能匹配的 A+B 组合增加 2 倍 |
| 3 | 引入 OpenReview 评审意图分析 | 🟡 中 | 区分"真热"vs"作者自吹"工作 |
| 4 | 知识库自动化更新流程 | 🟡 中 | 月度自动扫描 arxiv 补 B 库新基线 |
| 5 | 接入微信公众号渠道 | 🟢 低 | 中文 AI 深度报道补全 |
| 6 | Idea 后置追踪 | 🟢 低 | 跟踪生成的 idea 是否有同期发表的论文，验证我们 prompting 的"前瞻性" |

---

## 六、关键工程细节（彩蛋）

> 这一部分记录了一些非常细的工程坑，体现整个系统的鲁棒性建设深度。

- **Python 模块缓存陷阱**：发现多次 cron 跑用的还是旧版 `llm_client.py`（Python import 缓存），所有改动需通过 tmux 重启进程才能生效，已加入 SOP
- **subprocess 环境污染**：`call_linghuo_claude` 启动 Claude CLI 时必须显式传 `HTTPS_PROXY` 给 subprocess（Node fetch 自己会读环境变量）
- **httpx trust_env**：所有 LLM 调用统一 `trust_env=False`，避免 cron 环境的 `https_proxy` 把直连请求"莫名其妙地走代理"
- **stdout 缓冲**：`run_daily.sh` 用 `python3 -u` 强制无缓冲输出，否则 cron 日志看上去像"卡死"实际只是 stdout 还在 buffer
- **缺失依赖发现**：`feedparser`、`bs4` 在 cron 环境下抛 ImportError，已加入 requirements 列表
- **HN 标题模糊匹配**：HN 帖子标题会被站方或作者编辑，跨天去重必须做归一化（去 `Show HN:` 前缀、去标点、小写、保留前 60 字符）

---

## 七、一句话总结

> **在 6 天时间内，我们完成了一条从"网络原始信号"到"顶会级别可执行计划书"的端到端 AI 研究流水线，期间穿越了 8+ 个版本迭代、十余个工程暗坑、4 个核心算法重构，最终稳定产出 13 份计划书，并将边际成本通过路由优化降至接近零。**

---

*本报告自动维护于 `/data/renyiming/AutoResearch/STAGE_REPORT_IDEA_GENERATION.md`*  
*下一阶段（验证 + 实验执行框架）规划另行汇报*
