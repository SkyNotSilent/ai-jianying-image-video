<template>
  <div class="asset-page">
    <NavBar active-tab="library" searchable v-model:search-value="search" @navigate="handleNavigate" />

    <main class="asset-layout">
      <aside class="filters-panel">
        <div class="panel-title">
          <h2>筛选条件</h2>
          <button type="button" @click="resetFilters">重置</button>
        </div>

        <section class="filter-group">
          <div class="filter-head">项目状态</div>
          <button v-for="item in statusFilters" :key="item.key" type="button" :class="{ active: statusFilter === item.key }" @click="statusFilter = item.key">
            <span :class="['dot', item.tone]"></span>
            <strong>{{ item.label }}</strong>
            <em>{{ statusCount(item.key) }}</em>
          </button>
        </section>

        <section class="filter-group">
          <div class="filter-head">视频风格</div>
          <button type="button" :class="{ active: !styleFilter }" @click="styleFilter = ''">
            <span class="style-dot style-all"></span>
            <strong>全部风格</strong>
            <em>{{ statusCount('all') }}</em>
          </button>
          <button v-for="style in visualStyles" :key="style.value" type="button" :class="{ active: styleFilter === style.value }" @click="styleFilter = style.value">
            <span class="style-dot"></span>
            <strong>{{ style.label }}</strong>
            <em>{{ styleCount(style.value) }}</em>
          </button>
        </section>

        <section class="filter-group">
          <div class="filter-head">时长</div>
          <button v-for="item in durationFilters" :key="item" type="button" :class="{ active: durationFilter === item }" @click="durationFilter = item">
            <span class="radio"></span>
            <strong>{{ item }}</strong>
          </button>
        </section>

      </aside>

      <section class="project-section">
        <div class="section-top">
          <div>
            <h1>{{ sectionTitle }} <span>{{ filteredProjects.length }}</span></h1>
          </div>
          <div class="view-tools">
            <select v-model="sortMode">
              <option value="updated">最近更新</option>
              <option value="name">项目名称</option>
              <option value="status">项目状态</option>
            </select>
            <button type="button" class="primary-action new-script-btn" @click="createProject">
              <Plus />
              新建文稿
            </button>
          </div>
        </div>

        <div v-if="loading" class="project-grid">
          <article v-for="idx in 6" :key="idx" class="project-card skeleton"></article>
        </div>

        <el-empty v-else-if="filteredProjects.length === 0" description="暂无匹配项目" />

        <div v-else class="project-grid">
          <article v-for="project in filteredProjects" :key="project.id" class="project-card" @click="openProject(project)">
            <div class="thumb" :class="{ empty: !usableCover(project) }">
              <img v-if="usableCover(project)" :src="project.cover" :alt="project.name" @error="markCoverBroken(project.id)" />
              <div v-else class="thumb-empty">
                <strong>{{ project.name.slice(0, 2) }}</strong>
                <small>{{ project.type === 'draft' ? '文稿草稿' : '暂无画面' }}</small>
              </div>
              <span>{{ project.duration }}</span>
            </div>
            <div class="card-copy">
              <div class="card-title-row">
                <h3>{{ project.name }}</h3>
                <button type="button" @click.stop="deleteLocalProject(project)"><MoreFilled /></button>
              </div>
              <div class="status-row">
                <span :class="['status-pill', project.tone]">{{ project.statusLabel }}</span>
                <strong>{{ projectActionLabel(project) }}</strong>
              </div>
              <div class="meta-line">
                <small>{{ project.provider }}</small>
                <time>{{ project.updatedAt }}</time>
              </div>
            </div>
          </article>
        </div>

        <div v-if="!loading && filteredProjects.length > 0" class="result-count">
          <span>共 {{ filteredProjects.length }} 项</span>
        </div>
      </section>
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { MoreFilled, Plus } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import NavBar from '../components/NavBar.vue'
import { getSegments, listTasks } from '../api/task'
import { createDraft, deleteDraft, estimateDuration, formatLocalTime, listDrafts, visualStyles } from '../utils/projectDrafts'
import { normalizeMediaUrl } from '../utils/mediaUrl'
import { deriveTaskState } from '../utils/taskState'

