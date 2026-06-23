<template>
  <div class="export-view">
    <NavBar active-tab="" show-back @navigate="handleNavigate" @back="router.push(`/preview/${taskId}`)" />

    <main class="export-shell">
      <div v-loading="loading" element-loading-text="加载中..." class="export-content">
        <el-empty v-if="!loading && !state" description="导出状态不可用" />

        <template v-else-if="!loading">
          <section class="export-header">
            <div>
              <p class="eyebrow">导出中心</p>
              <h1>选择交付格式</h1>
            </div>
            <div class="ratio-pill">
              <span>{{ state.ratio }}</span>
              <strong>{{ state.canvas.width }}×{{ state.canvas.height }}</strong>
            </div>
          </section>

        <section class="status-strip">
          <div>
            <span>最终预览</span>
            <strong :class="{ ok: state.preview.valid, warn: state.preview.exists && !state.preview.valid }">{{ previewStatusText }}</strong>
          </div>
          <div>
            <span>MP4 成片</span>
            <strong :class="{ ok: state.outputs.mp4.available }">{{ state.outputs.mp4.available ? '可下载' : '未生成' }}</strong>
          </div>
          <div>
            <span>剪映草稿</span>
            <strong :class="{ ok: draftLocalJob?.status === 'completed' || state.outputs.draft.available || state }">{{ draftStatusText }}</strong>
          </div>
        </section>

        <section class="export-grid">
          <article class="export-card" :class="{ preferred: defaultExport === 'mp4' }">
            <div class="card-icon video-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2"/></svg>
            </div>
            <div class="card-copy">
              <h2>直接 MP4 视频</h2>
              <p>{{ state.preview.valid ? '会直接复用当前最终预览，速度最快。' : '当前最终预览不可复用，会重新生成 MP4。' }}</p>
            </div>
            <div class="card-actions">
              <button type="button" class="primary-btn" :disabled="!state.outputs.mp4.available" @click="downloadMp4">下载 MP4</button>
              <button type="button" class="secondary-btn" :disabled="mp4Busy" @click="startExport('mp4')">{{ mp4Busy ? '生成中...' : '重新生成 MP4' }}</button>
            </div>
            <p v-if="mp4Job?.status === 'failed'" class="error-text">{{ mp4Job.error || 'MP4 导出失败' }}</p>
          </article>

          <article class="export-card" :class="{ preferred: defaultExport === 'draft' }">
            <div class="card-icon draft-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
            </div>
            <div class="card-copy">
              <h2>剪映草稿</h2>
              <p>推荐直接写入本机剪映草稿目录。</p>
            </div>
            <div class="path-field">
              <span>剪映草稿目录</span>
              <div class="path-input-group">
                <input v-model.trim="extractPath" type="text" :placeholder="extractPlaceholder" @input="saveExtractPath" />
                <button type="button" class="folder-btn" :disabled="folderPicking" @click="chooseDraftFolder">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                    <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
                  </svg>
                  {{ folderPicking ? '选择中...' : '选择' }}
                </button>
              </div>
            </div>
            <div v-if="pathCheck.normalized && pathCheck.normalized !== extractPath" class="path-normalized">
              规范化后：{{ pathCheck.normalized }}
            </div>
            <div v-if="pathCheck.issues.length" class="path-issues">
              <span v-for="issue in pathCheck.issues" :key="issue">{{ issue }}</span>
            </div>
            <div class="platform-field">
              <span>剪映所在系统</span>
              <div class="platform-switch">
                <button type="button" :class="{ active: targetOS === 'mac' }" @click="setTargetOS('mac')">Mac</button>
                <button type="button" :class="{ active: targetOS === 'windows' }" @click="setTargetOS('windows')">Windows</button>
              </div>
            </div>
            <div v-if="draftLocalJob?.result?.draft_path" class="path-normalized">
              已写入：{{ draftLocalJob.result.draft_path }}
            </div>
            <div v-if="draftLocalJob?.result?.warnings?.length" class="path-issues">
              <span v-for="warning in draftLocalJob.result.warnings" :key="warning">{{ warning }}</span>
            </div>
            <div class="card-actions">
              <button type="button" class="primary-btn" :disabled="draftLocalBusy || !pathCheck.valid" @click="startExport('draft_local')">{{ draftLocalBusy ? '写入中...' : '写入剪映' }}</button>
            </div>
            <p v-if="draftLocalJob?.status === 'failed'" class="error-text">{{ draftLocalJob.error || '写入剪映失败' }}</p>
            <p v-if="draftJob?.status === 'failed'" class="error-text">{{ draftJob.error || '草稿导出失败' }}</p>
          </article>
        </section>

          <div class="footer-actions">
            <button type="button" class="secondary-btn" @click="router.push(`/preview/${taskId}`)">返回编辑</button>
            <button type="button" class="primary-btn" @click="router.push(`/result/${taskId}`)">查看结果页</button>
          </div>
        </template>
      </div>
    </main>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import NavBar from '../components/NavBar.vue'
