<template>
  <div class="preview-page">
    <NavBar active-tab="" :show-actions="taskState.canExport" @navigate="handleNavigate" @export="openExport" />

    <main class="preview-layout">
      <aside class="project-rail">
        <div class="project-cover">
          <img v-if="currentImageUrl" :src="currentImageUrl" alt="项目封面" />
          <span v-else>暂无封面</span>
          <em v-if="currentSegment">片段 {{ currentIndex + 1 }}</em>
        </div>
        <div class="project-title">
          <span>项目</span>
          <h1>{{ taskTitle }}</h1>
        </div>

        <section class="rail-segments" v-if="orderedSegments.length > 0">
          <div class="rail-section-head">
            <strong>分镜导航</strong>
            <span>{{ currentIndex + 1 }} / {{ orderedSegments.length }}</span>
          </div>
          <button
            v-for="(segment, index) in orderedSegments"
            :key="segment.id || index"
            type="button"
            class="rail-segment-card"
            :class="{ active: index === currentIndex }"
            @click="selectSegment(index)"
          >
            <span class="rail-shot-index">{{ String(index + 1).padStart(2, '0') }}</span>
            <span class="rail-shot-thumb">
              <img v-if="segmentImageUrl(segment)" :src="segmentImageUrl(segment)" :alt="`分镜 ${index + 1}`" />
              <em v-else>缺失</em>
            </span>
            <span class="rail-shot-copy">
              <small>{{ segment.text || '暂无文案' }}</small>
            </span>
            <span :class="['rail-shot-state', segmentStatusTone(segment)]">{{ segmentStatusText(segment) }}</span>
          </button>
        </section>

        <div class="project-meta-card compact-meta">
          <div>
            <span>比例</span>
            <strong>{{ videoRatioLabel }}</strong>
          </div>
          <div>
            <span>总时长</span>
            <strong>{{ totalDurationLabel }}</strong>
          </div>
          <div>
            <span>任务状态</span>
            <strong>{{ taskStatusLabel }}</strong>
          </div>
        </div>
        <div class="asset-note compact">
          <CircleCheck />
          <span>{{ taskState.canExport ? '素材可导出' : '素材可恢复' }}</span>
        </div>
      </aside>

      <section class="preview-workspace">
        <div v-if="loading" class="loading-state">正在加载分镜...</div>
        <el-empty v-else-if="segments.length === 0" description="暂无分镜数据，任务可能仍在生成或尚未保存资产。" />

        <template v-else>
          <div class="preview-toolbar">
            <div>项目 <span>›</span> 预览编辑</div>
          </div>
          <section class="player-panel">
            <div class="player-frame" :class="ratioClass">
              <img v-if="currentImageUrl" :src="currentImageUrl" :alt="`分镜 ${currentIndex + 1}`" />
              <div v-else class="missing-frame">暂无画面</div>
              <div class="subtitle" :style="subtitleStyle">{{ displaySubtitle }}</div>
            </div>
            <div class="player-controls">
              <button type="button" @click="togglePlay">
                <VideoPause v-if="playing" />
                <VideoPlay v-else />
              </button>
              <span>{{ currentTimeLabel }}</span>
              <input v-model.number="timelineValue" type="range" min="0" :max="Math.max(segments.length - 1, 0)" step="1" @input="selectSegment(timelineValue)" />
              <span>{{ totalDurationLabel }}</span>
            </div>
          </section>

          <section class="segment-panel">
            <div class="segment-toolbar">
              <strong>分镜表格</strong>
              <button type="button" @click="regenerateCurrentImage">重生图片</button>
              <button type="button" @click="regenerateCurrentAudio">重配音</button>
              <button type="button" @click="triggerUpload">上传替换</button>
              <button type="button" @click="saveSegmentText">保存片段</button>
              <span class="toolbar-spacer"></span>
              <button type="button" @click="selectSegment(Math.max(currentIndex - 1, 0))">上一段</button>
              <button type="button" @click="selectSegment(Math.min(currentIndex + 1, orderedSegments.length - 1))">下一段</button>
              <button type="button" :disabled="renderingPreview" @click="renderFinalPreview">
                <Refresh />
                {{ renderingPreview ? '生成中' : '预览' }}
              </button>
            </div>

            <div class="segment-table">
              <div class="table-row table-head">
                <span>#</span>
                <span>时间</span>
                <span>文案</span>
                <span>画面</span>
                <span>配音</span>
                <span>状态</span>
                <span>操作</span>
              </div>
              <button
                v-for="(segment, index) in orderedSegments"
                :key="segment.id || index"
                type="button"
                class="table-row"
                :class="{ active: index === currentIndex }"
                @click="selectSegment(index)"
              >
                <strong>{{ String(index + 1).padStart(2, '0') }}</strong>
                <span>{{ segmentTime(index, segment) }}</span>
                <span class="script-cell">{{ segment.text || '暂无文案' }}</span>
                <span class="thumb-cell">
                  <img v-if="segmentImageUrl(segment)" :src="segmentImageUrl(segment)" :alt="`画面 ${index + 1}`" />
                  <em v-else>缺失</em>
                </span>
                <span>{{ segment.audio_url ? '已生成' : '缺失' }}</span>
                <span :class="['status-pill', segmentStatusTone(segment)]">{{ segmentStatusText(segment) }}</span>
                <span class="row-actions">···</span>
              </button>
            </div>
          </section>
        </template>
      </section>

      <aside class="inspector" v-if="!loading && currentSegment">
        <div class="inspector-top">
          <div class="section-head">
            <p>片段设置</p>
            <h2>片段 {{ currentIndex + 1 }}</h2>
          </div>
          <div class="segment-nav">
            <button type="button" @click="selectSegment(Math.max(currentIndex - 1, 0))">‹</button>
            <button type="button" @click="selectSegment(Math.min(currentIndex + 1, orderedSegments.length - 1))">›</button>
            <button type="button" @click="router.push('/assets')">×</button>
          </div>
        </div>

        <div class="range-line">
          <span>片段范围</span>
          <strong>{{ segmentTime(currentIndex, currentSegment) }}</strong>
        </div>

        <div class="media-info-grid">
          <label>
            <span>视频比例</span>
            <strong>{{ videoRatioLabel }}</strong>
          </label>
          <label>
            <span>画布尺寸</span>
            <strong>{{ canvasSizeLabel }}</strong>
          </label>
          <label>
            <span>图片尺寸</span>
            <strong>{{ currentImageSizeLabel }}</strong>
          </label>
        </div>

        <label class="field">
          <span>提示词 Prompt</span>
          <textarea v-model="imagePromptDraft" maxlength="800" placeholder="描述这一段需要生成的画面"></textarea>
          <small>{{ imagePromptDraft.length }}/800</small>
          <button type="button" class="smart-btn" @click="optimizePrompt">智能优化</button>
        </label>

        <section class="style-section">
          <div class="section-title-row">
            <span>图像风格</span>
          </div>
          <div class="style-grid">
            <div v-for="style in visualStyles" :key="style.value" class="style-choice">
              <img :src="style.image" :alt="style.label" />
              <strong>{{ style.label }}</strong>
            </div>
          </div>
        </section>

        <label class="field">
          <span>配音音色</span>
          <select v-model="selectedVoiceType">
            <option value="">沿用任务音色</option>
            <option v-for="voice in voices" :key="voice.id" :value="voice.id">{{ voice.name }}</option>
          </select>
        </label>

        <label class="field compact-text">
          <span>字幕文案</span>
          <textarea v-model="textDraft" maxlength="1000" placeholder="当前分镜字幕文案"></textarea>
        </label>

        <section class="subtitle-settings">
          <div>
            <span>启用字幕</span>
            <strong>开启</strong>
          </div>
          <div>
            <span>字幕位置</span>
            <strong>底部安全区</strong>
          </div>
        </section>

        <div class="button-grid">
          <button type="button" class="surface-button" @click="saveSegmentText">保存文案</button>
          <button type="button" class="surface-button" @click="triggerUpload">上传替换</button>
          <button type="button" class="surface-button" :disabled="busyAction === 'image'" @click="regenerateCurrentImage">{{ busyAction === 'image' ? '生成中...' : '重生图片' }}</button>
          <button type="button" class="surface-button" :disabled="busyAction === 'audio'" @click="regenerateCurrentAudio">{{ busyAction === 'audio' ? '生成中...' : '重配音' }}</button>
        </div>
        <input ref="uploadInput" type="file" accept="image/*" hidden @change="onUploadSelected" />

        <div class="asset-strip">
          <div class="strip-head">
            <span>历史素材</span>
            <button type="button" @click="loadAssets">刷新</button>
          </div>
          <div class="asset-list">
            <button v-for="asset in imageAssets" :key="asset.asset_id" type="button" :disabled="!asset.has_file" @click="selectImageAsset(asset)">
              <img :src="asset.url || asset.file_url" :alt="asset.label" />
            </button>
            <span v-if="imageAssets.length === 0">暂无历史图片</span>
          </div>
        </div>

        <div class="asset-warning">
          当前页直接读取任务分镜和素材表。即使任务失败，已生成的图片、配音和文案仍会在这里保留。
        </div>

        <button type="button" :class="['export-btn', taskState.canExport ? 'primary-action' : 'surface-button']" @click="openExport">
          {{ taskState.canExport ? '导出视频' : '查看导出状态' }}
        </button>
      </aside>
    </main>

    <footer v-if="!loading && currentSegment" class="preview-bottom">
      <button type="button" class="surface-button" @click="router.push('/assets')">返回项目资产</button>
      <button type="button" class="surface-button" :disabled="renderingPreview" @click="renderFinalPreview">生成最终预览</button>
      <button type="button" :class="taskState.canExport ? 'primary-action' : 'surface-button'" @click="openExport">
        {{ taskState.canExport ? '导出视频' : '查看导出状态' }}
      </button>
    </footer>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  CircleCheck,
  Refresh,
  VideoPause,
  VideoPlay,
} from '@element-plus/icons-vue'
import NavBar from '../components/NavBar.vue'
import {
  getSegments,
  getTaskAssets,
  getExportState,
  getTaskStatus,
  getVoices,
  regenerateAudio,
  regenerateImage,
  renderPreview,
  selectSegmentImage,
  updateSegment,
  uploadImage,
} from '../api/task'
import { visualStyles } from '../utils/projectDrafts'
import { normalizeMediaUrl } from '../utils/mediaUrl'
import { deriveTaskState, ratioClassName, ratioLabel } from '../utils/taskState'

