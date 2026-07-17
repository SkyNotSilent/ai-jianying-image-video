export function preventComboboxOptionBlur(event) {
  event.preventDefault()
}

export function closedComboboxState(selectedLabel = '') {
  return {
    query: String(selectedLabel || ''),
    open: false,
  }
}
