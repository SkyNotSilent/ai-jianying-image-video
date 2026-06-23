<template>
  <header class="nav-bar">
    <div class="nav-brand-group" @click="emit('navigate', 'create')">
      <div class="logo-icon" aria-hidden="true">
        <div class="logo-glow"></div>
        <div class="logo-inner"></div>
        <div class="logo-reticles">
          <div class="reticle-row">
            <span class="reticle-corner reticle-tl"></span>
            <span class="reticle-corner reticle-tr"></span>
          </div>
          <div class="reticle-row">
            <span class="reticle-corner reticle-bl"></span>
            <span class="reticle-corner reticle-br"></span>
          </div>
        </div>
        <span class="logo-dot"></span>
      </div>
      <span class="logo-text">InsightCut</span>
      <span class="logo-badge">Beta</span>
    </div>

    <nav class="nav-tabs" aria-label="主导航">
      <button
        v-for="item in navItems"
        :key="item.key"
        type="button"
        class="nav-tab"
        :class="{ active: activeTab === item.key }"
        @click="emit('navigate', item.key)"
      >
        <span class="tab-icon" v-html="item.icon"></span>
        <span>{{ item.label }}</span>
      </button>
    </nav>

    <div class="nav-actions">
      <button v-if="showBack" type="button" class="nav-action" @click="emit('back')">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="15 18 9 12 15 6" /></svg>
        <span>返回编辑</span>
      </button>
      <button v-if="showActions" type="button" class="nav-action primary" @click="emit('export')">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" /></svg>
        <span>导出视频</span>
      </button>
    </div>
  </header>
</template>

<script setup>
defineProps({
  activeTab: { type: String, default: 'create' },
  showBack: { type: Boolean, default: false },
  showActions: { type: Boolean, default: false },
})

const emit = defineEmits(['navigate', 'back', 'export'])

const navItems = [
  {
    key: 'create',
    label: '首页',
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>',
  },
  {
    key: 'library',
    label: '资产记录',
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M7 8h10M7 12h6"/></svg>',
  },
  {
    key: 'settings',
    label: '模型配置',
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M12 1v6m0 6v6m9-9h-6m-6 0H3"/></svg>',
  },
]
</script>

<style scoped>
.nav-bar {
  height: 64px;
  border-bottom: 1px solid var(--color-border);
  display: grid;
  grid-template-columns: minmax(210px, 1fr) auto minmax(210px, 1fr);
  align-items: center;
  gap: 18px;
  padding: 0 24px;
  background: var(--color-card);
  position: sticky;
  top: 0;
  z-index: 50;
  flex-shrink: 0;
}

.nav-brand-group {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  min-width: 0;
}

.logo-icon {
  width: 32px;
  height: 32px;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  border-radius: 8px;
  background: var(--color-bg-secondary);
  transition: box-shadow 0.4s;
  flex-shrink: 0;
  isolation: isolate;
}

.logo-icon:hover { box-shadow: 0 0 16px rgba(0, 113, 227, 0.6); }

.logo-glow {
  position: absolute;
  inset: 0;
  background: conic-gradient(from 0deg, transparent 0 60deg, #60a5fa 120deg, transparent 120deg 180deg, var(--color-accent) 240deg, transparent 240deg 300deg, #818cf8 360deg);
  animation: logoSpin 4s linear infinite;
}

.logo-inner {
  position: absolute;
  inset: 1.5px;
  border-radius: 6px;
  background: var(--color-bg-secondary);
  z-index: 10;
}

.logo-reticles {
  position: absolute;
  inset: 6px;
  z-index: 20;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  animation: reticleSnap 5s cubic-bezier(0.34, 1.56, 0.64, 1) infinite;
}

.reticle-row { display: flex; justify-content: space-between; }
.reticle-corner { width: 6px; height: 6px; }
.reticle-tl { border-top: 1.5px solid var(--color-text); border-left: 1.5px solid var(--color-text); border-radius: 1px 0 0 0; }
.reticle-tr { border-top: 1.5px solid var(--color-text); border-right: 1.5px solid var(--color-text); border-radius: 0 1px 0 0; }
.reticle-bl { border-bottom: 1.5px solid var(--color-text); border-left: 1.5px solid var(--color-text); border-radius: 0 0 0 1px; }
.reticle-br { border-bottom: 1.5px solid var(--color-text); border-right: 1.5px solid var(--color-text); border-radius: 0 0 1px 0; }

.logo-dot {
  position: absolute;
  z-index: 20;
  width: 3px;
  height: 3px;
  background: var(--color-accent);
  border-radius: 50%;
  box-shadow: 0 0 6px rgba(0, 113, 227, 0.9);
  animation: dotPulse 2.5s linear infinite;
}

.logo-text {
  font-weight: 800;
  font-size: 16px;
  color: var(--color-text);
}

.logo-badge {
  font-size: 8px;
  font-weight: 700;
  padding: 1px 6px;
  background: rgba(134, 144, 156, 0.1);
  color: var(--color-text-tertiary);
  border: 1px solid var(--color-border);
  border-radius: 4px;
  text-transform: uppercase;
  letter-spacing: 1px;
  transform: translateY(-1px);
}

.nav-tabs {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
}

.nav-tab {
  padding: 8px 16px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  border: none;
  background: transparent;
  color: var(--color-text-tertiary);
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: all 0.2s;
  white-space: nowrap;
}

.nav-tab:hover {
  color: var(--color-text);
  background: var(--color-bg-secondary);
}

.nav-tab.active {
  background: var(--color-accent-light);
  color: var(--color-accent);
  font-weight: 600;
}

.tab-icon,
.tab-icon :deep(svg),
.nav-action svg {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}

.nav-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  min-width: 0;
}

.nav-action {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 6px;
  border: none;
  background: transparent;
  color: var(--color-text-tertiary);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: color 0.15s;
}

.nav-action:hover {
  color: var(--color-text);
}

.nav-action.primary {
  padding: 8px 16px;
  background: var(--color-accent);
  border: 1px solid var(--color-accent);
  color: #fff;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  box-shadow: 0 2px 8px rgba(0, 113, 227, 0.2);
}

.nav-action.primary:hover {
  background: var(--color-accent-hover);
  box-shadow: 0 4px 12px rgba(0, 113, 227, 0.3);
}

@keyframes logoSpin { to { transform: rotate(360deg); } }
@keyframes reticleSnap {
  0%, 20% { transform: rotate(0deg); }
  25%, 45% { transform: rotate(90deg); }
  50%, 70% { transform: rotate(180deg); }
  75%, 95% { transform: rotate(270deg); }
  100% { transform: rotate(360deg); }
}
@keyframes dotPulse {
  0%, 100% { transform: scale(1) rotate(0deg); }
  50% { transform: scale(1.4) rotate(180deg); }
}

@media (max-width: 860px) {
  .nav-bar {
    grid-template-columns: auto 1fr auto;
    padding: 0 12px;
    gap: 10px;
  }

  .logo-text,
  .logo-badge {
    display: none;
  }

  .nav-tabs {
    justify-content: flex-start;
    overflow-x: auto;
  }

  .nav-tab {
    padding: 8px 10px;
  }

  .nav-action span {
    display: none;
  }
}
</style>
