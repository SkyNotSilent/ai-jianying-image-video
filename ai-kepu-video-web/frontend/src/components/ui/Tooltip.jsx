import { cloneElement, isValidElement, useEffect, useId, useState } from 'react'

export function Tooltip({ label, children, placement = 'top' }) {
  const [open, setOpen] = useState(false)
  const id = useId()

  useEffect(() => {
    if (!open) return undefined
    const close = event => { if (event.key === 'Escape') setOpen(false) }
    window.addEventListener('keydown', close)
    return () => window.removeEventListener('keydown', close)
  }, [open])

  const trigger = isValidElement(children)
    ? cloneElement(children, { 'aria-describedby': open ? id : children.props['aria-describedby'] })
    : children

  return <span
    className={`ui-tooltip is-${placement}`}
    onMouseEnter={() => setOpen(true)}
    onMouseLeave={() => setOpen(false)}
    onFocusCapture={() => setOpen(true)}
    onBlurCapture={() => setOpen(false)}
  >
    {trigger}
    {open ? <span id={id} className="ui-tooltip-popover" role="tooltip">{label}</span> : null}
  </span>
}
