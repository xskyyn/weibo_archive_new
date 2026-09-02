<template>
  <article class="post-card">
    <div class="head">
      <el-avatar :size="36" :src="post.user.profile_image_url || undefined">
        {{ (post.user.screen_name || '?')[0] }}
      </el-avatar>
      <div class="info">
        <div class="name">{{ post.user.screen_name || '未知用户' }}</div>
        <div class="time">
          {{ fmtTime }}
          <span v-if="post.region_name" class="region">{{ post.region_name }}</span>
        </div>
      </div>
    </div>

    <div class="text" v-html="rendered"></div>

    <div v-if="post.media.length" class="media">
      <template v-for="m in post.media" :key="m.id">
        <el-image
          v-if="m.type === 'pic'"
          class="pic"
          :src="m.media_url || m.url"
          :preview-src-list="previewList"
          :initial-index="picIndex(m)"
          fit="cover"
          :infinite="false"
        />
        <video
          v-else-if="m.type === 'video'"
          :src="m.media_url || m.url"
          controls
          class="pic"
        />
      </template>
    </div>

    <div class="foot">
      <span>转发 {{ post.reposts_count }}</span>
      <span class="clickable" @click="$emit('show-comments', post)">评论 {{ post.comments_count }}</span>
      <span>赞 {{ post.attitudes_count }}</span>
      <a :href="`/api/export/markdown/${post.id}`" target="_blank" class="md">Markdown</a>
    </div>
  </article>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { PostItem } from '@/api/http'

const props = defineProps<{ post: PostItem }>()
defineEmits<{ (e: 'show-comments', post: PostItem): void }>()

const rendered = computed(() => linkify(cleanHtml(props.post.raw_html || props.post.text)))
const fmtTime = computed(() => {
  if (!props.post.created_at) return ''
  const d = new Date(props.post.created_at)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(
    d.getDate(),
  ).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
})

const previewList = computed(() => props.post.media.filter((m) => m.type === 'pic').map((m) => m.media_url || m.url))
function picIndex(m: any) {
  return props.post.media.filter((x) => x.type === 'pic').findIndex((x) => x.id === m.id)
}

function cleanHtml(html: string): string {
  return String(html)
    .replace(/<a[^>]*class="[^"]*url-icon[^"]*"[^>]*>.*?<\/a>/g, (m) => {
      const icon = 'icon'
      return ''
    })
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/<[^>]+>/g, '') // 去掉所有标签
    .replace(/\n{3,}/g, '\n\n')
    .replace(/ /g, ' ')
}

function linkify(text: string): string {
  return text
    .replace(/&nbsp;/g, ' ')
    .replace(/https?:\/\/[^\s]+/g, (u) => `<a href="${u}" target="_blank" rel="nofollow">${u}</a>`)
    .replace(/\n/g, '<br/>')
}
</script>

<style scoped>
.post-card { background: #fff; border-radius: 10px; padding: 16px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,.06); }
.head { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
.name { font-weight: 600; }
.time { color: #9ca3af; font-size: 12px; }
.region { color: #6b7280; margin-left: 6px; font-size: 12px; }
.text { line-height: 1.7; word-break: break-word; }
.media { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
.pic { width: 160px; height: 160px; border-radius: 8px; object-fit: cover; background: #f3f4f6; }
.foot { margin-top: 12px; color: #9ca3af; font-size: 13px; display: flex; gap: 16px; }
.clickable { cursor: pointer; color: #e6162d; }
.md { margin-left: auto; color: #2563eb; }
</style>