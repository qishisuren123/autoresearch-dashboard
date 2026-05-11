# LLM Agent 长期记忆

**本质问题：** Agent 在长任务中要么上下文爆炸，要么用 RAG 但不知道什么该存什么该忘。

---

## 一、社区共识

### ✅ 认同的
1. **全量上下文不可持续**（token 成本 + attention 稀释）
2. **纯 RAG 不够**（检索质量依赖 embedding，且不支持推理式访问）
3. **需要分层记忆**（short-term working memory + long-term episodic memory + semantic knowledge）

### ⚠️ 争议点

#### 要不要"遗忘"？
- **反对遗忘派（主流）**：AI 的优势就是能记住一切，遗忘是在开倒车
- **支持遗忘派**：无关信息会干扰决策，主动剪枝反而更强
- **实用中庸派**：**不是遗忘，而是分层存储** —— 重要的放主存，次要的放冷存储（可以检索但不占上下文）

---

## 二、常见错误直觉

### ❌ 避坑

1. **"直接套用艾宾浩斯遗忘曲线"**
   - 错因：生物遗忘是因为大脑容量有限，AI 存储几乎无限，强行遗忘只会丢失信息
   - 正确做法：**分层存储 + 按需调用**

2. **"记忆就是 RAG，检索就完事了"**
   - 错因：RAG 只能做 "这个信息和当前最相关"，但 Agent 需要的是"这个信息对当前任务有用"
   - 正确做法：**任务条件下的检索 + 重要性判断**

3. **"全部存进向量数据库就是记忆"**
   - 错因：向量只能做语义相似，不支持关系、时间、因果
   - 正确做法：**图 + 向量 + 符号混合**

4. **"Memory 一定要训练才能用"**
   - 错因：MemGPT 证明纯 prompting 就能做得不错
   - 正确做法：先做 training-free，有效后再考虑训练

---

## 三、值得做的方向

### ✅ 有前景

1. **Working Memory 的动态压缩**
   - 当前任务相关的上下文用更紧凑的形式存储
   - 代表：LongMem, RecurrentGPT

2. **Episodic Memory 的组织**
   - 按时间/任务/主题组织经验
   - 代表：A-Mem, Zep

3. **跨任务经验迁移**
   - 之前任务学到的技能如何复用
   - 代表：Skill Library (Voyager), ExpeL

4. **自我反思 + 记忆更新**
   - Agent 完成任务后主动更新自己的知识库
   - 代表：Reflexion, SELF

5. **多 Agent 共享记忆**
   - 多个 Agent 协作时的记忆同步
   - 代表：AutoGen 的 shared memory

---

## 四、数据集和基线

**数据集：**
- LongBench (长上下文)
- RULER (NIAH 扩展)
- InfiniteBench
- MemoryBank
- LoCoMo (长对话)

**基线：**
- MemGPT
- 基础 RAG (FAISS + GPT-3.5)
- Full-context baseline
- A-Mem

**评估：**
- 任务完成率
- 记忆检索准确率
- Token 成本
- 长期一致性（几千轮对话后还记得开头）
