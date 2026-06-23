<template>
  <div class="result-view">
    <div v-loading="loading" element-loading-text="加载中..." class="result-container">
      <div v-if="!loading && taskData" class="layout">
        <div class="info-side">
        <div class="info-content">
          <div class="success-icon">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="20 6 9 17 4 12" />
            </svg>
          </div>
          <h2 class="info-title">生成完成</h2>
          <p class="info-desc">视频草稿和 MP4 已准备就绪</p>

          <div class="meta-list">
            <div class="meta-item">
              <span class="meta-label">视频主题</span>
              <span class="meta-value">{{ taskData.result?.theme }}</span>
            </div>
            <div class="meta-item">
              <span class="meta-label">段落数</span>
              <span class="meta-value">{{ taskData.result?.segments_count }} 段</span>
            </div>
            <div class="meta-item">
              <span class="meta-label">画幅比例</span>
              <span class="meta-value">{{ exportState?.ratio || '--' }}</span>
            </div>
            <div class="meta-item">
              <span class="meta-label">创建时间</span>
              <span class="meta-value">{{ formatTimestamp(taskData.result?.created_at) }}</span>
            </div>
          </div>

          <div class="nav-actions">
            <button class="nav-btn" @click="handleBackToPrevious">返回编辑</button>
            <button class="nav-btn" @click="handleBackToExport">导出中心</button>
            <button class="nav-btn" @click="handleBackHome">创建新任务</button>
          </div>
        </div>
      </div>

        <div class="download-side">
        <div class="download-content">
          <h3 class="dl-title">文件下载</h3>

          <div class="form-field">
            <label class="field-label">解压路径</label>
            <input type="text" v-model="extractPath" class="text-field" placeholder="D:\JianyingPro Drafts" @input="onPathChange" />
            <div class="field-hint">下载后请解压到剪映草稿所在的文件夹</div>
          </div>

          <div class="download-card" :class="{ disabled: !draftAvailable || !extractPath?.trim() }" @click="handleDownloadDraft">
            <div class="dl-icon draft">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
            </div>
            <div class="dl-info">
              <div class="dl-name">剪映草稿</div>
              <div class="dl-desc">{{ draftAvailable ? 'ZIP 压缩包，导入剪映即可编辑' : '剪映草稿未生成' }}</div>
            </div>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--color-text-placeholder)" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
          </div>

          <div class="download-card" :class="{ disabled: !mp4Available }" @click="handleDownloadMp4">
            <div class="dl-icon mp4">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/></svg>
            </div>
            <div class="dl-info">
              <div class="dl-name">MP4 视频</div>
              <div class="dl-desc">{{ mp4Available ? '可直接播放的成片视频' : 'MP4 未生成' }}</div>
            </div>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--color-text-placeholder)" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
          </div>

          <div v-if="hasOssUrls" class="oss-section">
            <div class="field-label" style="margin-bottom:10px;">云端链接</div>
            <div v-if="exportState?.outputs?.draft?.url" class="oss-row" @click="copyUrl(exportState.outputs.draft.url)">
              <span>草稿 ZIP</span><span class="oss-copy">复制链接</span>
            </div>
            <div v-if="exportState?.outputs?.mp4?.url" class="oss-row" @click="copyUrl(exportState.outputs.mp4.url)">
              <span>MP4 视频</span><span class="oss-copy">复制链接</span>
            </div>
          </div>
        </div>
        </div>
      </div>

      <div v-if="!loading && !taskData" class="error-container">
        <el-empty description="任务不存在" />
        <button class="nav-btn" @click="handleBackHome">返回首页</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getExportState, getTaskStatus } from '../api/task'
import { formatTimestamp } from '../utils/format'

const route = useRoute()
const router = useRouter()
const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:2002'
const taskId = route.params.taskId
const loading = ref(true)
const taskData = ref(null)
const exportState = ref(null)
const extractPath = ref(localStorage.getItem('extract_path') || '')

const hasOssUrls = computed(() => Boolean(exportState.value?.outputs?.draft?.url || exportState.value?.outputs?.mp4?.url))
const mp4Available = computed(() => Boolean(exportState.value?.outputs?.mp4?.available))
const draftAvailable = computed(() => Boolean(exportState.value?.outputs?.draft?.available))

onMounted(async () => {
  if (!taskId) { router.push('/'); return }
  try {
    const data = await getTaskStatus(taskId)
    if (data.status !== 'completed') { ElMessage.warning('任务未完成'); router.push(`/process/${taskId}`); return }
    taskData.value = data
    exportState.value = await getExportState(taskId)
    if (data.extract_path && !extractPath.value) extractPath.value = data.extract_path
  } catch (error) { console.error('获取任务失败:', error); ElMessage.error('获取任务失败') }
  finally { loading.value = false }
})

const handleDownloadDraft = () => {
  if (!draftAvailable.value) { ElMessage.warning('剪映草稿未生成'); return }
  const path = extractPath.value?.trim()
  if (!path) { ElMessage.warning('请先填写解压路径'); return }
  localStorage.setItem('extract_path', path)
  window.open(`${baseURL}/ai/native/video/kepu/tasks/${taskId}/download?extract_path=${encodeURIComponent(path)}`, '_blank')
}
const onPathChange = (e) => { if (e.target.value) localStorage.setItem('extract_path', e.target.value) }
const handleDownloadMp4 = () => {
  if (!mp4Available.value) { ElMessage.warning('MP4 未生成'); return }
  window.open(`${baseURL}/ai/native/video/kepu/tasks/${taskId}/download-mp4`, '_blank')
}
const copyUrl = async (url) => {
  try { await navigator.clipboard.writeText(url); ElMessage.success('链接已复制') } catch { ElMessage.error('复制失败') }
}
const handleBackHome = () => { router.push('/') }
const handleBackToPrevious = () => { router.push(`/preview/${taskId}`) }
const handleBackToExport = () => { router.push(`/export/${taskId}`) }
</script>

