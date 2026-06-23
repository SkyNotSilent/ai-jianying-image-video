<template>
  <div class="preview-view">
    <NavBar active-tab="" show-back show-actions @navigate="handleNavigate" @back="onBack" @export="onRebuild" />

    <main class="workbench">
      <div v-loading="loading" element-loading-text="加载中..." class="workbench-content">
        <el-empty v-if="!loading && segments.length === 0" description="暂无段落数据" />

      <template v-if="!loading && segments.length > 0">
        <aside class="storyboard-panel">
          <div class="panel-title">
            <h2>分镜列表</h2>
            <span>{{ segments.length }} 段</span>
          </div>
          <div class="segment-list">
            <SegmentCard
              v-for="(segment, index) in segments"
              :key="segment.id || index"
              :segment="segment"
              :index="index"
              :active="index === currentIndex"
              :aspect-ratio="canvasAspectRatio"
              :preview-playing="isPlaying && playbackMode === 'single' && index === currentIndex"
              :preview-progress="index === currentIndex ? segmentPlaybackRatio : 0"
              :can-undo-image="Boolean(imageUndoStack[index]?.length)"
              @select="selectSegment"
              @preview-segment="previewSegment"
              @regenerate-image="onRegenerateImage"
              @regenerate-audio="onRegenerateAudio"
              @upload-image="onUploadImage"
              @undo-image="undoImageReplacement"
            />
          </div>
        </aside>

        <section class="preview-panel">
          <div class="media-stage">
            <div class="stage-topbar">
              <div class="stage-status">
                <span class="status-dot"></span>
                <span>{{ currentSceneLabel }}</span>
              </div>
              <div class="stage-meta">
                <span>{{ canvasRatioLabel }}</span>
                <span>{{ canvasSizeLabel }}</span>
                <span>{{ totalDurationLabel }}</span>
              </div>
            </div>

            <div class="stage-shell">
              <div class="render-canvas" :style="renderCanvasStyle">
                <img
                  v-if="currentSegment?.image_url && !imageError"
                  :key="`${currentIndex}-${currentSegment.image_url}`"
                  :src="currentSegment.image_url"
                  :alt="`当前分镜 ${currentIndex + 1}`"
                  :style="previewImageStyle"
                  @error="handlePreviewImageError"
                  @load="handlePreviewImageLoad"
                />
                <div v-else-if="imageError || currentSegment?.image_status === 'failed'" class="stage-error">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="48" height="48">
                    <circle cx="12" cy="12" r="10"/>
                    <line x1="12" y1="8" x2="12" y2="12"/>
                    <line x1="12" y1="16" x2="12.01" y2="16"/>
                  </svg>
                  <p>图片加载失败</p>
                  <p v-if="currentSegment?.image_error" class="error-detail">{{ currentSegment.image_error }}</p>
                </div>
                <div v-else class="stage-empty">暂无图片</div>
                <div v-if="previewSubtitleText" class="subtitle-overlay" :style="subtitleStyle">{{ previewSubtitleText }}</div>
                <video
                  v-if="precisePreviewUrl"
                  class="precise-video"
                  :src="precisePreviewUrl"
                  controls
                  autoplay
                  playsinline
                ></video>
                <button v-if="precisePreviewUrl" type="button" class="close-preview-btn" @click="precisePreviewUrl = ''">关闭精准预览</button>
              </div>
            </div>

            <div class="stage-footer">
              <span>{{ playbackSegmentLabel }}</span>
              <span>{{ currentSegmentDurationLabel }}</span>
            </div>
          </div>

          <div class="playbar">
            <div class="playback-main">
              <button type="button" class="play-btn" @click="togglePlayback">
                <svg v-if="!isPlaying" viewBox="0 0 24 24" fill="currentColor"><polygon points="7 4 20 12 7 20 7 4"/></svg>
                <svg v-else viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>
              </button>
              <div class="play-track" @click="seekByClick">
                <div class="play-fill" :style="{ width: playbackProgress + '%' }"></div>
              </div>
            </div>
            <div class="playback-meta">
              <span class="play-time">{{ playTimeLabel }}</span>
              <span class="play-segment">{{ playbackSegmentLabel }}</span>
            </div>
            <button type="button" class="preview-action-btn" :disabled="renderingPreview" @click="onRenderPrecisePreview">
              {{ renderingPreview ? '生成中...' : '生成最终效果预览' }}
            </button>
          </div>
          <audio ref="audioEl" class="hidden-audio" @ended="playNextSegment" @timeupdate="onAudioTimeUpdate" @loadedmetadata="onAudioTimeUpdate"></audio>
        </section>

        <aside class="edit-panel">
          <div class="edit-tabs">
            <button v-for="tab in editTabs" :key="tab.key" type="button" :class="{ active: editTab === tab.key }" @click="editTab = tab.key">{{ tab.label }}</button>
          </div>

          <div v-if="editTab === 'edit'" class="edit-body">
            <label class="upload-box">
              <input type="file" accept="image/jpeg,image/jpg,image/png,image/webp" @change="onCurrentImageSelected" />
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
              <span>上传替换图片</span>
            </label>

            <div class="image-history-row">
              <div class="history-strip">
                <button
                  v-for="asset in currentImageAssets"
                  :key="asset.asset_id"
                  type="button"
                  class="history-thumb"
                  :class="{ active: isCurrentImageAsset(asset) }"
                  :title="asset.label"
                  @click="onSelectImageAsset(asset)"
                >
                  <img :src="asset.url || asset.file_url" :alt="asset.label" />
                  <span>{{ asset.source === 'upload' ? '上传' : '生成' }}</span>
                </button>
                <div v-if="currentImageAssets.length === 0" class="history-empty">暂无历史图片</div>
              </div>
              <button
                type="button"
                class="undo-image-btn"
                :disabled="!imageUndoStack[currentIndex]?.length"
                @click="undoImageReplacement(currentIndex)"
              >
                撤销
              </button>
            </div>

            <label class="field">
              <span>画面描述</span>
              <textarea v-model="imagePromptDraft" placeholder="AI 图片生成提示词" @blur="saveCurrentImagePrompt"></textarea>
            </label>

            <label class="field">
              <span>字幕文案</span>
              <textarea v-model="textDraft" placeholder="请输入字幕文案" @blur="saveCurrentText"></textarea>
            </label>

            <label class="field">
              <span>重配音音色</span>
              <select v-model="selectedVoiceType" class="voice-select">
                <option v-for="voice in voiceOptions" :key="voice.id" :value="voice.id">{{ voice.name }} · {{ voiceGenderLabel(voice.gender) }}</option>
              </select>
            </label>

            <div class="edit-actions">
              <button type="button" class="secondary-btn" @click="saveCurrentText">保存文案</button>
              <button type="button" class="primary-btn" @click="onRegenerateImage(currentIndex)">重生图片</button>
              <button type="button" class="primary-btn" @click="onRegenerateAudio(currentIndex)">重生配音</button>
            </div>
          </div>

          <div v-else-if="editTab === 'assets'" class="asset-body">
            <div class="asset-toolbar">
              <div class="asset-filters">
                <button v-for="filter in assetFilters" :key="filter.key" type="button" :class="{ active: assetFilter === filter.key }" @click="switchAssetFilter(filter.key)">{{ filter.label }}</button>
              </div>
              <button type="button" class="download-all-btn" @click="downloadAssets">下载全部</button>
            </div>

            <div v-loading="assetsLoading" element-loading-text="加载中..." class="asset-container">
              <div v-if="!assetsLoading && filteredAssets.length === 0" class="asset-empty">暂无素材</div>
              <div v-else-if="!assetsLoading" class="asset-list">
                <article v-for="asset in filteredAssets" :key="asset.asset_id" class="asset-item" :class="{ missing: !asset.has_file }">
                  <img v-if="asset.asset_type === 'image' && asset.has_file" :src="asset.url || asset.file_url" :alt="asset.label" />
                  <audio v-else-if="asset.asset_type === 'audio' && asset.has_file" :src="asset.url || asset.file_url" controls></audio>
                  <div v-else-if="asset.asset_type === 'subtitle'" class="subtitle-file">SRT</div>
                  <div v-else class="missing-file">缺失</div>
                  <div class="asset-info">
                    <strong>{{ formatAssetLabel(asset) }}</strong>
                    <span>{{ assetMeta(asset) }}</span>
                  </div>
                  <div class="asset-actions">
                    <button v-if="asset.asset_type === 'image'" type="button" :disabled="!asset.has_file" @click="onSelectImageAsset(asset)">应用</button>
                    <button type="button" :disabled="!asset.has_file" @click="downloadAsset(asset)">下载</button>
                  </div>
                </article>
              </div>
            </div>
          </div>

          <div v-else class="mine-body">
            <div class="field">
              <span>剪映草稿默认位置</span>
              <div class="mine-input-group">
                <input v-model.trim="mineSettings.extractPath" class="mine-input" placeholder="D:\\JianyingPro Drafts" @input="saveMineSettings" />
                <button type="button" class="folder-select-btn" :disabled="folderPicking" @click="chooseDraftFolder">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                    <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
                  </svg>
                  {{ folderPicking ? '选择中...' : '选择' }}
                </button>
              </div>
            </div>

            <div class="field">
              <span>默认导出模式</span>
              <div class="export-mode-switch">
                <button type="button" :class="{ active: mineSettings.defaultExport === 'mp4' }" @click="setDefaultExport('mp4')">MP4 成片</button>
                <button type="button" :class="{ active: mineSettings.defaultExport === 'draft' }" @click="setDefaultExport('draft')">剪映草稿 ZIP</button>
              </div>
            </div>

            <button type="button" class="primary-btn full-btn" @click="router.push(`/export/${taskId}`)">进入导出中心</button>
          </div>
        </aside>
      </template>
      </div>
    </main>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox, ElLoading } from 'element-plus'
