<template>
  <div class="production-page">
    <NavBar active-tab="" @navigate="handleNavigate" />

    <main class="production-layout">
      <aside class="summary-panel">
        <div class="breadcrumb">项目 / 文稿编辑 / <strong>生产设置</strong></div>
        <h1>{{ draft.name || '未命名项目' }}</h1>
        <p>{{ manuscriptPreview || '从已编辑文稿生成 AI 解说视频。' }}</p>

        <div class="summary-card">
          <div>
            <span>{{ isThemeMode ? '扩写目标' : '脚本字数' }}</span>
            <strong>{{ isThemeMode ? `${targetLength} 字` : manuscriptLength }}</strong>
          </div>
          <div>
            <span>{{ isThemeMode ? '生成顺序' : '预计时长' }}</span>
            <strong>{{ isThemeMode ? '先扩写' : durationLabel }}</strong>
          </div>
          <div>
            <span>{{ isThemeMode ? '分镜拆分' : '分镜预估' }}</span>
            <strong>{{ isThemeMode ? '成稿后' : `${segmentCount} 段` }}</strong>
          </div>
        </div>

        <section class="segment-plan">
          <div class="plan-head">
            <strong>分镜计划</strong>
          </div>
          <div class="plan-table">
            <div class="plan-row head">
              <span>#</span>
              <span>内容摘要</span>
              <span>时长</span>
            </div>
            <div v-for="(item, index) in segmentPlan" :key="item.title" class="plan-row">
              <span>{{ String(index + 1).padStart(2, '0') }}</span>
              <span>{{ item.title }}</span>
              <span>{{ item.time }}</span>
            </div>
          </div>
          <div class="asset-protection">
            <WarningFilled />
            <div>
              <strong>资产保护已开启</strong>
              <p>生产过程中产生的素材与草稿将自动保存，失败也保留素材。</p>
            </div>
          </div>
        </section>

        <div v-if="!apiReady" class="api-warning">
          <Warning />
          <div>
            <strong>请先完成 API 配置</strong>
            <span>{{ apiMissingText }}</span>
          </div>
        </div>

        <button type="button" class="surface-button back-script" @click="router.push(`/manuscript/${draft.draft_id}`)">
          <EditPen />
          返回文稿编辑
        </button>
        <button v-if="!apiReady" type="button" class="primary-action config-entry" @click="router.push('/settings')">
          去配置 API
        </button>
      </aside>

      <section class="config-panel">
        <div class="section-head">
          <p>生产配置</p>
          <h2>生产配置</h2>
        </div>

        <section class="production-card">
          <section class="model-line">
            <div class="line-label">图像生成模型</div>
            <div class="model-card">
              <div class="model-avatar">A</div>
              <div>
                <strong>{{ imageModelLabel }} <em>推荐</em></strong>
                <span>{{ llmLabel }} / {{ ttsLabel }}，提交后由 FastAPI 编排</span>
              </div>
              <button type="button" @click="router.push('/settings')">切换模型 ›</button>
            </div>
          </section>

          <section class="style-line">
            <div class="line-row">
              <div class="line-label">画面风格</div>
            </div>
            <div class="style-grid">
              <button v-for="style in visualStyles" :key="style.value" type="button" :class="{ active: draft.visual_style === style.value }" @click="setDraft('visual_style', style.value)">
                <img :src="style.image" :alt="style.label" />
                <span>{{ style.label }}</span>
              </button>
            </div>
          </section>

          <section class="config-row">
            <label>
              <span>视频比例</span>
              <div class="ratio-segments">
                <button v-for="ratio in ratioOptions" :key="ratio" type="button" :class="{ active: draft.ratio === ratio }" @click="setDraft('ratio', ratio)">
                  {{ ratio }}
                </button>
              </div>
            </label>
            <label>
              <span>创作风格</span>
              <select v-model="draft.text_style" @change="persist">
                <option v-for="style in textStyles" :key="style" :value="style">{{ style }}</option>
              </select>
            </label>
          </section>

          <section class="tts-row">
            <label>
              <span>配音音色</span>
              <select v-model="draft.voice_type" @change="onVoiceChange">
                <option value="">自动匹配</option>
                <option v-for="voice in voices" :key="voice.id" :value="voice.id">{{ voice.name }}</option>
              </select>
            </label>
          </section>
        </section>
      </section>

      <aside class="readiness-panel">
        <div class="section-head">
          <p>生产就绪检查</p>
          <h2>生产检查</h2>
        </div>

        <div class="check-list">
          <div v-for="item in checks" :key="item.label" :class="['check-item', item.tone]">
            <component :is="item.icon" />
            <div>
              <strong>{{ item.label }}</strong>
              <span>{{ item.desc }}</span>
            </div>
          </div>
        </div>

        <div class="quota-card">
          <span>今日剩余额度</span>
          <strong>18 / 50 分钟</strong>
          <div class="quota-track"><span style="width: 36%"></span></div>
          <div class="quota-percent">36%</div>
          <p>生图免费限速按 20 RPM 处理，系统会自动串行生成并在 429 后等待重试。</p>
          <div class="quota-lines">
            <div><span>预计消耗时长</span><strong>{{ isThemeMode ? '成稿后计算' : `约 ${durationLabel} 分钟` }}</strong></div>
            <div><span>预计完成时间</span><strong>{{ isThemeMode ? '成稿后计算' : '约 10 分钟' }}</strong></div>
            <div><span>预计消耗额度</span><strong>{{ isThemeMode ? '成稿后计算' : '2.5 / 50 分钟' }}</strong></div>
          </div>
        </div>
      </aside>
    </main>

    <footer class="sticky-actions">
      <button type="button" class="surface-button" @click="router.push(`/manuscript/${draft.draft_id}`)">返回文稿</button>
      <button type="button" class="primary-action" :disabled="submitting || !canSubmit" @click="startProduction">
        {{ submitting ? '提交中...' : apiReady ? '开始生产' : '先配置 API' }}
      </button>
    </footer>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { CircleCheck, EditPen, Warning, WarningFilled } from '@element-plus/icons-vue'
