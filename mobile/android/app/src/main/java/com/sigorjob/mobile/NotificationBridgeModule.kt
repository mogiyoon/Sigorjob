package com.sigorjob.mobile

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.content.SharedPreferences
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.work.Constraints
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import com.facebook.react.bridge.Promise
import com.facebook.react.bridge.ReactApplicationContext
import com.facebook.react.bridge.ReactContextBaseJavaModule
import com.facebook.react.bridge.ReactMethod
import java.util.concurrent.TimeUnit

class NotificationBridgeModule(private val reactContext: ReactApplicationContext) :
  ReactContextBaseJavaModule(reactContext) {

  override fun getName(): String = "NotificationBridge"

  @ReactMethod
  fun savePairingConfig(url: String, token: String, promise: Promise) {
    try {
      preferences().edit()
        .putString(KEY_URL, url)
        .putString(KEY_TOKEN, token)
        .apply()
      ensureChannel()
      startBackgroundSyncInternal()
      promise.resolve(true)
    } catch (error: Exception) {
      promise.reject("save_pairing_failed", error)
    }
  }

  @ReactMethod
  fun clearPairingConfig(promise: Promise) {
    try {
      preferences().edit()
        .remove(KEY_URL)
        .remove(KEY_TOKEN)
        .apply()
      stopBackgroundSyncInternal()
      promise.resolve(true)
    } catch (error: Exception) {
      promise.reject("clear_pairing_failed", error)
    }
  }

  @ReactMethod
  fun showLocalNotification(title: String, body: String, promise: Promise) {
    try {
      ensureChannel()
      postNotification(reactContext, title, body)
      promise.resolve(true)
    } catch (error: Exception) {
      promise.reject("show_notification_failed", error)
    }
  }

  @ReactMethod
  fun startBackgroundSync(promise: Promise) {
    try {
      ensureChannel()
      startBackgroundSyncInternal()
      promise.resolve(true)
    } catch (error: Exception) {
      promise.reject("start_sync_failed", error)
    }
  }

  @ReactMethod
  fun stopBackgroundSync(promise: Promise) {
    try {
      stopBackgroundSyncInternal()
      promise.resolve(true)
    } catch (error: Exception) {
      promise.reject("stop_sync_failed", error)
    }
  }

  private fun preferences(): SharedPreferences {
    return reactContext.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
  }

  private fun ensureChannel() {
    ensureChannel(reactContext)
  }

  private fun startBackgroundSyncInternal() {
    val constraints = Constraints.Builder()
      .setRequiredNetworkType(NetworkType.CONNECTED)
      .build()
    val request = PeriodicWorkRequestBuilder<NotificationPollWorker>(15, TimeUnit.MINUTES)
      .setConstraints(constraints)
      .build()
    WorkManager.getInstance(reactContext).enqueueUniquePeriodicWork(
      WORK_NAME,
      ExistingPeriodicWorkPolicy.UPDATE,
      request
    )
  }

  private fun stopBackgroundSyncInternal() {
    WorkManager.getInstance(reactContext).cancelUniqueWork(WORK_NAME)
  }

  companion object {
    const val PREFS_NAME = "sigorjob_notifications"
    const val KEY_URL = "pairing_url"
    const val KEY_TOKEN = "pairing_token"
    const val CHANNEL_ID = "sigorjob_alerts"
    const val WORK_NAME = "sigorjob_notification_poll"

    fun ensureChannel(context: Context) {
      if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
        val channel = NotificationChannel(
          CHANNEL_ID,
          "Sigorjob Alerts",
          NotificationManager.IMPORTANCE_DEFAULT
        ).apply {
          description = "Notifications from your paired Sigorjob desktop"
        }
        val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        manager.createNotificationChannel(channel)
      }
    }

    fun postNotification(context: Context, title: String, body: String) {
      ensureChannel(context)
      if (Build.VERSION.SDK_INT >= 33) {
        val granted = context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) ==
          android.content.pm.PackageManager.PERMISSION_GRANTED
        if (!granted) return
      }
      val notification = NotificationCompat.Builder(context, CHANNEL_ID)
        .setSmallIcon(R.mipmap.ic_launcher)
        .setContentTitle(title.ifBlank { "Sigorjob" })
        .setContentText(body.ifBlank { "새 알림이 도착했습니다." })
        .setStyle(NotificationCompat.BigTextStyle().bigText(body.ifBlank { "새 알림이 도착했습니다." }))
        .setPriority(NotificationCompat.PRIORITY_DEFAULT)
        .setAutoCancel(true)
        .build()
      NotificationManagerCompat.from(context).notify((System.currentTimeMillis() % Int.MAX_VALUE).toInt(), notification)
    }
  }
}