import {
  getAssetsDownloadUrl,
  getSegments,
  getTaskAssets,
  getTaskRenderConfig,
  getTaskStatus,
  getVoices,
  regenerateAudio,
  regenerateImage,
  renderPreview,
  selectDraftFolder,
  selectSegmentImage,
  updateSegment,
  uploadImage,
} from '../api/task'
import NavBar from '../components/NavBar.vue'
import SegmentCard from '../components/SegmentCard.vue'

const route = useRoute()
const router = useRouter()
const taskId = route.params.taskId
const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:2002'
const loading = ref(true)
const renderingPreview = ref(false)
const segments = ref([])
const currentIndex = ref(0)
const editTab = ref('edit')
const textDraft = ref('')
const imagePromptDraft = ref('')
const imageUndoStack = ref({})
const assets = ref([])
const assetsLoading = ref(false)
const assetFilter = ref('all')
const voiceOptions = ref([])
const selectedVoiceType = ref('')
const taskVoiceType = ref('')
const mineSettings = ref({
  extractPath: '',
  defaultExport: 'mp4',
})
const folderPicking = ref(false)
const isPlaying = ref(false)
const playbackMode = ref('sequence')
const playbackProgress = ref(0)
const playbackTime = ref(0)
const audioEl = ref(null)
const precisePreviewUrl = ref('')
const renderConfig = ref({
  canvas: { width: 1920, height: 1080, fps: 30, aspect_ratio: 16 / 9 },
  duration: { default_seconds: 4 },
  subtitle: { font_size_ratio: 0.055, border_width: 3, y_ratio: 0.88 },
  fade: { seconds: 0.3 },
  animations: [],
  segment_durations: [],
})
const imageUndoStorageKey = `kepu:image-undo:${taskId}`
const imageError = ref(false)
let fallbackTimer = null
let fallbackStarted = 0
let fallbackDuration = 4000

const editTabs = [
  { key: 'edit', label: '修改段落' },
  { key: 'assets', label: '素材库' },
  { key: 'mine', label: '我的' },
]
const assetFilters = [
  { key: 'all', label: '全部' },
  { key: 'image', label: '图片素材' },
  { key: 'audio', label: '音频素材' },
  { key: 'subtitle', label: '字幕素材' },
  { key: 'upload', label: '历史上传' },
]

