import { createRouter, createWebHashHistory, type RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    component: () => import('@/layouts/AppShell.vue'),
    redirect: '/dashboard',
    children: [
      { path: 'dashboard', name: 'dashboard', component: () => import('@/views/DashboardView.vue') },
      { path: 'archives', name: 'archives', component: () => import('@/views/ArchivesView.vue') },
      { path: 'media', name: 'media', component: () => import('@/views/MediaView.vue') },
      { path: 'tasks', name: 'tasks', component: () => import('@/views/TasksView.vue') },
    ],
  },
]

export default createRouter({
  history: createWebHashHistory(),
  routes,
})