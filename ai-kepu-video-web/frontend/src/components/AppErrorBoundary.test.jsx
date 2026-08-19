import { render, screen } from '@testing-library/react'
import { AppErrorBoundary } from './AppErrorBoundary'

function SometimesBroken({ broken }) {
  if (broken) throw new Error('provider-secret-must-not-render')
  return <p>工作台已恢复</p>
}

describe('AppErrorBoundary', () => {
  it('shows a safe fallback and recovers when the route reset key changes', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    const { rerender } = render(
      <AppErrorBoundary resetKey="/workspace/old">
        <SometimesBroken broken />
      </AppErrorBoundary>,
    )

    expect(screen.getByRole('alert')).toHaveTextContent('项目数据仍然保留')
    expect(screen.getByRole('alert')).not.toHaveTextContent('provider-secret-must-not-render')

    rerender(
      <AppErrorBoundary resetKey="/workspace/new">
        <SometimesBroken broken={false} />
      </AppErrorBoundary>,
    )

    expect(await screen.findByText('工作台已恢复')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})
