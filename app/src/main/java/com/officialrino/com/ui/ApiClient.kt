// Modified & Promoted by officialrino
package com.officialrino.com.ui

import android.content.Context
import android.provider.Settings
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import org.json.JSONObject
import java.util.concurrent.TimeUnit

object ApiClient {
    
    // ========== LOCAL TESTING URL ==========
    // Use "http://10.0.2.2:5001" for Android Emulator
    // Use "http://YOUR_PC_IP:5001" for Physical Device
    private fun getBaseUrl(): String {
        return "http://10.24.138.7:5001"
    }
    
    private val client = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .writeTimeout(15, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .build()
    
    fun getDeviceId(context: Context): String {
        return Settings.Secure.getString(
            context.contentResolver,
            Settings.Secure.ANDROID_ID
        ) ?: "unknown"
    }
    
    suspend fun verifyKey(key: String): VerificationResult {
        val baseUrl = getBaseUrl()
        val json = JSONObject().apply {
            put("key", key)
            put("device_id", "apk_device")
        }
        
        val mediaType = "application/json".toMediaTypeOrNull()
        val body = json.toString().toRequestBody(mediaType)
        
        val request = Request.Builder()
            .url("$baseUrl/api/verify-key")
            .post(body)
            .build()
        
        return try {
            val response = client.newCall(request).execute()
            val responseBody = response.body?.string() ?: "{}"
            
            if (response.isSuccessful) {
                val jsonResponse = JSONObject(responseBody)
                if (jsonResponse.optBoolean("success")) {
                    VerificationResult(true, "", jsonResponse.optLong("expiry"))
                } else {
                    VerificationResult(false, jsonResponse.optString("reason"), 0)
                }
            } else {
                VerificationResult(false, "Server Error: ${response.code}", 0)
            }
        } catch (e: Exception) {
            VerificationResult(false, "Connection error", 0)
        }
    }
    
    suspend fun startAttack(key: String, ip: String, port: Int, duration: Int): AttackResult {
        val baseUrl = getBaseUrl()
        val json = JSONObject().apply {
            put("key", key)
            put("device_id", "apk_device")
            put("ip", ip)
            put("port", port)
            put("duration", duration)
        }
        
        val mediaType = "application/json".toMediaTypeOrNull()
        val body = json.toString().toRequestBody(mediaType)
        
        val request = Request.Builder()
            .url("$baseUrl/api/attack")
            .post(body)
            .build()
        
        return try {
            val response = client.newCall(request).execute()
            val responseBody = response.body?.string() ?: "{}"
            
            if (response.isSuccessful) {
                val jsonResponse = JSONObject(responseBody)
                if (jsonResponse.optBoolean("success")) {
                    AttackResult(true, jsonResponse.optString("message"))
                } else {
                    AttackResult(false, jsonResponse.optString("reason"))
                }
            } else {
                AttackResult(false, "Server Error: ${response.code}")
            }
        } catch (e: Exception) {
            AttackResult(false, "Connection error")
        }
    }
    
    data class VerificationResult(val success: Boolean, val reason: String, val expiry: Long)
    data class AttackResult(val success: Boolean, val message: String)
}