<style scoped>
.result-view { min-height: 100vh; background: var(--color-bg); }
.result-container { min-height: 100vh; }
.error-container { display: flex; flex-direction: column; justify-content: center; align-items: center; min-height: 100vh; gap: 20px; }
.layout { display: flex; min-height: 100vh; }

/* 左侧 */
.info-side {
  width: 400px;
  flex-shrink: 0;
  background: linear-gradient(180deg, #ffffff 0%, var(--color-bg-secondary) 100%);
  border-right: 1px solid var(--color-border);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 60px 44px;
}
.info-content { max-width: 300px; }

.success-icon {
  width: 52px;
  height: 52px;
  background: linear-gradient(135deg, var(--color-success), #22c55e);
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 24px;
}

.info-title { font-size: 24px; font-weight: 700; color: var(--color-text); margin-bottom: 6px; letter-spacing: -0.3px; }
.info-desc { font-size: 14px; color: var(--color-text-tertiary); margin-bottom: 32px; }

.meta-list { display: flex; flex-direction: column; gap: 14px; margin-bottom: 36px; }
.meta-item { display: flex; justify-content: space-between; align-items: center; }
.meta-label { font-size: 13px; color: var(--color-text-tertiary); }
.meta-value { font-size: 14px; font-weight: 500; color: var(--color-text-secondary); }

.nav-actions { display: flex; flex-direction: column; gap: 8px; }
.nav-btn {
  padding: 10px 0;
  border-radius: var(--radius-xl);
  border: 1px solid var(--color-primary);
  background: transparent;
  color: var(--color-primary);
  font-size: 14px;
  font-weight: 400;
  letter-spacing: -0.016em;
  cursor: pointer;
  transition: all var(--duration-normal) var(--ease-out);
  text-align: center;
}
.nav-btn:hover {
  background: var(--color-primary-bg);
  box-shadow: var(--shadow-sm);
}

/* 右侧 */
.download-side {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 60px;
  overflow-y: auto;
}
.download-content { width: 100%; max-width: 480px; }

.dl-title { font-size: 20px; font-weight: 700; color: var(--color-text); margin-bottom: 28px; letter-spacing: -0.2px; }

.form-field { margin-bottom: 24px; }
.field-label { display: block; font-size: 13px; font-weight: 500; color: var(--color-text-tertiary); margin-bottom: 6px; }

.text-field {
  width: 100%;
  padding: 12px 14px;
  font-size: 14px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg-secondary);
  color: var(--color-text);
  outline: none;
  font-family: inherit;
  box-sizing: border-box;
  transition: all var(--duration-fast) var(--ease-out);
}
.text-field:focus {
  border-color: var(--color-accent);
  background: #fff;
  box-shadow: 0 0 0 4px rgba(0, 113, 227, 0.1);
}
.field-hint { font-size: 12px; color: var(--color-text-placeholder); margin-top: 6px; }

.download-card {
  display: flex;
  align-items: center;
  padding: 16px 18px;
  background: var(--color-card);
  border-radius: var(--radius-lg);
  margin-bottom: 10px;
  border: none;
  box-shadow: var(--shadow-sm);
  cursor: pointer;
  transition: all var(--duration-normal) var(--ease-out);
}
.download-card:hover:not(.disabled) {
  box-shadow: var(--shadow-lg);
  transform: translateY(-4px);
}
.download-card.disabled { opacity: 0.5; cursor: not-allowed; }

.dl-icon {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-right: 14px;
  color: #fff;
}
.dl-icon.draft { background: linear-gradient(135deg, var(--color-primary), #1d1d1f); }
.dl-icon.mp4 { background: linear-gradient(135deg, #1d1d1f, #6e6e73); }

.dl-info { flex: 1; min-width: 0; }
.dl-name { font-size: 14px; font-weight: 600; color: var(--color-text); margin-bottom: 2px; }
.dl-desc { font-size: 13px; color: var(--color-text-tertiary); }

.oss-section { margin-top: 24px; }
.oss-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 16px;
  background: var(--color-card);
  border-radius: var(--radius-md);
  margin-bottom: 6px;
  border: none;
  box-shadow: var(--shadow-xs);
  cursor: pointer;
  font-size: 14px;
  color: var(--color-text-secondary);
  transition: all var(--duration-normal) var(--ease-out);
}
.oss-row:hover {
  box-shadow: var(--shadow-sm);
  transform: translateY(-1px);
}
.oss-copy { font-size: 13px; color: var(--color-primary); font-weight: 500; }

@media (max-width: 820px) {
  .layout {
    flex-direction: column;
  }

  .info-side {
    width: 100%;
    padding: 34px 22px;
    border-right: none;
    border-bottom: 1px solid var(--color-border);
  }

  .download-side {
    padding: 28px 18px 40px;
  }
}
</style>
