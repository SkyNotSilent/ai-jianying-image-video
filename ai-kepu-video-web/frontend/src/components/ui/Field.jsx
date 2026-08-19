export function Field({ label, hint, error, className = '', children }) {
  return <label className={`ui-field${error ? ' has-error' : ''}${className ? ` ${className}` : ''}`}>
    <span>{label}</span>
    {children}
    {error ? <small role="alert">{error}</small> : hint ? <small>{hint}</small> : null}
  </label>
}
