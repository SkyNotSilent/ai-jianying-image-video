import assert from 'node:assert/strict'
import test from 'node:test'

import { createPollingEngine } from '../src/hooks/pollingEngine.js'

function deferred() {
  let resolve
  let reject
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
}

function createManualScheduler() {
  let nextId = 1
  const timers = new Map()

  return {
    setTimeout(callback, delay) {
      const id = nextId
      nextId += 1
      timers.set(id, { callback, delay })
      return id
    },
    clearTimeout(id) {
      timers.delete(id)
    },
    delays() {
      return [...timers.values()].map((timer) => timer.delay)
    },
    runNext() {
      const entry = timers.entries().next().value
      assert.ok(entry, 'expected a scheduled timer')
      const [id, timer] = entry
      timers.delete(id)
      timer.callback()
    },
    size() {
      return timers.size
    },
  }
}

async function flushPromises() {
  await new Promise((resolve) => setImmediate(resolve))
}

test('never overlaps one resource and coalesces queued refreshes after settle', async () => {
  const scheduler = createManualScheduler()
  const requests = []
  let activeRequests = 0
  let maximumActiveRequests = 0
  const engine = createPollingEngine({
    interval: 100,
    scheduler,
    request(resourceKey) {
      const pending = deferred()
      activeRequests += 1
      maximumActiveRequests = Math.max(maximumActiveRequests, activeRequests)
      pending.promise.finally(() => { activeRequests -= 1 })
      requests.push({ resourceKey, pending })
      return pending.promise
    },
  })

  engine.start('workspace-a')
  await flushPromises()
  assert.equal(requests.length, 1)
  assert.equal(scheduler.size(), 0)

  engine.refresh()
  engine.refresh()
  assert.equal(requests.length, 1)
  assert.equal(engine.getState().refreshQueued, true)

  requests[0].pending.resolve({ version: 1 })
  await flushPromises()
  assert.deepEqual(scheduler.delays(), [0])

  scheduler.runNext()
  await flushPromises()
  assert.equal(requests.length, 2)
  assert.equal(maximumActiveRequests, 1)

  requests[1].pending.resolve({ version: 2 })
  await flushPromises()
  assert.deepEqual(scheduler.delays(), [100])
})

test('backs off at base and 2x, then exposes a persistent error on failure three', async () => {
  const scheduler = createManualScheduler()
  const failures = []
  let attempts = 0
  const engine = createPollingEngine({
    interval: 250,
    scheduler,
    request() {
      attempts += 1
      return Promise.reject(new Error(`offline-${attempts}`))
    },
    onError(error, metadata) {
      failures.push({ message: error.message, ...metadata })
    },
  })

  engine.start('workspace-a')
  await flushPromises()
  assert.deepEqual(scheduler.delays(), [250])
  assert.equal(failures[0].persistent, false)
  assert.equal(failures[0].retryDelay, 250)

  scheduler.runNext()
  await flushPromises()
  assert.deepEqual(scheduler.delays(), [500])
  assert.equal(failures[1].persistent, false)
  assert.equal(failures[1].retryDelay, 500)

  scheduler.runNext()
  await flushPromises()
  assert.equal(scheduler.size(), 0)
  assert.equal(attempts, 3)
  assert.equal(failures[2].persistent, true)
  assert.equal(failures[2].retryDelay, null)
  assert.equal(engine.getState().status, 'error')
  assert.equal(engine.getState().error.message, 'offline-3')

  engine.refresh()
  await flushPromises()
  assert.equal(attempts, 4)
  assert.equal(engine.getState().consecutiveFailures, 1)
  assert.deepEqual(scheduler.delays(), [250])
})

test('resource generations prevent a late response from replacing the current resource', async () => {
  const scheduler = createManualScheduler()
  const pendingByResource = new Map()
  const signalsByResource = new Map()
  const received = []
  const engine = createPollingEngine({
    scheduler,
    request(resourceKey, { signal }) {
      const pending = deferred()
      pendingByResource.set(resourceKey, pending)
      signalsByResource.set(resourceKey, signal)
      return pending.promise
    },
    onData(data, metadata) {
      received.push({ data, metadata })
    },
  })

  engine.start('task-a')
  await flushPromises()
  const generationA = engine.getState().generation

  engine.setResourceKey('task-b')
  await flushPromises()
  assert.equal(signalsByResource.get('task-a').aborted, true)
  const generationB = engine.getState().generation
  assert.ok(generationB > generationA)

  pendingByResource.get('task-a').resolve('late-a')
  await flushPromises()
  assert.deepEqual(received, [])

  pendingByResource.get('task-b').resolve('current-b')
  await flushPromises()
  assert.equal(received.length, 1)
  assert.equal(received[0].data, 'current-b')
  assert.equal(received[0].metadata.resourceKey, 'task-b')
})

test('pause and resume expose page-visibility control without losing a queued refresh', async () => {
  const scheduler = createManualScheduler()
  const requests = []
  const engine = createPollingEngine({
    interval: 100,
    scheduler,
    request() {
      const pending = deferred()
      requests.push(pending)
      return pending.promise
    },
  })

  engine.start('workspace-a')
  await flushPromises()
  engine.refresh()
  engine.setVisible(false)
  assert.equal(engine.getState().status, 'paused')

  requests[0].resolve('hidden-result')
  await flushPromises()
  assert.equal(scheduler.size(), 0)
  assert.equal(requests.length, 1)

  engine.setVisible(true)
  await flushPromises()
  assert.equal(requests.length, 2)
  assert.equal(engine.getState().status, 'polling')
})

test('stop invalidates in-flight work and dispose prevents future starts', async () => {
  const scheduler = createManualScheduler()
  const pending = deferred()
  const received = []
  let requestSignal
  const engine = createPollingEngine({
    scheduler,
    request: (_key, { signal }) => {
      requestSignal = signal
      return pending.promise
    },
    onData: (data) => received.push(data),
  })

  engine.start('workspace-a')
  await flushPromises()
  engine.stop()
  assert.equal(requestSignal.aborted, true)
  pending.resolve('too-late')
  await flushPromises()
  assert.deepEqual(received, [])
  assert.equal(engine.getState().status, 'idle')

  engine.dispose()
  assert.equal(engine.getState().status, 'disposed')
  assert.equal(engine.start('workspace-b'), false)
  assert.equal(engine.refresh(), false)
  assert.equal(scheduler.size(), 0)
})
