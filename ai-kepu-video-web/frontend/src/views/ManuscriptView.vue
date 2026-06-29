<template>
  <div class="manuscript-page">
    <NavBar active-tab="home" @navigate="handleNavigate" />

    <main class="manuscript-layout">
      <aside class="setup-panel">
        <div class="panel-head">
          <Operation />
          <div>
            <p>项目设置</p>
            <h2>文稿准备</h2>
          </div>
        </div>

        <label class="form-field">
          <span>项目名称</span>
          <input v-model="draft.name" maxlength="100" placeholder="给这条视频起个名字" @input="scheduleSave" />
          <small>{{ draft.name.length }}/100</small>
        </label>

        <section class="mode-block">
          <span>创作方式</span>
          <div class="mode-switch">
            <button type="button" :class="{ active: draft.input_mode === 'theme' }" @click="switchInputMode('theme')">
              主题模式
            </button>
            <button type="button" :class="{ active: draft.input_mode !== 'theme' }" @click="switchInputMode('script')">
              输入模式
            </button>
          </div>
          <p>{{ draft.input_mode === 'theme' ? '输入一句主题，由模型扩写成完整视频文稿。' : '直接使用你输入或导入的完整文稿生产视频。' }}</p>
        </section>

        <section v-if="draft.input_mode === 'theme'" class="script-length-block">
          <div class="knob-row">
            <label>扩写字数</label>
            <div class="knob-group">
              <div
                class="knob-dial"
                @mousedown="startKnobRotate"
                @touchstart="startKnobRotate"
              >
                <svg viewBox="0 0 56 56" class="knob-circle">
                  <defs>
                    <linearGradient id="manuscriptKnobGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                      <stop offset="0%" stop-color="#0f62fe" />
                      <stop offset="100%" stop-color="#22c1c3" />
                    </linearGradient>
                  </defs>
                  <circle cx="28" cy="28" r="24" class="knob-track" />
                  <circle
                    cx="28"
                    cy="28"
                    r="24"
                    class="knob-fill"
                    :style="{ strokeDashoffset: knobStrokeDashOffset }"
                  />
                </svg>
                <div class="knob-display">
                  <span class="knob-num">{{ draft.length === 0 ? '自动' : draft.length }}</span>
                </div>
                <div class="knob-marker" :style="{ transform: `rotate(${knobAngle}deg)` }"></div>
              </div>
              <input
                class="knob-field"
                :value="lengthInputFocused ? lengthDisplay : lengthLabel"
                inputmode="numeric"
                placeholder="自动"
                @focus="onLengthFocus"
                @blur="onLengthBlur"
                @input="onLengthInput"
              />
            </div>
          </div>
          <small>0 为自动，手动范围 50-2000 字。</small>
        </section>

        <section v-if="draft.input_mode !== 'theme'" class="source-block">
          <span>内容来源</span>
          <div class="source-actions">
            <button type="button" class="surface-button primary-source" @click="insertExampleManuscript">
              <MagicStick />
              插入示例文稿
            </button>
            <button type="button" class="surface-button" @click="triggerDocumentImport">
              <Upload />
              导入文档
            </button>
          </div>
          <small>支持 TXT、Markdown、Word DOCX、PDF</small>
          <input
            ref="documentInput"
            type="file"
            accept=".txt,.md,.markdown,.docx,.pdf,text/plain,text/markdown,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/pdf"
            hidden
            @change="onDocumentSelected"
          />
        </section>

        <div v-if="draft.input_mode !== 'theme'" class="source-actions">
          <button type="button" class="surface-button" @click="pasteFromClipboard">粘贴文本</button>
          <button type="button" class="surface-button" @click="clearManuscript">清空文稿</button>
        </div>

        <label class="form-field">
          <span>受众人群</span>
          <select v-model="audience">
            <option>大众通用</option>
            <option>知识创作者</option>
            <option>短视频观众</option>
            <option>专业学习者</option>
          </select>
        </label>

        <div v-if="showContentMetrics" class="metrics">
          <div>
            <span>预计时长</span>
            <strong>{{ durationLabel }}</strong>
          </div>
          <div>
            <span>分镜预估</span>
            <strong>{{ segmentCount }} 段</strong>
          </div>
          <div>
            <span>正文字符</span>
            <strong>{{ manuscriptLength }}</strong>
          </div>
        </div>

        <div v-else class="theme-pending-card">
          <span>扩写目标</span>
          <strong>{{ targetLengthLabel }}</strong>
          <p>主题模式会在提交生产后先扩写成完整文稿，再按成稿拆分分镜和计算时长。</p>
        </div>

        <div class="tip-card">
          <span>小贴士</span>
          <p>文稿页只处理内容准备。项目预览、素材恢复和导出结果统一进入项目资产页查看。</p>
        </div>
      </aside>

      <section class="editor-panel">
        <div class="editor-top">
          <div>
            <p>{{ editorEyebrow }}</p>
            <h1>{{ editorLabel }}</h1>
          </div>
          <span :class="['save-state', saveState]">
            <CircleCheck v-if="saveState === 'saved'" />
            <Loading v-else />
            {{ saveText }}
          </span>
        </div>

        <div class="paper-shell" :class="{ empty: showEmptyPrompt }">
          <textarea
            ref="paperEditor"
            v-model="editorValue"
            class="paper-editor"
            :maxlength="editorMaxLength"
            :placeholder="paperPlaceholder"
            @focus="paperFocused = true"
            @blur="paperFocused = false"
            @input="scheduleSave"
          ></textarea>
          <button v-if="showEmptyPrompt" type="button" class="value-rotator" @click="focusPaper">
            <div class="rotator-placeholder">{{ emptyHint }}</div>
            <div class="rotator-stage">
              <div
                v-if="currentRotatorItem.slot"
                :key="`slot-${rotatorIndex}`"
                class="slot-group anim-slot"
              >
                <div v-for="(word, idx) in slotWords" :key="word" class="slot-item">
                  <span class="slot-word" :style="{ animationDelay: `${idx * 150}ms` }">{{ word }}</span>
                </div>
              </div>
              <div
                v-else-if="currentRotatorItem.finale"
                :key="`finale-${rotatorIndex}`"
                class="rotator-text text-finale anim-finale"
              >
                All in one <span>但不</span>是画布
              </div>
              <div
                v-else
                :key="`text-${rotatorIndex}`"
                class="rotator-text"
                :class="[currentRotatorItem.class, currentRotatorItem.anim]"
              >
                {{ currentRotatorItem.text }}
              </div>
            </div>
          </button>
          <div class="paper-footer">
            <span>{{ draft.input_mode === 'theme' ? '主题字数' : '字数' }}：{{ manuscriptLength }}</span>
            <span>自动保存到本地草稿</span>
          </div>
        </div>
      </section>

      <aside class="generation-panel">
        <div class="panel-head">
          <Operation />
          <div>
            <p>生产设置</p>
            <h2>画面与配音</h2>
          </div>
        </div>

        <section class="side-config-card">
          <div class="config-section">
            <span>画面风格</span>
            <div class="mini-style-grid">
              <button
                v-for="style in visualStyles"
                :key="style.value"
                type="button"
                :class="{ active: draft.visual_style === style.value }"
                @click="setDraft('visual_style', style.value)"
              >
                <img :src="style.image" :alt="style.label" />
                <em>{{ style.label }}</em>
              </button>
            </div>
          </div>

          <div class="config-section">
            <span>视频比例</span>
            <div class="mini-ratio-group">
              <button
                v-for="ratio in ratioOptions"
                :key="ratio"
                type="button"
                :class="{ active: draft.ratio === ratio }"
                @click="setDraft('ratio', ratio)"
              >
                {{ ratio }}
              </button>
            </div>
          </div>

          <label class="side-field">
            <span>创作风格</span>
            <select v-model="draft.text_style" @change="persist">
              <option v-for="style in textStyles" :key="style" :value="style">{{ style }}</option>
            </select>
          </label>

          <label class="side-field">
            <span>配音音色</span>
            <select v-model="draft.voice_type" @change="onVoiceChange">
              <option value="">自动匹配</option>
              <option v-for="voice in voices" :key="voice.id" :value="voice.id">{{ voice.name }}</option>
            </select>
          </label>
        </section>

        <div class="side-actions">
          <button type="button" class="primary-action next-btn" :disabled="!canContinue" @click="goProduction">
            {{ nextButtonText }}
          </button>
        </div>
      </aside>
    </main>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  CircleCheck,
  Loading,
  MagicStick,
  Operation,
  Upload,
} from '@element-plus/icons-vue'
import NavBar from '../components/NavBar.vue'
import { extractDocumentText, getVoices } from '../api/task'
import {
  createDraft,
  estimateDuration,
  estimateSegments,
  getDraft,
  ratioOptions,
  saveDraft,
  textStyles,
  visualStyles,
} from '../utils/projectDrafts'

