import { useCallback, useEffect, useRef, useState } from 'react'

import { createPollingEngine } from './pollingEngine'

const IDLE_STATE = Object.freeze({
  status: 'idle',
  resourceKey: null,
  generation: 0,
  active: false,
  paused: false,
  disposed: false,
  inFlight: false,
  refreshQueued: false,
  consecutiveFailures: 0,
  error: null,
})

/**
 * React adapter for the single-flight polling engine.
 *
 * Callback refs keep the engine stable while resourceKey advances its
 * generation. A response from an older task/job is consequently ignored even
 * when the underlying HTTP request cannot be cancelled.
 */
export function usePollingResource({
  resourceKey,
  enabled = true,
  request,
  interval = 2000,
  maxConsecutiveFailures = 3,
  isTerminalError,
  onData,
  onError,
  onTerminalError,
}) {
  const requestRef = useRef(request)
  const onDataRef = useRef(onData)
  const onErrorRef = useRef(onError)
  const onTerminalErrorRef = useRef(onTerminalError)
  const isTerminalErrorRef = useRef(isTerminalError)
  const engineRef = useRef(null)
  const [state, setState] = useState(IDLE_STATE)
  const [terminalError, setTerminalError] = useState(null)

  requestRef.current = request
  onDataRef.current = onData
  onErrorRef.current = onError
  onTerminalErrorRef.current = onTerminalError
  isTerminalErrorRef.current = isTerminalError

  useEffect(() => {
    let mounted = true
    const engine = createPollingEngine({
      interval,
      maxConsecutiveFailures,
      request: (key, metadata) => requestRef.current(key, metadata),
      onData: (data, metadata) => onDataRef.current?.(data, metadata),
      onError: (error, metadata) => {
        if (isTerminalErrorRef.current?.(error, metadata)) {
          if (mounted) setTerminalError(error)
          onTerminalErrorRef.current?.(error, metadata)
          engine.stop()
          return
        }
        onErrorRef.current?.(error, metadata)
      },
      onStateChange: nextState => { if (mounted) setState(nextState) },
    })
    engineRef.current = engine
    setState(engine.getState())

    return () => {
      mounted = false
      engine.dispose()
      if (engineRef.current === engine) engineRef.current = null
    }
  }, [interval, maxConsecutiveFailures])

  useEffect(() => {
    setTerminalError(null)
    const engine = engineRef.current
    if (!engine) return
    if (!enabled || resourceKey === null || resourceKey === undefined || resourceKey === '') {
      engine.stop()
      return
    }
    engine.start(resourceKey)
  }, [enabled, resourceKey])

  useEffect(() => {
    const updateVisibility = () => engineRef.current?.setVisible(document.visibilityState !== 'hidden')
    document.addEventListener('visibilitychange', updateVisibility)
    updateVisibility()
    return () => document.removeEventListener('visibilitychange', updateVisibility)
  }, [])

  const refresh = useCallback(() => engineRef.current?.refresh() || false, [])
  const reconnect = useCallback(() => {
    setTerminalError(null)
    return engineRef.current?.refresh() || false
  }, [])

  return {
    ...state,
    error: terminalError || state.error,
    terminalError,
    refresh,
    reconnect,
  }
}
