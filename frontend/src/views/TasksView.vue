<template>
  <div>
    <el-card shadow="never" class="control">
      <div class="btns">
        <el-button type="primary" :disabled="!auth.hasCookie || isRunning" @click="onStart">
          ▶ 开始归档
        </el-button>
        <el-button type="danger" :disabled="!isRunning && status !== 'paused_captcha'" @click="task.doStop()">
          ⏹ 停止
        </el-button>
        <el-button
          v-if="status === 'paused_captcha'"
          type="success"
          @click="task.doResume()"
        >
          ✅ 我已完成验证码，继续
        </el-button>
        <span class="stat">累计 {{ task.totalFetched }} 条 · 第 {{ task.page }} 页 · 状态：{{ statusName }}</span>
      </div>
    </el-card>

    <el-dialog :model-value="!!task.captchaUrl" width="620px" title="需要验证码" @close="task.captchaUrl = ''">
      <p>微博触发了风控验证码，请在下方打开链接完成验证后点击继续：</p>
      <el-input readonly :model-value="task.captchaUrl"></el-input>
      <br />
      <el-button type="primary" @click="openCaptcha">打开验证页</el-button>
      <el-button type="success" @click="task.doResume()">已完成，继续抓取</el-button>
    </el-dialog>

    <el-card shadow="never" class="console-card">
      <template #header>
        <span>实时控制台</span>
        <el-button text type="danger" size="small" @click="task.clearLogs()">清空</el-button>
      </template>
      <div ref="logRef" class="console">
        <div
          v-for="(l, i) in task.logs"
          :key="i"
          :class="['line', l.type]"
        >
          <span class="t">{{ l.time }}</span> {{ l.data }}
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted } from 'vue'
import { useTaskStore, type TaskStatus } from '@/stores/task'
import { useAuthStore } from '@/stores/auth'
import { ElMessage } from 'element-plus'

const task = useTaskStore()
const auth = useAuthStore()
const logRef = ref<HTMLDivElement>()

const status = computed<TaskStatus>(() => task.status)
const isRunning = computed(() => status.value === 'running')
const statusName = computed(() => statusMap[status.value] || status.value)

const statusMap: Record<string, string> = {
  idle: '空闲', running: '运行中', paused_captcha: '等待验证码',
  stopped: '已停止', completed: '已完成', failed: '失败',
}

async function onStart() {
  try {
    await task.doStart()
    ElMessage.success('归档任务已启动')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '启动失败，请先导入 Cookie')
  }
}

function openCaptcha() {
  window.open(task.captchaUrl, '_blank')
}

watch(
  () => task.logs.length,
  async () => {
    await nextTick()
    if (logRef.value) logRef.value.scrollTop = logRef.value.scrollHeight
  },
)

onMounted(() => {
  task.refresh()
  task.connectWS()
})
</script>

<style scoped>
.control { margin-bottom: 16px; }
.btns { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.stat { margin-left: 12px; color: #6b7280; }
.console-card { }
.console { height: calc(100vh - 260px); overflow-y: auto; background: #0f172a; color: #e5e7eb; border-radius: 8px; padding: 12px; font-family: Menlo, Consolas, monospace; font-size: 13px; }
.line { padding: 2px 0; white-space: pre-wrap; word-break: break-all; }
.line .t { color: #64748b; margin-right: 8px; }
.line.error { color: #f87171; }
.line.info { color: #93c5fd; }
</style>