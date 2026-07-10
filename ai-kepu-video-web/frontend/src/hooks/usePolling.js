import { useCallback, useEffect, useRef, useState } from 'react'
import { getTaskStatus } from '../api/task'
import { createPollingSession } from './pollingSession'

/**
 * Polls a task until it reaches a terminal state or repeated requests fail.
 */
export function usePolling(taskId, interval = 2000) {
  const [state, setState] = useState({ taskId: null, data: null, error: null })
  const [isPolling, setIsPolling] = useState(false)
  const timerRef = useRef(null)
  const retryCountRef = useRef(0)
  const isPollingRef = useRef(false)
  const sessionRef = useRef(null)
  if (!sessionRef.current) sessionRef.current = createPollingSession()

  const stopPolling = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }
    sessionRef.current.invalidate()
    isPollingRef.current = false
    setIsPolling(false)
  }, [])

  const poll = useCallback(async () => {
    const requestGeneration = sessionRef.current.capture()
    const requestTaskId = taskId
    try {
      const result = await getTaskStatus(requestTaskId)
      if (!sessionRef.current.isCurrent(requestGeneration)) return
      setState({ taskId: requestTaskId, data: result, error: null })
      retryCountRef.current = 0

      if (result.status === 'completed' || result.status === 'failed') {
        stopPolling()
      }
    } catch (pollError) {
      if (!sessionRef.current.isCurrent(requestGeneration)) return
      console.error('[Polling Error]', pollError)
      retryCountRef.current += 1

      if (retryCountRef.current >= 3) {
        setState({ taskId: requestTaskId, data: null, error: '查询失败，请刷新页面重试' })
        stopPolling()
      }
    }
  }, [stopPolling, taskId])

  const startPolling = useCallback(() => {
    if (isPollingRef.current) return

    retryCountRef.current = 0
    isPollingRef.current = true
    setIsPolling(true)
    poll()
    timerRef.current = setInterval(poll, interval)
  }, [interval, poll])

  useEffect(() => {
    stopPolling()
    sessionRef.current.transition(taskId)
    retryCountRef.current = 0
    setState({ taskId, data: null, error: null })
  }, [stopPolling, taskId])

  useEffect(() => stopPolling, [stopPolling])

  const currentState = state.taskId === taskId ? state : { data: null, error: null }
  return { data: currentState.data, error: currentState.error, isPolling, startPolling, stopPolling }
}
