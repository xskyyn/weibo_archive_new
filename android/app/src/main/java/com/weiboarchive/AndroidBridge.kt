package com.weiboarchive

import android.content.Context
import android.content.Intent
import android.webkit.JavascriptInterface

class AndroidBridge(private val context: Context) {

    @JavascriptInterface
    fun isAndroid(): Boolean = true

    @JavascriptInterface
    fun startLogin(sid: String) {
        val intent = Intent(context, LoginActivity::class.java).apply {
            putExtra("sid", sid)
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        context.startActivity(intent)
    }
}