import NavBar from '../components/NavBar.vue'
import { createTask, getConfig, getVoices } from '../api/task'
import {
  estimateDuration,
  estimateSegments,
  getDraft,
  manuscriptText,
  ratioOptions,
  saveDraft,
  textStyles,
  updateDraft,
  visualStyles,
} from '../utils/projectDrafts'

const route = useRoute()
const router = useRouter()
const loadedDraft = getDraft(route.params.draftId)
const draft = reactive({ ...(loadedDraft || {}) })
const voices = ref([])
const config = ref(null)
const submitting = ref(false)

const manuscript = computed(() => manuscriptText(draft))
const isThemeMode = computed(() => draft.input_mode === 'theme')
const manuscriptLength = computed(() => manuscript.value.replace(/\s+/g, '').length)
const durationLabel = computed(() => estimateDuration(manuscript.value, draft.voice_speed))
const segmentCount = computed(() => estimateSegments(manuscript.value))
const targetLength = computed(() => Number(draft.length) === 0 ? 300 : Math.max(50, Math.min(2000, Number(draft.length) || 300)))
const canSubmit = computed(() => draft.draft_id && draft.name?.trim() && manuscript.value)
const llmLabel = computed(() => config.value?.llm?.model || config.value?.text?.model || 'LiteLLM 当前配置')
const imageModelLabel = computed(() => config.value?.image?.model || 'Agnes Image 2.1 Flash')
const ttsLabel = computed(() => draft.voice_name || config.value?.tts?.provider || '自动匹配')
const manuscriptPreview = computed(() => manuscript.value.replace(/\s+/g, ' ').slice(0, 92))
const segmentPlan = computed(() => {
  if (isThemeMode.value) {
    return [
      { title: `围绕主题扩写到约 ${targetLength.value} 字`, time: '扩写' },
      { title: '根据成稿拆分分镜、画面和配音', time: '生成' },
      { title: '进入预览页后逐段修改素材', time: '可编辑' },
    ]
  }
  const text = manuscript.value || '文稿内容'
  const chunks = text.split(/[。！？\n]/).map((item) => item.trim()).filter(Boolean).slice(0, 7)
  const titles = chunks.length ? chunks.map((item) => item.slice(0, 18)) : ['开场观点', '核心解释', '案例补充', '总结观点']
  return titles.map((title, index) => ({ title, time: `00:${String(15 + index).padStart(2, '0')}` }))
})
const missingApiItems = computed(() => {
  const cfg = config.value || {}
  const items = []
  if (!cfg.llm?.base_url || !cfg.llm?.model || !cfg.llm?.api_key) items.push('生文 API')
  if (!cfg.image?.api_url || !cfg.image?.model || !cfg.image?.api_key) items.push('生图 API')
  const tts = cfg.tts || {}
  if (tts.provider === 'mimo') {
    if (!tts.mimo?.base_url || !tts.mimo?.model || !tts.mimo?.api_key) items.push('小米 MiMo TTS')
  } else if (!tts.api_url || !tts.appid || !tts.token || !tts.cluster) {
    items.push('豆包 TTS')
  }
  return items
})
const llmReady = computed(() => Boolean(config.value?.llm?.base_url && config.value?.llm?.model && config.value?.llm?.api_key))
const imageReady = computed(() => Boolean(config.value?.image?.api_url && config.value?.image?.model && config.value?.image?.api_key))
const ttsReady = computed(() => {
  const tts = config.value?.tts || {}
  if (tts.provider === 'mimo') return Boolean(tts.mimo?.base_url && tts.mimo?.model && tts.mimo?.api_key)
  return Boolean(tts.api_url && tts.appid && tts.token && tts.cluster)
})
const apiReady = computed(() => Boolean(config.value) && missingApiItems.value.length === 0)
const apiMissingText = computed(() => {
  if (!config.value) return '未读取到配置，请确认后端服务在线。'
  return `缺少：${missingApiItems.value.join('、')}`
})