const route = useRoute()
const router = useRouter()
const saveState = ref('saved')
const audience = ref('大众通用')
const savedAtLabel = ref(new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }))
const documentInput = ref(null)
const paperEditor = ref(null)
const paperFocused = ref(false)
const voices = ref([])
const rotatorIndex = ref(0)
const lengthDisplay = ref('')
const lengthInputFocused = ref(false)
const knobDragging = ref(false)
const knobStartValue = ref(0)
const knobCenterX = ref(0)
const knobCenterY = ref(0)
let saveTimer = null
let promptTimer = null

const defaultManuscript = `1  大脑如何影响我们的决策？\n\n你是否有过这样的经历：明明知道不应该买，却在情绪低落时下单了很多东西？或者明明想要好好休息，却因为一时愤怒做了后悔的决定？\n\n这并不是你不够理智，而是情绪正在悄悄影响着你的大脑。\n\n2  情绪与大脑的关系\n\n研究表明，情绪会影响我们大脑中负责决策的区域，改变我们对风险和收益的判断。\n\n例如，在压力状态下，我们的大脑更倾向于选择“即时缓解”的方案，而忽略了长期后果。\n\n3  如何做出更好的决策？\n\n• 觉察情绪：识别当下的情绪状态。\n• 暂停片刻：给自己几秒钟，避免冲动反应。\n• 理性评估：列出选项的长期收益与风险。\n• 复盘反思：从过去的决策中学习，形成更清晰的判断。`
const firstDraft = route.params.draftId
  ? getDraft(route.params.draftId)
  : createDraft({
      visual_style: '吉卜力',
      text_style: '知识科普',
    })
