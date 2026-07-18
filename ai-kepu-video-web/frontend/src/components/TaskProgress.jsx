import { Check, LoaderCircle, X } from 'lucide-react'
import { calculateProgress, formatDuration, getStepLabel } from '../utils/format'

export function TaskProgress({ steps = [], currentStep }) {
  const percentage = calculateProgress(steps)
  const activeStep = steps.find(step => step.name === currentStep)
  const label = activeStep ? getStepLabel(activeStep.name) : '正在初始化...'
  const detail = activeStep?.status === 'processing' && activeStep.total
    ? `${label} ${activeStep.progress || 0}/${activeStep.total}`
    : label

  return (
    <section className="task-progress" aria-label="任务总进度">
      <div className="progress-ring" style={{ '--progress': `${percentage * 3.6}deg` }}>
        <div className="progress-ring-inner"><strong>{percentage}%</strong></div>
      </div>
      <div className="progress-copy">
        <span>生成进度</span>
        <strong>{detail}</strong>
      </div>
    </section>
  )
}

export function TaskStep({ step, isLast }) {
  const status = step.status || 'pending'
  const progress = Number(step.progress) || 0
  const total = Number(step.total) || 0
  const percentage = total ? Math.min(100, Math.round((progress / total) * 100)) : 0
  const Indicator = status === 'processing' ? LoaderCircle : status === 'completed' ? Check : status === 'failed' ? X : null

  return (
    <article className={`task-step task-step-${status}`}>
      <div className="task-step-rail" aria-hidden="true">
        <span className="task-step-dot">{Indicator && <Indicator size={14} />}</span>
        {!isLast && <span className="task-step-line" />}
      </div>
      <div className="task-step-body">
        <div className="task-step-heading">
          <strong>{getStepLabel(step.name)}</strong>
          {status === 'completed' && step.duration ? <span>{formatDuration(step.duration)}</span> : null}
          {status === 'processing' ? <span className="status-chip">进行中</span> : null}
          {status === 'failed' ? <span className="status-chip status-chip-danger">失败</span> : null}
        </div>
        {status === 'processing' && total ? (
          <div className="task-step-meter" aria-label={`${getStepLabel(step.name)} ${percentage}%`}>
            <span style={{ width: `${percentage}%` }} />
            <small>{progress}/{total}</small>
          </div>
        ) : null}
      </div>
    </article>
  )
}
