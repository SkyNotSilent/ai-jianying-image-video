import assert from 'node:assert/strict'
import test from 'node:test'

import { createPollingSession } from '../src/hooks/pollingSession.js'

test('switching task ids invalidates the previous polling generation', () => {
  const session = createPollingSession()

  const taskA = session.transition('task-a')
  assert.equal(taskA.changed, true)
  assert.equal(session.isCurrent(taskA.generation), true)

  const sameTask = session.transition('task-a')
  assert.equal(sameTask.changed, false)
  assert.equal(sameTask.generation, taskA.generation)

  const taskB = session.transition('task-b')
  assert.equal(taskB.changed, true)
  assert.equal(session.isCurrent(taskA.generation), false)
  assert.equal(session.isCurrent(taskB.generation), true)
})

test('stopping a polling session invalidates requests still in flight', () => {
  const session = createPollingSession()
  const active = session.transition('task-a')

  session.invalidate()

  assert.equal(session.isCurrent(active.generation), false)
})