const currentSegment = computed(() => segments.value[currentIndex.value] || null)
const currentImageAssets = computed(() => {
  const list = assets.value.filter(asset => asset.has_file && asset.asset_type === 'image' && Number(asset.segment_index) === currentIndex.value)
  const seen = new Set()
  return list.filter(asset => {
    const key = asset.path || asset.url || asset.file_url
    if (!key || seen.has(key)) return false
    seen.add(key)
    return true
  })
})
const filteredAssets = computed(() => {
  let filtered = []

  if (assetFilter.value === 'all') {
    // 全部：每个分镜显示一个图片 + 一个音频
    const result = []
    segments.value.forEach((segment, index) => {
      // 获取该分镜的图片（优先当前使用的）
      const imageAsset = assets.value.find(asset =>
        asset.asset_type === 'image' &&
        Number(asset.segment_index) === index &&
        asset.has_file &&
        (asset.path === segment.image_path || asset.url === segment.image_url || asset.file_url === segment.image_url)
      ) || assets.value.find(asset =>
        asset.asset_type === 'image' &&
        Number(asset.segment_index) === index &&
        asset.has_file
      )

      // 获取该分镜的音频（优先当前使用的）
      const audioAsset = assets.value.find(asset =>
        asset.asset_type === 'audio' &&
        Number(asset.segment_index) === index &&
        asset.has_file &&
        (asset.path === segment.audio_path || asset.url === segment.audio_url || asset.file_url === segment.audio_url)
      ) || assets.value.find(asset =>
        asset.asset_type === 'audio' &&
        Number(asset.segment_index) === index &&
        asset.has_file
      )

      if (imageAsset) result.push(imageAsset)
      if (audioAsset) result.push(audioAsset)
    })
    filtered = result
  } else if (assetFilter.value === 'image') {
    // 图片：每个分镜只显示一个图片（当前使用的）
    const result = []
    segments.value.forEach((segment, index) => {
      const imageAsset = assets.value.find(asset =>
        asset.asset_type === 'image' &&
        Number(asset.segment_index) === index &&
        asset.has_file &&
        (asset.path === segment.image_path || asset.url === segment.image_url || asset.file_url === segment.image_url)
      ) || assets.value.find(asset =>
        asset.asset_type === 'image' &&
        Number(asset.segment_index) === index &&
        asset.has_file
      )
      if (imageAsset) result.push(imageAsset)
    })
    filtered = result
  } else if (assetFilter.value === 'upload') {
    filtered = assets.value.filter(asset => asset.source === 'upload')
    // 按 segment_index 排序
    filtered.sort((a, b) => {
      const indexA = Number(a.segment_index ?? -1)
      const indexB = Number(b.segment_index ?? -1)
      if (indexA !== indexB) return indexA - indexB
      return (a.asset_id || '').localeCompare(b.asset_id || '')
    })
  } else {
    // 音频、字幕等其他类型
    filtered = assets.value.filter(asset => asset.asset_type === assetFilter.value)
    // 按 segment_index 排序
    filtered.sort((a, b) => {
      const indexA = Number(a.segment_index ?? -1)
      const indexB = Number(b.segment_index ?? -1)
      if (indexA !== indexB) return indexA - indexB
      return (a.asset_id || '').localeCompare(b.asset_id || '')
    })
  }

  return filtered
})
const previewSubtitleText = computed(() => cleanSubtitleText(textDraft.value || currentSegment.value?.text || ''))
const currentAnimation = computed(() => renderConfig.value.animations?.[currentIndex.value] || { anim_type: 0, scale_end: 1.08 })
const currentDuration = computed(() => {
  return getSegmentDuration(currentIndex.value)
})
const timeline = computed(() => {
  let cursor = 0
  const entries = segments.value.map((segment, index) => {
    const duration = getSegmentDuration(index, segment)
    const entry = { index, start: cursor, end: cursor + duration, duration }
    cursor += duration
    return entry
  })
  return { entries, total: cursor }
})
const currentTimelineEntry = computed(() => timeline.value.entries[currentIndex.value] || null)
const segmentPlaybackRatio = computed(() => {
  const entry = currentTimelineEntry.value
  if (!entry) return 0
  return Math.min(1, Math.max(0, (playbackTime.value - entry.start) / Math.max(0.1, entry.duration)))
})
const playTimeLabel = computed(() => {
  const total = timeline.value.total
  return `${formatTime(playbackTime.value)} / ${formatTime(total)}`
})
const playbackSegmentLabel = computed(() => `${currentIndex.value + 1}/${segments.value.length || 0}`)
const currentSceneLabel = computed(() => `镜头 ${String(currentIndex.value + 1).padStart(2, '0')}`)
const currentSegmentDurationLabel = computed(() => `${formatTime(currentDuration.value)} / 镜头`)
const totalDurationLabel = computed(() => `${formatTime(timeline.value.total)} 总长`)
const canvasSizeLabel = computed(() => {
  const canvas = renderConfig.value.canvas || {}
  return `${Number(canvas.width || 1920)}x${Number(canvas.height || 1080)}`
})
const canvasRatioLabel = computed(() => {
  if (renderConfig.value.ratio) return renderConfig.value.ratio
  const canvas = renderConfig.value.canvas || {}
  return ratioLabelForCanvas(Number(canvas.width || 1920), Number(canvas.height || 1080))
})
const renderCanvasStyle = computed(() => {
  const canvas = renderConfig.value.canvas || {}
  const width = Number(canvas.width || 1920)
  const height = Number(canvas.height || 1080)
  const ratio = width / Math.max(1, height)
  return {
    aspectRatio: `${width} / ${height}`,
    '--canvas-ratio': ratio,
  }
})
const canvasAspectRatio = computed(() => {
  const canvas = renderConfig.value.canvas || {}
  return `${Number(canvas.width || 1920)} / ${Number(canvas.height || 1080)}`
})
const previewImageStyle = computed(() => {
  const progress = segmentPlaybackRatio.value
  const animation = currentAnimation.value
  const scale = 1 + ((Number(animation.scale_end) || 1.08) - 1) * progress
  const shift = buildAnimationShift(Number(animation.anim_type || 0), progress)
  return {
    transform: `translate(${shift.x}%, ${shift.y}%) scale(${scale})`,
    opacity: isPlaying.value ? previewOpacity(progress) : 1,
  }
})
const subtitleStyle = computed(() => {
  const subtitle = renderConfig.value.subtitle || {}
  const canvas = renderConfig.value.canvas || {}
  const canvasWidth = Number(canvas.width || 1920)
  const canvasHeight = Number(canvas.height || 1080)
  const aspectRatio = canvasWidth / canvasHeight
  const fontRatio = Number(subtitle.font_size_ratio || 0.055)
  const fitUnits = Math.max(22, subtitleVisualUnits(previewSubtitleText.value))
  const singleLineFitRatio = (aspectRatio * 0.86) / fitUnits
  const finalRatio = Math.min(fontRatio, singleLineFitRatio)
  const borderWidth = Number(subtitle.border_width || 3)
  return {
    bottom: `${Math.max(0, 100 - Number(subtitle.y_ratio || 0.88) * 100)}%`,
    fontSize: `clamp(12px, ${finalRatio * 100}cqh, 68px)`,
    WebkitTextStroke: `${borderWidth}px ${subtitle.border_color || '#000'}`,
    textShadow: `0 0 ${borderWidth}px ${subtitle.border_color || '#000'}`,
  }
})

onMounted(async () => {
  restoreMineSettings()
  await Promise.all([loadVoices(), loadTaskMeta()])
  if (taskVoiceType.value) selectedVoiceType.value = taskVoiceType.value
  await loadSegments()
  await loadAssets()
})
onBeforeUnmount(() => {
  clearFallbackTimer()
  audioEl.value?.pause()
})

watch(currentSegment, (segment) => {
  textDraft.value = segment?.text || ''
  imagePromptDraft.value = segment?.image_prompt || segment?.prompt || ''
  precisePreviewUrl.value = ''
}, { immediate: true })

watch(textDraft, () => {
  precisePreviewUrl.value = ''
})

watch(imagePromptDraft, () => {
  precisePreviewUrl.value = ''
})

watch(imageUndoStack, persistImageUndoStack, { deep: true })

async function loadSegments() {
  try {
    loading.value = true
    restoreImageUndoStack()
    segments.value = await getSegments(taskId)
    currentIndex.value = 0
    setPlaybackTime(0)
    await loadRenderConfig()
  } catch (error) {
    console.error('[PreviewView] 加载段落失败:', error)
    ElMessage.error('加载段落失败')
  } finally {
    loading.value = false
  }
}

async function loadTaskMeta() {
  try {
    const task = await getTaskStatus(taskId)
    taskVoiceType.value = task?.voice_type || ''
    if (!selectedVoiceType.value) selectedVoiceType.value = taskVoiceType.value
  } catch (error) {
    console.warn('[PreviewView] 任务元信息加载失败:', error)
  }
}

async function loadVoices() {
  try {
    const voices = await getVoices()
    voiceOptions.value = voices
    if (!selectedVoiceType.value && voices.length > 0) {
      const mizai = voices.find(voice => voice.name === '米仔')
      const mimoDefault = voices.find(voice => voice.id === '冰糖')
      selectedVoiceType.value = taskVoiceType.value || mizai?.id || mimoDefault?.id || voices[0].id
    }
  } catch (error) {
    console.warn('[PreviewView] 音色列表加载失败:', error)
  }
}

