<template>
  <el-dialog
    v-model="visible"
    title="账号管理"
    :width="isMobile ? '100%' : '680px'"
    :fullscreen="isMobile"
    :close-on-click-modal="false"
    class="account-dialog"
    modal-class="account-dialog-overlay"
  >
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
          <el-table-column label="账号" min-width="120">
            <template #default="{ row }">
              <div class="acc-name">
                {{ row.name || '未命名' }}
                <el-tag v-if="row.id === auth.activeId" type="success" size="small">当前</el-tag>
              </div>
              <div v-if="row.uid" class="acc-uid">UID: {{ row.uid }}</div>
            </template>
          </el-table-column>
          <el-table-column label="登录态" width="70">
            <template #default="{ row }">
              <el-tag v-if="row.has_cookie" type="success" size="small">已登录</el-tag>
              <el-tag v-else type="info" size="small">未登录</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="180" align="right">
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
            <template v-if="isAndroid">
              点击后将打开应用内登录页面，使用手机微博 App 扫码并确认，或直接在页面中完成账号密码登录。
            </template>
            <template v-else>
              点击后将在本机弹出浏览器登录窗口（原生 CDP 驱动本机 Chrome/Edge）。
              使用手机微博 App 扫码并确认即可完成登录。
            </template>
          </el-alert>
          <el-button type="primary" :loading="qr.starting" @click="startQr">开始扫码登录</el-button>
        </template>
        <template v-else>
          <el-alert type="info" :closable="false" class="mb">
            <template v-if="isAndroid">
              请在<strong>应用内登录页面</strong>完成扫码或账号密码登录，登录成功后下方按钮会自动变为可用。
            </template>
            <template v-else>
              已在本机弹出浏览器登录窗口（passport.weibo.com）。
              请<strong>在弹出的浏览器窗口中用手机微博 App 扫码并点「确认登录」</strong>，
              登录成功后点击下方按钮完成 Cookie 抓取。
            </template>
          </el-alert>
          <div class="qr-status mt">
            <el-tag :type="qr.state === 'confirmed' ? 'success' : 'primary'">{{ qr.msg }}</el-tag>
            <el-button size="small" :loading="qr.confirming" @click="confirmQr">
              {{ qr.state === 'confirmed' ? '完成登录' : '我已扫码，获取Cookie' }}
            </el-button>
            <el-button size="small" @click="cancelQr">取消</el-button>
          </div>
          <div class="privacy-note mt">
            <div class="privacy-title">🔒 隐私与安全说明</div>
            <ul>
              <li><b>数据仅存本地</b>：您的微博账号信息（Cookie、UID、昵称等）仅保存在您的本地设备中，不会上传至任何第三方服务器。</li>
              <li><b>安全可靠</b>：本工具通过浏览器原生协议（CDP）完成登录流程，不经过任何中间服务器，与您在浏览器中正常登录微博无异。</li>
              <li><b>自主可控</b>：您可随时在「账号管理」中退出登录，一键清除所有登录态数据。</li>
            </ul>
            <div class="privacy-agree">扫码即表示您已了解并同意上述说明。</div>
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
const isAndroid = computed(() => !!(window as any).AndroidBridge)

// 移动端检测：Android 环境或窄屏时使用全屏弹窗
const isMobile = ref(
  !!(window as any).AndroidBridge || window.innerWidth <= 768
)
function _onResize() {
  isMobile.value = !!(window as any).AndroidBridge || window.innerWidth <= 768
}
onBeforeUnmount(() => {
  window.removeEventListener('resize', _onResize)
})
window.addEventListener('resize', _onResize)

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
    // Android：通过原生桥接打开 WebView 登录页
    if (res.android_webview && (window as any).AndroidBridge) {
      ;(window as any).AndroidBridge.startLogin(res.sid)
    }
    pollQr()
  } finally {
    qr.starting = false
  }
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
      tab.value = 'list'
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

// 强制移动端弹窗全屏（竖屏比例）
// Element Plus Dialog 通过 teleport 渲染到 body，scoped 样式无法作用到根元素，
// 因此用 MutationObserver 监听 DOM 变化，弹窗出现时立刻设置内联样式。
let _fsObserver: MutationObserver | null = null
let _fsTries = 0

