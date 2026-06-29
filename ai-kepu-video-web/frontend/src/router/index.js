/**
 * Vue Router 配置
 * History 模式 + 路由懒加载
 */

import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'HomeManuscript',
    component: () => import('../views/ManuscriptView.vue'),
    meta: { title: '文稿编辑' }
  },
  {
    path: '/manuscript/:draftId?',
    name: 'Manuscript',
    component: () => import('../views/ManuscriptView.vue'),
    meta: { title: '文稿编辑' }
  },
  {
    path: '/assets',
    name: 'ProjectAssets',
    component: () => import('../views/ProjectAssetsView.vue'),
    meta: { title: '项目资产' }
  },
  {
    path: '/production/:draftId',
    name: 'ProductionSetup',
    component: () => import('../views/ProductionSetupView.vue'),
    meta: { title: '视频生产' }
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('../views/SettingsView.vue'),
    meta: { title: 'API 配置' }
  },
  {
    path: '/process/:taskId',
    name: 'Process',
    component: () => import('../views/ProcessView.vue'),
    meta: { title: '生成中' }
  },
  {
    path: '/preview/:taskId',
    name: 'Preview',
    component: () => import('../views/PreviewView.vue'),
    meta: { title: '预览与编辑' }
  },
  {
    path: '/export/:taskId',
    name: 'Export',
    component: () => import('../views/ExportView.vue'),
    meta: { title: '导出视频' }
  },
  {
    path: '/result/:taskId',
    name: 'Result',
    redirect: to => `/export/${to.params.taskId}`
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 路由守卫：设置页面标题
router.beforeEach((to, from, next) => {
  if (to.meta.title) {
    document.title = `${to.meta.title} - InsightCut`
  }
  next()
})

export default router
