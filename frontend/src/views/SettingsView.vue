<template>
  <div class="settings">
    <el-card shadow="never">
      <template #header>
        <span>应用设置</span>
      </template>

      <el-form label-width="120px" label-position="left" class="form">
        <el-form-item label="数据目录">
          <div class="dir-row">
            <el-input v-model="workspaceDir" placeholder="选择数据文件存放位置" />
            <el-button @click="onPick">浏览…</el-button>
          </div>
          <div class="hint">
            数据库、图片、视频、导出文件等所有数据都存放在该目录下。修改后需重启应用生效。
          </div>
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

        <el-form-item>
          <el-button type="primary" :loading="saving" @click="onSave">保存并重启</el-button>
          <el-button :disabled="!changed" @click="onRestart">立即重启应用</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getSettings, setWorkspaceDir, pickWorkspaceDir, restartApp } from '@/api'

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
.form { margin-top: 8px; }
.dir-row { display: flex; gap: 8px; width: 100%; }
.hint { color: #6b7280; font-size: 12px; line-height: 1.6; margin-top: 4px; }
.path-tag { max-width: 100%; overflow: hidden; text-overflow: ellipsis; }
</style>
