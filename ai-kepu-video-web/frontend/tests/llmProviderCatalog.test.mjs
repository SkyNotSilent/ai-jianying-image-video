import test from 'node:test'
import assert from 'node:assert/strict'

import {
  applyProviderPreset,
  buildProviderRefreshPayload,
  isLlmProviderReady,
  mergeProviderModels,
  normalizeProviders,
  providerGroups,
  switchProviderDraft,
} from '../src/lib/llmProviderCatalog.js'

test('groups and searches recommended, project, and complete providers', () => {
  const providers = normalizeProviders({ providers: [
    { id: 'deepseek', name: 'DeepSeek', group: 'recommended' },
    { id: 'mimo', name: '小米 MiMo', group: 'project' },
    { id: 'bedrock', name: 'Amazon Bedrock', group: 'all' },
  ] })

  assert.deepEqual(providerGroups(providers, '').map(group => group.key), ['recommended', 'project', 'all'])
  assert.deepEqual(providerGroups(providers, 'mimo')[0].items.map(item => item.id), ['mimo'])
  assert.deepEqual(providerGroups(providers, 'BEDROCK')[0].items.map(item => item.id), ['bedrock'])
})

test('merges catalog, account, and current models without losing history', () => {
  const models = mergeProviderModels(
    [{ id: 'deepseek/deepseek-chat', label: 'DeepSeek Chat', sources: ['catalog'] }],
    [{ id: 'deepseek/deepseek-chat', label: 'chat', sources: ['account'] }],
    'deepseek/legacy-model',
  )

  assert.deepEqual(models.map(model => model.id), [
    'deepseek/deepseek-chat', 'deepseek/legacy-model',
  ])
  assert.equal(models[0].label, 'DeepSeek Chat')
  assert.deepEqual(models[0].sources.toSorted(), ['account', 'catalog'])
  assert.equal(models[1].historical, true)
})

test('orders models as recommended, account, catalog, then historical', () => {
  const models = mergeProviderModels(
    [
      { id: 'catalog', label: 'Catalog', sources: ['catalog'] },
      { id: 'recommended', label: 'Recommended', sources: ['catalog'], recommended: true },
    ],
    [{ id: 'account', label: 'Account', sources: ['account'] }],
    'legacy',
  )

  assert.deepEqual(models.map(model => model.id), ['recommended', 'account', 'catalog', 'legacy'])
})

test('switching providers caches unsaved drafts and applies a first-use preset', () => {
  const current = { provider: 'mimo', api_key: 'mimo-key', model: 'openai/mimo-v2.5-pro' }
  const deepseek = {
    id: 'deepseek',
    default_base_url: 'https://api.deepseek.com',
    recommended_model: 'deepseek/deepseek-chat',
    compatibility_protocol: 'openai',
  }
  const result = switchProviderDraft({}, current, deepseek)

  assert.equal(result.drafts.mimo.api_key, 'mimo-key')
  assert.equal(result.llm.provider, 'deepseek')
  assert.equal(result.llm.api_key, '')
  assert.equal(result.llm.model, 'deepseek/deepseek-chat')
})

test('restores only the selected provider draft without leaking provider options', () => {
  const drafts = {
    deepseek: {
      provider: 'deepseek',
      protocol: 'openai',
      base_url: 'https://api.deepseek.com',
      api_key: 'deepseek-key',
      model: 'deepseek/deepseek-chat',
      provider_options: { api_version: 'deepseek-only' },
    },
  }
  const current = {
    provider: 'bedrock',
    model: 'bedrock/claude',
    provider_options: { aws_region_name: 'us-east-1' },
  }
  const deepseek = { id: 'deepseek', recommended_model: 'deepseek/deepseek-chat' }
  const mimo = { id: 'mimo', recommended_model: 'openai/mimo-v2.5-pro' }

  const restored = switchProviderDraft(drafts, current, deepseek)
  assert.deepEqual(restored.llm.provider_options, { api_version: 'deepseek-only' })
  assert.deepEqual(restored.drafts.bedrock.provider_options, { aws_region_name: 'us-east-1' })

  const firstUse = switchProviderDraft(restored.drafts, restored.llm, mimo)
  assert.deepEqual(firstUse.llm.provider_options, {})
  assert.equal(drafts.bedrock, undefined)
})

test('applies a provider preset as a fresh isolated LLM config', () => {
  const preset = applyProviderPreset(
    { provider: 'bedrock', api_key: 'secret', provider_options: { aws_region_name: 'us-east-1' } },
    {
      id: 'anthropic',
      compatibility_protocol: 'anthropic',
      default_base_url: 'https://api.anthropic.com',
      recommended_model: 'anthropic/claude-sonnet-4-5',
    },
  )

  assert.deepEqual(preset, {
    provider: 'anthropic',
    protocol: 'anthropic',
    base_url: 'https://api.anthropic.com',
    api_key: '',
    model: 'anthropic/claude-sonnet-4-5',
    provider_options: {},
  })
})

test('builds a provider refresh payload from the unsaved draft and allowed options', () => {
  const payload = buildProviderRefreshPayload({
    provider: 'azure',
    protocol: '',
    base_url: '',
    api_key: 'azure-key',
    model: 'azure/deployment',
    provider_options: { api_version: '2025-01-01', unrelated: 'drop-me' },
  }, {
    id: 'azure',
    compatibility_protocol: 'openai',
    default_base_url: 'https://azure.test',
    credential_fields: [
      { id: 'api_key', required: true },
      { id: 'api_version', required: true },
    ],
  })

  assert.deepEqual(payload, {
    provider: 'azure',
    protocol: 'openai',
    base_url: 'https://azure.test',
    api_key: 'azure-key',
    model: 'azure/deployment',
    provider_options: { api_version: '2025-01-01' },
  })
})

test('checks registry credential fields across top-level and provider options', () => {
  const provider = {
    credential_fields: [
      { id: 'api_key', required: true },
      { id: 'base_url', required: true },
      { id: 'aws_region_name', required: true },
      { id: 'profile', required: false },
    ],
  }
  const ready = {
    api_key: 'key',
    base_url: 'https://provider.test',
    provider_options: { aws_region_name: 'us-east-1' },
  }

  assert.equal(isLlmProviderReady(ready, provider), true)
  assert.equal(isLlmProviderReady({ ...ready, provider_options: {} }, provider), false)
})
