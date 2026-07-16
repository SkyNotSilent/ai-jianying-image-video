import { Check, CircleAlert, LoaderCircle, Pause, Play, Sparkles, Volume2 } from 'lucide-react'
import { groupVisibleVoices, mergeTtsOptions, normalizeVoiceCatalog } from '../lib/voiceCatalog'
import './voice-picker.css'

const SPEED_OPTIONS = [
  ['very_slow', '很慢'],
  ['slow', '偏慢'],
  ['normal', '正常'],
  ['fast', '偏快'],
  ['very_fast', '很快'],
]

export function VoicePicker({
  voices = [],
  value = '',
  ttsOptions = {},
  onChange,
  onOptionsChange,
  onPreview,
  playingVoice = '',
  previewLoading = false,
  previewError = '',
  showAdvanced = true,
  includeUnavailable = false,
  compact = false,
}) {
  const normalized = normalizeVoiceCatalog(voices)
  const groups = groupVisibleVoices(normalized, { includeUnavailable })
  const selected = normalized.find(voice => voice.id === value)
  const provider = selected?.provider || (String(value).startsWith('doubao:') ? 'doubao' : 'mimo')
  const options = mergeTtsOptions({}, ttsOptions, provider)

  const updateOptions = patch => {
    onOptionsChange?.(mergeTtsOptions(options, patch, provider))
  }

  if (!groups.length) {
    return <div className="voice-picker-empty"><Volume2 size={18} /><span>当前没有已开放的音色</span></div>
  }

  return <div className={`voice-picker${compact ? ' is-compact' : ''}`}>
    <div className="voice-picker-groups">
      {groups.map(group => <section className="voice-provider-group" key={group.provider}>
        <header><span>{group.label}</span><small>{group.voices.length} 个音色</small></header>
        <div className="voice-card-grid">
          {group.voices.map(voice => {
            const selectedVoice = voice.id === value
            const previewing = voice.id === playingVoice
            return <article className={`voice-card${selectedVoice ? ' is-selected' : ''}${voice.selectable ? '' : ' is-unavailable'}`} key={voice.id}>
              <button
                type="button"
                className="voice-card-select"
                disabled={!voice.selectable}
                aria-pressed={selectedVoice}
                onClick={() => onChange?.(voice.id, voice)}
              >
                <span className="voice-avatar" aria-hidden="true">{voice.kind === 'clone' ? <Sparkles size={16} /> : voice.name.slice(0, 1)}</span>
                <span className="voice-card-copy"><strong>{voice.name}</strong><small>{voice.kind === 'clone' ? '克隆音色' : voice.description || (voice.gender === 'male' ? '男声' : voice.gender === 'female' ? '女声' : '预置音色')}</small></span>
                {selectedVoice ? <span className="voice-selected-mark"><Check size={13} /></span> : null}
              </button>
              <button
                type="button"
                className="voice-preview-button"
                disabled={previewLoading && !previewing}
                aria-label={`${previewing ? '停止' : '试听'}${voice.name}`}
                onClick={() => onPreview?.(voice)}
              >
                {previewing && previewLoading ? <LoaderCircle className="spin" size={15} /> : previewing ? <Pause size={15} /> : <Play size={15} />}
                <span>{previewing ? '停止' : '试听'}</span>
              </button>
              {!voice.selectable ? <span className="voice-status-label">{voice.status === 'draft' ? '待试听' : voice.status === 'failed' ? '试听失败' : '未开放'}</span> : null}
            </article>
          })}
        </div>
      </section>)}
    </div>

    {previewError ? <p className="voice-preview-error" role="alert"><CircleAlert size={15} />{previewError}</p> : null}

    {showAdvanced && selected ? <section className="voice-advanced" aria-label="配音参数">
      <label><span>语速</span><select value={options.speed_level} onChange={event => updateOptions({ speed_level: event.target.value })}>{SPEED_OPTIONS.map(([key, label]) => <option value={key} key={key}>{label}</option>)}</select></label>
      {provider === 'doubao'
        ? <label><span>音量 <strong>{options.volume_ratio.toFixed(1)}x</strong></span><input type="range" min="0.5" max="2" step="0.1" value={options.volume_ratio} onChange={event => updateOptions({ volume_ratio: Number(event.target.value) })} /></label>
        : <label className="voice-style-field"><span>风格指令</span><input value={options.style_prompt} maxLength="300" placeholder="例如：轻松、有感情，适合短视频旁白" onChange={event => updateOptions({ style_prompt: event.target.value })} /></label>}
    </section> : null}
  </div>
}
