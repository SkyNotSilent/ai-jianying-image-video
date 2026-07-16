# InsightCut 生文服务商目录与模型选择器设计

## 目标

将 API 配置页从“先理解协议、地址和模型名，再手工输入”改为“选择服务商和模型即可完成常规配置”：

1. 服务商、调用协议和模型成为三个独立概念，页面首先让用户选择真正的服务商。
2. 服务商与模型目录优先复用后端已经使用的 LiteLLM 元数据，不在前端重复维护一份容易过期的名单。
3. 常规配置使用预置地址、动态凭证字段和可搜索模型选择器；自由输入只保留在“自定义兼容接口”和高级配置中。
4. LiteLLM 本地模型目录与账号远程可用模型合并展示；远程同步失败不影响本地选择和已有配置。
5. 现有 OpenAI-compatible、Anthropic-compatible 配置继续兼容，Agnes 生图、豆包 TTS、MiMo TTS、音色试听和声音克隆链路不被破坏。

本设计只处理 API 配置体验与生文调用配置。它不会把生图、TTS 或任务系统迁移到新的 SDK。

## 问题定义与术语

当前页面把 `protocol` 当作最上层选择，又始终展示 `base_url` 和可自由输入的 `model`。即使点击“获取列表”，模型下拉框也只会作为第二个控件出现在输入框下面。对于已知服务商和固定模型，用户仍需理解并输入本应由系统决定的技术字段。

改造后统一使用以下术语：

- **服务商 Provider**：实际提供 API 的公司、云平台、本地运行时或聚合网关，例如 DeepSeek、Anthropic、OpenRouter、Ollama 和小米 MiMo。
- **协议 Protocol**：服务商接受的请求格式，例如 OpenAI Chat Completions 或 Anthropic Messages。协议由服务商预置决定，不作为普通用户的第一层选择。
- **模型 Model**：具体模型的 LiteLLM 规范 ID，例如 `deepseek/deepseek-chat`。
- **自定义兼容接口**：无法由服务商预置表达时使用的自由配置入口，继续支持 OpenAI-compatible 和 Anthropic-compatible。

## 产品原则

- 默认界面服务于常规选择，高级界面保留现有自由度。
- 能由服务商预置推导出的值不要求用户手填。
- API Key、云平台账号和区域等用户私有凭证仍需用户提供。
- 本地目录立即可用，远程同步只负责确认账号实际可用范围，不能成为配置页的单点故障。
- 已保存值优先于目录更新；系统不能因为模型下架、改名或同步失败而静默替换用户配置。
- Provider 目录由后端统一输出，前端只负责搜索、选择和动态渲染字段。

## Provider Registry

后端增加独立的 Provider Registry，作为配置页和生文运行时之间的唯一服务商元数据来源。Registry 的数据来自三层：

1. 当前安装版本 LiteLLM 的 provider 与模型元数据，过滤为可用于生文的模型。
2. 项目覆盖层，为常用服务商补充中文名称、推荐排序、默认地址、凭证字段、远程模型同步方式和推荐模型。
3. 项目扩展层，加入 LiteLLM 目录未完整覆盖但 InsightCut 已经实测使用的小米 MiMo 等服务商。

项目不在运行时强依赖公共 LiteLLM Catalog API。升级 Python 依赖后可以获得新的内置目录；覆盖层只维护产品展示和连接差异，不复制完整模型名单。

每个服务商条目至少包含：

```json
{
  "id": "deepseek",
  "name": "DeepSeek",
  "litellm_provider": "deepseek",
  "group": "recommended",
  "connection_mode": "litellm",
  "compatibility_protocol": "openai",
  "default_base_url": "https://api.deepseek.com",
  "recommended_model": "deepseek/deepseek-chat",
  "credential_fields": [
    { "id": "api_key", "label": "API Key", "required": true, "secret": true }
  ],
  "supports_live_models": true,
  "config_status": "ready"
}
```

Provider 目录完整性与直接配置能力分开表达：

- LiteLLM 生文目录中的服务商都可以被搜索和查看。
- 常规 API Key、Base URL 类服务商可以直接配置。
- Azure、Bedrock 等需要特殊账号、区域或部署参数的服务商由 `credential_fields` 动态声明字段。
- 如果当前 Registry 尚未为某个特殊认证方式提供安全字段映射，必须在选择前标记为“需要高级配置”，不能让用户填写完成后才发现运行时不支持。
- `provider_options` 只能接收 Registry 明确允许的字段，不能把任意前端键值直接透传给 LiteLLM。

