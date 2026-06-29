# InsightCut 功能逻辑审查报告

审查日期：2026-06-27

## 审查范围

- 当前运行页面：`http://localhost:2001/preview/1c205ef90cd04114905883ae232f134f`
- 前端源码：`ai-kepu-video-web/frontend/src`
- 后端接口存在性：`ai-kepu-video-server/src/api/routes.py`
- 当前任务接口：
  - `/ai/native/video/kepu/tasks/1c205ef90cd04114905883ae232f134f`
  - `/ai/native/video/kepu/tasks/1c205ef90cd04114905883ae232f134f/segments`
  - `/ai/native/video/kepu/tasks/1c205ef90cd04114905883ae232f134f/export-state`

## 当前任务核对

当前任务表面状态是 `completed`，但并不是一个真正可交付的视频任务：

- `task.status = completed`
- `task.error = expected str, bytes or os.PathLike object, not NoneType`
- 分镜数：3
- 3 个分镜的 `image_status` 全部为 `failed`
- 3 个分镜的 `image_url` 全部为空
- 3 个分镜的 `audio_status` 为 `completed`
- `export-state.preview.exists = false`
- `export-state.outputs.mp4.available = false`
- `export-state.outputs.draft.available = true`

结论：当前系统存在“部分失败任务被当成完成任务展示”的核心状态问题。

## Findings

### P0 - 完成、失败、可导出的状态被混在一起

位置：
- `ai-kepu-video-web/frontend/src/views/ProjectAssetsView.vue`
- `ai-kepu-video-web/frontend/src/views/PreviewView.vue`
- `ai-kepu-video-web/frontend/src/views/ResultView.vue`

证据：
- `ProjectAssetsView.vue` 的 `projectActionLabel()` 只对 `failed` 显示“查看已保存素材”，其他状态默认显示“查看预览”。
- `PreviewView.vue` 只要有分镜就显示“导出视频”。
- `ResultView.vue` 只判断 `data.status !== 'completed'`，没有检查 `task.error`、分镜素材状态、最终预览状态和 MP4 可用性。

用户影响：
- 用户会看到“已完成 / 查看预览 / 导出视频 / 生成完成”，但实际没有图片、没有最终预览、没有 MP4。
- 这会让用户误以为流程可交付，实际上只能恢复已有素材。

建议：
- 增加统一的前端派生状态，例如：
  - `draft`
  - `processing`
  - `completed`
  - `completed_with_missing_assets`
  - `recoverable_failed`
  - `export_ready`
- 资产页、预览页、导出页、结果页都使用同一个状态判定函数。
- 有 `task.error` 或关键素材失败时，不应显示普通“完成”，应显示“部分失败，可恢复素材”。

### P1 - 文稿页“AI 生成脚本”是未标明的前端模板

位置：
- `ai-kepu-video-web/frontend/src/views/ManuscriptView.vue`

证据：
- `generateScript()` 直接写入固定模板文案，没有调用后端 LLM 或配置里的生文模型。

用户影响：
- 用户以为已经通过 API 配置调用 AI 生成脚本，实际只是插入固定示例。
- 这会破坏“先配置 API，再生产”的信任链路。

建议：
- v1 如果要保留真实能力，应新增/复用生文接口生成文稿。
- 如果暂时不接真实接口，按钮应改为“插入示例文稿”或“使用模板草稿”，不能叫“AI 生成脚本”。

### P1 - 项目资产页承担了新建文稿职责，页面分工不清

位置：
- `ai-kepu-video-web/frontend/src/views/ProjectAssetsView.vue`

证据：
- 右侧 `create-panel` 包含“新建项目 / 文稿输入 / AI 辅写 / 创建文稿”。
- 当前产品原则是：首页是文稿，项目预览和资产在项目资产页。

用户影响：
- 用户不知道应该在首页文稿页创建，还是在资产页右侧创建。
- 资产页变回了旧“一体化创建页”的影子。

建议：
- 资产页只保留项目列表、任务状态、预览入口、恢复素材入口。
- 新建内容统一导向 `/manuscript`。
- 如果资产页需要新建按钮，只保留一个“新建文稿”入口，不在资产页内展开完整输入表单。

### P1 - 多个控件看起来可用，但没有真实行为

位置：
- `ManuscriptView.vue`：编辑器工具栏撤销、重做、标题、字号、加粗、斜体、列表、图片。
- `ProjectAssetsView.vue`：列表视图、分页、关闭新建面板、AI 辅写卡片、使用模板创建。
- `ProductionSetupView.vue`：试听、保存为生产预设、部分下拉项。
- `PreviewView.vue`：原始比例、预览质量、全屏、查看更多。
- `NavBar.vue`：通知、团队菜单。

用户影响：
- 用户会点击这些明显像按钮的控件，但没有反馈。
- 这会让用户误判系统坏了，而不是功能未开放。

