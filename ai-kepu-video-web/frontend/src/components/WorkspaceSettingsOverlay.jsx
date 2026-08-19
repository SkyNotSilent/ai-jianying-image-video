import { useEffect, useRef } from 'react'

const FOCUSABLE = 'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

export function WorkspaceSettingsOverlay({ open, onClose, children }) {
  const overlayRef = useRef(null)
  const closeRef = useRef(onClose)
  closeRef.current = onClose

  useEffect(() => {
    if (!open) return undefined
    const previouslyFocused = document.activeElement
    const overlay = overlayRef.current
    const focusable = () => Array.from(overlay?.querySelectorAll(FOCUSABLE) || [])
      .filter(element => !element.hasAttribute('hidden') && element.getAttribute('aria-hidden') !== 'true')
    const focusFirstControl = () => {
      const initial = overlay?.querySelector('[data-settings-initial-focus]') || focusable()[0]
      if (!initial) {
        overlay?.focus?.()
        return false
      }
      initial.focus()
      return true
    }
    let observer
    const focusFrame = window.requestAnimationFrame(() => {
      if (focusFirstControl()) return
      observer = new MutationObserver(() => {
        if (!focusFirstControl()) return
        observer.disconnect()
      })
      observer.observe(overlay, { childList: true, subtree: true })
    })

    const handleKeyDown = event => {
      if (event.key === 'Escape') {
        event.preventDefault()
        closeRef.current?.()
        return
      }
      if (event.key !== 'Tab') return
      const controls = focusable()
      if (!controls.length) {
        event.preventDefault()
        overlay?.focus()
        return
      }
      const first = controls[0]
      const last = controls[controls.length - 1]
      if (event.shiftKey && (document.activeElement === first || !overlay?.contains(document.activeElement))) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }

    overlay?.addEventListener('keydown', handleKeyDown)
    return () => {
      window.cancelAnimationFrame(focusFrame)
      observer?.disconnect()
      overlay?.removeEventListener('keydown', handleKeyDown)
      if (previouslyFocused instanceof HTMLElement && previouslyFocused.isConnected) {
        previouslyFocused.focus({ preventScroll: true })
      }
    }
  }, [open])

  if (!open) return null
  return <div ref={overlayRef} className="workspace-settings-overlay" role="dialog" aria-modal="true" aria-label="API 配置" tabIndex="-1">{children}</div>
}
