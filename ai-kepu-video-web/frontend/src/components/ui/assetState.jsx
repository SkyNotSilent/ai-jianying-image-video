import { AlertTriangle, Check, Clock3, RefreshCw, Sparkles } from 'lucide-react'

export const ASSET_STATES = Object.freeze({
  waiting: { label: '等待生成', tone: 'neutral', Icon: Clock3 },
  generating: { label: '正在生成', tone: 'info', Icon: Sparkles },
  complete: { label: '已完成', tone: 'success', Icon: Check },
  failed: { label: '生成失败', tone: 'danger', Icon: AlertTriangle },
  stale: { label: '待更新', tone: 'warning', Icon: RefreshCw },
})

export function getAssetState(status) {
  return ASSET_STATES[status] || ASSET_STATES.waiting
}

export function AssetStatus({ status }) {
  const state = getAssetState(status)
  const Icon = state.Icon

  return (
    <span className={`asset-status is-${state.tone}`} role="status" aria-label={state.label}>
      <Icon size={13} aria-hidden="true" />
      {state.label}
    </span>
  )
}
