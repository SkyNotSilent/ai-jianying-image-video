import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const frontendRoot = new URL('../', import.meta.url)

async function source(path) {
  return readFile(new URL(path, frontendRoot), 'utf8')
}

test('empty-state artwork stays reusable, inline, and token-driven', async () => {
  const [component, styles] = await Promise.all([
    source('src/components/ui/EmptyStateCard.jsx'),
    source('src/components/ui/ui.css'),
  ])

  assert.match(component, /export function EmptyStateCard/)
  assert.match(component, /export function EditorialLineIllustration/)
  assert.match(component, /<svg/)
  assert.doesNotMatch(component, /<img\b/)
  assert.match(styles, /\.ui-empty-state/)
  assert.match(styles, /var\(--color-(?:surface|ink|accent|border)/)
  assert.match(styles, /var\(--space-/)
})

test('primary creation, assets, and settings empty states use the shared card', async () => {
  const [manuscript, assets, settings, statusStates] = await Promise.all([
    source('src/pages/ManuscriptPage.jsx'),
    source('src/pages/ProjectAssetsPage.jsx'),
    source('src/pages/SettingsPage.jsx'),
    source('src/components/StatusStates.jsx'),
  ])

  assert.match(manuscript, /<EmptyStateCard[\s\S]*variant="manuscript"/)
  assert.match(assets, /<EmptyState variant="projects"/)
  assert.match(settings, /<EmptyStateCard variant="voice"/)
  assert.match(settings, /<EmptyState variant="configuration"/)
  assert.match(statusStates, /<EmptyStateCard/)
})
