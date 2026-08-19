import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Tooltip } from './Tooltip'

describe('Tooltip', () => {
  it('opens for pointer and keyboard focus and closes with Escape', async () => {
    const user = userEvent.setup()
    render(<Tooltip label="只重试当前失败素材"><button type="button">重试</button></Tooltip>)

    const button = screen.getByRole('button', { name: '重试' })
    await user.hover(button)
    expect(screen.getByRole('tooltip')).toHaveTextContent('只重试当前失败素材')
    await user.unhover(button)
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()

    await user.tab()
    expect(button).toHaveFocus()
    expect(screen.getByRole('tooltip')).toBeInTheDocument()
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
    expect(button).toHaveFocus()
  })
})
