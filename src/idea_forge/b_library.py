"""
B 方向库 - 各子领域的公认本质问题
这是 idea 质量的根基：B 的问题越具体、越深入，A+B 的 idea 质量才能高

每个 B 方向包含:
- 领域名
- 本质问题（1-2 句话，必须是公认痛点）
- 为什么是本质问题（为什么重要、为什么难、为什么现在的方法不够好）
- 近期代表性工作（给模型上下文）
- 可用的公开数据集和基线

后续由人工维护和更新，AI 不自动修改此文件。
"""

B_LIBRARY = [
    {
        "id": "mllm_fusion",
        "domain": "多模态大模型 (MLLM)",
        "problem": "视觉信息与文本信息的深层融合机制",
        "why_essential": """
当前主流方案（如 LLaVA 的 linear projection、Qwen-VL 的 cross-attention）本质上都是浅层对齐——
把视觉 token 映射到文本空间后拼接，模型并不能真正理解两种模态之间的结构对应关系。
这导致：细粒度视觉推理差（如空间关系、计数）、长图文交错理解差、幻觉严重。
真正的融合应该让模型理解"图片中的什么对应文本中的什么"，而不是把所有 token 扔到一起让 attention 自己猜。
""",
        "recent_works": [
            "LLaVA-OneVision (2024): 统一图/视频/多图，但融合仍是 concat",
            "InternVL2 (2024): 动态分辨率 + 更强 ViT，融合机制未本质改变",
            "Cambrian-1 (2024): 多视觉编码器融合，但仍是 token 级拼接",
        ],
        "datasets": ["MMBench", "MMMU", "MathVista", "RealWorldQA", "HallusionBench"],
        "baselines": ["LLaVA-1.6-7B", "InternVL2-8B", "Qwen-VL-7B"],
    },
    {
        "id": "mllm_position",
        "domain": "多模态大模型 (MLLM)",
        "problem": "视觉 token 和文本 token 的位置编码统一问题",
        "why_essential": """
文本是一维序列（有明确的左右顺序），图片是二维网格（有空间位置），视频还多了时间维度。
当前做法是把图像 patch 展平后用 1D 位置编码（RoPE 等），这丢失了 2D 空间信息。
这直接导致模型在空间推理、位置理解、多图排列等任务上表现差。
如何设计一个统一的位置编码方案，让模型同时理解文本的顺序和图像的空间结构，是一个核心开放问题。
""",
        "recent_works": [
            "RoPE 系列: 1D 旋转位置编码，对文本有效但图像不自然",
            "2D-RoPE / SigLIP: 尝试用 2D 位置但和文本 RoPE 不兼容",
            "NaViT (2023): 使用 factorized position encoding",
        ],
        "datasets": ["VSR (Visual Spatial Reasoning)", "What'sUp (spatial relations)", "GQA"],
        "baselines": ["LLaVA with standard RoPE", "InternVL2"],
    },
    {
        "id": "mllm_hallucination",
        "domain": "多模态大模型 (MLLM)",
        "problem": "多模态幻觉——模型生成与图片内容不符的描述",
        "why_essential": """
MLLM 的幻觉比纯文本 LLM 更严重且更难检测——模型可能"描述"了一个图中根本不存在的物体。
根本原因: 语言先验太强，视觉 grounding 不够，模型倾向于生成"合理但不忠实"的描述。
这是 MLLM 实际部署的最大障碍，也是近两年顶会论文产出最多的方向之一。
""",
        "recent_works": [
            "RLHF-V (2024): 用人类反馈减少幻觉",
            "LLaVA-RLHF: RL 对齐减少幻觉",
            "OPERA (2024): attention 模式分析解决幻觉",
        ],
        "datasets": ["POPE", "HallusionBench", "MMHal-Bench", "AMBER"],
        "baselines": ["LLaVA-1.6", "InternVL2", "Qwen-VL"],
    },
    {
        "id": "efficient_reasoning",
        "domain": "高效推理 / 测试时计算",
        "problem": "如何在有限推理预算下最大化 LLM 的推理能力",
        "why_essential": """
O1/O3 式的长思维链推理效果好但成本极高（token 消耗 10-100x）。
核心矛盾: 更多 test-time compute = 更好的推理结果，但实际部署有延迟和成本约束。
如何用更少的 token / 更短的链 / 更聪明的策略达到同样的推理质量，是当前最火的方向。
""",
        "recent_works": [
            "DeepSeek-R1 (2025): 通过 RL 训练思维链",
            "s1 (2025): test-time scaling 的 budget forcing",
            "STILL-2 (2025): 自适应推理长度",
        ],
        "datasets": ["MATH-500", "GSM8K", "AIME 2024", "LiveCodeBench"],
        "baselines": ["DeepSeek-R1-7B", "Qwen2.5-Math-7B", "Llama-3.1-8B-Instruct"],
    },
    {
        "id": "world_model",
        "domain": "世界模型 / 物理理解",
        "problem": "如何让模型理解物理世界的因果规律而非仅学表面统计相关",
        "why_essential": """
当前视频生成/预测模型（如 Sora）能生成逼真画面但不理解物理——球可以穿墙、水可以逆流。
LeCun 提出的 JEPA 路线认为世界模型应该在潜空间预测，而非像素空间。
核心问题: 如何用有限数据训练出能做物理推理（而非仅做视觉模式匹配）的模型？
""",
        "recent_works": [
            "V-JEPA (Meta, 2024): 视频潜空间预测",
            "Genie 2 (DeepMind, 2024): 可交互的世界模型",
            "LWM (2024): 大世界模型，统一视频+文本",
        ],
        "datasets": ["PhysBench", "Physion", "IntPhys", "CLEVRER"],
        "baselines": ["Video-LLaVA", "LWM-base"],
    },
    {
        "id": "agent_memory",
        "domain": "LLM Agent",
        "problem": "Agent 的长期记忆管理——如何记住重要信息、遗忘无关信息",
        "why_essential": """
当前 Agent 要么用全量上下文（context 爆炸），要么用 RAG 检索（但不知道什么该存什么该忘）。
人类记忆有主动遗忘、主动巩固的机制，当前 Agent 完全没有。
这导致: 长任务中 Agent 越来越慢/贵，旧信息干扰新决策，无法积累跨任务经验。
""",
        "recent_works": [
            "MemGPT (2023): 分层记忆管理",
            "Cognitive Architectures for LLM Agents (2024): 认知科学启发",
            "RecurrentGPT: 用 LSTM-like 机制管理长文本",
        ],
        "datasets": ["LongBench", "RULER", "InfiniteBench"],
        "baselines": ["基础 RAG", "MemGPT", "Full-context baseline"],
    },
]


def get_b_library():
    return B_LIBRARY


def get_b_by_id(b_id):
    for b in B_LIBRARY:
        if b["id"] == b_id:
            return b
    return None


def format_b_context(b):
    """格式化 B 方向的完整上下文，用于喂给 LLM"""
    return f"""
领域: {b['domain']}
本质问题: {b['problem']}

为什么这是本质问题:
{b['why_essential'].strip()}

近期代表性工作:
{chr(10).join('- ' + w for w in b['recent_works'])}

可用数据集: {', '.join(b['datasets'])}
基线方法: {', '.join(b['baselines'])}
"""
