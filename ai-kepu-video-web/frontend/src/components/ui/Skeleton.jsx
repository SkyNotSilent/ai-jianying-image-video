export function Skeleton({ className = '', label = '内容生成中', style }) {
  return <span className={`ui-skeleton${className ? ` ${className}` : ''}`} style={style} role="status" aria-label={label} />
}
