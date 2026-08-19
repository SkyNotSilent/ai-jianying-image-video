const ACTIVE_EXPORT_STATUSES = new Set(['pending', 'processing'])

export function isActiveExportJob(job) {
  return Boolean(job?.job_id && ACTIVE_EXPORT_STATUSES.has(job.status))
}

/**
 * Builds a stable polling identity from the task and the exact backend jobs.
 * Completed jobs are excluded, and object insertion order cannot restart the
 * polling engine or accidentally replace a retained job id.
 */
export function buildExportPollingKey(taskId, jobs) {
  if (!taskId || !jobs || typeof jobs !== 'object') return null
  const activeJobs = Object.entries(jobs)
    .filter(([, job]) => isActiveExportJob(job))
    .map(([target, job]) => ({ target, jobId: job.job_id }))
    .sort((left, right) => (
      left.target.localeCompare(right.target) || left.jobId.localeCompare(right.jobId)
    ))

  if (!activeJobs.length) return null
  return JSON.stringify({ taskId, jobs: activeJobs })
}