## API 设计

新增三个端点：

- `GET /ai/native/video/kepu/config/llm-providers`：返回服务商摘要、分组、凭证字段和能力标记，不返回密钥。
- `GET /ai/native/video/kepu/config/llm-providers/{provider_id}/models`：从本机 LiteLLM 目录与项目扩展层返回该服务商的生文模型。
- `POST /ai/native/video/kepu/config/llm-providers/{provider_id}/models/refresh`：接收当前未保存的连接草稿，尝试读取账号实际可用模型并返回合并所需的数据。

远程同步响应区分来源：

```json
{
  "models": [
    { "id": "deepseek/deepseek-chat", "label": "DeepSeek Chat", "sources": ["catalog", "account"] }
  ],
  "synced": true
}
```

不是所有服务商都提供标准模型列表接口。Registry 为支持同步的服务商指定适配器；没有适配器时只使用本地目录，并在页面显示“该服务商不支持账号模型同步”，而不是构造一个可能错误的 `/models` 地址。

现有 `POST /config/models` 在迁移期保留，内部可以继续服务旧前端或转调新的通用兼容接口同步逻辑。

## 配置结构与兼容

`llm` 配置增加明确的 `provider`，保留现有字段：

```json
{
  "llm": {
    "provider": "deepseek",
    "protocol": "openai",
    "base_url": "https://api.deepseek.com",
    "api_key": "...",
    "model": "deepseek/deepseek-chat",
    "provider_options": {}
  }
}
```

`provider` 与规范模型 ID 是新配置的运行时主键。`protocol` 继续保留，用于兼容旧配置并描述“自定义兼容接口”采用 OpenAI 还是 Anthropic 格式；已识别服务商不再依赖这个二选一字段决定 LiteLLM 路由。Registry 的 `connection_mode` 表示使用 LiteLLM 原生 provider、自定义 OpenAI-compatible 或自定义 Anthropic-compatible。

兼容规则如下：

- 新配置保存 LiteLLM 规范模型 ID；显示名称仅用于 UI，不作为运行时参数。
- 读取旧配置时，优先根据模型前缀识别 provider，其次根据 Base URL 和协议匹配项目预置；无法可靠识别时归入“自定义兼容接口”。
- 旧配置只在内存中归一化，不因打开配置页自动重写；用户保存后才写入新增字段。
- 旧模型不在当前目录时仍然保留，模型选择器将其标记为“当前配置”或“历史/自定义模型”。
- 用户切换服务商时，前端按 provider 暂存本次页面会话中的未保存草稿；切回时恢复。最终只持久化当前选中的生文服务商。

## 生文运行时

`ArticleGenerator` 继续使用 LiteLLM，不引入第二套 TypeScript SDK：

- 新配置中的规范模型 ID直接传给 `litellm.completion()`。
- 旧的不带前缀模型继续使用现有 `protocol` 前缀兼容逻辑。
- 新配置优先按 `provider` 和规范模型 ID 路由；只有旧配置或自定义兼容接口才使用 `protocol` 推断前缀。
- `api_base` 只在服务商预置要求覆盖地址或使用自定义兼容接口时传入，避免对 LiteLLM 原生 provider 强行覆盖错误地址。
- Registry 允许的 `provider_options` 经过后端校验后再映射为 LiteLLM 参数，以支持区域、部署名等特殊连接字段。
- 运行错误继续使用统一重试策略，但日志不得包含 API Key、Authorization header 或完整凭证对象。

## 前端交互

### 生文模型

“生文模型”区域改为渐进式配置：

1. 服务商使用可搜索组合框，按“常用推荐”“项目扩展”“全部服务商”分组。
2. 选择服务商后，页面根据 Registry 动态渲染其凭证字段，并立即读取本地模型目录。
3. 模型使用唯一的可搜索选择器，不再同时显示一个自由输入框和一个下拉框。
4. 模型按“推荐”“当前账号可用”“其他内置模型”分组；重复模型合并，账号可用状态优先展示。
5. 有远程同步能力时显示“验证并同步”按钮；同步结果合并到当前选择器，不创建第二个模型控件。
6. 协议、默认地址和 LiteLLM provider 收进“高级配置”，默认以只读摘要展示。
7. 只有“自定义兼容接口”允许直接编辑协议、Base URL 和 Model。

选择服务商时自动选中其推荐模型。若正在编辑已经保存的配置，则现有模型优先，不能被推荐值覆盖。

### Agnes 生图

