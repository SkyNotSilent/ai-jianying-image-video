import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  ChevronLeft,
  ChevronRight,
  CircleAlert,
  Clock3,
  FileImage,
  FolderKanban,
  ImageOff,
  LoaderCircle,
  Pause,
  Play,
  RefreshCw,
  Save,
  Sparkles,
  Upload,
  Volume2,
} from 'lucide-react'
import { Link, useNavigate, useParams } from 'react-router'
import {
  createExport,
  getExportState,
  getExportJob,
  getSegments,
  getTaskAssets,
  getTaskStatus,
  getVoices,
  previewVoice,
  regenerateAudio,
  regenerateImage,
  selectSegmentImage,
  updateSegment,
  uploadImage,
} from '../api/task'
import { EmptyState, LoadingState } from '../components/StatusStates'
import { VoicePicker } from '../components/VoicePicker'
import { toast } from '../lib/toast'
import { mergeTtsOptions, nextPreviewState, normalizeVoiceCatalog } from '../lib/voiceCatalog'
import { normalizeMediaUrl } from '../utils/mediaUrl'
import { deriveTaskState, ratioClassName, ratioLabel } from '../utils/taskState'
import {
  appendPromptGuidance,
  createTaskRequestGuard,
  getSegmentDraftSnapshot,
  getSegmentAssetState,
  isTaskLoadPending,
  nextPlaybackIndex,
  normalizeSubtitleText,
  secondsToLabel,
  segmentDuration,
  sortSegmentsByIndex,
  subtitleFontSize,
} from './previewUtils'
import './preview-page.css'

function segmentIndex(segment, fallback) {
  return segment?.segment_index ?? fallback
}

function taskName(task, taskId) {
  return task?.result?.theme || task?.name || `任务 ${String(taskId).slice(0, 8)}`
}

function parseTtsOptions(value) {
  if (value && typeof value === 'object') return value
  if (!value) return {}
  try {
    const parsed = JSON.parse(value)
    return parsed && typeof parsed === 'object' ? parsed : {}
  } catch {
    return {}
  }
}

