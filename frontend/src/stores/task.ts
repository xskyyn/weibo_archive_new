import { defineStore } from 'pinia'
import { ElMessage } from 'element-plus'
import {
  startTask, stopTask, resumeTask, getTaskStatus, taskWebSocketUrl,
} from '@/api'

export type TaskStatus =
  | 'idle' | 'running' | 'paused_captcha' | 'stopped' | 'completed' | 'failed'

interface LogLine {
  type: 'log' | 'error' | 'status' | 'info'
  time: string
  data: string
}

export const useTaskStore = defineStore('task', {
  state: () => ({
    status: 'idle' as TaskStatus,
    totalFetched: 0,
    page: 0,
    logs: [] as LogLine[],
    captchaUrl: '',
    connected: false,
    _ws: null as WebSocket | null,
    _reconnectTimer: 0 as any,
  }),
  actions: {
    appendLog(type: LogLine['type'], data: unknown) {
      const now = new Date()
      const time = `${now.getHours()}:${String(now.getMinutes()).padStart(2, '0')}:${String(
        now.getSeconds(),
      ).padStart(2, '0')}`
      this.logs.push({ type, data: String(data), time })
      if (this.logs.length > 2000) this.logs.splice(0, this.logs.length - 2000)
    },
    connectWS() {
      if (this._ws) return
      const ws = new WebSocket(taskWebSocketUrl())
      this._ws = ws as any
      ws.onopen = () => {
        this.connected = true
      }
      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data)
          this.handleMessage(msg)
        } catch (e) {
          console.error(e)
        }
      }
      ws.onclose = () => {
        this.connected = false
        this._ws = null
        this._reconnectTimer = setTimeout(() => this.connectWS(), 3000)
      }
      ws.onerror = () => ws.close()
    },
    handleMessage(msg: any) {
      switch (msg.type) {
        case 'status':
          this.status = msg.data
          break
        case 'log':
          this.appendLog('info', msg.data)
          break
        case 'error':
          this.appendLog('error', msg.data)
          ElMessage.error(String(msg.data))
          break
        case 'progress':
          this.totalFetched = msg.data.total_fetched
          this.page = msg.data.page
          break
        case 'captcha':
          this.captchaUrl = msg.data
          this.status = 'paused_captcha'
          break
      }
    },
    async doStart(uid?: number) {
      const r = await startTask(uid)
      return r
    },
    async doStop() {
      await stopTask()
    },
    async doResume() {
      this.captchaUrl = ''
      await resumeTask()
    },
    async refresh() {
      const r = await getTaskStatus()
      this.status = r.status
      this.totalFetched = r.total_fetched
      this.page = r.page
    },
    clearLogs() {
      this.logs = []
    },
  },
})