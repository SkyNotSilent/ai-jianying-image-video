import { useCallback, useEffect, useMemo, useState } from 'react'
import { ArrowRight, FileText, ImageOff, MoreHorizontal, Plus, RotateCcw, Search } from 'lucide-react'
import { useNavigate } from 'react-router'
import { getSegments, listTasks } from '../api/task'
import { ConfirmDialog } from '../components/Modal'
import { EmptyState, LoadingState } from '../components/StatusStates'
import { toast } from '../lib/toast'
import { createDraft, deleteDraft, estimateDuration, formatLocalTime, listDrafts, visualStyles } from '../utils/projectDrafts'
import { normalizeMediaUrl } from '../utils/mediaUrl'
import { deriveTaskState } from '../utils/taskState'
import './delivery-pages.css'

const STATUS_FILTERS = [
  { key: 'all', label: '全部项目', tone: 'info' },
  { key: 'draft', label: '草稿', tone: 'warning' },
  { key: 'processing', label: '生成中', tone: 'info' },
  { key: 'completed', label: '已完成', tone: 'success' },
  { key: 'recoverable_assets', label: '失败可恢复', tone: 'danger' },
]
const DURATION_FILTERS = ['全部时长', '1 分钟以内', '1-3 分钟', '3-5 分钟', '5 分钟以上']
const DEFAULT_VISIBLE_STATUSES = new Set(['processing', 'completed', 'export_ready', 'recoverable_assets'])

function secondsToLabel(value) {
  const seconds = Math.round(Number(value) || 0)
  return `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`
}

function durationToSeconds(label) {
  const [minutes = 0, seconds = 0] = String(label || '').split(':').map(Number)
  return (Number(minutes) || 0) * 60 + (Number(seconds) || 0)
}

function matchesDuration(seconds, filter) {
  if (!Number.isFinite(seconds) || seconds <= 0) return filter === '全部时长'
  if (filter === '1 分钟以内') return seconds < 60
  if (filter === '1-3 分钟') return seconds >= 60 && seconds < 180
  if (filter === '3-5 分钟') return seconds >= 180 && seconds < 300
  if (filter === '5 分钟以上') return seconds >= 300
  return true
}

function firstSegmentCover(segments) {
  return [...(Array.isArray(segments) ? segments : [])]
    .sort((a, b) => Number(a?.segment_index ?? 0) - Number(b?.segment_index ?? 0))
    .map(segment => normalizeMediaUrl(segment?.image_url))
    .find(Boolean) || ''
}