const loadedDraft = firstDraft || createDraft()
const draft = reactive({ ...loadedDraft })
if (!draft.input_mode) draft.input_mode = 'script'
if (!Number.isFinite(Number(draft.length))) draft.length = 300
const rotatorItems = [
  { text: '文稿变成视频', class: 'text-bloom', anim: 'anim-bloom' },
  { text: '导入剪映草稿', class: 'text-push', anim: 'anim-push' },
  { text: '素材自由修改', class: 'text-breathe', anim: 'anim-breathe' },
  { slot: true },
  { finale: true },
]
const slotWords = ['文稿', '分镜', '成片', '剪映']
const rotatorDurations = [3200, 3000, 3500, 5000, 2900]

const currentText = computed(() => draft.input_mode === 'theme' ? draft.theme : draft.manuscript)
const manuscriptLength = computed(() => currentText.value.replace(/\s+/g, '').length)
const durationLabel = computed(() => estimateDuration(currentText.value, draft.voice_speed))
const segmentCount = computed(() => estimateSegments(currentText.value))
const showContentMetrics = computed(() => draft.input_mode !== 'theme')
const targetLength = computed(() => Number(draft.length) === 0 ? 300 : Math.max(50, Math.min(2000, Number(draft.length) || 300)))
const targetLengthLabel = computed(() => `${targetLength.value} 字`)
const hasCurrentText = computed(() => Boolean(currentText.value.trim()))
const canContinue = computed(() => {
  if (draft.input_mode !== 'theme' && !hasCurrentText.value) return true
  return Boolean(draft.name.trim() && hasCurrentText.value)
})
const saveText = computed(() => saveState.value === 'saved' ? '已自动保存' : '保存中...')
const paperPlaceholder = computed(() => {
  if (!paperFocused.value) return ''
  return draft.input_mode === 'theme'
    ? '输入 100 字以内的视频主题，例如：为什么普通人越来越需要 AI 助手'
    : '直接输入或粘贴完整文稿'
})
const currentRotatorItem = computed(() => rotatorItems[rotatorIndex.value] || rotatorItems[0])
const showEmptyPrompt = computed(() => !hasCurrentText.value && !paperFocused.value)
const nextButtonText = computed(() => {
  if (draft.input_mode !== 'theme' && !hasCurrentText.value) return '插入示例文稿'
  return '继续配置画面与配音'
})
const editorValue = computed({
  get: () => currentText.value,
  set: (value) => {
    if (draft.input_mode === 'theme') draft.theme = String(value || '').slice(0, 100)
    else draft.manuscript = String(value || '').slice(0, 5000)
  },
})
const editorMaxLength = computed(() => draft.input_mode === 'theme' ? 100 : 5000)
const editorLabel = computed(() => draft.input_mode === 'theme' ? '主题输入' : '文稿编辑')
const editorEyebrow = computed(() => draft.input_mode === 'theme' ? '主题模式' : '脚本画布')
const emptyHint = computed(() => draft.input_mode === 'theme' ? '输入 100 字以内主题...' : '在这里输入或粘贴完整文稿...')
const lengthLabel = computed(() => Number(draft.length) === 0 ? '自动' : String(draft.length || 300))
const knobAngle = computed(() => {
  const value = Math.max(0, Math.min(2000, Number(draft.length) || 0))
  return (value / 2000) * 360
})
const knobStrokeDashOffset = computed(() => {
  const circumference = 2 * Math.PI * 24
  const value = Math.max(0, Math.min(2000, Number(draft.length) || 0))
  return circumference * (1 - value / 2000)
})

onMounted(async () => {
  if (!route.params.draftId) router.replace(`/manuscript/${draft.draft_id}`)
  try {
    voices.value = await getVoices()
  } catch (error) {
    voices.value = []
  }
  startRotator()
})

