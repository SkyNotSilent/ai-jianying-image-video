import { FilePlus2, LoaderCircle } from 'lucide-react'

export function LoadingState({ label = '正在加载...' }) {
  return <div className="status-state" role="status"><LoaderCircle className="spin" size={22} aria-hidden="true" /><span>{label}</span></div>
}

export function EmptyState({ title = '暂无内容', description = '开始创建内容后，它会显示在这里。', action }) {
  return (
    <section className="empty-state">
      <FilePlus2 size={28} aria-hidden="true" />
      <h2>{title}</h2>
      <p>{description}</p>
      {action}
    </section>
  )
}
