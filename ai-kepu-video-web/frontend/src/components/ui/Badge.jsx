export function Badge({ tone = 'neutral', className = '', children, ...props }) {
  return <span className={`ui-badge is-${tone}${className ? ` ${className}` : ''}`} {...props}>{children}</span>
}
