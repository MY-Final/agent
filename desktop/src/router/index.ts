import { createRouter, createWebHashHistory } from 'vue-router'
import { getStoredToken } from '@/utils/auth'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { title: '登录', public: true },
    },
    {
      path: '/',
      name: 'dashboard',
      component: () => import('@/views/DashboardView.vue'),
      meta: { title: '工作台' },
    },
    {
      path: '/tasks',
      name: 'tasks',
      component: () => import('@/views/TaskListView.vue'),
      meta: { title: '任务列表' },
    },
    {
      path: '/tasks/new',
      name: 'task-create',
      component: () => import('@/views/TaskCreateView.vue'),
      meta: { title: '新建任务' },
    },
    {
      path: '/guide',
      name: 'guide',
      component: () => import('@/views/GuideView.vue'),
      meta: { title: '使用指南' },
    },
    {
      path: '/tasks/:id',
      name: 'task-detail',
      component: () => import('@/views/TaskDetailView.vue'),
      meta: { title: '任务详情' },
    },
    {
      path: '/templates',
      name: 'templates',
      component: () => import('@/views/TemplatesView.vue'),
      meta: { title: '解析模板' },
    },
    {
      path: '/knowledge',
      name: 'knowledge',
      component: () => import('@/views/KnowledgeBaseView.vue'),
      meta: { title: '资质知识库' },
    },
    {
      path: '/stats',
      name: 'stats',
      component: () => import('@/views/StatsView.vue'),
      meta: { title: '统计与成本' },
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('@/views/SettingsView.vue'),
      meta: { title: '系统设置' },
    },
  ],
})

router.beforeEach((to) => {
  const hasToken = Boolean(getStoredToken())
  if (to.meta.public) {
    if (hasToken && to.name === 'login') return { path: '/', replace: true }
    return true
  }
  if (!hasToken) {
    return { path: '/login', query: { redirect: to.fullPath }, replace: true }
  }
  return true
})

router.afterEach((to) => {
  document.title = `${String(to.meta.title || '工作台')} - 投标分析`
})

export default router
