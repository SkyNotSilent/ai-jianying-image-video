import { useState } from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ConfirmDialog, Modal } from './Modal'

function ModalHarness({ onClose }) {
  const [open, setOpen] = useState(false)
  const close = () => {
    setOpen(false)
    onClose()
  }

  return <>
    <button type="button" onClick={() => setOpen(true)}>打开设置</button>
    <Modal
      open={open}
      title="生产设置"
      onClose={close}
      footer={<><button type="button" data-modal-initial-focus>取消</button><button type="button">保存</button></>}
    >
      <input aria-label="音色名称" />
    </Modal>
  </>
}

describe('Modal', () => {
  it('traps focus, closes with Escape, and restores focus to the opener', async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()
    render(<ModalHarness onClose={onClose} />)

    const opener = screen.getByRole('button', { name: '打开设置' })
    await user.click(opener)

    const cancel = screen.getByRole('button', { name: '取消' })
    const save = screen.getByRole('button', { name: '保存' })
    const closeButton = screen.getByRole('button', { name: '关闭对话框' })
    await waitFor(() => expect(cancel).toHaveFocus())

    save.focus()
    await user.tab()
    expect(closeButton).toHaveFocus()

    await user.tab({ shift: true })
    expect(save).toHaveFocus()

    await user.keyboard('{Escape}')
    expect(onClose).toHaveBeenCalledTimes(1)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(opener).toHaveFocus()
  })

  it('renders a disabled submit action while confirmation is unavailable', () => {
    render(<ConfirmDialog open title="确认生成" message="请先确认音色" confirmLabel="开始生成" confirmDisabled onClose={() => {}} onConfirm={() => {}} />)

    expect(screen.getByRole('button', { name: '开始生成' })).toBeDisabled()
  })
})
