/**
 * 首页 - 创建任务 + 资产库
 */
<template>
  <div class="create-view">
    <NavBar :active-tab="activeTab" @navigate="handleNavigate" />

    <main v-if="activeTab === 'create'" class="create-page">
      <section class="editor-panel">
        <div class="panel-head">
          <div class="panel-title-copy">
            <div class="eyebrow">Cognitive Video Studio</div>
            <h1>创建认知科普视频</h1>
          </div>
          <div class="title-field">
            <label>项目名称</label>
            <input v-model="form.name" class="name-input" maxlength="100" placeholder="给这条视频起个名字" />
          </div>
          <div class="mode-field">
            <label>模式选择</label>
            <div class="mode-switch">
              <button
                v-for="mode in inputModes"
                :key="mode.value"
                type="button"
                :class="{ active: inputMode === mode.value }"
                @click="switchInputMode(mode.value)"
              >
                {{ mode.label }}
              </button>
            </div>
          </div>
          <div v-if="inputMode === 'theme'" class="knob-wrapper-header">
            <div
              class="knob-compact"
              @mousedown="startKnobRotate"
              @touchstart="startKnobRotate"
            >
              <svg viewBox="0 0 48 48" class="knob-svg">
                <defs>
                  <linearGradient id="knobGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stop-color="#007AFF" />
                    <stop offset="100%" stop-color="#5AC8FA" />
                  </linearGradient>
                </defs>
                <circle cx="24" cy="24" r="20" class="knob-bg-ring" />
                <circle
                  cx="24"
                  cy="24"
                  r="20"
                  class="knob-progress-ring"
                  :style="{ strokeDashoffset: knobStrokeDashOffset }"
                />
              </svg>
              <div class="knob-inner">
                <span class="knob-text">{{ form.length === 0 ? '自动' : form.length }}</span>
              </div>
              <div class="knob-pointer" :style="{ transform: `rotate(${knobAngle}deg)` }"></div>
            </div>
            <div class="knob-label">
              <span class="knob-title">生成文案字数</span>
              <span class="knob-hint">旋转调节 · 0-2000</span>
            </div>
          </div>
          <button v-else type="button" class="ghost-btn" @click="router.push('/settings')">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M12 1v6m0 6v6m9-9h-6m-6 0H3"/></svg>
            模型配置
          </button>
        </div>

        <div class="script-field">
          <div class="section-head">
            <label>{{ inputMode === 'theme' ? '视频主题' : '文案内容' }}</label>
            <div class="head-right">
              <span>{{ form.theme.length }}/{{ themeMaxLength }}</span>
            </div>
          </div>
          <div class="textarea-shell">
            <div v-if="!form.theme && !themeFocused" class="value-rotator">
              <div class="rotator-placeholder">{{ inputMode === 'theme' ? '输入 100 字以内主题...' : '在此输入您的文案...' }}</div>
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
            </div>
            <textarea
              v-model="form.theme"
              class="theme-textarea"
              :maxlength="themeMaxLength"
              :placeholder="inputMode === 'theme' ? '输入 100 字以内的视频主题，例如：为什么普通人越来越需要 AI 助手' : '直接粘贴您的剧本文案...'"
              @focus="themeFocused = true"
              @blur="themeFocused = false"
            ></textarea>
          </div>
        </div>
      </section>

      <aside class="config-panel">
        <div class="config-tabs">
          <button v-for="tab in configTabs" :key="tab.key" type="button" :class="{ active: configTab === tab.key }" @click="configTab = tab.key">
            {{ tab.label }}
          </button>
        </div>

        <div v-if="configTab === 'visual'" class="tab-body">
          <div class="toggle-line">
            <button type="button" :class="{ active: visualSource === 'ai' }" @click="visualSource = 'ai'">智能生成</button>
            <button type="button" :class="{ active: visualSource === 'upload' }" @click="visualSource = 'upload'">本地上传</button>
          </div>

          <div v-if="visualSource === 'ai'">
            <div class="section-head">
              <label>画面风格</label>
            </div>
            <div class="style-grid">
              <button
                v-for="opt in allVisualStyleOptions"
                :key="opt.value"
                type="button"
                class="style-card"
                :class="{ active: form.visual_style === opt.value }"
                @click="form.visual_style = opt.value"
              >
                <img v-if="opt.image" :src="opt.image" :alt="opt.text" />
                <span v-else class="custom-style-bg">{{ opt.text.slice(0, 2) }}</span>
                <span class="style-name">{{ opt.text }}</span>
                <span v-if="opt.custom" class="style-remove" @click.stop="removeCustomVisualStyle(opt.value)">×</span>
              </button>
              <button type="button" class="style-card add-style" @click="openCustomVisualStyle">
                <span>+</span>
                <strong>自定义</strong>
              </button>
            </div>
          </div>

          <div v-else class="upload-image-block">
            <div class="section-head">
              <label>本地图片</label>
              <span>{{ uploadedImages.length }}/20</span>
            </div>
            <div class="upload-image-grid">
              <div
                v-for="(item, index) in uploadedImages"
                :key="item.id"
                class="upload-image-card"
                draggable="true"
                @dragstart="onUploadImageDragStart(index)"
                @dragover.prevent
                @drop="onUploadImageDrop(index)"
                @dragend="dragImageIndex = null"
              >
                <img :src="item.url" :alt="`上传图片 ${index + 1}`" />
                <span class="upload-image-order">{{ index + 1 }}</span>
                <button type="button" class="upload-image-remove" aria-label="删除图片" @click.stop="removeUploadedImage(index)">×</button>
              </div>
              <button type="button" class="upload-image-add" @click="uploadInput?.click()">
                <span>+</span>
              </button>
            </div>
            <input ref="uploadInput" type="file" multiple accept="image/*" class="hidden-input" @change="onUploadImagesSelected" />
            <p class="upload-hint">拖拽缩略图调整分镜顺序。</p>
          </div>

          <div class="ratio-block">
            <label>视频比例</label>
            <div class="ratio-options">
              <button v-for="ratio in videoRatios" :key="ratio" type="button" :class="{ active: videoRatio === ratio }" @click="videoRatio = ratio">{{ ratio }}</button>
            </div>
          </div>

          <div class="style-section">
            <div class="section-head">
              <label>创作风格</label>
            </div>
            <div class="chip-group">
              <button
                v-for="opt in allStyleOptions"
                :key="opt.value"
                type="button"
                class="chip"
                :class="{ active: form.style === opt.value }"
                @click="form.style = opt.value"
              >
                <span>{{ opt.text }}</span>
                <span v-if="opt.custom" class="chip-remove" @click.stop="removeCustomTextStyle(opt.value)">×</span>
              </button>
              <button type="button" class="chip add-chip" @click="openCustomTextStyle">+ 自定义</button>
            </div>
            <div v-if="showCustomTextStyle" class="custom-inline">
              <input v-model.trim="customTextStyleName" class="inline-input" placeholder="例如：学术严谨" @keyup.enter="addCustomTextStyle" />
              <button class="inline-primary" @click="addCustomTextStyle">添加</button>
              <button class="inline-secondary" @click="showCustomTextStyle = false">取消</button>
            </div>
          </div>
        </div>

        <div v-else-if="configTab === 'voice'" class="tab-body">
          <div class="section-head">
            <label>配音音色</label>
            <span>{{ form.voice_name || '未选择' }}</span>
          </div>
          <div class="voice-grid">
            <button
              v-for="voice in voiceOptions"
              :key="voice.value"
              type="button"
              class="voice-card"
              :class="{ active: form.voice_type === voice.value }"
              @click="selectVoice(voice)"
            >
              <span class="voice-avatar">{{ voice.text.slice(0, 1) }}</span>
              <span class="voice-text">{{ voice.text }}</span>
            </button>
          </div>

          <div class="range-block">
            <div class="section-head">
              <label>语速调节</label>
              <strong>{{ voiceSpeed.toFixed(1) }}x</strong>
            </div>
            <input type="range" v-model.number="voiceSpeed" min="0.8" max="1.4" step="0.1" class="slider" />
          </div>
        </div>

        <div v-else-if="configTab === 'clone'" class="tab-body placeholder-body">
          <div class="upload-placeholder">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
            <span>声音克隆待接入</span>
          </div>
          <div class="placeholder-list">
            <div>小米 VoiceClone 每次请求需携带本地参考音频 DataURL<span>无远端 voice_id</span></div>
            <div>当前已接入小米预置音色，VoiceDesign/VoiceClone 作为下一步能力<span>待接入</span></div>
          </div>
        </div>

        <div v-else class="tab-body placeholder-body">
          <textarea class="music-input" placeholder="描述想要的配乐氛围，例如：克制、科技、轻节奏"></textarea>
          <div class="placeholder-list">
            <div v-for="item in ['轻科技律动', '温暖钢琴', '纪录片氛围']" :key="item">{{ item }}<span>推荐</span></div>
          </div>
        </div>

        <p v-if="!form.name.trim()" class="generate-hint">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
          请先填写上方的「项目名称」
        </p>
        <button class="generate-btn" :disabled="loading || !canSubmit" @click="handleSubmit">
          <el-icon v-if="loading" class="is-loading" style="margin-right: 8px;"><Loading /></el-icon>
          <template v-else>
            <span class="generate-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg></span>
            生成视频
          </template>
        </button>
      </aside>
    </main>

    <main v-else class="library-page">
      <div class="library-header">
        <div>
          <div class="eyebrow">Assets</div>
          <h1>资产记录</h1>
        </div>
        <button class="dark-btn" @click="activeTab = 'create'">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          新建项目
        </button>
      </div>

      <div v-loading="libraryLoading" element-loading-text="加载中..." class="task-grid">
        <button type="button" class="new-task-card" @click="activeTab = 'create'">
          <span>+</span>
          <strong>新建项目</strong>
        </button>
        <div v-for="task in tasks" :key="task.task_id" class="task-card" @click="onTaskClick(task)">
          <button type="button" class="task-delete" @click.stop="onDeleteTask(task)" aria-label="删除">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
          </button>
          <div class="task-cover">
            <img :src="taskCover(task)" :alt="task.name || task.theme" />
            <span class="task-status" :class="'status-' + task.status">{{ statusLabel(task.status) }}</span>
          </div>
          <div class="task-body">
            <h3>{{ task.name || task.theme }}</h3>
            <p>{{ task.theme }}</p>
            <div class="task-meta">
              <span v-if="task.segments_count">{{ task.segments_count }} 段</span>
              <span>{{ formatTimestamp(task.created_at) }}</span>
            </div>
          </div>
        </div>
      </div>

      <div v-if="!libraryLoading && tasks.length === 0" class="empty-library">
        <p>暂无生成记录</p>
      </div>
    </main>

    <div v-if="showCustomVisualStyle" class="visual-style-overlay" @click.self="cancelCustomVisualStyle">
      <section class="visual-style-dialog">
        <div class="dialog-head">
          <div>
            <h2>添加画面风格</h2>
          </div>
          <button type="button" class="icon-btn" aria-label="关闭" @click="cancelCustomVisualStyle">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>

        <div class="visual-style-form">
          <label class="field-line">
            <span>风格名称</span>
            <input v-model.trim="customVisualForm.name" class="inline-input" placeholder="例如：赛博朋克" />
          </label>

          <label class="field-line">
            <span>Prompt 后缀</span>
            <textarea v-model.trim="customVisualForm.prompt" class="prompt-input" placeholder="英文 prompt 后缀，例如：cyberpunk, neon lights, futuristic city"></textarea>
          </label>

          <div class="visual-upload-grid">
            <label class="upload-card">
              <input type="file" accept="image/*" @change="onCustomVisualImageChange" />
              <span class="upload-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
              </span>
              <strong>上传预览图</strong>
              <small>建议使用正方形图片，自动裁切显示</small>
            </label>
            <div class="custom-preview large-preview">
              <img v-if="customVisualForm.image" :src="customVisualForm.image" alt="自定义预览" />
              <span v-else>预览</span>
            </div>
          </div>
        </div>

        <div class="dialog-actions">
          <button type="button" class="inline-secondary" @click="cancelCustomVisualStyle">取消</button>
          <button type="button" class="inline-primary" @click="addCustomVisualStyle">上传</button>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox, ElLoading } from 'element-plus'