async function loadAssets() {
  try {
    assetsLoading.value = true
    assets.value = await getTaskAssets(taskId)
  } catch (error) {
    console.error('[PreviewView] 素材加载失败:', error)
    ElMessage.error('素材加载失败')
  } finally {
    assetsLoading.value = false
  }
}

async function loadRenderConfig() {
  try {
    const config = await getTaskRenderConfig(taskId)
    renderConfig.value = {
      ...renderConfig.value,
      ...config,
      canvas: { ...renderConfig.value.canvas, ...(config.canvas || {}) },
      duration: { ...renderConfig.value.duration, ...(config.duration || {}) },
      subtitle: { ...renderConfig.value.subtitle, ...(config.subtitle || {}) },
      fade: { ...renderConfig.value.fade, ...(config.fade || {}) },
      animations: config.animations || [],
      segment_durations: config.segment_durations || [],
    }
    setPlaybackTime(playbackTime.value)
  } catch (error) {
    console.warn('[PreviewView] 渲染配置加载失败，使用默认配置:', error)
  }
}

function handleNavigate(tab) {
  if (tab === 'settings') router.push('/settings')
  else if (tab === 'library') router.push({ path: '/', query: { tab: 'library' } })
  else router.push('/')
}

function onBack() { router.back() }

function selectSegment(index) {
  imageError.value = false
  seekToSegment(index)
  precisePreviewUrl.value = ''
  if (isPlaying.value) playCurrentSegment({ preserveOffset: false })
}

function previewSegment(index) {
  if (isPlaying.value && playbackMode.value === 'single' && currentIndex.value === index) {
    pausePlayback()
    return
  }
  imageError.value = false
  playbackMode.value = 'single'
  seekToSegment(index)
  precisePreviewUrl.value = ''
  isPlaying.value = true
  playCurrentSegment({ preserveOffset: false })
}

function handlePreviewImageError() {
  imageError.value = true
}

function handlePreviewImageLoad() {
  imageError.value = false
}

async function saveCurrentText() {
  const newText = textDraft.value || ''
  if (newText === currentSegment.value?.text) return
  await onEditSegment(currentIndex.value, newText)
}

async function saveCurrentImagePrompt() {
  const newPrompt = imagePromptDraft.value || ''
  if (newPrompt === (currentSegment.value?.image_prompt || '')) return
  try {
    await updateSegment(taskId, currentIndex.value, { image_prompt: newPrompt })
    segments.value[currentIndex.value].image_prompt = newPrompt
    precisePreviewUrl.value = ''
    ElMessage.success('画面描述已保存')
  } catch (error) {
    console.error('保存画面描述失败:', error)
    ElMessage.error('保存画面描述失败')
  }
}

function pushImageUndo(index, snapshot) {
  if (!snapshot?.image_url && !snapshot?.image_path) return
  const current = imageUndoStack.value[index] || []
  imageUndoStack.value = {
    ...imageUndoStack.value,
    [index]: [...current, snapshot].slice(-10),
  }
}

function restoreImageUndoStack() {
  try {
    const raw = window.localStorage.getItem(imageUndoStorageKey)
    imageUndoStack.value = raw ? JSON.parse(raw) || {} : {}
  } catch {
    imageUndoStack.value = {}
  }
}

function persistImageUndoStack() {
  try {
    window.localStorage.setItem(imageUndoStorageKey, JSON.stringify(imageUndoStack.value))
  } catch {
    // localStorage may be unavailable in strict browser modes.
  }
}

async function onEditSegment(index, newText) {
  try {
    await updateSegment(taskId, index, { text: newText })
    segments.value[index].text = newText
    precisePreviewUrl.value = ''
    ElMessage.success('保存成功')
  } catch (error) {
    console.error('保存段落失败:', error)
    ElMessage.error('保存失败')
  }
}

