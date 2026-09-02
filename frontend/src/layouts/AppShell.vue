<template>
  <el-container class="shell">
    <!-- 桌面端侧边栏 -->
    <el-aside width="210px" class="aside desktop-aside">
      <div class="logo">📖 WeiboArchive</div>
      <el-menu :default-active="$route.path" router class="menu">
        <el-menu-item index="/dashboard">仪表盘</el-menu-item>
        <el-menu-item index="/archives">归档浏览</el-menu-item>
        <el-menu-item index="/media">媒体时光轴</el-menu-item>
        <el-menu-item index="/tasks">任务中心</el-menu-item>
        <el-menu-item index="/settings">设置</el-menu-item>
      </el-menu>
      <div class="aside-foot">
        <el-tag v-if="auth.activeAccount" type="success" size="small">当前：{{ auth.activeAccount.name || '未命名' }}</el-tag>
        <el-tag v-else-if="auth.hasCookie" type="success" size="small">已登录</el-tag>
        <el-tag v-else type="warning" size="small">未登录</el-tag>
      </div>
    </el-aside>

    <el-container>
      <!-- 顶部栏 -->
      <el-header class="header">
        <div class="header-left">
          <div class="logo-mobile">📖 WeiboArchive</div>
        </div>
      </el-header>

      <!-- 移动端横向导航 -->
      <div class="mobile-nav">
        <div class="mobile-tab" :class="{ active: $route.path === '/dashboard' }" @click="$router.push('/dashboard')">仪表盘</div>
        <div class="mobile-tab" :class="{ active: $route.path === '/archives' }" @click="$router.push('/archives')">归档</div>
        <div class="mobile-tab" :class="{ active: $route.path === '/media' }" @click="$router.push('/media')">媒体</div>
        <div class="mobile-tab" :class="{ active: $route.path === '/tasks' }" @click="$router.push('/tasks')">任务</div>
        <div class="mobile-tab" :class="{ active: $route.path === '/settings' }" @click="$router.push('/settings')">设置</div>
      </div>

      <el-main class="main"><router-view /></el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useTaskStore } from '@/stores/task'

const auth = useAuthStore()
const task = useTaskStore()

onMounted(async () => {
  await auth.refreshAll()
  task.connectWS()
})
</script>

<style scoped>
.shell { height: 100vh; }
.aside { background: #111827; color: #fff; display: flex; flex-direction: column; }
.logo { padding: 20px 16px; font-weight: 700; font-size: 18px; color: #fbbf24; }
.menu { flex: 1; border-right: none; background: transparent; }
.menu :deep(.el-menu-item) { color: #d1d5db; }
.menu :deep(.el-menu-item.is-active) { color: #fbbf24; background: #1f2937; }
.aside-foot { padding: 16px; }
.header { display: flex; align-items: center; justify-content: space-between; background: #fff; border-bottom: 1px solid #e5e7eb; }
.main { padding: 20px; overflow-y: auto; }

/* 移动端默认隐藏 */
.logo-mobile, .mobile-nav { display: none; }

@media (max-width: 768px) {
  .desktop-aside { display: none; }
  .logo-mobile { display: block; font-weight: 700; font-size: 16px; color: #111827; }
  .header { height: 48px; }
  .mobile-nav { display: flex; align-items: center; border-bottom: 1px solid #e5e7eb; }
  .mobile-tab { flex: 1; text-align: center; padding: 12px 0; font-size: 14px; color: #4b5563; cursor: pointer; white-space: nowrap; }
  .mobile-tab.active { color: #2563eb; font-weight: 600; box-shadow: inset 0 -2px 0 #2563eb; }
  .main { padding: 12px; }
}
</style>