Agnes 当前只有项目已验证的固定连接方式。普通配置展示服务商与模型摘要，只保留 API Key、图片尺寸等用户可变字段。API URL 和模型进入高级配置，可查看、覆盖并一键恢复项目预置。

### 豆包与 MiMo TTS

保留现有双 Provider、音色库、试听、语速、音量、风格与 MiMo 声音克隆交互。Base URL、Cluster、固定模型、克隆模型和音频格式收进各自的“高级配置”；凭证、默认音色和用户会经常调整的生成参数继续放在普通区域。

## 错误处理与安全

- Provider Registry 读取失败时返回项目扩展与当前配置的最小降级列表，配置页不能整体白屏。
- LiteLLM 本地模型目录为空时保留当前模型，并允许用户进入高级配置处理。
- 远程同步失败只更新同步状态，不清空本地目录、当前选择或已填写凭证。
- 错误响应区分凭证失败、接口不支持、限流、网络失败和响应无法解析；返回前清理 URL 查询密钥、请求头和响应中的敏感字段。
- 远程同步请求使用表单草稿但不单独持久化；只有用户点击“保存配置”后才写入本地配置。
- API Key 输入不得触发每次按键请求；用户明确点击“验证并同步”时才访问服务商。
- 搜索、模型过滤和分组在本地完成，避免输入内容发送给第三方。
- 目录更新不得静默替换已保存模型、协议或地址。

## 测试设计

### 后端单元与接口测试

- 从 LiteLLM 元数据中过滤生文服务商与模型，项目覆盖和 MiMo 扩展正确合并。
- 服务商分组、推荐模型、动态凭证字段和配置状态正确。
- 规范模型 ID、旧模型前缀、Base URL 推断与自定义兼容回退正确。
- 本地模型端点、远程同步成功、无同步适配器、无效凭证、限流和非 JSON 响应行为正确。
- 远程同步响应与日志不包含提交的 API Key。
- `provider_options` 只允许 Registry 声明字段，未知字段被拒绝。
- `ArticleGenerator` 对规范模型、旧配置、原生 provider、自定义 Base URL 和特殊 provider 参数生成正确的 LiteLLM 调用参数。

测试不能断言 LiteLLM 目录的固定总数量，以免依赖升级后产生无意义失败；应断言已知样本、过滤规则和项目扩展项。

### 前端测试

- 服务商搜索和三个分组正确，特殊认证服务商在选择前显示配置状态。
- 服务商切换不会丢失本次页面会话中的未保存草稿。
- 已保存模型优先于推荐模型；首次选择服务商时自动选择推荐模型。
- 本地、账号和历史模型正确合并、去重、分组和回显。
- 远程同步失败不清空选择，成功结果写入同一个模型选择器。
- 自定义兼容接口显示可编辑技术字段，普通服务商默认折叠这些字段。
- Agnes、豆包与 MiMo 的普通字段和高级字段边界正确。

### 回归与真实流程

- 运行后端和前端完整测试，以及前端生产构建。
- 实际完成“选择 MiMo → 自动显示内置模型 → 验证并同步 → 保存 → 刷新后正确回显”的浏览器流程。
- 用旧的 OpenAI-compatible 和 Anthropic-compatible 配置各做一次归一化回归，确认无需重新输入即可显示与保存。
- 验证 Agnes 生图配置、MiMo TTS、豆包 TTS、音色试听和 MiMo 声音克隆仍能加载；本次改造不修改其生成请求格式。

## 文档同步

实施时如果修改配置字段、启动约定或开发注意事项，必须同步更新根目录 `AGENTS.md` 和 `CLAUDE.md`，并保证两份文件内容一致。文档需要说明 `llm.provider`、LiteLLM 规范模型 ID、Provider Registry、自定义兼容回退和凭证安全边界。

## 非目标

- 不引入 Vercel AI SDK 或把 Python 生文运行时迁移到 Node.js。
- 不实现统一计费、模型价格结算、配额统计、路由故障转移或多模型负载均衡。
- 不要求每个服务商都支持远程账号模型同步。
- 不自动在线更新 LiteLLM 依赖或公共模型目录。
- 不将 API Key 上传到 InsightCut 自有远端服务；项目继续使用本地配置与本地存储。

## 参考资料

- LiteLLM 文档：<https://docs.litellm.ai/>
- LiteLLM Provider 与模型目录：<https://models.litellm.ai/>
- LiteLLM Model Catalog API：<https://api.litellm.ai/docs>
- Vercel AI SDK Provider 架构（仅作方案比较，本项目不引入）：<https://github.com/vercel/ai>
