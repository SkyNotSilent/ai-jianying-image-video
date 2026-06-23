<template>
  <router-view v-slot="{ Component }">
    <transition name="page" mode="out-in">
      <component :is="Component" />
    </transition>
  </router-view>
</template>

<script setup>
</script>

<style>
:root {
  /* ==================== 配色：科技蓝 + 极简黑白 ==================== */
  /* 主色：纯黑（Apple 标志性） */
  --color-primary: #000000;
  --color-primary-hover: #1d1d1f;
  --color-primary-bg: rgba(0, 0, 0, 0.04);

  /* 强调色：Apple 蓝（用于交互和视觉重点） */
  --color-accent: #0071e3;
  --color-accent-hover: #0077ed;
  --color-accent-light: #e8f0fe;
  --color-accent-subtle: rgba(0, 113, 227, 0.08);
  --accent-glow: rgba(0, 113, 227, 0.2);

  /* 背景：浅蓝渐变 + 纯白卡片 */
  --color-bg: #f5f7fa;
  --color-bg-gradient: linear-gradient(135deg, #f5f7fa 0%, #e8f0fe 100%);
  --color-bg-secondary: #e8f0fe;
  --color-card: #ffffff;

  /* 文字：层次分明 */
  --color-text: #1d1d1f;           /* 标题 */
  --color-text-secondary: #6e6e73; /* 正文 */
  --color-text-tertiary: #86868b;  /* 辅助 */
  --color-text-placeholder: #a1a1a6;

  /* 边框：几乎不可见 */
  --color-border: #d2d2d7;
  --color-divider: #e8e8ed;

  /* 状态色 */
  --color-success: #30d158;
  --color-success-bg: #ecfdf5;
  --color-danger: #ff3b30;
  --color-danger-bg: #fef2f2;

  /* 保留兼容性 */
  --color-dark: #1d1d1f;

  /* ==================== 阴影：轻柔自然 + 蓝色光晕 ==================== */
  --shadow-xs: 0 1px 3px rgba(0, 0, 0, 0.04);
  --shadow-sm: 0 2px 8px rgba(0, 0, 0, 0.08);
  --shadow-md: 0 4px 16px rgba(0, 0, 0, 0.12);
  --shadow-lg: 0 8px 32px rgba(0, 0, 0, 0.16);
  --shadow-xl: 0 16px 64px rgba(0, 0, 0, 0.20);

  /* 蓝色光晕阴影（用于卡片） */
  --shadow-blue-sm: 0 2px 8px rgba(0, 113, 227, 0.08);
  --shadow-blue-md: 0 4px 16px rgba(0, 113, 227, 0.12);
  --shadow-blue-lg: 0 8px 32px rgba(0, 113, 227, 0.16);

  /* ==================== 圆角：大而柔和 ==================== */
  --radius-sm: 8px;
  --radius-md: 12px;
  --radius-lg: 18px;
  --radius-xl: 24px;
  --radius-2xl: 32px;

  /* ==================== 字体：SF Pro Display ==================== */
  --font-main: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'PingFang SC', 'Helvetica Neue', sans-serif;
  --font-text: -apple-system, BlinkMacSystemFont, 'SF Pro Text', 'PingFang SC', 'Helvetica Neue', sans-serif;
  --font-mono: 'SF Mono', 'Menlo', 'Monaco', 'Courier New', monospace;

  /* ==================== 间距：8px 基准 ==================== */
  --space-xs: 4px;
  --space-sm: 8px;
  --space-md: 16px;
  --space-lg: 24px;
  --space-xl: 32px;
  --space-2xl: 48px;
  --space-3xl: 64px;
  --space-4xl: 96px;

  /* ==================== 动画：流畅自然 ==================== */
  --ease-in-out: cubic-bezier(0.4, 0, 0.2, 1);
  --ease-out: cubic-bezier(0, 0, 0.2, 1);
  --ease-in: cubic-bezier(0.4, 0, 1, 1);
  --duration-fast: 150ms;
  --duration-normal: 300ms;
  --duration-slow: 500ms;
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: var(--font-text);
  font-size: 17px;
  line-height: 1.47059;
  font-weight: 400;
  letter-spacing: -0.022em;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  text-rendering: optimizeLegibility;
  color: var(--color-text);
  background: var(--color-bg-gradient);
}

#app {
  width: 100%;
  min-height: 100vh;
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

::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

::-webkit-scrollbar-track {
  background: transparent;
}

::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.2);
  border-radius: 999px;
}

::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 0, 0, 0.3);
}

.page-enter-active,
.page-leave-active {
  transition: opacity 0.4s cubic-bezier(0.4, 0, 0.2, 1), transform 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}

.page-enter-from {
  opacity: 0;
  transform: translateY(20px);
}

.page-leave-to {
  opacity: 0;
  transform: translateY(-20px);
}

.van-toast {
  border-radius: 8px;
}
</style>