const route = useRoute()
const router = useRouter()
const taskId = route.params.taskId
const loading = ref(true)
const task = ref(null)
const exportState = ref(null)
const segments = ref([])
const currentIndex = ref(0)
const timelineValue = ref(0)
const playing = ref(false)
const renderingPreview = ref(false)
const busyAction = ref('')
const voices = ref([])
const assets = ref([])
const imagePromptDraft = ref('')
const textDraft = ref('')
const selectedVoiceType = ref('')
const uploadInput = ref(null)
const currentImageSize = ref(null)

const orderedSegments = computed(() => [...segments.value].sort((a, b) => Number(a.segment_index ?? 0) - Number(b.segment_index ?? 0)))
const currentSegment = computed(() => orderedSegments.value[currentIndex.value] || null)
const taskTitle = computed(() => task.value?.result?.theme || task.value?.name || `任务 ${String(taskId).slice(0, 8)}`)
const taskState = computed(() => deriveTaskState({ task: task.value, segments: orderedSegments.value, exportState: exportState.value }))
const taskStatusLabel = computed(() => taskState.value.label)
const totalSeconds = computed(() => orderedSegments.value.reduce((sum, item) => sum + (Number(item.duration) || 7), 0))
const totalDurationLabel = computed(() => secondsToLabel(totalSeconds.value))
const currentTimeLabel = computed(() => secondsToLabel(orderedSegments.value.slice(0, currentIndex.value).reduce((sum, item) => sum + (Number(item.duration) || 7), 0)))
const videoRatio = computed(() => exportState.value?.ratio || task.value?.ratio || task.value?.result?.ratio || '16:9')
const videoRatioLabel = computed(() => ratioLabel(videoRatio.value))
const ratioClass = computed(() => ratioClassName(videoRatio.value))
const currentImageUrl = computed(() => normalizeMediaUrl(currentSegment.value?.image_url))
const displaySubtitle = computed(() => normalizeSubtitleText(currentSegment.value?.text || '暂无字幕文案'))
const subtitleStyle = computed(() => ({ fontSize: `${subtitleFontSize(displaySubtitle.value, videoRatio.value)}px` }))
const canvasSizeLabel = computed(() => {
  const canvas = exportState.value?.canvas
  if (!canvas?.width || !canvas?.height) return '未读取'
  return `${canvas.width}x${canvas.height}`
})
const currentImageSizeLabel = computed(() => {
  if (!currentImageUrl.value) return '未生成'
  if (!currentImageSize.value?.width || !currentImageSize.value?.height) return '读取中'
  return `${currentImageSize.value.width}x${currentImageSize.value.height}`
})
const imageAssets = computed(() => assets.value.filter((asset) => asset.asset_type === 'image' && Number(asset.segment_index) === Number(currentSegment.value?.segment_index)))

