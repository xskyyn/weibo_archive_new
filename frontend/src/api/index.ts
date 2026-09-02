import http from './http'

// 认证
export function getCookieStatus() {
  return http.get('/auth/status').then((r) => r.data)
}
export function importCookie(cookie: Record<string, string>, name?: string, uid?: number) {
  return http.post('/auth/cookie', { cookie, name, uid }).then((r) => r.data)
}
export function validateCookie() {
  return http.post('/auth/validate').then((r) => r.data)
}
export function getAppConfig() {
  return http.get('/auth/config').then((r) => r.data)
}
export function logoutAccount() {
  return http.post('/auth/logout').then((r) => r.data)
}

// 多账号管理
export function getAccounts() {
  return http.get('/auth/accounts').then((r) => r.data)
}
export function switchAccount(id: string) {
  return http.post('/auth/accounts/switch', { id }).then((r) => r.data)
}
export function deleteAccount(id: string) {
  return http.delete(`/auth/accounts/${id}`).then((r) => r.data)
}

// 扫码登录（DrissionPage）
export function qrStart() {
  return http.post('/auth/qr/start').then((r) => r.data)
}
export function qrStatus(sid: string) {
  return http.get(`/auth/qr/${sid}/status`).then((r) => r.data)
}
export function qrConfirm(sid: string) {
  return http.post(`/auth/qr/${sid}/confirm`).then((r) => r.data)
}
export function qrCancel(sid: string) {
  return http.get(`/auth/qr/${sid}/cancel`).then((r) => r.data)
}

// 目标用户切换（浏览/归档其他用户）
export function setTarget(uid: number) {
  return http.post('/auth/target', { uid }).then((r) => r.data)
}

// 任务
export function startTask(uid?: number) {
  return http.post('/task/start', { uid }).then((r) => r.data)
}
export function stopTask() {
  return http.post('/task/stop').then((r) => r.data)
}
export function resumeTask() {
  return http.post('/task/resume').then((r) => r.data)
}
export function getTaskStatus() {
  return http.get('/task/status').then((r) => r.data)
}

// 数据查询
export function getStats() {
  return http.get('/stats').then((r) => r.data)
}
export function getTimeline() {
  return http.get('/posts/timeline').then((r) => r.data)
}
export function getPosts(params: Record<string, unknown>) {
  return http.get('/posts', { params }).then((r) => r.data)
}
export function searchPosts(params: Record<string, unknown>) {
  return http.get('/posts/search', { params }).then((r) => r.data)
}
export function getMedia(params: Record<string, unknown>) {
  return http.get('/media', { params }).then((r) => r.data)
}
export function getComments(postId: number) {
  return http.get(`/posts/${postId}/comments`).then((r) => r.data)
}
export function getYears() {
  return http.get('/years').then((r) => r.data)
}

// 导出
export function exportSupportMarkdown(postId: number) {
  return `${'/api'}/export/markdown/${postId}`
}
export function exportHtml() {
  return http.post('/export/html').then((r) => r.data)
}

// 设置
export function getSettings() {
  return http.get('/settings').then((r) => r.data)
}
export function setWorkspaceDir(path: string) {
  return http.put('/settings/workspace', { workspace_dir: path }).then((r) => r.data)
}
export function pickWorkspaceDir() {
  return http.post('/settings/pick-dir').then((r) => r.data)
}
export function restartApp() {
  return http.post('/settings/restart').then((r) => r.data)
}

// WebSocket
export function taskWebSocketUrl() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  return `${proto}://${location.host}/api/task/ws`
}