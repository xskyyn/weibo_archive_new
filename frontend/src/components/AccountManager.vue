<template>
  <el-dialog v-model="visible" title="账号管理" width="680px" :close-on-click-modal="false">
    <el-alert
      type="info"
      :closable="false"
      title="可管理多个微博账号：扫码登录或导入 Cookie，支持随时退出（清除登录态）和切换账号。各账号与会话目标用户的归档数据相互隔离。"
      class="mb"
    />

    <el-tabs v-model="tab">
      <!-- 账号列表 -->
      <el-tab-pane label="已登录账号" name="list">
        <el-table :data="auth.accounts" size="small" empty-text="暂无账号，请先扫码登录或导入 Cookie">
          <el-table-column label="账号" min-width="160">
            <template #default="{ row }">
              <div class="acc-name">
                {{ row.name || '未命名' }}
                <el-tag v-if="row.id === auth.activeId" type="success" size="small">当前</el-tag>
              </div>
              <div v-if="row.uid" class="acc-uid">UID: {{ row.uid }}</div>
            </template>
          </el-table-column>
          <el-table-column label="登录态" width="90">
            <template #default="{ row }">
              <el-tag v-if="row.has_cookie" type="success" size="small">已登录</el-tag>
              <el-tag v-else type="info" size="small">未登录</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="230" align="right">
            <template #default="{ row }">
              <el-button
                v-if="row.id !== auth.activeId"
                link type="primary"
                :disabled="auth.loading"
                @click="auth.switchTo(row.id)"
              >设为当前</el-button>
              <el-button
                v-if="row.id === auth.activeId"
                link type="warning"
                :disabled="!row.has_cookie || auth.loading"
                @click="logoutActive"
              >退出</el-button>
              <el-button link type="danger" :disabled="auth.loading" @click="remove(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <el-divider>会话目标</el-divider>
        <div class="target-row">
          <el-input
            v-model="targetInput"
            placeholder="输入要抓取/浏览的用户 UID（不填则归档当前登录账号）"
            style="flex: 1"
            clearable
          >
            <template #prefix>UID</template>
          </el-input>
          <el-button type="primary" :loading="auth.loading" @click="applyTarget">应用目标</el-button>
        </div>
        <div v-if="auth.targetUid" class="target-info mt">
          当前目标：<b>{{ auth.targetName || ('UID ' + auth.targetUid) }}</b>
          <el-button link type="info" @click="clearTarget">恢复为当前账号</el-button>
        </div>
      </el-tab-pane>

      <!-- 扫码登录 -->
      <el-tab-pane label="扫码登录" name="qr">
        <template v-if="!qr.sid">
          <el-alert type="warning" :closable="false" class="mb">
            点击后将在本机弹出浏览器登录窗口（DrissionPage 驱动，需安装 Chrome/Edge）。
            使用手机微博 App 扫码并确认即可完成登录。
          </el-alert>
          <el-button type="primary" :loading="qr.starting" @click="startQr">开始扫码登录</el-button>
        </template>
        <template v-else>
          <div class="qr-box">
            <template v-if="qr.img">
              <img :src="qr.img" alt="二维码" class="qr-img" />
            </template>
            <template v-else>
              <el-empty description="二维码未捕获：请在已弹出的浏览器窗口中直接扫码">
                <el-button @click="refreshQrImg">刷新截图</el-button>
              </el-empty>
            </template>
          </div>
          <div class="qr-status mt">
            <el-tag :type="qr.state === 'confirmed' ? 'success' : 'primary'">{{ qr.msg }}</el-tag>
            <el-button size="small" :loading="qr.confirming" @click="confirmQr">
              {{ qr.state === 'confirmed' ? '完成登录' : '我已扫码，获取Cookie' }}
            </el-button>
            <el-button size="small" @click="cancelQr">取消</el-button>
          </div>
        </template>
      </el-tab-pane>

      <!-- 手动导入 -->
      <el-tab-pane label="手动导入 Cookie" name="import">
        <el-input v-model="importName" placeholder="账号备注名（可选，如：小号）" class="mb" />
        <el-input
          v-model="importRaw"
          type="textarea"
          :rows="8"
          placeholder='{"SUB":"xxx","SUBP":"xxx","XSRF-TOKEN":"xxx",...}'
        />
        <div class="mt">
          <el-button type="primary" :loading="importing" @click="doImport">导入并设为当前</el-button>
        </div>
      </el-tab-pane>
    </el-tabs>

    <template #footer>
      <el-button @click="visible = false">关闭</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onBeforeUnmount, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { qrStart, qrStatus, qrConfirm, qrCancel } from '@/api'
import { ElMessage, ElMessageBox } from 'element-plus'

const props = defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{ (e: 'update:modelValue', v: boolean): void }>()

