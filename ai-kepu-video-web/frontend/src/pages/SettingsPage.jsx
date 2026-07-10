import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  ArrowLeft,
  CheckCircle2,
  CircleAlert,
  Cpu,
  Image,
  LoaderCircle,
  MessageSquareText,
  RefreshCw,
  Save,
  Volume2,
} from 'lucide-react'
import { useNavigate } from 'react-router'
import { fetchConfigModels, getConfig, testTtsConfig, updateConfig } from '../api/task'
import { EmptyState, LoadingState } from '../components/StatusStates'
import {
  MIMO_VOICES,
  applyMimoPreset,
  buildModelPayload,
  normalizeConcurrency,
  normalizeConfig,
  validateConfig,
  validateTtsTest,
} from '../lib/settingsConfig'
import { toast } from '../lib/toast'
import { normalizeMediaUrl } from '../utils/mediaUrl'
import './delivery-pages.css'

const IMAGE_SIZES = ['auto', '1024x1024', '1536x1024', '1024x1536', '1792x1024', '1024x1792', '1920x1080', '1080x1920']
const SECTION_LINKS = [
  { id: 'settings-llm', label: '生文模型', icon: MessageSquareText },
  { id: 'settings-image', label: 'Agnes 生图', icon: Image },
  { id: 'settings-tts', label: '配音模型', icon: Volume2 },
  { id: 'settings-runtime', label: '生成并发', icon: Cpu },
]

