import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { WorkspaceSettingsOverlay } from './WorkspaceSettingsOverlay'

function Harness() {
  const [open, setOpen] = useState(false)
  return <>
    <button type="button" onClick={() => setOpen(true)}>打开 API 配置</button>
    <WorkspaceSettingsOverlay open={open} onClose={() => setOpen(false)}>
      <button type="button" data-settings-initial-focus>关闭设置</button>
      <input aria-label="API Key" />
      <button type="button">保存配置</button>
    </WorkspaceSettingsOverlay>
  </>
}

describe('WorkspaceSettingsOverlay', () => {
  it('traps focus, closes on Escape, and restores the opener', async () => {
    const user = userEvent.setup()
    render(<Harness />)
    const opener = screen.getByRole('button', { name: '打开 API 配置' })
    await user.click(opener)

    const initial = screen.getByRole('button', { name: '关闭设置' })
    await waitFor(() => expect(initial).toHaveFocus())
    await user.tab({ shift: true })
    expect(screen.getByRole('button', { name: '保存配置' })).toHaveFocus()
    await user.tab()
    expect(initial).toHaveFocus()

    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog', { name: 'API 配置' })).not.toBeInTheDocument()
    expect(opener).toHaveFocus()
  })
})
