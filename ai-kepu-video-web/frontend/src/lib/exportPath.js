export function detectTargetOS(platform = typeof navigator === 'undefined' ? '' : navigator.platform) {
  return /mac/i.test(platform || '') ? 'mac' : 'windows'
}

export function stripWrappingQuotes(value) {
  return String(value || '').trim().replace(/^['"]+|['"]+$/g, '').trim()
}

export function normalizeExtractPath(value, osName) {
  const cleaned = stripWrappingQuotes(value)
  if (!cleaned) return ''
  if (osName === 'mac') return cleaned.replace(/\\/g, '/').replace(/\/+$/g, '')
  return cleaned.replace(/\//g, '\\').replace(/\\+$/g, '')
}

export function isWindowsAbsolute(path) {
  return /^[A-Za-z]:\\/.test(path) || /^\\\\/.test(path)
}

export function validateExtractPath(value, osName) {
  const raw = String(value || '').trim()
  const normalized = normalizeExtractPath(raw, osName)
  const issues = []

  if (!normalized) {
    issues.push('请填写剪映草稿解压路径')
    return { valid: false, normalized, issues }
  }

  if (raw !== stripWrappingQuotes(raw)) issues.push('检测到路径外侧引号，下载时会自动移除')
  if (osName === 'mac') {
    if (raw.includes('\\')) issues.push('检测到 Windows 反斜杠，下载时会转换为 Mac 正斜杠')
    if (!normalized.startsWith('/')) issues.push('Mac 路径必须以 / 开头')
  } else {
    if (raw.includes('/')) issues.push('检测到正斜杠，下载时会转换为 Windows 反斜杠')
    if (!isWindowsAbsolute(normalized)) issues.push('Windows 路径必须是盘符路径或 UNC 路径')
  }

  const valid = !issues.some(issue => issue.includes('必须') || issue.includes('请填写'))
  return { valid, normalized, issues }
}
