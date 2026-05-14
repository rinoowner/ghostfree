package com.officialrino.com.ui

import android.app.Service
import android.content.Context
import android.content.Intent
import android.graphics.PixelFormat
import android.os.Build
import android.os.IBinder
import android.view.Gravity
import android.view.LayoutInflater
import android.view.MotionEvent
import android.view.View
import android.view.WindowManager
import android.widget.Button
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.SeekBar
import android.widget.TextView
import android.widget.Toast
import android.widget.Spinner
import android.widget.ArrayAdapter
import android.widget.AdapterView
import androidx.core.content.ContextCompat
import com.officialrino.com.R
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class FloatingWindowService : Service() {

    private lateinit var windowManager: WindowManager
    private lateinit var floatingView: View
    private lateinit var params: WindowManager.LayoutParams
    
    private lateinit var executeButton: Button
    private lateinit var statusText: TextView
    private lateinit var contentLayout: LinearLayout
    private lateinit var minimizedLayout: View
    private lateinit var displayIp: TextView
    private lateinit var displayPort: TextView
    private lateinit var attackTimeLabel: TextView
    private lateinit var durationSeekBar: SeekBar
    private lateinit var activeSlotsText: TextView
    
    private var isMinimized = false
    private var selectedDuration = 180
    private val serviceScope = CoroutineScope(Dispatchers.Main + Job())
    
    private val fakeMessages = arrayOf(
        "🔥 User ID 47x ne abhi 300s ka VIP attack lagaya...",
        "🔥 User ID 12k ne abhi target down kiya...",
        "🔥 New VIP User joined the server!",
        "🔥 Server load high: Paid users attacking...",
        "🔥 User ID 88p ne bypass method use kiya..."
    )
    
    private var isSearching = false

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        
        windowManager = getSystemService(Context.WINDOW_SERVICE) as WindowManager
        floatingView = LayoutInflater.from(this).inflate(R.layout.floating_window, null)

        val layoutType = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
        } else {
            @Suppress("DEPRECATION")
            WindowManager.LayoutParams.TYPE_PHONE
        }

        val density = resources.displayMetrics.density
        params = WindowManager.LayoutParams(
            (320 * density).toInt(),
            WindowManager.LayoutParams.WRAP_CONTENT,
            layoutType,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE,
            PixelFormat.TRANSLUCENT
        )

        params.gravity = Gravity.TOP or Gravity.START
        params.x = 100
        params.y = 100

        windowManager.addView(floatingView, params)

        // Initialize Views
        executeButton = floatingView.findViewById(R.id.float_execute_button)
        statusText = floatingView.findViewById(R.id.float_status_text)
        contentLayout = floatingView.findViewById(R.id.content_layout)
        minimizedLayout = floatingView.findViewById(R.id.minimized_layout)
        minimizedLayout.outlineProvider = android.view.ViewOutlineProvider.BACKGROUND
        displayIp = floatingView.findViewById(R.id.display_ip)
        displayPort = floatingView.findViewById(R.id.display_port)
        attackTimeLabel = floatingView.findViewById(R.id.attack_time_label)
        durationSeekBar = floatingView.findViewById(R.id.duration_seekbar)
        activeSlotsText = floatingView.findViewById(R.id.active_slots_text)
        val btnGetIpPort = floatingView.findViewById<Button>(R.id.btn_get_ip_port)
        val closeButton = floatingView.findViewById<ImageView>(R.id.close_button)


        // Drag functionality
        val dragTouchListener = object : View.OnTouchListener {
            private var initialX: Int = 0
            private var initialY: Int = 0
            private var initialTouchX: Float = 0f
            private var initialTouchY: Float = 0f
            private var isMoved = false

            override fun onTouch(v: View, event: MotionEvent): Boolean {
                when (event.action) {
                    MotionEvent.ACTION_DOWN -> {
                        initialX = params.x
                        initialY = params.y
                        initialTouchX = event.rawX
                        initialTouchY = event.rawY
                        isMoved = false
                        return true
                    }
                    MotionEvent.ACTION_MOVE -> {
                        val dx = (event.rawX - initialTouchX).toInt()
                        val dy = (event.rawY - initialTouchY).toInt()
                        
                        if (Math.abs(dx) > 10 || Math.abs(dy) > 10) {
                            isMoved = true
                            params.x = initialX + dx
                            params.y = initialY + dy
                            windowManager.updateViewLayout(floatingView, params)
                        }
                        return true
                    }
                    MotionEvent.ACTION_UP -> {
                        if (!isMoved) {
                            v.performClick()
                        }
                        return true
                    }
                }
                return false
            }
        }
        
        floatingView.findViewById<View>(R.id.header_layout).setOnTouchListener(dragTouchListener)
        minimizedLayout.setOnTouchListener(dragTouchListener)

        // X Button now minimizes
        closeButton.setOnClickListener {
            vibrate(30)
            applyClickAnimation(it)
            toggleMinimize(true)
            showGlobalToast("WINDOW MINIMIZED")
        }

        minimizedLayout.setOnClickListener {
            vibrate(30)
            applyClickAnimation(it)
            toggleMinimize(false)
        }

        executeButton.setOnClickListener {
            vibrate(50)
            applyClickAnimation(it)
            
            // Low Priority Slots Simulation
            if (Math.random() < 0.4) {
                showVipDialog("Server Busy, Paid users are attacking. Buy Premium for instant attack.")
                return@setOnClickListener
            }
            
            performSmartLaunch()
        }

        val btnBuyPremium = floatingView.findViewById<Button>(R.id.btn_buy_premium)
        btnBuyPremium.setOnClickListener {
            vibrate(50)
            applyClickAnimation(it)
            
            val intent = Intent(Intent.ACTION_VIEW, android.net.Uri.parse("https://t.me/officialrino?text=/buy_premium"))
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            try {
                startActivity(intent)
            } catch (e: Exception) {
                showGlobalToast("Telegram not found. Visit t.me/officialrino")
            }
        }
        
        btnGetIpPort.setOnClickListener {
            vibrate(50)
            applyClickAnimation(it)
            
            NetworkCaptureService.clearCaptured()
            isSearching = true
            statusText.text = "SEARCHING..."
            displayIp.text = "IP: "
            displayPort.text = "PORT: "
            showGlobalToast("SEARCHING FOR TARGET...")

            val vpnIntent = android.net.VpnService.prepare(this)
            if (vpnIntent != null) {
                val intent = Intent(this, MainActivity::class.java)
                intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                intent.putExtra("REQUEST_VPN", true)
                startActivity(intent)
                showGlobalToast("Please grant VPN permission in the app")
            } else {
                val intent = Intent(this, NetworkCaptureService::class.java)
                ContextCompat.startForegroundService(this, intent)
            }
        }

        durationSeekBar.max = 5
        durationSeekBar.progress = 1
        selectedDuration = 60
        attackTimeLabel.text = "Attack Time: 60s"

        var triedToGoPastLimit = false
        durationSeekBar.setOnSeekBarChangeListener(object : SeekBar.OnSeekBarChangeListener {
            override fun onProgressChanged(seekBar: SeekBar?, progress: Int, fromUser: Boolean) {
                if (fromUser && progress > 1) {
                    seekBar?.progress = 1
                    triedToGoPastLimit = true
                    return
                }
                
                val duration = if (progress == 0) 30 else progress * 60
                selectedDuration = duration
                attackTimeLabel.text = "Attack Time: ${duration}s"
                
                if (fromUser) {
                    vibrate(30)
                }
            }
            override fun onStartTrackingTouch(seekBar: SeekBar?) {
                triedToGoPastLimit = false
            }
            override fun onStopTrackingTouch(seekBar: SeekBar?) {
                if (triedToGoPastLimit) {
                    vibrate(50)
                    showVipDialog("Upgrade to VIP for duration > 60s.")
                    triedToGoPastLimit = false
                }
            }
        })

        startSyncLoop()
        startTickerLoop()
    }

    private fun startTickerLoop() {
        val tickerText = floatingView.findViewById<TextView>(R.id.live_ticker)
        serviceScope.launch {
            var index = 0
            while (true) {
                tickerText.text = fakeMessages[index]
                index = (index + 1) % fakeMessages.size
                kotlinx.coroutines.delay(5000)
            }
        }
    }

    private fun toggleMinimize(minimize: Boolean) {
        isMinimized = minimize
        val density = resources.displayMetrics.density
        if (minimize) {
            contentLayout.visibility = View.GONE
            minimizedLayout.visibility = View.VISIBLE
            params.width = (56 * density).toInt()
            params.height = (56 * density).toInt()
        } else {
            contentLayout.visibility = View.VISIBLE
            minimizedLayout.visibility = View.GONE
            params.width = (220 * density).toInt()
            params.height = WindowManager.LayoutParams.WRAP_CONTENT
        }
        windowManager.updateViewLayout(floatingView, params)
    }

    private fun performSmartLaunch() {
        val ip = NetworkCaptureService.getCapturedIp()
        val port = NetworkCaptureService.getCapturedPort()

        if (ip == null || port == null) {
            showGlobalToast("WAITING FOR TARGET...")
            return
        }

        val sharedPrefs = getSharedPreferences("OfficialrinoPrefs", Context.MODE_PRIVATE)
        val key = sharedPrefs.getString("saved_key", null) ?: run {
            showGlobalToast("❌ LOGIN REQUIRED")
            return
        }

        // Daily Limit Check
        val today = java.text.SimpleDateFormat("yyyy-MM-dd", java.util.Locale.getDefault()).format(java.util.Date())
        val savedDate = sharedPrefs.getString("attack_date", "")
        var attackCount = sharedPrefs.getInt("attack_count", 0)
        
        if (savedDate != today) {
            attackCount = 0
            sharedPrefs.edit().putString("attack_date", today).putInt("attack_count", 0).apply()
        }
        
        if (attackCount >= 3) {
            showVipDialog("Today's Free Limit Over! Kal tak ka wait karein ya abhi Unlimited attacks ke liye Premium lein.")
            return
        }

        // One-Time Sample Check
        val isFirstAttack = sharedPrefs.getBoolean("is_first_attack", true)
        var durationToUse = selectedDuration
        
        if (isFirstAttack) {
            durationToUse = 300
            showGlobalToast("Welcome Gift: Enjoy 300s VIP Attack!")
        }

        executeButton.isEnabled = false
        executeButton.text = "LAUNCHING..."
        showGlobalToast("INITIATING ATTACK...")

        serviceScope.launch {
            val result = ApiClient.startAttack(this@FloatingWindowService, key, ip, port, durationToUse)
            executeButton.isEnabled = true
            executeButton.text = "START ATTACK"
            if (result.success) {
                sharedPrefs.edit()
                    .putLong("last_attack_time", System.currentTimeMillis())
                    .putInt("last_attack_duration", durationToUse)
                    .putInt("attack_count", attackCount + 1)
                    .putBoolean("is_first_attack", false)
                    .apply()
                showGlobalToast("🚀 ATTACK SENT SUCCESSFULLY!")
                vibrate(100)
            } else {
                showGlobalToast("❌ FAILED: ${result.message}")
                if (result.message.contains("Key expired", ignoreCase = true) || result.message.contains("401")) {
                    performLogout()
                }
            }
        }
    }

    private fun performLogout() {
        val sharedPrefs = getSharedPreferences("OfficialrinoPrefs", Context.MODE_PRIVATE)
        sharedPrefs.edit().clear().apply()
        
        showGlobalToast("❌ KEY EXPIRED. LOGGING OUT...")
        
        val intent = Intent(this, LoginActivity::class.java)
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        startActivity(intent)
        
        stopSelf()
    }

    private fun stopActiveAttack() {
        val sharedPrefs = getSharedPreferences("OfficialrinoPrefs", Context.MODE_PRIVATE)
        sharedPrefs.edit()
            .putLong("last_attack_time", 0)
            .putInt("last_attack_duration", 0)
            .apply()
        showGlobalToast("🛑 ATTACK STOPPED BY USER")
        attackTimeLabel.text = "Attack Time: 180s"
        durationSeekBar.progress = 180
    }

    private fun startSyncLoop() {
        serviceScope.launch {
            while (true) {
                val ip = NetworkCaptureService.getCapturedIp()
                val port = NetworkCaptureService.getCapturedPort()
                
                val sharedPrefs = getSharedPreferences("OfficialrinoPrefs", Context.MODE_PRIVATE)
                val lastAttackTime = sharedPrefs.getLong("last_attack_time", 0)
                val currentTime = System.currentTimeMillis()
                val cooldownDuration = 300 * 1000L // 300 seconds
                val cooldownEndTime = lastAttackTime + cooldownDuration
                
                val btnBuyPremium = floatingView.findViewById<Button>(R.id.btn_buy_premium)
                
                if (currentTime < cooldownEndTime) {
                    val remainingSec = (cooldownEndTime - currentTime) / 1000
                    
                    executeButton.isEnabled = false
                    executeButton.text = "COOLDOWN ${remainingSec}s"
                    
                    btnBuyPremium.text = "Skip Wait & Attack Now"
                    
                    if (ip != null && port != null) {
                        displayIp.text = "IP: $ip"
                        displayPort.text = "PORT: $port"
                    }
                } else {
                    executeButton.isEnabled = true
                    executeButton.text = "START ATTACK"
                    
                    btnBuyPremium.text = "BUY PREMIUM (TG)"
                    
                    if (isSearching) {
                        if (ip != null && port != null) {
                            isSearching = false
                            statusText.text = "IDLE"
                            displayIp.text = "IP: $ip"
                            displayPort.text = "PORT: $port"
                            showGlobalToast("TARGET ACQUIRED!")
                        } else {
                            statusText.text = "SEARCHING..."
                            displayIp.text = "IP: "
                            displayPort.text = "PORT: "
                        }
                    } else {
                        if (ip != null && port != null) {
                            displayIp.text = "IP: $ip"
                            displayPort.text = "PORT: $port"
                        } else {
                            displayIp.text = "IP: "
                            displayPort.text = "PORT: "
                        }
                    }
                }
                
                kotlinx.coroutines.delay(1000)
            }
        }

        serviceScope.launch {
            while (true) {
                try {
                    val attacksResult = ApiClient.getActiveAttacks()
                    if (attacksResult.success) {
                        updateActiveAttacksUI(attacksResult.attacks)
                    }
                } catch (e: Exception) {
                    // Ignore
                }
                kotlinx.coroutines.delay(5000)
            }
        }
    }

    private fun updateActiveAttacksUI(attacks: List<ApiClient.ActiveAttack>) {
        activeSlotsText.text = "ACTIVE SLOTS: ${attacks.size}/6"
    }

    private fun showGlobalToast(message: String) {
        Toast.makeText(this, message, Toast.LENGTH_SHORT).show()
    }

    private fun showVipDialog(message: String) {
        val builder = android.app.AlertDialog.Builder(this)
        builder.setTitle("GHOST X SERVER VIP")
        builder.setMessage(message)
        builder.setPositiveButton("BUY PREMIUM") { _, _ ->
            val intent = Intent(Intent.ACTION_VIEW, android.net.Uri.parse("https://t.me/officialrino?text=/buy_premium"))
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            try {
                startActivity(intent)
            } catch (e: Exception) {
                showGlobalToast("Telegram not found. Visit t.me/officialrino")
            }
        }
        builder.setNegativeButton("CANCEL", null)
        
        val dialog = builder.create()
        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.O) {
            dialog.window?.setType(WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY)
        } else {
            @Suppress("DEPRECATION")
            dialog.window?.setType(WindowManager.LayoutParams.TYPE_PHONE)
        }
        dialog.show()
    }

    private fun vibrate(durationMs: Long) {
        val vibrator = getSystemService(Context.VIBRATOR_SERVICE) as android.os.Vibrator
        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.O) {
            vibrator.vibrate(android.os.VibrationEffect.createOneShot(durationMs, android.os.VibrationEffect.DEFAULT_AMPLITUDE))
        } else {
            @Suppress("DEPRECATION")
            vibrator.vibrate(durationMs)
        }
    }

    private fun applyClickAnimation(view: View) {
        view.animate()
            .scaleX(0.95f)
            .scaleY(0.95f)
            .setDuration(100)
            .withEndAction {
                view.animate()
                    .scaleX(1.0f)
                    .scaleY(1.0f)
                    .setDuration(100)
                    .start()
            }
            .start()
    }

    override fun onDestroy() {
        super.onDestroy()
        serviceScope.cancel()
        if (::floatingView.isInitialized) {
            windowManager.removeView(floatingView)
        }
    }

    override fun onTaskRemoved(rootIntent: Intent?) {
        super.onTaskRemoved(rootIntent)
        stopSelf()
    }
}
