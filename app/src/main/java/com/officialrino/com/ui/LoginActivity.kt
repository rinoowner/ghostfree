package com.officialrino.com.ui

import android.content.Context
import android.content.Intent
import android.content.SharedPreferences
import android.os.Bundle
import android.webkit.JavascriptInterface
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.appcompat.app.AppCompatActivity
import com.officialrino.com.R
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class LoginActivity : AppCompatActivity() {

    lateinit var webView: WebView
    private lateinit var sharedPrefs: SharedPreferences
    
    companion object {
        private const val PREFS_NAME = "OfficialrinoPrefs"
        private const val SAVED_KEY = "saved_key"
        private const val SAVED_EXPIRY = "saved_expiry"
    }
    
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.clearFlags(android.view.WindowManager.LayoutParams.FLAG_SECURE)
        setContentView(R.layout.activity_login)

        // Make app full screen
        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.R) {
            window.insetsController?.hide(android.view.WindowInsets.Type.statusBars() or android.view.WindowInsets.Type.navigationBars())
        } else {
            @Suppress("DEPRECATION")
            window.setFlags(
                android.view.WindowManager.LayoutParams.FLAG_FULLSCREEN,
                android.view.WindowManager.LayoutParams.FLAG_FULLSCREEN
            )
        }

        sharedPrefs = getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        
        webView = findViewById(R.id.webView)
        webView.settings.javaScriptEnabled = true
        webView.settings.domStorageEnabled = true
        webView.settings.cacheMode = android.webkit.WebSettings.LOAD_DEFAULT
        
        // Add Javascript Interface
        webView.addJavascriptInterface(LoginAppInterface(this), "Android")

        webView.webViewClient = object : WebViewClient() {
            override fun onPageFinished(view: WebView?, url: String?) {
                super.onPageFinished(view, url)
                val savedKey = sharedPrefs.getString(SAVED_KEY, null)
                if (savedKey != null) {
                    webView.evaluateJavascript("document.getElementById('license-key').value = '$savedKey'", null)
                }
            }
        }

        webView.loadUrl("file:///android_asset/login.html")
    }

    fun verifyKey(key: String) {
        webView.evaluateJavascript("document.getElementById('status_msg').innerText = '> ESTABLISHING_CONNECTION...'", null)
        
        CoroutineScope(Dispatchers.IO).launch {
            val result = ApiClient.verifyKey(key)
            
            withContext(Dispatchers.Main) {
                if (result.success) {
                    sharedPrefs.edit()
                        .putString(SAVED_KEY, key)
                        .putLong(SAVED_EXPIRY, result.expiry)
                        .apply()
                    
                    startActivity(Intent(this@LoginActivity, MainActivity::class.java))
                    finish()
                } else {
                    val errorMsg = "[X] ACCESS_DENIED: ${result.reason.uppercase()}"
                    webView.evaluateJavascript("document.getElementById('status_msg').innerText = '$errorMsg'", null)
                    webView.evaluateJavascript("document.getElementById('status_msg').style.color = 'red'", null)
                    webView.evaluateJavascript("hideLoading()", null)
                    
                    if (result.reason.contains("expired")) {
                        sharedPrefs.edit().remove(SAVED_KEY).remove(SAVED_EXPIRY).apply()
                    }
                }
            }
        }
    }

    class LoginAppInterface(private val activity: LoginActivity) {
        @JavascriptInterface
        fun validateDevice(key: String) {
            activity.runOnUiThread {
                if (key.trim().isNotEmpty()) {
                    activity.verifyKey(key.trim())
                } else {
                    activity.webView.evaluateJavascript("document.getElementById('status_msg').innerText = '[!] PLEASE_INPUT_KEY'", null)
                    activity.webView.evaluateJavascript("document.getElementById('status_msg').style.color = 'red'", null)
                }
            }
        }
    }
}