const SPEED_LEVELS = new Set(['very_slow', 'slow', 'normal', 'fast', 'very_fast'])

function canonicalVoiceId(voice = {}) {
  const current = String(voice.id || '').trim()
  if (current.startsWith('mimo:') || current.startsWith('doubao:') || current.startsWith('mimo-clone:')) {
    return current
  }
  const provider = voice.provider === 'doubao' ? 'doubao' : 'mimo'
  const voiceId = String(voice.voice_id || current).trim()
  if (!voiceId) return ''
  return voice.kind === 'clone' ? `mimo-clone:${voiceId}` : `${provider}:${voiceId}`
}

export function normalizeVoiceCatalog(input) {
  if (!Array.isArray(input)) return []
  return input.map((voice, index) => {
    const provider = voice?.provider === 'doubao' ? 'doubao' : 'mimo'
    const kind = voice?.kind === 'clone' ? 'clone' : 'preset'
    const id = canonicalVoiceId({ ...voice, provider, kind })
    const status = voice?.status || 'ready'
    const isEnabled = Boolean(voice?.is_enabled)
    return {
      ...(voice || {}),
      id,
      voice_id: String(voice?.voice_id || id.split(':').slice(1).join(':') || ''),
      name: String(voice?.name || voice?.voice_id || `音色 ${index + 1}`),
      provider,
      kind,
      status,
      is_enabled: isEnabled,
      isClone: kind === 'clone',
      selectable: isEnabled && status === 'ready',
      preview_url: voice?.preview_url || '',
    }
  }).filter(voice => voice.id)
}

export function groupVisibleVoices(voices, { includeUnavailable = false } = {}) {
  const source = normalizeVoiceCatalog(voices)
  return ['mimo', 'doubao'].map(provider => ({
    provider,
    label: provider === 'mimo' ? '小米 MiMo' : '豆包 TTS',
    voices: source.filter(voice => (
      voice.provider === provider && (includeUnavailable || voice.selectable)
    )),
  })).filter(group => group.voices.length)
}

export function mergeTtsOptions(base = {}, override = {}, provider = 'mimo') {
  const merged = { ...(base || {}), ...(override || {}) }
  const speedLevel = SPEED_LEVELS.has(merged.speed_level) ? merged.speed_level : 'normal'
  if (provider === 'doubao') {
    const parsedVolume = Number(merged.volume_ratio)
    return {
      speed_level: speedLevel,
      volume_ratio: Number.isFinite(parsedVolume)
        ? Math.min(2, Math.max(0.5, parsedVolume))
        : 1,
    }
  }
  return {
    speed_level: speedLevel,
    style_prompt: String(merged.style_prompt || '').trim().slice(0, 300),
  }
}

export function buildVoiceTaskPayload(voiceType, options = {}, inherited = {}) {
  const id = canonicalVoiceId({
    id: voiceType,
    provider: String(voiceType || '').startsWith('doubao:') ? 'doubao' : 'mimo',
    kind: String(voiceType || '').startsWith('mimo-clone:') ? 'clone' : 'preset',
  })
  if (!id) return { voice_type: null, tts_options: {} }
  const provider = id.startsWith('doubao:') ? 'doubao' : 'mimo'
  return {
    voice_type: id,
    tts_options: mergeTtsOptions(inherited, options, provider),
  }
}

export function nextPreviewState(state = {}, action = {}) {
  const current = {
    playingVoice: state.playingVoice || '',
    token: state.token || 0,
    loading: Boolean(state.loading),
    url: state.url || '',
    error: state.error || '',
  }
  if (action.type === 'stop') {
    return { playingVoice: '', token: current.token, loading: false, url: '', error: '' }
  }
  if (action.type === 'start') {
    return {
      playingVoice: action.voiceId || '',
      token: action.token || current.token + 1,
      loading: true,
      url: '',
      error: '',
    }
  }
  if (action.token !== current.token || action.voiceId !== current.playingVoice) return current
  if (action.type === 'ready') return { ...current, loading: false, url: action.url || '' }
  if (action.type === 'error') return { ...current, loading: false, url: '', error: action.error || '试听失败' }
  return current
}
