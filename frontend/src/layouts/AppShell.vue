<template>
  <el-container class="shell">
    <el-aside width="210px" class="aside">
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
        <div class="foot-actions">
          <el-button text size="small" style="color:#d1d5db" @click="showAccountManager = true">账号管理</el-button>
        </div>
      </div>
    </el-aside>
    <el-container>
      <el-header class="header">
        <el-button text @click="showAccountManager = true">👤 账号管理 / 扫码登录</el-button>
      </el-header>
      <el-main class="main"><router-view /></el-main>
    </el-container>
  </el-container>

  <AccountManager v-model="showAccountManager" />
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useTaskStore } from '@/stores/task'
import AccountManager from '@/components/AccountManager.vue'

const auth = useAuthStore()
const task = useTaskStore()
const showAccountManager = ref(false)

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
.foot-actions { margin-top: 8px; }
.header { display: flex; align-items: center; justify-content: flex-end; background: #fff; border-bottom: 1px solid #e5e7eb; }
.main { padding: 20px; overflow-y: auto; }
</style>