import { createExport, getExportJob, getExportState, selectDraftFolder } from '../api/task'

const route = useRoute()
const router = useRouter()
const taskId = route.params.taskId
const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:2002'

const loading = ref(true)
const state = ref(null)
const mp4Job = ref(null)
const draftJob = ref(null)
const draftLocalJob = ref(null)
const extractPath = ref(localStorage.getItem('kepu:mine:extract_path') || localStorage.getItem('extract_path') || '')
const targetOS = ref(localStorage.getItem('kepu:mine:draft_target_os') || detectTargetOS())
const defaultExport = ref(localStorage.getItem('kepu:mine:default_export') || 'mp4')
const folderPicking = ref(false)
let pollTimer = null

const mp4Busy = computed(() => ['pending', 'processing'].includes(mp4Job.value?.status))
const draftBusy = computed(() => ['pending', 'processing'].includes(draftJob.value?.status))
const draftLocalBusy = computed(() => ['pending', 'processing'].includes(draftLocalJob.value?.status))
const mp4ActionText = computed(() => state.value?.preview?.valid ? '使用最终预览生成 MP4' : '重新生成 MP4')
const extractPlaceholder = computed(() => targetOS.value === 'mac'
  ? '/Users/你的用户名/Movies/JianyingPro/User Data/Projects/com.lveditor.draft'
  : 'D:\\JianyingPro Drafts'
)
const pathCheck = computed(() => validateExtractPath(extractPath.value, targetOS.value))
const previewStatusText = computed(() => {
  if (!state.value?.preview?.exists) return '未生成'
  if (state.value.preview.valid) return '可复用'
  if (state.value.preview.reason === 'stale') return '已过期'
  if (state.value.preview.reason === 'ratio_mismatch') return '比例不一致'
  return '不可用'
})
const draftStatusText = computed(() => {
  if (draftLocalJob.value?.status === 'completed') return '已写入剪映'
  if (draftLocalBusy.value) return '写入中'
  if (state.value?.outputs?.draft?.available) return '可浏览器下载'
  return '可浏览器下载'
})

onMounted(async () => {
  await loadState()
})

onBeforeUnmount(() => {
  stopPolling()
})

async function loadState() {
  try {
    loading.value = true
    state.value = await getExportState(taskId)
    const activeJobs = state.value.jobs || []
    mp4Job.value = activeJobs.find(job => job.target === 'mp4') || mp4Job.value
    draftJob.value = activeJobs.find(job => job.target === 'draft') || draftJob.value
    draftLocalJob.value = activeJobs.find(job => job.target === 'draft_local') || draftLocalJob.value
    if (mp4Busy.value || draftBusy.value || draftLocalBusy.value) startPolling()
  } catch (error) {
    console.error('加载导出状态失败:', error)
    ElMessage.error('加载导出状态失败')
  } finally {
    loading.value = false
  }
}

function handleNavigate(tab) {
  if (tab === 'settings') router.push('/settings')
  else if (tab === 'library') router.push({ path: '/', query: { tab: 'library' } })
  else router.push('/')
}

