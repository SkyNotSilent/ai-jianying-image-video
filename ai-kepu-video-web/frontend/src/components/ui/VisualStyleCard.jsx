import { CheckCircle2 } from 'lucide-react'
import { Tooltip } from './Tooltip'

export function VisualStyleCard({ style, selected, disabled = false, onSelect, className = '' }) {
  return <Tooltip label={`${style.label}：${style.description || '应用到全部分镜画面'}`} placement="top">
    <button
      type="button"
      className={`ui-visual-style-card${selected ? ' is-selected' : ''}${className ? ` ${className}` : ''}`}
      aria-pressed={selected}
      disabled={disabled}
      onClick={() => onSelect?.(style.value)}
    >
      <img src={style.image} alt="" />
      <span><strong>{style.label}</strong><small>{style.description}</small></span>
      {selected ? <i aria-hidden="true"><CheckCircle2 size={15} /></i> : null}
    </button>
  </Tooltip>
}
