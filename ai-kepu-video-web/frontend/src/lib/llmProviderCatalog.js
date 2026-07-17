const PROVIDER_GROUPS = [
  { key: 'recommended', label: '常用推荐' },
  { key: 'project', label: '项目扩展' },
  { key: 'all', label: '全部服务商' },
]

const TOP_LEVEL_CREDENTIAL_FIELDS = new Set(['api_key', 'base_url'])

function cloneProviderOptions(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return {}
  return { ...value }
}

function cloneLlm(llm = {}) {
  return {
    ...(llm || {}),
    provider_options: cloneProviderOptions(llm?.provider_options),
  }
}

function modelSources(value) {
  if (!Array.isArray(value)) return []
  return value.filter((source, index) => source && value.indexOf(source) === index)
}

function hasValue(value) {
  if (typeof value === 'string') return Boolean(value.trim())
  return value !== undefined && value !== null && value !== ''
}

export function normalizeProviders(payload = {}) {
  const providers = Array.isArray(payload?.providers) ? payload.providers : []
  return providers
    .filter(provider => provider && typeof provider === 'object' && String(provider.id || '').trim())
    .map(provider => ({
      ...provider,
      id: String(provider.id).trim(),
      name: String(provider.name || provider.id).trim(),
      group: PROVIDER_GROUPS.some(group => group.key === provider.group) ? provider.group : 'all',
      credential_fields: Array.isArray(provider.credential_fields)
        ? provider.credential_fields.map(field => ({ ...field }))
        : [],
      allowed_provider_options: Array.isArray(provider.allowed_provider_options)
        ? [...provider.allowed_provider_options]
        : [],
    }))
}

export function providerGroups(providers = [], query = '') {
  const normalizedQuery = String(query || '').trim().toLocaleLowerCase()
  const filtered = (Array.isArray(providers) ? providers : []).filter(provider => {
    if (!normalizedQuery) return true
    return [provider.id, provider.name].some(value => (
      String(value || '').toLocaleLowerCase().includes(normalizedQuery)
    ))
  })

  return PROVIDER_GROUPS.map(group => ({
    ...group,
    items: filtered.filter(provider => provider.group === group.key),
  })).filter(group => group.items.length)
}

export function mergeProviderModels(local = [], account = [], currentModel = '') {
  const merged = new Map()
  let insertionIndex = 0

  for (const model of Array.isArray(local) ? local : []) {
    const id = String(model?.id || '').trim()
    if (!id) continue
    merged.set(id, {
      ...model,
      id,
      label: String(model.label || '').trim(),
      sources: modelSources(model.sources),
      _index: insertionIndex++,
    })
  }

  for (const model of Array.isArray(account) ? account : []) {
    const id = String(model?.id || '').trim()
    if (!id) continue
    const existing = merged.get(id)
    if (!existing) {
      merged.set(id, {
        ...model,
        id,
        label: String(model.label || id).trim(),
        sources: modelSources(model.sources),
        _index: insertionIndex++,
      })
      continue
    }
    merged.set(id, {
      ...model,
      ...existing,
      label: existing.label || String(model.label || id).trim(),
      sources: modelSources([...existing.sources, ...modelSources(model.sources)]),
    })
  }

  const selectedModel = String(currentModel || '').trim()
  if (selectedModel && !merged.has(selectedModel)) {
    merged.set(selectedModel, {
      id: selectedModel,
      label: selectedModel,
      sources: [],
      current: true,
      historical: true,
      _index: insertionIndex++,
    })
  } else if (selectedModel) {
    merged.set(selectedModel, { ...merged.get(selectedModel), current: true })
  }

  const rank = model => {
    if (model.historical) return 3
    if (model.recommended || model.sources.includes('recommended')) return 0
    if (model.sources.includes('account')) return 1
    return 2
  }

  return [...merged.values()]
    .sort((left, right) => rank(left) - rank(right) || left._index - right._index)
    .map(({ _index, ...model }) => ({
      ...model,
      label: model.label || model.id,
      sources: [...model.sources],
    }))
}

export function applyProviderPreset(_currentLlm = {}, provider = {}) {
  return {
    provider: provider.id,
    protocol: provider.compatibility_protocol || 'openai',
    base_url: provider.default_base_url || '',
    api_key: '',
    model: provider.recommended_model || '',
    provider_options: {},
  }
}

export function switchProviderDraft(drafts = {}, currentLlm = {}, provider = {}) {
  const nextDrafts = Object.fromEntries(
    Object.entries(drafts || {}).map(([providerId, draft]) => [providerId, cloneLlm(draft)]),
  )
  const currentProvider = String(currentLlm?.provider || '').trim()
  if (currentProvider) nextDrafts[currentProvider] = cloneLlm(currentLlm)

  const restored = nextDrafts[provider.id]
  return {
    drafts: nextDrafts,
    llm: restored ? cloneLlm(restored) : applyProviderPreset(currentLlm, provider),
  }
}

export function buildProviderRefreshPayload(llm = {}, provider = {}) {
  const allowedOptionIds = new Set([
    ...(Array.isArray(provider.allowed_provider_options) ? provider.allowed_provider_options : []),
    ...(Array.isArray(provider.credential_fields)
      ? provider.credential_fields
        .map(field => field?.id)
        .filter(id => id && !TOP_LEVEL_CREDENTIAL_FIELDS.has(id))
      : []),
  ])
  const currentOptions = cloneProviderOptions(llm?.provider_options)
  const providerOptions = Object.fromEntries(
    Object.entries(currentOptions).filter(([id]) => allowedOptionIds.has(id)),
  )

  return {
    provider: provider.id || llm.provider || 'custom',
    protocol: llm.protocol || provider.compatibility_protocol || 'openai',
    base_url: llm.base_url || provider.default_base_url || '',
    api_key: llm.api_key || '',
    model: llm.model || '',
    provider_options: providerOptions,
  }
}

export function isLlmProviderReady(llm = {}, provider = {}) {
  const providerOptions = cloneProviderOptions(llm?.provider_options)
  const credentialFields = Array.isArray(provider?.credential_fields) ? provider.credential_fields : []

  return credentialFields.every(field => {
    if (field?.required === false) return true
    const fieldId = String(field?.id || '').trim()
    if (!fieldId) return true
    const value = TOP_LEVEL_CREDENTIAL_FIELDS.has(fieldId)
      ? llm?.[fieldId]
      : providerOptions[fieldId]
    return hasValue(value)
  })
}