import { createTask, createTaskFromImages, deleteTask, getVoices, listTasks } from '../api/task'
import { formatTimestamp } from '../utils/format'
import NavBar from '../components/NavBar.vue'

const router = useRouter()
const route = useRoute()
const activeTab = ref('create')
const configTab = ref('visual')
const form = ref({ name: '', theme: '', style: '温暖感人', length: 300, visual_style: '电影质感', voice_type: '', voice_name: '米仔' })
const inputMode = ref('script')
const loading = ref(false)
const voiceOptions = ref([])
const voiceMap = ref({})
const tasks = ref([])
const libraryLoading = ref(false)
const showCustomTextStyle = ref(false)
const showCustomVisualStyle = ref(false)
const customTextStyleName = ref('')
const customVisualForm = ref({ name: '', prompt: '', image: '' })
const customTextStyles = ref([])
const customVisualStyles = ref([])
const visualSource = ref('ai')
const videoRatio = ref('16:9')
const voiceSpeed = ref(1.0)
const themeFocused = ref(false)
const uploadedImages = ref([])
const uploadInput = ref(null)
const dragImageIndex = ref(null)
const lengthDisplay = ref('')
const lengthInputFocused = ref(false)
const knobDragging = ref(false)
const knobStartAngle = ref(0)
const knobStartValue = ref(0)
const knobCenterX = ref(0)
const knobCenterY = ref(0)

const knobAngle = computed(() => {
  const percent = form.value.length / 2000
  return percent * 360
})

const knobStrokeDashOffset = computed(() => {
  const circumference = 2 * Math.PI * 20
  const percent = form.value.length / 2000
  return circumference * (1 - percent)
})

const TEXT_STYLE_STORAGE_KEY = 'kepu_custom_text_styles'
const VISUAL_STYLE_STORAGE_KEY = 'kepu_custom_visual_styles'

const configTabs = [
  { key: 'visual', label: '画面' },
  { key: 'voice', label: '配音' },
  { key: 'clone', label: '声音克隆' },
  { key: 'music', label: '音乐' },
]
const inputModes = [
  { label: '写作模式', value: 'script' },
  { label: '主题模式', value: 'theme' },
]
const videoRatios = ['16:9', '9:16', '3:4']
const rotatorItems = [
  { text: '一键生成视频', class: 'text-bloom', anim: 'anim-bloom' },
  { text: '导出剪映草稿', class: 'text-push', anim: 'anim-push' },
  { text: '自由二次编辑', class: 'text-breathe', anim: 'anim-breathe' },
  { slot: true },
  { finale: true },
]
const slotWords = ['视频', '图片', '音频']
const rotatorDurations = [3200, 3000, 3500, 5000, 2600]
const rotatorIndex = ref(0)
let rotatorTimer = null

