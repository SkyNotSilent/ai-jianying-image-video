import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

afterEach(() => {
  cleanup()
})

if (!window.requestAnimationFrame) {
  window.requestAnimationFrame = callback => window.setTimeout(callback, 0)
}
