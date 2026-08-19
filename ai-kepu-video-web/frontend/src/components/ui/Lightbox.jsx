import { ChevronLeft, ChevronRight, X } from 'lucide-react'
import { useCallback, useEffect, useId, useRef, useState } from 'react'
import './asset-components.css'

const FOCUSABLE = 'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

/**
 * Controlled-friendly image lightbox with built-in keyboard and focus management.
 */
export function Lightbox({
  open,
  items = [],
  activeIndex = 0,
  title = '素材查看器',
  onIndexChange,
  onClose,
  promptSlot,
  actionSlot,
  className = '',
}) {
  const [localIndex, setLocalIndex] = useState(activeIndex)
  const dialogRef = useRef(null)
  const closeRef = useRef(onClose)
  const itemsRef = useRef(items)
  const indexChangeRef = useRef(onIndexChange)
  const titleId = useId()
  closeRef.current = onClose
  itemsRef.current = items
  indexChangeRef.current = onIndexChange

  useEffect(() => {
    if (open) setLocalIndex(Math.min(Math.max(activeIndex, 0), Math.max(items.length - 1, 0)))
  }, [activeIndex, items.length, open])

  const move = useCallback(direction => {
    const currentItems = itemsRef.current
    if (currentItems.length < 2) return
    setLocalIndex(current => {
      const next = (current + direction + currentItems.length) % currentItems.length
      indexChangeRef.current?.(next, currentItems[next])
      return next
    })
  }, [])

  useEffect(() => {
    if (!open) return undefined
    const previouslyFocused = document.activeElement
    const previousOverflow = document.body.style.overflow
    const dialog = dialogRef.current
    document.body.style.overflow = 'hidden'
    window.requestAnimationFrame(() => dialog?.querySelector('[data-lightbox-initial-focus]')?.focus())

    const handleKeyDown = event => {
      if (event.key === 'Escape') {
        event.preventDefault()
        closeRef.current?.()
        return
      }
      if (event.key === 'ArrowLeft') {
        event.preventDefault()
        move(-1)
        return
      }
      if (event.key === 'ArrowRight') {
        event.preventDefault()
        move(1)
        return
      }
      if (event.key !== 'Tab') return
      const controls = Array.from(dialog?.querySelectorAll(FOCUSABLE) || [])
      if (!controls.length) {
        event.preventDefault()
        dialog?.focus()
        return
      }
      const first = controls[0]
      const last = controls[controls.length - 1]
      if (event.shiftKey && (document.activeElement === first || !dialog?.contains(document.activeElement))) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }

    // Listen at the document level while the modal is open. This keeps Escape
    // and arrow navigation responsive during the single frame before initial
    // focus moves into the dialog, and if an image refresh temporarily moves
    // focus back to the page underneath.
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      document.body.style.overflow = previousOverflow
      if (previouslyFocused instanceof HTMLElement && previouslyFocused.isConnected) previouslyFocused.focus()
    }
  }, [move, open])

  if (!open) return null
  const item = items[localIndex]
  const renderSlot = (slot) => typeof slot === 'function' ? slot(item, localIndex) : slot

  return (
    <div className="asset-lightbox-backdrop" role="presentation" onMouseDown={() => closeRef.current?.()}>
      <section
        ref={dialogRef}
        className={`asset-lightbox${className ? ` ${className}` : ''}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex="-1"
        onMouseDown={event => event.stopPropagation()}
      >
        <header className="asset-lightbox-header">
          <div>
            <span>{items.length ? `${localIndex + 1} / ${items.length}` : '0 / 0'}</span>
            <h2 id={titleId}>{item?.title || title}</h2>
          </div>
          <button type="button" className="asset-lightbox-close" data-lightbox-initial-focus onClick={() => closeRef.current?.()} aria-label="关闭素材查看器">
            <X size={19} aria-hidden="true" />
          </button>
        </header>

        <div className="asset-lightbox-stage">
          {item?.src ? <img src={item.src} alt={item.alt || item.title || ''} /> : <p>暂无可查看的素材</p>}
          {items.length > 1 ? (
            <>
              <button type="button" className="asset-lightbox-nav is-previous" onClick={() => move(-1)} aria-label="查看上一张"><ChevronLeft size={22} aria-hidden="true" /></button>
              <button type="button" className="asset-lightbox-nav is-next" onClick={() => move(1)} aria-label="查看下一张"><ChevronRight size={22} aria-hidden="true" /></button>
            </>
          ) : null}
        </div>

        {(promptSlot || actionSlot) ? (
          <footer className="asset-lightbox-footer">
            {promptSlot ? <div className="asset-lightbox-prompt">{renderSlot(promptSlot)}</div> : null}
            {actionSlot ? <div className="asset-lightbox-actions">{renderSlot(actionSlot)}</div> : null}
          </footer>
        ) : null}
      </section>
    </div>
  )
}
