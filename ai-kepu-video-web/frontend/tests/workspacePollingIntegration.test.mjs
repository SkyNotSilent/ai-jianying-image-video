import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const workspaceSource = readFileSync(new URL('../src/pages/WorkspacePage.jsx', import.meta.url), 'utf8')
const noticeSource = readFileSync(new URL('../src/components/PollingFailureNotice.jsx', import.meta.url), 'utf8')

test('workspace and MP4 status use single-flight polling without interval loops', () => {
  assert.doesNotMatch(workspaceSource, /\bsetInterval\s*\(/)
  assert.equal(workspaceSource.match(/usePollingResource\s*\(\s*\{/g)?.length, 2)
  assert.match(workspaceSource, /resourceKey:\s*taskId[\s\S]*getTaskWorkspace\(currentTaskId/)
  assert.match(workspaceSource, /JSON\.stringify\(\[taskId, previewJob\.job_id\]\)/)
  assert.match(workspaceSource, /setPreviewJob\(current => \([\s\S]*activePreviewJob\(nextExport\)/)
})

test('failed MP4 polling reconnects the retained job and exposes an accessible alert', () => {
  assert.match(workspaceSource, /if \(previewJobIsActive\) \{[\s\S]*previewJobPolling\.reconnect\(\)[\s\S]*return/)
  assert.match(workspaceSource, /getExportJob\(currentTaskId, jobId, \{ silent: true, signal \}\)/)
  assert.match(noticeSource, /role="alert"/)
  assert.match(workspaceSource, /生成编号已保留。重新连接只会查询同一次生成，不会重复创建视频。/)
})

test('an active full-video job can be cancelled without creating a replacement job', () => {
  assert.match(workspaceSource, /cancelExportJob\(taskId, previewJob\.job_id\)/)
  assert.match(workspaceSource, /onCancelFullVideo=\{cancelFullVideoPreview\}/)
  assert.match(workspaceSource, /上一份可用视频仍然保留/)
})
