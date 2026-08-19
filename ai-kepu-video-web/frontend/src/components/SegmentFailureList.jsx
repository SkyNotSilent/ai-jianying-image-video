import { CircleAlert, LoaderCircle, RefreshCw } from 'lucide-react'
import { getErrorPresentation } from '../lib/errorMessages'
import { segmentFailureTargets } from '../pages/workspaceGuidance'

export function SegmentFailureList({ segment, onRetryPrompt, busy = false }) {
  const failures = segmentFailureTargets(segment)
  if (!failures.length) return null
  return <div className="workspace-inline-errors" role="status">
    {failures.map(target => {
      const error = getErrorPresentation(target.errorSource)
      return <div className="workspace-inline-error" key={target.key}>
        <CircleAlert size={14} aria-hidden="true" />
        <span><strong>{target.assetLabel} · {error.title}</strong><small>{error.action}</small></span>
        {target.assetType === 'prompt' && onRetryPrompt ? <button type="button" className="workspace-inline-retry" disabled={busy} onClick={onRetryPrompt}>{busy ? <LoaderCircle className="spin" size={13} /> : <RefreshCw size={13} />}{busy ? '正在生成…' : '重新生成提示词'}</button> : null}
      </div>
    })}
  </div>
}