const checks = computed(() => [
  {
    label: '文稿已保存',
    desc: isThemeMode.value ? `主题 ${manuscriptLength.value} 字，扩写目标 ${targetLength.value} 字` : `${manuscriptLength.value} 字，预计 ${segmentCount.value} 段`,
    tone: 'ok',
    icon: CircleCheck,
  },
  {
    label: '本地资产保留',
    desc: '失败前已生成的分镜、图片和音频不会隐藏',
    tone: 'ok',
    icon: CircleCheck,
  },
  {
    label: '生文 API',
    desc: llmReady.value ? `${llmLabel.value} 已配置` : '缺少 Base URL、API Key 或模型名',
    tone: llmReady.value ? 'ok' : 'warn',
    icon: llmReady.value ? CircleCheck : Warning,
  },
  {
    label: '生图 API',
    desc: imageReady.value ? `${imageModelLabel.value} 已配置` : '缺少 API URL、API Key 或模型名',
    tone: imageReady.value ? 'ok' : 'warn',
    icon: imageReady.value ? CircleCheck : Warning,
  },
  {
    label: 'TTS API',
    desc: ttsReady.value ? `${ttsLabel.value} 已配置` : '缺少配音 provider 的必要配置',
    tone: ttsReady.value ? 'ok' : 'warn',
    icon: ttsReady.value ? CircleCheck : Warning,
  },
  {
    label: '生成策略',
    desc: '生图串行生成，遇到限速自动等待',
    tone: 'warn',
    icon: Warning,
  },
])

onMounted(async () => {
  if (!loadedDraft) {
    ElMessage.warning('未找到文稿草稿，请重新创建项目')
    router.replace('/')
    return
  }
  try {
    const [voiceList, runtimeConfig] = await Promise.all([getVoices(), getConfig()])
    voices.value = voiceList
    config.value = runtimeConfig
  } catch (error) {
    console.warn('读取配置失败', error)
  }
})

function persist() {
  Object.assign(draft, saveDraft({ ...draft }))
}

function setDraft(key, value) {
  draft[key] = value
  persist()
}

function onVoiceChange() {
  const selected = voices.value.find((voice) => voice.id === draft.voice_type)
  draft.voice_name = selected?.name || ''
  persist()
}

async function startProduction() {
  if (!canSubmit.value) {
    ElMessage.warning('请先补全项目名称和文稿')
    return
  }
  if (!apiReady.value) {
    ElMessage.warning('请先完成模型 API 配置')
    router.push('/settings')
    return
  }
  persist()
  submitting.value = true
  try {
    const inputMode = draft.input_mode === 'theme' ? 'theme' : 'script'
    const payload = {
      name: draft.name,
      theme: manuscript.value.slice(0, 5000),
      input_mode: inputMode,
      style: `${draft.text_style || '知识科普'}|${draft.visual_style || '吉卜力'}`,
      ratio: draft.ratio || '16:9',
      length: inputMode === 'theme' ? Math.max(0, Math.min(2000, Math.round(Number(draft.length || 0) / 50) * 50)) : 0,
      voice_type: draft.voice_type || null,
    }
    const result = await createTask(payload)
    updateDraft(draft.draft_id, { created_task_id: result.task_id })
    ElMessage.success('生产任务已提交')
    router.push(`/process/${result.task_id}`)
  } catch (error) {
    console.error('提交生产任务失败', error)
    ElMessage.error(error?.response?.data?.detail || '提交生产任务失败')
  } finally {
    submitting.value = false
  }
}

