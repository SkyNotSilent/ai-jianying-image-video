const defaultScheduler = {
  setTimeout(callback, delay) {
    return globalThis.setTimeout(callback, delay)
  },
  clearTimeout(timerId) {
    globalThis.clearTimeout(timerId)
  },
}

function noop() {}

/**
 * A framework-agnostic polling loop shared by task and export-job consumers.
 *
 * The next request is scheduled only after the current request settles. Calling
 * refresh while a request is in flight queues one (and only one) immediate
 * follow-up request. Resource changes advance the generation so late responses
 * from the previous resource are ignored.
 */
export function createPollingEngine({
  request,
  interval = 2000,
  maxConsecutiveFailures = 3,
  scheduler = defaultScheduler,
  onData = noop,
  onError = noop,
  onStateChange = noop,
} = {}) {
  if (typeof request !== 'function') {
    throw new TypeError('polling request must be a function')
  }
  if (!Number.isFinite(interval) || interval < 0) {
    throw new RangeError('polling interval must be a non-negative number')
  }
  if (!Number.isInteger(maxConsecutiveFailures) || maxConsecutiveFailures < 1) {
    throw new RangeError('maxConsecutiveFailures must be a positive integer')
  }
  if (typeof scheduler?.setTimeout !== 'function' || typeof scheduler?.clearTimeout !== 'function') {
    throw new TypeError('polling scheduler must provide setTimeout and clearTimeout')
  }

  let resourceKey = null
  let generation = 0
  let active = false
  let paused = false
  let disposed = false
  let timerId = null
  let currentRequest = null
  let refreshQueued = false
  let consecutiveFailures = 0
  let persistentError = null

  const snapshot = () => {
    let status = 'idle'
    if (disposed) status = 'disposed'
    else if (active && persistentError) status = 'error'
    else if (active && paused) status = 'paused'
    else if (active && currentRequest?.generation === generation) status = 'polling'
    else if (active) status = 'scheduled'

    return Object.freeze({
      status,
      resourceKey,
      generation,
      active,
      paused,
      disposed,
      inFlight: Boolean(currentRequest?.generation === generation),
      refreshQueued,
      consecutiveFailures,
      error: persistentError,
    })
  }

  const emitState = () => {
    try {
      onStateChange(snapshot())
    } catch {
      // Consumer callbacks must not stop the polling state machine.
    }
  }

  const clearTimer = () => {
    if (timerId === null) return
    scheduler.clearTimeout(timerId)
    timerId = null
  }

  const isCurrent = (token) => (
    !disposed
    && active
    && token.generation === generation
    && Object.is(token.resourceKey, resourceKey)
    && currentRequest === token
  )

  let dispatch

  const schedule = (delay) => {
    if (disposed || !active || paused || persistentError || timerId !== null) return
    const scheduledGeneration = generation
    const scheduledResourceKey = resourceKey
    timerId = scheduler.setTimeout(() => {
      timerId = null
      if (
        disposed
        || !active
        || paused
        || persistentError
        || scheduledGeneration !== generation
        || !Object.is(scheduledResourceKey, resourceKey)
      ) {
        emitState()
        return
      }
      dispatch()
    }, delay)
    emitState()
  }

  dispatch = () => {
    if (disposed || !active || paused || persistentError) return false
    if (currentRequest?.generation === generation) {
      refreshQueued = true
      emitState()
      return false
    }

    clearTimer()
    const controller = typeof AbortController === 'function' ? new AbortController() : null
    const token = { generation, resourceKey, controller }
    currentRequest = token
    emitState()

    Promise.resolve()
      .then(() => request(token.resourceKey, {
        generation: token.generation,
        signal: controller?.signal,
      }))
      .then((data) => {
        if (!isCurrent(token)) return
        consecutiveFailures = 0
        persistentError = null
        try {
          onData(data, { resourceKey: token.resourceKey, generation: token.generation })
        } catch {
          // Consumer callbacks must not turn a successful request into a retry.
        }
      })
      .catch((error) => {
        if (!isCurrent(token)) return
        consecutiveFailures += 1
        const persistent = consecutiveFailures >= maxConsecutiveFailures
        const retryDelay = persistent
          ? null
          : interval * (2 ** (consecutiveFailures - 1))
        if (persistent) {
          persistentError = error
          refreshQueued = false
        }
        try {
          onError(error, {
            resourceKey: token.resourceKey,
            generation: token.generation,
            consecutiveFailures,
            persistent,
            retryDelay,
          })
        } catch {
          // Consumer callbacks must not stop retry accounting.
        }
      })
      .finally(() => {
        if (!isCurrent(token)) return
        currentRequest = null

        if (persistentError || disposed || !active || paused) {
          emitState()
          return
        }

        if (refreshQueued) {
          refreshQueued = false
          schedule(0)
          return
        }

        const delay = consecutiveFailures > 0
          ? interval * (2 ** (consecutiveFailures - 1))
          : interval
        schedule(delay)
      })

    return true
  }

  const beginGeneration = (nextResourceKey) => {
    clearTimer()
    currentRequest?.controller?.abort()
    generation += 1
    resourceKey = nextResourceKey
    currentRequest = null
    refreshQueued = false
    consecutiveFailures = 0
    persistentError = null
  }

  const start = (nextResourceKey = resourceKey) => {
    if (disposed) return false
    if (nextResourceKey === null || nextResourceKey === undefined) {
      throw new TypeError('polling resourceKey is required')
    }

    const changed = !Object.is(nextResourceKey, resourceKey)
    if (changed || !active) beginGeneration(nextResourceKey)
    active = true

    if (persistentError) {
      beginGeneration(nextResourceKey)
      active = true
    }

    if (!paused && !currentRequest && timerId === null) dispatch()
    else emitState()
    return true
  }

  const setResourceKey = (nextResourceKey) => {
    if (disposed) return false
    if (nextResourceKey === null || nextResourceKey === undefined) {
      stop()
      resourceKey = null
      emitState()
      return true
    }
    if (Object.is(nextResourceKey, resourceKey)) return false

    const wasActive = active
    beginGeneration(nextResourceKey)
    active = wasActive
    if (active && !paused) dispatch()
    else emitState()
    return true
  }

  const refresh = () => {
    if (disposed || !active || resourceKey === null || resourceKey === undefined) return false

    if (persistentError) {
      beginGeneration(resourceKey)
      active = true
    }
    if (paused) {
      refreshQueued = true
      emitState()
      return true
    }
    if (currentRequest?.generation === generation) {
      refreshQueued = true
      emitState()
      return true
    }

    clearTimer()
    return dispatch()
  }

  const pause = () => {
    if (disposed || paused) return false
    paused = true
    clearTimer()
    emitState()
    return true
  }

  const resume = () => {
    if (disposed || !paused) return false
    paused = false
    if (!active || persistentError || currentRequest?.generation === generation) {
      emitState()
      return true
    }
    refreshQueued = false
    dispatch()
    return true
  }

  const setVisible = (visible) => (visible ? resume() : pause())

  const stop = () => {
    if (disposed) return false
    clearTimer()
    currentRequest?.controller?.abort()
    generation += 1
    active = false
    currentRequest = null
    refreshQueued = false
    consecutiveFailures = 0
    persistentError = null
    emitState()
    return true
  }

  const dispose = () => {
    if (disposed) return false
    stop()
    disposed = true
    resourceKey = null
    emitState()
    return true
  }

  return Object.freeze({
    start,
    setResourceKey,
    refresh,
    pause,
    resume,
    setVisible,
    stop,
    dispose,
    getState: snapshot,
  })
}
