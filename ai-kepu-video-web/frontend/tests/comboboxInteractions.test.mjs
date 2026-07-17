import test from 'node:test'
import assert from 'node:assert/strict'

import {
  closedComboboxState,
  preventComboboxOptionBlur,
} from '../src/lib/comboboxInteractions.js'

test('option pointer down keeps the input focused until click selects the option', () => {
  const event = {
    defaultPrevented: false,
    preventDefault() { this.defaultPrevented = true },
  }

  preventComboboxOptionBlur(event)

  assert.equal(event.defaultPrevented, true)
})

test('normal blur always closes and restores the committed selection label', () => {
  assert.deepEqual(closedComboboxState('OpenAI'), {
    query: 'OpenAI',
    open: false,
  })
})