const defaultStyleOptions = [
  { text: '温暖感人', value: '温暖感人' },
  { text: '励志向上', value: '励志向上' },
  { text: '科普知识', value: '科普知识' },
  { text: '幽默轻松', value: '幽默轻松' },
  { text: '深度思考', value: '深度思考' },
]

const defaultVisualStyleOptions = [
  { text: '电影质感', value: '电影质感', image: '/styles/电影质感.jpg' },
  { text: '吉卜力', value: '吉卜力', image: '/styles/吉卜力.webp' },
  { text: '3D动画', value: '3D动画', image: '/styles/3D动画.webp' },
  { text: '毛毡风', value: '毛毡风', image: '/styles/毛毡风格.webp' },
  { text: '油彩画', value: '油彩画', image: '/styles/油彩画.jpg' },
  { text: '国风', value: '国风', image: '/styles/国风.webp' },
]

const allStyleOptions = computed(() => [...defaultStyleOptions, ...customTextStyles.value])
const allVisualStyleOptions = computed(() => [...defaultVisualStyleOptions, ...customVisualStyles.value])
const currentRotatorItem = computed(() => rotatorItems[rotatorIndex.value] || rotatorItems[0])
const themeMaxLength = computed(() => inputMode.value === 'theme' ? 100 : 2000)
const canSubmit = computed(() => {
  if (!form.value.name.trim()) return false
  if (visualSource.value === 'upload') return uploadedImages.value.length > 0
  return Boolean(form.value.theme.trim())
})

onMounted(async () => {
  startRotator()
  loadCustomOptions()
  if (route.query.tab === 'library') {
    activeTab.value = 'library'
    loadTasks()
  }

  try {
    const voices = await getVoices()
    voiceOptions.value = voices.map(v => ({
      text: `${v.name} (${voiceGenderLabel(v.gender)})`,
      value: v.id,
      description: v.description,
      provider: v.provider,
      language: v.language,
    }))
    voiceMap.value = voices.reduce((map, v) => { map[v.id] = v.name; return map }, {})
    if (voices.length > 0) {
      const defaultVoice = voices.find(v => v.name === '米仔') || voices.find(v => v.id === '冰糖') || voices[0]
      form.value.voice_type = defaultVoice.id
      form.value.voice_name = defaultVoice.name
    }
  } catch (error) {
    console.error('加载音色列表失败:', error)
    ElMessage.error('加载音色列表失败')
  }
})

onBeforeUnmount(() => {
  clearTimeout(rotatorTimer)
  uploadedImages.value.forEach(item => URL.revokeObjectURL(item.url))
})

function startRotator() {
  clearTimeout(rotatorTimer)
  rotatorTimer = setTimeout(() => {
    rotatorIndex.value = (rotatorIndex.value + 1) % rotatorItems.length
    startRotator()
  }, rotatorDurations[rotatorIndex.value] || 3200)
}

function handleNavigate(tab) {
  if (tab === 'settings') {
    router.push('/settings')
    return
  }
  if (tab === 'library') {
    switchToLibrary()
    return
  }
  activeTab.value = 'create'
}

function loadCustomOptions() {
  try {
    customTextStyles.value = JSON.parse(localStorage.getItem(TEXT_STYLE_STORAGE_KEY) || '[]')
    customVisualStyles.value = JSON.parse(localStorage.getItem(VISUAL_STYLE_STORAGE_KEY) || '[]')
  } catch (error) {
    console.error('读取自定义风格失败:', error)
    customTextStyles.value = []
    customVisualStyles.value = []
  }
}

function saveCustomTextStyles() {
  localStorage.setItem(TEXT_STYLE_STORAGE_KEY, JSON.stringify(customTextStyles.value))
}

function saveCustomVisualStyles() {
  localStorage.setItem(VISUAL_STYLE_STORAGE_KEY, JSON.stringify(customVisualStyles.value))
}

function openCustomTextStyle() {
  customTextStyleName.value = ''
  showCustomTextStyle.value = true
  nextTick(() => {
    document.querySelector('.custom-inline')?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  })
}

function addCustomTextStyle() {
  const name = customTextStyleName.value.trim()
  if (!name) { ElMessage.warning('请输入创作风格名称'); return }
  if (allStyleOptions.value.some(opt => opt.value === name)) { ElMessage.warning('该风格已存在'); return }
  customTextStyles.value.push({ text: name, value: name, custom: true })
  saveCustomTextStyles()
  form.value.style = name
  showCustomTextStyle.value = false
}

function removeCustomTextStyle(value) {
  customTextStyles.value = customTextStyles.value.filter(opt => opt.value !== value)
  saveCustomTextStyles()
  if (form.value.style === value) form.value.style = defaultStyleOptions[0].value
}

function openCustomVisualStyle() {
  customVisualForm.value = { name: '', prompt: '', image: '' }
  showCustomVisualStyle.value = true
}

function cancelCustomVisualStyle() {
  customVisualForm.value = { name: '', prompt: '', image: '' }
  showCustomVisualStyle.value = false
}

function onCustomVisualImageChange(event) {
  const file = event.target.files?.[0]
  if (!file) return
  const reader = new FileReader()
  reader.onload = () => { customVisualForm.value.image = reader.result }
  reader.readAsDataURL(file)
}

function addCustomVisualStyle() {
  const name = customVisualForm.value.name.trim()
  const prompt = customVisualForm.value.prompt.trim()
  if (!name) { ElMessage.warning('请输入画面风格名称'); return }
  if (!prompt) { ElMessage.warning('请输入英文 prompt 后缀'); return }
  if (allVisualStyleOptions.value.some(opt => opt.text === name)) { ElMessage.warning('该画面风格已存在'); return }

  const value = `custom-${Date.now()}`
  customVisualStyles.value.push({
    text: name,
    value,
    image: customVisualForm.value.image,
    prompt,
    custom: true,
  })
  saveCustomVisualStyles()
  form.value.visual_style = value
  customVisualForm.value = { name: '', prompt: '', image: '' }
  showCustomVisualStyle.value = false
}

function removeCustomVisualStyle(value) {
  customVisualStyles.value = customVisualStyles.value.filter(opt => opt.value !== value)
  saveCustomVisualStyles()
  if (form.value.visual_style === value) form.value.visual_style = defaultVisualStyleOptions[0].value
}

function selectVoice(voice) {
  form.value.voice_type = voice.value
  form.value.voice_name = voiceMap.value[voice.value] || voice.text
}

function voiceGenderLabel(gender) {
  if (gender === 'female') return '女'
  if (gender === 'male') return '男'
  return '自动'
}

function switchInputMode(mode) {
  inputMode.value = mode
  if (mode === 'theme' && form.value.theme.length > 100) {
    form.value.theme = form.value.theme.slice(0, 100)
    ElMessage.warning('主题模式最多输入 100 字，已自动截断')
  }
}

function normalizeLength() {
  const value = Number(form.value.length)
  if (Number.isNaN(value)) {
    form.value.length = 300
    return
  }
  if (value < 0) form.value.length = 0
  else if (value > 2000) form.value.length = 2000
  else form.value.length = Math.round(value / 50) * 50
}

function onLengthFocus() {
  lengthInputFocused.value = true
  if (form.value.length === 0) {
    lengthDisplay.value = ''
  } else {
    lengthDisplay.value = String(form.value.length)
  }
}

function onLengthBlur() {
  lengthInputFocused.value = false
  const value = lengthDisplay.value.trim()
  if (value === '' || value === '自动') {
    form.value.length = 0
    lengthDisplay.value = ''
  } else {
    const num = Number(value)
    if (!Number.isNaN(num)) {
      form.value.length = Math.max(0, Math.min(2000, Math.round(num / 50) * 50))
    }
    lengthDisplay.value = ''
  }
}

