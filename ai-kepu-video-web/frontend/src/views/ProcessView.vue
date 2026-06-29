/**
 * 生产页 - 实时进度展示
 * 直接从 design-preview/index.html 移植
 */
<template>
  <div class="process-view">
    <button type="button" class="exit-btn" @click="leaveProcess">退出</button>

    <div v-if="loading" class="loading-ring-container">
      <svg class="loading-svg" viewBox="0 0 100 100">
        <circle class="loading-circle-bg" cx="50" cy="50" r="46" />
        <circle class="loading-circle-progress" cx="50" cy="50" r="46" :style="{ strokeDashoffset: loadingOffset }" />
      </svg>
      <div class="loading-inner-ring"></div>
      <div class="loading-percent">{{ Math.round(loadingPercent) }}%</div>
    </div>
    <div v-if="loading" class="loading-info">
      <div class="loading-subtitle">AI 智能引擎</div>
      <div class="loading-task">{{ loadingTask }}</div>
      <div class="background-tip">退出后任务会继续在后台生成</div>
    </div>

    <template v-if="!loading && taskData">
      <section class="progress-stage">
        <ProgressBar
          v-if="taskData.progress"
          :steps="taskData.progress.steps"
          :current-step="taskData.progress.current_step"
        />

        <div v-if="taskData.status === 'pending'" class="pending-tip">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" /></svg>
          <span>任务已提交，等待调度执行</span>
        </div>
        <div v-else class="background-tip">可以退出此页面，任务会继续在后台生成</div>
      </section>

      <section v-if="taskData.progress" class="steps-panel">
        <div class="steps-head">
          <h2>执行步骤</h2>
          <span>{{ taskData.progress.current_step || 'pending' }}</span>
        </div>
        <div class="steps-list">
          <StepCard
            v-for="(step, idx) in taskData.progress.steps"
            :key="step.name"
            :name="step.name"
            :status="step.status"
            :progress="step.progress"
            :total="step.total"
            :duration="step.duration"
            :is-last="idx === taskData.progress.steps.length - 1"
          />
        </div>
      </section>

      <section v-if="taskData.status === 'failed'" class="recovery-panel">
        <div>
          <h2>已生成内容仍可查看</h2>
          <p>任务失败只表示后续流程停止，已经保存的分镜、图片、配音和草稿素材会保留在预览编辑页。</p>
        </div>
        <button type="button" class="recover-btn" @click="openRecoveredAssets">查看已保存素材</button>
      </section>
    </template>

    <ErrorDialog
      v-model:visible="showError"
      :error-message="errorMessage"
      :error-detail="errorDetail"
      recover-label="查看已保存素材"
      @retry="handleRetry"
      @recover="openRecoveredAssets"
    />
  </div>
</template>

<script setup>
import { ref, onBeforeUnmount, onMounted, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { usePolling } from '../composables/usePolling'
import ProgressBar from '../components/ProgressBar.vue'
import StepCard from '../components/StepCard.vue'
import ErrorDialog from '../components/ErrorDialog.vue'
import { listDrafts } from '../utils/projectDrafts'

const route = useRoute()
const router = useRouter()
const taskId = route.params.taskId
const loading = ref(true)
const loadingPercent = ref(0)
const loadingTask = ref('正在初始化...')
const showError = ref(false)
const { data: taskData, error: pollingError, startPolling } = usePolling(taskId, 2000)
let loadingTimer = null

const loadingTasks = [
  '正在分析文案并生成分镜脚本...',
  '正在生成画面提示词...',
  '正在匹配配音参数...',
  '正在生成分镜图片...',
  '正在合成音频和字幕...',
  '正在整理预览素材...',
]

const errorMessage = computed(() => {
  if (taskData.value?.error) return '生成失败，请重试'
  if (pollingError.value) return pollingError.value
  return '未知错误'
})
const errorDetail = computed(() => taskData.value?.error || '')
const loadingOffset = computed(() => 289 - (289 * loadingPercent.value) / 100)

onMounted(() => {
  if (!taskId) { router.push('/'); return }
  startLoadingAnimation()
  startPolling()
})

onBeforeUnmount(() => {
  clearInterval(loadingTimer)
})

watch(() => taskData.value?.status, (status) => {
  if (taskData.value && loading.value) finishLoadingAnimation()
  if (status === 'completed') {
    router.push(`/preview/${taskId}`)
  }
  if (status === 'failed') showError.value = true
})

watch(pollingError, (error) => {
  if (error && loading.value) finishLoadingAnimation()
})

function startLoadingAnimation() {
  clearInterval(loadingTimer)
  loadingTimer = setInterval(() => {
    const next = Math.min(92, loadingPercent.value + Math.random() * 8 + 2)
    loadingPercent.value = next
    const taskIdx = Math.min(Math.floor(next / 16), loadingTasks.length - 1)
    loadingTask.value = loadingTasks[taskIdx]
  }, 240)
}

function finishLoadingAnimation() {
  clearInterval(loadingTimer)
  loadingPercent.value = 100
  loadingTask.value = '初始化完成，正在进入任务面板...'
  setTimeout(() => {
    loading.value = false
  }, 260)
}

function leaveProcess() {
  router.push('/assets')
}

const handleRetry = () => {
  const draft = listDrafts().find((item) => item.created_task_id === taskId)
  if (draft?.draft_id) {
    router.push(`/production/${draft.draft_id}`)
    return
  }
  router.push('/assets')
}
const openRecoveredAssets = () => { router.push(`/preview/${taskId}`) }
</script>

<style scoped>
/*
 * LOADING PAGE — 从 design-preview/index.html 原样复制
 * 设计预览中 .page 基类: height: calc(100vh - 64px); display: flex; flex-direction: column;
 * #page-loading: align-items: center; justify-content: center; gap: 32px; overflow: hidden;
 * 此处无 NavBar，所以用 height: 100vh
 */
.process-view {
  height: 100vh;
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 32px;
  overflow: hidden;
  background: var(--color-bg);
}

.exit-btn {
  position: fixed;
  top: 18px;
  right: 22px;
  z-index: 20;
  height: 38px;
  padding: 0 16px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-card);
  color: var(--color-text-secondary);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  box-shadow: 0 1px 2px rgba(0,0,0,0.04);
}