function handleNavigate(tab) {
  if (tab === 'settings') router.push('/settings')
  else if (tab === 'library') router.push('/assets')
  else router.push('/')
}
</script>

<style scoped>
.production-page {
  min-height: 100vh;
  padding-bottom: 76px;
}

.production-layout {
  min-height: calc(100vh - 136px);
  display: grid;
  grid-template-columns: 300px minmax(0, 1fr) 330px;
}

.summary-panel,
.readiness-panel,
.config-panel {
  padding: 24px;
  padding-bottom: 92px;
}

.summary-panel,
.readiness-panel {
  background: rgba(255, 255, 255, 0.76);
}

.summary-panel {
  border-right: 1px solid var(--color-border);
}

.readiness-panel {
  border-left: 1px solid var(--color-border);
}

.breadcrumb {
  margin-bottom: 24px;
  color: var(--color-text-tertiary);
  font-size: 13px;
}

.summary-panel h1 {
  font-size: 26px;
  line-height: 1.2;
  letter-spacing: -0.03em;
  margin-bottom: 12px;
}

.summary-panel p {
  color: var(--color-text-secondary);
}

.summary-card {
  display: grid;
  gap: 1px;
  margin: 22px 0;
  overflow: hidden;
  border: 1px solid var(--color-border);
  border-radius: 12px;
  background: var(--color-divider);
}

.summary-card div {
  display: flex;
  justify-content: space-between;
  padding: 12px 14px;
  background: #fff;
}

.summary-card span {
  color: var(--color-text-secondary);
}

.back-script {
  width: 100%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.config-entry {
  width: 100%;
  margin-top: 12px;
}

.api-warning {
  display: flex;
  gap: 10px;
  margin: -8px 0 16px;
  border: 1px solid #f0d99e;
  border-radius: 12px;
  background: var(--color-warning-bg);
  color: var(--color-warning);
  padding: 12px;
}

.api-warning svg {
  width: 20px;
  flex: 0 0 auto;
}

.api-warning div {
  display: grid;
  gap: 3px;
}

.api-warning span {
  color: var(--color-text-secondary);
  font-size: 13px;
}

.config-panel {
  min-width: 0;
  overflow: auto;
}

.section-head {
  margin-bottom: 18px;
}

.section-head p {
  color: var(--color-text-tertiary);
  font-size: 12px;
  font-weight: 800;
}

.section-head h2 {
  font-size: 22px;
}

.production-card {
  display: grid;
  gap: 14px;
  border: 1px solid var(--color-border);
  border-radius: 10px;
  background: #fff;
  padding: 16px 18px;
}

.line-label {
  color: var(--color-text-secondary);
  font-size: 13px;
  font-weight: 900;
}

.model-line,
.style-line {
  display: grid;
  gap: 9px;
  padding-bottom: 14px;
  border-bottom: 1px solid var(--color-divider);
}

.line-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.line-row button {
  border: 0;
  background: transparent;
  color: var(--color-primary);
  font-weight: 800;
  cursor: pointer;
}

.model-card {
  display: grid;
  grid-template-columns: 44px 1fr auto;
  align-items: center;
  gap: 14px;
  min-height: 54px;
  border: 1px solid var(--color-border);
  border-radius: 10px;
  background: #fff;
  padding: 8px 12px;
}

.model-avatar {
  width: 38px;
  height: 38px;
  border-radius: 10px;
  display: grid;
  place-items: center;
  background: #111827;
  color: #fff;
  font-weight: 900;
}

.model-card div:nth-child(2) {
  display: grid;
  gap: 3px;
}

.model-card em {
  margin-left: 8px;
  border-radius: 4px;
  background: var(--color-primary-bg);
  color: var(--color-primary);
  padding: 1px 5px;
  font-size: 12px;
  font-style: normal;
}

.model-card button {
  border: 0;
  background: transparent;
  color: var(--color-text-secondary);
  cursor: pointer;
  font-weight: 800;
}

.model-card span,
.config-row span,
.tts-row span,
.quota-card span {
  color: var(--color-text-secondary);
  font-size: 13px;
  font-weight: 800;
}

.style-grid {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 10px;
}

.style-grid button {
  display: grid;
  gap: 6px;
  padding: 6px;
  border: 1px solid var(--color-border);
  border-radius: 10px;
  background: #fff;
  cursor: pointer;
  color: var(--color-text-secondary);
  font-weight: 800;
}

.style-grid button.active {
  border-color: var(--color-primary);
  color: var(--color-primary);
  background: var(--color-primary-bg);
}

.style-grid img {
  width: 100%;
  aspect-ratio: 16 / 8;
  border-radius: 7px;
  object-fit: cover;
}

.config-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.config-row label,
.tts-row label {
  display: grid;
  gap: 7px;
  border: 1px solid var(--color-border);
  border-radius: 10px;
  background: #fff;
  padding: 10px 12px;
}

.config-row select,
.config-row input,
.tts-row select,
.tts-row input {
  width: 100%;
  min-height: 36px;
}

.tts-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  align-items: end;
  gap: 12px;
  padding-bottom: 14px;
  border-bottom: 1px solid var(--color-divider);
}

