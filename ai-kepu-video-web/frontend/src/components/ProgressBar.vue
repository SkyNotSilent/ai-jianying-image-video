/**
 * 进度环组件 - 设计预览风格
 */
<template>
  <div class="loading-container">
    <div class="loading-ring-container">
      <svg class="loading-svg" viewBox="0 0 100 100">
        <circle class="loading-circle-bg" cx="50" cy="50" r="46" />
        <circle class="loading-circle-progress" cx="50" cy="50" r="46" :style="{ strokeDashoffset: dashOffset }" />
      </svg>
      <div class="loading-inner-ring"></div>
      <div class="loading-percent">{{ percentage }}%</div>
    </div>
    <div class="loading-info">
      <div class="loading-subtitle">AI 智能引擎</div>
      <div class="loading-task">{{ currentStepLabel }}</div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { calculateProgress, getStepLabel } from '../utils/format'

const props = defineProps({
  steps: { type: Array, required: true },
  currentStep: { type: String, default: '' }
})

const percentage = computed(() => calculateProgress(props.steps))
const circumference = 2 * Math.PI * 46
const dashOffset = computed(() => circumference - (percentage.value / 100) * circumference)

const currentStepLabel = computed(() => {
  if (!props.currentStep) return '正在初始化...'
  const step = props.steps.find(s => s.name === props.currentStep)
  if (!step) return '处理中'
  const label = getStepLabel(props.currentStep)
  if (step.status === 'processing' && step.progress && step.total) return `${label} ${step.progress}/${step.total}`
  return label
})
</script>

<style scoped>
.loading-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 32px;
}

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
  stroke: #e5e6eb;
  stroke-width: 4;
}

.loading-circle-progress {
  fill: none;
  stroke: var(--color-accent);
  stroke-width: 4;
  stroke-dasharray: 289;
  stroke-dashoffset: 289;
  transition: stroke-dashoffset 0.5s;
  filter: drop-shadow(0 0 8px rgba(0, 113, 227, 0.3));
}

.loading-inner-ring {
  position: absolute;
  inset: 15%;
  border-radius: 50%;
  border: 2px solid #e5e6eb;
  border-right-color: var(--color-accent);
  animation: innerSpin 2s linear infinite;
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
  color: var(--color-accent);
  font-weight: 500;
}

@keyframes innerSpin {
  to { transform: rotate(360deg); }
}
</style>