function applyFullscreenStyles() {
  const dialog = document.querySelector('.account-dialog') as HTMLElement | null
  const overlay = document.querySelector('.account-dialog-overlay') as HTMLElement | null
  const overlayDialog = document.querySelector(
    '.account-dialog-overlay .el-overlay-dialog'
  ) as HTMLElement | null

  if (!overlay && !overlayDialog && !dialog) {
    return false // 元素还没出现
  }

  const w = window.innerWidth + 'px'
  const h = window.innerHeight + 'px'

  if (overlay) {
    overlay.style.setProperty('padding', '0', 'important')
    overlay.style.setProperty('position', 'fixed', 'important')
    overlay.style.setProperty('top', '0', 'important')
    overlay.style.setProperty('left', '0', 'important')
    overlay.style.setProperty('width', w, 'important')
    overlay.style.setProperty('height', h, 'important')
    overlay.style.setProperty('z-index', '2000', 'important')
  }
  if (overlayDialog) {
    overlayDialog.style.setProperty('position', 'absolute', 'important')
    overlayDialog.style.setProperty('top', '0', 'important')
    overlayDialog.style.setProperty('left', '0', 'important')
    overlayDialog.style.setProperty('width', '100%', 'important')
    overlayDialog.style.setProperty('height', '100%', 'important')
    overlayDialog.style.setProperty('margin', '0', 'important')
    overlayDialog.style.setProperty('padding', '0', 'important')
    overlayDialog.style.setProperty('display', 'flex', 'important')
    overlayDialog.style.setProperty('align-items', 'stretch', 'important')
    overlayDialog.style.setProperty('justify-content', 'stretch', 'important')
    overlayDialog.style.setProperty('animation', 'none', 'important')
    overlayDialog.style.setProperty('transition', 'none', 'important')
  }
  if (dialog) {
    dialog.style.setProperty('position', 'relative', 'important')
    dialog.style.setProperty('top', '0', 'important')
    dialog.style.setProperty('left', '0', 'important')
    dialog.style.setProperty('width', '100%', 'important')
    dialog.style.setProperty('max-width', '100%', 'important')
    dialog.style.setProperty('height', '100%', 'important')
    dialog.style.setProperty('max-height', '100%', 'important')
    dialog.style.setProperty('margin', '0', 'important')
    dialog.style.setProperty('border-radius', '0', 'important')
    dialog.style.setProperty('display', 'flex', 'important')
    dialog.style.setProperty('flex-direction', 'column', 'important')
    dialog.style.setProperty('transform', 'none', 'important')
    dialog.style.setProperty('animation', 'none', 'important')
    dialog.style.setProperty('transition', 'none', 'important')
  }
  return !!(overlay && overlayDialog && dialog)
}

function startFullscreenObserver() {
  stopFullscreenObserver()
  _fsTries = 0

  // 先立即尝试一次
  if (applyFullscreenStyles()) return

  // 用 MutationObserver 监听 body，弹窗出现后立刻应用样式
  _fsObserver = new MutationObserver(() => {
    const done = applyFullscreenStyles()
    _fsTries++
    // 应用成功后再观察一会儿，防止 Element Plus 动画覆盖样式
    if (done && _fsTries > 10) {
      stopFullscreenObserver()
    }
  })
  _fsObserver.observe(document.body, {
    childList: true,
    subtree: true,
    attributes: true,
    attributeFilter: ['style', 'class'],
  })
}

function stopFullscreenObserver() {
  if (_fsObserver) {
    _fsObserver.disconnect()
    _fsObserver = null
  }
}

watch(
  () => props.modelValue,
  (v) => {
    if (v) {
      auth.fetchAccounts()
      // 强制弹窗全屏（移动端竖屏比例）
      // Element Plus Dialog 通过 teleport 渲染，用 MutationObserver 确保样式生效
      startFullscreenObserver()
    } else {
      stopFullscreenObserver()
    }
  },
  { immediate: true }
)
onBeforeUnmount(() => {
  clearQrTimer()
  stopFullscreenObserver()
})
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
.privacy-note {
  background: #fffdf5;
  border: 1px solid #fde68a;
  border-radius: 8px;
  padding: 12px 14px;
  font-size: 13px;
  line-height: 1.7;
  color: #374151;
  text-align: left;
}
.privacy-title {
  font-weight: 700;
  font-size: 14px;
  margin-bottom: 6px;
  color: #111827;
}
.privacy-note ul {
  margin: 0;
  padding-left: 18px;
}
.privacy-note li { margin-bottom: 2px; }
.privacy-agree {
  margin-top: 8px;
  font-weight: 600;
  color: #111827;
}
.target-row { display: flex; gap: 10px; }
.target-info { color: #6b7280; }

/* 桌面端：弹窗内容区最大高度，避免超高内容溢出 */
.account-dialog :deep(.el-dialog__body) {
  max-height: 72vh;
  overflow-y: auto;
  padding: 16px 20px;
}

/* 移动端：弹窗铺满整个屏幕（竖屏比例），内容区可滚动 */
/* 注意：el-dialog 通过 teleport 渲染到 body，根元素样式需用 :global() */
@media (max-width: 768px) {
  :global(.account-dialog-overlay .el-overlay-dialog) {
    display: flex;
    align-items: stretch;
    justify-content: stretch;
    padding: 0;
  }
  :global(.account-dialog) {
    width: 100% !important;
    max-width: 100% !important;
    height: 100% !important;
    max-height: 100% !important;
    margin: 0 !important;
    border-radius: 0 !important;
    display: flex;
    flex-direction: column;
  }
  :global(.account-dialog) .el-dialog__header {
    padding: 14px 16px 10px;
    flex-shrink: 0;
  }
  :global(.account-dialog) .el-dialog__body {
    flex: 1;
    overflow-y: auto;
    padding: 12px 16px;
    max-height: none;
  }
  :global(.account-dialog) .el-dialog__footer {
    padding: 10px 16px;
    flex-shrink: 0;
  }
  :global(.account-dialog) .el-table {
    font-size: 12px;
  }
  :global(.account-dialog) .el-table .el-button {
    padding: 0 3px;
  }
  .target-row { flex-direction: column; }
}

/* 弹窗遮罩层：移动端去掉默认内边距，让弹窗真正铺满 */
:global(.account-dialog-overlay) {
  padding: 0 !important;
}
</style>