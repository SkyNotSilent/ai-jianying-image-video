#!/bin/bash
# 快速测试脚本 - 测试最新生成的草稿

set -e

# 激活虚拟环境
source venv/bin/activate

# 如果提供了项目名称，测试指定项目
if [ $# -eq 1 ]; then
    PROJECT_NAME="$1"
    echo "🔍 测试项目: $PROJECT_NAME"
    python tests/test_jianying_compatibility.py "output/$PROJECT_NAME"
    exit $?
fi

# 否则测试最新修改的项目（必须包含 draft_content.json）
LATEST_PROJECT=""
for dir in $(ls -td output/*/); do
    if [ -f "${dir}draft_content.json" ]; then
        LATEST_PROJECT="$dir"
        break
    fi
done

if [ -z "$LATEST_PROJECT" ]; then
    echo "❌ 没有找到包含 draft_content.json 的项目"
    exit 1
fi

PROJECT_NAME=$(basename "$LATEST_PROJECT")

echo "🔍 测试最新项目: $PROJECT_NAME"
echo "📅 修改时间: $(stat -f "%Sm" -t "%Y-%m-%d %H:%M:%S" "$LATEST_PROJECT")"
echo ""

python tests/test_jianying_compatibility.py "$LATEST_PROJECT"

# 如果测试通过，提示可以导入
if [ $? -eq 0 ]; then
    echo ""
    echo "✨ 测试通过！可以导入到剪映："
    echo ""
    echo "   方法1 (推荐)："
    echo "   cp -r \"$LATEST_PROJECT\" ~/Movies/JianyingPro\\ Drafts/"
    echo ""
    echo "   方法2："
    echo "   在剪映中选择 文件 -> 导入草稿 -> 选择 $LATEST_PROJECT"
    echo ""
fi
