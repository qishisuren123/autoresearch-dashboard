#!/bin/bash
cd /data/renyiming/AutoResearch
/usr/bin/python3 daily_full.py >> logs/cron.log 2>&1