onBeforeUnmount(() => {
  clearTimeout(saveTimer)
  if (promptTimer) window.clearTimeout(promptTimer)
  persist()
})

function scheduleSave() {
  saveState.value = 'saving'
  clearTimeout(saveTimer)
  saveTimer = setTimeout(persist, 320)
}

function persist() {
  Object.assign(draft, saveDraft({ ...draft }))
  savedAtLabel.value = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  saveState.value = 'saved'
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

function switchInputMode(mode) {
  draft.input_mode = mode === 'theme' ? 'theme' : 'script'
  if (draft.input_mode === 'theme' && draft.theme.length > 100) {
    draft.theme = draft.theme.slice(0, 100)
    ElMessage.warning('主题模式最多输入 100 字，已自动截断')
  }
  paperFocused.value = false
  scheduleSave()
}

function focusPaper() {
  paperFocused.value = true
  paperEditor.value?.focus()
}

function startRotator() {
  if (promptTimer) window.clearTimeout(promptTimer)
  promptTimer = window.setTimeout(() => {
    rotatorIndex.value = (rotatorIndex.value + 1) % rotatorItems.length
    startRotator()
  }, rotatorDurations[rotatorIndex.value] || 3200)
}

function normalizeLength() {
  const value = Number(draft.length)
  if (Number.isNaN(value)) {
    draft.length = 300
    return
  }
  if (value < 0) draft.length = 0
  else if (value > 2000) draft.length = 2000
  else draft.length = Math.round(value / 50) * 50
}

function onLengthFocus() {
  lengthInputFocused.value = true
  lengthDisplay.value = Number(draft.length) === 0 ? '' : String(draft.length || 300)
}

function onLengthBlur() {
  lengthInputFocused.value = false
  const value = lengthDisplay.value.trim()
  if (value === '' || value === '自动') {
    draft.length = 0
  } else {
    const num = Number(value)
    if (!Number.isNaN(num)) draft.length = Math.max(0, Math.min(2000, Math.round(num / 50) * 50))
  }
  lengthDisplay.value = ''
  scheduleSave()
}

function onLengthInput(event) {
  const value = event.target.value
  if (value === '' || value === '自动') {
    lengthDisplay.value = value
    return
  }
  const num = Number(value)
  if (!Number.isNaN(num) && num >= 0 && num <= 2000) lengthDisplay.value = value
}

function startKnobRotate(event) {
  event.preventDefault()
  const knobEl = event.currentTarget
  const rect = knobEl.getBoundingClientRect()
  knobCenterX.value = rect.left + rect.width / 2
  knobCenterY.value = rect.top + rect.height / 2
  const clientX = event.type === 'mousedown' ? event.clientX : event.touches[0].clientX
  const clientY = event.type === 'mousedown' ? event.clientY : event.touches[0].clientY
  let lastAngle = Math.atan2(clientY - knobCenterY.value, clientX - knobCenterX.value) * (180 / Math.PI)
  let accumulatedRotation = 0
  knobStartValue.value = Number(draft.length) || 0
  knobDragging.value = true

  const moveHandler = (moveEvent) => {
    if (!knobDragging.value) return
    const currentX = moveEvent.type === 'mousemove' ? moveEvent.clientX : moveEvent.touches[0].clientX
    const currentY = moveEvent.type === 'mousemove' ? moveEvent.clientY : moveEvent.touches[0].clientY
    const currentAngle = Math.atan2(currentY - knobCenterY.value, currentX - knobCenterX.value) * (180 / Math.PI)
    let deltaAngle = currentAngle - lastAngle
    if (deltaAngle > 180) deltaAngle -= 360
    if (deltaAngle < -180) deltaAngle += 360
    accumulatedRotation += deltaAngle
    lastAngle = currentAngle
    const deltaValue = (accumulatedRotation / 360) * 2000
    draft.length = Math.max(0, Math.min(2000, Math.round((knobStartValue.value + deltaValue) / 50) * 50))
  }

  const endHandler = () => {
    knobDragging.value = false
    scheduleSave()
    document.removeEventListener('mousemove', moveHandler)
    document.removeEventListener('mouseup', endHandler)
    document.removeEventListener('touchmove', moveHandler)
    document.removeEventListener('touchend', endHandler)
  }

  document.addEventListener('mousemove', moveHandler)
  document.addEventListener('mouseup', endHandler)
  document.addEventListener('touchmove', moveHandler, { passive: false })
  document.addEventListener('touchend', endHandler)
}

function insertExampleManuscript() {
  draft.input_mode = 'script'
  const direction = draft.name || draft.manuscript.slice(0, 28) || '普通人为什么越来越需要 AI 助手'
  draft.manuscript = `1  ${direction}\n\n很多时候，我们以为自己缺的是灵感，其实缺的是把想法变成作品的完整路径。\n\n当一个观点停留在脑子里，它只是一个念头；当它被写成脚本、拆成分镜、配上画面和声音，它才真正具备传播的可能。\n\n2  问题不是不会表达，而是生产链太长\n\n一条知识视频背后，通常要经历选题、文稿、分镜、画面、配音、字幕和导出。每一步都不难，但叠在一起，就会把创作热情消耗掉。\n\n3  更好的工具应该保存过程\n\n真正可靠的一键成片，不应该只是给你一个最终视频。它应该保存每段文稿、每张图片、每段配音和每次修改，让创作者能继续判断、替换和打磨。\n\n理解这一点，我们就能把注意力重新放回内容本身：观点是否清楚，故事是否成立，表达是否值得被看见。`
  if (!draft.name) draft.name = direction.slice(0, 32)
  scheduleSave()
  ElMessage.success('已插入一版可编辑示例文稿')
}

async function pasteFromClipboard() {
  try {
    const text = await navigator.clipboard?.readText?.()
    if (!text) {
      ElMessage.info('剪贴板暂无可粘贴文本')
      return
    }
    draft.input_mode = 'script'
    draft.manuscript = text.slice(0, 5000)
    if (!draft.name) draft.name = draft.manuscript.slice(0, 24)
    scheduleSave()
    ElMessage.success('已粘贴到文稿画布')
  } catch (error) {
    ElMessage.warning('浏览器未授权读取剪贴板')
  }
}

function clearManuscript() {
  if (draft.input_mode === 'theme') draft.theme = ''
  else draft.manuscript = ''
  scheduleSave()
}

function triggerDocumentImport() {
  documentInput.value?.click()
}

async function onDocumentSelected(event) {
  const file = event.target.files?.[0]
  if (!file) return
  try {
    const result = await extractDocumentText(file)
    const text = result.text || ''
    if (!text.trim()) {
      ElMessage.warning('未能从文档中提取到可用文字')
      return
    }
    const truncated = text.length > 5000
    draft.input_mode = 'script'
    draft.manuscript = text.slice(0, 5000)
    if (!draft.name.trim()) draft.name = file.name.replace(/\.(txt|md|markdown|docx|pdf)$/i, '').slice(0, 100)
    scheduleSave()
    ElMessage.success(truncated ? '文档已导入，已截取前 5000 字' : '文档已导入文稿画布')
  } catch (error) {
    const message = error?.response?.data?.detail || '导入文档失败，请使用 TXT、Markdown、DOCX 或 PDF'
    ElMessage.error(message)
  } finally {
    event.target.value = ''
  }
}

function goProduction() {
  if (draft.input_mode !== 'theme' && !hasCurrentText.value) {
    insertExampleManuscript()
    return
  }
  if (!draft.name.trim()) {
    ElMessage.warning('请先填写项目名称')
    return
  }
  if (!hasCurrentText.value) {
    ElMessage.warning(draft.input_mode === 'theme' ? '请先输入视频主题' : '请先输入文稿内容')
    return
  }
  if (draft.input_mode === 'theme') normalizeLength()
  persist()
  router.push(`/production/${draft.draft_id}`)
}

function handleNavigate(tab) {
  if (tab === 'settings') router.push('/settings')
  else if (tab === 'library') router.push('/assets')
  else router.push('/')
}
</script>

<style scoped>
.manuscript-page {
  min-height: 100vh;
}

.manuscript-layout {
  height: calc(100vh - 64px);
  min-height: 720px;
  display: grid;
  grid-template-columns: 300px minmax(560px, 1fr) 300px;
}

.setup-panel,
.generation-panel {
  overflow: auto;
  padding: 26px 22px 96px;
  background: rgba(255, 255, 255, 0.74);
  scrollbar-width: thin;
  scrollbar-color: rgba(148, 163, 184, 0.22) transparent;
}

.setup-panel::-webkit-scrollbar,
.generation-panel::-webkit-scrollbar {
  width: 4px;
}

.setup-panel::-webkit-scrollbar-track,
.generation-panel::-webkit-scrollbar-track {
  background: transparent;
}

.setup-panel::-webkit-scrollbar-thumb,
.generation-panel::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.2);
}

