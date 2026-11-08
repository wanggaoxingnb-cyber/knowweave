#!/bin/bash
# 重置记忆库到种子状态（演示前用）：cd 织识-Demo && bash scripts/reset-demo.sh
set -e
cd "$(dirname "$0")/.."
mkdir -p /tmp/knowweave-backup-$(date +%s)
mv memory/concepts/*.md /tmp/knowweave-backup-*/ 2>/dev/null || true
cp data/seeds/concepts/*.md memory/concepts/
cp data/seeds/profiles/user.md memory/profiles/user.md 2>/dev/null || true
rm -f memory/inbox/*.md data/history/qa-*.md data/audio/*.mp3 2>/dev/null || true
echo "记忆库已重置（$(ls memory/concepts | wc -l | tr -d ' ') 个概念），inbox/留痕/音频已清空。旧文件备份在 /tmp/knowweave-backup-*"
