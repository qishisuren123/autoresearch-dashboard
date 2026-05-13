#!/bin/bash
cd /data/renyiming/AutoResearch
/data/renyiming/miniconda3/bin/python3 -u daily_full.py >> logs/cron.log 2>&1
