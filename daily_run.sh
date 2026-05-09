#!/bin/bash
# 大浪淘沙 每日自动运行脚本
# 用法: 加入 crontab: 0 8 * * * /data/renyiming/AutoResearch/daily_run.sh

cd /data/renyiming/AutoResearch

# 记录开始时间
echo "$(date): 大浪淘沙 daily run started" >> logs/cron.log

# 运行 pipeline
python3 src/pipeline_v4.py >> logs/pipeline_$(date +%Y%m%d).log 2>&1

# 运行新渠道采集
python3 -c "
import sys, json, time, os
from pathlib import Path
from datetime import datetime
sys.path.insert(0, 'src')
sys.path.insert(0, 'src/collectors')
from emergent_mind_collector import collect_emergent_mind
from paper_digest_collector import collect_paper_digest
from influential_voices import collect_research_blogs, collect_conference_highlights
from jina_chinese_media import collect_chinese_media

results = {}
results['emergent_mind'] = collect_emergent_mind()
results['paper_digest'] = collect_paper_digest()
results['blogs'] = collect_research_blogs(max_days=7)  # 日常只查7天
results['conferences'] = collect_conference_highlights()
results['chinese_media'] = collect_chinese_media(first_run=False)

# 保存
today = datetime.now().strftime('%Y%m%d')
all_items = []
for v in results.values():
    all_items.extend(v)
output_file = Path(f'data/candidates/channels_{today}.json')
output_file.parent.mkdir(parents=True, exist_ok=True)
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(all_items, f, ensure_ascii=False, indent=2)
print(f'Saved {len(all_items)} items to {output_file}')
" >> logs/channels_$(date +%Y%m%d).log 2>&1

# 生成网页并推送
python3 src/generate_dashboard.py >> logs/dashboard_$(date +%Y%m%d).log 2>&1

# 推送到 GitHub Pages
git add index.html data/ && \
git commit -m "Daily update $(date +%Y-%m-%d)" && \
git push origin gh-pages >> logs/git_$(date +%Y%m%d).log 2>&1

echo "$(date): 大浪淘沙 daily run completed" >> logs/cron.log
