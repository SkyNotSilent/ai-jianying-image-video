import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

import { buildExportPollingKey, isActiveExportJob } from '../src/pages/exportPolling.js'

const exportPageSource = readFileSync(new URL('../src/pages/ExportPage.jsx', import.meta.url), 'utf8')

test('export polling key retains the exact active job ids and is stable across object order', () => {
  const jobsA = {
    mp4: { job_id: 'job-mp4', status: 'processing' },
    materials: { job_id: 'job-materials', status: 'pending' },
    draft: { job_id: 'finished-draft', status: 'completed' },
  }
  const jobsB = {
    draft: jobsA.draft,
    materials: jobsA.materials,
    mp4: jobsA.mp4,
  }

  const key = buildExportPollingKey('task-a', jobsA)
  assert.equal(key, buildExportPollingKey('task-a', jobsB))
  assert.deepEqual(JSON.parse(key), {
    taskId: 'task-a',
    jobs: [
      { target: 'materials', jobId: 'job-materials' },
      { target: 'mp4', jobId: 'job-mp4' },
    ],
  })
  assert.equal(isActiveExportJob({ job_id: 'job-a', status: 'processing' }), true)
  assert.equal(isActiveExportJob({ job_id: 'job-a', status: 'failed' }), false)
  assert.equal(isActiveExportJob({ job_id: 'job-a', status: 'cancelled' }), false)
  assert.equal(isActiveExportJob({ status: 'processing' }), false)
  assert.equal(buildExportPollingKey('task-a', { mp4: jobsA.draft }), null)
})

test('export page uses single-flight GET reconnects and guards late task responses', () => {
  assert.doesNotMatch(exportPageSource, /\bsetInterval\s*\(/)
  assert.equal(exportPageSource.match(/usePollingResource\s*\(\s*\{/g)?.length, 1)
  assert.match(exportPageSource, /getExportJob\(batch\.taskId, jobId, \{ silent: true, signal \}\)/)
  assert.match(exportPageSource, /onReconnect=\{exportJobsPolling\.reconnect\}/)
  assert.match(exportPageSource, /重新连接只会查询原记录，不会重复创建导出/)
  assert.match(exportPageSource, /const expectedTaskId = taskId[\s\S]*createExport\(expectedTaskId, payload\)[\s\S]*activeTaskIdRef\.current !== expectedTaskId/)
  assert.match(exportPageSource, /activeTaskIdRef\.current !== polledTaskId/)
  assert.match(exportPageSource, /loadedTaskId !== taskId/)
  assert.match(exportPageSource, /cancelExportJob\(taskId, job\.job_id\)/)
  assert.match(exportPageSource, /取消生成/)
})
