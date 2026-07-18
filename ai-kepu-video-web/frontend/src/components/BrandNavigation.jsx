import { FileText, FolderKanban, Settings } from 'lucide-react'
import { NavLink } from 'react-router'

const navigationItems = [
  { to: '/', label: '文稿', icon: FileText, end: true },
  { to: '/assets', label: '项目资产', icon: FolderKanban },
  { to: '/settings', label: 'API 配置', icon: Settings }
]

export function BrandNavigation() {
  return (
    <header className="app-header">
      <NavLink className="brand" to="/" aria-label="InsightCut 首页">
        <span className="brand-mark" aria-hidden="true">
          <span className="brand-glow" />
          <span className="brand-inner" />
          <span className="brand-reticles">
            <span className="brand-reticle-row">
              <span className="brand-reticle-corner brand-reticle-tl" />
              <span className="brand-reticle-corner brand-reticle-tr" />
            </span>
            <span className="brand-reticle-row">
              <span className="brand-reticle-corner brand-reticle-bl" />
              <span className="brand-reticle-corner brand-reticle-br" />
            </span>
          </span>
          <span className="brand-dot" />
        </span>
        <span>
          <strong>InsightCut</strong>
          <small>AI 视频工作台</small>
        </span>
      </NavLink>

      <nav className="primary-navigation" aria-label="主导航">
        {navigationItems.map(({ to, label, icon: Icon, end }) => (
          <NavLink key={to} to={to} end={end} className={({ isActive }) => `nav-link${isActive ? ' is-active' : ''}`}>
            <Icon size={16} aria-hidden="true" />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>
    </header>
  )
}
