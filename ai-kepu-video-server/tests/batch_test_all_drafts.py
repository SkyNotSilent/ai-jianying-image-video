#!/usr/bin/env python3
"""
批量测试所有草稿的剪映兼容性
"""

import os
import sys
from pathlib import Path
from test_jianying_compatibility import JianyingCompatibilityTester


def find_all_drafts(output_dir: str) -> list:
    """查找所有包含 draft_content.json 的目录"""
    output_path = Path(output_dir)
    draft_dirs = []

    for item in output_path.iterdir():
        if item.is_dir():
            draft_content = item / "draft_content.json"
            if draft_content.exists():
                draft_dirs.append(item)

    return sorted(draft_dirs)


def main():
    """主函数"""
    output_dir = "output"

    if len(sys.argv) > 1:
        output_dir = sys.argv[1]

    if not os.path.exists(output_dir):
        print(f"❌ 目录不存在: {output_dir}")
        sys.exit(1)

    # 查找所有草稿
    draft_dirs = find_all_drafts(output_dir)

    if not draft_dirs:
        print(f"❌ 在 {output_dir} 中没有找到任何草稿")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"批量测试剪映兼容性")
    print(f"找到 {len(draft_dirs)} 个草稿项目")
    print(f"{'='*60}\n")

    # 测试结果统计
    results = {
        'passed': [],
        'failed': [],
        'warnings': []
    }

    # 逐个测试
    for i, draft_dir in enumerate(draft_dirs, 1):
        project_name = draft_dir.name
        print(f"\n[{i}/{len(draft_dirs)}] 测试: {project_name}")
        print("-" * 60)

        tester = JianyingCompatibilityTester(str(draft_dir))
        success = tester.run_all_tests()

        if success:
            if tester.warnings:
                results['warnings'].append(project_name)
            else:
                results['passed'].append(project_name)
        else:
            results['failed'].append(project_name)

    # 打印总结
    print(f"\n{'='*60}")
    print("批量测试总结")
    print(f"{'='*60}\n")

    print(f"✅ 完全通过: {len(results['passed'])} 个")
    for name in results['passed']:
        print(f"   - {name}")

    if results['warnings']:
        print(f"\n⚠️  有警告: {len(results['warnings'])} 个")
        for name in results['warnings']:
            print(f"   - {name}")

    if results['failed']:
        print(f"\n❌ 失败: {len(results['failed'])} 个")
        for name in results['failed']:
            print(f"   - {name}")

    print(f"\n总计: {len(draft_dirs)} 个项目")
    print(f"成功率: {(len(results['passed']) + len(results['warnings'])) / len(draft_dirs) * 100:.1f}%")
    print(f"\n{'='*60}\n")

    # 返回状态码
    sys.exit(0 if not results['failed'] else 1)


if __name__ == "__main__":
    main()