.setup-panel {
  border-right: 1px solid rgba(229, 232, 237, 0.24);
}

.generation-panel {
  border-left: 1px solid rgba(229, 232, 237, 0.24);
}

.panel-head {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
}

.panel-head > svg {
  width: 20px;
  height: 20px;
  color: var(--color-primary);
}

.panel-head p,
.editor-top p {
  color: var(--color-text-tertiary);
  font-size: 12px;
  font-weight: 800;
  text-transform: uppercase;
}

.panel-head h2,
.editor-top h1 {
  font-size: 19px;
}

.form-field {
  display: grid;
  gap: 7px;
  margin-bottom: 16px;
}

.source-block {
  display: grid;
  gap: 8px;
  margin-bottom: 16px;
}

.source-block > span {
  color: var(--color-text-secondary);
  font-weight: 800;
}

.source-block small {
  color: var(--color-text-tertiary);
  font-size: 12px;
  line-height: 1.4;
}

.mode-block {
  display: grid;
  gap: 10px;
  margin-bottom: 22px;
}

.mode-block > span {
  color: var(--color-text-secondary);
  font-weight: 800;
}

.mode-block p {
  color: var(--color-text-tertiary);
  font-size: 13px;
}

.mode-switch {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.mode-switch button {
  height: 42px;
  border: 1px solid var(--color-border);
  border-radius: 10px;
  background: #fff;
  color: var(--color-text-secondary);
  font-weight: 800;
  cursor: pointer;
}

.mode-switch button.active {
  border-color: var(--color-primary);
  background: var(--color-primary-bg);
  color: var(--color-primary);
}

.script-length-block {
  display: grid;
  gap: 10px;
  margin-bottom: 18px;
  border: 1px solid rgba(229, 232, 237, 0.82);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.84);
  padding: 14px;
}

