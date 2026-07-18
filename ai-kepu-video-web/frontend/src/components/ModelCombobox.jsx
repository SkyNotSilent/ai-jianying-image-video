import { useEffect, useId, useMemo, useState } from 'react'
import { ChevronDown } from 'lucide-react'
import { closedComboboxState, preventComboboxOptionBlur } from '../lib/comboboxInteractions'
import { mergeProviderModels, modelGroups } from '../lib/llmProviderCatalog'

export function ModelCombobox({ value, models = [], onChange }) {
  const inputId = useId()
  const listboxId = `${inputId}-models`
  const displayModels = useMemo(
    () => mergeProviderModels(models, [], value),
    [models, value],
  )
  const selected = displayModels.find(model => model.id === value)
  const selectedLabel = selected?.label || value || ''
  const [query, setQuery] = useState(selectedLabel)
  const [open, setOpen] = useState(false)
  const [activeIndex, setActiveIndex] = useState(0)
  const effectiveQuery = query === selectedLabel ? '' : query
  const groups = useMemo(
    () => modelGroups(displayModels, effectiveQuery),
    [displayModels, effectiveQuery],
  )
  const options = groups.flatMap(group => group.items)
  const activeOption = options[activeIndex]

  useEffect(() => {
    if (!open) setQuery(selectedLabel)
  }, [open, selectedLabel])

  useEffect(() => {
    setActiveIndex(current => Math.min(current, Math.max(options.length - 1, 0)))
  }, [options.length])

  const optionId = model => `${listboxId}-${encodeURIComponent(model.optionKey)}`

  const openList = event => {
    setOpen(true)
    const selectedIndex = options.findIndex(model => model.id === value)
    setActiveIndex(selectedIndex >= 0 ? selectedIndex : 0)
    event.currentTarget.select()
  }

  const selectModel = model => {
    if (!model) return
    setQuery(model.label)
    setOpen(false)
    onChange?.(model.id)
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
      selectModel(activeOption)
    }
  }

  const handleBlur = () => {
    const closed = closedComboboxState(selectedLabel)
    setQuery(closed.query)
    setOpen(closed.open)
  }

  return (
    <div className="provider-combobox model-combobox">
      <input
        id={inputId}
        role="combobox"
        aria-label="生文模型"
        aria-autocomplete="list"
        aria-expanded={open}
        aria-controls={listboxId}
        aria-activedescendant={open && activeOption ? optionId(activeOption) : undefined}
        autoComplete="off"
        value={query}
        placeholder="搜索模型名称或 ID"
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
      <ChevronDown
        className={`provider-combobox-chevron${open ? ' is-open' : ''}`}
        size={16}
        aria-hidden="true"
      />
      <div className="provider-combobox-list" id={listboxId} role="listbox" hidden={!open}>
        {groups.map(group => (
          <div className="provider-option-group" role="group" aria-label={group.label} key={group.key}>
            <strong>{group.label}</strong>
            {group.items.map(model => (
              <div
                id={optionId(model)}
                className={`provider-option model-option${model.id === value ? ' is-selected' : ''}${model.optionKey === activeOption?.optionKey ? ' is-active' : ''}`}
                role="option"
                aria-selected={model.id === value}
                key={model.optionKey}
                onPointerDown={preventComboboxOptionBlur}
                onClick={() => selectModel(model)}
                onMouseEnter={() => setActiveIndex(options.findIndex(item => item.optionKey === model.optionKey))}
              >
                <span><b>{model.label}</b><small>{model.id}</small></span>
                {model.historical
                  ? <em>历史/自定义</em>
                  : model.sources?.includes('account') ? <em>账号可用</em> : null}
              </div>
            ))}
          </div>
        ))}
        {!options.length ? <p className="provider-combobox-empty">没有匹配的模型</p> : null}
      </div>
    </div>
  )
}
