import test from 'node:test'
import assert from 'node:assert/strict'

import {
  AGNES_PRESET,
  MIMO_PRESET,
  MIMO_VOICES,
  buildModelPayload,
  normalizeConfig,
  normalizeConcurrency,
  restoreAgnesPreset,
  restoreMimoTechnicalPreset,
  validateConfig,
} from '../src/lib/settingsConfig.js'

test('normalizes a partial config without dropping provider fields', () => {
  const config = normalizeConfig({
    llm: {
      provider: 'anthropic',
      protocol: 'anthropic',
      base_url: 'https://llm.test',
      api_key: 'llm-key',
      model: 'claude',
      provider_options: { api_version: '2025-01-01' },
    },
    image: { api_url: 'https://image.test', api_key: 'image-key', model: 'agnes', size: '1024x1024' },
    tts: {
      provider: 'mimo',
      auth_method: 'api_key',
      api_url: 'https://doubao.test',
      appid: 'app',
      token: 'token',
      api_key: 'doubao-key',
      cluster: 'cluster',
      default_voice: 'voice',
      mimo: { api_key: 'mimo-key', default_voice: 'Mia' },
    },
    generation: { prompt_concurrency: 7, tts_concurrency: 99, image_concurrency: 5 },
  })

  assert.equal(config.llm.provider, 'anthropic')
  assert.equal(config.llm.protocol, 'anthropic')
  assert.deepEqual(config.llm.provider_options, { api_version: '2025-01-01' })
  assert.equal(config.tts.api_key, 'doubao-key')
  assert.equal(config.tts.mimo.api_key, 'mimo-key')
  assert.equal(config.tts.mimo.base_url, MIMO_PRESET.base_url)
  assert.equal(config.tts.mimo.default_voice, 'Mia')
  assert.deepEqual(config.tts.enabled_providers, ['doubao', 'mimo'])
  assert.equal(config.tts.speed_level, 'normal')
  assert.equal(config.tts.volume_ratio, 1)
  assert.equal(config.tts.mimo.speed_level, 'normal')
  assert.equal(config.tts.mimo.clone_model, 'mimo-v2.5-tts-voiceclone')
  assert.equal(config.generation.prompt_concurrency, 7)
  assert.equal(config.generation.tts_concurrency, 8)
  assert.equal(config.generation.image_concurrency, 1)
})

test('normalizes missing or invalid LLM provider state to custom defaults', () => {
  assert.equal(normalizeConfig({}).llm.provider, 'custom')
  assert.deepEqual(normalizeConfig({ llm: { provider_options: [] } }).llm.provider_options, {})
})

test('normalizes prompt concurrency to four by default and clamps runtime concurrency', () => {
  assert.equal(normalizeConcurrency('0'), 1)
  assert.equal(normalizeConcurrency('4.8'), 4)
  assert.equal(normalizeConcurrency('12'), 8)
  assert.equal(normalizeConcurrency('bad'), 1)
  assert.equal(normalizeConfig({}).generation.prompt_concurrency, 4)
  assert.equal(normalizeConfig({ generation: { prompt_concurrency: 0 } }).generation.prompt_concurrency, 1)
  assert.equal(normalizeConfig({ generation: { prompt_concurrency: 12 } }).generation.prompt_concurrency, 8)
  assert.equal(normalizeConfig({ generation: { image_concurrency: 8 } }).generation.image_concurrency, 1)
  assert.equal(normalizeConfig(null).generation.image_concurrency, 1)
})

test('uses exact MiMo voice IDs', () => {
  assert.deepEqual(MIMO_VOICES.map(voice => voice.id), [
    'mimo_default', '冰糖', '茉莉', '苏打', '白桦', 'Mia', 'Chloe', 'Milo', 'Dean',
  ])
})

test('builds current model discovery payloads', () => {
  const config = normalizeConfig({
    llm: { protocol: 'anthropic', base_url: 'https://llm.test', api_key: 'llm-key' },
    image: { api_url: 'https://image.test', api_key: 'image-key' },
  })
  assert.deepEqual(buildModelPayload('llm', config), {
    protocol: 'anthropic', base_url: 'https://llm.test', api_key: 'llm-key',
  })
  assert.deepEqual(buildModelPayload('image', config), {
    protocol: 'openai', base_url: 'https://image.test', api_key: 'image-key',
  })
})

