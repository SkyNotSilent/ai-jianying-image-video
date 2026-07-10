import { BrowserRouter, Navigate, Route, Routes, useParams } from 'react-router'
import { BrandNavigation } from './components/BrandNavigation'
import { ToastViewport } from './components/ToastViewport'
import { ExportPage } from './pages/ExportPage'
import { ManuscriptPage } from './pages/ManuscriptPage'
import { PreviewPage } from './pages/PreviewPage'
import { ProcessPage } from './pages/ProcessPage'
import { ProductionSetupPage } from './pages/ProductionSetupPage'
import { ProjectAssetsPage } from './pages/ProjectAssetsPage'
import { SettingsPage } from './pages/SettingsPage'

export default function App() {
  return (
    <BrowserRouter>
      <div className="app-shell">
        <BrandNavigation />
        <Routes>
          <Route path="/" element={<ManuscriptPage />} />
          <Route path="/manuscript/:draftId?" element={<ManuscriptPage />} />
          <Route path="/production/:draftId" element={<ProductionSetupPage />} />
          <Route path="/process/:taskId" element={<ProcessPage />} />
          <Route path="/preview/:taskId" element={<PreviewPage />} />
          <Route path="/export/:taskId" element={<ExportPage />} />
          <Route path="/assets" element={<ProjectAssetsPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/result/:taskId" element={<ResultRedirect />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        <ToastViewport />
      </div>
    </BrowserRouter>
  )
}

function ResultRedirect() {
  const { taskId } = useParams()
  return <Navigate to={`/export/${taskId}`} replace />
}
