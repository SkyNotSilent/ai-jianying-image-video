import { isLlmProviderReady } from './llmProviderCatalog.js'

export const AGNES_PRESET = {
  api_url: 'https://apihub.agnes-ai.com/v1/images/generations',
  model: 'agnes-image-2.1-flash',
}

export const MIMO_PRESET = {
  base_url: 'https://token-plan-sgp.xiaomimimo.com/v1',
  model: 'mimo-v2.5-tts',
  clone_model: 'mimo-v2.5-tts-voiceclone',
  default_voice: '冰糖',
  format: 'wav',
  style_prompt: '自然清晰，适合中文短视频旁白。',
  speed_level: 'normal',
}

export const MIMO_VOICES = [
  { id: 'mimo_default', name: 'MiMo 默认' },
  { id: '冰糖', name: '冰糖 · 女声' },
  { id: '茉莉', name: '茉莉 · 女声' },
  { id: '苏打', name: '苏打 · 男声' },
  { id: '白桦', name: '白桦 · 男声' },
  { id: 'Mia', name: 'Mia · English Female' },
  { id: 'Chloe', name: 'Chloe · English Female' },
  { id: 'Milo', name: 'Milo · English Male' },
  { id: 'Dean', name: 'Dean · English Male' },
]

export function normalizeConcurrency(value, fallback = 1) {
  const parsed = Number.parseInt(value, 10)
  if (!Number.isFinite(parsed)) return fallback
  return Math.min(8, Math.max(1, parsed))
}

export function normalizeRetryCount(value, fallback = 2) {
  const parsed = Number.parseInt(value, 10)
  if (!Number.isFinite(parsed)) return fallback
  return Math.min(5, Math.max(0, parsed))
}

export function normalizeMimoConfig(config = {}) {
  return {
    ...MIMO_PRESET,
    api_key: '',
    ...(config || {}),
  }
}

function normalizeEnabledProviders(value) {
  if (!Array.isArray(value)) return ['doubao', 'mimo']
  const providers = value.filter((provider, index) => (
    ['doubao', 'mimo'].includes(provider) && value.indexOf(provider) === index
  ))
  return providers.length ? providers : ['doubao', 'mimo']
}

function normalizeSpeedLevel(value) {
  return ['very_slow', 'slow', 'normal', 'fast', 'very_fast'].includes(value) ? value : 'normal'
}

export function normalizeConfig(config = {}) {
  const source = config || {}
  const llmProvider = typeof source.llm?.provider === 'string' && source.llm.provider.trim()
    ? source.llm.provider.trim()
    : 'custom'
  const llmProviderOptions = source.llm?.provider_options
    && typeof source.llm.provider_options === 'object'
    && !Array.isArray(source.llm.provider_options)
    ? { ...source.llm.provider_options }
    : {}
  const enabledProviders = normalizeEnabledProviders(source.tts?.enabled_providers)
  const requestedProvider = source.tts?.provider === 'mimo' ? 'mimo' : 'doubao'
  const provider = enabledProviders.includes(requestedProvider) ? requestedProvider : enabledProviders[0]
  const parsedVolume = Number(source.tts?.volume_ratio)
  return {
    ...source,
    llm: {
      ...(source.llm || {}),
      provider: llmProvider,
      base_url: source.llm?.base_url || '',
      api_key: source.llm?.api_key || '',
      model: source.llm?.model || '',
      protocol: source.llm?.protocol === 'anthropic' ? 'anthropic' : 'openai',
      provider_options: llmProviderOptions,
    },
    image: {
      ...(source.image || {}),
      api_url: source.image?.api_url || '',
      api_key: source.image?.api_key || '',
      model: source.image?.model || '',
      size: source.image?.size || 'auto',
    },
    tts: {
      ...(source.tts || {}),
      provider,
      enabled_providers: enabledProviders,
      preview_text: '欢迎来到 InsightCut，让我们一起把灵感变成精彩视频。',
      auth_method: source.tts?.auth_method === 'api_key' ? 'api_key' : 'access_token',
      api_url: source.tts?.api_url || '',
      appid: source.tts?.appid || '',
      token: source.tts?.token || '',
      api_key: source.tts?.api_key || '',
      cluster: source.tts?.cluster || 'volcano_tts',
      default_voice: source.tts?.default_voice || 'zh_male_jieshuoxiaoming_moon_bigtts',
      speed_level: normalizeSpeedLevel(source.tts?.speed_level),
      volume_ratio: Number.isFinite(parsedVolume) ? Math.min(2, Math.max(.5, parsedVolume)) : 1,
      mimo: {
        ...normalizeMimoConfig(source.tts?.mimo),
        speed_level: normalizeSpeedLevel(source.tts?.mimo?.speed_level),
      },
    },
    generation: {
      ...(source.generation || {}),
      prompt_concurrency: normalizeConcurrency(source.generation?.prompt_concurrency, 4),
      tts_concurrency: normalizeConcurrency(source.generation?.tts_concurrency),
      image_concurrency: normalizeConcurrency(source.generation?.image_concurrency, 8),
      retry_count: normalizeRetryCount(source.generation?.retry_count),
    },
  }
}

