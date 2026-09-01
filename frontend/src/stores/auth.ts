import { defineStore } from 'pinia'
import {
  getAppConfig,
  importCookie as apiImport,
  validateCookie as apiValidate,
  logoutAccount as apiLogout,
  getAccounts as apiAccounts,
  switchAccount as apiSwitch,
  deleteAccount as apiDelete,
  setTarget as apiSetTarget,
} from '@/api'
import { ElMessage } from 'element-plus'

export interface AccountItem {
  id: string
  name?: string | null
  uid?: number | null
  has_cookie?: boolean
  updated_at?: number | null
}

export const useAuthStore = defineStore('auth', {
  state: () => ({
    hasCookie: false,
    cookieKeys: [] as string[],
    verified: false,
    name: '',
    uid: null as number | null,
    accounts: [] as AccountItem[],
    activeId: null as string | null,
    targetUid: null as number | null,
    targetName: '',
    qrEnabled: true,
    loading: false,
  }),
  getters: {
    activeAccount(state): AccountItem | null {
      return state.accounts.find((a) => a.id === state.activeId) ?? null
    },
  },
  actions: {
    async fetchStatus() {
      try {
        const r = await getAppConfig()
        this.hasCookie = !!r.has_cookie
        this.cookieKeys = r.cookie_keys || []
        this.name = r.name || ''
        this.uid = r.uid || null
        this.qrEnabled = r.qr_enabled !== false
      } catch (e) {
        this.hasCookie = false
        console.error(e)
      }
    },
    async fetchAccounts() {
      try {
        const r = await apiAccounts()
        this.accounts = r.accounts || []
        this.activeId = r.active || null
        const a = this.activeAccount
        this.name = a?.name || ''
        this.uid = a?.uid ?? null
      } catch (e) {
        console.error(e)
      }
    },
    async importCookies(raw: string, name?: string, uid?: number) {
      let data: Record<string, string>
      try {
        data = JSON.parse(raw)
      } catch {
        throw new Error('Cookie 必须是合法的 JSON 对象')
      }
      const res = await apiImport(data, name, uid)
      await this.refreshAll()
      return res
    },
    async validate() {
      const res: any = await apiValidate()
      this.verified = !!res.ok
      if (!res.ok) {
        ElMessage.error(res.msg || 'Cookie 校验失败')
      } else {
        ElMessage.success('Cookie 校验成功')
        await this.refreshAll()
      }
      return res
    },
    async logout() {
      const res: any = await apiLogout()
      this.hasCookie = false
      this.cookieKeys = []
      this.verified = false
      await this.refreshAll()
      return res
    },
    async switchTo(accId: string) {
      this.loading = true
      try {
        const res: any = await apiSwitch(accId)
        if (res.ok) {
          ElMessage.success('已切换账号')
          await this.refreshAll()
        }
        return res
      } finally {
        this.loading = false
      }
    },
    async removeAccount(accId: string) {
      await apiDelete(accId)
      await this.refreshAll()
    },
    async applyTarget(uid: number) {
      this.loading = true
      try {
        const res: any = await apiSetTarget(uid)
        if (res.ok) {
          this.targetUid = res.uid
          this.targetName = res.name || ''
          ElMessage.success(`已切换到目标用户：${res.name || res.uid}`)
        } else {
          ElMessage.error(res.msg || '切换目标失败')
        }
        return res
      } finally {
        this.loading = false
      }
    },
    async refreshAll() {
      await Promise.all([this.fetchStatus(), this.fetchAccounts()])
    },
  },
})