const auth = useAuthStore()
const tab = ref('list')

// 目标会话
const targetInput = ref('')
async function applyTarget() {
  const uid = Number(targetInput.value)
  if (!uid) {
    ElMessage.warning('请输入合法的用户 UID')
    return
  }
  const res = await auth.applyTarget(uid)
  if (res?.ok) targetInput.value = ''
}
async function clearTarget() {
  if (!auth.uid) {
    ElMessage.warning('当前登录账号无 UID，无法恢复')
    return
  }
  await auth.applyTarget(auth.uid)
}

// 扫码
const qr = reactive({ sid: '', img: '', state: 'idle', msg: '等待扫码', starting: false, confirming: false })
let qrTimer: number | null = null

async function startQr() {
  qr.starting = true
  try {
    const res: any = await qrStart()
    if (!res.ok) {
      ElMessage.error(res.msg || '扫码启动失败')
      return
    }
    qr.sid = res.sid
    qr.img = res.qr_url || ''
    qr.state = 'wait'
    qr.msg = '等待扫码并确认…'
    pollQr()
  } finally {
    qr.starting = false
  }
}
async function refreshQrImg() {
  // 重新请求状态（后端保留浏览器引用），并重试刷新二维码截图地址
  const res: any = await qrStatus(qr.sid)
  if (res.ok && res.qr_url) qr.img = res.qr_url
}
async function pollQr() {
  clearQrTimer()
  qrTimer = window.setInterval(async () => {
    if (!qr.sid) return
    const res: any = await qrStatus(qr.sid).catch(() => null)
    if (!res || !res.ok) {
      qr.state = 'expired'
      qr.msg = res?.msg || '扫码会话失效'
      clearQrTimer()
      return
    }
    qr.state = res.state || 'wait'
    qr.msg = res.msg || qr.msg
    if (res.qr_url) qr.img = res.qr_url
    if (res.state === 'confirmed') {
      clearQrTimer()
      await confirmQr()
    } else if (res.state === 'expired') {
      clearQrTimer()
    }
  }, 2000)
}
async function confirmQr() {
  if (!qr.sid) return
  qr.confirming = true
  try {
    const res: any = await qrConfirm(qr.sid)
    if (res.ok) {
      ElMessage.success('登录成功')
      resetQr()
      await auth.refreshAll()
    } else {
      ElMessage.error(res.msg || '获取 Cookie 失败')
    }
  } finally {
    qr.confirming = false
  }
}
function cancelQr() {
  if (qr.sid) qrCancel(qr.sid).catch(() => {})
  resetQr()
}
function resetQr() {
  clearQrTimer()
  qr.sid = ''
  qr.img = ''
  qr.state = 'idle'
  qr.msg = '等待扫码'
}
function clearQrTimer() {
  if (qrTimer) {
    window.clearInterval(qrTimer)
    qrTimer = null
  }
}

// 手动导入
const importRaw = ref('')
const importName = ref('')
const importing = ref(false)
async function doImport() {
  importing.value = true
  try {
    await auth.importCookies(importRaw.value, importName.value || undefined)
    ElMessage.success('Cookie 导入成功')
    importRaw.value = ''
  } catch (e: any) {
    ElMessage.error(e.message || 'Cookie 导入失败')
  } finally {
    importing.value = false
  }
}

// 退出 / 删除
async function logoutActive() {
  try {
    await ElMessageBox.confirm('退出将清除当前账号的登录态，归档数据会保留。是否继续？', '退出登录', { type: 'warning' })
  } catch {
    return
  }
  await auth.logout()
  ElMessage.success('已退出当前账号')
}
async function remove(row: any) {
  try {
    await ElMessageBox.confirm(`确定删除账号「${row.name || '未命名'}」？其登录 Cookie 将被清除，归档数据保留。`, '删除账号', { type: 'warning' })
  } catch {
    return
  }
  await auth.removeAccount(row.id)
  ElMessage.success('已删除')
}

// 打开时刷新账号列表
const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})
watch(
  () => props.modelValue,
  (v) => {
    if (v) auth.fetchAccounts()
  }
)
onBeforeUnmount(clearQrTimer)
</script>

<style scoped>
.mb { margin-bottom: 12px; }
.mt { margin-top: 12px; }
.acc-name { display: flex; align-items: center; gap: 6px; }
.acc-uid { color: #9ca3af; font-size: 12px; }
.qr-box {
  display: flex;
  justify-content: center;
  padding: 12px;
  background: #f9fafb;
  border-radius: 8px;
}
.qr-img { width: 220px; height: 220px; }
.qr-status { display: flex; align-items: center; gap: 10px; }
.target-row { display: flex; gap: 10px; }
.target-info { color: #6b7280; }
</style>