const router = useRouter()
const loading = ref(true)
const search = ref('')
const statusFilter = ref('all')
const styleFilter = ref('')
const durationFilter = ref('全部时长')
const sortMode = ref('updated')
const remoteTasks = ref([])
const localDrafts = ref([])
const brokenCovers = ref({})
const fallbackCovers = ref({})

const statusFilters = [
  { key: 'all', label: '全部项目', tone: 'info' },
  { key: 'draft', label: '草稿', tone: 'neutral' },
  { key: 'processing', label: '生成中', tone: 'info' },
  { key: 'completed', label: '已完成', tone: 'success' },
  { key: 'recoverable_assets', label: '失败可恢复', tone: 'danger' },
]
const durationFilters = ['全部时长', '1 分钟以内', '1-3 分钟', '3-5 分钟', '5 分钟以上']
const defaultVisibleStatuses = new Set(['processing', 'completed', 'export_ready'])

const projects = computed(() => {
  const usefulDrafts = localDrafts.value.filter((draft) => draft.name?.trim() || draft.manuscript?.trim() || draft.theme?.trim())
  const drafts = usefulDrafts.map((draft) => ({
    id: draft.draft_id,
    type: 'draft',
    name: draft.name || draft.theme || '未命名文稿',
    status: 'draft',
    statusLabel: '草稿',
    tone: 'warning',
    provider: '本地文稿',
    duration: estimateDuration(draft.manuscript || draft.theme),
    updatedAt: formatLocalTime(draft.updated_at),
    cover: '',
    visualStyle: draft.visual_style,
    draft,
  }))

  const tasks = remoteTasks.value.map((task) => {
    const state = deriveTaskState({ task })
    return {
      id: task.task_id,
      type: 'task',
      name: task.name || task.result?.theme || task.theme || `视频任务 ${task.task_id?.slice(0, 6)}`,
      status: state.key,
      statusLabel: state.label,
      tone: state.tone,
      actionLabel: state.actionLabel,
      provider: task.voice_type ? `TTS · ${task.voice_type}` : '生成任务',
      duration: task.result?.total_duration ? secondsToLabel(task.result.total_duration) : '--:--',
      updatedAt: formatLocalTime(task.updated_at || task.created_at || task.result?.created_at),
      cover: normalizeMediaUrl(task.cover_image_url || fallbackCovers.value[task.task_id] || ''),
      visualStyle: '',
      task,
    }
  })

  return [...drafts, ...tasks]
})

const sectionTitle = computed(() => statusFilters.find((item) => item.key === statusFilter.value)?.label || '全部项目')

const filteredProjects = computed(() => {
  const keyword = search.value.trim().toLowerCase()
  return projects.value
    .filter((project) => {
      if (statusFilter.value === 'draft') return project.type === 'draft'
      if (project.type === 'draft') return false
      if (statusFilter.value === 'all') return defaultVisibleStatuses.has(project.status)
      return project.status === statusFilter.value
    })
    .filter((project) => project.type === 'draft' || !styleFilter.value || project.visualStyle === styleFilter.value)
    .filter((project) => !keyword || project.name.toLowerCase().includes(keyword) || project.provider.toLowerCase().includes(keyword))
    .sort((a, b) => {
      if (sortMode.value === 'name') return a.name.localeCompare(b.name, 'zh-CN')
      if (sortMode.value === 'status') return a.status.localeCompare(b.status)
      return b.updatedAt.localeCompare(a.updatedAt)
    })
})

onMounted(loadProjects)

async function loadProjects() {
  loading.value = true
  localDrafts.value = listDrafts()
  try {
    remoteTasks.value = await listTasks(undefined, 80, 0)
    await hydrateFallbackCovers(remoteTasks.value)
  } catch (error) {
    console.warn('加载任务列表失败', error)
    remoteTasks.value = []
  } finally {
    loading.value = false
  }
}

