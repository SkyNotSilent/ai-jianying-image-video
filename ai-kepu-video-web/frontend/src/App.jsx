import { BrowserRouter, Navigate, Route, Routes, useLocation, useParams } from 'react-router'
import { AppErrorBoundary } from './components/AppErrorBoundary'
import { BrandNavigation } from './components/BrandNavigation'
import { ToastViewport } from './components/ToastViewport'
import { ExportPage } from './pages/ExportPage'
import { ManuscriptPage } from './pages/ManuscriptPage'
import { ProjectAssetsPage } from './pages/ProjectAssetsPage'
import { SettingsPage } from './pages/SettingsPage'
import { WorkspacePage } from './pages/WorkspacePage'
import { getDraft } from './utils/projectDrafts'

export default function App() {
  return (
    <BrowserRouter>
      <AppSurface />
    </BrowserRouter>
  )
}

function AppSurface() {
  const location = useLocation()
  return <AppErrorBoundary resetKey={`${location.pathname}${location.search}`}>
    <div className="app-shell">
      <BrandNavigation />
      <Routes>
        <Route path="/" element={<ManuscriptPage />} />
        <Route path="/manuscript/:draftId?" element={<ManuscriptPage />} />
        <Route path="/workspace/:taskId/*" element={<WorkspacePage />} />
        <Route path="/production/:draftId" element={<ProductionRedirect />} />
        <Route path="/process/:taskId" element={<WorkspaceRedirect />} />
        <Route path="/preview/:taskId" element={<WorkspaceRedirect />} />
        <Route path="/export/:taskId" element={<ExportPage />} />
        <Route path="/assets" element={<ProjectAssetsPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/result/:taskId" element={<ResultRedirect />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      <ToastViewport />
    </div>
  </AppErrorBoundary>
}

function ResultRedirect() {
  const { taskId } = useParams()
  return <Navigate to={`/export/${taskId}`} replace />
}

function WorkspaceRedirect() {
  const { taskId } = useParams()
  return <Navigate to={`/workspace/${taskId}`} replace />
}

function ProductionRedirect() {
  const { draftId } = useParams()
  const draft = getDraft(draftId)
  return <Navigate to={draft?.created_task_id ? `/workspace/${draft.created_task_id}` : `/manuscript/${draftId}`} replace />
}