function onLengthInput(event) {
  const value = event.target.value
  if (value === '' || value === '自动') {
    lengthDisplay.value = value
    return
  }
  const num = Number(value)
  if (!Number.isNaN(num) && num >= 0 && num <= 2000) {
    lengthDisplay.value = value
  }
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
  knobStartValue.value = form.value.length
  knobDragging.value = true

  const moveHandler = (e) => {
    if (!knobDragging.value) return
    const currentX = e.type === 'mousemove' ? e.clientX : e.touches[0].clientX
    const currentY = e.type === 'mousemove' ? e.clientY : e.touches[0].clientY

    const currentAngle = Math.atan2(currentY - knobCenterY.value, currentX - knobCenterX.value) * (180 / Math.PI)
    let deltaAngle = currentAngle - lastAngle

    if (deltaAngle > 180) deltaAngle -= 360
    if (deltaAngle < -180) deltaAngle += 360

    accumulatedRotation += deltaAngle
    lastAngle = currentAngle

    const deltaValue = (accumulatedRotation / 360) * 2000
    const newValue = Math.max(0, Math.min(2000, Math.round((knobStartValue.value + deltaValue) / 50) * 50))
    form.value.length = newValue
  }

  const endHandler = () => {
    knobDragging.value = false
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

function buildStylePayload() {
  const selectedVisual = allVisualStyleOptions.value.find(opt => opt.value === form.value.visual_style) || defaultVisualStyleOptions[0]
  const visualStyleName = selectedVisual.text || selectedVisual.value
  const visualPromptSuffix = selectedVisual.prompt || ''
  return visualPromptSuffix
    ? `${form.value.style}|${visualStyleName}|${visualPromptSuffix}`
    : `${form.value.style}|${visualStyleName}`
}

function onUploadImagesSelected(event) {
  const files = Array.from(event.target.files || [])
  if (files.length > 0) appendUploadedFiles(files)
  event.target.value = ''
}

function appendUploadedFiles(files) {
  const imageFiles = files.filter(file => file.type?.startsWith('image/'))
  if (imageFiles.length !== files.length) ElMessage.warning('已忽略非图片文件')

  const remaining = 20 - uploadedImages.value.length
  if (remaining <= 0) {
    ElMessage.warning('最多上传 20 张图片')
    return
  }
  if (imageFiles.length > remaining) ElMessage.warning('最多上传 20 张图片，已自动截断')

  const nextItems = imageFiles.slice(0, remaining).map(file => ({
    id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
    file,
    url: URL.createObjectURL(file),
  }))
  uploadedImages.value.push(...nextItems)
}

function removeUploadedImage(index) {
  const [removed] = uploadedImages.value.splice(index, 1)
  if (removed?.url) URL.revokeObjectURL(removed.url)
}

function onUploadImageDragStart(index) {
  dragImageIndex.value = index
}

function onUploadImageDrop(targetIndex) {
  const sourceIndex = dragImageIndex.value
  dragImageIndex.value = null
  if (sourceIndex === null || sourceIndex === targetIndex) return
  const [moved] = uploadedImages.value.splice(sourceIndex, 1)
  uploadedImages.value.splice(targetIndex, 0, moved)
}

const handleSubmit = async () => {
  if (!form.value.name.trim()) { ElMessage.warning('请输入项目名称'); return }
  if (visualSource.value === 'upload' && uploadedImages.value.length === 0) { ElMessage.warning('请先上传图片'); return }
  if (visualSource.value !== 'upload' && !form.value.theme.trim()) { ElMessage.warning(inputMode.value === 'theme' ? '请输入视频主题' : '请输入文案内容'); return }
  if (inputMode.value === 'theme' && form.value.theme.trim().length > 100) { ElMessage.warning('主题模式最多输入 100 字'); return }
  normalizeLength()

  const stylePayload = buildStylePayload()

  loading.value = true
  try {
    if (visualSource.value === 'upload') {
      const formData = new FormData()
      uploadedImages.value.forEach(item => formData.append('images', item.file))
      formData.append('style', stylePayload)
      formData.append('ratio', videoRatio.value)
      formData.append('voice_type', form.value.voice_type || '')
      formData.append('name', form.value.name.trim())

      const response = await createTaskFromImages(formData)
      ElMessage.success('已创建分镜')
      await router.push(`/preview/${response.task_id}`)
      return
    }

    const response = await createTask({
      name: form.value.name.trim(),
      theme: form.value.theme.trim(),
      input_mode: inputMode.value,
      style: stylePayload,
      ratio: videoRatio.value,
      length: form.value.length,
      voice_type: form.value.voice_type || undefined,
    })
    ElMessage.success('任务创建成功')
    setTimeout(() => { router.push(`/process/${response.task_id}`) }, 1500)
  } catch (error) {
    console.error('创建任务失败:', error)
    ElMessage.error('创建任务失败，请重试')
  } finally {
    loading.value = false
  }
}

async function switchToLibrary() {
  activeTab.value = 'library'
  await loadTasks()
}

async function loadTasks() {
  libraryLoading.value = true
  try {
    tasks.value = await listTasks(null, 50, 0)
  } catch (error) {
    console.error('加载资产列表失败:', error)
    ElMessage.error('加载资产列表失败')
  } finally {
    libraryLoading.value = false
  }
}

function statusLabel(status) {
  const map = { pending: '排队中', processing: '生成中', completed: '已完成', failed: '失败' }
  return map[status] || status
}

function taskCover(task) {
  const styleName = (task.style || '').split('|')[1] || '电影质感'
  return defaultVisualStyleOptions.find(item => item.text === styleName)?.image || defaultVisualStyleOptions[0].image
}

function onTaskClick(task) {
  if (task.status === 'completed' || task.status === 'failed') router.push(`/preview/${task.task_id}`)
  else if (task.status === 'processing' || task.status === 'pending') router.push(`/process/${task.task_id}`)
  else ElMessage.warning('该任务状态异常，无法查看')
}

async function onDeleteTask(task) {
  try {
    await ElMessageBox.confirm(
      `确定删除「${task.name || task.theme}」吗？此操作不可恢复。`,
      '删除任务',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
  } catch {
    return
  }
  try {
    await deleteTask(task.task_id)
    tasks.value = tasks.value.filter(t => t.task_id !== task.task_id)
    ElMessage.success('已删除')
  } catch (error) {
    console.error('删除任务失败:', error)
    ElMessage.error('删除失败，请重试')
  }
}
</script>

<style scoped>
.create-view {
  height: 100vh;
  --create-bright-blue: #0a84ff;
  --create-bright-blue-soft: rgba(10, 132, 255, 0.1);
  --create-bright-blue-glow: rgba(10, 132, 255, 0.24);
  background: #fff;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.create-page {
  height: calc(100vh - 64px);
  display: grid;
  grid-template-columns: minmax(0, 1fr) 320px;
  gap: 12px;
  padding: 12px 16px;
  overflow: hidden;
  background: #fff;
}

.editor-panel,
.config-panel {
  min-height: 0;
  background: var(--color-card);
  border: none;
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-md);
  transition: all var(--duration-normal) var(--ease-out);
}

.editor-panel:hover,
.config-panel:hover {
  box-shadow: var(--shadow-lg);
}

.editor-panel {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 16px;
  padding: 20px 32px 20px 56px;
  overflow: hidden;
}

.editor-panel .panel-head {
  display: grid;
  grid-template-columns: minmax(190px, 1fr) minmax(260px, 1.15fr) minmax(250px, 1fr) minmax(112px, auto);
  align-items: end;
  gap: 16px;
}

.config-panel {
  display: flex;
  flex-direction: column;
  padding: 12px;
  overflow: hidden;
}

.panel-head,
.library-header,
.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.panel-title-copy {
  min-width: 0;
}

.editor-panel .title-field {
  height: 40px;
  width: 100%;
  max-width: none;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 12px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-bg-secondary);
  justify-self: stretch;
  transition: border-color 0.16s, box-shadow 0.16s, background 0.16s;
}

.editor-panel .mode-field {
  height: 40px;
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 0 8px 0 12px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-bg-secondary);
  justify-self: stretch;
}