async function hydrateFallbackCovers(tasks) {
  const missingTasks = tasks
    .filter((task) => !normalizeMediaUrl(task.cover_image_url))
    .slice(0, 24)
  if (missingTasks.length === 0) return

  const entries = await Promise.all(missingTasks.map(async (task) => {
    try {
      const segments = await getSegments(task.task_id)
      const first = Array.isArray(segments) ? segments.find((segment) => normalizeMediaUrl(segment.image_url)) : null
      return [task.task_id, normalizeMediaUrl(first?.image_url)]
    } catch (error) {
      return [task.task_id, '']
    }
  }))

  const next = {}
  entries.forEach(([taskId, cover]) => {
    if (cover) next[taskId] = cover
  })
  fallbackCovers.value = { ...fallbackCovers.value, ...next }
}

function createProject() {
  const draft = createDraft()
  router.push(`/manuscript/${draft.draft_id}`)
}

function projectActionLabel(project) {
  if (project.type === 'draft') return '继续文稿'
  return project.actionLabel || '查看预览'
}

function openProject(project) {
  if (project.type === 'draft') {
    router.push(`/manuscript/${project.id}`)
    return
  }
  if (project.status === 'processing') {
    router.push(`/process/${project.id}`)
    return
  }
  router.push(`/preview/${project.id}`)
}

async function deleteLocalProject(project) {
  if (project.type !== 'draft') return
  await ElMessageBox.confirm('确认删除这个本地草稿？', '删除草稿', { type: 'warning' })
  deleteDraft(project.id)
  localDrafts.value = listDrafts()
  ElMessage.success('草稿已删除')
}

function resetFilters() {
  statusFilter.value = 'all'
  styleFilter.value = ''
  durationFilter.value = '全部时长'
  search.value = ''
}

function statusCount(key) {
  if (key === 'all') return projects.value.filter((project) => project.type !== 'draft' && defaultVisibleStatuses.has(project.status)).length
  return projects.value.filter((project) => project.status === key).length
}

function styleCount(value) {
  return projects.value.filter((project) => project.type !== 'draft' && defaultVisibleStatuses.has(project.status) && project.visualStyle === value).length
}

function usableCover(project) {
  return Boolean(project.cover && !brokenCovers.value[project.id])
}

function markCoverBroken(projectId) {
  brokenCovers.value = { ...brokenCovers.value, [projectId]: true }
}

function handleNavigate(tab) {
  if (tab === 'settings') router.push('/settings')
  else if (tab === 'library') router.push('/assets')
  else router.push('/')
}

