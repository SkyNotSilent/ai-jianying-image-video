<template>
  <router-view v-slot="{ Component }">
    <transition name="page" mode="out-in">
      <component :is="Component" />
    </transition>
  </router-view>
</template>

<style>
:root {
  --color-primary: #0f62fe;
  --color-primary-hover: #0751d8;
  --color-primary-bg: #eef5ff;
  --color-accent: #0f62fe;
  --color-accent-hover: #0751d8;
  --color-accent-light: #eef5ff;
  --color-accent-subtle: rgba(15, 98, 254, 0.08);
  --accent-glow: rgba(15, 98, 254, 0.16);

  --color-bg: #f7f8fa;
  --color-bg-gradient: linear-gradient(180deg, #ffffff 0%, #f6f8fb 100%);
  --color-bg-secondary: #f4f6f8;
  --color-card: #ffffff;
  --color-paper: #fffdf8;
  --color-elevated: rgba(255, 255, 255, 0.92);

  --color-text: #171a1f;
  --color-text-secondary: #626b78;
  --color-text-tertiary: #8b94a1;
  --color-text-placeholder: #a7aeba;

  --color-border: #e3e6eb;
  --color-divider: #eceef2;

  --color-success: #22a06b;
  --color-success-bg: #edf8f3;
  --color-warning: #b7791f;
  --color-warning-bg: #fff7e6;
  --color-danger: #e5484d;
  --color-danger-bg: #fff0f0;

  --color-dark: #171a1f;

  --shadow-xs: 0 1px 2px rgba(17, 24, 39, 0.04);
  --shadow-sm: 0 4px 14px rgba(17, 24, 39, 0.06);
  --shadow-md: 0 12px 32px rgba(17, 24, 39, 0.08);
  --shadow-lg: 0 18px 48px rgba(17, 24, 39, 0.12);

  --radius-sm: 8px;
  --radius-md: 10px;
  --radius-lg: 14px;
  --radius-xl: 18px;
  --radius-2xl: 24px;

  --font-main: ui-sans-serif, -apple-system, BlinkMacSystemFont, "SF Pro Display", "PingFang SC", "Helvetica Neue", Arial, sans-serif;
  --font-text: ui-sans-serif, -apple-system, BlinkMacSystemFont, "SF Pro Text", "PingFang SC", "Helvetica Neue", Arial, sans-serif;
  --font-serif: "Songti SC", "STSong", "Noto Serif CJK SC", serif;
  --font-mono: "SF Mono", Menlo, Monaco, Consolas, monospace;

  --space-xs: 4px;
  --space-sm: 8px;
  --space-md: 16px;
  --space-lg: 24px;
  --space-xl: 32px;
  --space-2xl: 48px;
  --duration-fast: 150ms;
  --duration-normal: 260ms;
  --ease-out: cubic-bezier(0.16, 1, 0.3, 1);
}

* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

html,
body,
#app {
  min-height: 100vh;
}

body {
  font-family: var(--font-text);
  font-size: 15px;
  line-height: 1.55;
  color: var(--color-text);
  background: var(--color-bg-gradient);
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
}

button,
input,
textarea,
select {
  font: inherit;
}

button {
  letter-spacing: 0;
}

button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

a {
  color: inherit;
}

::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

::-webkit-scrollbar-track {
  background: transparent;
}

::-webkit-scrollbar-thumb {
  background: rgba(99, 110, 124, 0.28);
  border-radius: 999px;
}

.page-enter-active,
.page-leave-active {
  transition: opacity 0.22s var(--ease-out), transform 0.22s var(--ease-out);
}

.page-enter-from {
  opacity: 0;
  transform: translateY(8px);
}

.page-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

.surface-button {
  min-height: 40px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-card);
  color: var(--color-text);
  cursor: pointer;
  transition: border-color var(--duration-fast), background var(--duration-fast), transform var(--duration-fast);
}

.surface-button:hover {
  border-color: #c9d1dc;
  background: #fbfcff;
}

.primary-action {
  min-height: 44px;
  border: 1px solid var(--color-primary);
  border-radius: var(--radius-sm);
  background: var(--color-primary);
  color: #fff;
  font-weight: 700;
  cursor: pointer;
  box-shadow: 0 12px 24px rgba(15, 98, 254, 0.16);
  transition: background var(--duration-fast), transform var(--duration-fast);
}

.primary-action:hover {
  background: var(--color-primary-hover);
  transform: translateY(-1px);
}

.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 24px;
  padding: 3px 9px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
}

.status-pill.success {
  color: var(--color-success);
  background: var(--color-success-bg);
}

.status-pill.warning {
  color: var(--color-warning);
  background: var(--color-warning-bg);
}

.status-pill.danger {
  color: var(--color-danger);
  background: var(--color-danger-bg);
}

.status-pill.info {
  color: var(--color-primary);
  background: var(--color-primary-bg);
}
</style>
