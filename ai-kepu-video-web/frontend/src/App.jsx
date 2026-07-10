import { BrowserRouter, Navigate, Route, Routes, useParams } from 'react-router'
import { BrandNavigation } from './components/BrandNavigation'
import { ToastViewport } from './components/ToastViewport'
import { ManuscriptPage } from './pages/ManuscriptPage'
import { PreviewPage } from './pages/PreviewPage'
import { ProcessPage } from './pages/ProcessPage'
import { ProductionSetupPage } from './pages/ProductionSetupPage'
import { RoutePlaceholder } from './pages/RoutePlaceholder'

const routePages = [
  { path: '/export/:taskId', title: '导出视频', description: '选择交付方式并导出已完成的视频。' },
  { path: '/assets', title: '项目资产', description: '管理本地草稿、媒体资源和可继续编辑的项目。' },
  { path: '/settings', title: 'API 配置', description: '维护模型、图像和语音服务的连接配置。' }
]

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
          {routePages.map(page => <Route key={page.path} path={page.path} element={<RoutePlaceholder {...page} route={page.path} />} />)}
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
