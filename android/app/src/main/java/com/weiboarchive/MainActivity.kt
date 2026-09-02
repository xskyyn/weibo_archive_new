package com.weiboarchive

import android.Manifest
import android.annotation.SuppressLint
import android.app.DownloadManager
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Environment
import android.webkit.CookieManager
import android.webkit.DownloadListener
import android.webkit.MimeTypeMap
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import kotlin.concurrent.thread

class MainActivity : AppCompatActivity() {

    private lateinit var webView: WebView
    private var filePathCallback: ValueCallback<Array<Uri>>? = null

    private val requestPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (!granted) {
            Toast.makeText(this, "未授予通知权限，后台任务提醒可能不可见", Toast.LENGTH_SHORT).show()
        }
    }

    private val fileChooserLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        val callback = filePathCallback ?: return@registerForActivityResult
        filePathCallback = null
        if (result.resultCode == RESULT_OK && result.data?.data != null) {
            callback.onReceiveValue(arrayOf(result.data!!.data!!))
        } else {
            callback.onReceiveValue(null)
        }
    }

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        startBackendService()
        requestNotificationPermission()

        webView = WebView(this)
        setContentView(webView)
        setupWebView()
        waitForBackendAndLoad()
    }

    private fun startBackendService() {
        val intent = Intent(this, BackendService::class.java)
        ContextCompat.startForegroundService(this, intent)
    }

    private fun requestNotificationPermission() {
        if (Build.VERSION.SDK_INT >= 33) {
            val granted = ContextCompat.checkSelfPermission(
                this, Manifest.permission.POST_NOTIFICATIONS
            ) == PackageManager.PERMISSION_GRANTED
            if (!granted) {
                requestPermissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
            }
        }
    }

    @SuppressLint("SetJavaScriptEnabled")
    private fun setupWebView() {
        webView.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            databaseEnabled = true
            allowFileAccess = true
            mediaPlaybackRequiresUserGesture = false
            mixedContentMode = WebSettings.MIXED_CONTENT_ALWAYS_ALLOW
            useWideViewPort = true
            loadWithOverviewMode = true
            cacheMode = WebSettings.LOAD_DEFAULT
        }
        CookieManager.getInstance().setAcceptCookie(true)
        CookieManager.getInstance().setAcceptThirdPartyCookies(webView, true)

        webView.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView?, request: WebResourceRequest?): Boolean {
                val url = request?.url?.toString() ?: return false
                if (url.startsWith("http://") || url.startsWith("https://")) {
                    return false
                }
                return false
            }
        }

        webView.webChromeClient = object : WebChromeClient() {
            override fun onCreateWindow(
                view: WebView?, isDialog: Boolean, isUserGesture: Boolean, resultMsg: android.os.Message?
            ): Boolean {
                val newWebView = WebView(this@MainActivity)
                newWebView.settings.javaScriptEnabled = true
                val transport = resultMsg?.obj as? WebView.WebViewTransport ?: return false
                transport.webView = newWebView
                resultMsg.sendToTarget()
                newWebView.webViewClient = object : WebViewClient() {
                    override fun onPageFinished(view: WebView?, url: String?) {
                        view?.loadUrl(url ?: return)
                    }
                }
                return true
            }

            override fun onShowFileChooser(
                webView: WebView?,
                filePathCallback: ValueCallback<Array<Uri>>?,
                fileChooserParams: FileChooserParams?
            ): Boolean {
                this@MainActivity.filePathCallback = filePathCallback
                val intent = fileChooserParams?.createIntent()
                if (intent != null) {
                    fileChooserLauncher.launch(intent)
                } else {
                    filePathCallback?.onReceiveValue(null)
                    this@MainActivity.filePathCallback = null
                }
                return true
            }
        }

        webView.setDownloadListener(DownloadListener { url, userAgent, contentDisposition, mimetype, contentLength ->
            downloadFile(url, userAgent, contentDisposition, mimetype)
        })

        webView.addJavascriptInterface(AndroidBridge(this), "AndroidBridge")
    }

    private fun downloadFile(url: String, userAgent: String, contentDisposition: String, mimetype: String) {
        try {
            val filename = parseFilename(contentDisposition, url)
            val request = DownloadManager.Request(Uri.parse(url)).apply {
                setMimeType(mimetype)
                setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
                setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, filename)
            }
            val dm = getSystemService(Context.DOWNLOAD_SERVICE) as DownloadManager
            dm.enqueue(request)
            Toast.makeText(this, "已开始下载：$filename", Toast.LENGTH_SHORT).show()
        } catch (e: Exception) {
            Toast.makeText(this, "下载失败：${e.message}", Toast.LENGTH_SHORT).show()
        }
    }

    private fun parseFilename(contentDisposition: String?, url: String): String {
        val match = Regex("filename\\*?=(?:UTF-8'')?\"?([^\";]+)\"?").find(contentDisposition ?: "")
        val name = match?.groupValues?.get(1)?.trim() ?: url.substringAfterLast('/')
        return Uri.decode(name).ifBlank { "download_${System.currentTimeMillis()}" }
    }

    private fun waitForBackendAndLoad() {
        thread(name = "weibo-wait-backend") {
            var ready = false
            for (i in 0..150) {
                try {
                    val conn = java.net.URL("http://127.0.0.1:${BackendService.PORT}/api/version")
                        .openConnection() as java.net.HttpURLConnection
                    conn.connectTimeout = 500
                    conn.readTimeout = 500
                    if (conn.responseCode == 200) {
                        ready = true
                        break
                    }
                } catch (e: Exception) {
                    // 后端尚未就绪，继续等待
                }
                Thread.sleep(200)
            }
            runOnUiThread {
                if (ready) {
                    webView.loadUrl("http://127.0.0.1:${BackendService.PORT}/")
                } else {
                    Toast.makeText(this, "后端启动超时，请重启应用", Toast.LENGTH_LONG).show()
                }
            }
        }
    }

    override fun onBackPressed() {
        if (webView.canGoBack()) {
            webView.goBack()
        } else {
            super.onBackPressed()
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        webView.destroy()
    }
}
