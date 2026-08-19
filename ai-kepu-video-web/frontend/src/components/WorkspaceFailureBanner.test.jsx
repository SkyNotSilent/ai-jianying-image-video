import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { WorkspaceFailureBanner } from './WorkspaceFailureBanner'

const promptFailure = {
  key: '2:prompt',
  segmentIndex: 2,
  assetType: 'prompt',
  assetLabel: '提示词',
  errorSource: { error_code: 'timeout' },
}

describe('WorkspaceFailureBanner', () => {
  it('routes prompt repair through the precise segment action and never the material batch action', async () => {
    const user = userEvent.setup()
    const onRetryAll = vi.fn()
    const onRetryPrompt = vi.fn()
    render(<WorkspaceFailureBanner
      issues={{
        failures: [promptFailure],
        failureCount: 1,
        failedSegmentCount: 1,
        counts: { prompt: 1, image: 0, audio: 0 },
      }}
      onRetryAll={onRetryAll}
      onRetryPrompt={onRetryPrompt}
      onSelect={vi.fn()}
    />)

    expect(screen.queryByRole('button', { name: /\u5931\u8d25\u7d20\u6750/ })).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '展开清单' }))
    await user.click(screen.getByRole('button', { name: '重生这段提示词' }))

    expect(onRetryPrompt).toHaveBeenCalledWith(2)
    expect(onRetryAll).not.toHaveBeenCalled()
  })

  it('keeps image and audio failures on the material batch action', async () => {
    const user = userEvent.setup()
    const onRetryAll = vi.fn()
    const failures = [
      { key: '0:image', segmentIndex: 0, assetType: 'image', assetLabel: '图片', errorSource: { error_code: 'rate_limit' } },
      { key: '1:audio', segmentIndex: 1, assetType: 'audio', assetLabel: '配音', errorSource: { error_code: 'provider_error' } },
    ]
    render(<WorkspaceFailureBanner
      issues={{ failures, failureCount: 2, failedSegmentCount: 2, counts: { prompt: 0, image: 1, audio: 1 } }}
      onRetryAll={onRetryAll}
      onRetryPrompt={vi.fn()}
      onSelect={vi.fn()}
    />)

    await user.click(screen.getByRole('button', { name: '重试 2 个失败素材' }))
    expect(onRetryAll).toHaveBeenCalledTimes(1)
  })
})
