import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  CircleAlert,
  Clock3,
  Download,
  ImageOff,
  LoaderCircle,
  PanelRightClose,
  PanelRightOpen,
  Pause,
  Play,
  RefreshCw,
  Save,
  Settings2,
  Sparkles,
  Volume2,
  WandSparkles,
} from 'lucide-react'
import { useLocation, useNavigate, useParams } from 'react-router'
import {
  createExport,
  generateTaskWorkspaceAssets,
  getExportJob,
  getExportState,
  getTaskWorkspace,
  getVoices,
  previewVoice,
  regenerateAudio,
  regenerateImage,
  resegmentTaskWorkspace,
  resumeTask,
  updateSegment,
  updateTaskWorkspaceSettings,
} from '../api/task'
import { VoicePicker } from '../components/VoicePicker'
import { toast } from '../lib/toast'
import { mergeTtsOptions, nextPreviewState, normalizeVoiceCatalog } from '../lib/voiceCatalog'
import { normalizeMediaUrl } from '../utils/mediaUrl'
import { ratioOptions, visualStyles } from '../utils/projectDrafts'
import { ratioClassName } from '../utils/taskState'
import { normalizeSubtitleText, secondsToLabel, segmentDuration } from './previewUtils'
import { SettingsPage } from './SettingsPage'
import './workspace-page.css'

const LAST_VOICE_KEY = 'insightcut:last-voice'
const LAST_WORKSPACE_KEY = 'insightcut:last-workspace'

function pendingKey(taskId) {
  return `insightcut:workspace-pending:${taskId}`
}

function readPending(taskId) {
  try {
    const parsed = JSON.parse(localStorage.getItem(pendingKey(taskId)) || '{}')
    return parsed && typeof parsed === 'object' ? parsed : {}
  } catch {
    return {}
  }
}

function writePending(taskId, value) {
  if (Object.keys(value).length) localStorage.setItem(pendingKey(taskId), JSON.stringify(value))
  else localStorage.removeItem(pendingKey(taskId))
}

function stageMeta(workspace) {
  const stage = workspace?.stage
  const error = workspace?.error
  if (stage === 'planning') {
    const ready = workspace?.progress?.prompts_ready || 0
    const total = workspace?.progress?.prompts_total || workspace?.segments_count || 0
    if (workspace?.planning_step === 'image_prompt_generation') {
      return {
        title: `正在生成提示词 ${ready}/${total}`,
        description: '每个分镜独立生成，完成的内容会立即填入工作台',
        tone: 'working',
      }
    }
    if (workspace?.planning_step === 'segmentation') {
      return { title: '正在拆分分镜', description: '完整文案已保存，正在按口播节奏拆分画面', tone: 'working' }
    }
    return { title: '正在扩写完整文案', description: '文案返回后会立即展示，无需等待全部提示词', tone: 'working' }
  }
  const states = {
    awaiting_confirmation: ['预案等待确认', '检查文案、提示词与音色后再生成素材', 'review'],
    generating_assets: ['正在生成图片与配音', '完成的素材会逐段填入左侧预览', 'working'],
    ready: ['素材已就绪', '可以即时预览、继续修改或按需生成高保真视频', 'ready'],
    interrupted: ['生成已暂停', error || '已有内容已保存，可以从检查点继续', 'warning'],
    failed: ['部分流程失败', error || '已有内容仍然保留，可以修正后重试', 'warning'],
  }
  const [title, description, tone] = states[stage] || states.interrupted
  return { title, description, tone }
}

function segmentState(segment) {
  if (!segment) return { label: '等待分镜', tone: 'pending' }
  if (segment.image_status === 'failed' || segment.audio_status === 'failed' || segment.prompt_status === 'failed') {
    return { label: '需要处理', tone: 'error' }
  }
  if (segment.image_status === 'stale' || segment.audio_status === 'stale' || segment.prompt_needs_review) {
    return { label: '待更新', tone: 'warning' }
  }
  if (segment.image_status === 'completed' && segment.audio_status === 'completed') {
    return { label: '素材完成', tone: 'ready' }
  }
  if (segment.prompt_status === 'processing' || segment.image_status === 'processing' || segment.audio_status === 'processing') {
    return { label: '生成中', tone: 'working' }
  }
  return { label: segment.image_prompt ? '等待素材' : '等待提示词', tone: 'pending' }
}

function formatEstimate(estimate) {
  const min = Math.max(1, Math.ceil(Number(estimate?.min_seconds || 0) / 60))
  const max = Math.max(min, Math.ceil(Number(estimate?.max_seconds || 0) / 60))
  return `${min}–${max} 分钟`
}

function parseOptions(value) {
  if (value && typeof value === 'object') return value
  try { return JSON.parse(value || '{}') } catch { return {} }
}

