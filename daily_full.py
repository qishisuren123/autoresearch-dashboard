"""
每日完整流水线：大浪淘沙（信息聚合+筛选）→ Idea Forge（A+B 生成+验证+计划书）
后台运行，无需人工干预。
"""

import sys
import json
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))
sys.path.insert(0, str(Path(__file__).parent / "src" / "collectors"))

LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_DIR / f"daily_{datetime.now().strftime('%Y%m%d')}.log", "a") as f:
        f.write(line + "\n")


def run_dalang_taosha():
    """模块一：大浪淘沙 - 信息采集 + 筛选种子"""
    log("=" * 60)
    log("模块一：大浪淘沙 - 信息采集与热点筛选")
    log("=" * 60)

    from pipeline_v4 import run_pipeline_v4
    result = run_pipeline_v4()
    return result


def run_extra_channels():
    """采集附加渠道：博客 + Emergent Mind + 中文媒体 + 顶会"""
    log("附加渠道采集...")
    from emergent_mind_collector import collect_emergent_mind
    from paper_digest_collector import collect_paper_digest
    from influential_voices import collect_research_blogs, collect_conference_highlights
    from jina_chinese_media import collect_chinese_media

    items = []
    items.extend(collect_emergent_mind())
    items.extend(collect_paper_digest())
    items.extend(collect_research_blogs(max_days=7))
    items.extend(collect_conference_highlights())
    items.extend(collect_chinese_media(first_run=False))

    log(f"  附加渠道总计: {len(items)} 条")
    return items


def run_idea_forge(seeds):
    """模块二：Idea Forge - A+B 生成+验证+计划书"""
    log("=" * 60)
    log(f"模块二：Idea Forge - {len(seeds)} 个种子")
    log("=" * 60)

    from idea_forge.forge import run_idea_forge
    from idea_forge.b_library import get_b_library

    # 用全部 B 方向
    b_ids = [b["id"] for b in get_b_library()]
    result = run_idea_forge(seeds, b_ids=b_ids)
    return result


def update_dashboard():
    """更新网页"""
    log("更新网页...")
    from generate_dashboard import generate_html
    generate_html()


def git_push():
    """推送到 GitHub Pages"""
    import subprocess
    try:
        subprocess.run(
            ["git", "add", "-A"],
            cwd=str(Path(__file__).parent), capture_output=True
        )
        subprocess.run(
            ["git", "commit", "-m", f"Daily auto: {datetime.now().strftime('%Y-%m-%d')}"],
            cwd=str(Path(__file__).parent), capture_output=True
        )
        subprocess.run(
            ["git", "push", "origin", "gh-pages"],
            cwd=str(Path(__file__).parent), capture_output=True
        )
        log("  Git push 完成")
    except Exception as e:
        log(f"  Git push 失败: {e}")


def main():
    start = time.time()
    today = datetime.now().strftime("%Y-%m-%d")
    log(f"{'═' * 60}")
    log(f"每日全流程开始: {today}")
    log(f"{'═' * 60}")

    # 1. 大浪淘沙
    try:
        v4_result = run_dalang_taosha()
    except Exception as e:
        log(f"大浪淘沙失败: {e}")
        v4_result = None

    # 2. 附加渠道
    try:
        extra = run_extra_channels()
    except Exception as e:
        log(f"附加渠道失败: {e}")
        extra = []

    # 3. 提取强推荐种子
    seeds = []
    if v4_result:
        candidates = v4_result.get("final_candidates", [])
        seeds = [c for c in candidates if "强推荐" in c.get("conclusion", "")]
    log(f"强推荐种子: {len(seeds)} 个")

    # 如果今天没有新种子，加载历史种子
    if not seeds:
        import glob
        verified_dir = Path(__file__).parent / "data" / "verified"
        files = sorted(glob.glob(str(verified_dir / "final_*.json")) +
                       glob.glob(str(verified_dir / "pipeline_v4_*.json")))
        if files:
            with open(files[-1]) as f:
                data = json.load(f)
            candidates = data.get("final_candidates", [])
            seeds = [c for c in candidates if "强推荐" in c.get("conclusion", "")]
        log(f"使用历史种子: {len(seeds)} 个")

    # 4. Idea Forge（对所有强推荐种子跑 A+B）
    if seeds:
        try:
            forge_result = run_idea_forge(seeds)
            log(f"Forge 结果: {forge_result['summary']}")
        except Exception as e:
            log(f"Idea Forge 失败: {e}")
    else:
        log("无种子可处理，跳过 Forge")

    # 5. 更新网页
    try:
        update_dashboard()
    except Exception as e:
        log(f"网页更新失败: {e}")

    # 6. 推送
    git_push()

    elapsed = time.time() - start
    log(f"{'═' * 60}")
    log(f"全流程完成，耗时 {elapsed/60:.1f} 分钟")
    log(f"{'═' * 60}")


if __name__ == "__main__":
    main()
