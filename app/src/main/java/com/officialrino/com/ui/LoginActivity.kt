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
import android.content.pm.PackageManager
import android.util.Log
import android.widget.Toast
import java.security.MessageDigest

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
        
        // Check signature
        if (!checkSignature()) {
            Toast.makeText(this, "Illegal APK modification detected!", Toast.LENGTH_LONG).show()
            finish()
            return
        }
        
        webView = findViewById(R.id.webView)
        webView.settings.javaScriptEnabled = true
        webView.settings.domStorageEnabled = true
        webView.settings.cacheMode = android.webkit.WebSettings.LOAD_DEFAULT
        
        webView.addJavascriptInterface(LoginAppInterface(this), "Android")

        webView.webViewClient = object : WebViewClient() {
            override fun onPageFinished(view: WebView?, url: String?) {
                super.onPageFinished(view, url)
            }

            @Suppress("DEPRECATION")
            override fun shouldOverrideUrlLoading(view: WebView?, url: String?): Boolean {
                if (url != null && url.startsWith("https://t.me/")) {
                    val intent = Intent(Intent.ACTION_VIEW, android.net.Uri.parse(url))
                    intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                    try {
                        startActivity(intent)
                    } catch (e: Exception) {
                        val browserIntent = Intent(Intent.ACTION_VIEW, android.net.Uri.parse(url))
                        browserIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                        startActivity(browserIntent)
                    }
                    return true
                }
                return false
            }
        }

        val savedKey = sharedPrefs.getString(SAVED_KEY, null)
        val keyToVerify = savedKey ?: "GhostXServerxFree"
        
        kotlinx.coroutines.CoroutineScope(kotlinx.coroutines.Dispatchers.IO).launch {
            val result = ApiClient.verifyKey(this@LoginActivity, keyToVerify)
            kotlinx.coroutines.withContext(kotlinx.coroutines.Dispatchers.Main) {
                if (result.success) {
                    sharedPrefs.edit()
                        .putString(SAVED_KEY, keyToVerify)
                        .putLong(SAVED_EXPIRY, result.expiry)
                        .apply()
                    
                    startActivity(Intent(this@LoginActivity, MainActivity::class.java))
                    finish()
                } else {
                    if (savedKey != null) {
                        sharedPrefs.edit().remove(SAVED_KEY).remove(SAVED_EXPIRY).apply()
                    }
                    webView.loadUrl("file:///android_asset/login.html")
                }
            }
        }
    }

    fun verifyKey(key: String) {
        webView.evaluateJavascript("document.getElementById('status_msg').innerText = '> ESTABLISHING_CONNECTION...'", null)
        
        CoroutineScope(Dispatchers.IO).launch {
            val result = ApiClient.verifyKey(this@LoginActivity, key)
            
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

    @Suppress("DEPRECATION")
    private fun checkSignature(): Boolean {
        try {
            val info = packageManager.getPackageInfo(packageName, PackageManager.GET_SIGNATURES)
            val signatures = info.signatures
            if (signatures != null) {
                for (signature in signatures) {
                    val md = MessageDigest.getInstance("SHA-1")
                    md.update(signature.toByteArray())
                    val currentSignature = bytesToHex(md.digest())
                    
                    Log.d("SIGNATURE_CHECK", "Current Signature: $currentSignature")
                    
                    val expectedSignature = "811A7F270BC3082C3C4F45EC5CA59A6817ED4B45"
                    
                    if (currentSignature == expectedSignature) {
                        return true
                    } else {
                        if (expectedSignature == "YOUR_SHA1_SIGNATURE_HERE") {
                            Log.w("SIGNATURE_CHECK", "Please set your actual signature in LoginActivity.kt!")
                            return true
                        }
                    }
                }
            }
        } catch (e: Exception) {
            e.printStackTrace()
        }
        return false
    }

    private fun bytesToHex(bytes: ByteArray): String {
        val hexArray = "0123456789ABCDEF".toCharArray()
        val hexChars = CharArray(bytes.size * 2)
        for (j in bytes.indices) {
            val v = bytes[j].toInt() and 0xFF
            hexChars[j * 2] = hexArray[v ushr 4]
            hexChars[j * 2 + 1] = hexArray[v and 0x0F]
        }
        return String(hexChars)
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