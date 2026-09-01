import { defineStore } from 'pinia'
import { getCookieStatus, getAppConfig, importCookie as apiImport } from '@/api'
import http from '@/api/http'
import { ElMessage } from 'element-plus'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    hasCookie: false,
    cookieKeys: [] as string[],
    verified: false,
  }),
  actions: {
    async fetchStatus() {
      try {
        const r = await getAppConfig()
        this.hasCookie = !!r.has_cookie
        this.cookieKeys = r.cookie_keys || []
      } catch (e) {
        this.hasCookie = false
        console.error(e)
      }
    },
    async importCookies(raw: string) {
      let data: Record<string, string>
      try {
        data = JSON.parse(raw)
      } catch {
        throw new Error('Cookie 必须是合法的 JSON 对象')
      }
      const res = await apiImport(data)
      await this.fetchStatus()
      return res
    },
    async validate() {
      const res: any = await import('@/api').then((m) => m.validateCookie())
      this.verified = !!res.ok
      if (!res.ok) {
        ElMessage.error(res.msg || 'Cookie 校验失败')
      } else {
        ElMessage.success('Cookie 校验成功')
      }
      return res.ok
    },
    logout() {
      this.hasCookie = false
      this.cookieKeys = []
      this.verified = false
    },
  },
})