async function onRegenerateImage(index) {
  let loadingInstance
  try {
    if (index === currentIndex.value) await saveCurrentImagePrompt()
    await ElMessageBox.confirm('重新生成图片需要一定时间，确认继续吗？', '确认重新生成', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
    loadingInstance = ElLoading.service({ text: '生成中...', lock: true })
    const result = await regenerateImage(taskId, index)
    pushImageUndo(index, {
      image_url: result.previous_image_url || segments.value[index]?.image_url,
      image_path: result.previous_image_path || segments.value[index]?.image_path,
    })
    segments.value[index].image_url = result.image_url
    segments.value[index].image_path = result.image_path
    segments.value[index].image_prompt = result.image_prompt || segments.value[index].image_prompt || ''
    if (index === currentIndex.value) imagePromptDraft.value = segments.value[index].image_prompt || ''
    await loadAssets()
    precisePreviewUrl.value = ''
    ElMessage.success('图片生成成功')
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('图片生成失败')
  } finally {
    loadingInstance?.close()
  }
}

async function onRegenerateAudio(index) {
  let loadingInstance
  try {
    await ElMessageBox.confirm('重新生成音频需要一定时间，确认继续吗？', '确认重新生成', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
    loadingInstance = ElLoading.service({ text: '生成中...', lock: true })
    const result = await regenerateAudio(taskId, index, selectedVoiceType.value || taskVoiceType.value || null)
    segments.value[index].audio_url = result.audio_url
    await loadRenderConfig()
    await loadAssets()
    precisePreviewUrl.value = ''
    ElMessage.success('音频生成成功')
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('音频生成失败')
  } finally {
    loadingInstance?.close()
  }
}

async function onRenderPrecisePreview() {
  if (renderingPreview.value) return
  try {
    await saveCurrentText()
    renderingPreview.value = true
    ElMessage.info('正在生成最终预览，可继续使用顶部导航')
    const result = await renderPreview(taskId, null)
    precisePreviewUrl.value = `${result.preview_url}${result.preview_url.includes('?') ? '&' : '?'}t=${Date.now()}`
    pausePlayback()
    ElMessage.success('精准预览已生成')
  } catch (error) {
    console.error('精准预览生成失败:', error)
    ElMessage.error('精准预览生成失败')
  } finally {
    renderingPreview.value = false
  }
}

async function onUploadImage(index, file) {
  let loadingInstance
  try {
    loadingInstance = ElLoading.service({ text: '上传中...', lock: true })
    const result = await uploadImage(taskId, index, file)
    pushImageUndo(index, {
      image_url: result.previous_image_url || segments.value[index]?.image_url,
      image_path: result.previous_image_path || segments.value[index]?.image_path,
    })
    segments.value[index].image_url = result.image_url
    segments.value[index].image_path = result.image_path
    await loadAssets()
    precisePreviewUrl.value = ''
    ElMessage.success('图片上传成功')
  } catch (error) {
    console.error('上传图片失败:', error)
    ElMessage.error('图片上传失败')
  } finally {
    loadingInstance?.close()
  }
}

async function undoImageReplacement(index) {
  const stack = imageUndoStack.value[index] || []
  const previous = stack[stack.length - 1]
  if (!previous) return
  let loadingInstance
  try {
    loadingInstance = ElLoading.service({ text: '恢复中...', lock: true })
    await updateSegment(taskId, index, {
      image_url: previous.image_url,
      image_path: previous.image_path,
    })
    segments.value[index].image_url = previous.image_url
    segments.value[index].image_path = previous.image_path
    await loadAssets()
    imageUndoStack.value = {
      ...imageUndoStack.value,
      [index]: stack.slice(0, -1),
    }
    precisePreviewUrl.value = ''
    ElMessage.success('已恢复上一张图片')
  } catch (error) {
    console.error('恢复图片失败:', error)
    ElMessage.error('恢复图片失败')
  } finally {
    loadingInstance?.close()
  }
}

async function onSelectImageAsset(asset) {
  if (!asset?.asset_id) return
  if (isCurrentImageAsset(asset)) return
  let loadingInstance
  try {
    loadingInstance = ElLoading.service({ text: '切换中...', lock: true })
    const result = await selectSegmentImage(taskId, currentIndex.value, asset.asset_id)
    pushImageUndo(currentIndex.value, {
      image_url: result.previous_image_url || currentSegment.value?.image_url,
      image_path: result.previous_image_path || currentSegment.value?.image_path,
    })
    segments.value[currentIndex.value].image_url = result.image_url || asset.url || asset.file_url
    segments.value[currentIndex.value].image_path = result.image_path || asset.path
    segments.value[currentIndex.value].image_prompt = result.image_prompt || segments.value[currentIndex.value].image_prompt || ''
    imagePromptDraft.value = segments.value[currentIndex.value].image_prompt || ''
    await loadAssets()
    precisePreviewUrl.value = ''
    ElMessage.success('图片已切换')
  } catch (error) {
    console.error('切换图片失败:', error)
    ElMessage.error('切换图片失败')
  } finally {
    loadingInstance?.close()
  }
}

function isCurrentImageAsset(asset) {
  const current = currentSegment.value
  if (!current || !asset) return false
  return Boolean(
    (asset.path && current.image_path && asset.path === current.image_path) ||
    (asset.url && current.image_url && asset.url === current.image_url) ||
    (asset.file_url && current.image_url && asset.file_url === current.image_url)
  )
}

function switchAssetFilter(filter) {
  assetFilter.value = filter
  loadAssets()
}

function assetMeta(asset) {
  if (!asset.has_file) return '素材文件缺失，请重新生成'

  if (asset.asset_type === 'image') {
    return asset.prompt ? asset.prompt.slice(0, 42) : imageSourceLabel(asset.source)
  }
  if (asset.asset_type === 'audio') {
    return voiceName(asset.voice_type) || imageSourceLabel(asset.source)
  }
  return '项目 SRT 字幕文件'
}

function formatAssetLabel(asset) {
  // 根据分镜编号和类型生成标签
  if (asset.segment_index !== undefined) {
    const segmentNum = Number(asset.segment_index) + 1
    if (asset.asset_type === 'image') {
      return `分镜${segmentNum} - 图片`
    }
    if (asset.asset_type === 'audio') {
      return `分镜${segmentNum} - 音频`
    }
  }
  return asset.label || '素材'
}

function imageSourceLabel(source) {
  const map = { generated: 'AI 生成', regenerated: '重新生成', upload: '本地上传', selected: '历史选择', legacy: '历史素材', subtitle: '字幕素材' }
  return map[source] || '素材'
}

function voiceName(voiceType) {
  return voiceOptions.value.find(voice => voice.id === voiceType)?.name || ''
}

function voiceGenderLabel(gender) {
  if (gender === 'female') return '女声'
  if (gender === 'male') return '男声'
  return '自动'
}

function downloadAsset(asset) {
  const url = asset.download_url || asset.file_url || asset.url
  if (url) {
    window.open(url, '_blank')
    return
  }
  ElMessage.warning('素材文件缺失，请重新生成')
}

function downloadAssets() {
  window.open(`${baseURL}${getAssetsDownloadUrl(taskId, assetFilter.value === 'all' ? 'all' : assetFilter.value)}`, '_blank')
}

function restoreMineSettings() {
  mineSettings.value = {
    extractPath: localStorage.getItem('kepu:mine:extract_path') || localStorage.getItem('extract_path') || '',
    defaultExport: localStorage.getItem('kepu:mine:default_export') || 'mp4',
  }
}

function saveMineSettings() {
  localStorage.setItem('kepu:mine:extract_path', mineSettings.value.extractPath || '')
  localStorage.setItem('extract_path', mineSettings.value.extractPath || '')
  localStorage.setItem('kepu:mine:default_export', mineSettings.value.defaultExport || 'mp4')
}

function setDefaultExport(target) {
  mineSettings.value.defaultExport = target
  saveMineSettings()
  ElMessage.success('默认导出模式已保存')
}

async function chooseDraftFolder() {
  try {
    folderPicking.value = true
    ElMessage.info('请在弹出的窗口里选择剪映草稿目录')
    const result = await selectDraftFolder(taskId)
    mineSettings.value.extractPath = result.path || ''
    saveMineSettings()
    if (result.warnings?.length) {
      ElMessage.warning(result.warnings[0])
    } else {
      ElMessage.success('已选择剪映草稿目录')
    }
  } catch (error) {
    console.error('选择剪映草稿目录失败:', error)
    ElMessage.error(error?.response?.data?.detail || '未选择文件夹')
  } finally {
    folderPicking.value = false
  }
}

function onCurrentImageSelected(event) {
  const file = event.target.files?.[0]
  if (file) {
    onUploadImage(currentIndex.value, file)
    event.target.value = ''
  }
}

function onRebuild() {
  router.push(`/export/${taskId}`)
}

function togglePlayback() {
  if (isPlaying.value) {
    pausePlayback()
    return
  }
  playbackMode.value = 'sequence'
  isPlaying.value = true
  playCurrentSegment({ preserveOffset: true })
}

async function playCurrentSegment({ preserveOffset = true } = {}) {
  clearFallbackTimer()
  const audio = audioEl.value
  if (!audio || !currentSegment.value) return
  audio.pause()
  const entry = currentTimelineEntry.value
  const segmentOffset = preserveOffset && entry ? Math.max(0, playbackTime.value - entry.start) : 0
  if (!preserveOffset && entry) setPlaybackTime(entry.start)
  if (currentSegment.value.audio_url) {
    audio.src = currentSegment.value.audio_url
    audio.onerror = () => {
      console.warn('音频加载失败，使用 fallback timer')
      startFallbackTimer(segmentOffset)
    }
    await nextTick()
    await waitForAudioMetadata(audio)
    if (Number.isFinite(audio.duration) && audio.duration > 0) {
      audio.currentTime = Math.min(segmentOffset, Math.max(0, audio.duration - 0.05))
    }
    audio.play().catch(() => {
      ElMessage.warning('音频播放失败，使用静默预览')
      startFallbackTimer(segmentOffset)
    })
  } else {
    audio.removeAttribute('src')
    startFallbackTimer(segmentOffset)
  }
}

function pausePlayback() {
  isPlaying.value = false
  audioEl.value?.pause()
  clearFallbackTimer()
}

function playNextSegment() {
  if (!isPlaying.value) return
  if (playbackMode.value === 'single') {
    isPlaying.value = false
    const entry = currentTimelineEntry.value
    if (entry) setPlaybackTime(entry.end, { syncIndex: false })
    return
  }
  if (currentIndex.value < segments.value.length - 1) {
    seekToSegment(currentIndex.value + 1)
    playCurrentSegment({ preserveOffset: false })
  } else {
    isPlaying.value = false
    setPlaybackTime(timeline.value.total)
  }
}

function onAudioTimeUpdate() {
  const audio = audioEl.value
  if (!audio || !audio.duration || Number.isNaN(audio.duration)) return
  const entry = currentTimelineEntry.value
  if (!entry) return
  setPlaybackTime(entry.start + Math.min(audio.currentTime, entry.duration), { syncIndex: false })
}

function startFallbackTimer(offsetSeconds = 0) {
  fallbackStarted = Date.now() - offsetSeconds * 1000
  fallbackDuration = Math.max(1000, currentDuration.value * 1000)
  fallbackTimer = window.setInterval(() => {
    const elapsed = Date.now() - fallbackStarted
    const entry = currentTimelineEntry.value
    if (entry) setPlaybackTime(entry.start + Math.min(elapsed / 1000, entry.duration), { syncIndex: false })
    if (elapsed >= fallbackDuration) {
      clearFallbackTimer()
      playNextSegment()
    }
  }, 120)
}

function clearFallbackTimer() {
  if (fallbackTimer) {
    window.clearInterval(fallbackTimer)
    fallbackTimer = null
  }
}

function seekByClick(event) {
  const rect = event.currentTarget.getBoundingClientRect()
  const pct = Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width))
  const targetTime = timeline.value.total * pct
  setPlaybackTime(targetTime)
  const audio = audioEl.value
  if (isPlaying.value) {
    playbackMode.value = 'sequence'
    playCurrentSegment({ preserveOffset: true })
  } else if (audio?.duration) {
    const entry = currentTimelineEntry.value
    audio.currentTime = entry ? Math.max(0, targetTime - entry.start) : 0
  }
}