test('restores fixed Agnes endpoint and model without changing key or size', () => {
  const config = normalizeConfig({ image: {
    api_url: 'https://custom.test/images',
    api_key: 'keep-key',
    model: 'custom-image',
    size: '1024x1024',
  } })

  const restored = restoreAgnesPreset(config)

  assert.equal(restored.image.api_url, AGNES_PRESET.api_url)
  assert.equal(restored.image.model, AGNES_PRESET.model)
  assert.equal(restored.image.api_key, 'keep-key')
  assert.equal(restored.image.size, '1024x1024')
})

test('restores MiMo technical fields without changing credentials or voice', () => {
  const config = normalizeConfig({ tts: { mimo: {
    api_key: 'keep-key',
    default_voice: 'Mia',
    base_url: 'bad',
    model: 'bad',
    clone_model: 'bad-clone',
    format: 'mp3',
  } } })

  const restored = restoreMimoTechnicalPreset(config)

  assert.equal(restored.tts.mimo.api_key, 'keep-key')
  assert.equal(restored.tts.mimo.default_voice, 'Mia')
  assert.equal(restored.tts.mimo.model, MIMO_PRESET.model)
  assert.equal(restored.tts.mimo.clone_model, MIMO_PRESET.clone_model)
  assert.equal(restored.tts.mimo.format, MIMO_PRESET.format)
})

test('validates the selected TTS provider and auth method', () => {
  const base = normalizeConfig({
    llm: { base_url: 'https://llm.test', api_key: 'key', model: 'model' },
    image: { api_url: 'https://image.test', api_key: 'key', model: 'agnes' },
  })
  assert.equal(validateConfig(base), '请输入 TTS API URL')

  const mimo = normalizeConfig({ ...base, tts: { ...base.tts, provider: 'mimo' } })
  assert.equal(validateConfig(mimo), '请输入小米 MiMo API Key')
})

test('validates every enabled provider while allowing one side to be disabled', () => {
  const configured = normalizeConfig({
    llm: { base_url: 'https://llm.test', api_key: 'key', model: 'model' },
    image: { api_url: 'https://image.test', api_key: 'key', model: 'agnes' },
    tts: {
      provider: 'doubao',
      enabled_providers: ['doubao'],
      auth_method: 'api_key',
      api_url: 'https://doubao.test',
      api_key: 'doubao-key',
      cluster: 'volcano_tts',
      default_voice: 'zh_male_jieshuoxiaoming_moon_bigtts',
    },
  })
  assert.equal(validateConfig(configured), '')

  const both = normalizeConfig({ ...configured, tts: { ...configured.tts, enabled_providers: ['doubao', 'mimo'] } })
  assert.equal(validateConfig(both), '请输入小米 MiMo API Key')
})

test('uses provider metadata instead of requiring Base URL for native LLM providers', () => {
  const configured = normalizeConfig({
    llm: {
      provider: 'deepseek',
      base_url: '',
      api_key: 'deepseek-key',
      model: 'deepseek/deepseek-chat',
    },
    image: { api_url: 'https://image.test', api_key: 'key', model: 'agnes' },
    tts: {
      provider: 'doubao',
      enabled_providers: ['doubao'],
      auth_method: 'api_key',
      api_url: 'https://doubao.test',
      api_key: 'doubao-key',
      cluster: 'volcano_tts',
      default_voice: 'zh_male_jieshuoxiaoming_moon_bigtts',
    },
  })
  const deepseek = {
    id: 'deepseek',
    credential_fields: [{ id: 'api_key', label: 'API Key', required: true }],
  }

  assert.equal(validateConfig(configured, deepseek), '')
  assert.equal(validateConfig(configured), '请输入生文 Base URL')
  assert.equal(validateConfig(configured, { id: 'custom' }), '请输入生文 Base URL')
})