export function WorkspacePage() {
  const { taskId } = useParams()
  const navigate = useNavigate()
  const location = useLocation()
  const isSettingsOverlay = location.pathname.endsWith('/settings')
  const [workspace, setWorkspace] = useState(null)
  const workspaceRef = useRef(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [selectedIndex, setSelectedIndex] = useState(() => Number(localStorage.getItem(`insightcut:selected:${taskId}`) || 0))
  const [settingsOpen, setSettingsOpen] = useState(true)
  const [mobilePane, setMobilePane] = useState('preview')
  const [voices, setVoices] = useState([])
  const [selectedVoice, setSelectedVoice] = useState('')
  const [ttsOptions, setTtsOptions] = useState({ speed_level: 'normal' })
  const [voicePreviewState, setVoicePreviewState] = useState(() => nextPreviewState())
  const voiceAudioRef = useRef(null)
  const previewTokenRef = useRef(0)
  const playbackAudioRef = useRef(null)
  const playbackTimerRef = useRef(null)
  const [playing, setPlaying] = useState(false)
  const [previewMode, setPreviewMode] = useState('content')
  const [exportState, setExportState] = useState(null)
  const [previewJob, setPreviewJob] = useState(null)
  const [busyAction, setBusyAction] = useState('')
  const [savingCount, setSavingCount] = useState(0)
  const [saveMessage, setSaveMessage] = useState('已同步')
  const saveTimersRef = useRef(new Map())
  const saveQueueRef = useRef(Promise.resolve())
  const pendingRef = useRef(readPending(taskId))

  useEffect(() => { workspaceRef.current = workspace }, [workspace])

  const applyPendingEdits = useCallback(data => {
    const pending = pendingRef.current
    if (!Object.keys(pending).length) return data
    return {
      ...data,
      segments: (data.segments || []).map(segment => ({
        ...segment,
        ...(pending[segment.segment_index] || {}),
      })),
    }
  }, [])

  const loadWorkspace = useCallback(async ({ quiet = false } = {}) => {
    if (!quiet) {
      setLoading(true)
      setLoadError('')
    }
    try {
      const data = applyPendingEdits(await getTaskWorkspace(taskId))
      setWorkspace(data)
      workspaceRef.current = data
      const safeIndex = Math.max(0, Math.min(selectedIndex, Math.max((data.segments?.length || 1) - 1, 0)))
      if (safeIndex !== selectedIndex) setSelectedIndex(safeIndex)
      if (!quiet) {
        const rememberedVoice = localStorage.getItem(LAST_VOICE_KEY) || ''
        setSelectedVoice(data.voice_type || rememberedVoice)
        setTtsOptions(mergeTtsOptions({}, data.tts_options || {}, String(data.voice_type || rememberedVoice).startsWith('doubao:') ? 'doubao' : 'mimo'))
        const hasConfirmedVoice = Boolean(data.voice_confirmed && data.voice_type)
        setSettingsOpen(!hasConfirmedVoice)
        if (!hasConfirmedVoice && window.matchMedia?.('(max-width: 780px)').matches) setMobilePane('settings')
      }
      localStorage.setItem(LAST_WORKSPACE_KEY, JSON.stringify({ taskId, name: data.name, path: `/workspace/${taskId}` }))
      window.dispatchEvent(new Event('insightcut:workspace'))
      setLoadError('')
      return data
    } catch (error) {
      if (!quiet) setLoadError(error?.response?.data?.detail || '工作台加载失败')
      return null
    } finally {
      if (!quiet) setLoading(false)
    }
  }, [applyPendingEdits, selectedIndex, taskId])

  useEffect(() => {
    let active = true
    Promise.all([
      loadWorkspace(),
      getVoices({ include_disabled: true }).catch(() => []),
      getExportState(taskId).catch(() => null),
    ]).then(([, voiceList, nextExport]) => {
      if (!active) return
      setVoices(normalizeVoiceCatalog(voiceList))
      setExportState(nextExport)
    })
    return () => { active = false }
  }, [taskId]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!workspace || !['planning', 'generating_assets'].includes(workspace.stage)) return undefined
    const timer = window.setInterval(() => loadWorkspace({ quiet: true }), 1500)
    return () => window.clearInterval(timer)
  }, [loadWorkspace, workspace?.stage])

  useEffect(() => {
    if (!previewJob || !['pending', 'processing'].includes(previewJob.status)) return undefined
    const timer = window.setInterval(async () => {
      try {
        const next = await getExportJob(taskId, previewJob.job_id)
        setPreviewJob(next)
        if (next.status === 'completed') {
          window.clearInterval(timer)
          const state = await getExportState(taskId)
          setExportState(state)
          setPreviewMode('high')
          toast.success('高保真预览已生成')
        } else if (next.status === 'failed') {
          window.clearInterval(timer)
          toast.error(next.error || '高保真预览生成失败')
        }
      } catch {
        window.clearInterval(timer)
      }
    }, 1800)
    return () => window.clearInterval(timer)
  }, [previewJob, taskId])

  useEffect(() => () => {
    saveTimersRef.current.forEach(timer => window.clearTimeout(timer))
    playbackAudioRef.current?.pause()
    voiceAudioRef.current?.pause()
    window.clearTimeout(playbackTimerRef.current)
  }, [])

  const segments = workspace?.segments || []
  const currentSegment = segments[selectedIndex] || null
  const imageUrl = normalizeMediaUrl(currentSegment?.image_url)
  const highFidelityUrl = normalizeMediaUrl(
    exportState?.render?.video_url || exportState?.preview?.manifest?.preview_url || exportState?.outputs?.mp4?.url,
  )
  const activeStyle = visualStyles.find(style => style.value === workspace?.visual_style) || visualStyles[0]
  const stage = stageMeta(workspace)
  const voiceReady = Boolean(workspace?.voice_confirmed && workspace?.voice_type)
  const isPlanning = workspace?.stage === 'planning'
  const editable = !isPlanning && workspace?.stage !== 'generating_assets'
  const staleSegments = useMemo(
    () => segments.filter(segment => segment.image_status === 'stale' || segment.audio_status === 'stale'),
    [segments],
  )

  const selectSegment = index => {
    const safe = Math.max(0, Math.min(Number(index), Math.max(segments.length - 1, 0)))
    setSelectedIndex(safe)
    localStorage.setItem(`insightcut:selected:${taskId}`, String(safe))
  }

  const stopPlayback = useCallback(() => {
    playbackAudioRef.current?.pause()
    playbackAudioRef.current = null
    window.clearTimeout(playbackTimerRef.current)
    setPlaying(false)
  }, [])

  const playFrom = useCallback(index => {
    const segment = (workspaceRef.current?.segments || [])[index]
    if (!segment) return stopPlayback()
    selectSegment(index)
    setPlaying(true)
    const next = () => {
      const all = workspaceRef.current?.segments || []
      if (index + 1 >= all.length) return stopPlayback()
      playFrom(index + 1)
    }
    const audioUrl = normalizeMediaUrl(segment.audio_url)
    if (audioUrl) {
      const audio = new Audio(audioUrl)
      playbackAudioRef.current = audio
      audio.onended = next
      audio.onerror = next
      audio.play().catch(() => {
        toast.warning('浏览器阻止了音频播放，请再次点击播放')
        stopPlayback()
      })
    } else {
      playbackTimerRef.current = window.setTimeout(next, segmentDuration(segment) * 1000)
    }
  }, [stopPlayback, taskId]) // eslint-disable-line react-hooks/exhaustive-deps

  const togglePlayback = () => {
    if (playing) stopPlayback()
    else playFrom(selectedIndex)
  }

  const updateLocalSegment = (segmentIndex, patch) => {
    setWorkspace(current => {
      const next = {
        ...current,
        segments: current.segments.map(segment => segment.segment_index === segmentIndex ? { ...segment, ...patch } : segment),
      }
      workspaceRef.current = next
      return next
    })
    pendingRef.current = {
      ...pendingRef.current,
      [segmentIndex]: { ...(pendingRef.current[segmentIndex] || {}), ...patch },
    }
    writePending(taskId, pendingRef.current)
  }

  const enqueueSave = (segmentIndex, patch) => {
    updateLocalSegment(segmentIndex, patch)
    const timerKey = `${segmentIndex}:${Object.keys(patch).sort().join(',')}`
    window.clearTimeout(saveTimersRef.current.get(timerKey))
    setSaveMessage('等待保存…')
    saveTimersRef.current.set(timerKey, window.setTimeout(() => {
      setSavingCount(count => count + 1)
      setSaveMessage('正在保存…')
      saveQueueRef.current = saveQueueRef.current.catch(() => {}).then(async () => {
        const live = workspaceRef.current
        try {
          const result = await updateSegment(taskId, segmentIndex, {
            ...patch,
            expected_plan_version: live?.plan_version,
          })
          pendingRef.current = { ...pendingRef.current }
          delete pendingRef.current[segmentIndex]
          writePending(taskId, pendingRef.current)
          setWorkspace(current => {
            const next = { ...current, plan_version: result.plan_version, snapshot_key: result.snapshot_key }
            workspaceRef.current = next
            return next
          })
          setSaveMessage('已同步')
        } catch (error) {
          setSaveMessage('保存失败')
          toast.error(error?.response?.data?.detail || '分镜保存失败')
          if (error?.response?.status === 409) await loadWorkspace()
        } finally {
          setSavingCount(count => Math.max(0, count - 1))
        }
      })
    }, 320))
  }

  const stopVoicePreview = useCallback(() => {
    voiceAudioRef.current?.pause()
    voiceAudioRef.current = null
    setVoicePreviewState(current => nextPreviewState(current, { type: 'stop' }))
  }, [])

  const previewSelectedVoice = async voice => {
    if (voicePreviewState.playingVoice === voice.id) return stopVoicePreview()
    stopVoicePreview()
    const token = ++previewTokenRef.current
    setVoicePreviewState(current => nextPreviewState(current, { type: 'start', voiceId: voice.id, token }))
    try {
      const result = await previewVoice({ voice_type: voice.id })
      const audio = new Audio(normalizeMediaUrl(result.url))
      voiceAudioRef.current = audio
      audio.onended = stopVoicePreview
      audio.onerror = () => setVoicePreviewState(current => nextPreviewState(current, { type: 'error', voiceId: voice.id, token, error: '试听播放失败' }))
      setVoicePreviewState(current => nextPreviewState(current, { type: 'ready', voiceId: voice.id, token, url: result.url }))
      await audio.play()
    } catch (error) {
      setVoicePreviewState(current => nextPreviewState(current, { type: 'error', voiceId: voice.id, token, error: error?.response?.data?.detail || '音色试听失败' }))
    }
  }

  const saveWorkspaceSettings = async patch => {
    setBusyAction('settings')
    try {
      const result = await updateTaskWorkspaceSettings(taskId, {
        ...patch,
        expected_plan_version: workspaceRef.current?.plan_version,
      })
      if (patch.voice_type) localStorage.setItem(LAST_VOICE_KEY, patch.voice_type)
      await loadWorkspace({ quiet: true })
      setWorkspace(current => ({ ...current, plan_version: result.plan_version, snapshot_key: result.snapshot_key }))
      return true
    } catch (error) {
      toast.error(error?.response?.data?.detail || '设置保存失败')
      if (error?.response?.status === 409) await loadWorkspace()
      return false
    } finally {
      setBusyAction('')
    }
  }

  const confirmVoice = async () => {
    if (!selectedVoice) return toast.warning('请先选择一个配音音色')
    const saved = await saveWorkspaceSettings({ voice_type: selectedVoice, tts_options: ttsOptions, voice_confirmed: true })
    if (saved) {
      setSettingsOpen(false)
      if (window.matchMedia?.('(max-width: 780px)').matches) setMobilePane('preview')
      toast.success('全片音色已确认')
    }
  }

  const startAssets = async () => {
    if (savingCount || Object.keys(pendingRef.current).length) return toast.info('请等待当前编辑保存完成')
    setBusyAction('generate')
    try {
      await generateTaskWorkspaceAssets(taskId, { snapshot_key: workspace.snapshot_key })
      toast.success('已开始生成图片与配音')
      await loadWorkspace({ quiet: true })
    } catch (error) {
      toast.error(error?.response?.data?.detail || '素材生成启动失败')
      if (error?.response?.status === 409) await loadWorkspace()
    } finally {
      setBusyAction('')
    }
  }

  const updateStaleAssets = async () => {
    setBusyAction('stale')
    try {
      for (const segment of staleSegments) {
        if (segment.audio_status === 'stale') {
          await regenerateAudio(taskId, segment.segment_index, {
            voice_type: segment.audio_voice_type || workspace.voice_type,
            tts_options: parseOptions(segment.audio_tts_options_json) || workspace.tts_options,
          })
        }
        if (segment.image_status === 'stale') await regenerateImage(taskId, segment.segment_index)
      }
      toast.success('受影响素材已更新')
      await loadWorkspace({ quiet: true })
    } catch (error) {
      toast.error(error?.response?.data?.detail || '更新素材时发生中断，已完成内容仍会保留')
      await loadWorkspace({ quiet: true })
    } finally {
      setBusyAction('')
    }
  }

  const regenerateOne = async (segment, target) => {
    setBusyAction(`${target}:${segment.segment_index}`)
    try {
      if (target === 'image') await regenerateImage(taskId, segment.segment_index)
      else await regenerateAudio(taskId, segment.segment_index, {
        voice_type: segment.audio_voice_type || workspace.voice_type,
        tts_options: parseOptions(segment.audio_tts_options_json) || workspace.tts_options,
      })
      await loadWorkspace({ quiet: true })
      toast.success(target === 'image' ? '图片已更新' : '配音已更新')
    } catch (error) {
      toast.error(error?.response?.data?.detail || '单段素材更新失败')
    } finally {
      setBusyAction('')
    }
  }

  const resegment = async () => {
    if (!window.confirm('重新拆分会重建分镜结构和自动提示词，已经生成的素材仍会保留在项目资产中。继续吗？')) return
    setBusyAction('resegment')
    try {
      await resegmentTaskWorkspace(taskId, {
        script_text: workspace.script_text,
        expected_plan_version: workspace.plan_version,
      })
      toast.success('已开始重新拆分分镜')
      await loadWorkspace({ quiet: true })
    } catch (error) {
      toast.error(error?.response?.data?.detail || '重新拆分失败')
    } finally {
      setBusyAction('')
    }
  }

  const createHighPreview = async () => {
    setBusyAction('preview')
    try {
      const job = await createExport(taskId, { target: 'mp4', use_preview: true, auto_download: false })
      setPreviewJob(job)
      if (job.status === 'completed') {
        setExportState(await getExportState(taskId))
        setPreviewMode('high')
      } else toast.success('已开始生成高保真预览')
    } catch (error) {
      toast.error(error?.response?.data?.detail || '高保真预览生成失败')
    } finally {
      setBusyAction('')
    }
  }

  const resumeGeneration = async () => {
    setBusyAction('resume')
    try {
      await resumeTask(taskId)
      toast.success('已从检查点继续生成')
      await loadWorkspace({ quiet: true })
    } catch (error) {
      toast.error(error?.response?.data?.detail || '当前任务暂时无法继续')
    } finally {
      setBusyAction('')
    }
  }

  if (loading) return <main className="workspace-loading"><div className="workspace-loading-card"><span className="workspace-orbit" /><strong>正在恢复生产工作台</strong><p>分镜、提示词和已有素材正在从本地任务中载入。</p></div></main>
  if (loadError || !workspace) return <main className="workspace-loading"><div className="workspace-error-card"><CircleAlert size={24} /><strong>工作台暂时无法打开</strong><p>{loadError}</p><button type="button" className="button button-primary" onClick={() => loadWorkspace()}>重新加载</button></div></main>

  const closeSettingsPanel = () => {
    if (window.matchMedia?.('(max-width: 780px)').matches) setMobilePane('storyboard')
    else setSettingsOpen(false)
  }

  return <main className={`production-workspace${settingsOpen ? ' is-settings-open' : ''}`} data-mobile-pane={mobilePane}>
    <nav className="workspace-mobile-tabs" aria-label="工作台分区">
      <button type="button" className={mobilePane === 'storyboard' ? 'is-active' : ''} onClick={() => setMobilePane('storyboard')}>分镜</button>
      <button type="button" className={mobilePane === 'preview' ? 'is-active' : ''} onClick={() => setMobilePane('preview')}>预览</button>
      <button type="button" className={mobilePane === 'settings' ? 'is-active' : ''} onClick={() => { setSettingsOpen(true); setMobilePane('settings') }}>设置</button>
    </nav>
    <div className="workspace-grid">
      <aside className="workspace-preview" aria-label="当前分镜预览">
        <header className="workspace-preview-heading">
          <div><span>内容预览</span><strong>{selectedIndex + 1} / {segments.length || 0}</strong></div>
          <span className={`workspace-stage-dot is-${stage.tone}`}>{stage.title}</span>
        </header>

        <section className={`workspace-canvas ${ratioClassName(workspace.ratio)}`}>
          {previewMode === 'high' && highFidelityUrl
            ? <video controls preload="metadata" src={highFidelityUrl} aria-label="高保真视频预览" />
            : imageUrl
              ? <img src={imageUrl} alt={`分镜 ${selectedIndex + 1} 画面`} />
              : <div className="workspace-image-pending" style={{ backgroundImage: `url(${activeStyle?.image || ''})` }}>
                  <span className="workspace-image-glow" />
                  <ImageOff size={24} />
                  <strong>{currentSegment?.image_prompt ? '画面等待生成' : '正在准备画面描述'}</strong>
                  <small>{workspace.visual_style} · {workspace.ratio}</small>
                </div>}
          {previewMode === 'content' ? <p className="workspace-subtitle">{normalizeSubtitleText(currentSegment?.text || '分镜文案生成后会显示在这里')}</p> : null}
        </section>

        <div className="workspace-player-controls">
          <button type="button" className="workspace-icon-button" onClick={() => selectSegment(selectedIndex - 1)} disabled={selectedIndex <= 0} aria-label="上一段"><ChevronLeft size={17} /></button>
          <button type="button" className="workspace-play-button" onClick={togglePlayback} disabled={!segments.length} aria-label={playing ? '暂停即时预览' : '播放即时预览'}>{playing ? <Pause size={18} /> : <Play size={18} />}</button>
          <button type="button" className="workspace-icon-button" onClick={() => selectSegment(selectedIndex + 1)} disabled={selectedIndex >= segments.length - 1} aria-label="下一段"><ChevronRight size={17} /></button>
          <div><strong>{secondsToLabel(segments.slice(0, selectedIndex).reduce((sum, segment) => sum + segmentDuration(segment), 0))}</strong><span>/ {secondsToLabel(workspace.estimated_duration)}</span></div>
        </div>

        <div className="workspace-preview-tabs">
          <button type="button" className={previewMode === 'content' ? 'is-active' : ''} onClick={() => setPreviewMode('content')}>即时预览</button>
          <button type="button" className={previewMode === 'high' ? 'is-active' : ''} disabled={!highFidelityUrl} onClick={() => setPreviewMode('high')}>高保真</button>
        </div>

        <dl className="workspace-metrics">
          <div><dt>实际分镜</dt><dd>{workspace.segments_count} 段</dd></div>
          <div><dt>{workspace.duration_is_estimate ? '预计时长' : '真实时长'}</dt><dd>{secondsToLabel(workspace.estimated_duration)}</dd></div>
          <div><dt>素材耗时</dt><dd>{formatEstimate(workspace.generation_estimate)}</dd></div>
        </dl>

        <section className={`workspace-stage-note is-${stage.tone}`}>
          {stage.tone === 'warning' ? <AlertTriangle size={17} /> : stage.tone === 'working' ? <LoaderCircle className="spin" size={17} /> : <Sparkles size={17} />}
          <div><strong>{stage.title}</strong><p>{stage.description}</p></div>
        </section>

        <details className={`workspace-center-script${workspace.script_text ? '' : ' is-loading'}`} open>
          <summary><span><strong>完整文案</strong><small>{workspace.input_mode === 'theme' ? '主题扩写结果' : '严格保留用户原文'}</small></span><span>{workspace.script_text ? `${workspace.script_text.replace(/\s/g, '').length} 字` : '生成中'}</span></summary>
          {workspace.script_text ? <p>{workspace.script_text}</p> : <div className="workspace-script-skeleton"><i /><i /><i /><i /></div>}
        </details>

        <section className="workspace-preview-table-panel">
          <header><div><strong>分镜总表</strong><span>{workspace.progress.prompts_ready}/{workspace.progress.prompts_total || workspace.segments_count} 提示词完成{workspace.progress.prompts_failed ? ` · ${workspace.progress.prompts_failed} 段失败` : ''}</span></div><button type="button" onClick={resegment} disabled={!editable || busyAction === 'resegment'}><RefreshCw size={13} />重新拆分</button></header>
          <div className="workspace-preview-table">
            <div className="workspace-preview-row is-head"><span>#</span><span>文案</span><span>时长</span><span>提示词</span><span>图片</span><span>配音</span></div>
            {!segments.length ? Array.from({ length: 4 }, (_, index) => <div className="workspace-preview-row is-skeleton" key={index}><i /><i /><i /><i /><i /><i /></div>) : segments.map((segment, index) => <button type="button" key={segment.id || segment.segment_index} className={`workspace-preview-row${index === selectedIndex ? ' is-selected' : ''}`} onClick={() => selectSegment(index)}>
              <strong>{String(index + 1).padStart(2, '0')}</strong>
              <span>{segment.text || '等待文案'}</span>
              <span><Clock3 size={12} />{secondsToLabel(segmentDuration(segment))}</span>
              <span className={`is-${segment.prompt_status}`}>{assetStatusLabel(segment.prompt_status)}</span>
              <span className={`is-${segment.image_status}`}>{assetStatusLabel(segment.image_status)}</span>
              <span className={`is-${segment.audio_status}`}>{assetStatusLabel(segment.audio_status)}</span>
            </button>)}
          </div>
        </section>
      </aside>

      <section className="workspace-content" aria-label="分镜导航">
        <header className="workspace-content-header">
          <div className="workspace-rail-cover">{imageUrl ? <img src={imageUrl} alt="当前分镜缩略图" /> : <div style={{ backgroundImage: `url(${activeStyle?.image || ''})` }}><span /><ImageOff size={17} /></div>}<strong>{segments.length ? `片段 ${selectedIndex + 1}` : '等待分镜'}</strong></div>
          <div className="workspace-title-row">
            <div><span>生产预案</span><h1>{workspace.name}</h1></div>
            <div className="workspace-summary-chips"><span>{workspace.visual_style}</span><span>{workspace.ratio}</span><span>{workspace.text_style}</span></div>
          </div>
          <div className="workspace-sync-row">
            <span className={`workspace-status-pill is-${stage.tone}`}>{stage.title}</span>
            <span><Save size={14} />{saveMessage}</span>
            <button type="button" onClick={resegment} disabled={!editable || busyAction === 'resegment'}><RefreshCw size={14} />重新拆分</button>
          </div>
        </header>

        <details className="workspace-script" open>
          <summary><span><strong>完整文案</strong><small>{workspace.input_mode === 'theme' ? '主题扩写结果' : '严格保留用户原文'}</small></span><span>{workspace.script_text.replace(/\s/g, '').length} 字</span></summary>
          <p>{workspace.script_text || '完整文案生成后会显示在这里。'}</p>
        </details>

        <div className="workspace-section-heading">
          <div><strong>全分镜流</strong><span>点击卡片同步左侧画面；普通编辑不会改变分镜数量。</span></div>
          <span>{workspace.progress.prompts_ready}/{workspace.segments_count} 提示词完成</span>
        </div>

        <div className="workspace-segment-stream">
          {!segments.length ? Array.from({ length: 4 }, (_, index) => <SegmentSkeleton key={index} index={index} />) : segments.map((segment, index) => {
            const state = segmentState(segment)
            const segmentVoice = segment.audio_voice_type || ''
            return <article key={segment.id || segment.segment_index} className={`workspace-segment-card${index === selectedIndex ? ' is-selected' : ''}`} onClick={() => selectSegment(index)} style={{ '--segment-order': index }}>
              <header>
                <span className="workspace-segment-number">{String(index + 1).padStart(2, '0')}</span>
                <div><strong>分镜 {index + 1}</strong><span><Clock3 size={13} />{segment.duration ? '真实' : '预计'} {secondsToLabel(segmentDuration(segment))}</span></div>
                <span className={`workspace-segment-state is-${state.tone}`}>{state.label}</span>
              </header>
              <p className="workspace-segment-summary">{segment.text || '等待文案'}</p>
              <div className="workspace-segment-fields">
                <label><span>配音文案</span><textarea value={segment.text} readOnly={!editable} onClick={event => event.stopPropagation()} onChange={event => enqueueSave(segment.segment_index, { text: event.target.value })} /></label>
                <label className={segment.prompt_status !== 'completed' ? 'is-loading' : ''}><span>生图提示词 {segment.prompt_manual ? <em>手工编辑</em> : null}</span>{segment.prompt_status === 'completed'
                  ? <textarea value={segment.image_prompt} readOnly={!editable} onClick={event => event.stopPropagation()} onChange={event => enqueueSave(segment.segment_index, { image_prompt: event.target.value })} />
                  : <div className="workspace-prompt-skeleton"><i /><i /><i /></div>}</label>
              </div>
              {segment.prompt_needs_review ? <p className="workspace-inline-warning"><AlertTriangle size={14} />文案已变化，请检查提示词是否仍然匹配。</p> : null}
              {segment.prompt_error || segment.image_error || segment.audio_error ? <p className="workspace-inline-error"><CircleAlert size={14} />{segment.prompt_error || segment.image_error || segment.audio_error}</p> : null}
              <footer>
                <div className="workspace-asset-states"><span className={`is-${segment.image_status}`}>图片 · {assetStatusLabel(segment.image_status)}</span><span className={`is-${segment.audio_status}`}>配音 · {assetStatusLabel(segment.audio_status)}</span></div>
                <div className="workspace-card-actions" onClick={event => event.stopPropagation()}>
                  <label><span className="sr-only">分镜音色</span><select value={segmentVoice} disabled={!editable} onChange={event => enqueueSave(segment.segment_index, { audio_voice_type: event.target.value })}><option value="">跟随全片音色</option>{voices.filter(voice => voice.selectable && voice.id !== workspace.voice_type).map(voice => <option key={voice.id} value={voice.id}>{voice.name}</option>)}</select></label>
                  <button type="button" disabled={!editable || busyAction === `image:${segment.segment_index}`} onClick={() => regenerateOne(segment, 'image')}><WandSparkles size={14} />更新图片</button>
                  <button type="button" disabled={!editable || busyAction === `audio:${segment.segment_index}`} onClick={() => regenerateOne(segment, 'audio')}><Volume2 size={14} />更新配音</button>
                </div>
              </footer>
            </article>
          })}
        </div>
      </section>

      <aside className={`workspace-settings${settingsOpen ? ' is-open' : ''}`} aria-label="生产设置">
        <nav className="workspace-inspector-tabs" aria-label="右侧编辑区"><button type="button" className={!settingsOpen ? 'is-active' : ''} onClick={() => setSettingsOpen(false)}>当前分镜</button><button type="button" className={settingsOpen ? 'is-active' : ''} onClick={() => setSettingsOpen(true)}>全片设置{!voiceReady ? <i /> : null}</button></nav>
        <button type="button" className="workspace-settings-toggle" onClick={() => setSettingsOpen(open => !open)} aria-label={settingsOpen ? '收起设置' : '展开设置'}>{settingsOpen ? <PanelRightClose size={19} /> : <PanelRightOpen size={19} />}</button>
        {!settingsOpen ? <div className="workspace-segment-inspector">
          <header className="workspace-inspector-heading"><div><span>片段设置</span><h2>{currentSegment ? `分镜 ${selectedIndex + 1}` : '等待分镜'}</h2></div><div><button type="button" onClick={() => selectSegment(selectedIndex - 1)} disabled={selectedIndex <= 0} aria-label="上一段"><ChevronLeft size={16} /></button><button type="button" onClick={() => selectSegment(selectedIndex + 1)} disabled={selectedIndex >= segments.length - 1} aria-label="下一段"><ChevronRight size={16} /></button></div></header>
          {currentSegment ? <>
            <div className="workspace-inspector-status"><span className={`workspace-segment-state is-${segmentState(currentSegment).tone}`}>{segmentState(currentSegment).label}</span><span>{currentSegment.duration ? '真实' : '预计'} {secondsToLabel(segmentDuration(currentSegment))}</span></div>
            <label className="workspace-inspector-field"><span>配音文案</span><textarea value={currentSegment.text} readOnly={!editable} onChange={event => enqueueSave(currentSegment.segment_index, { text: event.target.value })} /></label>
            <label className="workspace-inspector-field"><span>生图提示词 {currentSegment.prompt_manual ? <em>手工编辑</em> : null}</span>{currentSegment.prompt_status === 'completed' ? <textarea value={currentSegment.image_prompt} readOnly={!editable} onChange={event => enqueueSave(currentSegment.segment_index, { image_prompt: event.target.value })} /> : <div className="workspace-prompt-skeleton"><i /><i /><i /></div>}</label>
            {currentSegment.prompt_needs_review ? <p className="workspace-inline-warning"><AlertTriangle size={14} />文案已变化，请检查提示词。</p> : null}
            {currentSegment.prompt_error || currentSegment.image_error || currentSegment.audio_error ? <p className="workspace-inline-error"><CircleAlert size={14} />{currentSegment.prompt_error || currentSegment.image_error || currentSegment.audio_error}</p> : null}
            <section className="workspace-inspector-section"><div className="workspace-setting-heading"><strong>分镜音色</strong><span>留空时跟随全片音色</span></div><select value={currentSegment.audio_voice_type || ''} disabled={!editable} onChange={event => enqueueSave(currentSegment.segment_index, { audio_voice_type: event.target.value })}><option value="">跟随全片 · {voiceName(voices, workspace.voice_type)}</option>{voices.filter(voice => voice.selectable && voice.id !== workspace.voice_type).map(voice => <option key={voice.id} value={voice.id}>{voice.name}</option>)}</select></section>
            <div className="workspace-asset-states"><span className={`is-${currentSegment.image_status}`}>图片 · {assetStatusLabel(currentSegment.image_status)}</span><span className={`is-${currentSegment.audio_status}`}>配音 · {assetStatusLabel(currentSegment.audio_status)}</span></div>
            <div className="workspace-inspector-actions"><button type="button" disabled={!editable || busyAction === `image:${currentSegment.segment_index}`} onClick={() => regenerateOne(currentSegment, 'image')}><WandSparkles size={14} />更新图片</button><button type="button" disabled={!editable || busyAction === `audio:${currentSegment.segment_index}`} onClick={() => regenerateOne(currentSegment, 'audio')}><Volume2 size={14} />更新配音</button></div>
          </> : <div className="workspace-inspector-skeleton"><i /><i /><i /><i /><i /></div>}
        </div> : <div className="workspace-settings-panel">
          <header><div><span>全片设置</span><h2>画面与配音</h2></div><button type="button" aria-label="收起设置" onClick={closeSettingsPanel}><PanelRightClose size={18} /></button></header>
          <section className="workspace-setting-section"><div className="workspace-setting-heading"><strong>配音音色</strong><span>选择一次作用全片，分镜可单独覆盖</span></div><VoicePicker voices={voices} value={selectedVoice} ttsOptions={ttsOptions} onChange={(id) => { setSelectedVoice(id); setTtsOptions(mergeTtsOptions({}, workspace.tts_options || {}, id.startsWith('doubao:') ? 'doubao' : 'mimo')) }} onOptionsChange={setTtsOptions} onPreview={previewSelectedVoice} playingVoice={voicePreviewState.playingVoice} previewLoading={voicePreviewState.loading} previewError={voicePreviewState.error} compact /></section>
          <button type="button" className="button button-primary workspace-confirm-voice" disabled={!selectedVoice || busyAction === 'settings'} onClick={confirmVoice}>{busyAction === 'settings' ? '正在保存…' : voiceReady ? '更新全片音色' : '确认全片音色'}</button>
          <section className="workspace-setting-section"><div className="workspace-setting-heading"><strong>画面风格</strong><span>修改后自动重算系统提示词</span></div><div className="workspace-style-grid">{visualStyles.map(style => <button type="button" key={style.value} className={workspace.visual_style === style.value ? 'is-selected' : ''} onClick={() => saveWorkspaceSettings({ visual_style: style.value, voice_confirmed: voiceReady })}><img src={style.image} alt="" /><span>{style.label}</span></button>)}</div></section>
          <section className="workspace-setting-section"><div className="workspace-setting-heading"><strong>视频比例</strong><span>已有图片会标记为待更新</span></div><div className="workspace-ratio-control">{ratioOptions.map(ratio => <button type="button" key={ratio} className={workspace.ratio === ratio ? 'is-selected' : ''} onClick={() => saveWorkspaceSettings({ ratio, voice_confirmed: voiceReady })}>{ratio}</button>)}</div></section>
          <button type="button" className="button button-secondary workspace-api-button" onClick={() => navigate(`/workspace/${taskId}/settings`)}><Settings2 size={16} />打开 API 配置</button>
        </div>}
      </aside>
    </div>

    <footer className="workspace-actionbar">
      <div><strong>{stage.title}</strong><span>{voiceReady ? `全片音色：${voiceName(voices, workspace.voice_type)}` : '生成前需要确认全片音色'}</span></div>
      <div>
        {['interrupted', 'failed'].includes(workspace.stage) ? <button type="button" className="button button-secondary" disabled={busyAction === 'resume'} onClick={resumeGeneration}><RefreshCw size={16} />从检查点继续</button> : null}
        {staleSegments.length ? <button type="button" className="button button-secondary" disabled={busyAction === 'stale'} onClick={updateStaleAssets}><RefreshCw size={16} />更新 {staleSegments.length} 段受影响素材</button> : null}
        {workspace.stage === 'awaiting_confirmation' ? <button type="button" className="button button-primary" disabled={!voiceReady || savingCount > 0 || busyAction === 'generate'} onClick={startAssets}>{busyAction === 'generate' ? <LoaderCircle className="spin" size={16} /> : <Sparkles size={16} />}确认预案并生成图片与配音</button> : null}
        {workspace.stage === 'ready' ? <button type="button" className="button button-secondary" disabled={busyAction === 'preview' || previewJob?.status === 'processing'} onClick={createHighPreview}><Play size={16} />{exportState?.preview?.valid ? '重新生成高保真预览' : '生成高保真预览'}</button> : null}
        <button type="button" className="button button-primary" disabled={!segments.length} onClick={() => navigate(`/export/${taskId}`)}><Download size={16} />进入导出中心</button>
      </div>
    </footer>

    {isSettingsOverlay ? <div className="workspace-settings-overlay" role="dialog" aria-modal="true" aria-label="API 配置"><SettingsPage embedded onClose={() => navigate(`/workspace/${taskId}`)} /></div> : null}
  </main>
}

function SegmentSkeleton({ index }) {
  return <article className="workspace-segment-card is-skeleton" style={{ '--segment-order': index }}><header><span className="workspace-segment-number">{String(index + 1).padStart(2, '0')}</span><div><i /><i /></div></header><div className="workspace-segment-fields"><div className="workspace-prompt-skeleton"><i /><i /><i /></div><div className="workspace-prompt-skeleton"><i /><i /><i /></div></div></article>
}

function assetStatusLabel(status) {
  return ({ completed: '完成', stale: '待更新', failed: '失败', processing: '生成中', pending: '等待' })[status] || '等待'
}

function voiceName(voices, id) {
  return voices.find(voice => voice.id === id)?.name || '尚未确认'
}
