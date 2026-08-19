import { CircleAlert, RefreshCw } from 'lucide-react'

export function PollingFailureNotice({ title, description, onReconnect, reconnecting = false }) {
  return <section className="workspace-polling-notice" role="alert">
    <CircleAlert size={18} aria-hidden="true" />
    <div>
      <strong>{title}</strong>
      <span>{description}</span>
    </div>
    <button type="button" onClick={onReconnect} disabled={reconnecting}>
      <RefreshCw className={reconnecting ? 'spin' : ''} size={15} aria-hidden="true" />
      {reconnecting ? '正在重连…' : '重新连接'}
    </button>
  </section>
}
