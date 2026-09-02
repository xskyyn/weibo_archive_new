package com.weiboarchive

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Intent
import android.os.Build
import android.os.IBinder
import android.util.Log
import androidx.core.app.NotificationCompat
import com.chaquo.python.Python
import kotlin.concurrent.thread

class BackendService : Service() {

    companion object {
        private const val TAG = "WeiboBackend"
        private const val CHANNEL_ID = "weibo_backend"
        private const val NOTIFICATION_ID = 1001
        const val PORT = 8964
    }

    override fun onCreate() {
        super.onCreate()
        createChannel()
        startForeground(NOTIFICATION_ID, buildNotification())
        thread(name = "weibo-backend") {
            try {
                val py = Python.getInstance()
                val module = py.getModule("android_entry")
                module.callAttr("start_server", PORT)
            } catch (e: Throwable) {
                Log.e(TAG, "后端启动失败", e)
            }
        }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int = START_STICKY

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        super.onDestroy()
        try {
            val py = Python.getInstance()
            py.getModule("android_entry").callAttr("stop_server")
        } catch (e: Throwable) {
            Log.w(TAG, "后端停止异常", e)
        }
    }

    private fun createChannel() {
        val manager = getSystemService(NotificationManager::class.java)
        val channel = NotificationChannel(
            CHANNEL_ID, "微博备份后台服务", NotificationManager.IMPORTANCE_LOW
        ).apply {
            description = "保持归档任务在后台运行"
        }
        manager.createNotificationChannel(channel)
    }

    private fun buildNotification(): android.app.Notification {
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("微博备份运行中")
            .setContentText("归档服务正在后台运行")
            .setSmallIcon(android.R.drawable.stat_sys_download)
            .setOngoing(true)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .build()
    }
}
