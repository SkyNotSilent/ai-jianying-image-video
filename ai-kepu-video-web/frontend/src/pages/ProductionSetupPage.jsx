import { useEffect, useMemo, useState } from 'react'
import { CheckCircle2, Edit3, Image, Settings2, ShieldCheck, TriangleAlert } from 'lucide-react'
import { useNavigate, useParams } from 'react-router'
import { createTask, getConfig, getVoices } from '../api/task'
import { toast } from '../lib/toast'
import { estimateDuration, estimateSegments, getDraft, manuscriptText, ratioOptions, saveDraft, textStyles, updateDraft, visualStyles } from '../utils/projectDrafts'
import './creation-flow.css'

function normalizedThemeLength(value) {
  const number = Number(value)
  if (!Number.isFinite(number) || number <= 0) return 0
  return Math.max(50, Math.min(2000, Math.round(number / 50) * 50))
}

function apiReadiness(config) {
  const missing = []
  if (!config?.llm?.base_url || !config?.llm?.model || !config?.llm?.api_key) missing.push('生文 API')
  if (!config?.image?.api_url || !config?.image?.model || !config?.image?.api_key) missing.push('生图 API')
  const tts = config?.tts || {}
  if (tts.provider === 'mimo') {
    if (!tts.mimo?.base_url || !tts.mimo?.model || !tts.mimo?.api_key || !tts.mimo?.default_voice) missing.push('小米 MiMo TTS')
  } else if (tts.auth_method === 'api_key') {
    if (!tts.api_url || !tts.api_key || !tts.cluster || !tts.default_voice) missing.push('豆包 TTS')
  } else if (!tts.api_url || !tts.appid || !tts.token || !tts.cluster || !tts.default_voice) {
    missing.push('豆包 TTS')
  }
  return missing
}

