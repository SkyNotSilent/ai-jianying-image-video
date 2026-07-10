import { useEffect, useMemo, useRef, useState } from 'react'
import {
  ArrowLeft,
  CheckCircle2,
  CircleAlert,
  Download,
  FileArchive,
  Film,
  FolderOpen,
  HardDriveDownload,
  LoaderCircle,
} from 'lucide-react'
import { useNavigate, useParams } from 'react-router'
import { createExport, getExportJob, getExportState, selectDraftFolder } from '../api/task'
import { EmptyState, LoadingState } from '../components/StatusStates'
import { detectTargetOS, validateExtractPath } from '../lib/exportPath'
import { toast } from '../lib/toast'
import './delivery-pages.css'

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:2002'
const ACTIVE_STATUSES = new Set(['pending', 'processing'])

function isBusy(job) {
  return ACTIVE_STATUSES.has(job?.status)
}

function jobLabel(job) {
  if (!job) return ''
  if (job.status === 'completed') return '已完成'
  if (job.status === 'failed') return '失败'
  if (job.status === 'processing') return '处理中'
  if (job.status === 'pending') return '等待中'
  return job.status || ''
}

export function ExportPage() {
  const { taskId } = useParams()
  const navigate = useNavigate()
  const notifiedJobs = useRef(new Set())
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [loadedTaskId, setLoadedTaskId] = useState(null)
  const [state, setState] = useState(null)
  const [jobs, setJobs] = useState({ mp4: null, draft: null, draft_local: null })
  const [extractPath, setExtractPath] = useState(() => (
    localStorage.getItem('kepu:mine:extract_path') || localStorage.getItem('extract_path') || ''
  ))
  const [targetOS, setTargetOSState] = useState(() => (
    localStorage.getItem('kepu:mine:draft_target_os') || detectTargetOS()
  ))
  const [defaultExport] = useState(() => localStorage.getItem('kepu:mine:default_export') || 'mp4')
  const [folderPicking, setFolderPicking] = useState(false)
  const pathCheck = useMemo(() => validateExtractPath(extractPath, targetOS), [extractPath, targetOS])
  const activeJobs = useMemo(
    () => loadedTaskId === taskId ? Object.entries(jobs).filter(([, job]) => isBusy(job)) : [],
    [jobs, loadedTaskId, taskId],
  )

  const loadState = async ({ showLoader = false } = {}) => {
    if (showLoader) setLoading(true)
    try {
      const nextState = await getExportState(taskId)
      const stateJobs = Array.isArray(nextState?.jobs) ? nextState.jobs : []
      setState(nextState)
      setLoadedTaskId(taskId)
      setJobs(current => ({
        mp4: stateJobs.find(job => job.target === 'mp4') || current.mp4,
        draft: stateJobs.find(job => job.target === 'draft') || current.draft,
        draft_local: stateJobs.find(job => job.target === 'draft_local') || current.draft_local,
      }))
      setLoadError('')
    } catch (error) {
      console.error('加载导出状态失败', error)
      setLoadError('导出状态不可用，请确认后端服务在线后重试。')
      toast.error('加载导出状态失败')
    } finally {
      if (showLoader) setLoading(false)
    }
  }

  useEffect(() => {
    let active = true
    setLoading(true)
    setLoadedTaskId(null)
    getExportState(taskId)
      .then(nextState => {
        if (!active) return
        const stateJobs = Array.isArray(nextState?.jobs) ? nextState.jobs : []
        setState(nextState)
        setLoadedTaskId(taskId)
        setJobs({
          mp4: stateJobs.find(job => job.target === 'mp4') || null,
          draft: stateJobs.find(job => job.target === 'draft') || null,
          draft_local: stateJobs.find(job => job.target === 'draft_local') || null,
        })
        setLoadError('')
      })
      .catch(error => {
        if (!active) return
        console.error('加载导出状态失败', error)
        setLoadError('导出状态不可用，请确认后端服务在线后重试。')
        toast.error('加载导出状态失败')
      })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [taskId])

  useEffect(() => {
    if (activeJobs.length === 0) return undefined
    let cancelled = false
    let polling = false

    const poll = async () => {
      if (polling) return
      polling = true
      try {
        const results = await Promise.all(activeJobs.map(async ([target, job]) => {
          try {
            return [target, await getExportJob(taskId, job.job_id)]
          } catch (error) {
            console.error('轮询导出任务失败', error)
            return [target, null]
          }
        }))
        if (cancelled) return
        let finished = false
        results.forEach(([target, job]) => {
          if (!job || ACTIVE_STATUSES.has(job.status)) return
          finished = true
          const notificationKey = `${job.job_id}:${job.status}`
          if (notifiedJobs.current.has(notificationKey)) return
          notifiedJobs.current.add(notificationKey)
          if (job.status === 'completed') {
            toast.success(target === 'mp4' ? 'MP4 已生成' : target === 'draft_local' ? '已写入剪映草稿目录' : '草稿下载已准备好')
          } else if (job.status === 'failed') {
            toast.error(job.error || '导出失败')
          }
        })
        setJobs(current => {
          const next = { ...current }
          results.forEach(([target, job]) => {
            if (!job) return
            next[target] = job
          })
          return next
        })
        if (finished) await loadState()
      } finally {
        polling = false
      }
    }

    poll()
    const timer = window.setInterval(poll, 2000)
    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
  }, [activeJobs, taskId])

  const saveExtractPath = value => {
    setExtractPath(value)
    localStorage.setItem('kepu:mine:extract_path', value || '')
    if (value) localStorage.setItem('extract_path', value)
  }

  const setTargetOS = value => {
    const next = value === 'mac' ? 'mac' : 'windows'
    setTargetOSState(next)
    localStorage.setItem('kepu:mine:draft_target_os', next)
  }

  const chooseDraftFolder = async () => {
    setFolderPicking(true)
    toast.info('请在弹出的窗口里选择剪映草稿目录')
    try {
      const result = await selectDraftFolder(taskId)
      const nextPath = result?.path || ''
      const nextOS = result?.target_os || targetOS
      saveExtractPath(nextPath)
      setTargetOS(nextOS)
      if (result?.warnings?.length) toast.warning(result.warnings[0])
      else toast.success('已选择剪映草稿目录')
    } catch (error) {
      console.error('选择剪映草稿目录失败', error)
      toast.error(error?.response?.data?.detail || '未选择文件夹')
    } finally {
      setFolderPicking(false)
    }
  }

  const startExport = async target => {
    const payload = { target, use_preview: true }
    if (target === 'draft_local') {
      if (!pathCheck.valid) {
        toast.warning(pathCheck.issues[0] || '请先选择剪映草稿目录')
        return
      }
      Object.assign(payload, {
        draft_root: pathCheck.normalized,
        target_os: targetOS,
        overwrite: true,
      })
    }
    try {
      const job = await createExport(taskId, payload)
      setJobs(current => ({ ...current, [target]: job }))
      toast.success(target === 'mp4' ? 'MP4 导出已开始' : target === 'draft_local' ? '正在写入剪映草稿目录' : '草稿下载准备已开始')
    } catch (error) {
      console.error('创建导出任务失败', error)
      toast.error(error?.response?.data?.detail || '创建导出任务失败')
    }
  }

  const downloadMp4 = () => {
    if (state?.outputs?.mp4?.available) window.open(`${API_BASE}/ai/native/video/kepu/tasks/${taskId}/download-mp4`, '_blank')
  }

  const downloadDraft = () => {
    const query = new URLSearchParams({ target_os: targetOS })
    if (pathCheck.valid && pathCheck.normalized) {
      saveExtractPath(pathCheck.normalized)
      query.set('extract_path', pathCheck.normalized)
    }
    localStorage.setItem('kepu:mine:draft_target_os', targetOS)
    window.open(`${API_BASE}/ai/native/video/kepu/tasks/${taskId}/download?${query.toString()}`, '_blank')
  }

  if (loading) return <main className="delivery-loading"><LoadingState label="正在读取导出状态..." /></main>
  if (loadError || !state) {
    return <main className="delivery-loading"><EmptyState title="导出状态不可用" description={loadError} action={<button className="button button-primary" type="button" onClick={() => loadState({ showLoader: true })}>重试</button>} /></main>
  }

  const previewStatus = !state.preview?.exists ? '未生成' : state.preview.valid ? '可复用' : state.preview.reason === 'stale' ? '已过期' : state.preview.reason === 'ratio_mismatch' ? '比例不一致' : '不可用'
  const draftStatus = jobs.draft_local?.status === 'completed' ? '已写入剪映' : isBusy(jobs.draft_local) ? '写入中' : state.outputs?.draft?.available ? '草稿可下载' : '未生成'
  const canvas = state.canvas || {}
  const mp4Available = Boolean(state.outputs?.mp4?.available)
  const draftAvailable = Boolean(state.outputs?.draft?.available)

  return (
    <main className="delivery-page export-page">
      <header className="delivery-heading">
        <button className="button button-secondary" type="button" onClick={() => navigate(`/preview/${taskId}`)}><ArrowLeft size={16} aria-hidden="true" />返回编辑</button>
        <div>
          <p className="eyebrow">导出中心</p>
          <h1>选择交付格式</h1>
          <p>生成成片、下载剪映草稿，或直接写入本机草稿目录。</p>
        </div>
        <div className="export-canvas-meta"><span>{state.ratio || '--'}</span><strong>{canvas.width || '--'} × {canvas.height || '--'}</strong></div>
      </header>

      <section className="delivery-status-strip" aria-label="交付状态">
        <StatusMetric label="最终预览" value={previewStatus} ready={state.preview?.valid} warning={state.preview?.exists && !state.preview?.valid} />
        <StatusMetric label="MP4 成片" value={mp4Available ? '可下载' : '未生成'} ready={mp4Available} />
        <StatusMetric label="剪映草稿" value={draftStatus} ready={jobs.draft_local?.status === 'completed' || draftAvailable} warning={jobs.draft_local?.status === 'failed'} />
      </section>

      <div className="export-options">
        <section className={`export-option${defaultExport === 'mp4' ? ' is-preferred' : ''}`}>
          <div className="export-option-title"><span><Film size={19} aria-hidden="true" /></span><div><h2>直接 MP4 视频</h2><p>{mp4Available ? 'MP4 已生成，可直接下载。' : state.preview?.valid ? '会直接复用当前最终预览，速度最快。' : '最终预览不可复用，需要重新生成 MP4。'}</p></div></div>
          <JobState job={jobs.mp4} fallback="尚未创建 MP4 导出任务" />
          <div className="export-actions">
            <button className="button button-primary" type="button" disabled={!mp4Available} onClick={downloadMp4}><Download size={16} aria-hidden="true" />下载 MP4</button>
            <button className="button button-secondary" type="button" disabled={isBusy(jobs.mp4)} onClick={() => startExport('mp4')}>{isBusy(jobs.mp4) ? <LoaderCircle className="spin" size={16} aria-hidden="true" /> : <Film size={16} aria-hidden="true" />}{isBusy(jobs.mp4) ? '生成中...' : state.preview?.valid ? '使用最终预览生成' : '重新生成 MP4'}</button>
          </div>
        </section>

        <section className={`export-option${defaultExport === 'draft' ? ' is-preferred' : ''}`}>
          <div className="export-option-title"><span><FileArchive size={19} aria-hidden="true" /></span><div><h2>剪映草稿</h2><p>推荐直接写入本机剪映草稿目录，也可以准备 ZIP 后下载。</p></div></div>
          <label className="delivery-field export-path-field">
            <span>剪映草稿目录</span>
            <div className="field-with-action">
              <input value={extractPath} onChange={event => saveExtractPath(event.target.value)} placeholder={targetOS === 'mac' ? '/Users/你的用户名/Movies/JianyingPro/User Data/Projects/com.lveditor.draft' : 'D:\\JianyingPro Drafts'} />
              <button className="button button-secondary" type="button" disabled={folderPicking} onClick={chooseDraftFolder}>{folderPicking ? <LoaderCircle className="spin" size={16} aria-hidden="true" /> : <FolderOpen size={16} aria-hidden="true" />}{folderPicking ? '选择中' : '选择'}</button>
            </div>
          </label>
          {pathCheck.normalized && pathCheck.normalized !== extractPath && <p className="delivery-note"><strong>规范化后：</strong>{pathCheck.normalized}</p>}
          {pathCheck.issues.length > 0 && <div className={`delivery-message${pathCheck.valid ? ' is-warning' : ' is-error'}`}><CircleAlert size={16} aria-hidden="true" /><div>{pathCheck.issues.map(issue => <span key={issue}>{issue}</span>)}</div></div>}
          <fieldset className="delivery-segmented"><legend>剪映所在系统</legend><button type="button" className={targetOS === 'mac' ? 'is-active' : ''} onClick={() => setTargetOS('mac')}>Mac</button><button type="button" className={targetOS === 'windows' ? 'is-active' : ''} onClick={() => setTargetOS('windows')}>Windows</button></fieldset>
          {jobs.draft_local?.result?.draft_path && <p className="delivery-note"><strong>已写入：</strong>{jobs.draft_local.result.draft_path}</p>}
          {jobs.draft_local?.result?.warnings?.length > 0 && <div className="delivery-message is-warning"><CircleAlert size={16} aria-hidden="true" /><div>{jobs.draft_local.result.warnings.map(warning => <span key={warning}>{warning}</span>)}</div></div>}
          <div className="export-job-pair"><JobState job={jobs.draft_local} fallback="尚未写入本地剪映" /><JobState job={jobs.draft} fallback={draftAvailable ? '草稿 ZIP 可下载' : '尚未准备草稿 ZIP'} /></div>
          <div className="export-actions">
            <button className="button button-primary" type="button" disabled={isBusy(jobs.draft_local) || !pathCheck.valid} onClick={() => startExport('draft_local')}>{isBusy(jobs.draft_local) ? <LoaderCircle className="spin" size={16} aria-hidden="true" /> : <HardDriveDownload size={16} aria-hidden="true" />}{isBusy(jobs.draft_local) ? '写入中...' : '写入剪映'}</button>
            {draftAvailable ? <button className="button button-secondary" type="button" onClick={downloadDraft}><Download size={16} aria-hidden="true" />下载草稿 ZIP</button> : <button className="button button-secondary" type="button" disabled={isBusy(jobs.draft)} onClick={() => startExport('draft')}>{isBusy(jobs.draft) ? <LoaderCircle className="spin" size={16} aria-hidden="true" /> : <FileArchive size={16} aria-hidden="true" />}{isBusy(jobs.draft) ? '准备中...' : '准备草稿 ZIP'}</button>}
          </div>
        </section>
      </div>
    </main>
  )
}

function StatusMetric({ label, value, ready = false, warning = false }) {
  return <div><span>{label}</span><strong className={ready ? 'is-ready' : warning ? 'is-warning' : ''}>{ready ? <CheckCircle2 size={15} aria-hidden="true" /> : warning ? <CircleAlert size={15} aria-hidden="true" /> : null}{value}</strong></div>
}

function JobState({ job, fallback }) {
  return (
    <div className={`export-job${job?.status === 'failed' ? ' is-error' : job?.status === 'completed' ? ' is-success' : ''}`}>
      <span>{job ? jobLabel(job) : fallback}</span>
      {job?.error && <strong>{job.error}</strong>}
    </div>
  )
}
