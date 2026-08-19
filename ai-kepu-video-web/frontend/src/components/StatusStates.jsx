import { LoaderCircle } from 'lucide-react'
import { EmptyStateCard } from './ui/EmptyStateCard'

export function LoadingState({ label = '正在加载...' }) {
  return <div className="status-state" role="status"><LoaderCircle className="spin" size={22} aria-hidden="true" /><span>{label}</span></div>
}

export function EmptyState({ title = '暂无内容', description = '开始创建内容后，它会显示在这里。', action, variant = 'media', eyebrow, compact = false, className = '' }) {
  return <EmptyStateCard variant={variant} eyebrow={eyebrow} title={title} description={description} action={action} compact={compact} className={className} />
}
