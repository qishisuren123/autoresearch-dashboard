"""
补跑脚本：对 pending_forge_seeds.json 里的种子运行 Idea Forge
在免费窗口（北京时间 00:00-08:00）内运行，优先使用灵活 Claude
"""
import sys
import json
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

PENDING_FILE = Path(__file__).parent / "data" / "pending_forge_seeds.json"


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG_DIR / f"pending_forge_{datetime.now().strftime('%Y%m%d')}.log", "a") as f:
        f.write(line + "\n")


def main():
    if not PENDING_FILE.exists():
        log("没有找到 pending_forge_seeds.json，退出")
        return

    data = json.loads(PENDING_FILE.read_text())
    seeds = data.get("seeds", [])
    if not seeds:
        log("pending 列表为空，无需补跑")
        return

    log(f"补跑 Forge：共 {len(seeds)} 个待处理种子")
    for s in seeds:
        log(f"  · {s.get('title','')[:70]}")

    from idea_forge.forge import run_idea_forge
    from idea_forge.b_library import get_b_library

    b_ids = [b["id"] for b in get_b_library()]

    start = time.time()
    result = run_idea_forge(seeds, b_ids=b_ids)
    elapsed = time.time() - start

    log(f"补跑完成，耗时 {elapsed/60:.1f} 分钟")
    log(f"结果: {result.get('summary', result)}")

    # 更新网页
    try:
        from generate_dashboard import generate_html
        generate_html()
        log("网页已更新")
    except Exception as e:
        log(f"网页更新失败: {e}")

    try:
        from generate_idea_page import generate as gen_idea
        gen_idea()
        log("Idea 页面已更新")
    except Exception as e:
        log(f"Idea 页面更新失败: {e}")

    # git push
    import subprocess
    subprocess.run(["git", "add", "-A"], cwd=str(Path(__file__).parent), capture_output=True)
    subprocess.run(["git", "commit", "-m", f"Pending forge: {datetime.now().strftime('%Y-%m-%d')}"],
                   cwd=str(Path(__file__).parent), capture_output=True)
    r = subprocess.run(["git", "push", "origin", "gh-pages"],
                       cwd=str(Path(__file__).parent), capture_output=True)
    log(f"Git push: {'ok' if r.returncode == 0 else r.stderr.decode()[:100]}")

    # 清空 pending（跑完了）
    PENDING_FILE.write_text(json.dumps({"seeds": [], "count": 0}, ensure_ascii=False, indent=2))
    log("pending_forge_seeds.json 已清空")


if __name__ == "__main__":
    main()