export function restoreAgnesPreset(config) {
  return {
    ...config,
    image: {
      ...config.image,
      ...AGNES_PRESET,
    },
  }
}

export function restoreMimoTechnicalPreset(config) {
  return {
    ...config,
    tts: {
      ...config.tts,
      mimo: {
        ...config.tts?.mimo,
        base_url: MIMO_PRESET.base_url,
        model: MIMO_PRESET.model,
        clone_model: MIMO_PRESET.clone_model,
        format: MIMO_PRESET.format,
      },
    },
  }
}

export function buildModelPayload(type, config) {
  if (type === 'image') {
    return {
      protocol: 'openai',
      base_url: config.image.api_url,
      api_key: config.image.api_key,
    }
  }
  return {
    protocol: config.llm.protocol || 'openai',
    base_url: config.llm.base_url,
    api_key: config.llm.api_key,
  }
}

export function validateConfig(config, llmProvider = null) {
  const usesProviderMetadata = llmProvider?.id && llmProvider.id !== 'custom'
  if (usesProviderMetadata) {
    if (!isLlmProviderReady(config.llm, llmProvider)) {
      const providerOptions = config.llm.provider_options || {}
      const missingField = (llmProvider.credential_fields || []).find(field => {
        if (field?.required === false) return false
        const value = ['api_key', 'base_url'].includes(field?.id)
          ? config.llm[field.id]
          : providerOptions[field?.id]
        return typeof value === 'string' ? !value.trim() : !value
      })
      return missingField?.label
        ? `请输入生文 ${missingField.label}`
        : '请补齐生文服务商必填凭证'
    }
  } else {
    if (!config.llm.base_url.trim()) return '请输入生文 Base URL'
    if (!config.llm.api_key.trim()) return '请输入生文 API Key'
  }
  if (!config.llm.model.trim()) return '请输入生文模型'
  if (!config.image.api_url.trim()) return '请输入生图 API URL'
  if (!config.image.api_key.trim()) return '请输入生图 API Key'
  if (!config.image.model.trim()) return '请输入生图模型'

  const validateMimo = () => {
    if (!config.tts.mimo.base_url.trim()) return '请输入小米 MiMo Base URL'
    if (!config.tts.mimo.api_key.trim()) return '请输入小米 MiMo API Key'
    if (!config.tts.mimo.model.trim()) return '请输入小米 MiMo TTS 模型'
    if (!config.tts.mimo.clone_model.trim()) return '请输入小米 MiMo 声音克隆模型'
    if (!config.tts.mimo.default_voice.trim()) return '请选择小米默认音色'
    if (!config.tts.mimo.format.trim()) return '请输入小米音频格式'
    return ''
  }

  const validateDoubao = () => {
    if (!config.tts.api_url.trim()) return '请输入 TTS API URL'
    if (config.tts.auth_method === 'api_key') {
      if (!config.tts.api_key.trim()) return '请输入豆包 API Key'
    } else {
      if (!config.tts.appid.trim()) return '请输入 TTS App ID'
      if (!config.tts.token.trim()) return '请输入豆包 Access Token'
    }
    if (!config.tts.cluster.trim()) return '请输入 TTS Cluster'
    if (!config.tts.default_voice.trim()) return '请输入默认音色'
    return ''
  }

  const enabled = normalizeEnabledProviders(config.tts.enabled_providers)
  const validationOrder = [config.tts.provider, ...enabled.filter(provider => provider !== config.tts.provider)]
  for (const provider of validationOrder) {
    if (!enabled.includes(provider)) continue
    const issue = provider === 'mimo' ? validateMimo() : validateDoubao()
    if (issue) return issue
  }
  return ''
}

export function validateTtsTest(config) {
  if (config.tts.provider === 'mimo') {
    if (!config.tts.mimo.base_url.trim() || !config.tts.mimo.api_key.trim() || !config.tts.mimo.model.trim()) {
      return '请先补齐小米 MiMo TTS 配置'
    }
    return ''
  }
  if (config.tts.auth_method === 'api_key') {
    if (!config.tts.api_url.trim() || !config.tts.api_key.trim() || !config.tts.default_voice.trim()) {
      return '请先补齐豆包 API Key、API URL 和默认音色'
    }
    return ''
  }
  if (!config.tts.api_url.trim() || !config.tts.appid.trim() || !config.tts.token.trim() || !config.tts.default_voice.trim()) {
    return '请先补齐豆包 AppID、Access Token、API URL 和默认音色'
  }
  return ''
}

export function applyMimoPreset(config) {
  const current = config.tts.mimo || {}
  return {
    ...config,
    tts: {
      ...config.tts,
      provider: 'mimo',
      mimo: {
        ...MIMO_PRESET,
        ...current,
        api_key: current.api_key || config.llm.api_key || '',
        base_url: current.base_url || MIMO_PRESET.base_url,
        model: current.model || MIMO_PRESET.model,
        default_voice: current.default_voice || MIMO_PRESET.default_voice,
        format: current.format || MIMO_PRESET.format,
        style_prompt: current.style_prompt || MIMO_PRESET.style_prompt,
      },
    },
  }
}
