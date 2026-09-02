package com.weiboarchive

import android.app.Application
import android.util.Log
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import java.io.File

class App : Application() {
    override fun onCreate() {
        super.onCreate()
        extractFfmpeg()
        if (!Python.isStarted()) {
            Python.start(AndroidPlatform(this))
        }
    }

    private fun extractFfmpeg() {
        try {
            val dest = File(filesDir, "ffmpeg/ffmpeg")
            if (dest.exists()) return
            dest.parentFile?.mkdirs()
            assets.open("ffmpeg/ffmpeg").use { input ->
                dest.outputStream().use { output -> input.copyTo(output) }
            }
            dest.setExecutable(true, false)
            dest.setReadable(true, false)
            Log.i("WeiboApp", "ffmpeg 已解压到 ${dest.absolutePath}")
        } catch (e: Exception) {
            Log.e("WeiboApp", "ffmpeg 解压失败", e)
        }
    }
}