onMounted(loadPage)

watch(currentSegment, (segment) => {
  imagePromptDraft.value = segment?.image_prompt || ''
  textDraft.value = segment?.text || ''
  timelineValue.value = currentIndex.value
}, { immediate: true })

watch(currentImageUrl, (url) => {
  currentImageSize.value = null
  if (!url) return
  const image = new Image()
  image.onload = () => {
    currentImageSize.value = {
      width: image.naturalWidth,
      height: image.naturalHeight,
    }
  }
  image.onerror = () => {
    currentImageSize.value = { width: 0, height: 0 }
  }
  image.src = url
}, { immediate: true })

async function loadPage() {
  loading.value = true
  try {
    const [taskData, segmentData, exportData, voiceData] = await Promise.all([
      getTaskStatus(taskId),
      getSegments(taskId),
      getExportState(taskId).catch(() => null),
      getVoices().catch(() => []),
    ])
    task.value = taskData
    segments.value = Array.isArray(segmentData) ? segmentData : []
    exportState.value = exportData
    voices.value = voiceData
    await loadAssets()
  } catch (error) {
    console.error('加载预览页失败', error)
    ElMessage.error('加载预览页失败')
  } finally {
    loading.value = false
  }
}

async function loadAssets() {
  try {
    assets.value = await getTaskAssets(taskId)
  } catch (error) {
    assets.value = []
  }
}