function seekToSegment(index) {
  const entry = timeline.value.entries[index]
  currentIndex.value = Math.min(Math.max(index, 0), Math.max(segments.value.length - 1, 0))
  setPlaybackTime(entry?.start || 0, { syncIndex: false })
}

function setPlaybackTime(seconds, { syncIndex = true } = {}) {
  const total = Math.max(0, timeline.value.total)
  const nextTime = Math.min(Math.max(0, seconds || 0), total)
  playbackTime.value = nextTime
  playbackProgress.value = total > 0 ? Math.min(100, (nextTime / total) * 100) : 0
  if (!syncIndex) return

  const entries = timeline.value.entries
  const match = entries.find((entry) => nextTime >= entry.start && nextTime < entry.end)
  if (match) {
    currentIndex.value = match.index
  } else if (entries.length) {
    currentIndex.value = entries.length - 1
  }
}

function getSegmentDuration(index, segment = segments.value[index]) {
  const configured = renderConfig.value.segment_durations?.[index]
  const segmentDuration = segment?.duration
  return Math.max(0.5, Number(configured || segmentDuration || renderConfig.value.duration?.default_seconds || 4))
}

function formatTime(seconds) {
  const totalSeconds = Math.max(0, Math.floor(seconds || 0))
  const minutes = Math.floor(totalSeconds / 60)
  const remain = totalSeconds % 60
  return `${minutes}:${String(remain).padStart(2, '0')}`
}

function ratioLabelForCanvas(width, height) {
  const ratio = width / Math.max(1, height)
  if (Math.abs(ratio - 16 / 9) < 0.08) return '16:9'
  if (Math.abs(ratio - 9 / 16) < 0.08) return '9:16'
  if (Math.abs(ratio - 3 / 4) < 0.08) return '3:4'
  const divisor = gcd(Math.round(width), Math.round(height))
  return `${Math.round(width / divisor)}:${Math.round(height / divisor)}`
}

function gcd(a, b) {
  let x = Math.abs(a)
  let y = Math.abs(b)
  while (y) {
    const next = x % y
    x = y
    y = next
  }
  return x || 1
}

