# 多模态大模型的模态融合

**本质问题：** 当前 MLLM 把视觉 token 和文本 token 简单拼接后交给 LLM 自己去 attention，这种浅层对齐导致：细粒度视觉推理差、幻觉、空间理解弱。

---

## 一、社区真实共识

### ✅ 大家都认同的
1. **当前方案（LLaVA 的 linear projection）是"对齐不足"**
2. **视觉-文本的对齐应该是多层次的**（低层视觉-低层语言，高层视觉-高层语言）
3. **视觉 encoder 本身的限制**：CLIP 训练目标是图文对比学习，对细粒度理解天然弱

### ⚠️ 路线之争

#### 路线 A：Cross-Attention（传统）
- 代表：Flamingo、IDEFICS
- 特点：单独的 cross-attention 层做融合
- 优点：模态隔离清晰
- 缺点：训练复杂，不如 decoder-only 自然

#### 路线 B：Token 拼接（当前主流）
- 代表：LLaVA、Qwen-VL、InternVL
- 特点：视觉 token 直接拼入 LLM 上下文
- 优点：简单、兼容纯文本 LLM
- 缺点：浅层对齐

#### 路线 C：Early Fusion（萌芽）
- 代表：Chameleon、Janus
- 特点：从预训练阶段就混合模态
- 优点：深度对齐
- 缺点：贵，要从头训

**社区当前倾向**：路线 B 占 80%，但认为它的天花板快到了，需要 B→C 的演进。

---

## 二、常见错误直觉（避坑）

### ❌ 看似合理但其实不行的

1. **"给 MLLM 加一个额外的视觉 attention 层"**
   - 问题：会破坏 LLM 的预训练权重，且训练极不稳定
   - 实际效果：大概率掉点

2. **"让文本 token 主动 query 视觉 token"**
   - 问题：标准 decoder attention 本来就是 causal，后面的 token 会 attend 到前面的视觉 token，等于是已经在做 query 了
   - 实际效果：加了等于没加

3. **"用图像生成损失作为辅助任务"**
   - 问题：生成损失和理解损失冲突，会拉低理解性能
   - 实际效果：Chameleon 论文已经证明这个路线很难调

4. **"想办法让视觉 token 和文本 token 更相似"**
   - 问题：刻意让分布相似会破坏模态的区分度，反而损害性能
   - 实际效果：已有多篇论文验证失败

---

## 三、真正有价值的切入点

### ✅ 社区认为有前景的方向

1. **Mixture of Vision Encoders**
   - 不同 encoder 对应不同视觉能力（DINO 偏 local，CLIP 偏 semantic，SAM 偏 segmentation）
   - 代表：Cambrian-1、MoVA
   - 可做：轻量级融合机制

2. **Native Resolution + Dynamic Tiling**
   - 支持任意分辨率，切 tile 后各自 encode
   - 代表：NaViT、InternVL2 dynamic tiling
   - 可做：更优的 tile 策略 / tile 间的 token 关系建模

3. **显式的 Grounding 机制**
   - 让模型在生成每个词时显式指向视觉区域
   - 代表：KOSMOS-2、Ferret、GLaMM
   - 可做：将 grounding 和理解统一

4. **Video 时序建模**
   - 视频有额外的时间维度，融合更难
   - 代表：VideoLLaVA、LLaVA-OneVision
   - 可做：更好的时序 token 组织

5. **Text-Aware Visual Encoding**
   - 先看问题再看图（而不是先把图全部编码）
   - 代表：ATP-LLaVA、MQT-LLaVA
   - 可做：端到端的 query-conditional encoding

---

## 四、关键数据集和基线

**数据集：**
- MMBench / MMBench-CN（综合）
- MMMU（大学级知识）
- MathVista（视觉推理）
- RealWorldQA（真实场景）
- HallusionBench（幻觉）
- POPE（物体幻觉）
- BLINK（视觉感知基础能力）

**基线（2025-2026 主流，必须使用最新模型）：**
- Qwen2.5-VL-7B / 72B（2025 年最强开源 VL 之一）
- InternVL3-8B / 78B（2025）
- LLaVA-OneVision-7B（2024 末→2025 主流）
- Cambrian-1-8B / NVILA-8B / Molmo-7B（2024-2025）
- ⚠️ LLaVA-1.5/1.6、Qwen2-VL、InternVL2 仅作为"过时对比基线"出现，不能作为主基线，否则 ICLR/NeurIPS 2026 会被秒拒。

**Benchmark（必须包含 2025+ 新基准）：**
- MMMU-Pro（2025 升级版）、MEGA-Bench（2025）、MMBench-V2、HallusionBench、BLINK
- 仅用 GQA / VQAv2 / 老 MMBench 会被审稿人质疑"为什么不在新 benchmark 上验证"

---

## 五、值得深入的开放问题

1. 视觉 encoder 的瓶颈到底在哪里？
2. 如何统一 2D 图像和 1D 文本的位置编码？
3. 多图/视频场景下的 token 组织？
4. 如何让 MLLM 从图像中学会新概念（in-context learning for vision）？
5. Reasoning 能力为什么不能完全从 LLM 迁移到 MLLM？