export function ProductionSetupPage() {
  const { draftId } = useParams()
  const navigate = useNavigate()
  const [draft, setDraft] = useState(() => getDraft(draftId))
  const [voices, setVoices] = useState([])
  const [config, setConfig] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const manuscript = manuscriptText(draft)
  const isTheme = draft?.input_mode === 'theme'
  const targetLength = normalizedThemeLength(draft?.length) || 300
  const contentLength = manuscript.replace(/\s+/g, '').length
  const duration = estimateDuration(manuscript, draft?.voice_speed)
  const segments = estimateSegments(manuscript)
  const missingApiItems = apiReadiness(config)
  const apiReady = Boolean(config) && missingApiItems.length === 0

  useEffect(() => {
    const loaded = getDraft(draftId)
    if (!loaded) {
      toast.warning('未找到文稿草稿，请重新创建项目')
      navigate('/', { replace: true })
      return
    }
    setDraft(loaded)
    Promise.all([getVoices(), getConfig()])
      .then(([voiceList, runtimeConfig]) => { setVoices(Array.isArray(voiceList) ? voiceList : []); setConfig(runtimeConfig) })
      .catch(() => toast.warning('未能读取完整配置，请确认后端服务在线'))
  }, [draftId, navigate])

  const plan = useMemo(() => {
    if (isTheme) return [
      { title: `围绕主题扩写到约 ${targetLength} 字`, value: '扩写' },
      { title: '根据成稿拆分分镜、画面和配音', value: '生成' },
      { title: '进入预览页后逐段修改素材', value: '可编辑' },
    ]
    const chunks = manuscript.split(/[。！？\n]/).map(item => item.trim()).filter(Boolean).slice(0, 7)
    return (chunks.length ? chunks : ['开场观点', '核心解释', '案例补充', '总结观点']).map((title, index) => ({ title: title.slice(0, 18), value: `00:${String(15 + index).padStart(2, '0')}` }))
  }, [isTheme, manuscript, targetLength])

  if (!draft) return null

  const updateLocalDraft = patch => {
    const next = saveDraft({ ...draft, ...patch })
    setDraft(next)
  }

  const chooseVoice = value => {
    const voice = voices.find(item => item.id === value)
    updateLocalDraft({ voice_type: value, voice_name: voice?.name || '' })
  }

  const startProduction = async () => {
    if (!manuscript.trim()) {
      toast.warning('请先补全文稿内容')
      navigate(`/manuscript/${draft.draft_id}`)
      return
    }
    const name = draft.name?.trim() || manuscript.replace(/\s+/g, ' ').trim().slice(0, 32)
    const prepared = saveDraft({ ...draft, name })
    setDraft(prepared)
    if (!apiReady) {
      toast.warning(config ? `请先完成 ${missingApiItems.join('、')} 配置` : '请先完成模型 API 配置')
      navigate('/settings')
      return
    }
    setSubmitting(true)
    try {
      const inputMode = prepared.input_mode === 'theme' ? 'theme' : 'script'
      const result = await createTask({
        name: prepared.name,
        theme: manuscript.slice(0, 5000),
        input_mode: inputMode,
        style: `${prepared.text_style || '知识科普'}|${prepared.visual_style || '吉卜力'}`,
        ratio: prepared.ratio || '16:9',
        length: inputMode === 'theme' ? normalizedThemeLength(prepared.length) : 0,
        voice_type: prepared.voice_type || null,
      })
      updateDraft(prepared.draft_id, { created_task_id: result.task_id })
      toast.success('生产任务已提交')
      navigate(`/process/${result.task_id}`)
    } catch (error) {
      toast.error(error?.response?.data?.detail || '提交生产任务失败')
    } finally {
      setSubmitting(false)
    }
  }

  const checks = [
    { label: '文稿已保存', description: isTheme ? `主题 ${contentLength} 字，扩写目标 ${targetLength} 字` : `${contentLength} 字，预计 ${segments} 段`, ready: true },
    { label: '本地资产保留', description: '失败前已生成的分镜、图片和音频不会隐藏', ready: true },
    { label: '生文 API', description: missingApiItems.includes('生文 API') ? '缺少 Base URL、API Key 或模型名' : `${config?.llm?.model || config?.text?.model || '当前模型'} 已配置`, ready: !missingApiItems.includes('生文 API') },
    { label: '生图 API', description: missingApiItems.includes('生图 API') ? '缺少 API URL、API Key 或模型名' : `${config?.image?.model || '当前图像模型'} 已配置`, ready: !missingApiItems.includes('生图 API') },
    { label: 'TTS API', description: missingApiItems.some(item => item.includes('TTS')) ? '缺少当前配音 provider 的必要配置' : `${draft.voice_name || config?.tts?.provider || '自动匹配'} 已配置`, ready: !missingApiItems.some(item => item.includes('TTS')) },
    { label: '生成策略', description: '生图串行生成，遇到限速会自动等待后重试', ready: false },
  ]

  return (
    <main className="creation-page production-page">
      <div className="production-layout">
        <aside className="work-panel production-summary">
          <p className="breadcrumb">项目 / 文稿编辑 / <strong>生产设置</strong></p>
          <h1>{draft.name || '未命名项目'}</h1>
          <p className="project-preview">{manuscript.replace(/\s+/g, ' ').slice(0, 92)}</p>
          <div className="production-stat-grid">
            <Stat label={isTheme ? '扩写目标' : '脚本字数'} value={isTheme ? `${targetLength} 字` : contentLength} />
            <Stat label={isTheme ? '生成顺序' : '预计时长'} value={isTheme ? '先扩写' : duration} />
            <Stat label={isTheme ? '分镜拆分' : '分镜预估'} value={isTheme ? '成稿后' : `${segments} 段`} />
          </div>
          <section className="segment-plan"><header><strong>分镜计划</strong></header><div className="segment-plan-head"><span>#</span><span>内容摘要</span><span>时长</span></div>{plan.map((item, index) => <div className="segment-plan-row" key={`${item.title}-${index}`}><span>{String(index + 1).padStart(2, '0')}</span><span>{item.title}</span><span>{item.value}</span></div>)}</section>
          <section className="asset-protection"><ShieldCheck size={19} /><div><strong>资产保护已开启</strong><p>生产过程中产生的素材与草稿将自动保存，失败也保留素材。</p></div></section>
          {!apiReady ? <section className="config-warning"><TriangleAlert size={18} /><div><strong>请先完成 API 配置</strong><p>{config ? `缺少：${missingApiItems.join('、')}` : '未读取到配置，请确认后端服务在线。'}</p></div></section> : null}
          <button type="button" className="button button-secondary wide-button" onClick={() => navigate(`/manuscript/${draft.draft_id}`)}><Edit3 size={16} />返回文稿编辑</button>
        </aside>

        <section className="work-panel production-config">
          <PanelHeading eyebrow="生产配置" title="画面与配音" />
          <section className="model-summary"><Image size={20} /><div><strong>{config?.image?.model || '图像服务待配置'}</strong><span>{config?.llm?.model || config?.text?.model || '生文服务'} / {draft.voice_name || config?.tts?.provider || '自动匹配'}，提交后由 FastAPI 编排</span></div><button type="button" className="button button-secondary" onClick={() => navigate('/settings')} title="前往 API 配置"><Settings2 size={16} /></button></section>
          <fieldset className="control-group"><legend>画面风格</legend><div className="production-style-grid">{visualStyles.map(style => <button type="button" key={style.value} className={draft.visual_style === style.value ? 'is-selected' : ''} onClick={() => updateLocalDraft({ visual_style: style.value })}><img src={style.image} alt="" /><span>{style.label}</span></button>)}</div></fieldset>
          <div className="production-field-grid"><fieldset className="control-group"><legend>视频比例</legend><div className="segmented-control">{ratioOptions.map(ratio => <button type="button" key={ratio} className={draft.ratio === ratio ? 'is-selected' : ''} onClick={() => updateLocalDraft({ ratio })}>{ratio}</button>)}</div></fieldset><label className="field-label">创作风格<select value={draft.text_style || '知识科普'} onChange={event => updateLocalDraft({ text_style: event.target.value })}>{textStyles.map(style => <option key={style}>{style}</option>)}</select></label></div>
          <label className="field-label">配音音色<select value={draft.voice_type || ''} onChange={event => chooseVoice(event.target.value)}><option value="">自动匹配</option>{voices.map(voice => <option value={voice.id} key={voice.id}>{voice.name}</option>)}</select></label>
        </section>

        <aside className="work-panel readiness-panel"><PanelHeading eyebrow="生产就绪检查" title="生产检查" /><div className="readiness-list">{checks.map(item => <div className={`readiness-item ${item.ready ? 'is-ready' : 'is-warning'}`} key={item.label}>{item.ready ? <CheckCircle2 size={18} /> : <TriangleAlert size={18} />}<div><strong>{item.label}</strong><span>{item.description}</span></div></div>)}</div><section className="runtime-facts"><span>运行配置</span><strong>{apiReady ? '服务已就绪' : '需要完成 API 配置'}</strong><p>实际可用性由当前本地配置与任务状态决定。提交后会依次执行主题扩写、分镜、画面提示词与图片、TTS 和剪映草稿构建。</p></section></aside>
      </div>
      <footer className="sticky-production-actions"><button type="button" className="button button-secondary" onClick={() => navigate(`/manuscript/${draft.draft_id}`)}>返回文稿</button><button type="button" className="button button-primary" disabled={submitting} onClick={startProduction}>{submitting ? '提交中...' : apiReady ? '开始生产' : '先配置 API'}</button></footer>
    </main>
  )
}

function PanelHeading({ eyebrow, title }) { return <header className="panel-heading"><p>{eyebrow}</p><h2>{title}</h2></header> }
function Stat({ label, value }) { return <div><span>{label}</span><strong>{value}</strong></div> }