function cleanSubtitleText(text) {
  return String(text || '')
    .trim()
    .replace(/^[“”"‘’'「」『』《》〈〉]+/g, '')
    .replace(/[，,。\.、；;：:！!？?…~～“”"‘’'「」『』《》〈〉\s]+$/g, '')
}

function subtitleVisualUnits(text) {
  return Array.from(String(text || '')).reduce((sum, char) => {
    if (/\s/.test(char)) return sum + 0.35
    if (/[\x00-\x7F]/.test(char)) return sum + 0.55
    return sum + 1
  }, 0)
}

function waitForAudioMetadata(audio) {
  if (audio.readyState >= 1) return Promise.resolve()
  return new Promise((resolve) => {
    const cleanup = () => {
      audio.removeEventListener('loadedmetadata', onReady)
      audio.removeEventListener('error', onReady)
      window.clearTimeout(timer)
      resolve()
    }
    const onReady = () => cleanup()
    const timer = window.setTimeout(cleanup, 1200)
    audio.addEventListener('loadedmetadata', onReady, { once: true })
    audio.addEventListener('error', onReady, { once: true })
  })
}

function buildAnimationShift(animType, progress) {
  const distanceX = 1.5
  const distanceY = 1
  const t = 1 - progress
  if (animType === 1) return { x: distanceX * t, y: 0 }
  if (animType === 2) return { x: -distanceX * t, y: 0 }
  if (animType === 3) return { x: 0, y: distanceY * t }
  if (animType === 4) return { x: 0, y: -distanceY * t }
  if (animType === 5) return { x: distanceX * t, y: distanceY * t }
  if (animType === 6) return { x: -distanceX * t, y: -distanceY * t }
  return { x: 0, y: 0 }
}

function previewOpacity(progress) {
  const fadeSeconds = Number(renderConfig.value.fade?.seconds || 0.3)
  const fadeRatio = Math.min(0.45, fadeSeconds / Math.max(1, currentDuration.value))
  if (progress < fadeRatio) return progress / fadeRatio
  if (progress > 1 - fadeRatio) return Math.max(0, (1 - progress) / fadeRatio)
  return 1
}
</script>

<style scoped>
.preview-view {
  height: 100vh;
  background: #f3f5f8;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.workbench {
  height: calc(100vh - 64px);
  padding: 12px;
  overflow: hidden;
}

.workbench-content {
  height: 100%;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(230px, 260px) minmax(520px, 1fr) minmax(270px, 292px);
  gap: 12px;
  overflow: hidden;
}

.workbench-content > .el-empty,
.empty-state {
  grid-column: 1 / -1;
  display: grid;
  place-items: center;
  min-height: 360px;
}

.storyboard-panel,
.preview-panel,
.edit-panel {
  min-height: 0;
  background: var(--color-card);
  border: 1px solid rgba(29, 29, 31, 0.08);
  border-radius: 18px;
  box-shadow: 0 10px 30px rgba(20, 23, 31, 0.06);
}

.storyboard-panel,
.edit-panel {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.panel-title {
  height: 52px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  border-bottom: 1px solid rgba(29, 29, 31, 0.08);
}

.panel-title h2 {
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 0;
  color: var(--color-text);
}

.panel-title span {
  font-size: 12px;
  color: var(--color-text-tertiary);
  letter-spacing: 0;
}

.segment-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 8px;
  display: grid;
  align-content: start;
  gap: 6px;
}

.preview-panel {
  min-width: 0;
  display: grid;
  grid-template-rows: minmax(0, 1fr) auto;
  overflow: hidden;
}

.media-stage {
  position: relative;
  min-height: 0;
  background:
    linear-gradient(180deg, rgba(255,255,255,0.055), rgba(255,255,255,0)),
    #0b0d11;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
  overflow: hidden;
  padding: 14px 16px 12px;
}

.stage-topbar,
.stage-footer {
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  color: rgba(245, 247, 250, 0.74);
  font-size: 11px;
  letter-spacing: 0;
}

.stage-topbar {
  padding-bottom: 10px;
}

.stage-footer {
  padding-top: 10px;
}

.stage-status,
.stage-meta {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  white-space: nowrap;
}

.stage-status {
  color: rgba(255, 255, 255, 0.9);
  font-weight: 600;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #5ee0a0;
  box-shadow: 0 0 12px rgba(94, 224, 160, 0.72);
}

.stage-meta {
  overflow: hidden;
  justify-content: flex-end;
}

.stage-meta span,
.stage-footer span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
}

.stage-meta span {
  padding: 3px 7px;
  border: 1px solid rgba(255,255,255,0.11);
  border-radius: 999px;
  background: rgba(255,255,255,0.055);
}

.stage-shell {
  min-width: 0;
  min-height: 0;
  display: grid;
  place-items: center;
  container-type: size;
  border-radius: 14px;
  background:
    linear-gradient(90deg, rgba(255,255,255,0.025) 1px, transparent 1px),
    linear-gradient(0deg, rgba(255,255,255,0.025) 1px, transparent 1px),
    #08090c;
  background-size: 28px 28px;
  box-shadow: inset 0 0 0 1px rgba(255,255,255,0.055);
}

.render-canvas {
  position: relative;
  width: min(100cqw, calc(100cqh * var(--canvas-ratio)));
  height: min(100cqh, calc(100cqw / var(--canvas-ratio)));
  background: #000;
  overflow: hidden;
  container-type: size;
  border-radius: 6px;
  box-shadow:
    0 22px 80px rgba(0,0,0,0.42),
    0 0 0 1px rgba(255,255,255,0.08);
}

.render-canvas img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  will-change: transform, opacity;
  transition: transform 0.1s linear, opacity 0.1s linear;
}

.stage-empty {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  color: rgba(255,255,255,0.58);
  font-size: 13px;
  background:
    radial-gradient(circle at center, rgba(255,255,255,0.06), transparent 52%),
    #050506;
}

.stage-error {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: #ee0a24;
  background: rgba(0, 0, 0, 0.85);
}

.stage-error svg {
  width: 48px;
  height: 48px;
}

.stage-error p {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
}

.stage-error .error-detail {
  font-size: 12px;
  font-weight: 400;
  color: #999;
  max-width: 300px;
  text-align: center;
  word-break: break-word;
}

.subtitle-overlay {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  width: 86%;
  color: #fff;
  font-weight: 700;
  line-height: 1;
  letter-spacing: 0;
  text-align: center;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: clip;
  paint-order: stroke fill;
  pointer-events: none;
  filter: drop-shadow(0 3px 10px rgba(0,0,0,0.38));
}

.precise-video {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: contain;
  background: #000;
  z-index: 4;
}

.close-preview-btn {
  position: absolute;
  top: 12px;
  right: 12px;
  z-index: 5;
  height: 28px;
  padding: 0 11px;
  border: 1px solid rgba(255,255,255,0.24);
  border-radius: 999px;
  background: rgba(0,0,0,0.64);
  backdrop-filter: blur(12px);
  color: #fff;
  font-size: 12px;
  cursor: pointer;
}

.playbar {
  min-height: 58px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  align-items: center;
  gap: 14px;
  padding: 0 14px;
  border-top: 1px solid rgba(29, 29, 31, 0.08);
  background: #fff;
}

.playback-main {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 12px;
}

.play-btn {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: var(--color-primary);
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all var(--duration-normal) var(--ease-out);
  color: #ffffff;
}

.play-btn:hover {
  background: var(--color-primary-hover);
}

.play-btn:active {
  transform: scale(0.95);
}

.play-btn svg {
  width: 14px;
  height: 14px;
}

.play-track {
  flex: 1;
  height: 6px;
  border-radius: 999px;
  background: #e8ebf0;
  overflow: hidden;
  cursor: pointer;
}

.play-fill {
  height: 100%;
  border-radius: inherit;
  background: var(--color-primary);
  transition: width 0.1s;
}

.play-time {
  font-size: 11px;
  color: var(--color-text-secondary);
  font-family: var(--font-mono);
  white-space: nowrap;
}

.playback-meta {
  display: grid;
  gap: 2px;
  justify-items: end;
  line-height: 1.2;
}

.play-segment {
  font-size: 10px;
  color: var(--color-text-tertiary);
  white-space: nowrap;
}

.preview-action-btn {
  height: 34px;
  padding: 0 14px;
  border: 1px solid #111318;
  border-radius: 999px;
  background: #111318;
  color: #fff;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
}

.preview-action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.hidden-audio {
  display: none;
}

.edit-tabs {
  display: flex;
  gap: 4px;
  padding: 10px;
  border-bottom: 1px solid rgba(29, 29, 31, 0.08);
  background: #fff;
}

.edit-tabs button {
  flex: 1;
  min-height: 30px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
  border: none;
  background: transparent;
  color: var(--color-text-tertiary);
  cursor: pointer;
  transition: all 0.2s;
}

.edit-tabs button.active {
  color: var(--color-text);
  background: #f0f2f5;
  box-shadow: inset 0 0 0 1px rgba(29, 29, 31, 0.06);
}

.edit-tabs button:hover {
  color: var(--color-text);
}

.edit-body,
.asset-body,
.mine-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 12px;
  display: grid;
  align-content: start;
  gap: 12px;
}

.upload-box {
  height: 72px;
  border: 1px dashed rgba(29, 29, 31, 0.24);
  border-radius: 8px;
  background: #f7f8fa;
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: var(--color-text-tertiary);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.upload-box:hover {
  border-color: rgba(29, 29, 31, 0.58);
  background: #fff;
}

.upload-box input {
  display: none;
}

.upload-box svg {
  width: 20px;
  height: 20px;
}

.undo-image-btn {
  min-width: 48px;
  min-height: 48px;
  border: 1px solid rgba(29, 29, 31, 0.12);
  border-radius: 8px;
  background: #fff;
  color: var(--color-text-secondary);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
}

.undo-image-btn:hover:not(:disabled) {
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.undo-image-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.image-history-row {
  min-width: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
  align-items: stretch;
}

.history-strip {
  min-width: 0;
  min-height: 48px;
  display: flex;
  gap: 6px;
  overflow-x: auto;
  padding-bottom: 2px;
}

.history-thumb {
  position: relative;
  width: 64px;
  height: 48px;
  flex: 0 0 auto;
  overflow: hidden;
  border: 1px solid transparent;
  border-radius: 8px;
  background: #f1f3f6;
  cursor: pointer;
}

.history-thumb.active {
  border-color: var(--color-primary);
}

.history-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.history-thumb span {
  position: absolute;
  left: 4px;
  bottom: 4px;
  padding: 1px 4px;
  border-radius: 4px;
  background: rgba(0,0,0,0.58);
  color: #fff;
  font-size: 10px;
}

.history-empty,
.asset-empty {
  min-height: 52px;
  display: grid;
  place-items: center;
  color: var(--color-text-tertiary);
  font-size: 12px;
}

.voice-select {
  width: 100%;
  min-height: 36px;
  padding: 0 10px;
  border: 1px solid rgba(29, 29, 31, 0.13);
  border-radius: 8px;
  background: #f7f8fa;
  color: var(--color-text);
  outline: none;
  font-size: 12px;
}

.voice-select:focus {
  border-color: var(--color-accent);
  background: #fff;
  box-shadow: 0 0 0 4px rgba(0, 113, 227, 0.1);
}

.mine-input-group {
  display: flex;
  gap: 8px;
  align-items: center;
}

.mine-input {
  flex: 1;
  height: 36px;
  padding: 0 12px;
  border: 1px solid rgba(29, 29, 31, 0.13);
  border-radius: 8px;
  background: #f7f8fa;
  color: var(--color-text);
  outline: none;
}

.mine-input:focus {
  border-color: var(--color-accent);
  background: #fff;
  box-shadow: 0 0 0 4px rgba(0, 113, 227, 0.1);
}

.folder-select-btn {
  height: 36px;
  padding: 0 12px;
  display: flex;
  align-items: center;
  gap: 6px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: #fff;
  color: var(--color-text-secondary);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
}

.folder-select-btn:hover:not(:disabled) {
  border-color: var(--color-primary);
  color: var(--color-primary);
  background: var(--color-primary-bg);
}

.folder-select-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.field {
  display: grid;
  gap: 6px;
}

.field span {
  font-size: 11px;
  font-weight: 700;
  color: var(--color-text-secondary);
  letter-spacing: 0;
}

.field textarea {
  width: 100%;
  height: 88px;
  resize: none;
  padding: 10px;
  border: 1px solid rgba(29, 29, 31, 0.13);
  border-radius: 8px;
  background: #f7f8fa;
  color: var(--color-text);
  font-size: 12px;
  line-height: 1.55;
  outline: none;
}

.field textarea:focus {
  border-color: var(--color-accent);
  background: #fff;
  box-shadow: 0 0 0 4px rgba(0, 113, 227, 0.1);
}

.edit-actions {
  display: grid;
  grid-template-columns: 0.9fr 1fr 1fr;
  gap: 7px;
}

.primary-btn,
.secondary-btn {
  flex: 1;
  justify-content: center;
  min-height: 34px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 4px;
  transition: all var(--duration-normal) var(--ease-out);
  padding: 8px 12px;
  white-space: nowrap;
}

.primary-btn {
  border: none;
  background: var(--color-primary);
  color: #ffffff;
  box-shadow: var(--shadow-sm);
}

.primary-btn:hover {
  background: var(--color-primary-hover);
  transform: scale(1.02);
}

.primary-btn:active {
  transform: scale(0.98);
}

.secondary-btn {
  border: 1px solid rgba(29, 29, 31, 0.16);
  background: #fff;
  color: var(--color-text-secondary);
}

.secondary-btn:hover {
  border-color: rgba(29, 29, 31, 0.42);
  background: #f7f8fa;
}

.asset-toolbar {
  display: grid;
  gap: 10px;
}

.asset-filters {
  display: flex;
  gap: 6px;
  overflow-x: auto;
}

.asset-filters button,
.download-all-btn,
.asset-actions button {
  min-height: 30px;
  padding: 0 10px;
  border: 1px solid rgba(29, 29, 31, 0.13);
  border-radius: 999px;
  background: #fff;
  color: var(--color-text-secondary);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
}

.asset-filters button.active {
  border-color: var(--color-primary);
  background: var(--color-primary-bg);
  color: var(--color-primary);
}

.download-all-btn {
  width: 100%;
  color: #fff;
  background: #111318;
  border-color: #111318;
}

.asset-loading {
  min-height: 120px;
}

.asset-list {
  display: grid;
  gap: 10px;
}

.asset-item {
  display: grid;
  grid-template-columns: 64px minmax(0, 1fr);
  gap: 9px;
  padding: 9px;
  border: 1px solid rgba(29, 29, 31, 0.1);
  border-radius: 8px;
  background: #fff;
}

.asset-item img,
.subtitle-file,
.missing-file {
  width: 64px;
  height: 48px;
  border-radius: 6px;
  object-fit: cover;
  background: var(--color-bg-secondary);
}

.asset-item audio {
  grid-column: 1 / -1;
  width: 100%;
  height: 32px;
}

.subtitle-file,
.missing-file {
  display: grid;
  place-items: center;
  color: var(--color-primary);
  font-size: 13px;
  font-weight: 800;
}

.asset-item.missing {
  border-style: dashed;
  background: #fff7f7;
}

.missing-file {
  color: var(--color-danger);
  background: #ffecec;
}

.asset-actions button:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.asset-info {
  min-width: 0;
  display: grid;
  align-content: start;
  gap: 4px;
}

.asset-info strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
}

.asset-info span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--color-text-tertiary);
  font-size: 11px;
}

