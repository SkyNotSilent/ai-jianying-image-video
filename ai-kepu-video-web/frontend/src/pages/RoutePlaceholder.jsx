import { useEffect } from 'react'
import { ArrowRight, CircleDot, Wrench } from 'lucide-react'
import { Link } from 'react-router'
import { EmptyState } from '../components/StatusStates'

export function RoutePlaceholder({ title, description, route }) {
  useEffect(() => {
    document.title = `${title} - InsightCut`
  }, [title])

  return (
    <main className="workspace-shell">
      <section className="workspace-heading">
        <div>
          <p className="eyebrow"><CircleDot size={14} aria-hidden="true" />工作区</p>
          <h1>{title}</h1>
          <p>{description}</p>
        </div>
        <Link className="button button-primary" to="/manuscript"><span>开始文稿</span><ArrowRight size={16} aria-hidden="true" /></Link>
      </section>
      <section className="foundation-panel" aria-label={`${title} 页面基础`}>
        <div className="panel-status"><Wrench size={17} aria-hidden="true" /><span>React 迁移进行中</span></div>
        <EmptyState title={`${title} 页面待迁移`} description={`当前路由 ${route} 已连接到 React 运行时。后续任务会在此处接入完整的业务页面。`} />
      </section>
    </main>
  )
}
