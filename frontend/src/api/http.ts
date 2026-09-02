import axios, { type AxiosInstance } from 'axios'

const http: AxiosInstance = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

export interface MediaItem {
  id: number
  post_id: number
  type: 'pic' | 'video' | 'livephoto'
  url?: string
  local_path?: string | null
  media_url?: string | null
  ext?: string | null
  width?: number | null
  height?: number | null
}

export interface PostItem {
  id: number
  mid: string
  text: string
  raw_html?: string | null
  created_at: string | null
  created_ts: number
  reposts_count: number
  comments_count: number
  attitudes_count: number
  region_name?: string | null
  retweeted_status_id?: number | null
  user: { id: number | null; screen_name: string; profile_image_url?: string }
  media: MediaItem[]
}

export interface Stats {
  users: number
  posts: number
  comments: number
  media: number
  videos: number
}

export default http