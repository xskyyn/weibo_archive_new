<template>
  <div>
    <div class="stat-grid">
      <el-card class="stat" shadow="never"><div class="num">{{ stats.posts }}</div><div class="lbl">总微博</div></el-card>
      <el-card class="stat" shadow="never"><div class="num">{{ stats.comments }}</div><div class="lbl">总评论</div></el-card>
      <el-card class="stat" shadow="never"><div class="num">{{ stats.media }}</div><div class="lbl">总媒体</div></el-card>
      <el-card class="stat" shadow="never"><div class="num">{{ stats.videos }}</div><div class="lbl">视频</div></el-card>
      <el-card class="stat" shadow="never"><div class="num">{{ stats.users }}</div><div class="lbl">用户</div></el-card>
    </div>

    <el-card shadow="never" class="mt">
      <template #header>发博活跃度（按星期-小时）</template>
      <div ref="heatRef" style="height: 360px"></div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import * as echarts from 'echarts'
import { getStats, getTimeline } from '@/api'
import type { Stats } from '@/api/http'

const stats = ref<Stats>({ users: 0, posts: 0, comments: 0, media: 0, videos: 0 })
const heatRef = ref<HTMLDivElement>()
let chart: echarts.ECharts | null = null

async function loadStats() {
  stats.value = (await getStats()) as Stats
}

async function loadHeatmap() {
  const tl = await getTimeline()
  const data: any[] = []
  tl.matrix.forEach((row: number[], di: number) => {
    row.forEach((cnt, hi) => {
      if (cnt > 0) data.push([hi, di, cnt])
    })
  })
  if (!heatRef.value) return
  chart = echarts.init(heatRef.value)
  chart.setOption({
    tooltip: { position: 'top' },
    grid: { left: 80, right: 30, top: 10, bottom: 40 },
    xAxis: { type: 'category', data: tl.hours, name: '时' },
    yAxis: { type: 'category', data: tl.days, name: '星期' },
    visualMap: {
      min: 0,
      max: Math.max(10, ...data.map((d) => d[2])),
      calculable: true,
      orient: 'horizontal',
      left: 'center',
      bottom: 0,
    },
    series: [
      {
        name: '发博数',
        type: 'heatmap',
        data,
        label: { show: false },
        emphasis: { itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.5)' } },
      },
    ],
  })
}

function onResize() {
  chart?.resize()
}

onMounted(async () => {
  await Promise.all([loadStats(), loadHeatmap()])
  window.addEventListener('resize', onResize)
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  chart?.dispose()
})
</script>

<style scoped>
.stat-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 16px; }
.stat { text-align: center; }
.num { font-size: 30px; font-weight: 700; color: #e6162d; }
.lbl { color: #6b7280; margin-top: 4px; }
.mt { margin-top: 16px; }
@media (max-width: 900px) { .stat-grid { grid-template-columns: repeat(2, 1fr); } }
</style>