async function startExport(target) {
  try {
    const payload = { target, use_preview: true }
    if (target === 'draft_local') {
      const check = pathCheck.value
      if (!check.valid) {
        ElMessage.warning(check.issues[0] || '请先选择剪映草稿目录')
        return
      }
      payload.draft_root = check.normalized
      payload.target_os = targetOS.value
      payload.overwrite = true
    }
    const job = await createExport(taskId, payload)
    if (target === 'mp4') mp4Job.value = job
    else if (target === 'draft_local') draftLocalJob.value = job
    else draftJob.value = job
    ElMessage.success(target === 'mp4' ? 'MP4 导出已开始' : target === 'draft_local' ? '正在写入剪映草稿目录' : '草稿下载准备已开始')
    startPolling()
  } catch (error) {
    console.error('创建导出任务失败:', error)
    ElMessage.error(error?.response?.data?.detail || '创建导出任务失败')
  }
}

function startPolling() {
  if (pollTimer) return
  pollTimer = window.setInterval(pollJobs, 2000)
  pollJobs()
}

function stopPolling() {
  if (pollTimer) {
    window.clearInterval(pollTimer)
    pollTimer = null
  }
}

async function pollJobs() {
  await Promise.all([pollJob('mp4'), pollJob('draft'), pollJob('draft_local')])
  if (!mp4Busy.value && !draftBusy.value && !draftLocalBusy.value) {
    stopPolling()
    await loadState()
  }
}

async function pollJob(target) {
  const current = target === 'mp4' ? mp4Job.value : target === 'draft_local' ? draftLocalJob.value : draftJob.value
  if (!current?.job_id || !['pending', 'processing'].includes(current.status)) return
  try {
    const next = await getExportJob(taskId, current.job_id)
    if (target === 'mp4') mp4Job.value = next
    else if (target === 'draft_local') draftLocalJob.value = next
    else draftJob.value = next
    if (next.status === 'completed') ElMessage.success(target === 'mp4' ? 'MP4 已生成' : target === 'draft_local' ? '已写入剪映草稿目录' : '草稿下载已准备好')
    if (next.status === 'failed') ElMessage.error(next.error || '导出失败')
  } catch (error) {
    console.error('轮询导出任务失败:', error)
  }
}

async function chooseDraftFolder() {
  try {
    folderPicking.value = true
    ElMessage.info('请在弹出的窗口里选择剪映草稿目录')
    const result = await selectDraftFolder(taskId)
    extractPath.value = result.path || ''
    targetOS.value = result.target_os || targetOS.value
    saveExtractPath()
    localStorage.setItem('kepu:mine:draft_target_os', targetOS.value)
    if (result.warnings?.length) ElMessage.warning(result.warnings[0])
    else ElMessage.success('已选择剪映草稿目录')
  } catch (error) {
    console.error('选择剪映草稿目录失败:', error)
    ElMessage.error(error?.response?.data?.detail || '未选择文件夹')
  } finally {
    folderPicking.value = false
  }
}

function saveExtractPath() {
  localStorage.setItem('kepu:mine:extract_path', extractPath.value || '')
  if (extractPath.value) localStorage.setItem('extract_path', extractPath.value)
}

function detectTargetOS() {
  if (typeof navigator !== 'undefined' && /mac/i.test(navigator.platform || '')) return 'mac'
  return 'windows'
}

function setTargetOS(value) {
  targetOS.value = value === 'mac' ? 'mac' : 'windows'
  localStorage.setItem('kepu:mine:draft_target_os', targetOS.value)
}

