package com.sigorjob.mobile

import android.content.Intent
import com.facebook.react.bridge.Promise
import com.facebook.react.bridge.ReactApplicationContext
import com.facebook.react.bridge.ReactContext
import com.facebook.react.bridge.ReactContextBaseJavaModule
import com.facebook.react.bridge.ReactMethod
import com.facebook.react.modules.core.DeviceEventManagerModule

class ShareIntentModule(private val reactContext: ReactApplicationContext) :
  ReactContextBaseJavaModule(reactContext) {

  override fun getName(): String = "ShareIntentBridge"

  @ReactMethod
  fun getPendingSharedText(promise: Promise) {
    promise.resolve(consumePendingSharedText())
  }

  @ReactMethod
  fun addListener(eventName: String) {
    // Required for NativeEventEmitter on Android.
  }

  @ReactMethod
  fun removeListeners(count: Int) {
    // Required for NativeEventEmitter on Android.
  }

  companion object {
    private const val EVENT_NAME = "shareTextReceived"
    private var pendingSharedText: String? = null

    fun handleIntent(intent: Intent?, reactContext: ReactContext?) {
      val sharedText = extractSharedText(intent) ?: return
      pendingSharedText = sharedText
      emitSharedText(reactContext, sharedText)
    }

    private fun extractSharedText(intent: Intent?): String? {
      if (intent?.action != Intent.ACTION_SEND) return null
      val directText = intent.getStringExtra(Intent.EXTRA_TEXT)?.trim()
      if (!directText.isNullOrBlank()) {
        return directText
      }
      val subject = intent.getStringExtra(Intent.EXTRA_SUBJECT)?.trim()
      return subject?.takeIf { it.isNotBlank() }
    }

    private fun emitSharedText(reactContext: ReactContext?, text: String) {
      reactContext
        ?.getJSModule(DeviceEventManagerModule.RCTDeviceEventEmitter::class.java)
        ?.emit(EVENT_NAME, text)
    }

    private fun consumePendingSharedText(): String? {
      val value = pendingSharedText
      pendingSharedText = null
      return value
    }
  }
}
