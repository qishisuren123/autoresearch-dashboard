"""
B 方向库 - 各子领域的公认本质问题
关键: 每个方向现在关联一个 knowledge_base/ 下的 .md 文件
这样 LLM 不只看到问题陈述，还能看到社区共识、路线之争、常见误区
"""

from pathlib import Path

KNOWLEDGE_BASE_DIR = Path(__file__).parent.parent.parent / "knowledge_base"


def load_knowledge(md_filename):
    """加载对应的知识 MD 文件"""
    path = KNOWLEDGE_BASE_DIR / md_filename
    if path.exists():
        return path.read_text(encoding="utf-8")
    return None


B_LIBRARY = [
    {
        "id": "mllm_fusion",
        "domain": "多模态大模型 - 模态融合",
        "problem": "视觉信息与文本信息的深层融合机制",
        "knowledge_md": "mllm_fusion.md",
        "datasets": ["MMBench", "MMMU", "MathVista", "HallusionBench"],
        "baselines": ["LLaVA-1.6-7B", "Qwen2-VL-7B", "InternVL2-8B"],
    },
    {
        "id": "mllm_visual_tokens",
        "domain": "多模态大模型 - 视觉 Token 管理",
        "problem": "视觉 token 的数量、层间动态、查询相关性",
        "knowledge_md": "mllm_visual_tokens.md",
        "datasets": ["MMBench", "GQA", "POPE", "TextVQA"],
        "baselines": ["LLaVA-1.6", "FastV", "VisionZip"],
    },
    {
        "id": "llm_reasoning",
        "domain": "LLM 推理与测试时计算",
        "problem": "如何在有限推理预算下最大化推理能力",
        "knowledge_md": "llm_reasoning.md",
        "datasets": ["MATH-500", "GSM8K", "AIME 2024", "LiveCodeBench"],
        "baselines": ["DeepSeek-R1-7B", "Qwen2.5-Math-7B"],
    },
    {
        "id": "agent_memory",
        "domain": "LLM Agent 长期记忆",
        "problem": "Agent 在长任务中的记忆管理",
        "knowledge_md": "agent_memory.md",
        "datasets": ["LongBench", "RULER", "LoCoMo"],
        "baselines": ["MemGPT", "RAG baseline", "A-Mem"],
    },
]


def get_b_library():
    return B_LIBRARY


def get_b_by_id(b_id):
    for b in B_LIBRARY:
        if b["id"] == b_id:
            return b
    return None


def format_b_context(b, include_full_knowledge=True):
    """
    格式化 B 方向的上下文
    include_full_knowledge=True: 包含完整的 MD 知识（长但深）
    """
    base = f"""
领域: {b['domain']}
本质问题: {b['problem']}
可用数据集: {', '.join(b['datasets'])}
基线方法: {', '.join(b['baselines'])}
"""

    if include_full_knowledge and b.get("knowledge_md"):
        md_content = load_knowledge(b["knowledge_md"])
        if md_content:
            base += f"\n\n【社区深度知识 - 必读！】\n{md_content}\n"

    return base


if __name__ == "__main__":
    for b in B_LIBRARY:
        print(f"[{b['id']}] {b['domain']}")
        md = load_knowledge(b.get("knowledge_md", ""))
        if md:
            print(f"  知识MD: ✅ {len(md)} 字符")
        else:
            print(f"  知识MD: ❌ 缺失")
