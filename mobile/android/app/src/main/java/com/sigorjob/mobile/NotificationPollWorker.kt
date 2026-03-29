package com.sigorjob.mobile

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedReader
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL

class NotificationPollWorker(appContext: Context, params: WorkerParameters) :
  CoroutineWorker(appContext, params) {

  override suspend fun doWork(): Result {
    val prefs = applicationContext.getSharedPreferences(NotificationBridgeModule.PREFS_NAME, Context.MODE_PRIVATE)
    val baseUrl = prefs.getString(NotificationBridgeModule.KEY_URL, null)?.trim().orEmpty()
    val token = prefs.getString(NotificationBridgeModule.KEY_TOKEN, null)?.trim().orEmpty()
    if (baseUrl.isBlank() || token.isBlank()) {
      return Result.success()
    }

    return try {
      val notifications = fetchNotifications(baseUrl, token)
      if (notifications.isEmpty()) {
        Result.success()
      } else {
        notifications.forEach { item ->
          NotificationBridgeModule.postNotification(
            applicationContext,
            item.optString("title", "Sigorjob"),
            item.optString("body", "새 알림이 도착했습니다.")
          )
        }
        acknowledgeNotifications(baseUrl, token, notifications)
        Result.success()
      }
    } catch (_: Exception) {
      Result.retry()
    }
  }

  private fun fetchNotifications(baseUrl: String, token: String): List<JSONObject> {
    val connection = URL("${baseUrl.trimEnd('/')}/mobile/notifications?limit=10").openConnection() as HttpURLConnection
    connection.requestMethod = "GET"
    connection.setRequestProperty("Authorization", "Bearer $token")
    connection.connectTimeout = 10000
    connection.readTimeout = 10000

    val response = connection.inputStream.bufferedReader().use(BufferedReader::readText)
    val json = JSONObject(response)
    val array = json.optJSONArray("notifications") ?: JSONArray()
    return buildList {
      for (index in 0 until array.length()) {
        add(array.getJSONObject(index))
      }
    }
  }

  private fun acknowledgeNotifications(baseUrl: String, token: String, notifications: List<JSONObject>) {
    val ids = JSONArray()
    notifications.forEach { item ->
      item.optString("id")?.takeIf { it.isNotBlank() }?.let(ids::put)
    }
    if (ids.length() == 0) return

    val connection = URL("${baseUrl.trimEnd('/')}/mobile/notifications/ack").openConnection() as HttpURLConnection
    connection.requestMethod = "POST"
    connection.doOutput = true
    connection.setRequestProperty("Authorization", "Bearer $token")
    connection.setRequestProperty("Content-Type", "application/json")
    connection.connectTimeout = 10000
    connection.readTimeout = 10000
    OutputStreamWriter(connection.outputStream).use { writer ->
      val payload = JSONObject().put("ids", ids)
      writer.write(payload.toString())
    }
    connection.inputStream.close()
  }
}
