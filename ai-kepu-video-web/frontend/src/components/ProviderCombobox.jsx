import { useEffect, useId, useMemo, useState } from 'react'
import { closedComboboxState, preventComboboxOptionBlur } from '../lib/comboboxInteractions'
import { providerGroups } from '../lib/llmProviderCatalog'

export function ProviderCombobox({ value, providers = [], onChange }) {
  const inputId = useId()
  const listboxId = `${inputId}-providers`
  const selected = providers.find(provider => provider.id === value)
  const selectedLabel = selected?.name || value || ''
  const [query, setQuery] = useState(selectedLabel)
  const [open, setOpen] = useState(false)
  const [activeIndex, setActiveIndex] = useState(0)
  const effectiveQuery = query === selectedLabel ? '' : query
  const groups = useMemo(
    () => providerGroups(providers, effectiveQuery),
    [effectiveQuery, providers],
  )
  const options = groups.flatMap(group => group.items)
  const activeOption = options[activeIndex]

  useEffect(() => {
    if (!open) setQuery(selectedLabel)
  }, [open, selectedLabel])

  useEffect(() => {
    setActiveIndex(current => Math.min(current, Math.max(options.length - 1, 0)))
  }, [options.length])

  const optionId = provider => `${listboxId}-${encodeURIComponent(provider.optionKey)}`

  const openList = event => {
    setOpen(true)
    const selectedIndex = options.findIndex(provider => provider.id === value)
    setActiveIndex(selectedIndex >= 0 ? selectedIndex : 0)
    event.currentTarget.select()
  }

  const selectProvider = provider => {
    if (!provider) return
    setQuery(provider.name)
    setOpen(false)
    onChange?.(provider)
  }

  const handleKeyDown = event => {
    if (event.key === 'Escape') {
      event.preventDefault()
      setQuery(selectedLabel)
      setOpen(false)
      return
    }
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault()
      setOpen(true)
      if (!options.length) return
      const direction = event.key === 'ArrowDown' ? 1 : -1
      setActiveIndex(current => (current + direction + options.length) % options.length)
      return
    }
    if (event.key === 'Enter' && open && activeOption) {
      event.preventDefault()
      selectProvider(activeOption)
    }
  }

  const handleBlur = () => {
    const closed = closedComboboxState(selectedLabel)
    setQuery(closed.query)
    setOpen(closed.open)
  }

  return (
    <div className="provider-combobox">
      <input
        id={inputId}
        role="combobox"
        aria-label="生文服务商"
        aria-autocomplete="list"
        aria-expanded={open}
        aria-controls={listboxId}
        aria-activedescendant={open && activeOption ? optionId(activeOption) : undefined}
        autoComplete="off"
        value={query}
        placeholder="搜索服务商名称或 ID"
        onFocus={openList}
        onClick={openList}
        onChange={event => {
          setQuery(event.target.value)
          setOpen(true)
          setActiveIndex(0)
        }}
        onKeyDown={handleKeyDown}
        onBlur={handleBlur}
      />
      <div className="provider-combobox-list" id={listboxId} role="listbox" hidden={!open}>
        {groups.map(group => (
          <div className="provider-option-group" role="group" aria-label={group.label} key={group.key}>
            <strong>{group.label}</strong>
            {group.items.map(provider => (
              <div
                id={optionId(provider)}
                className={`provider-option${provider.id === value ? ' is-selected' : ''}${provider.optionKey === activeOption?.optionKey ? ' is-active' : ''}`}
                role="option"
                aria-selected={provider.id === value}
                key={provider.optionKey}
                onPointerDown={preventComboboxOptionBlur}
                onClick={() => selectProvider(provider)}
                onMouseEnter={() => setActiveIndex(options.findIndex(item => item.optionKey === provider.optionKey))}
              >
                <span><b>{provider.name}</b><small>{provider.id}</small></span>
                {provider.statusLabel ? <em>{provider.statusLabel}</em> : null}
              </div>
            ))}
          </div>
        ))}
        {!options.length ? <p className="provider-combobox-empty">没有匹配的服务商</p> : null}
      </div>
    </div>
  )
}
