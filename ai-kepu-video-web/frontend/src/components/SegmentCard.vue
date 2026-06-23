<template>
  <article class="segment-card" :class="{ active }" @click="emit('select', index)">
    <div class="segment-thumb" @click.stop="previewImage">
      <img
        v-if="segment.image_url && imageLoadState !== 'error'"
        :src="segment.image_url"
        :alt="`分镜 ${index + 1}`"
        @error="handleImageError"
        @load="handleImageLoad"
      />
      <div v-else-if="imageLoadState === 'error' || segment.image_status === 'failed'" class="thumb-error">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10"/>
          <line x1="12" y1="8" x2="12" y2="12"/>
          <line x1="12" y1="16" x2="12.01" y2="16"/>
        </svg>
        <span class="error-text">加载失败</span>
      </div>
      <div v-else class="thumb-empty">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
      </div>
    </div>

    <div class="segment-main">
      <div class="segment-meta">
        <span class="segment-index">镜头 {{ String(index + 1).padStart(2, '0') }}</span>
        <span class="time-code">{{ timeCode }}</span>
      </div>
      <div v-if="segment.image_status === 'failed' || segment.audio_status === 'failed'" class="error-badges">
        <span v-if="segment.image_status === 'failed'" class="error-badge">
          <svg viewBox="0 0 24 24" fill="currentColor" width="10" height="10">
            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/>
          </svg>
          图片失败
        </span>
        <span v-if="segment.audio_status === 'failed'" class="error-badge">
          <svg viewBox="0 0 24 24" fill="currentColor" width="10" height="10">
            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/>
          </svg>
          音频失败
        </span>
      </div>
      <p :class="{ placeholder: !segment.text }">{{ segment.text || '点击编辑文案' }}</p>
      <div v-if="previewPlaying || previewProgress > 0" class="segment-preview-track">
        <div class="segment-preview-fill" :style="{ width: `${Math.round(previewProgress * 100)}%` }"></div>
      </div>
      <div class="segment-tools">
        <button
          type="button"
          title="单段预览"
          :class="{ playing: previewPlaying }"
          :disabled="!segment.audio_url && !segment.image_url"
          @click.stop="emit('preview-segment', index)"
        >
          <svg v-if="!previewPlaying" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>
          <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="6" y="5" width="4" height="14"/><rect x="14" y="5" width="4" height="14"/></svg>
        </button>
        <button type="button" title="重新生成图片" @click.stop="emit('regenerate-image', index)">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M21 15l-5-5L5 21"/></svg>
        </button>
        <button type="button" title="更换图片" @click.stop="imageInput?.click()">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
        </button>
        <button type="button" title="撤销图片替换" :disabled="!canUndoImage" @click.stop="emit('undo-image', index)">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 14 4 9l5-5"/><path d="M4 9h10a6 6 0 0 1 0 12h-3"/></svg>
        </button>
        <button type="button" title="重新生成音频" @click.stop="emit('regenerate-audio', index)">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg>
        </button>
      </div>
    </div>

    <input ref="imageInput" type="file" accept="image/jpeg,image/jpg,image/png,image/webp" class="hidden-input" @change="onImageSelected" />

    <el-image-viewer
      v-if="showImageViewer"
      :url-list="previewImages"
      :initial-index="0"
      @close="showImageViewer = false"
    />
  </article>
</template>

<script setup>
import { computed, ref } from 'vue'
import { ElImageViewer } from 'element-plus'

const props = defineProps({
  segment: { type: Object, required: true },
  index: { type: Number, required: true },
  active: { type: Boolean, default: false },
  aspectRatio: { type: String, default: '16 / 9' },
  previewPlaying: { type: Boolean, default: false },
  previewProgress: { type: Number, default: 0 },
  canUndoImage: { type: Boolean, default: false },
})
const emit = defineEmits(['select', 'edit', 'preview-segment', 'regenerate-image', 'regenerate-audio', 'upload-image', 'undo-image'])
const imageInput = ref(null)
const imageLoadState = ref('idle')
const showImageViewer = ref(false)
const previewImages = ref([])

const timeCode = computed(() => {
  const duration = Number(props.segment.duration || 0)
  if (!duration) return '--:--'
  const minutes = Math.floor(duration / 60)
  const seconds = Math.floor(duration % 60)
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
})

