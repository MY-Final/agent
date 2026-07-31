import { createRouter, createWebHashHistory } from 'vue-router'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
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

router.afterEach((to) => {
  document.title = `${String(to.meta.title || '工作台')} - 投标分析`
})

export default router
