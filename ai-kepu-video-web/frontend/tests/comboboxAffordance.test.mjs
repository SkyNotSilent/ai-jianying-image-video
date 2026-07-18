import assert from 'node:assert/strict'
import { after, before, test } from 'node:test'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer } from 'vite'

let vite
let ModelCombobox
let ProviderCombobox

before(async () => {
  vite = await createServer({
    appType: 'custom',
    logLevel: 'silent',
    server: { middlewareMode: true },
  })
  ;({ ModelCombobox } = await vite.ssrLoadModule('/src/components/ModelCombobox.jsx'))
  ;({ ProviderCombobox } = await vite.ssrLoadModule('/src/components/ProviderCombobox.jsx'))
})

after(async () => {
  await vite?.close()
})

test('model combobox renders a permanent dropdown indicator', () => {
  const html = renderToStaticMarkup(createElement(ModelCombobox, {
    value: 'openai/mimo-v2.5-pro',
    models: [{ id: 'openai/mimo-v2.5-pro', label: 'MiMo V2.5 Pro' }],
  }))

  assert.match(html, /provider-combobox-chevron/)
})

test('provider combobox renders the same dropdown indicator', () => {
  const html = renderToStaticMarkup(createElement(ProviderCombobox, {
    value: 'mimo',
    providers: [{ id: 'mimo', name: '小米 MiMo' }],
  }))

  assert.match(html, /provider-combobox-chevron/)
})
