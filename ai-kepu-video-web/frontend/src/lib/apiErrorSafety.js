const SAFE_METHODS = new Set(['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS'])
const SENSITIVE_TEXT = /(?:api[\s_-]*key|authorization|bearer|token\s*[=:]|secret)/i
const SENSITIVE_FIELD = /(?:key|token|authorization|secret|password|credential)/i

function requestSecrets(...configs) {
  const values = new Set()
  const seen = new Set()
  const collect = (value, collectAll = false) => {
    if (typeof value === 'string') {
      const normalized = value.trim()
      if (!normalized) return
      if ((normalized.startsWith('{') || normalized.startsWith('['))) {
        try {
          collect(JSON.parse(normalized), collectAll)
          return
        } catch {
          // Keep processing as an opaque string.
        }
      }
      if (collectAll && normalized.length >= 4) values.add(normalized)
      return
    }
    if (!value || typeof value !== 'object' || seen.has(value)) return
    seen.add(value)
    if (Array.isArray(value)) {
      value.forEach(item => collect(item, collectAll))
      return
    }
    for (const [key, item] of Object.entries(value)) {
      collect(item, collectAll || SENSITIVE_FIELD.test(key))
    }
  }

  for (const config of configs) {
    collect(config?.data, true)
    collect(config?.params, true)
    collect(config?.headers, false)
  }
  return [...values]
}

function containsRequestSecret(value, secrets) {
  return secrets.some(secret => value.includes(secret))
}

function safeMethod(config = {}) {
  const method = String(config?.method || '').trim().toUpperCase()
  return SAFE_METHODS.has(method) ? method : 'UNKNOWN'
}

function safePath(config = {}, secrets = []) {
  const url = String(config?.url || '').trim()
  if (!url) return '/'
  try {
    const path = new URL(url, 'http://insightcut.local').pathname || '/'
    return path.length <= 300
      && !SENSITIVE_TEXT.test(path)
      && !containsRequestSecret(path, secrets)
      ? path
      : '/'
  } catch {
    return '/'
  }
}

function safeStatus(response) {
  const status = Number(response?.status)
  return Number.isInteger(status) && status >= 100 && status <= 599 ? status : null
}

function safeDetail(response, secrets = []) {
  const detail = response?.data?.detail
  if (typeof detail !== 'string') return '请求失败'
  const normalized = detail.replace(/[\r\n\t]+/g, ' ').trim()
  if (!normalized
    || normalized.length > 300
    || SENSITIVE_TEXT.test(normalized)
    || containsRequestSecret(normalized, secrets)) {
    return '请求失败'
  }
  return normalized
}

function safeCorrelationId(response, secrets = []) {
  const value = response?.data?.correlation_id
    || response?.headers?.['x-correlation-id']
    || response?.headers?.['x-request-id']
  const normalized = String(value || '').trim()
  if (!/^[A-Za-z0-9._-]{1,64}$/.test(normalized)
    || SENSITIVE_TEXT.test(normalized)
    || containsRequestSecret(normalized, secrets)) return ''
  return normalized
}

function isRequestCancellation(error) {
  return Boolean(
    error?.code === 'ERR_CANCELED'
    || error?.name === 'CanceledError'
    || error?.__CANCEL__ === true
    || error?.kind === 'cancelled'
  )
}

export class SafeApiError extends Error {
  constructor({ status = null, detail = '', method = 'UNKNOWN', path = '/', correlationId = '', cancelled = false } = {}) {
    super(cancelled ? '请求已取消' : status === null ? '网络异常' : detail || '请求失败')
    this.name = 'SafeApiError'
    this.kind = cancelled ? 'cancelled' : status === null ? 'network' : 'http'
    this.status = status
    this.method = method
    this.path = path
    this.correlationId = correlationId
    if (status !== null) {
      this.response = { status, data: { detail: detail || '请求失败' } }
    }
  }
}

export function toSafeApiError(rawError) {
  if (rawError instanceof SafeApiError) return rawError
  const response = rawError?.response
  const status = safeStatus(response)
  const config = rawError?.config || response?.config
  const secrets = requestSecrets(rawError?.config, response?.config)
  return new SafeApiError({
    status,
    detail: status === null ? '' : safeDetail(response, secrets),
    method: safeMethod(config),
    path: safePath(config, secrets),
    correlationId: safeCorrelationId(response, secrets),
    cancelled: isRequestCancellation(rawError),
  })
}

export function safeApiRequestLogArgs(label, config, status = null) {
  const args = [
    label,
    safeMethod(config),
    safePath(config, requestSecrets(config)),
  ]
  if (status !== null) args.push(safeStatus({ status }) || 'unknown')
  return args
}

export function safeApiLogArgs(label, safeError) {
  const error = safeError instanceof SafeApiError ? safeError : toSafeApiError(safeError)
  return [
    label,
    error.method,
    error.path,
    error.status === null ? 'network' : error.status,
    error.correlationId || '-',
  ]
}
