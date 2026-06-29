/**
 * 错误弹窗组件
 */
<template>
  <el-dialog
    v-model="dialogVisible"
    title="生成失败"
    width="500px"
    :close-on-click-modal="false"
  >
    <div class="error-content">
      <p class="error-message">{{ errorMessage }}</p>
      <div v-if="errorDetail" class="error-detail">
        <el-collapse v-model="activeNames">
          <el-collapse-item title="查看详细信息" name="1">
            <p class="detail-text">{{ errorDetail }}</p>
          </el-collapse-item>
        </el-collapse>
      </div>
    </div>
    <template #footer>
      <span class="dialog-footer">
        <el-button @click="dialogVisible = false">关闭</el-button>
        <el-button v-if="recoverLabel" @click="handleRecover">{{ recoverLabel }}</el-button>
        <el-button type="primary" @click="handleRetry">重新生成</el-button>
      </span>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  errorMessage: { type: String, default: '生成过程中出现错误' },
  errorDetail: { type: String, default: '' },
  recoverLabel: { type: String, default: '' }
})
const emit = defineEmits(['update:visible', 'retry', 'recover'])
const dialogVisible = ref(props.visible)
const activeNames = ref([])

watch(() => props.visible, (val) => { dialogVisible.value = val })
watch(dialogVisible, (val) => { emit('update:visible', val) })
const handleRetry = () => { emit('retry'); dialogVisible.value = false }
const handleRecover = () => { emit('recover'); dialogVisible.value = false }
</script>

<style scoped>
.error-content { padding: 20px; background: var(--color-card); }
.error-message { font-size: 14px; color: var(--color-text-secondary); line-height: 1.6; margin-bottom: 12px; }
.error-detail { margin-top: 8px; }
.detail-text { font-size: 13px; color: var(--color-text-tertiary); line-height: 1.5; word-break: break-all; white-space: pre-wrap; }
.dialog-footer { display: flex; justify-content: flex-end; gap: 10px; }
</style>