export function ProjectAssetsPage() {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [styleFilter, setStyleFilter] = useState('')
  const [durationFilter, setDurationFilter] = useState('全部时长')
  const [sortMode, setSortMode] = useState('updated')
  const [remoteTasks, setRemoteTasks] = useState([])
  const [taskSegments, setTaskSegments] = useState({})
  const [localDrafts, setLocalDrafts] = useState([])
  const [brokenCovers, setBrokenCovers] = useState({})
  const [fallbackCovers, setFallbackCovers] = useState({})
  const [draftToDelete, setDraftToDelete] = useState(null)

  const loadProjects = useCallback(async () => {
    setLoading(true)
    setLocalDrafts(listDrafts())
    try {
      const tasks = await listTasks(undefined, 80, 0)
      const taskList = Array.isArray(tasks) ? tasks : []
      setRemoteTasks(taskList)
      const segmentEntries = await Promise.all(taskList.map(async task => {
        try {
          return [task.task_id, await getSegments(task.task_id)]
        } catch {
          return [task.task_id, []]
        }
      }))
      const nextSegments = Object.fromEntries(segmentEntries)
      setTaskSegments(nextSegments)
      const missing = taskList.filter(task => !normalizeMediaUrl(task.cover_image_url)).slice(0, 24)
      setFallbackCovers(current => ({
        ...current,
        ...Object.fromEntries(missing
          .map(task => [task.task_id, firstSegmentCover(nextSegments[task.task_id])])
          .filter(([, cover]) => cover)),
      }))
    } catch (error) {
      console.warn('加载任务列表失败', error)
      setRemoteTasks([])
      toast.error('加载项目任务失败，本地草稿仍可使用')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadProjects() }, [loadProjects])

  const projects = useMemo(() => {
    const drafts = localDrafts
      .filter(draft => draft.name?.trim() || draft.manuscript?.trim() || draft.theme?.trim())
      .map(draft => {
        const duration = estimateDuration(draft.manuscript || draft.theme)
        return {
          id: draft.draft_id,
          type: 'draft',
          name: draft.name || draft.theme || '未命名文稿',
          status: 'draft',
          statusLabel: '草稿',
          tone: 'warning',
          provider: '本地文稿',
          duration,
          durationSeconds: durationToSeconds(duration),
          updatedAt: formatLocalTime(draft.updated_at),
          sortTime: draft.updated_at || '',
          cover: '',
          visualStyle: draft.visual_style || '',
        }
      })
    const tasks = remoteTasks.map(task => {
      const segments = taskSegments[task.task_id] || []
      const state = deriveTaskState({ task, segments })
      const durationSeconds = taskDurationSeconds(task, segments)
      return {
        id: task.task_id,
        type: 'task',
        name: task.name || task.result?.theme || task.theme || `视频任务 ${task.task_id?.slice(0, 6)}`,
        status: state.key,
        statusLabel: state.label,
        tone: state.tone,
        actionLabel: state.actionLabel,
        provider: task.voice_type ? `TTS · ${task.voice_type}` : '生成任务',
        duration: durationSeconds ? secondsToLabel(durationSeconds) : '--:--',
        durationSeconds,
        updatedAt: formatLocalTime(task.updated_at || task.created_at || task.result?.created_at),
        sortTime: task.updated_at || task.created_at || task.result?.created_at || '',
        cover: normalizeMediaUrl(task.cover_image_url || fallbackCovers[task.task_id] || ''),
        visualStyle: task.visual_style || task.result?.visual_style || '',
      }
    })
    return [...drafts, ...tasks]
  }, [fallbackCovers, localDrafts, remoteTasks, taskSegments])

  const filteredProjects = useMemo(() => {
    const keyword = search.trim().toLowerCase()
    return projects
      .filter(project => {
        if (statusFilter === 'draft') return project.type === 'draft'
        if (project.type === 'draft') return false
        if (statusFilter === 'all') return DEFAULT_VISIBLE_STATUSES.has(project.status)
        if (statusFilter === 'completed') return project.status === 'completed' || project.status === 'export_ready'
        return project.status === statusFilter
      })
      .filter(project => project.type === 'draft' || !styleFilter || project.visualStyle === styleFilter)
      .filter(project => matchesDuration(project.durationSeconds, durationFilter))
      .filter(project => !keyword || project.name.toLowerCase().includes(keyword) || project.provider.toLowerCase().includes(keyword))
      .sort((a, b) => {
        if (sortMode === 'name') return a.name.localeCompare(b.name, 'zh-CN')
        if (sortMode === 'status') return a.status.localeCompare(b.status)
        return String(b.sortTime).localeCompare(String(a.sortTime))
      })
  }, [durationFilter, projects, search, sortMode, statusFilter, styleFilter])

  const statusCount = key => {
    if (key === 'all') return projects.filter(project => project.type === 'task' && DEFAULT_VISIBLE_STATUSES.has(project.status)).length
    if (key === 'completed') return projects.filter(project => project.status === 'completed' || project.status === 'export_ready').length
    return projects.filter(project => project.status === key).length
  }
  const styleCount = value => projects.filter(project => project.type === 'task' && DEFAULT_VISIBLE_STATUSES.has(project.status) && project.visualStyle === value).length

  const resetFilters = () => {
    setStatusFilter('all')
    setStyleFilter('')
    setDurationFilter('全部时长')
    setSearch('')
  }

  const createProject = () => {
    const draft = createDraft()
    navigate(`/manuscript/${draft.draft_id}`)
  }

  const openProject = project => {
    if (project.type === 'draft') navigate(`/manuscript/${project.id}`)
    else if (project.status === 'processing') navigate(`/process/${project.id}`)
    else navigate(`/preview/${project.id}`)
  }

  const confirmDelete = () => {
    if (!draftToDelete) return
    deleteDraft(draftToDelete.id)
    setLocalDrafts(listDrafts())
    setDraftToDelete(null)
    toast.success('草稿已删除')
  }

  const sectionTitle = STATUS_FILTERS.find(item => item.key === statusFilter)?.label || '全部项目'

  return (
    <main className="assets-page">
      <aside className="assets-filters" aria-label="项目筛选">
        <div className="assets-filter-title"><h2>筛选条件</h2><button type="button" onClick={resetFilters}><RotateCcw size={14} aria-hidden="true" />重置</button></div>
        <FilterGroup label="项目状态" items={STATUS_FILTERS.map(item => ({ ...item, count: statusCount(item.key) }))} value={statusFilter} onChange={setStatusFilter} />
        <FilterGroup label="视频风格" items={[{ key: '', label: '全部风格', count: statusCount('all') }, ...visualStyles.map(style => ({ key: style.value, label: style.label, count: styleCount(style.value) }))]} value={styleFilter} onChange={setStyleFilter} />
        <FilterGroup label="时长" items={DURATION_FILTERS.map(item => ({ key: item, label: item }))} value={durationFilter} onChange={setDurationFilter} />
      </aside>

      <section className="assets-workspace">
        <header className="assets-toolbar">
          <div><p className="eyebrow">项目资产</p><h1>{sectionTitle} <span>{filteredProjects.length}</span></h1></div>
          <div className="assets-toolbar-actions">
            <label className="assets-search"><Search size={16} aria-hidden="true" /><span className="sr-only">搜索项目</span><input value={search} onChange={event => setSearch(event.target.value)} placeholder="搜索名称或音色" /></label>
            <select aria-label="项目排序" value={sortMode} onChange={event => setSortMode(event.target.value)}><option value="updated">最近更新</option><option value="name">项目名称</option><option value="status">项目状态</option></select>
            <button className="button button-primary" type="button" onClick={createProject}><Plus size={16} aria-hidden="true" />新建文稿</button>
          </div>
        </header>

        {loading ? <LoadingState label="正在汇总本地草稿和任务..." /> : filteredProjects.length === 0 ? <EmptyState title="暂无匹配项目" description="调整筛选条件，或创建一份新文稿。" action={<button className="button button-primary" type="button" onClick={createProject}><Plus size={16} aria-hidden="true" />新建文稿</button>} /> : (
          <div className="asset-project-grid">
            {filteredProjects.map(project => {
              const usableCover = Boolean(project.cover && !brokenCovers[project.id])
              return (
                <article className="asset-project-card" key={project.id}>
                  <button className="asset-project-open" type="button" onClick={() => openProject(project)} aria-label={`打开 ${project.name}`}>
                    <div className={`asset-project-thumb${usableCover ? '' : ' is-empty'}`}>
                      {usableCover ? <img src={project.cover} alt="" onError={() => setBrokenCovers(current => ({ ...current, [project.id]: true }))} /> : <div><ImageOff size={22} aria-hidden="true" /><strong>{project.name.slice(0, 2)}</strong><small>{project.type === 'draft' ? '文稿草稿' : '暂无画面'}</small></div>}
                      <span>{project.duration}</span>
                    </div>
                    <div className="asset-project-copy">
                      <h2>{project.name}</h2>
                      <div className="asset-project-status"><span className={`status-pill is-${project.tone}`}>{project.statusLabel}</span><strong>{project.type === 'draft' ? '继续文稿' : project.actionLabel || '查看预览'} <ArrowRight size={13} aria-hidden="true" /></strong></div>
                      <div className="asset-project-meta"><span>{project.provider}</span><time>{project.updatedAt}</time></div>
                    </div>
                  </button>
                  {project.type === 'draft' && <button className="asset-project-menu icon-button" type="button" title="删除本地草稿" aria-label={`删除 ${project.name}`} onClick={() => setDraftToDelete(project)}><MoreHorizontal size={18} aria-hidden="true" /></button>}
                </article>
              )
            })}
          </div>
        )}
        {!loading && filteredProjects.length > 0 && <footer className="assets-result-count"><FileText size={15} aria-hidden="true" />共 {filteredProjects.length} 项</footer>}
      </section>

      <ConfirmDialog open={Boolean(draftToDelete)} title="删除草稿" message="确认删除这个本地草稿？此操作不会删除任何后端任务。" confirmLabel="删除草稿" danger onConfirm={confirmDelete} onClose={() => setDraftToDelete(null)} />
    </main>
  )
}

function taskDurationSeconds(task, segments) {
  const directDuration = Number(task?.total_duration ?? task?.result?.total_duration)
  if (directDuration > 0) return directDuration
  return (Array.isArray(segments) ? segments : []).reduce((total, segment) => total + (Number(segment?.duration) || 0), 0)
}

function FilterGroup({ label, items, value, onChange }) {
  return (
    <section className="assets-filter-group">
      <h3>{label}</h3>
      {items.map(item => <button type="button" key={item.key} className={value === item.key ? 'is-active' : ''} onClick={() => onChange(item.key)}><span className={`filter-dot is-${item.tone || 'neutral'}`} aria-hidden="true" /><strong>{item.label}</strong>{item.count !== undefined && <em>{item.count}</em>}</button>)}
    </section>
  )
}
