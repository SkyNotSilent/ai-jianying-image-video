/**
 * 步骤卡片组件
 */
<template>
  <div class="step-card" :class="`step-${status}`">
    <div class="step-indicator">
      <div class="indicator-dot">
        <el-icon v-if="status === 'processing'" class="is-loading" :size="14" color="#fff"><Loading /></el-icon>
        <svg v-else-if="status === 'completed'" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12" /></svg>
        <svg v-else-if="status === 'failed'" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>
      </div>
      <div v-if="!isLast" class="indicator-line"></div>
    </div>

    <div class="step-body">
      <div class="step-header">
        <span class="step-name">{{ stepLabel }}</span>
        <span v-if="status === 'completed' && duration" class="step-duration">{{ formatDuration(duration) }}</span>
        <span v-else-if="status === 'processing'" class="step-badge">进行中</span>
        <span v-else-if="status === 'failed'" class="step-badge failed">失败</span>
      </div>
      <el-progress
        v-if="status === 'processing' && progress && total"
        :percentage="Math.round((progress / total) * 100)"
        :stroke-width="3"
        color="var(--color-accent)"
        :show-text="false"
        class="step-progress"
      />
      <div v-if="status === 'processing' && progress && total" class="step-sub">{{ progress }}/{{ total }}</div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Loading } from '@element-plus/icons-vue'
import { getStepLabel, formatDuration } from '../utils/format'

const props = defineProps({
  name: { type: String, required: true },
  status: { type: String, default: 'pending' },
  progress: { type: Number, default: null },
  total: { type: Number, default: null },
  duration: { type: Number, default: null },
  isLast: { type: Boolean, default: false }
})

const stepLabel = computed(() => getStepLabel(props.name))
</script>

<style scoped>
.step-card { display: flex; gap: 12px; min-height: 52px; }

.step-indicator { display: flex; flex-direction: column; align-items: center; flex-shrink: 0; width: 24px; }

.indicator-dot {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: var(--color-border);
  transition: background 0.3s;
}
.step-processing .indicator-dot { background: var(--color-accent); box-shadow: 0 0 0 4px rgba(0, 113, 227, 0.15); }
.step-completed .indicator-dot { background: var(--color-success); }
.step-failed .indicator-dot { background: var(--color-danger); }

.indicator-line { flex: 1; width: 1px; background: var(--color-border); margin: 4px 0; min-height: 14px; }

.step-body {
  flex: 1;
  min-width: 0;
  padding-bottom: 18px;
  background: var(--color-card);
  border-radius: 8px;
  padding: 12px 14px;
  border: 1px solid var(--color-border);
}
.step-processing .step-body { border-color: rgba(0, 113, 227, 0.3); border-left: 2px solid var(--color-accent); box-shadow: 0 2px 8px rgba(0, 113, 227, 0.08); }

.step-header { display: flex; justify-content: space-between; align-items: center; }
.step-name { font-size: 14px; font-weight: 500; color: var(--color-text-secondary); }
.step-pending .step-name { color: var(--color-text-placeholder); }

.step-duration { font-size: 12px; color: var(--color-success); font-weight: 500; }

.step-badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
  font-weight: 600;
  color: var(--color-accent);
  background: var(--color-accent-light);
}
.step-badge.failed { color: var(--color-danger); background: var(--color-danger-bg); }

.step-progress { margin-top: 8px; }
.step-sub { margin-top: 4px; font-size: 12px; color: var(--color-text-placeholder); }
</style>
