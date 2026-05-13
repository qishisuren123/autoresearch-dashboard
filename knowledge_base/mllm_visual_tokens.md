# 视觉 Token 管理（MLLM）

**本质问题：** 一张图经 ViT 编码后产生 300-700 个视觉 token，但文本任务真正需要的可能只有几十个。如何管理这些 token 是 MLLM 的核心工程痛点。

---

## 一、社区真实共识（重要！）

### ✅ 大家都认同的
1. **视觉 token 过多**：推理时视觉 token 占用 50%+ 的 KV cache，是推理成本主因
2. **不同层对视觉 token 的需求不同**：浅层需要保留更多细节，深层只需要语义抽象
3. **视觉 token 的重要性是 query-dependent 的**：同一张图，不同问题关心的区域完全不同

### ⚠️ 有争议的
1. **"遗忘"这个概念**：
   - **支持方**：视觉 token 太多了，应该像人脑一样主动遗忘无关信息
   - **反对方（主流）**：AI 的优势就是能记住更多，随便遗忘就是在开倒车。我们要做的是**在合适的时机减少 token 数量**，而不是随时间衰减
   - **真实可行的做法**：**浅层保留全量视觉 token，深层逐步减少**（token merging/pruning）—— 这是目前主流研究方向
2. **是 prune 还是 merge**：
   - prune：直接扔掉（信息损失大，不可逆）
   - merge：相似 token 合并（保留信息，可能增加计算）
   - 社区结论：**merge 为主，少量 prune**

---

## 二、公认的错误直觉（避免踩坑）

### ❌ 常见但错误的想法

1. **"按时间衰减视觉 token"**
   - 错因：视觉 token 没有时间维度，只有**层深度**和**query 相关性**两个维度
   - 正确方向：层深驱动 + query 驱动

2. **"视觉 token 之间自主竞争（注意力 top-k）"**
   - 错因：ViT 输出的 token 没有竞争关系，强行 top-k 会丢失空间结构
   - 正确方向：基于**空间一致性** + **语义相关性**的 merge

3. **"把视觉 token 压到 1 个全局 token"**
   - 错因：Q-Former 路线已经被主流抛弃，信息瓶颈太严重
   - 正确方向：保留一定数量（64-256 个）的精选 token

4. **"用 RL 训练视觉 token 选择器"**
   - 错因：RL 开销大，不稳定，目前没有成功案例
   - 正确方向：可微分的 soft masking 或 top-k with straight-through estimator

---

## 三、当前最火的子方向（2025 年）

1. **Token Merging (ToMe)**：相邻相似 token 合并
   - 代表：ToMe (原始)、TurboVLM、VisionZip
2. **Token Pruning 基于 attention 分数**：
   - 代表：FastV、SparseVLM
3. **层间动态 token 数量**：
   - 浅层 576 → 中层 144 → 深层 36
   - 代表：LLaVA-PruMerge, DynamicVLM
4. **Query-aware token selection**：
   - 根据文本 query 动态选择相关视觉区域
   - 代表：MQT-LLaVA, ATP-LLaVA

---

## 四、可行的创新切入点

### 有价值的方向
1. **层间渐进式 token 减少**：从浅到深按某个函数减少（线性？指数？幂律？）
2. **Query-aware + 层深双因素**：同时考虑问题相关性和层深度
3. **保留空间结构的 merge**：不打散 patch 的空间连续性
4. **多轮对话中的 token 复用**：下一轮问题到来时，复用前一轮的 token 筛选结果

### 容易扑街的方向
1. 简单地套用"生物遗忘曲线"—— 前面说了，视觉 token 没有时间
2. 单纯靠 attention 分数 top-k —— 会破坏空间结构
3. 一刀切的 token 数量 —— 不同问题难度不同，需要动态

---

## 五、关键数据集和基线

**数据集：**
- MMBench（综合理解）
- GQA（空间推理）
- POPE（幻觉检测，看看压缩后幻觉是否增加）
- TextVQA（细粒度 OCR）
- MME-RealWorld（实际效率）

**基线（2025-2026 主流，禁止用 LLaVA-1.5/1.6 作主基线）：**
- Qwen2.5-VL-7B / InternVL3-8B / LLaVA-OneVision-7B（全量 token）
- FastV / VisionZip / PyramidDrop（pruning baselines，2024-2025）
- SparseVLM / TokenPacker / LLaVA-Mini（2025 新方法）
- ⚠️ 评测必须额外报告 OCRBench / DocVQA / ChartQA / MMMU-Pro 等 2025 主流 benchmark

**评估指标：**
- 准确率 vs token 数量曲线
- 推理速度（tokens/s）
- KV cache 占用

---

## 六、值得读的核心论文

1. FastV (ECCV 2024)
2. VisionZip (2024)
3. Token Merging (原始, ICLR 2023)
4. ATP-LLaVA (2024)
5. LLaVA-PruMerge (ECCV 2024)
