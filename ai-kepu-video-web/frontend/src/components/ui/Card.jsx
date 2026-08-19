export function Card({ as: Tag = 'section', className = '', children, ...props }) {
  return <Tag className={`ui-card${className ? ` ${className}` : ''}`} {...props}>{children}</Tag>
}
