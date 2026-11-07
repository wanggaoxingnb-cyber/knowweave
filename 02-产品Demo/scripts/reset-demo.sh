#!/bin/bash
# 重置记忆库到种子状态（演示前用）：cd 02-产品Demo && bash scripts/reset-demo.sh
set -e
cd "$(dirname "$0")/.."
mkdir -p /tmp/knowweave-backup-$(date +%s)
mv memory/concepts/*.md /tmp/knowweave-backup-*/ 2>/dev/null || true
cp ../04-记忆库样例/*.md memory/concepts/
cp ../04-记忆库样例/profiles/user.md memory/profiles/user.md
# 清掉测试期残留：待学习区、问答留痕、TTS 音频（演绎缓存保留，演示时秒开）
rm -f memory/inbox/*.md data/history/qa-*.md data/audio/*.mp3 2>/dev/null || true
echo "记忆库已重置（$(ls memory/concepts | wc -l | tr -d ' ') 个概念），inbox/留痕/音频已清空，演绎缓存保留。旧文件备份在 /tmp/knowweave-backup-*"
