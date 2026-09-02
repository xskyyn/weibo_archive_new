package com.weiboarchive

import android.annotation.SuppressLint
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.webkit.CookieManager
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.appcompat.app.AppCompatActivity
import kotlin.concurrent.thread
import org.json.JSONObject

class LoginActivity : AppCompatActivity() {

    private lateinit var webView: WebView
    private var sid: String = ""
    private val handler = Handler(Looper.getMainLooper())
    private var polling = false
    private var submitted = false

    companion object {
        private const val TAG = "WeiboLogin"
        private const val LOGIN_URL =
            "https://passport.weibo.cn/signin/login?entry=mweibo&res=wel&wm=3349&r=https%3A%2F%2Fm.weibo.cn"
        private val AUTH_COOKIES = listOf("SUB", "SUBSCRIBE", "gsid")
        private val COOKIE_URLS = listOf(
            "https://passport.weibo.cn", "https://weibo.cn", "https://m.weibo.cn", "https://weibo.com"
        )
    }

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        sid = intent.getStringExtra("sid") ?: ""
        webView = WebView(this)
        setContentView(webView)

        webView.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            mixedContentMode = WebSettings.MIXED_CONTENT_ALWAYS_ALLOW
            userAgentString = userAgentString.replace("; wv", "")
            // 移动端视口适配：按手机宽度渲染，避免登录页右侧被截断
            useWideViewPort = true
            loadWithOverviewMode = true
            setSupportZoom(true)
            builtInZoomControls = true
            displayZoomControls = false
            textZoom = 100
        }
        CookieManager.getInstance().setAcceptCookie(true)
        CookieManager.getInstance().setAcceptThirdPartyCookies(webView, true)

        webView.webViewClient = object : WebViewClient() {
            override fun onPageFinished(view: WebView?, url: String?) {
                startPolling()
            }
        }
        // 清除与主界面共享的旧微博 Cookie，避免残留 SUB 导致一打开就被判定已登录而立即关闭
        CookieManager.getInstance().removeAllCookies {
            CookieManager.getInstance().flush()
            webView.loadUrl(LOGIN_URL)
        }
    }

    private fun startPolling() {
        if (polling || submitted) return
        polling = true
        handler.post(object : Runnable {
            override fun run() {
                if (submitted) return
                val cookies = getCookies()
                if (hasAuthCookie(cookies)) {
                    submitCookies(cookies)
                } else {
                    handler.postDelayed(this, 2000)
                }
            }
        })
    }

    private fun getCookies(): Map<String, String> {
        val manager = CookieManager.getInstance()
        val map = mutableMapOf<String, String>()
        COOKIE_URLS.forEach { url ->
            val cookieStr = manager.getCookie(url) ?: return@forEach
            cookieStr.split(";").forEach {
                val parts = it.trim().split("=", limit = 2)
                if (parts.size == 2 && parts[0].isNotBlank()) map[parts[0]] = parts[1]
            }
        }
        return map
    }

    private fun hasAuthCookie(cookies: Map<String, String>): Boolean =
        cookies.keys.any { AUTH_COOKIES.contains(it) }

    private fun submitCookies(cookies: Map<String, String>) {
        submitted = true
        polling = false
        thread(name = "weibo-login-submit") {
            try {
                val json = JSONObject()
                val cookieObj = JSONObject()
                cookies.forEach { (k, v) -> cookieObj.put(k, v) }
                json.put("cookie", cookieObj)
                val url = java.net.URL("http://127.0.0.1:${BackendService.PORT}/api/auth/qr/$sid/complete")
                val conn = url.openConnection() as java.net.HttpURLConnection
                conn.requestMethod = "POST"
                conn.doOutput = true
                conn.connectTimeout = 5000
                conn.readTimeout = 5000
                conn.setRequestProperty("Content-Type", "application/json")
                conn.outputStream.use { it.write(json.toString().toByteArray()) }
                val code = conn.responseCode
                Log.i(TAG, "Cookie 提交结果: $code")
                runOnUiThread {
                    if (code == 200) {
                        finish()
                    } else {
                        submitted = false
                        startPolling()
                    }
                }
            } catch (e: Exception) {
                Log.w(TAG, "Cookie 提交失败", e)
                runOnUiThread {
                    submitted = false
                    startPolling()
                }
            }
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        handler.removeCallbacksAndMessages(null)
        webView.destroy()
    }
}
