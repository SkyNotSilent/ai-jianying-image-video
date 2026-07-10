import test from 'node:test'
import assert from 'node:assert/strict'

import { normalizeExtractPath, validateExtractPath } from '../src/lib/exportPath.js'

test('normalizes quoted Mac paths and Windows separators', () => {
  assert.equal(
    normalizeExtractPath('  "\\Users\\mei\\Movies\\Jianying\\"  ', 'mac'),
    '/Users/mei/Movies/Jianying',
  )
})

test('accepts Mac absolute paths while keeping conversion warnings non-blocking', () => {
  assert.deepEqual(validateExtractPath('"\\Users\\mei\\Jianying"', 'mac'), {
    valid: true,
    normalized: '/Users/mei/Jianying',
    issues: [
      '检测到路径外侧引号，下载时会自动移除',
      '检测到 Windows 反斜杠，下载时会转换为 Mac 正斜杠',
    ],
  })
})

test('rejects relative Mac paths', () => {
  const result = validateExtractPath('Users/mei/Jianying', 'mac')
  assert.equal(result.valid, false)
  assert.ok(result.issues.includes('Mac 路径必须以 / 开头'))
})

test('accepts Windows drive and UNC paths after slash conversion', () => {
  assert.equal(validateExtractPath('D:/Jianying/Drafts/', 'windows').valid, true)
  assert.equal(validateExtractPath('D:/Jianying/Drafts/', 'windows').normalized, 'D:\\Jianying\\Drafts')
  assert.equal(validateExtractPath('\\\\server\\share\\drafts\\', 'windows').valid, true)
})

test('rejects empty and relative Windows paths', () => {
  assert.equal(validateExtractPath('', 'windows').issues[0], '请填写剪映草稿解压路径')
  assert.equal(validateExtractPath('Jianying\\Drafts', 'windows').valid, false)
})
