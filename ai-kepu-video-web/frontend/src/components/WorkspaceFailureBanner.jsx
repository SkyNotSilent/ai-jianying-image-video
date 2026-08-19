import { useState } from 'react'
import { AlertTriangle, ChevronDown, ChevronUp, LoaderCircle, RefreshCw } from 'lucide-react'
import { getErrorPresentation } from '../lib/errorMessages'
import { partitionWorkspaceFailures } from '../pages/workspaceGuidance'
import { Tooltip } from './ui/Tooltip'

export function WorkspaceFailureBanner({ issues, busy = false, onRetryAll, onRetryPrompt, onSelect }) {
  const [expanded, setExpanded] = useState(false)
  if (!issues?.failureCount) return null
  const retryable = partitionWorkspaceFailures(issues)
  const assetFailureCount = retryable.assets.length

  return <section className="workspace-failure-banner" role="alert" aria-live="polite">
    <div className="workspace-failure-summary">
      <AlertTriangle size={18} aria-hidden="true" />
      <div>
        <strong key={`${issues.failureCount}:${issues.failedSegmentCount}`} className="workspace-failure-count">{issues.failureCount} 个问题，涉及 {issues.failedSegmentCount} 段分镜</strong>
        <span>图片 {issues.counts.image} · 配音 {issues.counts.audio} · 提示词 {issues.counts.prompt}；待更新素材不计入失败</span>
      </div>
      <button type="button" className="workspace-failure-toggle" onClick={() => setExpanded(value => !value)} aria-expanded={expanded}>
        {expanded ? <ChevronUp size={15} /> : <ChevronDown size={15} />}{expanded ? '收起清单' : '展开清单'}
      </button>
      {assetFailureCount ? <Tooltip label="仅重试当前失败或缺失的图片与配音；提示词请逐段重新生成，待更新素材不包含在内" placement="bottom"><button type="button" className="workspace-failure-retry" disabled={busy} onClick={onRetryAll}>
        {busy ? <LoaderCircle className="spin" size={15} /> : <RefreshCw size={15} />}{busy ? '正在重试…' : `重试 ${assetFailureCount} 个失败素材`}
      </button></Tooltip> : null}
    </div>
    {expanded ? <ul>
      {issues.failures.map(target => {
        const error = getErrorPresentation(target.errorSource)
        return <li key={target.key}>
          <button type="button" className="workspace-failure-target" onClick={() => onSelect(target.segmentIndex)}>
            <span>分镜 {target.segmentIndex + 1} · {target.assetLabel}</span>
            <strong>{error.title}</strong>
            <small>{error.action}</small>
          </button>
          {target.assetType === 'prompt' && onRetryPrompt ? <button type="button" className="workspace-failure-prompt-retry" disabled={busy} onClick={() => onRetryPrompt(target.segmentIndex)}>{busy ? <LoaderCircle className="spin" size={13} /> : <RefreshCw size={13} />}{busy ? '正在生成…' : '重生这段提示词'}</button> : null}
        </li>
      })}
    </ul> : null}
  </section>
}
