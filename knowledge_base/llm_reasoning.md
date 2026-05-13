# LLM 推理与测试时计算

**本质问题：** O1/R1 式长思维链推理效果好但成本高。如何在有限推理预算下最大化能力？

---

## 一、社区共识

### ✅ 认同的
1. **测试时计算（test-time compute）是 scaling 的下一个维度**
2. **RL + 可验证奖励（RLVR）是训练推理模型的主流范式**（DeepSeek-R1 验证）
3. **思维链长度不是越长越好**，存在最优 budget
4. **不同任务需要不同推理深度**（数学 > 代码 > 常识 QA）

### ⚠️ 路线之争

#### PRM（过程奖励）vs ORM（结果奖励）
- PRM：对每一步打分，理论好但难训练
- ORM + RLVR：只看最终答案对错，工程简单
- **社区目前倾向 ORM + RL**（DeepSeek-R1 证明可行）

#### 思维链显式 vs 隐式
- 显式：token 级的推理过程（O1、R1）
- 隐式：潜空间推理（Coconut、Quiet-STaR）
- **当前显式占主流**，但隐式被认为是下一波突破

---

## 二、常见错误直觉

### ❌ 避坑

1. **"让模型思考更多步就会更对"**
   - 真相：超过某长度会劣化。存在最优 budget。

2. **"PRM 一定比 ORM 好"**
   - 真相：PRM 标注成本高且往往有偏，RLVR + ORM 更鲁棒

3. **"思维链是模型真的在推理"**
   - 真相：存在大量研究表明思维链可能是 post-hoc rationalization，不一定反映真实的推理过程

4. **"自我批评/self-refine 一定有用"**
   - 真相：强模型自我批评有用，弱模型反而越改越错

---

## 三、真正值得做的方向

### ✅ 有前景

1. **Budget-Forcing / Dynamic Budget**
   - 让模型自适应决定思考多久
   - 代表：s1 (Stanford)、STILL-2

2. **Retrieval-Augmented Reasoning**
   - 推理过程中检索外部知识
   - 代表：Search-R1、ReAct

3. **Process Supervision 的低成本化**
   - 用模型自动标注过程奖励
   - 代表：Math-Shepherd、Eurus-PRM

4. **多轨迹搜索 + 自选择**
   - 生成多条思维链，让模型自己选
   - 代表：MCTS + LLM、Best-of-N + Verifier

5. **推理能力的跨模态迁移**
   - LLM 的推理能力能否迁移到 MLLM？
   - 代表：LLaVA-CoT、Mulberry
   - **热点方向**

---

## 四、数据集和基线

**数据集（2025-2026 主流）：**
- MATH-500、AIME 2024/2025、Olympiad Bench
- LiveCodeBench-v6（2025 滚动更新）、SWE-Bench-Verified
- ARC-AGI-2（2025）、FrontierMath、HumanEval-V
- ⚠️ 仅用 GSM8K / 老 GPQA 作为主指标会被审稿人质疑"已被刷爆"

**基线（2025-2026 主流推理模型，禁止用 Llama-2/3、Vicuna、GPT-3.5 作主基线）：**
- DeepSeek-R1（2025 旗舰）/ DeepSeek-V3.1
- Qwen3-32B（2025）、QwQ-32B
- Llama-4-Scout / Maverick（2025）
- o3-mini-style 推理模型作为闭源参考

**评估指标：**
- Pass@1
- 平均思维链长度（token count）
- Accuracy vs Budget 曲线
