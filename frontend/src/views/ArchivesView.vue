<template>
  <div>
    <el-card shadow="never" class="toolbar">
      <div class="filters">
        <el-input v-model="keyword" placeholder="全文搜索(支持中文分词, FTS5)" clearable style="width: 320px" :disabled="onThisDay" @keyup.enter="doSearch" />
        <el-select v-model="year" placeholder="年份" clearable style="width: 120px" :disabled="onThisDay">
          <el-option v-for="y in years" :key="y" :value="y" :label="`${y}年`" />
        </el-select>
        <el-select v-model="month" placeholder="月份" clearable style="width: 110px" :disabled="onThisDay">
          <el-option v-for="m in 12" :key="m" :value="m" :label="`${m}月`" />
        </el-select>
        <el-select v-model="hasMedia" placeholder="媒体" clearable style="width: 110px">
          <el-option value="true" label="有图" />
          <el-option value="false" label="无图" />
        </el-select>
        <el-button :type="onThisDay ? 'warning' : 'default'" @click="toggleOnThisDay">往年今日</el-button>
        <el-select v-model="pageSize" filterable allow-create default-first-option style="width: 110px" @change="onPageSizeChange">
          <el-option v-for="s in [10, 20, 50]" :key="s" :value="s" :label="`${s}条/页`" />
        </el-select>
        <el-button type="primary" @click="doSearch">搜索</el-button>
        <el-button @click="resetFilters">重置</el-button>
      </div>
    </el-card>

    <div class="scroll-area">
      <PostCard
        v-for="p in posts"
        :key="p.id"
        :post="p"
        @show-comments="openComments"
      />
      <el-empty v-if="!loading && posts.length === 0" description="暂无微博，请先到任务中心开始归档" />
      <div v-loading="loading" class="load-more">{{ loading ? '加载中…' : '' }}</div>
    </div>

    <div class="pager">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next, jumper"
        @current-change="doSearch"
      />
    </div>

    <el-dialog v-model="commentVisible" :title="`评论 (${commentCount})`" width="720px">
      <div v-if="comments.length === 0" class="empty">暂无评论</div>
      <div v-for="c in comments" :key="c.id" class="comment">
        <span class="cname">{{ c.user.screen_name || '?' }}：</span>{{ c.text }}
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { getPosts, searchPosts, getComments, getYears } from '@/api'
import type { PostItem } from '@/api/http'
import PostCard from '@/components/PostCard.vue'

const keyword = ref('')
const year = ref<number | undefined>()
const month = ref<number | undefined>()
const hasMedia = ref<string | undefined>()
const onThisDay = ref(false)
const years = ref<string[]>([])

const posts = ref<PostItem[]>([])
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const total = ref(0)

const commentVisible = ref(false)
const comments = ref<any[]>([])
const commentCount = ref(0)

// 递增请求序号：丢弃过期/乱序响应，避免 watch 与显式调用竞态覆盖列表
let _searchSeq = 0

async function doSearch() {
  const reqId = ++_searchSeq
  posts.value = []
  loading.value = true
  try {
    if (keyword.value.trim() && !onThisDay.value) {
      const r = await searchPosts({ keyword: keyword.value.trim(), page: page.value, page_size: pageSize.value })
      if (reqId !== _searchSeq) return // 已有更新的请求，丢弃过期响应
      posts.value = r.items
      total.value = r.total
    } else {
      const r = await getPosts({
        year: year.value,
        month: month.value,
        has_media: hasMedia.value,
        on_this_day: onThisDay.value || undefined,
        page: page.value,
        page_size: pageSize.value,
      })
      if (reqId !== _searchSeq) return
      posts.value = r.items
      total.value = r.total
    }
  } catch (e) {
    if (reqId !== _searchSeq) return
    console.error('加载微博失败', e)
  } finally {
    if (reqId === _searchSeq) loading.value = false
  }
}

function onPageSizeChange(v: number | string) {
  const n = Number(v)
  if (!Number.isFinite(n) || n < 1) return
  pageSize.value = Math.min(Math.floor(n), 200)
  page.value = 1
  doSearch()
}

function toggleOnThisDay() {
  onThisDay.value = !onThisDay.value
  if (onThisDay.value) {
    // 往年今日为独立模式：清空并禁用关键词/年份/月份筛选
    keyword.value = ''
    year.value = undefined
    month.value = undefined
  }
}

function resetFilters() {
  keyword.value = ''
  year.value = undefined
  month.value = undefined
  hasMedia.value = undefined
  onThisDay.value = false
  doSearch()
}

async function openComments(p: PostItem) {
  comments.value = []
  commentCount.value = p.comments_count
  commentVisible.value = true
  const r = await getComments(p.id)
  comments.value = r.items
}

onMounted(async () => {
  const y = await getYears()
  years.value = y.items
  doSearch()
})

watch([year, month, hasMedia, onThisDay], () => doSearch())
</script>

<style scoped>
.toolbar { margin-bottom: 16px; }
.filters { display: flex; gap: 10px; flex-wrap: wrap; }
.scroll-area { height: calc(100vh - 260px); overflow-y: auto; padding-right: 4px; }
.load-more { text-align: center; color: #9ca3af; padding: 12px; }
.pager { display: flex; justify-content: center; padding: 16px 0; }
.comment { padding: 8px 0; border-bottom: 1px dashed #eee; font-size: 14px; line-height: 1.6; }
.cname { color: #e6162d; }
.empty { color: #9ca3af; text-align: center; padding: 30px; }
</style>