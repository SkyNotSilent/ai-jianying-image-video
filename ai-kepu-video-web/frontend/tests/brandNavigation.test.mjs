import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const component = readFileSync(new URL('../src/components/BrandNavigation.jsx', import.meta.url), 'utf8')
const css = readFileSync(new URL('../src/styles/app.css', import.meta.url), 'utf8')

test('brand navigation renders the historical animated icon layers', () => {
  assert.doesNotMatch(component, /\bClapperboard\b/)
  for (const className of ['brand-glow', 'brand-inner', 'brand-reticles', 'brand-reticle-row', 'brand-reticle-corner', 'brand-dot']) {
    assert.match(component, new RegExp(`className="[^"]*${className}`))
  }
  assert.match(component, /className="brand-mark" aria-hidden="true"/)
})

test('brand icon restores stepped pauses and reduced-motion behavior', () => {
  assert.match(css, /\.brand-glow\s*\{[^}]*conic-gradient[^}]*animation:\s*brand-glow-spin 4s linear infinite/s)
  assert.match(css, /@keyframes brand-reticle-snap\s*\{\s*0%, 20%\s*\{[^}]*rotate\(0deg\)[^}]*\}\s*25%, 45%\s*\{[^}]*rotate\(90deg\)/s)
  assert.match(css, /\.brand-dot\s*\{[^}]*animation:\s*brand-dot-pulse 2\.5s linear infinite/s)
  assert.match(css, /@media \(prefers-reduced-motion: reduce\)\s*\{[^}]*\.brand-glow,[\s\S]*\.brand-dot\s*\{\s*animation:\s*none/s)
})
