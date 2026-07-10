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
  getExportState,
  getSegments,
  getTaskAssets,
  getTaskStatus,
  getVoices,
  regenerateAudio,
  regenerateImage,
  renderPreview,
  selectSegmentImage,
  updateSegment,
  uploadImage,
} from '../api/task'
import { EmptyState, LoadingState } from '../components/StatusStates'
import { toast } from '../lib/toast'
import { normalizeMediaUrl } from '../utils/mediaUrl'
import { deriveTaskState, ratioClassName, ratioLabel } from '../utils/taskState'
import {
  appendPromptGuidance,
  getSegmentAssetState,
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

export function PreviewPage() {
  const { taskId } = useParams()
  const navigate = useNavigate()
  const uploadRef = useRef(null)
  const playTimer = useRef(null)
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
  const [imageSize, setImageSize] = useState(null)
  const [playing, setPlaying] = useState(false)
  const [busyAction, setBusyAction] = useState('')
  const [renderingPreview, setRenderingPreview] = useState(false)

  const orderedSegments = useMemo(() => sortSegmentsByIndex(segments), [segments])
  const currentSegment = orderedSegments[selectedIndex] || null
  const state = useMemo(
    () => deriveTaskState({ task, segments: orderedSegments, exportState }),
    [exportState, orderedSegments, task],
  )
  const ratio = exportState?.ratio || task?.ratio || task?.result?.ratio || '16:9'
  const imageUrl = normalizeMediaUrl(currentSegment?.image_url)
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

  const reloadAssets = useCallback(async () => {
    try {
      const nextAssets = await getTaskAssets(taskId)
      setAssets(Array.isArray(nextAssets) ? nextAssets : [])
    } catch {
      setAssets([])
    }
  }, [taskId])

  const loadPage = useCallback(async () => {
    setLoading(true)
    setLoadError('')
    try {
      const [taskData, segmentData, exportData, voiceData, assetData] = await Promise.all([
        getTaskStatus(taskId),
        getSegments(taskId),
        getExportState(taskId).catch(() => null),
        getVoices().catch(() => []),
        getTaskAssets(taskId).catch(() => []),
      ])
      setTask(taskData || null)
      setSegments(sortSegmentsByIndex(segmentData))
      setExportState(exportData)
      setVoices(Array.isArray(voiceData) ? voiceData : [])
      setAssets(Array.isArray(assetData) ? assetData : [])
    } catch (error) {
      console.error('加载预览页失败', error)
      setLoadError('未能读取任务分镜。请确认后端服务在线后重试。')
      toast.error('加载预览页失败')
    } finally {
      setLoading(false)
    }
  }, [taskId])

  useEffect(() => { loadPage() }, [loadPage])

  useEffect(() => {
    if (selectedIndex >= orderedSegments.length) setSelectedIndex(Math.max(orderedSegments.length - 1, 0))
  }, [orderedSegments.length, selectedIndex])

  useEffect(() => {
    setTextDraft(currentSegment?.text || '')
    setImagePromptDraft(currentSegment?.image_prompt || '')
    setSelectedVoiceType('')
  }, [currentSegment?.segment_index])

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
    window.clearTimeout(playTimer.current)
    if (!playing || !currentSegment) return undefined
    if (selectedIndex >= orderedSegments.length - 1) {
      setPlaying(false)
      return undefined
    }
    playTimer.current = window.setTimeout(() => setSelectedIndex(index => index + 1), Math.min(segmentDuration(currentSegment) * 1000, 2000))
    return () => window.clearTimeout(playTimer.current)
  }, [currentSegment, orderedSegments.length, playing, selectedIndex])

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
  }

  const saveCurrentSegment = async ({ quiet = false } = {}) => {
    if (!currentSegment) return false
    await updateSegment(taskId, segmentIndex(currentSegment, selectedIndex), {
      text: textDraft,
      image_prompt: imagePromptDraft,
    })
    patchCurrentSegment({ text: textDraft, image_prompt: imagePromptDraft })
    if (!quiet) toast.success('片段已保存')
    return true
  }

  const saveSegment = async () => {
    try {
      await saveCurrentSegment()
    } catch (error) {
      toast.error(error?.response?.data?.detail || '保存片段失败')
    }
  }

  const regenerateCurrentImage = async () => {
    if (!currentSegment) return
    setBusyAction('image')
    try {
      await saveCurrentSegment({ quiet: true })
      const result = await regenerateImage(taskId, segmentIndex(currentSegment, selectedIndex))
      patchCurrentSegment({ image_url: result?.image_url || currentSegment.image_url, image_status: 'completed' })
      await reloadAssets()
      toast.success('图片已重新生成')
    } catch (error) {
      toast.error(error?.response?.data?.detail || '重生图片失败')
    } finally {
      setBusyAction('')
    }
  }

  const regenerateCurrentAudio = async () => {
    if (!currentSegment) return
    setBusyAction('audio')
    try {
      await saveCurrentSegment({ quiet: true })
      const result = await regenerateAudio(taskId, segmentIndex(currentSegment, selectedIndex), selectedVoiceType || null)
      patchCurrentSegment({ audio_url: result?.audio_url || currentSegment.audio_url, audio_status: 'completed' })
      await reloadAssets()
      toast.success('配音已重新生成')
    } catch (error) {
      toast.error(error?.response?.data?.detail || '重配音失败')
    } finally {
      setBusyAction('')
    }
  }

  const uploadReplacement = async event => {
    const file = event.target.files?.[0]
    if (!file || !currentSegment) return
    setBusyAction('upload')
    try {
      const result = await uploadImage(taskId, segmentIndex(currentSegment, selectedIndex), file)
      patchCurrentSegment({ image_url: result?.image_url || currentSegment.image_url, image_status: 'completed' })
      await reloadAssets()
      toast.success('图片已替换')
    } catch (error) {
      toast.error(error?.response?.data?.detail || '上传替换失败')
    } finally {
      event.target.value = ''
      setBusyAction('')
    }
  }

  const applyHistoricalImage = async asset => {
    if (!currentSegment || !asset?.has_file) return
    try {
      await selectSegmentImage(taskId, segmentIndex(currentSegment, selectedIndex), asset.asset_id)
      patchCurrentSegment({ image_url: asset.url || asset.file_url || currentSegment.image_url, image_status: 'completed' })
      await reloadAssets()
      toast.success('已应用历史图片')
    } catch (error) {
      toast.error(error?.response?.data?.detail || '应用历史图片失败')
    }
  }

  const createFinalPreview = async () => {
    setRenderingPreview(true)
    try {
      await renderPreview(taskId)
      const nextExportState = await getExportState(taskId).catch(() => null)
      setExportState(nextExportState)
      toast.success('最终预览已生成')
    } catch (error) {
      toast.error(error?.response?.data?.detail || '生成最终预览失败')
    } finally {
      setRenderingPreview(false)
    }
  }

  const openExport = () => {
    if (!state.canExport) toast.warning('素材缺失或最终预览不可用，请先补齐素材或生成最终预览')
    navigate(`/export/${taskId}`)
  }

  if (loading) return <main className="preview-editor preview-editor-loading"><LoadingState label="正在加载分镜与已保存素材..." /></main>
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
                <span className="preview-segment-copy">{segment.text || '暂无文案'}</span>
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
              <div className={`preview-canvas ${ratioClassName(ratio)}`}>
                {imageUrl ? <img src={imageUrl} alt={`分镜 ${selectedIndex + 1} 的画面`} /> : <ImagePlaceholder label="图片素材缺失，可上传替换或重新生成" />}
                <p className="preview-subtitle" style={{ fontSize: `${subtitleFontSize(subtitle, ratio)}px` }}>{subtitle}</p>
              </div>
              <div className="preview-player-controls">
                <button type="button" className="icon-button preview-play-button" onClick={() => setPlaying(value => !value)} aria-label={playing ? '暂停时间线' : '播放时间线'} title={playing ? '暂停时间线' : '播放时间线'}>{playing ? <Pause size={17} /> : <Play size={17} />}</button>
                <time>{secondsToLabel(currentSeconds)}</time>
                <input aria-label="选择时间线片段" type="range" min="0" max={Math.max(orderedSegments.length - 1, 0)} value={selectedIndex} onChange={event => selectSegment(event.target.value)} />
                <time>{secondsToLabel(totalSeconds)}</time>
              </div>
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
            <label className="preview-field"><span>配音音色</span><select value={selectedVoiceType} onChange={event => setSelectedVoiceType(event.target.value)}><option value="">沿用任务音色</option>{voices.map(voice => <option key={voice.id} value={voice.id}>{voice.name}</option>)}</select></label>
            <label className="preview-field"><span>字幕文案</span><textarea value={textDraft} maxLength="1000" placeholder="当前分镜字幕文案" onChange={event => setTextDraft(event.target.value)} /><small>{textDraft.length}/1000</small></label>
            <section className="preview-subtitle-settings"><div><span>启用字幕</span><strong>开启</strong></div><div><span>字幕位置</span><strong>底部安全区</strong></div></section>
            <div className="preview-action-grid"><button type="button" className="button button-secondary" onClick={saveSegment}><Save size={16} />保存文案</button><button type="button" className="button button-secondary" onClick={() => uploadRef.current?.click()} disabled={busyAction === 'upload'}><Upload size={16} />上传替换</button><button type="button" className="button button-secondary" onClick={regenerateCurrentImage} disabled={busyAction === 'image'}><RefreshCw size={16} />{busyAction === 'image' ? '生成中...' : '重生图片'}</button><button type="button" className="button button-secondary" onClick={regenerateCurrentAudio} disabled={busyAction === 'audio'}><Volume2 size={16} />{busyAction === 'audio' ? '生成中...' : '重配音'}</button></div>
            <input ref={uploadRef} type="file" accept="image/*" hidden onChange={uploadReplacement} />
            <section className="preview-history"><header><strong>历史图片</strong><button type="button" className="icon-button" onClick={reloadAssets} aria-label="刷新历史图片" title="刷新历史图片"><RefreshCw size={16} /></button></header><div>{imageAssets.length ? imageAssets.map(asset => <button type="button" key={asset.asset_id} disabled={!asset.has_file} onClick={() => applyHistoricalImage(asset)} title={asset.label || '应用历史图片'}>{asset.url || asset.file_url ? <img src={normalizeMediaUrl(asset.url || asset.file_url)} alt={asset.label || '历史图片'} /> : <FileImage size={17} />}</button>) : <p>暂无历史图片</p>}</div></section>
            <section className="preview-asset-warning"><CircleAlert size={17} /><p>即使任务失败，已生成的图片、配音和文案仍会在这里保留。</p></section>
            <button type="button" className={state.canExport ? 'button button-primary preview-export-button' : 'button button-secondary preview-export-button'} onClick={openExport}>{state.canExport ? '导出视频' : '查看导出状态'}</button>
          </> : <EmptyState title="等待分镜" description="分镜写入后将在此处显示编辑控件。" />}
        </aside>
      </section>
      {currentSegment ? <footer className="preview-editor-footer"><Link className="button button-secondary" to="/assets">返回项目资产</Link><button type="button" className="button button-secondary" disabled={renderingPreview} onClick={createFinalPreview}><LoaderCircle className={renderingPreview ? 'spin' : ''} size={16} />{renderingPreview ? '生成中...' : '生成最终预览'}</button><button type="button" className={state.canExport ? 'button button-primary' : 'button button-secondary'} onClick={openExport}>{state.canExport ? '导出视频' : '查看导出状态'}</button></footer> : null}
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
  return <button type="button" className={`preview-table-row${selected ? ' is-selected' : ''}`} role="row" onClick={() => onSelect(index)}><strong>{String(index + 1).padStart(2, '0')}</strong><span>{segmentRange(allSegments, index)}</span><span className="preview-table-script">{segment.text || '暂无文案'}</span><span className="preview-table-image">{image ? <img src={image} alt={`分镜 ${index + 1} 画面`} /> : <ImageOff size={16} aria-label="图片缺失" />}</span><span>{segment.audio_url ? '已生成' : '缺失'}</span><span className={`preview-status preview-status-${assetState.tone}`}>{assetState.label}</span></button>
}

function segmentRange(segments, index) {
  const start = segments.slice(0, index).reduce((total, segment) => total + segmentDuration(segment), 0)
  return `${secondsToLabel(start)}-${secondsToLabel(start + segmentDuration(segments[index]))}`
}