export function PreviewPage() {
  const { taskId } = useParams()
  const navigate = useNavigate()
  const uploadRef = useRef(null)
  const audioRef = useRef(null)
  const previewTimerRef = useRef(null)
  const voicePreviewAudioRef = useRef(null)
  const voicePreviewTokenRef = useRef(0)
  const loadRequestRef = useRef(0)
  const taskRequestGuardRef = useRef(createTaskRequestGuard(taskId))
  taskRequestGuardRef.current.changeTask(taskId)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [task, setTask] = useState(null)
  const [exportState, setExportState] = useState(null)
  const [segments, setSegments] = useState([])
  const [assets, setAssets] = useState([])
  const [voices, setVoices] = useState([])
  const [selectedIndex, setSelectedIndex] = useState(0)
  const [textDraft, setTextDraft] = useState('')
  const [imagePromptDraft, setImagePromptDraft] = useState('')
  const [selectedVoiceType, setSelectedVoiceType] = useState('')
  const [segmentTtsOptions, setSegmentTtsOptions] = useState({ speed_level: 'normal' })
  const [voicePreviewState, setVoicePreviewState] = useState(() => nextPreviewState())
  const [imageSize, setImageSize] = useState(null)
  const [playing, setPlaying] = useState(false)
  const [busyAction, setBusyAction] = useState('')
  const [previewJob, setPreviewJob] = useState(null)
  const [previewMode, setPreviewMode] = useState('content')
  const [loadedTaskId, setLoadedTaskId] = useState(null)

  const orderedSegments = useMemo(() => sortSegmentsByIndex(segments), [segments])
  const currentSegment = orderedSegments[selectedIndex] || null
  const currentSegmentIdentity = `${taskId}:${currentSegment?.id ?? ''}:${currentSegment?.segment_index ?? ''}`
  const currentDraft = useMemo(
    () => getSegmentDraftSnapshot(taskId, currentSegment),
    [currentSegment?.id, currentSegment?.image_prompt, currentSegment?.segment_index, currentSegment?.text, taskId],
  )
  const state = useMemo(
    () => deriveTaskState({ task, segments: orderedSegments, exportState }),
    [exportState, orderedSegments, task],
  )
  const ratio = exportState?.ratio || task?.ratio || task?.result?.ratio || '16:9'
  const imageUrl = normalizeMediaUrl(currentSegment?.image_url)
  const audioUrl = normalizeMediaUrl(currentSegment?.audio_url)
  const highFidelityUrl = normalizeMediaUrl(exportState?.render?.video_url || exportState?.preview?.manifest?.preview_url || exportState?.outputs?.mp4?.url)
  const renderingPreview = ['pending', 'processing'].includes(previewJob?.status)
  const subtitle = normalizeSubtitleText(currentSegment?.text || '暂无字幕文案')
  const totalSeconds = useMemo(
    () => orderedSegments.reduce((total, segment) => total + segmentDuration(segment), 0),
    [orderedSegments],
  )
  const currentSeconds = useMemo(
    () => orderedSegments.slice(0, selectedIndex).reduce((total, segment) => total + segmentDuration(segment), 0),
    [orderedSegments, selectedIndex],
  )
  const imageAssets = useMemo(
    () => assets.filter(asset => asset.asset_type === 'image' && Number(asset.segment_index) === Number(currentSegment?.segment_index)),
    [assets, currentSegment?.segment_index],
  )

  const beginTaskRequest = () => taskRequestGuardRef.current.begin(taskId)
  const acceptsTaskRequest = requestToken => taskRequestGuardRef.current.accepts(requestToken)

  const reloadAssets = useCallback(async requestToken => {
    const token = requestToken || taskRequestGuardRef.current.begin(taskId)
    try {
      const nextAssets = await getTaskAssets(taskId)
      if (!taskRequestGuardRef.current.accepts(token)) return false
      setAssets(Array.isArray(nextAssets) ? nextAssets : [])
      return true
    } catch {
      if (!taskRequestGuardRef.current.accepts(token)) return false
      setAssets([])
      return true
    }
  }, [taskId])

  const loadPage = useCallback(async () => {
    const requestId = ++loadRequestRef.current
    setLoading(true)
    setLoadError('')
    setLoadedTaskId(null)
    try {
      const [taskData, segmentData, exportData, voiceData, assetData] = await Promise.all([
        getTaskStatus(taskId),
        getSegments(taskId),
        getExportState(taskId).catch(() => null),
        getVoices().catch(() => []),
        getTaskAssets(taskId).catch(() => []),
      ])
      if (requestId !== loadRequestRef.current) return
      setTask(taskData || null)
      setSegments(sortSegmentsByIndex(segmentData))
      setExportState(exportData)
      setPreviewJob((exportData?.jobs || []).find(job => job.target === 'mp4' && ['pending', 'processing'].includes(job.status)) || null)
      setVoices(normalizeVoiceCatalog(voiceData))
      setAssets(Array.isArray(assetData) ? assetData : [])
      setLoadedTaskId(taskId)
    } catch (error) {
      if (requestId !== loadRequestRef.current) return
      console.error('加载预览页失败', error)
      setLoadError('未能读取任务分镜。请确认后端服务在线后重试。')
      toast.error('加载预览页失败')
    } finally {
      if (requestId === loadRequestRef.current) setLoading(false)
    }
  }, [taskId])

  useEffect(() => { loadPage() }, [loadPage])

  useEffect(() => {
    audioRef.current?.pause()
    setSelectedIndex(0)
    setPlaying(false)
    setBusyAction('')
    setPreviewJob(null)
    setPreviewMode('content')
    setTextDraft('')
    setImagePromptDraft('')
    setSelectedVoiceType('')
    setSegmentTtsOptions({ speed_level: 'normal' })
    setImageSize(null)
  }, [taskId])

  useEffect(() => {
    if (selectedIndex >= orderedSegments.length) setSelectedIndex(Math.max(orderedSegments.length - 1, 0))
  }, [orderedSegments.length, selectedIndex])

  useEffect(() => {
    setTextDraft(currentDraft.text)
    setImagePromptDraft(currentDraft.imagePrompt)
  }, [currentDraft])

  useEffect(() => {
    const voice = currentSegment?.audio_voice_type || task?.voice_type || ''
    const provider = voice.startsWith('doubao:') ? 'doubao' : 'mimo'
    const inherited = parseTtsOptions(currentSegment?.audio_tts_options_json)
    const taskOptions = task?.tts_options || {}
    setSelectedVoiceType(voice)
    setSegmentTtsOptions(mergeTtsOptions(taskOptions, inherited, provider))
  }, [currentSegment?.audio_tts_options_json, currentSegment?.audio_voice_type, currentSegmentIdentity, task?.tts_options, task?.voice_type])

  const stopVoicePreview = useCallback(() => {
    voicePreviewAudioRef.current?.pause()
    voicePreviewAudioRef.current = null
    setVoicePreviewState(current => nextPreviewState(current, { type: 'stop' }))
  }, [])

  useEffect(() => () => stopVoicePreview(), [stopVoicePreview])

  useEffect(() => {
    setImageSize(null)
    if (!imageUrl) return undefined
    let active = true
    const image = new Image()
    image.onload = () => { if (active) setImageSize({ width: image.naturalWidth, height: image.naturalHeight }) }
    image.onerror = () => { if (active) setImageSize({ width: 0, height: 0 }) }
    image.src = imageUrl
    return () => { active = false }
  }, [imageUrl])

  useEffect(() => {
    if (exportState?.preview?.valid) return
    setPreviewMode('content')
  }, [exportState?.preview?.valid])

  useEffect(() => {
    if (!previewJob || !['pending', 'processing'].includes(previewJob.status)) return undefined
    let cancelled = false
    let polling = false
    const poll = async () => {
      if (polling) return
      polling = true
      try {
        const nextJob = await getExportJob(taskId, previewJob.job_id)
        if (cancelled) return
        if (nextJob.status === 'completed') {
          const nextState = await getExportState(taskId)
          if (cancelled) return
          setPreviewJob(nextJob)
          setExportState(nextState)
          setPreviewMode('high')
          toast.success('完整视频预览已生成，可直接下载同一份 MP4')
        } else if (nextJob.status === 'failed') {
          setPreviewJob(nextJob)
          toast.error(nextJob.error || '完整视频预览生成失败')
        } else {
          setPreviewJob(nextJob)
        }
      } catch (error) {
        if (!cancelled) console.error('轮询完整视频预览失败', error)
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
  }, [previewJob?.job_id, previewJob?.status, taskId])

  useEffect(() => {
    const audio = audioRef.current
    window.clearTimeout(previewTimerRef.current)
    if (!audio) return
    if (!playing) {
      audio.pause()
      return
    }
    if (!audioUrl) {
      previewTimerRef.current = window.setTimeout(() => {
        const nextIndex = nextPlaybackIndex(selectedIndex, orderedSegments.length)
        if (nextIndex === null) setPlaying(false)
        else setSelectedIndex(nextIndex)
      }, segmentDuration(currentSegment) * 1000)
      return () => window.clearTimeout(previewTimerRef.current)
    }
    audio.currentTime = 0
    audio.play().catch(error => {
      console.error('播放片段配音失败', error)
      setPlaying(false)
      toast.error('配音加载失败，请稍后重试')
    })
    return () => window.clearTimeout(previewTimerRef.current)
  }, [audioUrl, currentSegmentIdentity, orderedSegments.length, playing, selectedIndex])

  const togglePlayback = async () => {
    const audio = audioRef.current
    if (playing) {
      audio?.pause()
      setPlaying(false)
      return
    }
    if (!audioUrl || !audio) {
      setPlaying(true)
      return
    }
    try {
      await audio.play()
      setPlaying(true)
    } catch (error) {
      console.error('播放片段配音失败', error)
      setPlaying(false)
      toast.error('配音加载失败，请稍后重试')
    }
  }

  const handleAudioEnded = () => {
    const nextIndex = nextPlaybackIndex(selectedIndex, orderedSegments.length)
    if (nextIndex === null) {
      setPlaying(false)
      return
    }
    setSelectedIndex(nextIndex)
  }

  const selectSegment = index => {
    setPlaying(false)
    setSelectedIndex(Math.max(0, Math.min(Number(index) || 0, orderedSegments.length - 1)))
  }

  const patchCurrentSegment = patch => {
    if (!currentSegment) return
    const index = segmentIndex(currentSegment, selectedIndex)
    setSegments(current => current.map(segment => (
      Number(segmentIndex(segment, 0)) === Number(index) ? { ...segment, ...patch } : segment
    )))
    setExportState(current => current ? {
      ...current,
      preview: { ...current.preview, valid: false, exists: true, reason: 'stale', status: 'stale' },
      render: { ...current.render, status: 'stale' },
      outputs: { ...current.outputs, mp4: { ...current.outputs?.mp4, available: false, stale: true } },
    } : current)
  }

  const saveCurrentSegment = async ({ quiet = false, requestToken = beginTaskRequest() } = {}) => {
    if (!currentSegment) return false
    await updateSegment(taskId, segmentIndex(currentSegment, selectedIndex), {
      text: textDraft,
      image_prompt: imagePromptDraft,
    })
    if (!acceptsTaskRequest(requestToken)) return false
    patchCurrentSegment({ text: textDraft, image_prompt: imagePromptDraft })
    if (!quiet) toast.success('片段已保存')
    return true
  }

  const saveSegment = async () => {
    const requestToken = beginTaskRequest()
    try {
      await saveCurrentSegment({ requestToken })
    } catch (error) {
      if (acceptsTaskRequest(requestToken)) toast.error(error?.response?.data?.detail || '保存片段失败')
    }
  }

  const regenerateCurrentImage = async () => {
    if (!currentSegment) return
    const requestToken = beginTaskRequest()
    setBusyAction('image')
    try {
      if (!await saveCurrentSegment({ quiet: true, requestToken })) return
      const result = await regenerateImage(taskId, segmentIndex(currentSegment, selectedIndex))
      if (!acceptsTaskRequest(requestToken)) return
      patchCurrentSegment({ image_url: result?.image_url || currentSegment.image_url, image_status: 'completed' })
      await reloadAssets(requestToken)
      if (!acceptsTaskRequest(requestToken)) return
      toast.success('图片已重新生成')
    } catch (error) {
      if (acceptsTaskRequest(requestToken)) toast.error(error?.response?.data?.detail || '重生图片失败')
    } finally {
      if (acceptsTaskRequest(requestToken)) setBusyAction('')
    }
  }

  const previewSegmentVoice = async voice => {
    if (voicePreviewState.playingVoice === voice.id) return stopVoicePreview()
    stopVoicePreview()
    const token = ++voicePreviewTokenRef.current
    setVoicePreviewState(current => nextPreviewState(current, { type: 'start', voiceId: voice.id, token }))
    try {
      const result = await previewVoice({
        voice_type: voice.id,
        text: textDraft || currentSegment?.text || '这是当前分段的音色试听。',
        tts_options: segmentTtsOptions,
      })
      const audio = new Audio(normalizeMediaUrl(result.url))
      voicePreviewAudioRef.current = audio
      audio.onended = stopVoicePreview
      audio.onerror = () => setVoicePreviewState(current => nextPreviewState(current, { type: 'error', voiceId: voice.id, token, error: '试听播放失败' }))
      setVoicePreviewState(current => nextPreviewState(current, { type: 'ready', voiceId: voice.id, token, url: result.url }))
      await audio.play()
    } catch (error) {
      setVoicePreviewState(current => nextPreviewState(current, { type: 'error', voiceId: voice.id, token, error: error?.response?.data?.detail || '音色试听失败' }))
    }
  }

  const regenerateCurrentAudio = async () => {
    if (!currentSegment) return
    const requestToken = beginTaskRequest()
    setBusyAction('audio')
    try {
      if (!await saveCurrentSegment({ quiet: true, requestToken })) return
      const result = await regenerateAudio(taskId, segmentIndex(currentSegment, selectedIndex), {
        voice_type: selectedVoiceType || null,
        tts_options: segmentTtsOptions,
      })
      if (!acceptsTaskRequest(requestToken)) return
      patchCurrentSegment({
        audio_url: result?.audio_url || currentSegment.audio_url,
        audio_status: 'completed',
        audio_voice_type: result?.voice_type || selectedVoiceType,
        audio_tts_options_json: JSON.stringify(result?.tts_options || segmentTtsOptions),
      })
      await reloadAssets(requestToken)
      if (!acceptsTaskRequest(requestToken)) return
      toast.success('配音已重新生成')
    } catch (error) {
      if (acceptsTaskRequest(requestToken)) toast.error(error?.response?.data?.detail || '重配音失败')
    } finally {
      if (acceptsTaskRequest(requestToken)) setBusyAction('')
    }
  }

  const uploadReplacement = async event => {
    const file = event.target.files?.[0]
    if (!file || !currentSegment) return
    const requestToken = beginTaskRequest()
    setBusyAction('upload')
    try {
      const result = await uploadImage(taskId, segmentIndex(currentSegment, selectedIndex), file)
      if (!acceptsTaskRequest(requestToken)) return
      patchCurrentSegment({ image_url: result?.image_url || currentSegment.image_url, image_status: 'completed' })
      await reloadAssets(requestToken)
      if (!acceptsTaskRequest(requestToken)) return
      toast.success('图片已替换')
    } catch (error) {
      if (acceptsTaskRequest(requestToken)) toast.error(error?.response?.data?.detail || '上传替换失败')
    } finally {
      event.target.value = ''
      if (acceptsTaskRequest(requestToken)) setBusyAction('')
    }
  }

  const applyHistoricalImage = async asset => {
    if (!currentSegment || !asset?.has_file) return
    const requestToken = beginTaskRequest()
    try {
      await selectSegmentImage(taskId, segmentIndex(currentSegment, selectedIndex), asset.asset_id)
      if (!acceptsTaskRequest(requestToken)) return
      patchCurrentSegment({ image_url: asset.url || asset.file_url || currentSegment.image_url, image_status: 'completed' })
      await reloadAssets(requestToken)
      if (!acceptsTaskRequest(requestToken)) return
      toast.success('已应用历史图片')
    } catch (error) {
      if (acceptsTaskRequest(requestToken)) toast.error(error?.response?.data?.detail || '应用历史图片失败')
    }
  }

  const createFinalPreview = async () => {
    const requestToken = beginTaskRequest()
    try {
      if (!await saveCurrentSegment({ quiet: true, requestToken })) return
      const job = await createExport(taskId, { target: 'mp4', use_preview: !exportState?.preview?.valid, auto_download: false })
      if (!acceptsTaskRequest(requestToken)) return
      setPreviewJob(job)
      toast.success(job.status === 'completed' ? '完整视频预览已可用' : '已开始生成完整视频预览')
    } catch (error) {
      if (acceptsTaskRequest(requestToken)) toast.error(error?.response?.data?.detail || '生成完整视频预览失败')
    }
  }

  const openExport = () => {
    if (!state.canExport) toast.warning('当前还没有可交付的分镜素材')
    navigate(`/export/${taskId}`)
  }

  if (isTaskLoadPending({ loading, loadError, loadedTaskId, taskId })) return <main className="preview-editor preview-editor-loading"><LoadingState label="正在加载分镜与已保存素材..." /></main>
  if (loadError) return <main className="preview-editor preview-editor-loading"><EmptyState title="预览编辑暂不可用" description={loadError} action={<button type="button" className="button button-primary" onClick={loadPage}>重新加载</button>} /></main>

  return (
    <main className="preview-editor">
      <section className="preview-editor-layout">
        <aside className="preview-rail" aria-label="分镜导航">
          <div className="preview-project-cover">
            {imageUrl ? <img src={imageUrl} alt="当前分镜画面" /> : <ImagePlaceholder label="当前分镜缺少图片" />}
            {currentSegment ? <span>片段 {selectedIndex + 1}</span> : null}
          </div>
          <div className="preview-project-title"><span>项目</span><h1>{taskName(task, taskId)}</h1></div>
          <div className="preview-rail-heading"><strong>分镜导航</strong><span>{orderedSegments.length ? `${selectedIndex + 1} / ${orderedSegments.length}` : '0 / 0'}</span></div>
          <div className="preview-segment-list">
            {orderedSegments.map((segment, index) => {
              const assetState = getSegmentAssetState(segment)
              const segmentImage = normalizeMediaUrl(segment.image_url)
              return <button type="button" key={segment.id || `${segment.segment_index}-${index}`} className={`preview-segment-item${index === selectedIndex ? ' is-selected' : ''}`} onClick={() => selectSegment(index)}>
                <strong>{String(index + 1).padStart(2, '0')}</strong>
                <span className="preview-segment-thumb">{segmentImage ? <img src={segmentImage} alt={`分镜 ${index + 1}`} /> : <ImageOff size={16} aria-label="图片缺失" />}</span>
                <span className="preview-segment-copy">{normalizeSubtitleText(segment.text || '暂无文案')}</span>
                <span className={`preview-status preview-status-${assetState.tone}`}>{assetState.label}</span>
              </button>
            })}
          </div>
          <dl className="preview-project-metrics">
            <div><dt>比例</dt><dd>{ratioLabel(ratio)}</dd></div>
            <div><dt>总时长</dt><dd>{secondsToLabel(totalSeconds)}</dd></div>
            <div><dt>任务状态</dt><dd>{state.label}</dd></div>
          </dl>
        </aside>

        <section className="preview-stage" aria-label="视觉预览与分镜表">
          <header className="preview-breadcrumb"><span>项目 / 预览编辑</span><span className={`preview-status preview-status-${state.tone}`}>{state.label}</span></header>
          {state.key === 'recoverable_assets' ? <section className="preview-recovery"><CircleAlert size={18} /><div><strong>已生成素材处于恢复模式</strong><p>任务失败不会隐藏已保存的文案、图片或配音。缺失素材可在右侧直接补齐。</p></div></section> : null}
          {orderedSegments.length === 0 ? <EmptyState title="暂无分镜数据" description="任务可能仍在生成，或尚未保存分镜。已生成资产仍可从项目资产中恢复查看。" action={<Link className="button button-secondary" to="/assets"><FolderKanban size={16} />返回项目资产</Link>} /> : <>
            <section className="preview-player-panel">
              <header className="preview-mode-toolbar">
                <div role="group" aria-label="预览模式"><button type="button" className={previewMode === 'content' ? 'is-active' : ''} onClick={() => setPreviewMode('content')}>内容预览</button><button type="button" className={previewMode === 'high' ? 'is-active' : ''} disabled={!exportState?.preview?.valid || !highFidelityUrl} onClick={() => setPreviewMode('high')}>完整视频预览</button></div>
                <span className={`preview-render-state is-${exportState?.preview?.status || 'missing'}`}>{renderingPreview ? '正在渲染完整视频' : exportState?.preview?.valid ? '已与当前素材同步' : exportState?.preview?.reason === 'stale' ? '完整视频已过期' : '内容预览无需生成视频'}</span>
              </header>
              {previewMode === 'high' && exportState?.preview?.valid && highFidelityUrl ? <div className={`preview-canvas preview-video-canvas ${ratioClassName(ratio)}`}><video controls preload="metadata" src={highFidelityUrl} aria-label="完整视频预览" /></div> : <>
                <div className={`preview-canvas ${ratioClassName(ratio)}`}>
                  {imageUrl ? <img src={imageUrl} alt={`分镜 ${selectedIndex + 1} 的画面`} /> : <ImagePlaceholder label="图片素材缺失，可上传替换或重新生成" />}
                  <p className="preview-subtitle" style={{ fontSize: `${subtitleFontSize(subtitle, ratio)}px` }}>{subtitle}</p>
                  {!audioUrl ? <span className="preview-no-audio">该段无配音 · 按 {segmentDuration(currentSegment)} 秒播放</span> : null}
                </div>
                <div className="preview-player-controls">
                  <button type="button" className="icon-button preview-play-button" onClick={togglePlayback} aria-label={playing ? '暂停时间线' : '播放时间线'} title={playing ? '暂停时间线' : '播放时间线'}>{playing ? <Pause size={17} /> : <Play size={17} />}</button>
                  <time>{secondsToLabel(currentSeconds)}</time>
                  <input aria-label="选择时间线片段" type="range" min="0" max={Math.max(orderedSegments.length - 1, 0)} value={selectedIndex} onChange={event => selectSegment(event.target.value)} />
                  <time>{secondsToLabel(totalSeconds)}</time>
                  <audio ref={audioRef} src={audioUrl || undefined} preload="auto" onEnded={handleAudioEnded} />
                </div>
              </>}
            </section>

            <section className="preview-table-panel">
              <header className="preview-table-toolbar"><strong>分镜表格</strong><div><ActionButton icon={Save} label="保存片段" onClick={saveSegment} /><ActionButton icon={RefreshCw} label="重生图片" onClick={regenerateCurrentImage} disabled={busyAction === 'image'} /><ActionButton icon={Volume2} label="重配音" onClick={regenerateCurrentAudio} disabled={busyAction === 'audio'} /><ActionButton icon={Upload} label="上传替换" onClick={() => uploadRef.current?.click()} disabled={busyAction === 'upload'} /><button type="button" className="icon-button" onClick={() => selectSegment(selectedIndex - 1)} disabled={selectedIndex === 0} aria-label="上一段" title="上一段"><ChevronLeft size={17} /></button><button type="button" className="icon-button" onClick={() => selectSegment(selectedIndex + 1)} disabled={selectedIndex === orderedSegments.length - 1} aria-label="下一段" title="下一段"><ChevronRight size={17} /></button></div></header>
              <div className="preview-segment-table" role="table" aria-label="分镜表格"><div className="preview-table-row preview-table-head" role="row"><span>#</span><span>时间</span><span>文案</span><span>画面</span><span>配音</span><span>状态</span></div>{orderedSegments.map((segment, index) => <SegmentRow key={segment.id || `${segment.segment_index}-${index}`} segment={segment} index={index} selected={index === selectedIndex} allSegments={orderedSegments} onSelect={selectSegment} />)}</div>
            </section>
          </>}
        </section>

        <aside className="preview-inspector" aria-label="选中分镜设置">
          {currentSegment ? <>
            <header className="preview-inspector-heading"><div><span>片段设置</span><h2>片段 {selectedIndex + 1}</h2></div><div><button type="button" className="icon-button" onClick={() => selectSegment(selectedIndex - 1)} disabled={selectedIndex === 0} aria-label="上一段" title="上一段"><ChevronLeft size={17} /></button><button type="button" className="icon-button" onClick={() => selectSegment(selectedIndex + 1)} disabled={selectedIndex === orderedSegments.length - 1} aria-label="下一段" title="下一段"><ChevronRight size={17} /></button></div></header>
            <div className="preview-segment-range"><span>片段范围</span><strong>{segmentRange(orderedSegments, selectedIndex)}</strong></div>
            <dl className="preview-media-grid"><div><dt>视频比例</dt><dd>{ratioLabel(ratio)}</dd></div><div><dt>画布尺寸</dt><dd>{exportState?.canvas?.width && exportState?.canvas?.height ? `${exportState.canvas.width} x ${exportState.canvas.height}` : '未读取'}</dd></div><div><dt>图片尺寸</dt><dd>{!imageUrl ? '未生成' : imageSize?.width && imageSize?.height ? `${imageSize.width} x ${imageSize.height}` : '读取中'}</dd></div></dl>
            <label className="preview-field"><span>提示词 Prompt</span><textarea value={imagePromptDraft} maxLength="800" placeholder="描述这一段需要生成的画面" onChange={event => setImagePromptDraft(event.target.value)} /><small>{imagePromptDraft.length}/800</small><button type="button" className="preview-smart-button" onClick={() => setImagePromptDraft(value => appendPromptGuidance(value || textDraft || currentSegment.text))}><Sparkles size={15} />优化提示词</button></label>
            <section className="preview-voice-picker"><header><span>配音音色</span><small>仅覆盖当前分段</small></header><VoicePicker voices={voices} value={selectedVoiceType} ttsOptions={segmentTtsOptions} onChange={voiceId => { stopVoicePreview(); setSelectedVoiceType(voiceId) }} onOptionsChange={options => { stopVoicePreview(); setSegmentTtsOptions(options) }} onPreview={previewSegmentVoice} playingVoice={voicePreviewState.playingVoice} previewLoading={voicePreviewState.loading} previewError={voicePreviewState.error} compact /></section>
            <label className="preview-field"><span>字幕文案</span><textarea value={textDraft} maxLength="1000" placeholder="当前分镜字幕文案" onChange={event => setTextDraft(event.target.value)} /><small>{textDraft.length}/1000</small></label>
            <section className="preview-subtitle-settings"><div><span>启用字幕</span><strong>开启</strong></div><div><span>字幕位置</span><strong>底部安全区</strong></div></section>
            <div className="preview-action-grid"><button type="button" className="button button-secondary" onClick={saveSegment}><Save size={16} />保存文案</button><button type="button" className="button button-secondary" onClick={() => uploadRef.current?.click()} disabled={busyAction === 'upload'}><Upload size={16} />上传替换</button><button type="button" className="button button-secondary" onClick={regenerateCurrentImage} disabled={busyAction === 'image'}><RefreshCw size={16} />{busyAction === 'image' ? '生成中...' : '重生图片'}</button><button type="button" className="button button-secondary" onClick={regenerateCurrentAudio} disabled={busyAction === 'audio'}><Volume2 size={16} />{busyAction === 'audio' ? '生成中...' : '重配音'}</button></div>
            <input ref={uploadRef} type="file" accept="image/*" hidden onChange={uploadReplacement} />
            <section className="preview-history"><header><strong>历史图片</strong><button type="button" className="icon-button" onClick={() => reloadAssets()} aria-label="刷新历史图片" title="刷新历史图片"><RefreshCw size={16} /></button></header><div>{imageAssets.length ? imageAssets.map(asset => <button type="button" key={asset.asset_id} disabled={!asset.has_file} onClick={() => applyHistoricalImage(asset)} title={asset.label || '应用历史图片'}>{asset.url || asset.file_url ? <img src={normalizeMediaUrl(asset.url || asset.file_url)} alt={asset.label || '历史图片'} /> : <FileImage size={17} />}</button>) : <p>暂无历史图片</p>}</div></section>
            <section className="preview-asset-warning"><CircleAlert size={17} /><p>即使任务失败，已生成的图片、配音和文案仍会在这里保留。</p></section>
            <button type="button" className={state.canExport ? 'button button-primary preview-export-button' : 'button button-secondary preview-export-button'} onClick={openExport}>{state.canExport ? '导出视频' : '查看导出状态'}</button>
          </> : <EmptyState title="等待分镜" description="分镜写入后将在此处显示编辑控件。" />}
        </aside>
      </section>
      {currentSegment ? <footer className="preview-editor-footer"><Link className="button button-secondary" to="/assets">返回项目资产</Link><button type="button" className="button button-secondary" disabled={renderingPreview} onClick={createFinalPreview}><LoaderCircle className={renderingPreview ? 'spin' : ''} size={16} />{renderingPreview ? '正在生成完整视频...' : exportState?.preview?.valid ? '重新生成完整视频预览' : '生成完整视频预览'}</button><button type="button" className={state.canExport ? 'button button-primary' : 'button button-secondary'} onClick={openExport}>{state.canExport ? '前往导出中心' : '查看导出状态'}</button></footer> : null}
    </main>
  )
}

function ActionButton({ icon: Icon, label, onClick, disabled }) {
  return <button type="button" className="preview-toolbar-action" onClick={onClick} disabled={disabled}><Icon size={15} />{label}</button>
}

function ImagePlaceholder({ label }) {
  return <div className="preview-image-placeholder"><ImageOff size={25} /><span>{label}</span></div>
}

function SegmentRow({ allSegments, index, onSelect, segment, selected }) {
  const image = normalizeMediaUrl(segment.image_url)
  const assetState = getSegmentAssetState(segment)
  return <button type="button" className={`preview-table-row${selected ? ' is-selected' : ''}`} role="row" onClick={() => onSelect(index)}><strong>{String(index + 1).padStart(2, '0')}</strong><span>{segmentRange(allSegments, index)}</span><span className="preview-table-script">{normalizeSubtitleText(segment.text || '暂无文案')}</span><span className="preview-table-image">{image ? <img src={image} alt={`分镜 ${index + 1} 画面`} /> : <ImageOff size={16} aria-label="图片缺失" />}</span><span>{segment.audio_url ? '已生成' : '缺失'}</span><span className={`preview-status preview-status-${assetState.tone}`}>{assetState.label}</span></button>
}

function segmentRange(segments, index) {
  const start = segments.slice(0, index).reduce((total, segment) => total + segmentDuration(segment), 0)
  return `${secondsToLabel(start)}-${secondsToLabel(start + segmentDuration(segments[index]))}`
}