.ratio-segments {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}

.ratio-segments button {
  height: 36px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: #fff;
  color: var(--color-text-secondary);
  font-weight: 800;
  cursor: pointer;
}

.ratio-segments button.active {
  border-color: var(--color-primary);
  background: var(--color-primary-bg);
  color: var(--color-primary);
}

.segment-plan {
  margin-bottom: 16px;
}

.plan-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.plan-table {
  display: grid;
  overflow: hidden;
  border: 1px solid var(--color-border);
  border-radius: 10px;
}

.plan-row {
  min-height: 34px;
  display: grid;
  grid-template-columns: 42px 1fr 62px;
  align-items: center;
  gap: 8px;
  border-bottom: 1px solid var(--color-divider);
  background: #fff;
  padding: 0 10px;
  color: var(--color-text-secondary);
  font-size: 13px;
}

.plan-row:last-child {
  border-bottom: 0;
}

.plan-row.head {
  background: #f8fafc;
  color: var(--color-text-tertiary);
  font-weight: 900;
}

.asset-protection {
  display: flex;
  gap: 10px;
  margin-top: 12px;
  border: 1px solid #f0d99e;
  border-radius: 10px;
  background: var(--color-warning-bg);
  color: var(--color-warning);
  padding: 10px 12px;
}

.asset-protection svg {
  width: 20px;
  flex: 0 0 auto;
}

.asset-protection p {
  color: var(--color-text-secondary);
  font-size: 13px;
}

.config-row select {
  border: 1px solid var(--color-border);
  border-radius: 9px;
  padding: 0 10px;
  background: #fff;
}

.check-list {
  display: grid;
  gap: 0;
  overflow: hidden;
  border: 1px solid var(--color-border);
  border-radius: 10px;
  background: #fff;
}

.check-item {
  display: flex;
  gap: 12px;
  border: 0;
  border-bottom: 1px solid var(--color-divider);
  border-radius: 0;
  background: #fff;
  padding: 12px 14px;
}

.check-item:last-child {
  border-bottom: 0;
}

.check-item svg {
  width: 20px;
  flex: 0 0 auto;
}

.check-item.ok svg {
  color: var(--color-success);
}

.check-item.warn svg {
  color: var(--color-warning);
}

.check-item div {
  display: grid;
  gap: 4px;
}

.check-item span {
  color: var(--color-text-secondary);
  font-size: 13px;
}

.quota-card {
  margin-top: 18px;
  border: 1px solid var(--color-border);
  border-radius: 10px;
  background: #fff;
  padding: 16px;
}

.quota-card strong {
  display: block;
  margin: 6px 0;
  font-size: 22px;
}

.quota-track {
  height: 5px;
  border-radius: 999px;
  background: #e6eaf0;
  overflow: hidden;
  margin: 12px 0 4px;
}

.quota-track span {
  display: block;
  height: 100%;
  background: var(--color-primary);
}

.quota-percent {
  text-align: right;
  color: var(--color-primary);
  font-weight: 800;
  font-size: 13px;
}

.quota-lines {
  display: grid;
  gap: 10px;
  margin-top: 16px;
  border-top: 1px solid #f0d99e;
  padding-top: 12px;
}

.quota-lines div {
  display: flex;
  justify-content: space-between;
}

.quota-lines strong {
  margin: 0;
  font-size: 14px;
}

.quota-card p {
  color: var(--color-text-secondary);
}

.sticky-actions {
  position: fixed;
  left: 28px;
  right: 28px;
  bottom: 12px;
  z-index: 30;
  height: 58px;
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 14px;
  padding: 0 18px;
  border: 1px solid var(--color-border);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(18px);
  box-shadow: var(--shadow-md);
}

.sticky-actions button {
  min-width: 150px;
  padding: 0 20px;
}

@media (max-width: 1240px) {
  .production-layout {
    grid-template-columns: 280px minmax(0, 1fr);
  }

  .readiness-panel {
    display: none;
  }
}
</style>
