<template>
  <header class="nav-bar">
    <button type="button" class="brand" @click="emit('navigate', 'home')">
      <BrandMark />
      <span class="brand-copy">
        <strong>InsightCut</strong>
        <small>AI 图片视频工作室</small>
      </span>
    </button>

    <nav class="nav-tabs" aria-label="主导航">
      <button
        v-for="item in navItems"
        :key="item.key"
        type="button"
        class="nav-tab"
        :class="{ active: activeTab === item.key }"
        @click="emit('navigate', item.key)"
      >
        <component :is="item.icon" />
        <span>{{ item.label }}</span>
      </button>
    </nav>

    <div class="nav-actions">
      <div v-if="searchable" class="search-box">
        <Search />
        <input :value="searchValue" placeholder="搜索项目、文稿或标签" @input="emit('update:searchValue', $event.target.value)" />
        <kbd>⌘ K</kbd>
      </div>
      <button v-if="showBack" type="button" class="icon-action" @click="emit('back')">
        <ArrowLeft />
        <span>返回</span>
      </button>
      <button v-if="showActions" type="button" class="primary-small" @click="emit('export')">
        <Download />
        <span>导出视频</span>
      </button>
      <div class="team-menu">
        <span>IC</span>
        <strong>创作中</strong>
      </div>
    </div>
  </header>
</template>

<script setup>
import { ArrowLeft, Download, Files, HomeFilled, Search, Setting } from '@element-plus/icons-vue'
import BrandMark from './BrandMark.vue'

defineProps({
  activeTab: { type: String, default: 'home' },
  showBack: { type: Boolean, default: false },
  showActions: { type: Boolean, default: false },
  searchable: { type: Boolean, default: false },
  searchValue: { type: String, default: '' },
})

const emit = defineEmits(['navigate', 'back', 'export', 'update:searchValue'])

const navItems = [
  { key: 'home', label: '文稿', icon: HomeFilled },
  { key: 'library', label: '项目资产', icon: Files },
  { key: 'settings', label: 'API 配置', icon: Setting },
]
</script>

<style scoped>
.nav-bar {
  position: sticky;
  top: 0;
  z-index: 40;
  height: 64px;
  display: grid;
  grid-template-columns: minmax(260px, 1fr) auto minmax(360px, 1fr);
  align-items: center;
  gap: 24px;
  padding: 0 24px;
  border-bottom: 1px solid var(--color-border);
  background: rgba(255, 255, 255, 0.94);
  backdrop-filter: blur(18px);
}

.brand {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  width: fit-content;
  border: 0;
  background: transparent;
  cursor: pointer;
  color: var(--color-text);
}

.brand-copy {
  display: grid;
  gap: 1px;
  text-align: left;
}

.brand-copy strong {
  font-size: 18px;
  line-height: 1;
  letter-spacing: 0;
}

.brand-copy small {
  color: var(--color-text-secondary);
  font-size: 12px;
}

.nav-tabs {
  display: inline-flex;
  align-items: center;
  gap: 34px;
  height: 64px;
}

.nav-tab {
  position: relative;
  height: 64px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 0 4px;
  border: 1px solid transparent;
  border-radius: 0;
  background: transparent;
  color: var(--color-text-secondary);
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
}

.nav-tab svg {
  width: 17px;
  height: 17px;
}

.nav-tab:hover {
  color: var(--color-text);
  background: transparent;
}

.nav-tab.active {
  color: var(--color-primary);
  background: transparent;
  border-color: transparent;
}

.nav-tab.active::after {
  content: "";
  position: absolute;
  left: 4px;
  right: 4px;
  bottom: -1px;
  height: 3px;
  border-radius: 999px 999px 0 0;
  background: var(--color-primary);
}

.nav-actions {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.search-box {
  width: min(360px, 100%);
  height: 40px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 12px;
  border: 1px solid var(--color-border);
  border-radius: 10px;
  background: #fff;
  color: var(--color-text-tertiary);
}

.search-box svg {
  width: 16px;
  height: 16px;
}

.search-box input {
  min-width: 0;
  flex: 1;
  border: 0;
  outline: 0;
  color: var(--color-text);
}

.search-box kbd {
  padding: 2px 6px;
  border-radius: 6px;
  background: #f2f4f7;
  color: var(--color-text-tertiary);
  font-size: 12px;
}

.icon-action,
.primary-small,
.team-menu {
  height: 40px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border-radius: 10px;
  border: 1px solid var(--color-border);
  background: #fff;
  color: var(--color-text);
  padding: 0 12px;
  font-weight: 700;
}

.icon-action svg,
.primary-small svg,
.team-menu svg {
  width: 16px;
  height: 16px;
}

.primary-small {
  border-color: var(--color-primary);
  background: var(--color-primary);
  color: #fff;
}

.icon-action,
.primary-small {
  cursor: pointer;
}

.team-menu span {
  display: inline-flex;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  align-items: center;
  justify-content: center;
  background: #dff3d7;
  color: #276749;
  font-size: 12px;
  font-weight: 800;
}

.team-menu strong {
  font-size: 13px;
}

@media (max-width: 1180px) {
  .nav-bar {
    grid-template-columns: auto 1fr auto;
  }

  .search-box {
    display: none;
  }
}
</style>
