export function Button({ variant = 'secondary', className = '', type = 'button', children, ...props }) {
  return <button type={type} className={`button button-${variant}${className ? ` ${className}` : ''}`} {...props}>{children}</button>
}
