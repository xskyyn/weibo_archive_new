<template>
  <el-dialog v-model="visible" title="Cookie 管理" width="580px">
    <el-alert
      type="info"
      :closable="false"
      title="将微博登录后的 Cookie 导出为 JSON 对象粘贴到下方（来自浏览器开发者工具，通常在 weibo.com 或 m.weibo.cn 下）。"
    />
    <el-input
      v-model="raw"
      type="textarea"
      :rows="8"
      placeholder='{"SUB":"xxx","SUBP":"xxx","XSRF-TOKEN":"xxx",...}'
      class="mt"
    />
    <template #footer>
      <el-button :loading="loading" type="primary" @click="doImport">导入 Cookie</el-button>
      <el-button :disabled="!auth.hasCookie" :loading="loading" @click="doValidate">校验</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { ElMessage } from 'element-plus'

const props = defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{ (e: 'update:modelValue', v: boolean): void }>()

const auth = useAuthStore()
const raw = ref('')
const loading = ref(false)
const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

async function doImport() {
  loading.value = true
  try {
    await auth.importCookies(raw.value)
    raw.value = ''
    visible.value = false
  } catch (e: any) {
    ElMessage.error(e.message || 'Cookie 导入失败')
  } finally {
    loading.value = false
  }
}

async function doValidate() {
  loading.value = true
  try {
    await auth.validate()
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.mt { margin-top: 12px; }
</style>