function stripWrappingQuotes(value) {
  return String(value || '').trim().replace(/^['"]+|['"]+$/g, '').trim()
}

function normalizeExtractPath(value, osName) {
  const cleaned = stripWrappingQuotes(value)
  if (!cleaned) return ''
  if (osName === 'mac') return cleaned.replace(/\\/g, '/').replace(/\/+$/g, '')
  return cleaned.replace(/\//g, '\\').replace(/\\+$/g, '')
}

function isWindowsAbsolute(path) {
  return /^[A-Za-z]:\\/.test(path) || /^\\\\/.test(path)
}

function validateExtractPath(value, osName) {
  const raw = String(value || '').trim()
  const normalized = normalizeExtractPath(raw, osName)
  const issues = []
  if (!normalized) {
    issues.push('请填写剪映草稿解压路径')
    return { valid: false, normalized, issues }
  }
  if (raw !== stripWrappingQuotes(raw)) issues.push('检测到路径外侧引号，下载时会自动移除')
  if (osName === 'mac') {
    if (raw.includes('\\')) issues.push('检测到 Windows 反斜杠，下载时会转换为 Mac 正斜杠')
    if (!normalized.startsWith('/')) issues.push('Mac 路径必须以 / 开头')
  } else {
    if (raw.includes('/')) issues.push('检测到正斜杠，下载时会转换为 Windows 反斜杠')
    if (!isWindowsAbsolute(normalized)) issues.push('Windows 路径必须是盘符路径或 UNC 路径')
  }
  const valid = !issues.some(issue => issue.includes('必须') || issue.includes('请填写'))
  return { valid, normalized, issues }
}

function downloadMp4() {
  if (!state.value?.outputs?.mp4?.available) return
  window.open(`${baseURL}/ai/native/video/kepu/tasks/${taskId}/download-mp4`, '_blank')
}

function downloadDraft() {
  const check = pathCheck.value
  const query = new URLSearchParams({ target_os: targetOS.value })
  if (check.valid && check.normalized) {
    const path = check.normalized
    extractPath.value = path
    localStorage.setItem('extract_path', path)
    localStorage.setItem('kepu:mine:extract_path', path)
    query.set('extract_path', path)
  }
  localStorage.setItem('kepu:mine:draft_target_os', targetOS.value)
  window.open(`${baseURL}/ai/native/video/kepu/tasks/${taskId}/download?${query.toString()}`, '_blank')
}
</script>

<style scoped>
.export-view {
  min-height: 100vh;
  background: var(--color-bg);
}

.export-shell {
  width: min(1120px, calc(100% - 32px));
  margin: 0 auto;
  padding: 28px 0 40px;
}

.export-content {
  min-height: 360px;
}

.export-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}

.eyebrow {
  margin: 0 0 6px;
  color: var(--color-text-tertiary);
  font-size: 12px;
  font-weight: 700;
}

h1 {
  margin: 0;
  font-size: 26px;
  letter-spacing: 0;
}

.ratio-pill {
  min-width: 132px;
  min-height: 54px;
  display: grid;
  place-items: center;
  border: none;
  border-radius: var(--radius-lg);
  background: #fff;
  box-shadow: var(--shadow-sm);
}

.ratio-pill span {
  font-size: 18px;
  font-weight: 800;
  color: var(--color-text);
}

.ratio-pill strong {
  font-size: 11px;
  color: var(--color-text-tertiary);
}

.status-strip {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  margin-bottom: 14px;
}

.status-strip > div {
  min-height: 62px;
  padding: 12px;
  border: none;
  border-radius: var(--radius-md);
  background: #fff;
  box-shadow: var(--shadow-sm);
}

.status-strip span {
  display: block;
  margin-bottom: 8px;
  color: var(--color-text-tertiary);
  font-size: 12px;
}

.status-strip strong {
  color: var(--color-text-secondary);
  font-size: 15px;
}

.status-strip strong.ok {
  color: var(--color-success);
}

.status-strip strong.warn {
  color: #b45309;
}

.export-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.export-card {
  min-height: 300px;
  display: grid;
  align-content: start;
  gap: 18px;
  padding: 20px;
  border: none;
  border-radius: var(--radius-xl);
  background: #fff;
  box-shadow: var(--shadow-md);
  transition: all var(--duration-normal) var(--ease-out);
}

.export-card:hover {
  box-shadow: var(--shadow-lg);
  transform: translateY(-2px);
}

.export-card.preferred {
  border: 2px solid var(--color-primary);
  box-shadow: 0 0 0 4px rgba(0, 0, 0, 0.04);
}

.export-card.preferred::before {
  content: "默认";
  justify-self: start;
  padding: 4px 12px;
  border-radius: var(--radius-md);
  background: var(--color-primary);
  color: #ffffff;
  font-size: 12px;
  font-weight: 600;
}

.card-icon {
  width: 42px;
  height: 42px;
  display: grid;
  place-items: center;
  border-radius: 8px;
}

.video-icon {
  color: #2563eb;
  background: rgba(37, 99, 235, 0.1);
}

.draft-icon {
  color: #059669;
  background: rgba(5, 150, 105, 0.1);
}

.card-icon svg {
  width: 20px;
  height: 20px;
}

.card-copy h2 {
  margin: 0 0 8px;
  font-size: 18px;
}

.card-copy p,
.error-text {
  margin: 0;
  color: var(--color-text-tertiary);
  font-size: 13px;
  line-height: 1.6;
}

.error-text {
  color: #b91c1c;
}

.path-field,
.platform-field {
  display: grid;
  gap: 8px;
}

.path-field span,
.platform-field span {
  color: var(--color-text-secondary);
  font-size: 12px;
  font-weight: 600;
}

.path-input-group {
  display: flex;
  gap: 8px;
  align-items: center;
}

.path-input-group input {
  flex: 1;
  height: 40px;
  padding: 0 14px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg-secondary);
  color: var(--color-text);
  outline: none;
  transition: all var(--duration-fast) var(--ease-out);
}

.path-input-group input:focus {
  border-color: var(--color-accent);
  background: #fff;
  box-shadow: 0 0 0 4px rgba(0, 113, 227, 0.1);
}

.folder-btn {
  height: 40px;
  padding: 0 18px;
  display: flex;
  align-items: center;
  gap: 6px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xl);
  background: #fff;
  color: var(--color-text-secondary);
  font-size: 14px;
  font-weight: 400;
  letter-spacing: -0.016em;
  cursor: pointer;
  transition: all var(--duration-normal) var(--ease-out);
  white-space: nowrap;
}

