import assert from 'node:assert/strict'
import test from 'node:test'

import {
  getDeleteConfirmation,
  getDeletionIssueCount,
  getProjectPrimaryAction,
} from '../src/pages/projectActions.js'
import { deriveTaskState } from '../src/utils/taskState.js'

test('interrupted task exposes continue generation', () => {
  const state = deriveTaskState({
    task: { status: 'interrupted' },
    segments: [{ text: 'saved' }],
  })

  assert.equal(state.key, 'interrupted')
  assert.equal(state.actionLabel, '继续生成')
  assert.equal(getProjectPrimaryAction({ type: 'task', status: state.key }), 'resume')
})

test('processing and local draft projects keep their existing primary actions', () => {
  assert.equal(getProjectPrimaryAction({ type: 'task', status: 'processing' }), 'progress')
  assert.equal(getProjectPrimaryAction({ type: 'draft', status: 'draft' }), 'draft')
})

test('generated project deletion warns that every local artifact is permanent', () => {
  const confirmation = getDeleteConfirmation({ type: 'task', name: '测试项目' })

  assert.match(confirmation.message, /图片、配音、视频和剪映草稿/u)
  assert.equal(confirmation.title, '删除项目')
  assert.equal(confirmation.confirmLabel, '永久删除')
})

test('local draft deletion remains scoped to the browser draft', () => {
  const confirmation = getDeleteConfirmation({ type: 'draft', name: '本地文稿' })

  assert.match(confirmation.message, /本地文稿草稿/u)
  assert.doesNotMatch(confirmation.message, /图片、配音、视频/u)
  assert.equal(confirmation.confirmLabel, '删除草稿')
})

test('counts failed and skipped cleanup paths for warning feedback', () => {
  assert.equal(getDeletionIssueCount({
    deletion_report: {
      failed_paths: ['locked.mp4'],
      skipped_paths: ['outside.mp4', 'outside.wav'],
    },
  }), 3)
  assert.equal(getDeletionIssueCount({ outcome: 'deleting' }), 0)
})