export function SettingsPage() {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [saving, setSaving] = useState(false)
  const [testingTts, setTestingTts] = useState(false)
  const [ttsTestUrl, setTtsTestUrl] = useState('')
  const [modelLoading, setModelLoading] = useState({ llm: false, image: false })
  const [modelOptions, setModelOptions] = useState({ llm: [], image: [] })
  const [form, setForm] = useState(() => normalizeConfig())

  const loadConfig = useCallback(async () => {
    setLoading(true)
    setTtsTestUrl('')
    setLoadError('')
    try {
      setForm(normalizeConfig(await getConfig()))
    } catch (error) {
      console.error('加载 API 配置失败', error)
      setLoadError('API 配置暂不可用，请确认后端服务在线后重试。')
      toast.error('加载 API 配置失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadConfig() }, [loadConfig])

  const readiness = useMemo(() => {
    const llmReady = Boolean(form.llm.base_url && form.llm.api_key && form.llm.model)
    const imageReady = Boolean(form.image.api_url && form.image.api_key && form.image.model)
    const ttsReady = form.tts.provider === 'mimo'
      ? Boolean(form.tts.mimo.base_url && form.tts.mimo.api_key && form.tts.mimo.model && form.tts.mimo.default_voice)
      : form.tts.auth_method === 'api_key'
        ? Boolean(form.tts.api_url && form.tts.api_key && form.tts.cluster && form.tts.default_voice)
        : Boolean(form.tts.api_url && form.tts.appid && form.tts.token && form.tts.cluster && form.tts.default_voice)
    return [
      { label: '生文 API', ready: llmReady, detail: llmReady ? form.llm.model : '配置不完整' },
      { label: 'Agnes 生图', ready: imageReady, detail: imageReady ? form.image.model : '配置不完整' },
      { label: 'TTS API', ready: ttsReady, detail: ttsReady ? (form.tts.provider === 'mimo' ? 'MiMo' : '豆包') : '配置不完整' },
    ]
  }, [form])

  const updateSection = (section, key, value) => setForm(current => ({ ...current, [section]: { ...current[section], [key]: value } }))
  const updateTts = (key, value) => setForm(current => ({ ...current, tts: { ...current.tts, [key]: value } }))
  const updateMimo = (key, value) => setForm(current => ({ ...current, tts: { ...current.tts, mimo: { ...current.tts.mimo, [key]: value } } }))

  const loadModels = async type => {
    const payload = buildModelPayload(type, form)
    const isImage = type === 'image'
    if (!payload.base_url?.trim()) {
      toast.warning(isImage ? '请先填写生图 API URL' : '请先填写生文 Base URL')
      return
    }
    if (!payload.api_key?.trim()) {
      toast.warning(isImage ? '请先填写生图 API Key' : '请先填写生文 API Key')
      return
    }
    setModelLoading(current => ({ ...current, [type]: true }))
    try {
      const result = await fetchConfigModels(payload)
      const models = Array.isArray(result?.models) ? result.models : []
      setModelOptions(current => ({ ...current, [type]: models }))
      if (!models.length) {
        toast.warning('没有获取到可选模型')
      } else {
        if (!form[type].model && models[0]?.id) updateSection(type, 'model', models[0].id)
        toast.success(`已获取 ${models.length} 个模型`)
      }
    } catch (error) {
      console.error('获取模型列表失败', error)
      toast.error('获取模型列表失败')
    } finally {
      setModelLoading(current => ({ ...current, [type]: false }))
    }
  }

  const saveConfig = async () => {
    const normalized = normalizeConfig(form)
    const issue = validateConfig(normalized)
    if (issue) {
      toast.warning(issue)
      return
    }
    setSaving(true)
    try {
      const saved = await updateConfig(normalized)
      setForm(normalizeConfig(saved || normalized))
      toast.success('配置已保存')
    } catch (error) {
      console.error('保存 API 配置失败', error)
      toast.error('保存 API 配置失败')
    } finally {
      setSaving(false)
    }
  }

  const testTts = async () => {
    setTtsTestUrl('')
    const issue = validateTtsTest(form)
    if (issue) {
      toast.warning(issue)
      return
    }
    setTestingTts(true)
    try {
      const result = await testTtsConfig({
        tts: form.tts,
        voice_type: form.tts.provider === 'mimo' ? form.tts.mimo.default_voice : form.tts.default_voice,
        text: 'InsightCut 配音配置测试成功。',
      })
      setTtsTestUrl(result?.url || '')
      toast.success('TTS 配置测试通过')
    } catch (error) {
      console.error('TTS 配置测试失败', error)
      toast.error(error?.response?.data?.detail || 'TTS 配置测试失败')
    } finally {
      setTestingTts(false)
    }
  }

  if (loading) return <main className="delivery-loading"><LoadingState label="正在读取 API 配置..." /></main>
  if (loadError) return <main className="delivery-loading"><EmptyState title="API 配置不可用" description={loadError} action={<button className="button button-primary" type="button" onClick={loadConfig}>重试</button>} /></main>

  return (
    <main className="settings-page">
      <header className="settings-heading">
        <div><p className="eyebrow">配置控制台</p><h1>API 配置</h1><p>维护生文、生图和配音服务连接，配置会原样提交给本地后端。</p></div>
        <button className="button button-secondary" type="button" onClick={() => navigate(-1)}><ArrowLeft size={16} aria-hidden="true" />返回生产</button>
      </header>

      <section className="settings-readiness" aria-label="配置状态">
        {readiness.map(item => <div key={item.label} className={item.ready ? 'is-ready' : 'is-warning'}>{item.ready ? <CheckCircle2 size={17} aria-hidden="true" /> : <CircleAlert size={17} aria-hidden="true" />}<span><strong>{item.label}</strong><small>{item.detail}</small></span></div>)}
      </section>

      <div className="settings-layout">
        <nav className="settings-section-nav" aria-label="配置章节">
          {SECTION_LINKS.map(({ id, label, icon: Icon }) => <a href={`#${id}`} key={id}><Icon size={16} aria-hidden="true" />{label}</a>)}
        </nav>

        <div className="settings-console">
          <ConfigSection id="settings-llm" icon={MessageSquareText} title="生文模型" badge="LLM" description="LiteLLM 统一调用层，支持 OpenAI 或 Anthropic 兼容协议。">
            <Field label="协议类型" wide group><Segmented value={form.llm.protocol} onChange={value => updateSection('llm', 'protocol', value)} options={[['openai', 'OpenAI 兼容'], ['anthropic', 'Anthropic 兼容']]} /></Field>
            <Field label="API Base URL"><input value={form.llm.base_url} onChange={event => updateSection('llm', 'base_url', event.target.value)} placeholder="https://api.example.com/v1" /></Field>
            <Field label="API Key"><input type="password" autoComplete="off" value={form.llm.api_key} onChange={event => updateSection('llm', 'api_key', event.target.value)} placeholder="sk-..." /></Field>
            <ModelField type="llm" value={form.llm.model} options={modelOptions.llm} loading={modelLoading.llm} onChange={value => updateSection('llm', 'model', value)} onLoad={() => loadModels('llm')} />
          </ConfigSection>

          <ConfigSection id="settings-image" icon={Image} title="Agnes 生图" badge="Image" description="真实调用 Agnes Image 2.1 Flash 图片生成接口。">
            <Field label="API URL"><input value={form.image.api_url} onChange={event => updateSection('image', 'api_url', event.target.value)} placeholder="https://apihub.agnes-ai.com/v1/images/generations" /></Field>
            <Field label="API Key"><input type="password" autoComplete="off" value={form.image.api_key} onChange={event => updateSection('image', 'api_key', event.target.value)} placeholder="sk-..." /></Field>
            <ModelField type="image" value={form.image.model} options={modelOptions.image} loading={modelLoading.image} onChange={value => updateSection('image', 'model', value)} onLoad={() => loadModels('image')} />
            <Field label="图片尺寸"><select value={form.image.size} onChange={event => updateSection('image', 'size', event.target.value)}>{IMAGE_SIZES.map(size => <option value={size} key={size}>{size === 'auto' ? '自动匹配画幅' : size}</option>)}</select></Field>
          </ConfigSection>

          <ConfigSection id="settings-tts" icon={Volume2} title="配音模型" badge={form.tts.provider === 'mimo' ? 'MiMo TTS' : 'Doubao TTS'} description="任务创建和重配音统一使用所选 provider 的音色 ID。">
            <Field label="Provider" wide group><Segmented value={form.tts.provider} onChange={value => value === 'mimo' ? setForm(current => applyMimoPreset(current)) : updateTts('provider', 'doubao')} options={[['doubao', '豆包 TTS'], ['mimo', '小米 MiMo TTS']]} /></Field>
            {form.tts.provider === 'doubao' ? <DoubaoFields form={form} updateTts={updateTts} /> : <MimoFields form={form} updateMimo={updateMimo} />}
            <div className="settings-test-row">
              <button className="button button-secondary" type="button" disabled={testingTts} onClick={testTts}>{testingTts ? <LoaderCircle className="spin" size={16} aria-hidden="true" /> : <Volume2 size={16} aria-hidden="true" />}{testingTts ? '测试中...' : '测试配音配置'}</button>
              {ttsTestUrl ? <audio src={normalizeMediaUrl(ttsTestUrl)} controls aria-label="TTS 配置测试音频" /> : <span>测试成功后可在此试听返回音频。</span>}
            </div>
          </ConfigSection>

          <ConfigSection id="settings-runtime" icon={Cpu} title="生成并发" badge="Runtime" description="并发值会在保存前按后端约束归一化。">
            <Field label="配音并发" help="范围 1-8；调高更快，也更容易触发 provider 限流。"><input type="number" min="1" max="8" step="1" value={form.generation.tts_concurrency} onChange={event => updateSection('generation', 'tts_concurrency', event.target.value)} onBlur={() => updateSection('generation', 'tts_concurrency', normalizeConcurrency(form.generation.tts_concurrency))} /></Field>
            <Field label="生图并发" help="Agnes 免费限速下固定为 1。"><input type="number" value="1" min="1" max="1" disabled readOnly /></Field>
          </ConfigSection>
        </div>
      </div>

      <footer className="settings-actions"><button className="button button-secondary" type="button" disabled={saving} onClick={loadConfig}><RefreshCw size={16} aria-hidden="true" />重置</button><button className="button button-primary" type="button" disabled={saving} onClick={saveConfig}>{saving ? <LoaderCircle className="spin" size={16} aria-hidden="true" /> : <Save size={16} aria-hidden="true" />}{saving ? '保存中...' : '保存配置'}</button></footer>
    </main>
  )
}

function ConfigSection({ id, icon: Icon, title, badge, description, children }) {
  return <section className="settings-section" id={id}><header><span><Icon size={18} aria-hidden="true" /></span><div><h2>{title}</h2><p>{description}</p></div><strong>{badge}</strong></header><div className="settings-fields">{children}</div></section>
}

function Field({ label, help, wide = false, group = false, children }) {
  const Tag = group ? 'div' : 'label'
  return <Tag className={`settings-field${wide ? ' is-wide' : ''}`}><span>{label}</span>{children}{help && <small>{help}</small>}</Tag>
}

function Segmented({ value, options, onChange }) {
  return <span className="settings-segmented">{options.map(([key, label]) => <button type="button" className={value === key ? 'is-active' : ''} onClick={() => onChange(key)} key={key}>{label}</button>)}</span>
}

function ModelField({ type, value, options, loading, onChange, onLoad }) {
  return <Field label="Model" group><span className="settings-model-field"><input aria-label={`${type} 模型`} value={value} onChange={event => onChange(event.target.value)} placeholder={type === 'image' ? 'agnes-image-2.1-flash' : 'mimo-v2.5-pro'} /><button className="button button-secondary" type="button" disabled={loading} onClick={onLoad}>{loading ? <LoaderCircle className="spin" size={15} aria-hidden="true" /> : <RefreshCw size={15} aria-hidden="true" />}<span>{loading ? '获取中' : '获取列表'}</span></button></span>{options.length > 0 && <select aria-label={`${type} 模型列表`} value={value} onChange={event => onChange(event.target.value)}><option value="">请选择模型</option>{options.map(model => <option value={model.id} key={model.id}>{model.label}</option>)}</select>}</Field>
}

function DoubaoFields({ form, updateTts }) {
  return <>
    <Field label="豆包认证方式" wide group help="旧版在线合成使用 AppID / Access Token；火山新版语音接口也支持 API Key。"><Segmented value={form.tts.auth_method} onChange={value => updateTts('auth_method', value)} options={[['access_token', 'AppID / Access Token'], ['api_key', 'API Key']]} /></Field>
    <Field label="API URL"><input value={form.tts.api_url} onChange={event => updateTts('api_url', event.target.value)} placeholder="https://openspeech.bytedance.com/api/v1/tts" /></Field>
    {form.tts.auth_method === 'access_token' ? <><Field label="App ID"><input value={form.tts.appid} onChange={event => updateTts('appid', event.target.value)} placeholder="豆包 TTS App ID" /></Field><Field label="Access Token"><input type="password" autoComplete="off" value={form.tts.token} onChange={event => updateTts('token', event.target.value)} placeholder="豆包 Access Token" /></Field></> : <Field label="API Key"><input type="password" autoComplete="off" value={form.tts.api_key} onChange={event => updateTts('api_key', event.target.value)} placeholder="火山控制台 API Key" /></Field>}
    <Field label="Cluster" help="旧版在线合成通常为 volcano_tts。"><input value={form.tts.cluster} onChange={event => updateTts('cluster', event.target.value)} placeholder="volcano_tts" /></Field>
    <Field label="默认音色 ID"><input value={form.tts.default_voice} onChange={event => updateTts('default_voice', event.target.value)} placeholder="zh_male_jieshuoxiaoming_moon_bigtts" /></Field>
  </>
}

function MimoFields({ form, updateMimo }) {
  return <>
    <Field label="Base URL"><input value={form.tts.mimo.base_url} onChange={event => updateMimo('base_url', event.target.value)} placeholder="https://token-plan-sgp.xiaomimimo.com/v1" /></Field>
    <Field label="API Key"><input type="password" autoComplete="off" value={form.tts.mimo.api_key} onChange={event => updateMimo('api_key', event.target.value)} placeholder="小米 Token Plan API Key" /></Field>
    <Field label="Model"><input value={form.tts.mimo.model} onChange={event => updateMimo('model', event.target.value)} placeholder="mimo-v2.5-tts" /></Field>
    <Field label="默认音色"><select value={form.tts.mimo.default_voice} onChange={event => updateMimo('default_voice', event.target.value)}>{MIMO_VOICES.map(voice => <option value={voice.id} key={voice.id}>{voice.name}</option>)}</select></Field>
    <Field label="音频格式" help="音频从 chat/completions 返回的 message.audio.data 读取。"><input value={form.tts.mimo.format} onChange={event => updateMimo('format', event.target.value)} placeholder="wav" /></Field>
    <Field label="风格指令"><input value={form.tts.mimo.style_prompt} onChange={event => updateMimo('style_prompt', event.target.value)} placeholder="自然清晰，适合中文短视频旁白。" /></Field>
  </>
}
