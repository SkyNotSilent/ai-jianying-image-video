import { BrowserRouter, Navigate, Route, Routes, useParams } from 'react-router'
import { BrandNavigation } from './components/BrandNavigation'
import { ToastViewport } from './components/ToastViewport'
import { RoutePlaceholder } from './pages/RoutePlaceholder'

const routePages = [
  { path: '/', title: '文稿编辑', description: '整理主题、导入资料，并建立可复用的视频文稿。' },
  { path: '/manuscript/:draftId?', title: '文稿编辑', description: '整理主题、导入资料，并建立可复用的视频文稿。' },
  { path: '/production/:draftId', title: '视频生产', description: '配置画面、声音和生成参数，然后提交生产任务。' },
  { path: '/process/:taskId', title: '生成进度', description: '跟踪生成状态并在需要时处理异常。' },
  { path: '/preview/:taskId', title: '预览与编辑', description: '检查分镜、素材与配音，完成最终调整。' },
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