.editor-panel .title-field:focus-within {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px var(--accent-glow);
  background: #fff;
}

.editor-panel .title-field label,
.editor-panel .mode-field label {
  flex-shrink: 0;
  font-size: 12px;
  color: var(--color-text-tertiary);
}

.editor-panel .ghost-btn {
  justify-self: end;
  min-width: 112px;
}

.eyebrow {
  font-size: 11px;
  line-height: 1;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--color-primary);
  font-weight: 800;
  margin-bottom: 7px;
}

h1 {
  font-size: 24px;
  line-height: 1.15;
  color: var(--color-text);
}

label,
.section-head label {
  font-size: 13px;
  font-weight: 700;
  color: var(--color-text-secondary);
}

.section-head span {
  font-size: 12px;
  color: var(--color-text-tertiary);
}

.text-link {
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  padding: 0 10px;
  border-radius: 7px;
  border: 1px solid var(--color-border);
  background: #fff;
  color: var(--color-primary);
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  box-shadow: var(--shadow-xs);
  transition: border-color 0.16s, background 0.16s, transform 0.16s, box-shadow 0.16s;
}

.text-link svg {
  width: 13px;
  height: 13px;
  stroke-width: 2.4;
}

.text-link:hover {
  border-color: var(--color-primary);
  background: var(--color-primary-bg);
  box-shadow: 0 2px 8px rgba(22, 93, 255, 0.12);
  transform: translateY(-1px);
}

.text-link:active {
  transform: translateY(0);
}

.ghost-btn,
.dark-btn,
.icon-btn {
  height: 40px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 0 16px;
  border-radius: var(--radius-xl);
  border: 1px solid var(--color-border);
  background: var(--color-card);
  color: var(--color-text-secondary);
  font-size: 14px;
  font-weight: 400;
  letter-spacing: -0.016em;
  cursor: pointer;
  transition: all var(--duration-normal) var(--ease-out);
}

.ghost-btn:hover {
  background: var(--color-bg-secondary);
  border-color: var(--color-primary);
}

.ghost-btn svg,
.dark-btn svg,
.icon-btn svg,
.upload-icon svg,
.generate-icon svg,
.upload-placeholder svg {
  width: 16px;
  height: 16px;
}

.icon-btn {
  width: 40px;
  padding: 0;
  color: var(--color-text-tertiary);
  background: var(--color-bg-secondary);
}

.icon-btn:hover {
  color: var(--color-text);
  border-color: var(--color-primary);
}

.dark-btn,
.generate-btn {
  background: var(--color-primary);
  border-color: var(--color-primary);
  color: #ffffff;
}

.dark-btn:hover,
.generate-btn:hover {
  background: var(--color-primary-hover);
  transform: scale(1.02);
}

.dark-btn:active,
.generate-btn:active {
  transform: scale(0.98);
}

.title-field {
  display: grid;
  gap: 6px;
  min-width: 0;
}

.name-input,
.inline-input,
.prompt-input,
.music-input {
  width: 100%;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-bg-secondary);
  color: var(--color-text);
  outline: none;
  transition: border-color 0.16s, box-shadow 0.16s, background 0.16s;
}

.name-input,
.inline-input {
  height: 40px;
  padding: 0 12px;
  font-size: 14px;
}

.name-input {
  text-align: center;
}

.editor-panel .name-input {
  height: 100%;
  min-width: 0;
  padding: 0;
  border: none;
  background: transparent;
  box-shadow: none;
  text-align: center;
}

.editor-panel .name-input:focus {
  border-color: transparent;
  box-shadow: none;
  background: transparent;
}

.name-input:focus,
.inline-input:focus,
.prompt-input:focus,
.theme-textarea:focus,
.music-input:focus {
  border-color: var(--color-accent);
  box-shadow: 0 0 0 4px rgba(0, 113, 227, 0.1);
  background: #fff;
}

.script-field {
  min-height: 0;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.mode-switch {
  width: fit-content;
  display: inline-flex;
  gap: 4px;
  padding: 3px;
  border-radius: 7px;
  background: #fff;
}

.mode-switch button {
  height: 28px;
  padding: 0 10px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--color-text-tertiary);
  font-size: 12px;
  font-weight: 800;
  cursor: pointer;
}

.mode-switch button.active {
  background: var(--color-dark);
  color: #fff;
  box-shadow: var(--shadow-xs);
}

.mode-switch button:not(.active) {
  color: var(--color-text);
}

.textarea-shell {
  flex: 1;
  min-height: 340px;
  position: relative;
  border-radius: var(--radius-sm);
  background: #fff;
}

.theme-textarea {
  width: 100%;
  height: 100%;
  min-height: 340px;
  padding: 16px;
  font-size: 15px;
  line-height: 1.7;
  color: var(--color-text);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  resize: none;
  outline: none;
  background: #fff;
}

.textarea-shell:not(:focus-within) .theme-textarea::placeholder {
  color: transparent;
}

.value-rotator {
  position: absolute;
  inset: 0;
  padding: 24px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  pointer-events: none;
  z-index: 5;
}

.rotator-placeholder {
  position: absolute;
  top: 22px;
  left: 22px;
  color: var(--color-text-tertiary);
  font-size: 15px;
  opacity: 0.45;
  font-weight: 300;
}

