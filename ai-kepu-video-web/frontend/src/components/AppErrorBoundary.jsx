import { Component } from 'react'
import { CircleAlert, Home, RefreshCw } from 'lucide-react'

export class AppErrorBoundary extends Component {
  state = { failed: false }

  static getDerivedStateFromError() {
    return { failed: true }
  }

  componentDidCatch(error) {
    // Do not serialize arbitrary error messages: provider responses can contain secrets.
    console.error('界面渲染失败', error?.name || 'Error')
  }

  componentDidUpdate(previousProps) {
    if (this.state.failed && previousProps.resetKey !== this.props.resetKey) {
      this.setState({ failed: false })
    }
  }

  render() {
    if (!this.state.failed) return this.props.children
    return <main className="app-error-boundary" role="alert">
      <span><CircleAlert size={24} aria-hidden="true" /></span>
      <p className="eyebrow">页面没有正确完成渲染</p>
      <h1>项目数据仍然保留</h1>
      <p>这次界面异常不会取消后台生成。你可以重新载入当前页面，或先返回文稿页再继续制作。</p>
      <div>
        <button className="button button-primary" type="button" onClick={() => window.location.reload()}><RefreshCw size={16} aria-hidden="true" />重新载入</button>
        <button className="button button-secondary" type="button" onClick={() => { window.location.href = '/' }}><Home size={16} aria-hidden="true" />返回文稿</button>
      </div>
    </main>
  }
}
