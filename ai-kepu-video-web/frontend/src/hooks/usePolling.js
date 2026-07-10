import { useCallback, useEffect, useRef, useState } from 'react'
import { getTaskStatus } from '../api/task'

/**
 * Polls a task until it reaches a terminal state or repeated requests fail.
 */
export function usePolling(taskId, interval = 2000) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [isPolling, setIsPolling] = useState(false)
  const timerRef = useRef(null)
  const retryCountRef = useRef(0)
  const isPollingRef = useRef(false)

  const stopPolling = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }
    isPollingRef.current = false
    setIsPolling(false)
  }, [])

  const poll = useCallback(async () => {
    try {
      const result = await getTaskStatus(taskId)
      setData(result)
      setError(null)
      retryCountRef.current = 0

      if (result.status === 'completed' || result.status === 'failed') {
        stopPolling()
      }
    } catch (pollError) {
      console.error('[Polling Error]', pollError)
      retryCountRef.current += 1

      if (retryCountRef.current >= 3) {
        setError('查询失败，请刷新页面重试')
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

  useEffect(() => stopPolling, [stopPolling])

  return { data, error, isPolling, startPolling, stopPolling }
}
