<template>
  <div class="settings">
    <el-card shadow="never" class="mb">
      <template #header>
        <span>账号管理</span>
      </template>
      <div class="account-row">
        <div class="account-info">
          <template v-if="auth.activeAccount">
            <el-avatar :size="40" class="acc-avatar">
              {{ (auth.activeAccount.name || '?')[0] }}
            </el-avatar>
            <div>
              <div class="acc-name">{{ auth.activeAccount.name || '未命名' }}</div>
              <div class="acc-uid" v-if="auth.activeAccount.uid">UID: {{ auth.activeAccount.uid }}</div>
            </div>
          </template>
          <template v-else-if="auth.hasCookie">
            <div class="acc-name">已登录</div>
          </template>
          <template v-else>
            <div class="acc-name">未登录</div>
            <div class="acc-uid">登录后可归档微博数据</div>
          </template>
        </div>
        <el-button type="primary" @click="showAccountManager = true">登录 / 管理账号</el-button>
      </div>
    </el-card>

    <el-card shadow="never">
      <template #header>
        <span>应用设置</span>
      </template>

      <el-form label-width="120px" label-position="left" class="form">
        <el-form-item label="数据目录">
          <template v-if="isAndroid">
            <el-tag type="info" class="path-tag">{{ workspaceDir }}</el-tag>
            <div class="hint">Android 版数据保存在应用内部存储，无需手动修改。</div>
          </template>
          <template v-else>
            <div class="dir-row">
              <el-input v-model="workspaceDir" placeholder="选择数据文件存放位置" />
              <el-button @click="onPick">浏览…</el-button>
            </div>
            <div class="hint">
              数据库、图片、视频、导出文件等所有数据都存放在该目录下。修改后需重启应用生效。
            </div>
          </template>
        </el-form-item>

        <el-form-item label="当前目录">
          <el-tag type="info" class="path-tag">{{ currentDir }}</el-tag>
        </el-form-item>

        <el-form-item label="应用版本">
          <span>{{ settings.version }}<template v-if="settings.frozen">（打包版）</template></span>
        </el-form-item>

        <el-form-item label="设置文件">
          <el-tag type="info" class="path-tag">{{ settings.settings_file }}</el-tag>
        </el-form-item>

        <el-form-item v-if="!isAndroid">
          <el-button type="primary" :loading="saving" @click="onSave">保存并重启</el-button>
          <el-button :disabled="!changed" @click="onRestart">立即重启应用</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>

  <AccountManager v-model="showAccountManager" />
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getSettings, setWorkspaceDir, pickWorkspaceDir, restartApp } from '@/api'
import { useAuthStore } from '@/stores/auth'
import AccountManager from '@/components/AccountManager.vue'

const auth = useAuthStore()
const showAccountManager = ref(false)

const isAndroid = computed(() => !!(window as any).AndroidBridge)

const settings = ref<{ version: string; frozen: boolean; workspace_dir: string; settings_file: string }>({
  version: '',
  frozen: false,
  workspace_dir: '',
  settings_file: '',
})
const workspaceDir = ref('')
const saving = ref(false)

const currentDir = computed(() => settings.value.workspace_dir || '—')
const changed = computed(() => workspaceDir.value.trim() !== settings.value.workspace_dir)

onMounted(async () => {
  try {
    settings.value = await getSettings()
    workspaceDir.value = settings.value.workspace_dir
  } catch {
    ElMessage.error('加载设置失败')
  }
  await auth.refreshAll()
})

async function onPick() {
  try {
    const r = await pickWorkspaceDir()
    if (r.ok && r.path) {
      workspaceDir.value = r.path
    } else if (r.msg) {
      ElMessage.warning(r.msg)
    }
  } catch {
    ElMessage.error('打开目录选择失败')
  }
}

async function onSave() {
  const path = workspaceDir.value.trim()
  if (!path) {
    ElMessage.warning('请先填写数据目录')
    return
  }
  saving.value = true
  try {
    const r = await setWorkspaceDir(path)
    ElMessage.success(r.msg || '已保存')
    await ElMessageBox.confirm('数据目录已保存，需要重启应用才能生效。是否立即重启？', '重启应用', {
      confirmButtonText: '立即重启',
      cancelButtonText: '稍后手动重启',
      type: 'warning',
    })
    await doRestart()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

async function onRestart() {
  await ElMessageBox.confirm('重启后应用将重新打开，是否继续？', '重启应用', {
    confirmButtonText: '重启',
    cancelButtonText: '取消',
    type: 'warning',
  })
  await doRestart()
}

async function doRestart() {
  try {
    await restartApp()
    ElMessage.info('正在重启应用…')
  } catch {
    ElMessage.error('重启失败，请手动关闭并重新打开应用')
  }
}
</script>

<style scoped>
.settings { max-width: 760px; }
.mb { margin-bottom: 16px; }
.account-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.account-info { display: flex; align-items: center; gap: 12px; }
.acc-avatar { background: #2563eb; color: #fff; font-weight: 600; }
.acc-name { font-weight: 600; }
.acc-uid { color: #6b7280; font-size: 12px; margin-top: 2px; }
.form { margin-top: 8px; }
.dir-row { display: flex; gap: 8px; width: 100%; }
.hint { color: #6b7280; font-size: 12px; line-height: 1.6; margin-top: 4px; }
.path-tag { max-width: 100%; overflow: hidden; text-overflow: ellipsis; }
</style>