建议：
- 暂未实现的控件要么隐藏，要么禁用并给出明确提示。
- 不要在 v1 主流程中展示“假按钮”。
- 只保留能真实改变状态、发起接口、导航或给出反馈的控件。

### P1 - 生产设置页展示了不会进入提交参数的设置

位置：
- `ai-kepu-video-web/frontend/src/views/ProductionSetupView.vue`

证据：
- 页面展示了生成并发数、字幕模板、导出模板、高级设置、语速等。
- `startProduction()` 提交 payload 只有 `name/theme/input_mode/style/ratio/length/voice_type`。

用户影响：
- 用户以为改了生产设置，实际很多设置不生效。
- 后续结果和用户预期不一致。

建议：
- v1 页面只展示后端实际消费的参数。
- 字幕、导出模板、高级设置如果暂不接入，应放到“后续能力”或禁用。
- 语速如果需要生效，应进入 task payload 并由后端 TTS 使用。

### P1 - 结果页和导出中心重复，且结果页文案容易误导

位置：
- `ai-kepu-video-web/frontend/src/views/ExportView.vue`
- `ai-kepu-video-web/frontend/src/views/ResultView.vue`

证据：
- 导出中心已有 MP4、剪映草稿导出能力。
- 结果页仍提供旧下载流。
- 结果页标题固定为“生成完成”，副文案固定为“视频草稿和 MP4 已准备就绪”。

用户影响：
- 当前任务没有 MP4，但用户仍可能进入“生成完成”页。
- 两个交付页面会让用户不知道最终应该在哪里下载。

建议：
- 删除结果页，导出中心作为唯一交付页。
- 或将结果页改为导出任务完成后的只读 summary，且所有文案由 `export-state.outputs` 决定。

### P2 - 预览页比例和项目元信息硬编码

位置：
- `ai-kepu-video-web/frontend/src/views/PreviewView.vue`

证据：
- 左侧元信息固定显示 `16:9（横屏）`。
- `ratioClass` 固定返回 `ratio-wide`。

用户影响：
- 9:16、1:1、3:4 项目会在预览页展示错误比例。

建议：
- 从任务详情或 `export-state.ratio/canvas` 读取真实比例。
- player、左侧元信息、导出提示统一由真实 ratio 驱动。

### P2 - 资产页筛选和分页存在假数据

位置：
- `ai-kepu-video-web/frontend/src/views/ProjectAssetsView.vue`

证据：
- 分页条固定显示 `1 / 2 / 3 / 9`，没有真实翻页逻辑。
- `styleCount()` 在没有真实项目时会返回 `Math.max(12, value.length * 4)`。
- 创建时间筛选只是静态展示。

用户影响：
- 用户以为资产页是可靠的数据管理页，但计数和分页不可信。

建议：
- 没有真实分页前隐藏分页。
- 所有筛选计数必须来自真实列表。
- 创建时间筛选要么接真实日期输入和过滤，要么移除。

### P2 - 生产进度页退出和重试都回到文稿首页

位置：
- `ai-kepu-video-web/frontend/src/views/ProcessView.vue`

证据：
- `leaveProcess()` 跳到 `/`。
- `handleRetry()` 跳到 `/`。

用户影响：
- 用户从生成中退出后，很难回到对应项目资产或当前任务。
- 失败后“重新生成”没有带回原文稿或生产配置。

建议：
- 退出应回到 `/assets` 或该任务的资产卡片。
- 重试应回到关联草稿的 `/production/:draftId`，找不到草稿再回资产页。

## 建议处理顺序

### 第一批：状态和交付可信度

1. 建立统一任务派生状态函数。
2. 修复资产页、预览页、导出页、结果页的完成/失败/可恢复判断。
3. 删除或降级结果页，明确导出中心是唯一交付入口。

### 第二批：去掉假功能和重复入口

1. 文稿页 AI 生成脚本接真实接口，或改名为示例模板。
2. 资产页移除内嵌新建表单，只保留“新建文稿”导航入口。
3. 隐藏或禁用所有未实现按钮。

### 第三批：补齐真实参数链路

1. 生产设置只展示真实提交并生效的参数。
2. 语速、字幕、导出模板等如保留，需要进入 payload 并由后端消费。
3. 预览页比例从真实任务/导出状态读取。

## 审查限制

- 本次没有做读屏和完整键盘可访问性测试。
- 本次没有真实触发长耗时生成、重生图、重配音、导出写入剪映目录。
- 本次后端接口存在性已核对，但每个接口的业务成功率未全部复测。

## 结论

现在最需要处理的不是视觉问题，而是产品状态模型和入口职责。当前结构已经接近“文稿 -> 生产 -> 预览 -> 导出/资产”的方向，但还残留旧一体化创建页、旧结果页和一批假控件。先修状态可信度和去假功能，再继续做 1:1 视觉打磨。
