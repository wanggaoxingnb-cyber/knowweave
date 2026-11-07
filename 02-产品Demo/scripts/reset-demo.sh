#!/bin/bash
# 重置记忆库到种子状态（演示前用）：cd 02-产品Demo && bash scripts/reset-demo.sh
set -e
cd "$(dirname "$0")/.."
mkdir -p /tmp/knowweave-backup-$(date +%s)
mv memory/concepts/*.md /tmp/knowweave-backup-*/ 2>/dev/null || true
cp ../04-记忆库样例/*.md memory/concepts/
cp ../04-记忆库样例/profiles/user.md memory/profiles/user.md
echo "记忆库已重置（$(ls memory/concepts | wc -l | tr -d ' ') 个概念），旧文件备份在 /tmp/knowweave-backup-*"
