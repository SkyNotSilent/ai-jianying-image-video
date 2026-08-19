import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { EmptyStateCard, EditorialLineIllustration } from './EmptyStateCard'

describe('EmptyStateCard', () => {
  it('renders an accessible editorial card with a decorative inline illustration', () => {
    const { container } = render(
      <EmptyStateCard
        variant="projects"
        eyebrow="项目档案"
        title="还没有项目"
        description="从一份文稿开始。"
      />,
    )

    expect(screen.getByRole('region', { name: '还没有项目' })).toBeInTheDocument()
    expect(screen.getByText('项目档案')).toBeInTheDocument()
    expect(screen.getByText('从一份文稿开始。')).toBeInTheDocument()
    const illustration = container.querySelector('svg[data-variant="projects"]')
    expect(illustration).toHaveAttribute('aria-hidden', 'true')
    expect(illustration).toHaveAttribute('focusable', 'false')
    expect(container.querySelector('img')).not.toBeInTheDocument()
    expect(container.querySelector('.ui-empty-copy')?.tagName).toBe('DIV')
  })

  it('renders only caller-provided actions and delegates their behavior', async () => {
    const user = userEvent.setup()
    const onCreate = vi.fn()
    render(
      <EmptyStateCard
        variant="projects"
        title="还没有项目"
        action={<button type="button" onClick={onCreate}>新建文稿</button>}
      />,
    )

    expect(screen.getAllByRole('button')).toHaveLength(1)
    await user.click(screen.getByRole('button', { name: '新建文稿' }))
    expect(onCreate).toHaveBeenCalledTimes(1)
  })

  it('supports inline composition without introducing nested interactive controls', () => {
    const { container } = render(
      <button type="button">
        <EmptyStateCard as="span" variant="manuscript" title="开始写文稿" description="点击进入编辑。">
          <span>三步制作流程</span>
        </EmptyStateCard>
      </button>,
    )

    expect(screen.getAllByRole('button')).toHaveLength(1)
    expect(container.querySelector('.ui-empty-state')?.tagName).toBe('SPAN')
    expect(container.querySelector('.ui-empty-copy')?.tagName).toBe('SPAN')
    expect(screen.getByText('三步制作流程')).toBeInTheDocument()
  })

  it.each(['manuscript', 'projects', 'media', 'voice', 'configuration'])(
    'exposes the %s illustration variant for visual contracts',
    variant => {
      const { container } = render(<EditorialLineIllustration variant={variant} />)
      expect(container.querySelector('svg')).toHaveAttribute('data-variant', variant)
    },
  )
})
