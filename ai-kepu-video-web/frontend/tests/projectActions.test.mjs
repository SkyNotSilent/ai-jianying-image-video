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
  assert.equal(state.actionLabel, '查看并继续')
  assert.equal(getProjectPrimaryAction({ type: 'task', status: state.key }), 'workspace')
})

test('failed task with a saved segment exposes continue generation', () => {
  const state = deriveTaskState({
    task: { status: 'failed', error: 'provider timeout' },
    segments: [{ segment_index: 0, text: '已保存分镜' }],
  })

  assert.equal(state.key, 'interrupted')
  assert.equal(state.actionLabel, '查看并继续')
  assert.equal(getProjectPrimaryAction({ type: 'task', status: state.key }), 'workspace')
})

test('failed task with only a saved script still exposes continue generation', () => {
  const state = deriveTaskState({
    task: { status: 'failed', script_text: '已保存完整脚本' },
    segments: [],
  })

  assert.equal(state.key, 'interrupted')
  assert.equal(state.actionLabel, '查看并继续')
})

test('failed task detail can expose resume without returning checkpoint content', () => {
  const state = deriveTaskState({
    task: { status: 'failed', can_resume: true },
    segments: [],
  })

  assert.equal(state.key, 'interrupted')
  assert.equal(state.actionLabel, '查看并继续')
})

test('failed task without checkpoint evidence retains recovery-only action', () => {
  const state = deriveTaskState({
    task: { status: 'failed', error: 'failed before checkpoint' },
    segments: [],
  })

  assert.equal(state.key, 'recoverable_assets')
  assert.equal(state.actionLabel, '查看已保存素材')
  assert.equal(getProjectPrimaryAction({ type: 'task', status: state.key }), 'workspace')
})

test('all generated projects open the persistent workspace without triggering generation', () => {
  assert.equal(deriveTaskState({ task: { status: 'pending' } }).key, 'processing')
  assert.equal(deriveTaskState({ task: { status: 'processing' } }).key, 'processing')
  assert.equal(deriveTaskState({ task: { status: 'completed' } }).key, 'completed')
  assert.equal(getProjectPrimaryAction({ type: 'task', status: 'processing' }), 'workspace')
  assert.equal(getProjectPrimaryAction({ type: 'task', status: 'completed' }), 'workspace')
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
