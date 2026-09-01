<template>
  <div>
    <el-card shadow="never" class="toolbar">
      <div class="filters">
        <el-input v-model="keyword" placeholder="全文搜索(支持中文分词, FTS5)" clearable style="width: 320px" @keyup.enter="doSearch" />
        <el-select v-model="year" placeholder="年份" clearable style="width: 120px">
          <el-option v-for="y in years" :key="y" :value="y" :label="`${y}年`" />
        </el-select>
        <el-select v-model="month" placeholder="月份" clearable style="width: 110px">
          <el-option v-for="m in 12" :key="m" :value="m" :label="`${m}月`" />
        </el-select>
        <el-select v-model="hasMedia" placeholder="媒体" clearable style="width: 110px">
          <el-option value="true" label="有图" />
          <el-option value="false" label="无图" />
        </el-select>
        <el-button type="primary" @click="doSearch">搜索</el-button>
        <el-button @click="resetFilters">重置</el-button>
      </div>
    </el-card>

    <div ref="scrollRef" class="scroll-area">
      <PostCard
        v-for="p in posts"
        :key="p.id"
        :post="p"
        @show-comments="openComments"
      />
      <el-empty v-if="!loading && posts.length === 0" description="暂无微博，请先到任务中心开始归档" />
      <div v-loading="loading" class="load-more">{{ finished ? '已加载全部' : '加载中…' }}</div>
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
const years = ref<string[]>([])

const posts = ref<PostItem[]>([])
const page = ref(1)
const loading = ref(false)
const finished = ref(false)
const total = ref(0)

const commentVisible = ref(false)
const comments = ref<any[]>([])
const commentCount = ref(0)

const scrollRef = ref<HTMLDivElement>()

// 递增请求序号：丢弃过期/乱序响应，避免 watch 与显式调用竞态覆盖列表
let _searchSeq = 0

async function doSearch(loadMore = false) {
  const more = loadMore === true // 防止 @click/@keyup 传入 Event 对象被当作 truthy
  const reqId = ++_searchSeq
  if (!more) {
    page.value = 1
    posts.value = []
    finished.value = false
  }
  loading.value = true
  try {
    if (keyword.value.trim()) {
      const r = await searchPosts({ keyword: keyword.value.trim(), page: page.value, page_size: 20 })
      if (reqId !== _searchSeq) return // 已有更新的请求，丢弃过期响应
      posts.value.push(...r.items)
      total.value = r.total
    } else {
      const r = await getPosts({
        year: year.value,
        month: month.value,
        has_media: hasMedia.value,
        page: page.value,
        page_size: 20,
      })
      if (reqId !== _searchSeq) return
      posts.value.push(...r.items)
      total.value = r.total
    }
    if (posts.value.length >= total.value) finished.value = true
  } catch (e) {
    if (reqId !== _searchSeq) return
    console.error('加载微博失败', e)
    finished.value = true
  } finally {
    if (reqId === _searchSeq) loading.value = false
  }
}

function resetFilters() {
  keyword.value = ''
  year.value = undefined
  month.value = undefined
  hasMedia.value = undefined
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

  // 滚动到底部加载更多
  scrollRef.value?.addEventListener('scroll', () => {
    const el = scrollRef.value!
    if (el.scrollTop + el.clientHeight >= el.scrollHeight - 60 && !loading.value && !finished.value) {
      page.value += 1
      doSearch(true)
    }
  })
})

watch([year, month, hasMedia], () => doSearch())
</script>

<style scoped>
.toolbar { margin-bottom: 16px; }
.filters { display: flex; gap: 10px; flex-wrap: wrap; }
.scroll-area { height: calc(100vh - 200px); overflow-y: auto; padding-right: 4px; }
.load-more { text-align: center; color: #9ca3af; padding: 12px; }
.comment { padding: 8px 0; border-bottom: 1px dashed #eee; font-size: 14px; line-height: 1.6; }
.cname { color: #e6162d; }
.empty { color: #9ca3af; text-align: center; padding: 30px; }
</style>