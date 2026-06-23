# 剪映兼容性测试工具使用指南

## 快速开始

### 1. 测试最新生成的项目（最常用）

```bash
./tests/quick_test.sh
```

这会自动找到最新修改的包含 `draft_content.json` 的项目并测试。

### 2. 测试指定项目

```bash
./tests/quick_test.sh 行行出状元
```

或者：

```bash
source venv/bin/activate
python tests/test_jianying_compatibility.py output/行行出状元
```

### 3. 批量测试所有项目

```bash
source venv/bin/activate
python tests/batch_test_all_drafts.py
```

## 测试工具说明

### 📋 测试内容（8项检查）

1. **文件存在性** - 检查 draft_content.json 和 draft_meta_info.json
2. **JSON 格式** - 验证 JSON 语法正确性
3. **必需字段** - 检查 id, duration, fps, materials, tracks 等
4. **轨道结构** - 验证视频轨、音频轨、文本轨结构
5. **时间轴连续性** - 检测间隙和重叠
6. **素材引用** - 验证所有引用的素材都存在
7. **文件路径** - 检查素材文件是否真实存在
8. **时长一致性** - 验证草稿时长与轨道时长匹配

### 📊 测试结果解读

#### ✅ 完全通过
```
🎉 所有关键测试通过！草稿应该可以在剪映中正常打开。
```
**说明：** 可以安全导入到剪映

#### ⚠️ 有警告
```
⚠️  警告 (不影响导入):
  轨道 video 存在间隙: 0.033秒
```
**说明：** 可以导入，但可能有小问题

#### ❌ 有错误
```
💥 发现 3 个错误，需要修复后才能导入剪映。
```
**说明：** 必须修复错误才能导入

## 实际导入到剪映

### macOS 导入方法

测试通过后，使用以下命令导入：

```bash
# 复制到剪映草稿目录
cp -r output/项目名称 ~/Movies/JianyingPro\ Drafts/
```

然后打开剪映专业版，在草稿列表中就能看到导入的项目。

### 验证清单

在剪映中打开项目后，检查：

- [ ] 草稿能正常打开（无报错）
- [ ] 视频片段按顺序排列
- [ ] 音频正确对齐
- [ ] 字幕显示正常
- [ ] 播放流畅
- [ ] 时长正确

## 测试结果统计

最近一次批量测试结果：

```
✅ 完全通过: 9 个项目
   - 11
   - 3:4测试-短
   - 3:4测试v3
   - 书
   - 毅力
   - 穷人的本质
   - 萧炎
   - 行行出状元
   - 贫穷的本质

总计: 9 个项目
成功率: 100.0%
```

## 常见问题

### Q: 测试通过但剪映打不开？

A: 自动化测试只能验证格式，某些兼容性问题需要实际导入才能发现。请提供错误信息以便改进测试工具。

### Q: 如何测试特定功能？

A: 创建最小测试用例，例如：
- 只有3段视频的简单项目
- 测试特定画幅比例（3:4, 9:16）
- 测试长视频（10分钟+）

### Q: 测试失败如何修复？

A: 查看测试报告中的错误信息，通常是：
- 素材文件缺失 → 检查生成流程
- 时间轴不连续 → 检查时长计算逻辑
- 必需字段缺失 → 检查 JSON 生成代码

## 开发建议

1. **每次生成后立即测试**
   ```bash
   # 生成草稿
   python main.py --topic "测试主题"
   
   # 立即测试
   ./tests/quick_test.sh
   ```

2. **修改代码前后对比**
   ```bash
   # 修改前
   python tests/batch_test_all_drafts.py > before.txt
   
   # 修改代码...
   
   # 修改后
   python tests/batch_test_all_drafts.py > after.txt
   
   # 对比
   diff before.txt after.txt
   ```

3. **定期批量验证**
   ```bash
   # 每周运行一次
   python tests/batch_test_all_drafts.py
   ```

## 文件说明

- `test_jianying_compatibility.py` - 单项目测试工具
- `batch_test_all_drafts.py` - 批量测试工具
- `quick_test.sh` - 快速测试脚本（推荐日常使用）
- `README.md` - 详细文档

## 更多信息

详细文档请查看：`tests/README.md`
