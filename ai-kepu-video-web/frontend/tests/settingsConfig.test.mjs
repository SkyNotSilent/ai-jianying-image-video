import test from 'node:test'
import assert from 'node:assert/strict'

import {
  MIMO_PRESET,
  MIMO_VOICES,
  buildModelPayload,
  normalizeConfig,
  normalizeConcurrency,
  validateConfig,
} from '../src/lib/settingsConfig.js'

test('normalizes a partial config without dropping provider fields', () => {
  const config = normalizeConfig({
    llm: { protocol: 'anthropic', base_url: 'https://llm.test', api_key: 'llm-key', model: 'claude' },
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
    generation: { tts_concurrency: 99, image_concurrency: 5 },
  })

  assert.equal(config.llm.protocol, 'anthropic')
  assert.equal(config.tts.api_key, 'doubao-key')
  assert.equal(config.tts.mimo.api_key, 'mimo-key')
  assert.equal(config.tts.mimo.base_url, MIMO_PRESET.base_url)
  assert.equal(config.tts.mimo.default_voice, 'Mia')
  assert.deepEqual(config.tts.enabled_providers, ['doubao', 'mimo'])
  assert.equal(config.tts.speed_level, 'normal')
  assert.equal(config.tts.volume_ratio, 1)
  assert.equal(config.tts.mimo.speed_level, 'normal')
  assert.equal(config.tts.mimo.clone_model, 'mimo-v2.5-tts-voiceclone')
  assert.equal(config.generation.tts_concurrency, 8)
  assert.equal(config.generation.image_concurrency, 1)
})

test('clamps TTS concurrency to 1-8 and always fixes image concurrency to one', () => {
  assert.equal(normalizeConcurrency('0'), 1)
  assert.equal(normalizeConcurrency('4.8'), 4)
  assert.equal(normalizeConcurrency('12'), 8)
  assert.equal(normalizeConcurrency('bad'), 1)
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
      default_voice: 'zh_male_yangguangxiaolei_moon_bigtts',
    },
  })
  assert.equal(validateConfig(configured), '')

  const both = normalizeConfig({ ...configured, tts: { ...configured.tts, enabled_providers: ['doubao', 'mimo'] } })
  assert.equal(validateConfig(both), '请输入小米 MiMo API Key')
})