.asset-actions {
  grid-column: 1 / -1;
  display: flex;
  gap: 8px;
}

.asset-actions button {
  flex: 1;
}

.export-mode-switch {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.export-mode-switch button {
  min-height: 36px;
  border: 1px solid rgba(29, 29, 31, 0.13);
  border-radius: 999px;
  background: #fff;
  color: var(--color-text-secondary);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}

.export-mode-switch button.active {
  border-color: #111318;
  background: #111318;
  color: #fff;
}

.full-btn {
  width: 100%;
}

@media (max-width: 1120px) {
  .workbench-content {
    grid-template-columns: minmax(220px, 260px) minmax(0, 1fr);
  }
  .edit-panel {
    grid-column: 1 / -1;
    min-height: 320px;
  }
}

@media (max-width: 760px) {
  .preview-view {
    overflow: auto;
  }
  .workbench {
    height: auto;
    overflow: visible;
    padding: 10px;
  }
  .workbench-content {
    height: auto;
    grid-template-columns: 1fr;
    overflow: visible;
  }
  .storyboard-panel,
  .edit-panel {
    min-height: 320px;
  }
  .preview-panel {
    min-height: 420px;
    order: -1;
  }
  .media-stage {
    min-height: 360px;
    padding: 12px;
  }
  .stage-topbar,
  .stage-footer {
    align-items: flex-start;
  }
  .stage-meta {
    flex-wrap: wrap;
  }
  .playbar {
    grid-template-columns: 1fr;
    gap: 8px;
    padding: 10px;
  }
  .playback-meta {
    grid-template-columns: auto auto;
    justify-content: space-between;
    justify-items: start;
  }
  .subtitle-overlay {
    width: 90%;
  }
  .edit-actions {
    grid-template-columns: 1fr;
  }
}
</style>