function secondsToLabel(value) {
  const seconds = Math.round(Number(value) || 0)
  const min = Math.floor(seconds / 60)
  const sec = seconds % 60
  return `${String(min).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
}
</script>

<style scoped>
.asset-page {
  min-height: 100vh;
}

.asset-layout {
  height: calc(100vh - 64px);
  display: grid;
  grid-template-columns: 236px minmax(0, 1fr);
  border-top: 1px solid rgba(255, 255, 255, 0.6);
}

.filters-panel {
  min-height: 0;
  overflow: auto;
  background: rgba(255, 255, 255, 0.68);
  border-right: 1px solid var(--color-border);
  padding: 24px 20px;
}

.panel-title,
.section-top,
.card-title-row,
.meta-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.panel-title h2 {
  font-size: 18px;
}

.panel-title button,
.card-title-row button {
  border: 0;
  background: transparent;
  color: var(--color-text-tertiary);
  cursor: pointer;
}

.filter-group {
  display: grid;
  gap: 8px;
  margin-top: 28px;
}

.filter-head {
  margin-bottom: 6px;
  color: var(--color-text-secondary);
  font-size: 13px;
  font-weight: 800;
}

.filter-group button {
  min-height: 38px;
  display: flex;
  align-items: center;
  gap: 10px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: var(--color-text-secondary);
  padding: 0 10px;
  cursor: pointer;
  text-align: left;
}

.filter-group button.active,
.filter-group button:hover {
  background: var(--color-primary-bg);
  color: var(--color-primary);
}

.style-dot {
  width: 26px;
  height: 26px;
  border-radius: 7px;
  border: 1px solid #d8e2f0;
  background:
    linear-gradient(135deg, rgba(15, 98, 254, 0.12), rgba(21, 190, 166, 0.08)),
    #f8fafc;
}

.style-all {
  background: linear-gradient(135deg, #eff4ff, #e8f7ee);
}

.filter-group strong {
  flex: 1;
  font-size: 14px;
}

.filter-group em {
  font-style: normal;
  color: var(--color-text-tertiary);
}

.dot,
.radio {
  width: 13px;
  height: 13px;
  border-radius: 50%;
  border: 2px solid currentColor;
}

.dot.success { color: var(--color-success); }
.dot.danger { color: var(--color-danger); }
.dot.info { color: var(--color-primary); }
.dot.neutral { color: var(--color-text-tertiary); }

.project-section {
  min-width: 0;
  min-height: 0;
  overflow: auto;
  padding: 30px 24px 34px;
}

.section-top {
  margin-bottom: 20px;
}

.section-top h1 {
  font-size: 23px;
  letter-spacing: -0.02em;
}

.section-top h1 span {
  color: var(--color-text-tertiary);
  font-weight: 500;
}

.view-tools {
  display: flex;
  gap: 10px;
  align-items: center;
}

.view-tools select {
  height: 40px;
  border: 1px solid var(--color-border);
  border-radius: 10px;
  padding: 0 12px;
  background: #fff;
}

.new-script-btn {
  height: 40px;
  padding: 0 16px;
}

.new-script-btn svg {
  width: 16px;
  height: 16px;
}

.project-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(190px, 1fr));
  gap: 16px;
}

.project-card {
  min-width: 0;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: #fff;
  overflow: hidden;
  cursor: pointer;
  box-shadow: none;
  transition: transform 0.18s var(--ease-out), box-shadow 0.18s var(--ease-out), border-color 0.18s;
}

.project-card:hover {
  transform: translateY(-1px);
  border-color: #d2d8e2;
  box-shadow: var(--shadow-xs);
}

.project-card.skeleton {
  height: 248px;
  background: linear-gradient(90deg, #f4f5f7, #fff, #f4f5f7);
}

.thumb {
  position: relative;
  aspect-ratio: 16 / 9;
  background: #eef1f5;
}

.thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.thumb.empty {
  display: grid;
  place-items: center;
  background:
    linear-gradient(135deg, rgba(15, 98, 254, 0.08), rgba(21, 190, 166, 0.06)),
    #f6f8fb;
}

.thumb-empty {
  display: grid;
  gap: 6px;
  place-items: center;
  color: var(--color-text-secondary);
}

.thumb-empty strong {
  width: 44px;
  height: 44px;
  display: grid;
  place-items: center;
  border-radius: 10px;
  background: #fff;
  color: var(--color-primary);
  font-size: 16px;
  box-shadow: var(--shadow-sm);
}

.thumb-empty small {
  color: var(--color-text-tertiary);
  font-size: 12px;
}

.thumb span {
  position: absolute;
  right: 10px;
  bottom: 10px;
  padding: 3px 8px;
  border-radius: 7px;
  background: rgba(0, 0, 0, 0.72);
  color: #fff;
  font-size: 12px;
  font-weight: 800;
}

.card-copy {
  display: grid;
  gap: 9px;
  padding: 12px 12px 14px;
}

.status-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.status-row strong {
  color: var(--color-primary);
  font-size: 13px;
}

.result-count {
  display: flex;
  align-items: center;
  margin-top: 30px;
  color: var(--color-text-secondary);
}

.card-title-row h3 {
  min-width: 0;
  font-size: 15px;
  line-height: 1.35;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.meta-line {
  min-width: 0;
  color: var(--color-text-tertiary);
  gap: 10px;
}

.meta-line small {
  min-width: 0;
  max-width: 128px;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  padding: 4px 8px;
  border-radius: 7px;
  background: #f5f4f2;
  color: var(--color-text-secondary);
  font-weight: 700;
}

@media (max-width: 1240px) {
  .asset-layout {
    grid-template-columns: 220px minmax(0, 1fr);
  }

  .project-grid {
    grid-template-columns: repeat(2, minmax(220px, 1fr));
  }
}
</style>
