"""
AutoResearch 主入口
一键运行关 1 + 关 2，输出高置信 A 候选清单
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from pipeline_gate1 import run_gate1
from analyzers.sentiment_analyzer import run_gate2


def main():
    print("""
    ╔══════════════════════════════════════════════════╗
    ║         AutoResearch - Idea 采集系统            ║
    ║         关 1: 主流媒体共识筛选                   ║
    ║         关 2: 社交舆情真伪验证                   ║
    ╚══════════════════════════════════════════════════╝
    """)

    # 关 1
    gate1_output, gate1_file = run_gate1()

    if not gate1_output:
        print("\n关 1 未产出候选，终止。")
        return

    # 关 2
    verified = run_gate2(gate1_output, top_k=10)

    # 最终输出：高置信 A 清单
    genuine = [v for v in verified if v["gate2_verdict"] in ("genuine_hot", "likely_genuine")]
    print(f"\n{'═' * 60}")
    print(f"  最终结果：{len(genuine)} 个高置信 A 候选")
    print(f"{'═' * 60}")
    for i, item in enumerate(genuine, 1):
        print(f"  {i}. [{item['gate2_authenticity']:.2f}] {item['title'][:65]}")
    print()


if __name__ == "__main__":
    main()
