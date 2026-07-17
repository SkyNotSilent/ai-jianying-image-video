import test from 'node:test'
import assert from 'node:assert/strict'

import {
  safeApiLogArgs,
  toSafeApiError,
} from '../src/lib/apiErrorSafety.js'

function graphText(value) {
  const seen = new Set()
  const visit = current => {
    if (current === null || current === undefined) return String(current)
    if (typeof current !== 'object' && typeof current !== 'function') return String(current)
    if (seen.has(current)) return '[circular]'
    seen.add(current)
    const entries = []
    for (const key of Reflect.ownKeys(current)) {
      let item
      try {
        item = current[key]
      } catch {
        item = '[unreadable]'
      }
      entries.push(`${String(key)}=${visit(item)}`)
    }
    return `${current.constructor?.name || 'Object'}{${entries.join(',')}}`
  }
  return visit(value)
}

test('HTTP failures produce a detached safe error and safe log arguments', () => {
  const markers = [
    'REQUEST-BODY-TOP-SECRET',
    'AUTHORIZATION-TOP-SECRET',
    'RESPONSE-CONFIG-TOP-SECRET',
    'AXIOS-MESSAGE-TOP-SECRET',
    'RESPONSE-BODY-TOP-SECRET',
  ]
  const raw = new Error(`request failed ${markers[3]}`)
  raw.config = {
    method: 'post',
    url: '/ai/native/video/kepu/config?token=QUERY-TOP-SECRET',
    data: { api_key: markers[0] },
    headers: { Authorization: `Bearer ${markers[1]}` },
  }
  raw.request = { privateHeader: markers[1] }
  raw.response = {
    status: 401,
    data: { detail: '凭证无效', debug: markers[4] },
    config: { data: markers[2], headers: { Authorization: markers[1] } },
  }
  raw.cause = new Error(markers[3])

  const safe = toSafeApiError(raw)
  const logArgs = safeApiLogArgs('[API Response Error]', safe)
  const rendered = `${graphText(safe)}\n${JSON.stringify(safe)}\n${graphText(logArgs)}`

  assert.notEqual(safe, raw)
  assert.equal(safe.response.status, 401)
  assert.equal(safe.response.data.detail, '凭证无效')
  assert.equal(safe.method, 'POST')
  assert.equal(safe.path, '/ai/native/video/kepu/config')
  assert.equal(safe.cause, undefined)
  assert.equal(safe.config, undefined)
  assert.equal(safe.request, undefined)
  for (const marker of [...markers, 'QUERY-TOP-SECRET']) {
    assert.equal(rendered.includes(marker), false)
  }
})

test('network and credential-bearing endpoint failures keep existing caller behavior safely', () => {
  for (const path of [
    '/ai/native/video/kepu/config/llm-providers/mimo/models/refresh',
    '/ai/native/video/kepu/config',
    '/ai/native/video/kepu/config/test-tts',
  ]) {
    const raw = new Error('NETWORK-CREDENTIAL-TOP-SECRET')
    raw.config = {
      method: 'post',
      url: path,
      data: { api_key: 'PAYLOAD-CREDENTIAL-TOP-SECRET' },
    }

    const safe = toSafeApiError(raw)

    assert.equal(safe.message, '网络异常')
    assert.equal(safe.response, undefined)
    assert.equal(graphText(safe).includes('TOP-SECRET'), false)
    assert.deepEqual(safeApiLogArgs('[API Response Error]', safe), [
      '[API Response Error]', 'POST', path, 'network', '-',
    ])
  }
})

test('unsafe server detail falls back instead of echoing a credential', () => {
  const credential = 'sk-live-DETAIL-MARKER-1234'
  const raw = {
    config: {
      method: 'put',
      url: '/ai/native/video/kepu/config',
      data: { llm: { api_key: credential } },
    },
    response: {
      status: 400,
      data: { detail: `provider rejected ${credential}` },
    },
  }

  const safe = toSafeApiError(raw)

  assert.equal(safe.response.data.detail, '请求失败')
  assert.equal(graphText(safe).includes(credential), false)
})