function handleImageError() {
  imageLoadState.value = 'error'
}

function handleImageLoad() {
  imageLoadState.value = 'loaded'
}

function previewImage() {
  if (props.segment.image_url && imageLoadState.value !== 'error') {
    previewImages.value = [props.segment.image_url]
    showImageViewer.value = true
  }
}

function onImageSelected(event) {
  const file = event.target.files?.[0]
  if (file) {
    emit('upload-image', props.index, file)
    event.target.value = ''
  }
}
</script>

<style scoped>
.segment-card {
  display: grid;
  grid-template-columns: 68px minmax(0, 1fr);
  gap: 9px;
  padding: 9px;
  border: 1px solid transparent;
  border-left: 3px solid transparent;
  border-radius: 10px;
  background: #fff;
  cursor: pointer;
  box-shadow: inset 0 0 0 1px rgba(29, 29, 31, 0.08);
  transition: border-color 0.18s, box-shadow 0.18s, transform 0.18s, background 0.18s;
}

.segment-card:hover {
  background: #fbfcfd;
  border-color: rgba(29, 29, 31, 0.12);
  transform: translateY(-1px);
}

.segment-card.active {
  border-left-color: #111318;
  background: #f8f9fb;
  box-shadow:
    inset 0 0 0 1px rgba(17, 19, 24, 0.18),
    0 6px 16px rgba(20, 23, 31, 0.07);
}

.segment-thumb {
  width: 68px;
  aspect-ratio: v-bind(aspectRatio);
  align-self: start;
  border-radius: 7px;
  overflow: hidden;
  background: #eff2f6;
  box-shadow: inset 0 0 0 1px rgba(29, 29, 31, 0.08);
}

.segment-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.thumb-empty {
  width: 100%;
  height: 100%;
  display: grid;
  place-items: center;
  color: var(--color-text-tertiary);
  border: 1px dashed rgba(29, 29, 31, 0.18);
}

.thumb-empty svg {
  width: 18px;
  height: 18px;
}

.thumb-error {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  color: #c9342b;
  background: rgba(255, 59, 48, 0.07);
}

.thumb-error svg {
  width: 20px;
  height: 20px;
}

.thumb-error .error-text {
  font-size: 10px;
  font-weight: 500;
}

.error-badges {
  display: flex;
  gap: 4px;
  margin-bottom: 3px;
}

.error-badge {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 2px 5px;
  background: rgba(255, 59, 48, 0.1);
  color: #b42318;
  font-size: 10px;
  font-weight: 600;
  border-radius: 999px;
}

.segment-main {
  min-width: 0;
}

.segment-meta {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 3px;
}

.segment-index,
.time-code {
  font-size: 11px;
  font-weight: 700;
  color: var(--color-text-tertiary);
  letter-spacing: 0;
  white-space: nowrap;
}

.segment-card.active .segment-index {
  color: #111318;
}

p {
  margin: 0;
  height: 34px;
  overflow: hidden;
  color: var(--color-text-secondary);
  font-size: 12px;
  line-height: 1.42;
}

p.placeholder {
  color: var(--color-text-placeholder);
}

.segment-preview-track {
  height: 3px;
  margin-top: 6px;
  border-radius: 999px;
  background: #e7eaf0;
  overflow: hidden;
}

.segment-preview-fill {
  height: 100%;
  border-radius: inherit;
  background: var(--color-primary);
  transition: width 0.1s linear;
}

.segment-tools {
  display: flex;
  gap: 3px;
  margin-top: 6px;
}

.segment-tools button {
  width: 23px;
  height: 23px;
  display: grid;
  place-items: center;
  border: 1px solid rgba(29, 29, 31, 0.12);
  border-radius: 6px;
  background: #fbfcfd;
  color: var(--color-text-tertiary);
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s, color 0.15s;
}

.segment-tools button:hover:not(:disabled) {
  color: #111318;
  border-color: rgba(17, 19, 24, 0.5);
  background: #fff;
}

.segment-tools button.playing {
  color: #fff;
  background: #111318;
  border-color: #111318;
}

.segment-tools button:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.segment-tools svg {
  width: 13px;
  height: 13px;
}

.hidden-input {
  display: none;
}
</style>
