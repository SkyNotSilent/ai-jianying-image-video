export function AdvancedSettings({ title, summary, onRestore, children }) {
  const restorePreset = event => {
    event.preventDefault()
    onRestore()
  }

  return (
    <details className="settings-advanced">
      <summary>
        <span className="settings-advanced-summary-row">
          <span className="settings-advanced-heading">
            <strong>{title}</strong>
            {summary ? <small>{summary}</small> : null}
          </span>
          {onRestore ? <button type="button" onClick={restorePreset}>恢复预置</button> : null}
        </span>
      </summary>
      <div className="settings-advanced-grid">{children}</div>
    </details>
  )
}
