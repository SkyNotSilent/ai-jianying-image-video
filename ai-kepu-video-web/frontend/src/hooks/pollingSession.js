export function createPollingSession() {
  let taskId = null
  let generation = 0

  return {
    transition(nextTaskId) {
      if (taskId === nextTaskId) return { changed: false, generation }
      taskId = nextTaskId
      generation += 1
      return { changed: true, generation }
    },
    capture() {
      return generation
    },
    invalidate() {
      generation += 1
      return generation
    },
    isCurrent(requestGeneration) {
      return requestGeneration === generation
    },
  }
}
