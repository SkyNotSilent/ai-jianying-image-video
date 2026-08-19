import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const cssUrl = new URL('../src/pages/delivery-pages.css', import.meta.url)
const css = await readFile(cssUrl, 'utf8')

test('delivery pages use the shared semantic palette instead of page-local colors', () => {
  assert.match(css, /var\(--color-canvas\)|var\(--color-surface\)/)
  assert.match(css, /var\(--color-ink\)/)
  assert.match(css, /var\(--color-success\)/)
  assert.match(css, /var\(--color-warning\)/)
  assert.match(css, /var\(--color-danger\)/)
  assert.doesNotMatch(css, /#[0-9a-f]{3,8}\b/i)
  assert.doesNotMatch(css, /rgba?\(/i)
})

test('assets, settings, and export layouts keep min-width escape hatches', () => {
  assert.match(css, /\.assets-page\s*\{[^}]*grid-template-columns:\s*232px minmax\(0, 1fr\)/s)
  assert.match(css, /\.assets-workspace\s*\{[^}]*min-width:\s*0/s)
  assert.match(css, /\.settings-layout\s*\{[^}]*minmax\(0, 1fr\)/s)
  assert.match(css, /\.export-options\s*\{[^}]*minmax\(0, 1fr\)/s)
  assert.match(css, /@media \(max-width:\s*766px\)[\s\S]*\.assets-page\s*\{[^}]*display:\s*block/s)
  assert.match(css, /@media \(max-width:\s*500px\)[\s\S]*\.asset-project-grid\s*\{[^}]*minmax\(0, 1fr\)/s)
})

test('editorial delivery hierarchy uses the display face for primary titles', () => {
  assert.match(css, /\.delivery-heading h1,[\s\S]*font-family:\s*var\(--font-display\)/)
  assert.match(css, /\.asset-project-copy h2\s*\{[^}]*font-family:\s*var\(--font-display\)/s)
  assert.match(css, /\.settings-section h2\s*\{[^}]*font-family:\s*var\(--font-display\)/s)
})
