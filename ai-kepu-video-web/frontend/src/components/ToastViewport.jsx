import { useEffect, useState } from 'react'
import { CheckCircle2, CircleAlert, Info, X, XCircle } from 'lucide-react'
import { subscribeToasts } from '../lib/toast'

const icons = { success: CheckCircle2, warning: CircleAlert, error: XCircle, info: Info }

export function ToastViewport() {
  const [notifications, setNotifications] = useState([])

  useEffect(() => subscribeToasts(notification => {
    setNotifications(current => [...current, notification])
    if (notification.duration > 0) {
      window.setTimeout(() => {
        setNotifications(current => current.filter(item => item.id !== notification.id))
      }, notification.duration)
    }
  }), [])

  const dismiss = id => setNotifications(current => current.filter(notification => notification.id !== id))

  return (
    <section className="toast-viewport" aria-label="通知" aria-live="polite">
      {notifications.map(notification => {
        const Icon = icons[notification.type]
        return (
          <div className={`toast toast-${notification.type}`} key={notification.id} role="status">
            <Icon size={18} aria-hidden="true" />
            <p>{notification.message}</p>
            <button type="button" className="icon-button" onClick={() => dismiss(notification.id)} aria-label="关闭通知" title="关闭通知">
              <X size={16} aria-hidden="true" />
            </button>
          </div>
        )
      })}
    </section>
  )
}
