import { useEffect, useRef, useState } from 'react'
import { ArrowRight, CircleAlert, FolderKanban, X } from 'lucide-react'
import { useNavigate, useParams } from 'react-router'
import { Modal } from '../components/Modal'
import { TaskProgress, TaskStep } from '../components/TaskProgress'
import { usePolling } from '../hooks/usePolling'
import { listDrafts } from '../utils/projectDrafts'
import './creation-flow.css'

const loadingTasks = ['正在分析文案并生成分镜脚本...', '正在生成画面提示词...', '正在匹配配音参数...', '正在生成分镜图片...', '正在合成音频和字幕...', '正在整理预览素材...']

export function ProcessPage() {
  const { taskId } = useParams()
  const navigate = useNavigate()
  const { data: task, error, startPolling } = usePolling(taskId, 2000)
  const [loading, setLoading] = useState(true)
  const [loadingPercent, setLoadingPercent] = useState(0)
  const [showError, setShowError] = useState(false)
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

  const retry = () => {
    const draft = listDrafts().find(item => item.created_task_id === taskId)
    navigate(draft?.draft_id ? `/production/${draft.draft_id}` : '/assets')
  }
  const recover = () => navigate(`/preview/${taskId}`)
  const loadingTask = loadingTasks[Math.min(Math.floor(loadingPercent / 16), loadingTasks.length - 1)]

  return (
    <main className="process-page">
      <button type="button" className="process-exit" onClick={() => navigate('/assets')}><X size={17} />退出</button>
      {loading ? <section className="process-loading" aria-live="polite"><div className="initial-progress-ring" style={{ '--progress': `${loadingPercent * 3.6}deg` }}><span>{Math.round(loadingPercent)}%</span></div><p>任务初始化</p><strong>{loadingTask}</strong><small>退出后任务会继续在后台生成</small></section> : null}
      {!loading && task ? <div className="process-workspace">
        <section className="process-overview"><TaskProgress steps={task.progress?.steps || []} currentStep={task.progress?.current_step} />{task.status === 'pending' ? <p className="pending-notice">任务已提交，等待调度执行</p> : <p className="background-notice">可以退出此页面，任务会继续在后台生成</p>}</section>
        <section className="process-steps"><header><h1>执行步骤</h1><span>{task.progress?.current_step || 'pending'}</span></header><div>{(task.progress?.steps || []).map((step, index, items) => <TaskStep key={step.name} step={step} isLast={index === items.length - 1} />)}</div></section>
        {task.status === 'failed' ? <section className="recovery-notice"><FolderKanban size={23} /><div><h2>已生成内容仍可查看</h2><p>任务失败只表示后续流程停止，已经保存的分镜、图片、配音和草稿素材会保留在预览编辑页。</p></div><button type="button" className="button button-secondary" onClick={recover}>查看已保存素材<ArrowRight size={16} /></button></section> : null}
      </div> : null}
      <Modal open={showError} title="生成失败" onClose={() => setShowError(false)} footer={<><button type="button" className="button button-secondary" onClick={() => setShowError(false)}>关闭</button><button type="button" className="button button-secondary" onClick={recover}>查看已保存素材</button><button type="button" className="button button-primary" onClick={retry}>重新生成</button></>}><div className="process-error"><CircleAlert size={20} /><div><p>{task?.error ? '生成失败，请重试' : error || '查询任务状态失败，请重试'}</p>{task?.error ? <pre>{task.error}</pre> : null}</div></div></Modal>
    </main>
  )
}
