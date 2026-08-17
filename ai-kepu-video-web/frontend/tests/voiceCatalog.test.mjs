import assert from 'node:assert/strict'
import test from 'node:test'

import {
  buildVoiceTaskPayload,
  groupVisibleVoices,
  hasUsableVoice,
  mergeTtsOptions,
  nextPreviewState,
  normalizeVoiceCatalog,
  reconcileTtsVoiceConfig,
  resolveEnabledVoiceDefaults,
} from '../src/lib/voiceCatalog.js'

const catalog = [
  { voice_id: '冰糖', name: '冰糖', provider: 'mimo', kind: 'preset', is_enabled: true, status: 'ready' },
  { voice_id: '茉莉', name: '茉莉', provider: 'mimo', kind: 'preset', is_enabled: false, status: 'ready' },
  { voice_id: 'clone-1', name: '我的声音', provider: 'mimo', kind: 'clone', is_enabled: true, status: 'ready' },
  { voice_id: 'clone-draft', name: '待试听', provider: 'mimo', kind: 'clone', is_enabled: false, status: 'draft' },
  { voice_id: 'zh_male_jieshuoxiaoming_moon_bigtts', name: '讲解小明', provider: 'doubao', kind: 'preset', is_enabled: true, status: 'ready' },
]

test('normalizes canonical IDs for presets and local clones', () => {
  const voices = normalizeVoiceCatalog(catalog)
  assert.deepEqual(voices.map(voice => voice.id), [
    'mimo:冰糖',
    'mimo:茉莉',
    'mimo-clone:clone-1',
    'mimo-clone:clone-draft',
    'doubao:zh_male_jieshuoxiaoming_moon_bigtts',
  ])
  assert.equal(voices[2].isClone, true)
})

test('groups every ready preset for task pickers while clones still require enablement', () => {
  const normalized = normalizeVoiceCatalog(catalog)
  const visible = groupVisibleVoices(normalized)
  assert.deepEqual(visible.map(group => group.provider), ['mimo', 'doubao'])
  assert.deepEqual(visible[0].voices.map(voice => voice.name), ['冰糖', '茉莉', '我的声音'])

  const settings = groupVisibleVoices(normalized, { includeUnavailable: true })
  assert.equal(settings[0].voices.length, 4)
  assert.equal(settings[0].voices.find(voice => voice.name === '待试听').selectable, false)
})

test('keeps disabled presets valid as defaults and repairs unknown defaults', () => {
  const resolved = resolveEnabledVoiceDefaults(catalog, {
    mimo: '冰糖',
    doubao: 'zh_missing_voice',
  }, 'mimo')

  assert.equal(resolved.defaults.mimo, 'mimo:冰糖')
  assert.equal(resolved.defaults.doubao, 'doubao:zh_male_jieshuoxiaoming_moon_bigtts')
  assert.equal(resolved.provider, 'mimo')
})

test('provider availability no longer depends on preset checkmarks', () => {
  const disabledPresets = catalog.map(voice => voice.kind === 'preset' ? { ...voice, is_enabled: false } : voice)
  const resolved = resolveEnabledVoiceDefaults(disabledPresets, { doubao: 'zh_male_jieshuoxiaoming_moon_bigtts' }, 'doubao')

  assert.equal(resolved.defaults.doubao, 'doubao:zh_male_jieshuoxiaoming_moon_bigtts')
  assert.equal(resolved.provider, 'doubao')
  assert.deepEqual(resolved.availableProviders, ['doubao', 'mimo'])
})

test('reconciles stale clone defaults and validates only enabled providers', () => {
  const config = reconcileTtsVoiceConfig({
    provider: 'mimo',
    enabled_providers: ['mimo'],
    default_voice: 'zh_male_jieshuoxiaoming_moon_bigtts',
    mimo: { default_voice: 'mimo-clone:missing-clone' },
  }, catalog)

  assert.equal(config.mimo.default_voice, '冰糖')
  assert.equal(config.provider, 'mimo')
  assert.equal(hasUsableVoice(catalog, config.enabled_providers), true)
  assert.equal(hasUsableVoice(catalog, ['missing-provider']), false)

  const disabledCatalog = catalog.map(voice => ({ ...voice, is_enabled: false }))
  const disabledConfig = reconcileTtsVoiceConfig(config, disabledCatalog)
  assert.deepEqual(disabledConfig.enabled_providers, ['mimo'])
  assert.equal(disabledConfig.default_voice, 'zh_male_jieshuoxiaoming_moon_bigtts')
  assert.equal(disabledConfig.mimo.default_voice, '冰糖')
  assert.equal(hasUsableVoice(disabledCatalog, disabledConfig.enabled_providers), true)
})

test('merges inherited options and emits only provider-relevant task fields', () => {
  assert.deepEqual(
    mergeTtsOptions(
      { speed_level: 'slow', volume_ratio: 1.2, style_prompt: '旧风格' },
      { speed_level: 'fast', style_prompt: '轻松' },
      'mimo',
    ),
    { speed_level: 'fast', style_prompt: '轻松' },
  )
  assert.deepEqual(
    buildVoiceTaskPayload(
      'doubao:zh_male_jieshuoxiaoming_moon_bigtts',
      { speed_level: 'very_fast', volume_ratio: 1.8, style_prompt: '忽略' },
    ),
    {
      voice_type: 'doubao:zh_male_jieshuoxiaoming_moon_bigtts',
      tts_options: { speed_level: 'very_fast', volume_ratio: 1.8 },
    },
  )
})

test('preview state keeps one active voice and ignores stale completions', () => {
  let state = nextPreviewState({}, { type: 'start', voiceId: 'mimo:冰糖', token: 1 })
  state = nextPreviewState(state, { type: 'start', voiceId: 'doubao:voice', token: 2 })
  assert.equal(state.playingVoice, 'doubao:voice')
  assert.equal(state.loading, true)

  state = nextPreviewState(state, { type: 'ready', voiceId: 'mimo:冰糖', token: 1, url: '/old.wav' })
  assert.equal(state.url, '')
  state = nextPreviewState(state, { type: 'ready', voiceId: 'doubao:voice', token: 2, url: '/new.wav' })
  assert.equal(state.url, '/new.wav')
  assert.equal(state.loading, false)
  assert.deepEqual(nextPreviewState(state, { type: 'stop' }), {
    playingVoice: '', token: 2, loading: false, url: '', error: '',
  })
})
