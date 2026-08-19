import assert from 'node:assert/strict'
import { access, readFile } from 'node:fs/promises'
import test from 'node:test'

const frontend = new URL('../', import.meta.url)

test('legacy page implementations stay deleted while compatibility redirects remain', async () => {
  const removed = [
    'src/pages/PreviewPage.jsx',
    'src/pages/ProcessPage.jsx',
    'src/pages/ProductionSetupPage.jsx',
    'src/components/TaskProgress.jsx',
    'src/hooks/usePolling.js',
    'src/hooks/pollingSession.js',
    'src/pages/preview-page.css',
    'src/styles/apple-design.css',
  ]

  for (const path of removed) {
    await assert.rejects(access(new URL(path, frontend)), `${path} must not return as a second implementation`)
  }

  const app = await readFile(new URL('src/App.jsx', frontend), 'utf8')
  assert.match(app, /path="\/production\/:draftId"[^\n]*ProductionRedirect/)
  assert.match(app, /path="\/process\/:taskId"[^\n]*WorkspaceRedirect/)
  assert.match(app, /path="\/preview\/:taskId"[^\n]*WorkspaceRedirect/)
})

test('the active creation stylesheet contains no orphan production/process UI', async () => {
  const css = await readFile(new URL('src/pages/creation-flow.css', frontend), 'utf8')
  assert.doesNotMatch(css, /\.(?:process-page|process-workspace|task-progress|production-layout|production-style-grid)\b/)
  assert.doesNotMatch(css, /#[0-9a-f]{3,8}\b|rgba?\(/i)
})