.rotator-stage {
  position: relative;
  width: 100%;
  height: 112px;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  -webkit-mask-image: linear-gradient(to bottom, transparent 0%, #000 30%, #000 70%, transparent 100%);
  mask-image: linear-gradient(to bottom, transparent 0%, #000 30%, #000 70%, transparent 100%);
}

.rotator-text {
  position: absolute;
  font-size: 32px;
  font-weight: 800;
  line-height: 1.2;
  white-space: nowrap;
}

.anim-bloom {
  animation: bloomIn 1.2s cubic-bezier(0.4, 0, 0.2, 1) forwards, bloomOut 0.5s cubic-bezier(0.4, 0, 0.2, 1) 2.7s forwards;
}

@keyframes bloomIn {
  from { transform: scale(0.8); opacity: 0; filter: blur(20px); letter-spacing: 0; }
  to { transform: scale(1); opacity: 1; filter: blur(0); letter-spacing: 0.05em; }
}

@keyframes bloomOut {
  to { transform: translateX(-150px); opacity: 0; filter: blur(10px); }
}

.text-bloom {
  background: linear-gradient(to right, var(--color-text), var(--create-bright-blue), #60a5fa);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.anim-push {
  animation: pushIn 0.8s cubic-bezier(0.33, 1, 0.68, 1) forwards, pushOut 0.6s cubic-bezier(0.4, 0, 0.2, 1) 2.4s forwards;
}

@keyframes pushIn {
  from { transform: translateX(200px); opacity: 0; filter: blur(10px); }
  to { transform: translateX(0); opacity: 1; filter: blur(0); }
}

@keyframes pushOut {
  to { transform: translateY(60px) scale(0.9); opacity: 0; filter: blur(15px); }
}

.text-push {
  background: linear-gradient(to bottom right, var(--color-text), var(--create-bright-blue), #60a5fa);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.anim-breathe {
  animation: breatheIn 2.2s ease-out forwards, breatheOut 0.8s ease-out 2.2s forwards;
}

@keyframes breatheIn {
  from { transform: translateY(-60px) scale(0.9); opacity: 0; }
  to { transform: translateY(0) scale(1.05); opacity: 1; }
}

@keyframes breatheOut {
  to { transform: translateY(-60px) scale(0.9); opacity: 0; filter: blur(10px); }
}

.text-breathe {
  background: linear-gradient(to right, var(--create-bright-blue), #1d4ed8, var(--create-bright-blue));
  background-size: 200% auto;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  animation: shimmer 3s linear infinite, breatheIn 2.2s ease-out forwards, breatheOut 0.8s ease-out 2.2s forwards;
}

@keyframes shimmer {
  to { background-position: 200% center; }
}

.anim-slot {
  animation: slotIn 0.6s cubic-bezier(0.4, 0, 0.2, 1) forwards, slotOut 0.8s cubic-bezier(0.4, 0, 0.2, 1) 2.5s forwards;
}

@keyframes slotIn {
  from { transform: translateY(30px); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
}

@keyframes slotOut {
  to { transform: scale(0.1); opacity: 0; filter: blur(20px); }
}

.slot-group {
  display: flex;
  gap: 12px;
  align-items: center;
}

.slot-item {
  height: 40px;
  padding: 0 12px;
  display: flex;
  align-items: center;
  overflow: hidden;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: #fff;
  box-shadow: inset 0 1px 2px rgba(0,0,0,0.06);
}

.slot-item:nth-child(2) {
  border-color: rgba(10, 132, 255, 0.36);
  background: linear-gradient(180deg, #fff, rgba(10, 132, 255, 0.06));
  box-shadow:
    inset 0 1px 2px rgba(10, 132, 255, 0.08),
    0 8px 22px rgba(10, 132, 255, 0.12);
}

.slot-word {
  opacity: 0;
  font-size: 24px;
  font-weight: 700;
  color: var(--color-text);
  animation: wordSlideUp 0.8s cubic-bezier(0.4, 0, 0.2, 1) forwards;
}

.slot-item:nth-child(2) .slot-word {
  color: var(--create-bright-blue);
}

@keyframes wordSlideUp {
  from { transform: translateY(40px); filter: blur(10px); opacity: 0; }
  to { transform: translateY(0); filter: blur(0); opacity: 1; }
}

.anim-finale {
  animation: finaleIn 1.5s cubic-bezier(0.4, 0, 0.2, 1) forwards, finaleOut 0.6s cubic-bezier(0.4, 0, 0.2, 1) 2.5s forwards;
}

@keyframes finaleIn {
  from { transform: scale(0.1); opacity: 0; filter: blur(20px); }
  to { transform: scale(1); opacity: 1; filter: blur(0); }
}

@keyframes finaleOut {
  to { transform: scale(1.2); opacity: 0; filter: blur(10px); }
}

.text-finale {
  color: var(--color-text);
}

.text-finale span {
  color: var(--create-bright-blue);
}

.knob-wrapper-header {
  display: flex;
  align-items: center;
  gap: 10px;
}

.knob-wrapper {
  display: flex;
  align-items: center;
  gap: 10px;
}

.knob-compact {
  position: relative;
  width: 48px;
  height: 48px;
  cursor: grab;
  user-select: none;
  -webkit-user-select: none;
  flex-shrink: 0;
}

.knob-compact:active {
  cursor: grabbing;
}

.knob-svg {
  width: 100%;
  height: 100%;
  transform: rotate(-90deg);
}

.knob-bg-ring {
  fill: none;
  stroke: #e5e7eb;
  stroke-width: 3;
}

.knob-progress-ring {
  fill: none;
  stroke: url(#knobGrad);
  stroke-width: 3;
  stroke-linecap: round;
  stroke-dasharray: 125.66;
  transition: stroke-dashoffset 0.1s ease-out;
}

.knob-inner {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: linear-gradient(135deg, #007AFF 0%, #5AC8FA 100%);
  box-shadow: 0 2px 8px rgba(0, 122, 255, 0.25);
}

.knob-text {
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.knob-pointer {
  position: absolute;
  top: 4px;
  left: 50%;
  width: 2px;
  height: 8px;
  background: #fff;
  border-radius: 1px;
  transform-origin: center 20px;
  transition: transform 0.1s ease-out;
  margin-left: -1px;
}

.knob-label {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.knob-title {
  color: var(--color-text);
  font-size: 13px;
  font-weight: 600;
  line-height: 1.2;
}

.knob-hint {
  color: var(--color-text-tertiary);
  font-size: 11px;
  line-height: 1.2;
}

.head-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.head-right > span {
  color: var(--color-text-tertiary);
  font-size: 12px;
  white-space: nowrap;
}

.style-section {
  flex-shrink: 0;
  margin-top: 14px;
}

.chip-group {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}

.chip {
  min-height: 30px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 0 10px;
  border-radius: 7px;
  font-size: 13px;
  color: var(--color-text-secondary);
  background: #fff;
  border: 1px solid var(--color-border);
  cursor: pointer;
}

.chip:hover,
.chip.active {
  color: var(--color-primary);
  border-color: var(--color-primary);
  background: var(--color-primary-bg);
}

.add-chip {
  border-style: dashed;
}

.chip-remove,
.style-remove {
  width: 18px;
  height: 18px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: rgba(29, 33, 41, 0.08);
}

.custom-inline {
  display: grid;
  grid-template-columns: 1fr auto auto;
  gap: 8px;
  margin-top: 10px;
}

.inline-primary,
.inline-secondary {
  height: 36px;
  padding: 0 12px;
  border-radius: var(--radius-sm);
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  border: none;
}

.inline-primary { background: var(--color-primary); color: #fff; }
.inline-secondary { background: #fff; color: var(--color-text-secondary); border: 1px solid var(--color-border); }

.config-tabs {
  display: flex;
  gap: 16px;
  padding: 10px 14px;
  border-bottom: 1px solid var(--color-border);
  flex-shrink: 0;
}

.config-tabs button {
  font-size: 13px;
  font-weight: 500;
  padding-bottom: 4px;
  border: none;
  background: transparent;
  color: var(--color-text-tertiary);
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: all 0.2s;
}

.config-tabs button.active {
  color: var(--color-text);
  border-bottom-color: var(--color-primary);
}

.config-tabs button:hover {
  color: var(--color-text);
}

.toggle-line button,
.ratio-options button {
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--color-text-tertiary);
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}

.toggle-line button.active,
.ratio-options button.active {
  background: #fff;
  color: var(--color-primary);
  box-shadow: var(--shadow-xs);
}

.tab-body {
  min-height: 0;
  flex: 1;
  overflow-y: auto;
  padding-right: 2px;
}

.toggle-line,
.ratio-options {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 6px;
  padding: 4px;
  background: var(--color-bg-secondary);
  border-radius: var(--radius-sm);
  margin-bottom: 14px;
}

.toggle-line button,
.ratio-options button {
  height: 30px;
}

.style-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  margin: 10px 0 14px;
}

.style-card {
  aspect-ratio: 1 / 1;
  position: relative;
  overflow: hidden;
  border-radius: 6px;
  border: 2px solid transparent;
  cursor: pointer;
  padding: 6px;
  background: var(--color-bg-secondary);
  transition: all 0.3s;
}

.style-card:hover {
  border-color: var(--color-border);
}

.style-card:hover .style-card-img,
.style-card:hover img {
  transform: scale(1.1);
}

.style-card.active {
  border-color: var(--color-primary);
}

.style-card img,
.custom-preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  position: absolute;
  inset: 0;
  transition: transform 0.5s;
}

.style-card::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(to top, rgba(0,0,0,0.6), transparent);
}

.style-name {
  position: absolute;
  left: 6px;
  bottom: 6px;
  z-index: 1;
  color: #fff;
  font-size: 11px;
  font-weight: 500;
  text-shadow: 0 1px 3px rgba(0,0,0,0.5);
}

.style-remove {
  position: absolute;
  z-index: 2;
  right: 8px;
  top: 8px;
  background: rgba(255,255,255,0.88);
  color: var(--color-text);
}

.custom-style-bg,
.add-style {
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-primary);
  font-weight: 800;
}

.add-style {
  flex-direction: column;
  gap: 4px;
  border: 1px dashed var(--color-border);
}

.add-style::after {
  display: none;
}

.add-style span {
  font-size: 22px;
  line-height: 1;
}

.add-style strong {
  position: relative;
  z-index: 1;
  font-size: 12px;
}

.upload-image-block {
  margin-bottom: 14px;
}

.upload-image-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  margin-top: 10px;
}

.upload-image-card,
.upload-image-add {
  aspect-ratio: 1 / 1;
  border-radius: 6px;
  border: 1px solid var(--color-border);
  overflow: hidden;
  background: var(--color-bg-secondary);
}

.upload-image-card {
  position: relative;
  cursor: grab;
}

.upload-image-card:active {
  cursor: grabbing;
}

.upload-image-card img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.upload-image-order {
  position: absolute;
  left: 6px;
  top: 6px;
  min-width: 18px;
  height: 18px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  background: rgba(0,0,0,0.58);
  color: #fff;
  font-size: 10px;
  font-weight: 800;
}

.upload-image-remove {
  position: absolute;
  right: 6px;
  top: 6px;
  width: 22px;
  height: 22px;
  border: none;
  border-radius: 999px;
  background: rgba(0,0,0,0.62);
  color: #fff;
  font-size: 16px;
  line-height: 1;
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.16s;
}

.upload-image-card:hover .upload-image-remove {
  opacity: 1;
}

.upload-image-add {
  display: grid;
  place-items: center;
  border-style: dashed;
  color: var(--color-primary);
  cursor: pointer;
}

.upload-image-add span {
  font-size: 28px;
  line-height: 1;
  font-weight: 700;
}

.upload-image-add:hover {
  border-color: var(--color-primary);
  background: var(--color-primary-bg);
}

.upload-hint {
  margin-top: 8px;
  color: var(--color-text-tertiary);
  font-size: 12px;
}

.hidden-input {
  display: none;
}

.custom-visual-panel {
  display: grid;
  gap: 8px;
  padding: 10px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-bg-secondary);
  margin-bottom: 14px;
}

.prompt-input,
.music-input {
  min-height: 72px;
  padding: 10px 12px;
  resize: vertical;
  font-size: 13px;
}

.upload-line {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--color-text-tertiary);
}

.upload-line input {
  min-width: 0;
  font-size: 12px;
}

.custom-preview {
  position: relative;
  height: 82px;
  border-radius: var(--radius-sm);
  overflow: hidden;
  background: #fff;
  border: 1px dashed var(--color-border);
  color: var(--color-text-placeholder);
  display: flex;
  align-items: center;
  justify-content: center;
}

.custom-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.script-length-block {
  padding: 14px 16px;
  margin-bottom: 16px;
  border-radius: 10px;
  background: #ffffff;
  border: 1px solid rgba(0, 0, 0, 0.08);
}

.knob-row {
  display: flex;
  align-items: center;
  gap: 16px;
}

.knob-row > label {
  font-size: 13px;
  font-weight: 600;
  color: #1d1d1f;
  white-space: nowrap;
}

.knob-group {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 12px;
}

.knob-dial {
  position: relative;
  width: 56px;
  height: 56px;
  flex-shrink: 0;
  cursor: ns-resize;
  user-select: none;
  -webkit-user-select: none;
}

.knob-dial:active {
  opacity: 0.9;
}

.knob-circle {
  width: 100%;
  height: 100%;
  transform: rotate(-90deg);
}

.knob-track {
  fill: none;
  stroke: #f0f0f0;
  stroke-width: 4;
  stroke-linecap: round;
}

.knob-fill {
  fill: none;
  stroke: url(#knobGrad);
  stroke-width: 4;
  stroke-linecap: round;
  stroke-dasharray: 150.8;
  transition: stroke-dashoffset 0.12s ease-out;
}

.knob-display {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  pointer-events: none;
}

.knob-num {
  font-size: 16px;
  font-weight: 700;
  color: #1d1d1f;
  font-variant-numeric: tabular-nums;
  line-height: 1;
}

.knob-marker {
  position: absolute;
  top: 4px;
  left: 50%;
  width: 2px;
  height: 10px;
  margin-left: -1px;
  background: linear-gradient(180deg, #007AFF, #5AC8FA);
  border-radius: 1px;
  transform-origin: 50% 24px;
  transition: transform 0.12s ease-out;
  box-shadow: 0 1px 3px rgba(0, 122, 255, 0.3);
}

.knob-field {
  flex: 1;
  height: 36px;
  padding: 0 12px;
  border: 1px solid rgba(0, 0, 0, 0.1);
  border-radius: 8px;
  background: #f9f9f9;
  color: #1d1d1f;
  font-size: 14px;
  font-weight: 500;
  text-align: center;
  outline: none;
  transition: all 0.15s ease;
  font-variant-numeric: tabular-nums;
}

.knob-field:hover {
  background: #ffffff;
  border-color: rgba(0, 122, 255, 0.2);
}

.knob-field:focus {
  background: #ffffff;
  border-color: #007AFF;
  box-shadow: 0 0 0 3px rgba(0, 122, 255, 0.08);
}

.knob-field::placeholder {
  color: #86868b;
  font-weight: 400;
}

.ratio-block,
.range-block {
  display: grid;
  gap: 10px;
  margin-top: 14px;
}

.compact-length {
  margin-top: 0;
}

.ratio-options {
  grid-template-columns: repeat(3, 1fr);
  margin-bottom: 0;
}

.voice-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 6px;
}

.voice-card {
  min-height: 48px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border-radius: 6px;
  border: 1px solid var(--color-border);
  background: #fff;
  color: var(--color-text-secondary);
  cursor: pointer;
  text-align: left;
  transition: all 0.2s;
}

.voice-card:hover {
  border-color: var(--color-primary);
  background: var(--color-bg-secondary);
}

.voice-card.active {
  border-color: var(--color-primary);
  background: var(--color-primary-bg);
  color: var(--color-primary);
}

.voice-avatar {
  width: 28px;
  height: 28px;
  border-radius: 999px;
  background: var(--color-dark);
  color: #fff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 800;
}

.voice-text {
  font-size: 13px;
  font-weight: 700;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.slider {
  width: 100%;
  height: 4px;
  appearance: none;
  -webkit-appearance: none;
  background: var(--color-border);
  border-radius: 999px;
  outline: none;
}

.slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 16px;
  height: 16px;
  background: var(--color-primary);
  border-radius: 50%;
  cursor: pointer;
}

.placeholder-body {
  display: grid;
  gap: 12px;
  align-content: start;
}

.upload-placeholder {
  height: 118px;
  border: 1px dashed var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-bg-secondary);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: var(--color-text-tertiary);
  font-size: 13px;
}

.upload-placeholder svg {
  width: 24px;
  height: 24px;
}

.placeholder-list {
  display: grid;
  gap: 8px;
}

.placeholder-list div {
  min-height: 42px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 12px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: #fff;
  font-size: 13px;
  font-weight: 700;
  color: var(--color-text-secondary);
}

.placeholder-list span {
  font-size: 11px;
  color: var(--color-text-tertiary);
}

.generate-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 0 0 4px;
  font-size: 12px;
  color: var(--color-danger, #ee0a24);
  line-height: 1;
  animation: hintPulse 2s ease-in-out infinite;
}

.generate-hint svg {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
}

@keyframes hintPulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.generate-btn {
  height: 40px;
  width: 100%;
  flex-shrink: 0;
  margin-top: 0;
  border-radius: 8px;
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.2s, opacity 0.2s;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  padding: 0 16px;
}

.generate-btn:hover:not(:disabled) {
  background: #333;
}

.generate-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.generate-icon {
  width: 14px;
  height: 14px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: linear-gradient(to top right, #60a5fa, #a78bfa);
}

.generate-icon svg {
  width: 10px;
  height: 10px;
}

.library-page {
  height: calc(100vh - 64px);
  overflow-y: auto;
  padding: 26px 32px 40px;
}

.library-header {
  margin-bottom: 20px;
}

.task-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 24px;
}

.new-task-card,
.task-card {
  position: relative;
  min-height: 224px;
  border-radius: 12px;
  background: #fff;
  border: 1px solid var(--color-border);
  overflow: hidden;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  flex-direction: column;
}

.task-delete {
  position: absolute;
  top: 8px;
  right: 8px;
  z-index: 5;
  width: 28px;
  height: 28px;
  border: none;
  border-radius: 6px;
  background: rgba(0, 0, 0, 0.5);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.16s, background 0.16s;
}

.task-card:hover .task-delete {
  opacity: 1;
}

.task-delete:hover {
  background: var(--color-danger, #ee0a24);
}

.task-delete svg {
  width: 14px;
  height: 14px;
}

.new-task-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: var(--color-text-tertiary);
  border: 2px dashed var(--color-border);
  min-height: 240px;
  background: transparent;
  box-shadow: none;
}

.new-task-card:hover {
  border-color: var(--color-primary);
  background: var(--color-bg-secondary);
}

.new-task-card span {
  font-size: 28px;
  line-height: 1;
}

.task-card:hover,
.new-task-card:hover {
  box-shadow: 0 4px 12px rgba(0,0,0,0.08);
  transform: translateY(-2px);
}

.task-card:hover .task-cover img {
  transform: scale(1.05);
}

.task-cover {
  position: relative;
  aspect-ratio: 16 / 9;
  overflow: hidden;
}

.task-cover img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  transition: transform 0.5s;
}

.task-status {
  position: absolute;
  right: 8px;
  top: 8px;
  font-size: 11px;
  padding: 3px 8px;
  border-radius: 999px;
  font-weight: 800;
  background: rgba(255,255,255,0.9);
}

.status-pending { color: var(--color-text-tertiary); }
.status-processing { color: var(--color-primary); }
.status-completed { color: var(--color-success); }
.status-failed { color: var(--color-danger); }

.task-body {
  padding: 12px;
}

.task-body h3,
.task-body p {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-body h3 {
  font-size: 14px;
  color: var(--color-text);
  margin-bottom: 7px;
}

.task-body p {
  font-size: 12px;
  color: var(--color-text-tertiary);
  margin-bottom: 12px;
}

.task-meta {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  font-size: 12px;
  color: var(--color-text-placeholder);
}

.loading-state,
.empty-library {
  padding: 70px 0;
  text-align: center;
  color: var(--color-text-tertiary);
}

.visual-style-overlay {
  position: fixed;
  inset: 0;
  z-index: 50;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(17, 24, 39, 0.42);
  backdrop-filter: blur(8px);
}

.visual-style-dialog {
  width: min(560px, 100%);
  max-height: min(720px, calc(100vh - 48px));
  overflow-y: auto;
  border-radius: 12px;
  border: 1px solid var(--color-border);
  background: var(--color-card);
  box-shadow: 0 24px 70px rgba(17, 24, 39, 0.28);
  padding: 18px;
}

.dialog-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}

.dialog-head span {
  display: block;
  margin-bottom: 6px;
  color: var(--color-primary);
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.dialog-head h2 {
  font-size: 20px;
  line-height: 1.2;
  color: var(--color-text);
}

.visual-style-form {
  display: grid;
  gap: 14px;
}

.field-line {
  display: grid;
  gap: 8px;
}

.field-line span {
  font-size: 13px;
  font-weight: 700;
  color: var(--color-text-secondary);
}

.visual-upload-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 160px;
  gap: 12px;
  align-items: stretch;
}

.upload-card {
  min-height: 160px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 18px;
  border: 1px dashed var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-bg-secondary);
  color: var(--color-text-tertiary);
  text-align: center;
  cursor: pointer;
  transition: border-color 0.16s, background 0.16s;
}

.upload-card:hover {
  border-color: var(--color-primary);
  background: var(--color-primary-bg);
}

.upload-card input {
  display: none;
}

.upload-icon {
  width: 34px;
  height: 34px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  background: #fff;
  color: var(--color-primary);
  box-shadow: var(--shadow-xs);
}

.upload-card strong {
  font-size: 13px;
  color: var(--color-text-secondary);
}

.upload-card small {
  max-width: 180px;
  font-size: 12px;
  line-height: 1.5;
}

.large-preview {
  width: 160px;
  height: 160px;
}

.dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 18px;
  padding-top: 14px;
  border-top: 1px solid var(--color-border);
}

.popup-panel {
  padding: 22px;
}

.popup-panel h3 {
  font-size: 18px;
  margin-bottom: 10px;
}

.popup-panel p {
  color: var(--color-text-tertiary);
  font-size: 14px;
  line-height: 1.7;
  margin-bottom: 18px;
}

@media (max-width: 1180px) {
  .task-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}

@media (max-width: 920px) {
  .create-view { overflow: auto; }
  .create-page {
    height: auto;
    min-height: calc(100vh - 64px);
    grid-template-columns: 1fr;
    overflow: visible;
  }
  .editor-panel {
    justify-content: flex-start;
    padding: 20px;
  }
  .textarea-shell { height: auto; min-height: 340px; }
  .editor-panel,
  .config-panel {
    overflow: visible;
  }
  .task-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}

@media (max-width: 620px) {
  .create-page,
  .library-page {
    padding: 12px;
  }
  .editor-panel .panel-head {
    grid-template-columns: 1fr;
    align-items: stretch;
  }
  .panel-head,
  .library-header {
    align-items: flex-start;
    flex-direction: column;
  }
  .custom-inline {
    grid-template-columns: 1fr;
  }
  .value-rotator {
    padding: 18px;
  }
  .rotator-placeholder {
    top: 18px;
    left: 18px;
    font-size: 13px;
  }
  .rotator-text {
    font-size: 24px;
  }
  .slot-group {
    gap: 6px;
  }
  .slot-item {
    height: 34px;
    padding: 0 8px;
  }
  .slot-word {
    font-size: 18px;
  }
  .visual-style-overlay {
    padding: 12px;
  }
  .visual-upload-grid {
    grid-template-columns: 1fr;
  }
  .large-preview {
    width: 100%;
    aspect-ratio: 1 / 1;
    height: auto;
  }
  .task-grid { grid-template-columns: 1fr; }
}
</style>
