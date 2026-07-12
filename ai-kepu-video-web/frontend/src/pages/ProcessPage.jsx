import { useEffect, useRef, useState } from 'react'
import { ArrowRight, CircleAlert, FolderKanban, LoaderCircle, X } from 'lucide-react'
import { useNavigate, useParams } from 'react-router'
import { getSegments, resumeTask } from '../api/task'
import { Modal } from '../components/Modal'
import { TaskProgress, TaskStep } from '../components/TaskProgress'
import { usePolling } from '../hooks/usePolling'
import { listDrafts } from '../utils/projectDrafts'
import { deriveTaskState } from '../utils/taskState'
import { toast } from '../lib/toast'
import './creation-flow.css'

const loadingTasks = ['正在分析文案并生成分镜脚本...', '正在生成画面提示词...', '正在匹配配音参数...', '正在生成分镜图片...', '正在合成音频和字幕...', '正在整理预览素材...']

export function ProcessPage() {
  const { taskId } = useParams()
  const navigate = useNavigate()
  const { data: task, error, startPolling } = usePolling(taskId, 2000)
  const [loading, setLoading] = useState(true)
  const [loadingPercent, setLoadingPercent] = useState(0)
  const [showError, setShowError] = useState(false)
  const [resuming, setResuming] = useState(false)
  const [segments, setSegments] = useState([])
  const [segmentsLoaded, setSegmentsLoaded] = useState(false)
  const loadingTimer = useRef(null)
  const finishTimer = useRef(null)

  useEffect(() => {
    if (!taskId) { navigate('/', { replace: true }); return undefined }
    setLoading(true)
    setLoadingPercent(0)
    setShowError(false)
    startPolling()
    loadingTimer.current = window.setInterval(() => setLoadingPercent(value => Math.min(92, value + Math.random() * 8 + 2)), 240)
    return () => { window.clearInterval(loadingTimer.current); window.clearTimeout(finishTimer.current) }
  }, [navigate, startPolling, taskId])

  useEffect(() => {
    if (!task && !error) return
    if (loading) {
      window.clearInterval(loadingTimer.current)
      setLoadingPercent(100)
      finishTimer.current = window.setTimeout(() => setLoading(false), 260)
    }
  }, [error, loading, task])

  useEffect(() => {
    if (task?.status === 'completed') navigate(`/preview/${taskId}`, { replace: true })
    if (task?.status === 'failed') setShowError(true)
  }, [navigate, task?.status, taskId])

  useEffect(() => { if (error) setShowError(true) }, [error])

  useEffect(() => {
    let active = true
    setSegments([])
    setSegmentsLoaded(task?.status !== 'failed')
    if (task?.status !== 'failed') return () => { active = false }
    getSegments(taskId)
      .then(items => { if (active) setSegments(Array.isArray(items) ? items : []) })
      .catch(segmentError => console.warn('加载已保存分镜失败', segmentError))
      .finally(() => { if (active) setSegmentsLoaded(true) })
    return () => { active = false }
  }, [task?.status, taskId])

  const retry = () => {
    const draft = listDrafts().find(item => item.created_task_id === taskId)
    navigate(draft?.draft_id ? `/production/${draft.draft_id}` : '/assets')
  }
  const recover = () => navigate(`/preview/${taskId}`)
  const resumeGeneration = async () => {
    if (resuming) return
    setResuming(true)
    try {
      await resumeTask(taskId)
      setShowError(false)
      startPolling()
      toast.success('任务已继续生成')
    } catch (resumeError) {
      console.warn('继续生成失败', resumeError)
      toast.error('任务暂时无法继续，请稍后重试')
    } finally {
      setResuming(false)
    }
  }
  const loadingTask = loadingTasks[Math.min(Math.floor(loadingPercent / 16), loadingTasks.length - 1)]
  const taskState = deriveTaskState({ task, segments })
  const canResume = taskState.key === 'interrupted'
  const checkingRecovery = task?.status === 'failed' && !segmentsLoaded

  return (
    <main className="process-page">
      <button type="button" className="process-exit" onClick={() => navigate('/assets')}><X size={17} />退出</button>
      {loading ? <section className="process-loading" aria-live="polite"><div className="initial-progress-ring" style={{ '--progress': `${loadingPercent * 3.6}deg` }}><span>{Math.round(loadingPercent)}%</span></div><p>任务初始化</p><strong>{loadingTask}</strong><small>退出后任务会继续在后台生成</small></section> : null}
      {!loading && task ? <div className="process-workspace">
        <section className="process-overview"><TaskProgress steps={task.progress?.steps || []} currentStep={task.progress?.current_step} />{task.status === 'pending' ? <p className="pending-notice">任务已提交，等待调度执行</p> : canResume ? <p className="interrupted-notice">生成已停止，已完成的内容和素材都已保存</p> : <p className="background-notice">可以退出此页面，任务会继续在后台生成</p>}</section>
        <section className="process-steps"><header><h1>执行步骤</h1><span>{task.progress?.current_step || 'pending'}</span></header><div>{(task.progress?.steps || []).map((step, index, items) => <TaskStep key={step.name} step={step} isLast={index === items.length - 1} />)}</div></section>
        {task.status === 'failed' && !canResume ? <section className="recovery-notice"><FolderKanban size={23} /><div><h2>已生成内容仍可查看</h2><p>任务失败只表示后续流程停止，已经保存的分镜、图片、配音和草稿素材会保留在预览编辑页。</p></div><button type="button" className="button button-secondary" onClick={recover}>查看已保存素材<ArrowRight size={16} /></button></section> : null}
        {canResume ? <section className="recovery-notice recovery-notice-interrupted"><FolderKanban size={23} /><div><h2>可以从中断处继续</h2><p>继续后只会补齐缺失的提示词、图片和配音，已完成内容不会重复生成。</p></div><div className="recovery-actions"><button type="button" className="button button-secondary" onClick={recover}>查看已保存素材</button><button type="button" className="button button-primary" disabled={resuming} onClick={resumeGeneration}>{resuming ? <LoaderCircle className="spin" size={16} aria-hidden="true" /> : <ArrowRight size={16} aria-hidden="true" />}{resuming ? '正在继续...' : '继续生成'}</button></div></section> : null}
      </div> : null}
      <Modal open={showError} title="生成失败" onClose={() => setShowError(false)} footer={<><button type="button" className="button button-secondary" onClick={() => setShowError(false)}>关闭</button><button type="button" className="button button-secondary" onClick={recover}>查看已保存素材</button><button type="button" className="button button-primary" disabled={checkingRecovery || (canResume && resuming)} onClick={canResume ? resumeGeneration : retry}>{checkingRecovery ? '检查恢复点...' : canResume && resuming ? '正在继续...' : canResume ? '继续生成' : '重新生成'}</button></>}><div className="process-error"><CircleAlert size={20} /><div><p>{task?.error ? canResume ? '生成失败，可以从已保存的恢复点继续' : '生成失败，请重试' : error || '查询任务状态失败，请重试'}</p>{task?.error ? <pre>{task.error}</pre> : null}</div></div></Modal>
    </main>
  )
}