.script-length-block small {
  color: var(--color-text-tertiary);
  font-size: 12px;
}

.knob-row {
  display: grid;
  gap: 12px;
}

.knob-row > label {
  color: var(--color-text-secondary);
  font-weight: 800;
}

.knob-group {
  display: flex;
  align-items: center;
  gap: 12px;
}

.knob-dial {
  position: relative;
  width: 56px;
  height: 56px;
  flex: 0 0 auto;
  cursor: ns-resize;
  user-select: none;
}

.knob-circle {
  width: 100%;
  height: 100%;
  transform: rotate(-90deg);
}

.knob-track {
  fill: none;
  stroke: rgba(226, 232, 240, 0.92);
  stroke-width: 4;
  stroke-linecap: round;
}

.knob-fill {
  fill: none;
  stroke: url(#manuscriptKnobGrad);
  stroke-width: 4;
  stroke-linecap: round;
  stroke-dasharray: 150.8;
  transition: stroke-dashoffset 0.12s var(--ease-out);
}

.knob-display {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  pointer-events: none;
}

.knob-num {
  color: var(--color-text-primary);
  font-size: 14px;
  font-weight: 900;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

.knob-marker {
  position: absolute;
  top: 5px;
  left: 50%;
  width: 2px;
  height: 10px;
  margin-left: -1px;
  border-radius: 999px;
  background: linear-gradient(180deg, #0f62fe, #22c1c3);
  transform-origin: 50% 23px;
  transition: transform 0.12s var(--ease-out);
}

.knob-field {
  min-width: 0;
  flex: 1;
  height: 40px;
  border: 1px solid var(--color-border);
  border-radius: 10px;
  background: #fff;
  color: var(--color-text-primary);
  text-align: center;
  font-weight: 900;
  outline: 0;
  font-variant-numeric: tabular-nums;
}

.knob-field:focus {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px rgba(15, 98, 254, 0.08);
}

.form-field span,
.section-label {
  color: var(--color-text-secondary);
  font-weight: 800;
}

.form-field small {
  justify-self: end;
  color: var(--color-text-tertiary);
}

.form-field input,
.form-field textarea,
.form-field select {
  width: 100%;
  border: 1px solid var(--color-border);
  border-radius: 10px;
  background: #fff;
  outline: none;
}

.form-field input,
.form-field select {
  height: 40px;
  padding: 0 12px;
}

.form-field textarea {
  min-height: 138px;
  resize: vertical;
  padding: 12px;
}

.form-field.compact {
  margin-top: 20px;
}

.source-actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-bottom: 14px;
}

.source-actions button,
.side-actions button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.source-actions svg,
.side-actions svg {
  width: 16px;
  height: 16px;
}

.primary-source {
  color: var(--color-primary);
  border-color: var(--color-primary);
  background: var(--color-primary-bg);
  font-weight: 800;
}

.metrics {
  display: grid;
  gap: 1px;
  margin-top: 18px;
  overflow: hidden;
  border: 1px solid var(--color-border);
  border-radius: 12px;
  background: var(--color-divider);
}

.tip-card {
  display: grid;
  gap: 8px;
  margin-top: 16px;
  border: 1px solid #ead8b6;
  border-radius: 12px;
  background: #fffaf0;
  padding: 12px 14px;
}

.tip-card span {
  color: var(--color-warning);
  font-weight: 900;
}

.tip-card p {
  color: var(--color-text-secondary);
  font-size: 13px;
}

.metrics div {
  display: flex;
  justify-content: space-between;
  background: #fff;
  padding: 10px 14px;
}

.metrics span {
  color: var(--color-text-secondary);
}

.theme-pending-card {
  display: grid;
  gap: 7px;
  margin-top: 18px;
  border: 1px solid rgba(15, 98, 254, 0.16);
  border-radius: 12px;
  background: linear-gradient(135deg, rgba(15, 98, 254, 0.06), rgba(34, 193, 195, 0.06));
  padding: 13px 14px;
}

.theme-pending-card span {
  color: var(--color-text-secondary);
  font-weight: 800;
}

.theme-pending-card strong {
  color: var(--color-primary);
  font-size: 20px;
}

.theme-pending-card p {
  color: var(--color-text-tertiary);
  font-size: 12px;
  line-height: 1.5;
}

.editor-panel {
  min-width: 0;
  overflow: auto;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  padding: 22px 24px 28px;
}

.editor-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}

.editor-top h1 {
  font-size: 21px;
  letter-spacing: 0;
}

.save-state {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  color: var(--color-success);
  font-weight: 800;
}

.save-state svg {
  width: 16px;
  height: 16px;
}

.save-state.saving {
  color: var(--color-warning);
}

.paper-shell {
  position: relative;
  min-height: 0;
  height: 100%;
  display: grid;
  grid-template-rows: 1fr auto;
  border: 1px solid rgba(218, 223, 230, 0.86);
  border-radius: 10px;
  background: #fff;
  box-shadow: 0 14px 40px rgba(17, 24, 39, 0.045);
  transition: border-color 0.22s var(--ease-out), box-shadow 0.22s var(--ease-out);
}

.paper-shell.empty {
  border-color: rgba(15, 98, 254, 0.18);
  box-shadow: 0 18px 54px rgba(15, 98, 254, 0.06);
}

.paper-editor {
  width: 100%;
  min-height: 0;
  height: 100%;
  border: 0;
  outline: 0;
  resize: none;
  padding: 36px 58px 28px;
  background: transparent;
  color: #25211c;
  font-family: var(--font-serif);
  font-size: 17px;
  line-height: 1.55;
  white-space: pre-wrap;
}

.value-rotator {
  position: absolute;
  inset: 0;
  z-index: 5;
  display: grid;
  grid-template-rows: auto 1fr;
  align-items: center;
  justify-items: center;
  padding: 36px 44px 68px;
  border: 0;
  background: transparent;
  cursor: text;
  text-align: center;
  overflow: hidden;
  animation: hint-rise 0.5s var(--ease-out);
}

.rotator-placeholder {
  justify-self: start;
  align-self: start;
  color: var(--color-text-tertiary);
  font-family: var(--font-serif);
  font-size: 18px;
  line-height: 1.5;
  opacity: 0.52;
}

.rotator-stage {
  position: relative;
  width: min(100%, 720px);
  height: 220px;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  -webkit-mask-image: linear-gradient(to bottom, transparent 0%, #000 24%, #000 76%, transparent 100%);
  mask-image: linear-gradient(to bottom, transparent 0%, #000 24%, #000 76%, transparent 100%);
}

.rotator-text {
  position: absolute;
  max-width: 100%;
  white-space: nowrap;
  font-family: var(--font-sans);
  font-size: clamp(38px, 5vw, 68px);
  font-weight: 950;
  line-height: 1.08;
  letter-spacing: 0;
}

.text-bloom {
  background: linear-gradient(90deg, #111827 0%, #0f62fe 46%, #18a0a6 100%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}

.anim-bloom {
  animation: bloomIn 1.15s cubic-bezier(0.4, 0, 0.2, 1) forwards, bloomOut 0.55s cubic-bezier(0.4, 0, 0.2, 1) 2.65s forwards;
}

.text-push {
  background: linear-gradient(135deg, #121826 0%, #1b6cff 50%, #0f9f7a 100%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}

.anim-push {
  animation: pushIn 0.8s cubic-bezier(0.33, 1, 0.68, 1) forwards, pushOut 0.6s cubic-bezier(0.4, 0, 0.2, 1) 2.4s forwards;
}

.text-breathe {
  background: linear-gradient(90deg, #0f62fe, #0f9f7a, #f97316, #0f62fe);
  background-size: 220% auto;
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  animation: shimmer 3s linear infinite, breatheIn 2.2s ease-out forwards, breatheOut 0.8s ease-out 2.2s forwards;
}

.slot-group {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  align-items: center;
  justify-content: center;
}

.slot-item {
  height: 58px;
  min-width: 96px;
  padding: 0 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  border: 1px solid rgba(207, 216, 228, 0.92);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.86);
  box-shadow: inset 0 1px 2px rgba(17, 24, 39, 0.05), 0 14px 36px rgba(17, 24, 39, 0.07);
}

.slot-word {
  opacity: 0;
  color: #172033;
  font-size: 30px;
  font-weight: 900;
  letter-spacing: 0;
  animation: wordSlideUp 0.8s cubic-bezier(0.4, 0, 0.2, 1) forwards;
}

.anim-slot {
  animation: slotIn 0.6s cubic-bezier(0.4, 0, 0.2, 1) forwards, slotOut 0.8s cubic-bezier(0.4, 0, 0.2, 1) 2.5s forwards;
}

.text-finale {
  color: #172033;
}

.text-finale span {
  color: #0f62fe;
}

.anim-finale {
  animation: finaleIn 1.5s cubic-bezier(0.4, 0, 0.2, 1) forwards, finaleOut 0.6s cubic-bezier(0.4, 0, 0.2, 1) 2.5s forwards;
}

.paper-footer {
  display: flex;
  justify-content: space-between;
  border-top: 1px solid var(--color-divider);
  padding: 11px 18px;
  color: var(--color-text-tertiary);
  font-size: 13px;
}

@keyframes hint-rise {
  from {
    opacity: 0;
    transform: translateY(5px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes bloomIn {
  from { transform: scale(0.82); opacity: 0; filter: blur(20px); }
  to { transform: scale(1); opacity: 1; filter: blur(0); }
}

@keyframes bloomOut {
  to { transform: translateX(-150px); opacity: 0; filter: blur(10px); }
}

@keyframes pushIn {
  from { transform: translateX(200px); opacity: 0; filter: blur(10px); }
  to { transform: translateX(0); opacity: 1; filter: blur(0); }
}

@keyframes pushOut {
  to { transform: translateY(60px) scale(0.9); opacity: 0; filter: blur(15px); }
}

@keyframes breatheIn {
  from { transform: translateY(-60px) scale(0.9); opacity: 0; }
  to { transform: translateY(0) scale(1.05); opacity: 1; }
}

@keyframes breatheOut {
  to { transform: translateY(-60px) scale(0.9); opacity: 0; filter: blur(10px); }
}

@keyframes shimmer {
  to { background-position: 220% center; }
}

@keyframes slotIn {
  from { transform: translateY(30px); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
}

@keyframes slotOut {
  to { transform: scale(0.1); opacity: 0; filter: blur(20px); }
}

@keyframes wordSlideUp {
  from { transform: translateY(40px); filter: blur(10px); opacity: 0; }
  to { transform: translateY(0); filter: blur(0); opacity: 1; }
}

@keyframes finaleIn {
  from { transform: scale(0.1); opacity: 0; filter: blur(20px); }
  to { transform: scale(1); opacity: 1; filter: blur(0); }
}

@keyframes finaleOut {
  to { transform: scale(1.2); opacity: 0; filter: blur(10px); }
}

.side-config-card {
  display: grid;
  gap: 16px;
  padding: 14px;
  margin-bottom: 16px;
  border: 1px solid rgba(219, 226, 236, 0.75);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.74);
}

.config-section,
.side-field {
  display: grid;
  gap: 9px;
}

.config-section > span,
.side-field > span {
  color: var(--color-text-secondary);
  font-weight: 800;
}

.mini-style-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.mini-style-grid button {
  display: grid;
  gap: 5px;
  border: 1px solid var(--color-border);
  border-radius: 10px;
  background: #fff;
  padding: 5px;
  color: var(--color-text-secondary);
  font-weight: 800;
  cursor: pointer;
}

.mini-style-grid button.active,
.mini-ratio-group button.active {
  border-color: var(--color-primary);
  background: var(--color-primary-bg);
  color: var(--color-primary);
}

.mini-style-grid img {
  width: 100%;
  aspect-ratio: 16 / 9;
  border-radius: 7px;
  object-fit: cover;
}

.mini-style-grid em {
  overflow: hidden;
  padding: 0 2px 2px;
  font-size: 12px;
  font-style: normal;
  text-align: center;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mini-ratio-group {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}

.mini-ratio-group button {
  height: 38px;
  border: 1px solid var(--color-border);
  border-radius: 10px;
  background: #fff;
  color: var(--color-text-secondary);
  font-weight: 900;
  cursor: pointer;
}

.side-field select {
  width: 100%;
  height: 40px;
  border: 1px solid var(--color-border);
  border-radius: 10px;
  background: #fff;
  padding: 0 12px;
  color: var(--color-text-primary);
  outline: 0;
}

.side-actions {
  display: grid;
  grid-template-columns: 1fr;
  gap: 10px;
  margin: 0;
}

.next-btn {
  width: 100%;
  min-width: 0;
  padding: 0 20px;
}

@media (max-width: 1180px) {
  .manuscript-layout {
    grid-template-columns: 280px minmax(0, 1fr);
  }

  .generation-panel {
    display: none;
  }
}
</style>