function selectSegment(index) {
  currentIndex.value = Number(index)
  timelineValue.value = Number(index)
}

function segmentImageUrl(segment) {
  return normalizeMediaUrl(segment?.image_url)
}

function normalizeSubtitleText(value) {
  const compact = String(value || '').replace(/\s+/g, ' ').trim()
  const clean = compact
    .replace(/^[。！？!?…，,；;、：:“”"‘’'「」『』《》〈〉]+/u, '')
    .replace(/[。！？!?…，,；;、：:“”"‘’'「」『』《》〈〉\s]+$/u, '')
  return clean || compact
}

function subtitleFontSize(text, ratio) {
  const units = Array.from(text || '').reduce((sum, char) => {
    if (/\s/.test(char)) return sum + 0.35
    return sum + (char.charCodeAt(0) < 128 ? 0.55 : 1)
  }, 0)
  const safeUnits = ratio === '9:16' ? 18 : ratio === '3:4' ? 23 : 34
  const baseSize = 16
  if (!units || units <= safeUnits) return baseSize
  return Math.max(11, Math.floor(baseSize * safeUnits / units))
}

function togglePlay() {
  playing.value = !playing.value
  if (playing.value) {
    const next = Math.min(currentIndex.value + 1, orderedSegments.value.length - 1)
    window.setTimeout(() => {
      if (playing.value) selectSegment(next)
      if (next === orderedSegments.value.length - 1) playing.value = false
    }, 800)
  }
}

async function saveSegmentText() {
  const segment = currentSegment.value
  if (!segment) return
  await updateSegment(taskId, segment.segment_index ?? currentIndex.value, {
    text: textDraft.value,
    image_prompt: imagePromptDraft.value,
  })
  segment.text = textDraft.value
  segment.image_prompt = imagePromptDraft.value
  ElMessage.success('片段已保存')
}

function optimizePrompt() {
  const base = imagePromptDraft.value || textDraft.value || currentSegment.value?.text || ''
  imagePromptDraft.value = `${base}\n画面要求：主体清晰、风格统一、适合知识解说视频，构图留出字幕安全区。`
}

async function regenerateCurrentImage() {
  const segment = currentSegment.value
  if (!segment) return
  busyAction.value = 'image'
  try {
    await saveSegmentText()
    const result = await regenerateImage(taskId, segment.segment_index ?? currentIndex.value)
    segment.image_url = normalizeMediaUrl(result.image_url || segment.image_url)
    segment.image_status = 'completed'
    await loadAssets()
    ElMessage.success('图片已重新生成')
  } finally {
    busyAction.value = ''
  }
}

async function regenerateCurrentAudio() {
  const segment = currentSegment.value
  if (!segment) return
  busyAction.value = 'audio'
  try {
    await saveSegmentText()
    const result = await regenerateAudio(taskId, segment.segment_index ?? currentIndex.value, selectedVoiceType.value || null)
    segment.audio_url = result.audio_url || segment.audio_url
    segment.audio_status = 'completed'
    await loadAssets()
    ElMessage.success('配音已重新生成')
  } finally {
    busyAction.value = ''
  }
}

function triggerUpload() {
  uploadInput.value?.click()
}

async function onUploadSelected(event) {
  const file = event.target.files?.[0]
  const segment = currentSegment.value
  if (!file || !segment) return
  busyAction.value = 'upload'
  try {
    const result = await uploadImage(taskId, segment.segment_index ?? currentIndex.value, file)
    segment.image_url = normalizeMediaUrl(result.image_url || segment.image_url)
    await loadAssets()
    ElMessage.success('图片已替换')
  } finally {
    busyAction.value = ''
    event.target.value = ''
  }
}

async function selectImageAsset(asset) {
  const segment = currentSegment.value
  if (!segment) return
  await selectSegmentImage(taskId, segment.segment_index ?? currentIndex.value, asset.asset_id)
  segment.image_url = normalizeMediaUrl(asset.url || asset.file_url)
  ElMessage.success('已应用历史图片')
}

async function renderFinalPreview() {
  renderingPreview.value = true
  try {
    await renderPreview(taskId)
    ElMessage.success('最终预览已生成')
  } finally {
    renderingPreview.value = false
  }
}

function openExport() {
  if (!taskState.value.canExport) {
    ElMessage.warning('素材缺失或最终预览不可用，请先补齐素材或生成最终预览')
  }
  router.push(`/export/${taskId}`)
}

function segmentTime(index, segment) {
  const start = orderedSegments.value.slice(0, index).reduce((sum, item) => sum + (Number(item.duration) || 7), 0)
  const end = start + (Number(segment.duration) || 7)
  return `${secondsToLabel(start)}-${secondsToLabel(end)}`
}

function segmentStatusText(segment) {
  if (segment.image_status === 'failed') return '图片失败'
  if (segment.audio_status === 'failed') return '配音失败'
  if (!segment.image_url || !segment.audio_url) return '素材缺失'
  return '已生成'
}

function segmentStatusTone(segment) {
  if (segment.image_status === 'failed' || segment.audio_status === 'failed') return 'danger'
  if (!segment.image_url || !segment.audio_url) return 'warning'
  return 'success'
}

function secondsToLabel(value) {
  const seconds = Math.max(0, Math.round(Number(value) || 0))
  const min = Math.floor(seconds / 60)
  const sec = seconds % 60
  return `${String(min).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
}

function handleNavigate(tab) {
  if (tab === 'settings') router.push('/settings')
  else if (tab === 'library') router.push('/assets')
  else router.push('/')
}

</script>

<style scoped>
.preview-page {
  min-height: 100vh;
  padding-bottom: 64px;
}

.preview-layout {
  height: calc(100vh - 120px);
  min-height: 720px;
  display: grid;
  grid-template-columns: 236px minmax(0, 1fr) 360px;
}

.project-rail,
.inspector {
  overflow: auto;
  padding: 22px 20px 82px;
  background: rgba(255, 255, 255, 0.78);
}

.project-rail {
  border-right: 1px solid var(--color-border);
  display: flex;
  flex-direction: column;
}

.inspector {
  border-left: 1px solid var(--color-border);
}

.project-cover {
  position: relative;
  display: grid;
  place-items: center;
  overflow: hidden;
  aspect-ratio: 16 / 9;
  margin-bottom: 12px;
  border: 1px solid var(--color-border);
  border-radius: 12px;
  background:
    linear-gradient(135deg, rgba(17, 24, 39, 0.06), rgba(15, 98, 254, 0.06)),
    #f5f7fb;
  color: var(--color-text-tertiary);
  font-weight: 800;
}

.project-cover img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.project-cover em {
  position: absolute;
  right: 8px;
  bottom: 8px;
  padding: 4px 8px;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.76);
  color: #fff;
  font-size: 12px;
  font-style: normal;
  font-weight: 800;
}

.project-title {
  margin-bottom: 14px;
}

.project-title span,
.section-head p {
  color: var(--color-text-tertiary);
  font-size: 12px;
  font-weight: 800;
}

.project-title h1 {
  font-size: 18px;
  line-height: 1.3;
}

.project-meta-card {
  display: grid;
  gap: 1px;
  overflow: hidden;
  margin: 18px 0;
  border: 1px solid var(--color-border);
  border-radius: 10px;
  background: var(--color-divider);
}

.project-meta-card div {
  display: flex;
  justify-content: space-between;
  background: #fff;
  padding: 11px 12px;
}

.project-meta-card span {
  color: var(--color-text-secondary);
}

.project-meta-card strong {
  color: var(--color-text);
}

.project-rail svg {
  width: 17px;
}

.rail-segments {
  display: grid;
  gap: 8px;
  margin: 4px 0 14px;
}

.rail-section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: var(--color-text-secondary);
  font-size: 13px;
}

.rail-section-head strong {
  color: var(--color-text);
}

.rail-section-head span {
  font-weight: 800;
}

.rail-segment-card {
  display: grid;
  grid-template-columns: 28px 58px minmax(0, 1fr);
  grid-template-areas:
    "idx thumb copy"
    "idx thumb state";
  align-items: center;
  gap: 6px 8px;
  min-height: 62px;
  border: 1px solid var(--color-border);
  border-radius: 10px;
  background: #fff;
  padding: 7px;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.18s var(--ease-out), background 0.18s var(--ease-out), transform 0.18s var(--ease-out);
}

.rail-segment-card:hover {
  border-color: #c8d4e4;
  transform: translateY(-1px);
}

.rail-segment-card.active {
  border-color: var(--color-primary);
  background: #f7faff;
  box-shadow: inset 3px 0 0 var(--color-primary);
}

.rail-shot-index {
  grid-area: idx;
  align-self: start;
  color: var(--color-text);
  font-size: 13px;
  font-weight: 900;
}

.rail-shot-thumb {
  grid-area: thumb;
  display: grid;
  place-items: center;
  width: 58px;
  height: 40px;
  overflow: hidden;
  border-radius: 7px;
  background: #111318;
  color: #fff;
  font-size: 11px;
  font-weight: 800;
}

.rail-shot-thumb img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.rail-shot-copy {
  grid-area: copy;
  min-width: 0;
}

.rail-shot-copy small {
  display: -webkit-box;
  overflow: hidden;
  color: var(--color-text-secondary);
  font-size: 12px;
  line-height: 1.35;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.rail-shot-state {
  grid-area: state;
  justify-self: start;
  padding: 2px 7px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 800;
}

.rail-shot-state.success {
  background: var(--color-success-bg);
  color: var(--color-success);
}

.rail-shot-state.warning {
  background: var(--color-warning-bg);
  color: #a16207;
}

.rail-shot-state.danger {
  background: var(--color-danger-bg);
  color: var(--color-danger);
}

.asset-note {
  display: flex;
  gap: 10px;
  margin-top: 18px;
  border-radius: 12px;
  background: var(--color-success-bg);
  color: var(--color-success);
  padding: 12px;
  font-size: 13px;
  font-weight: 700;
}

.asset-note.compact {
  margin-top: 14px;
}

.asset-note svg {
  width: 18px;
  flex: 0 0 auto;
}

.preview-workspace {
  min-width: 0;
  overflow: auto;
  padding: 12px 24px 82px;
}

.preview-toolbar {
  height: 30px;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  margin-bottom: 8px;
}

.preview-toolbar div {
  margin-right: auto;
  color: var(--color-text-secondary);
  font-weight: 700;
}

.preview-toolbar span {
  margin: 0 8px;
  color: var(--color-text-tertiary);
}

.loading-state {
  height: 100%;
  display: grid;
  place-items: center;
  color: var(--color-text-secondary);
}

.player-panel,
.segment-panel {
  border: 1px solid var(--color-border);
  border-radius: 10px;
  background: #fff;
  box-shadow: var(--shadow-xs);
}

.player-frame {
  position: relative;
  width: 100%;
  overflow: hidden;
  border-radius: 10px 10px 0 0;
  background:
    radial-gradient(circle at 50% 30%, rgba(255, 255, 255, 0.08), transparent 42%),
    #111318;
  aspect-ratio: 16 / 9;
}

.player-frame.ratio-vertical {
  width: min(100%, 380px);
  margin: 0 auto;
  aspect-ratio: 9 / 16;
}

.player-frame.ratio-square {
  width: min(100%, 620px);
  margin: 0 auto;
  aspect-ratio: 1 / 1;
}

.player-frame.ratio-portrait {
  width: min(100%, 470px);
  margin: 0 auto;
  aspect-ratio: 3 / 4;
}

.player-frame.ratio-classic {
  width: min(100%, 760px);
  margin: 0 auto;
  aspect-ratio: 4 / 3;
}

.player-frame img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.missing-frame {
  height: 100%;
  display: grid;
  place-items: center;
  color: #fff;
}

.subtitle {
  position: absolute;
  left: 11%;
  right: 11%;
  bottom: 30px;
  overflow: hidden;
  padding: 0;
  border-radius: 0;
  background: transparent;
  color: #fff;
  text-align: center;
  font-size: 16px;
  font-weight: 800;
  line-height: 1.45;
  white-space: nowrap;
  text-overflow: ellipsis;
  text-shadow: 0 2px 10px rgba(0, 0, 0, 0.74), 0 1px 2px rgba(0, 0, 0, 0.86);
  pointer-events: none;
}

.player-controls {
  height: 38px;
  display: grid;
  grid-template-columns: 42px auto 1fr auto 42px;
  align-items: center;
  gap: 14px;
  padding: 0 16px;
}

.player-controls button {
  width: 32px;
  height: 32px;
  border: 0;
  border-radius: 10px;
  background: #f4f6fb;
  cursor: pointer;
}

.player-controls svg {
  width: 18px;
}

.segment-panel {
  margin-top: 8px;
  padding: 10px;
}

.section-head h2 {
  font-size: 18px;
}

.segment-toolbar button {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 0 12px;
}

.segment-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
  padding: 6px 8px;
  border: 1px solid var(--color-border);
  border-radius: 10px;
  background: #f8fafc;
}

.segment-toolbar strong {
  margin-right: 2px;
  color: var(--color-text);
  white-space: nowrap;
}

.toolbar-spacer {
  flex: 1;
}

.segment-toolbar button {
  height: 30px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: #fff;
  color: var(--color-text-secondary);
  font-weight: 800;
  white-space: nowrap;
  cursor: pointer;
}

.segment-table {
  display: grid;
  overflow: hidden;
  border: 1px solid var(--color-border);
  border-radius: 12px;
}

.table-row {
  display: grid;
  grid-template-columns: 42px 92px minmax(220px, 1fr) 98px 76px 86px 44px;
  align-items: center;
  gap: 10px;
  min-height: 46px;
  border: 0;
  border-bottom: 1px solid var(--color-divider);
  background: #fff;
  padding: 0 10px;
  text-align: left;
  cursor: pointer;
}

.table-row:last-child {
  border-bottom: 0;
}

.table-head {
  min-height: 32px;
  background: #f8fafc;
  color: var(--color-text-secondary);
  font-weight: 800;
  cursor: default;
}

.table-row.active {
  outline: 2px solid var(--color-primary);
  outline-offset: -2px;
  background: #fbfdff;
}

.script-cell {
  display: -webkit-box;
  overflow: hidden;
  color: var(--color-text-secondary);
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.thumb-cell img {
  width: 78px;
  height: 38px;
  border-radius: 6px;
  object-fit: contain;
  background: #111318;
}

.thumb-cell em {
  color: var(--color-danger);
  font-style: normal;
}

.row-actions {
  color: var(--color-text-tertiary);
  text-align: center;
  font-size: 18px;
}

.inspector-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
}

.section-head {
  margin-bottom: 12px;
}

.segment-nav {
  display: flex;
  gap: 8px;
}

.segment-nav button {
  width: 34px;
  height: 34px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: #fff;
  color: var(--color-text-secondary);
  cursor: pointer;
  font-size: 18px;
  font-weight: 900;
}

.range-line {
  display: flex;
  justify-content: space-between;
  margin-bottom: 10px;
  border-radius: 10px;
  background: #f8fafc;
  padding: 10px 12px;
}

.media-info-grid {
  display: grid;
  grid-template-columns: 1.05fr 1fr 1fr;
  gap: 8px;
  margin-bottom: 12px;
}

.media-info-grid label {
  display: grid;
  gap: 6px;
}

.media-info-grid span {
  color: var(--color-text-secondary);
  font-weight: 800;
}

.media-info-grid strong {
  min-height: 36px;
  display: flex;
  align-items: center;
  border: 1px solid var(--color-border);
  border-radius: 9px;
  background: #fff;
  padding: 0 10px;
  color: var(--color-text);
  font-size: 13px;
}

.range-line span,
.field span,
.style-section > span {
  color: var(--color-text-secondary);
  font-weight: 800;
}

.field {
  display: grid;
  gap: 6px;
  margin-bottom: 12px;
}

.field textarea,
.field select {
  width: 100%;
  border: 1px solid var(--color-border);
  border-radius: 10px;
  background: #fff;
  outline: 0;
}

.field textarea {
  min-height: 78px;
  resize: vertical;
  padding: 10px 12px;
}

.field.compact-text textarea {
  min-height: 58px;
}

.field small {
  justify-self: end;
  color: var(--color-text-tertiary);
}

.field select {
  height: 42px;
  padding: 0 12px;
}

.smart-btn {
  justify-self: end;
  height: 32px;
  border: 0;
  border-radius: 8px;
  background: var(--color-primary-bg);
  color: var(--color-primary);
  padding: 0 10px;
  font-weight: 800;
  cursor: pointer;
}

.style-section {
  margin-bottom: 12px;
}

.section-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.style-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 7px;
  margin-top: 7px;
}

.style-choice {
  display: grid;
  gap: 4px;
  border: 1px solid var(--color-border);
  border-radius: 10px;
  background: #fff;
  padding: 5px;
}

.style-grid img {
  width: 100%;
  aspect-ratio: 16 / 7;
  border-radius: 8px;
  object-fit: cover;
}

.button-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.subtitle-settings {
  display: grid;
  gap: 1px;
  overflow: hidden;
  margin-bottom: 14px;
  border: 1px solid var(--color-border);
  border-radius: 10px;
  background: var(--color-divider);
}

.subtitle-settings div {
  display: flex;
  justify-content: space-between;
  background: #fff;
  padding: 10px 12px;
}

.subtitle-settings span {
  color: var(--color-text-secondary);
  font-weight: 800;
}

.subtitle-settings strong {
  color: var(--color-primary);
}

.asset-strip {
  margin-top: 22px;
}

.strip-head {
  display: flex;
  justify-content: space-between;
  margin-bottom: 10px;
  color: var(--color-text-secondary);
  font-weight: 800;
}

.strip-head button {
  border: 0;
  background: transparent;
  color: var(--color-primary);
  cursor: pointer;
}

.asset-list {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
}

.asset-list button {
  border: 1px solid var(--color-border);
  border-radius: 8px;
  overflow: hidden;
  background: #fff;
  cursor: pointer;
}

.asset-list img {
  width: 100%;
  aspect-ratio: 1;
  object-fit: cover;
}

.asset-list span {
  grid-column: 1 / -1;
  color: var(--color-text-tertiary);
}

.asset-warning {
  margin-top: 20px;
  border: 1px solid #f0d99e;
  border-radius: 10px;
  background: var(--color-warning-bg);
  color: var(--color-text-secondary);
  padding: 12px;
  font-size: 13px;
  line-height: 1.6;
}

.export-btn {
  width: 100%;
  margin-top: 24px;
}

.preview-bottom {
  position: fixed;
  right: 28px;
  left: auto;
  bottom: 10px;
  z-index: 30;
  width: min(520px, calc(100vw - 56px));
  height: 52px;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 14px;
  padding: 0 18px;
  border: 1px solid var(--color-border);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(18px);
  box-shadow: var(--shadow-md);
}

.preview-bottom button {
  min-width: 148px;
  padding: 0 16px;
}

@media (max-width: 1240px) {
  .preview-layout {
    grid-template-columns: minmax(0, 1fr) 340px;
  }

  .project-rail {
    display: none;
  }
}
</style>
