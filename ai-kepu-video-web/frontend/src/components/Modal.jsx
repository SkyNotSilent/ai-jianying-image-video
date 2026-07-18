import { useEffect } from 'react'
import { X } from 'lucide-react'

export function Modal({ open, title, children, onClose, footer }) {
  useEffect(() => {
    if (!open) return undefined
    const onKeyDown = event => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [onClose, open])

  if (!open) return null

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <section className="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title" onMouseDown={event => event.stopPropagation()}>
        <header className="modal-header">
          <h2 id="modal-title">{title}</h2>
          <button type="button" className="icon-button" onClick={onClose} aria-label="关闭对话框" title="关闭对话框"><X size={18} aria-hidden="true" /></button>
        </header>
        <div className="modal-content">{children}</div>
        {footer && <footer className="modal-footer">{footer}</footer>}
      </section>
    </div>
  )
}

export function ConfirmDialog({ open, title = '确认操作', message, confirmLabel = '确认', cancelLabel = '取消', onConfirm, onClose, danger = false, confirmDisabled = false }) {
  return (
    <Modal
      open={open}
      title={title}
      onClose={onClose}
      footer={<><button type="button" className="button button-secondary" onClick={onClose} disabled={confirmDisabled}>{cancelLabel}</button><button type="button" className={`button ${danger ? 'button-danger' : 'button-primary'}`} onClick={onConfirm} disabled={confirmDisabled}>{confirmLabel}</button></>}
    >
      <p>{message}</p>
    </Modal>
  )
}
