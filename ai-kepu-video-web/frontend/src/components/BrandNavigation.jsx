import { useEffect, useState } from 'react'
import { FileText, FolderKanban, Settings } from 'lucide-react'
import { NavLink, useLocation } from 'react-router'

function readLastWorkspace() {
  try {
    const value = JSON.parse(localStorage.getItem('insightcut:last-workspace') || 'null')
    return value?.taskId ? value : null
  } catch {
    return null
  }
}

export function BrandNavigation() {
  const location = useLocation()
  const [lastWorkspace, setLastWorkspace] = useState(readLastWorkspace)
  const workspaceMatch = location.pathname.match(/^\/workspace\/([^/]+)/)
  const navigationItems = [
    { to: '/', label: '文稿', icon: FileText, end: true },
    { to: '/assets', label: '项目资产', icon: FolderKanban },
    { to: workspaceMatch ? `/workspace/${workspaceMatch[1]}/settings` : '/settings', label: 'API 配置', icon: Settings },
  ]

  useEffect(() => {
    const refresh = () => setLastWorkspace(readLastWorkspace())
    window.addEventListener('storage', refresh)
    window.addEventListener('insightcut:workspace', refresh)
    refresh()
    return () => {
      window.removeEventListener('storage', refresh)
      window.removeEventListener('insightcut:workspace', refresh)
    }
  }, [location.pathname])

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
        {lastWorkspace && !workspaceMatch ? <NavLink className="nav-link active-workspace-link" to={lastWorkspace.path || `/workspace/${lastWorkspace.taskId}`}><span>继续制作 · {lastWorkspace.name || '当前项目'}</span></NavLink> : null}
      </nav>
    </header>
  )
}