.folder-btn:hover:not(:disabled) {
  border-color: var(--color-primary);
  color: var(--color-primary);
  background: var(--color-primary-bg);
}

.folder-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.path-normalized,
.path-issues {
  display: grid;
  gap: 4px;
  padding: 8px 10px;
  border-radius: 8px;
  font-size: 11px;
  line-height: 1.45;
}

.path-normalized {
  overflow-wrap: anywhere;
  background: var(--color-success-bg);
  color: #047857;
}

.path-issues {
  background: #fff7ed;
  color: #b45309;
}

.platform-switch {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.platform-switch button {
  min-height: 36px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: #fff;
  color: var(--color-text-secondary);
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}

.platform-switch button.active {
  border-color: var(--color-primary);
  background: var(--color-primary-bg);
  color: var(--color-primary);
}

.card-actions,
.footer-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.footer-actions {
  justify-content: flex-end;
  margin-top: 16px;
}

.primary-btn,
.secondary-btn {
  min-height: 40px;
  padding: 0 20px;
  border-radius: var(--radius-xl);
  font-size: 14px;
  font-weight: 400;
  letter-spacing: -0.016em;
  cursor: pointer;
  transition: all var(--duration-normal) var(--ease-out);
}

.primary-btn {
  border: none;
  background: var(--color-primary);
  color: #ffffff;
  box-shadow: var(--shadow-sm);
}

.primary-btn:hover:not(:disabled) {
  background: var(--color-primary-hover);
  transform: scale(1.02);
}

.primary-btn:active:not(:disabled) {
  transform: scale(0.98);
}

.secondary-btn {
  border: 1px solid var(--color-primary);
  background: transparent;
  color: var(--color-primary);
}

.secondary-btn:hover:not(:disabled) {
  background: var(--color-primary-bg);
}

.primary-btn:disabled,
.secondary-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

@media (max-width: 820px) {
  .export-header,
  .footer-actions {
    align-items: stretch;
    flex-direction: column;
  }
  .status-strip,
  .export-grid {
    grid-template-columns: 1fr;
  }
}
</style>
