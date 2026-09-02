<template>
  <div>
    <el-card shadow="never" class="toolbar">
      <div class="toolbar-row">
        <el-radio-group v-model="mtype" @change="load">
          <el-radio-button value="">全部</el-radio-button>
          <el-radio-button value="pic">图片</el-radio-button>
          <el-radio-button value="video">视频</el-radio-button>
        </el-radio-group>
        <el-radio-group v-model="order" @change="load">
          <el-radio-button value="desc">倒序</el-radio-button>
          <el-radio-button value="asc">正序</el-radio-button>
        </el-radio-group>
      </div>
    </el-card>

    <div class="waterfall">
      <div v-for="m in items" :key="m.id" class="cell" @click="open(m)">
        <video v-if="m.type === 'video'" :src="m.media_url || m.url" preload="metadata" class="thumb" />
        <el-image v-else :src="m.media_url || m.url" :preview-src-list="previewList" :initial-index="previewIndex(m)" fit="cover" class="thumb" />
        <div class="cell-foot">{{ m.post_text }}</div>
      </div>
    </div>
    <el-empty v-if="items.length === 0" description="暂无媒体，请先归档" />
    <div class="loadbar">
      <el-button :loading="loading" @click="loadMore">{{ loading ? '加载中…' : '加载更多' }}</el-button>
      <span v-if="items.length >= total" class="done">已加载全部</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getMedia } from '@/api'

interface MediaRow {
  id: number
  type: string
  url?: string
  media_url?: string | null
  post_text?: string
  post_mid?: string | null
}

const mtype = ref('')
const order = ref('desc')
const items = ref<MediaRow[]>([])
const page = ref(1)
const pageSize = 60
const total = ref(0)
const loading = ref(false)

const previewList = ref<string[]>([])

function buildPreviewList() {
  previewList.value = items.value
    .filter((i) => i.type === 'pic')
    .map((i) => i.media_url || i.url || '')
    .filter(Boolean)
}

async function load() {
  page.value = 1
  items.value = []
  loading.value = true
  try {
    const r = await getMedia({ page: 1, page_size: pageSize, mtype: mtype.value || undefined, order: order.value })
    items.value = r.items
    total.value = r.total
    buildPreviewList()
  } finally {
    loading.value = false
  }
}

async function loadMore() {
  if (loading.value || items.value.length >= total.value) return
  page.value += 1
  loading.value = true
  try {
    const r = await getMedia({ page: page.value, page_size: pageSize, mtype: mtype.value || undefined, order: order.value })
    items.value.push(...r.items)
    buildPreviewList()
  } finally {
    loading.value = false
  }
}

function open(m: MediaRow) {
  if (m.type === 'pic') return // el-image 自带预览
}
function previewIndex(m: MediaRow) {
  return previewList.value.indexOf(m.media_url || m.url || '')
}

onMounted(load)
</script>

<style scoped>
.toolbar { margin-bottom: 16px; }
.toolbar-row { display: flex; gap: 16px; align-items: center; flex-wrap: wrap; }
.waterfall { columns: 5 180px; column-gap: 12px; }
.cell { break-inside: avoid; background: #fff; border-radius: 8px; overflow: hidden; margin-bottom: 12px; box-shadow: 0 1px 3px rgba(0,0,0,.08); cursor: pointer; }
.thumb { width: 100%; display: block; background: #eee; }
.cell-foot { padding: 6px 10px; font-size: 12px; color: #6b7280; max-height: 32px; overflow: hidden; }
.loadbar { text-align: center; padding: 16px; }
.done { color: #9ca3af; margin-left: 12px; }
</style>