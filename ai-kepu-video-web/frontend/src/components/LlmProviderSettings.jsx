import { LoaderCircle, RefreshCw } from 'lucide-react'
import { ModelCombobox } from './ModelCombobox'
import { ProviderCombobox } from './ProviderCombobox'

const TOP_LEVEL_FIELDS = new Set(['api_key', 'base_url', 'model'])

export function LlmProviderSettings({
  value,
  providers = [],
  models = [],
  syncState = { status: 'idle', message: '' },
  onChange,
  onProviderChange,
  onSync,
}) {
  const llm = value || {}
  const provider = providers.find(item => item.id === llm.provider) || providers[0] || null
  const isCustom = provider?.id === 'custom'
  const credentialFields = (provider?.credential_fields || []).filter(field => (
    field.id !== 'model' && !(isCustom && field.id === 'base_url')
  ))

  const updateTopLevel = (field, nextValue) => {
    onChange?.({ ...llm, [field]: nextValue })
  }

  const updateCredential = (field, nextValue) => {
    if (TOP_LEVEL_FIELDS.has(field)) {
      updateTopLevel(field, nextValue)
      return
    }
    onChange?.({
      ...llm,
      provider_options: {
        ...(llm.provider_options || {}),
        [field]: nextValue,
      },
    })
  }

  const credentialValue = field => (
    TOP_LEVEL_FIELDS.has(field)
      ? llm[field] || ''
      : llm.provider_options?.[field] || ''
  )

  return (
    <div className="settings-llm-provider">
      <label className="settings-field is-wide">
        <span>服务商</span>
        <ProviderCombobox
          value={llm.provider || ''}
          providers={providers}
          onChange={onProviderChange}
        />
        <small>按名称或 LiteLLM Provider ID 搜索；切换后会保留本页未保存的服务商草稿。</small>
      </label>

      {credentialFields.length ? (
        <div className="settings-provider-credentials">
          {credentialFields.map(field => (
            <label className="settings-field" key={field.id}>
              <span>{field.label || field.id}{field.required === false ? '（可选）' : ''}</span>
              <input
                type={field.secret ? 'password' : 'text'}
                autoComplete={field.secret ? 'new-password' : 'off'}
                value={credentialValue(field.id)}
                onChange={event => updateCredential(field.id, event.target.value)}
              />
            </label>
          ))}
        </div>
      ) : null}

      <label className="settings-field is-wide">
        <span>Model</span>
        <ModelCombobox
          value={llm.model || ''}
          models={models}
          onChange={model => updateTopLevel('model', model)}
        />
        <small>搜索文字只用于筛选；必须从结果中选择模型。历史配置会继续保留。</small>
      </label>

      {provider?.supports_live_models ? (
        <div className="settings-provider-sync">
          <button
            className="button button-secondary"
            type="button"
            disabled={syncState.status === 'loading'}
            onClick={onSync}
          >
            {syncState.status === 'loading'
              ? <LoaderCircle className="spin" size={15} aria-hidden="true" />
              : <RefreshCw size={15} aria-hidden="true" />}
            {syncState.status === 'loading' ? '同步中...' : '验证并同步'}
          </button>
          <span>使用当前未保存的连接信息验证账号模型。</span>
        </div>
      ) : null}

      {syncState.message ? (
        <p
          className={`settings-sync-status is-${syncState.status}`}
          role={syncState.status === 'error' ? 'alert' : 'status'}
          aria-live="polite"
        >
          {syncState.message}
        </p>
      ) : null}

      <details className="settings-advanced">
        <summary>高级配置</summary>
        <div className="settings-advanced-grid">
          <label><span>Provider ID</span><code>{provider?.id || llm.provider || '—'}</code></label>
          <label><span>连接方式</span><code>{provider?.connection_mode || '—'}</code></label>
          {isCustom ? (
            <>
              <label>
                <span>Protocol</span>
                <select value={llm.protocol || 'openai'} onChange={event => updateTopLevel('protocol', event.target.value)}>
                  <option value="openai">OpenAI 兼容</option>
                  <option value="anthropic">Anthropic 兼容</option>
                </select>
              </label>
              <label>
                <span>Base URL</span>
                <input value={llm.base_url || ''} onChange={event => updateTopLevel('base_url', event.target.value)} placeholder="https://api.example.com/v1" />
              </label>
              <label className="is-wide">
                <span>Model</span>
                <input value={llm.model || ''} onChange={event => updateTopLevel('model', event.target.value)} placeholder="provider/model-or-deployment" />
              </label>
            </>
          ) : (
            <>
              <label><span>Protocol</span><code>{llm.protocol || provider?.compatibility_protocol || '—'}</code></label>
              <label><span>Base URL</span><code>{llm.base_url || provider?.default_base_url || '—'}</code></label>
            </>
          )}
        </div>
      </details>
    </div>
  )
}
