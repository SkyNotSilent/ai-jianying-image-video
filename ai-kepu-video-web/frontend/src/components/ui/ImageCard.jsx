import { AlertTriangle, Eye, Image as ImageIcon, RefreshCw, RotateCcw } from 'lucide-react'
import { useEffect, useState } from 'react'
import { getErrorPresentation } from '../../lib/errorMessages'
import { AssetStatus } from './assetState'
import './asset-components.css'

function primaryAction(status, callbacks) {
  if (status === 'failed' && callbacks.onRetry) {
    return { label: '重试图片', Icon: RotateCcw, onClick: callbacks.onRetry }
  }
  if (status === 'stale' && (callbacks.onUpdate || callbacks.onRegenerate)) {
    return { label: '更新图片', Icon: RefreshCw, onClick: callbacks.onUpdate || callbacks.onRegenerate }
  }
  if (status === 'complete' && callbacks.onRegenerate) {
    return { label: '重新生成', Icon: RefreshCw, onClick: callbacks.onRegenerate }
  }
  return null
}

/**
 * A provider-agnostic image asset surface. The parent owns every mutation.
 */
export function ImageCard({
  status = 'waiting',
  ratio = '16 / 9',
  src = '',
  alt = '',
  title = '画面素材',
  eyebrow,
  meta,
  error,
  onOpen,
  onRetry,
  onRegenerate,
  onUpdate,
  actions,
  className = '',
}) {
  const [elapsedSeconds, setElapsedSeconds] = useState(0)
  const presentation = status === 'failed' ? getErrorPresentation(error) : null
  const action = primaryAction(status, { onRetry, onRegenerate, onUpdate })
  const ActionIcon = action?.Icon
  const canOpen = Boolean(src && onOpen)

  useEffect(() => {
    if (status !== 'generating') {
      setElapsedSeconds(0)
      return undefined
    }
    const startedAt = Date.now()
    const timer = window.setInterval(() => setElapsedSeconds(Math.floor((Date.now() - startedAt) / 1000)), 1000)
    return () => window.clearInterval(timer)
  }, [status])

  return (
    <article className={`asset-card image-asset-card is-${status}${className ? ` ${className}` : ''}`}>
      <div className="asset-card-media" style={{ aspectRatio: ratio }}>
        {status === 'failed' ? (
          <div className="image-asset-failure" role="alert">
            <AlertTriangle size={24} aria-hidden="true" />
            <strong>{presentation?.title || '图片生成未完成'}</strong>
            <span>{presentation?.action || '请检查配置后重试当前图片。'}</span>
            {action ? (
              <button type="button" className="asset-text-action" onClick={action.onClick}>
                <ActionIcon size={14} aria-hidden="true" />
                {action.label}
              </button>
            ) : null}
          </div>
        ) : src ? (
          <img className="asset-card-image" src={src} alt={alt} loading="lazy" />
        ) : (
          <div className="asset-card-placeholder" aria-hidden="true">
            <ImageIcon size={28} />
            <span />
          </div>
        )}

        {status === 'generating' ? <><span className="asset-card-scan" aria-hidden="true" /><span className="asset-generating-elapsed">已用时 {elapsedSeconds} 秒</span></> : null}
        {status === 'stale' ? <span className="asset-card-stale-ribbon">待更新</span> : null}

        {(canOpen || (action && status !== 'failed') || actions) ? (
          <div className="asset-card-operation-layer" aria-label={`${title}操作`}>
            {canOpen ? (
              <button type="button" className="asset-icon-action" onClick={onOpen} aria-label={`查看${title}`}>
                <Eye size={16} aria-hidden="true" />
              </button>
            ) : null}
            {action && status !== 'failed' ? (
              <button type="button" className="asset-text-action" onClick={action.onClick}>
                <ActionIcon size={14} aria-hidden="true" />
                {action.label}
              </button>
            ) : null}
            {actions}
          </div>
        ) : null}
      </div>

      <div className="asset-card-copy">
        <div className="asset-card-heading">
          <div>
            {eyebrow ? <span className="asset-card-eyebrow">{eyebrow}</span> : null}
            <h3>{title}</h3>
          </div>
          <AssetStatus status={status} />
        </div>
        {meta ? <p className="asset-card-meta">{meta}</p> : null}
      </div>
    </article>
  )
}
