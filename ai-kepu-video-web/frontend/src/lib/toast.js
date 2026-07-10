const listeners = new Set()

function emit(type, message, options = {}) {
  const notification = {
    id: crypto.randomUUID?.() ?? `${Date.now()}-${Math.random()}`,
    type,
    message,
    duration: options.duration ?? 5000
  }

  listeners.forEach(listener => listener(notification))
  return notification.id
}

export const toast = {
  success: (message, options) => emit('success', message, options),
  warning: (message, options) => emit('warning', message, options),
  error: (message, options) => emit('error', message, options),
  info: (message, options) => emit('info', message, options)
}

export function subscribeToasts(listener) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}