.exit-btn:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
}

/* 以下全部从 design-preview 原样复制，只把 CSS 变量替换为 Vue 项目的变量名 */

.loading-ring-container {
  width: 192px;
  height: 192px;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
}

.loading-svg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  transform: rotate(-90deg);
}

.loading-circle-bg {
  fill: none;
  stroke: #222;
  stroke-width: 4;
}

.loading-circle-progress {
  fill: none;
  stroke: var(--color-primary);
  stroke-width: 4;
  stroke-dasharray: 289;
  stroke-dashoffset: 289;
  transition: stroke-dashoffset 0.5s;
}

.loading-inner-ring {
  position: absolute;
  inset: 15%;
  border-radius: 50%;
  border: 2px solid #222;
  border-right-color: var(--color-primary);
  animation: innerSpin 2s linear infinite;
}

@keyframes innerSpin {
  to { transform: rotate(360deg); }
}

.loading-percent {
  font-size: 18px;
  font-weight: 600;
  color: var(--color-text);
  z-index: 10;
}

.loading-info {
  text-align: center;
}

.loading-subtitle {
  font-size: 11px;
  font-weight: 500;
  color: var(--color-text-tertiary);
  text-transform: uppercase;
  letter-spacing: 3px;
  margin-bottom: 4px;
}

.loading-task {
  font-size: 13px;
  color: var(--color-primary);
}

.background-tip {
  margin-top: 10px;
  font-size: 12px;
  color: var(--color-text-tertiary);
}

/* 进度阶段（任务数据加载后） */

.progress-stage {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  flex-shrink: 0;
}

.pending-tip {
  margin-top: 22px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--color-text-tertiary);
  font-size: 13px;
}

.pending-tip svg {
  width: 18px;
  height: 18px;
  animation: tickPulse 1.8s ease-in-out infinite;
}

.steps-panel {
  width: min(760px, 100%);
  background: var(--color-card);
  border: 1px solid var(--color-border);
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 1px 2px rgba(0,0,0,0.04);
}

.steps-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.steps-head h2 {
  font-size: 16px;
}

.steps-head span {
  font-size: 12px;
  color: var(--color-text-tertiary);
  font-family: var(--font-mono);
}

.steps-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px 14px;
}

.recovery-panel {
  width: min(760px, 100%);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  border: 1px solid #bde8cf;
  border-radius: 12px;
  background: var(--color-success-bg);
  padding: 16px 18px;
  color: var(--color-text);
}

.recovery-panel h2 {
  font-size: 16px;
  margin-bottom: 4px;
}

.recovery-panel p {
  color: var(--color-text-secondary);
  font-size: 13px;
}

.recover-btn {
  height: 40px;
  border: 1px solid var(--color-success);
  border-radius: 8px;
  background: #fff;
  color: var(--color-success);
  padding: 0 16px;
  font-weight: 800;
  cursor: pointer;
  white-space: nowrap;
}

@keyframes tickPulse {
  0%, 100% { opacity: 0.55; transform: scale(1); }
  50% { opacity: 1; transform: scale(1.05); }
}

@media (max-width: 720px) {
  .steps-list {
    grid-template-columns: 1fr;
  }
}
</style>
