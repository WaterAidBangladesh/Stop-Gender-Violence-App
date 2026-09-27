package com.wateraidbd.shomotashurokkha

import android.view.WindowManager
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

/**
 * Adds one capability Flutter cannot reach on its own: FLAG_SECURE.
 *
 * The phone in a survivor's hand is often not private. With FLAG_SECURE set, the
 * window is excluded from screenshots, screen recording, and — the one that
 * matters most here — the thumbnail Android shows in the recent-apps switcher.
 * Without it, someone who picks up the phone and taps the app switcher sees the
 * Bharosha conversation rendered as a preview.
 *
 * It is toggled per screen rather than set for the whole app, because it also
 * blocks screenshots the user may legitimately want elsewhere (a helpline number
 * to share with a friend). The chat screen turns it on when it opens and off when
 * it closes.
 */
class MainActivity : FlutterActivity() {
    private val channelName = "com.wateraidbd.shomotashurokkha/secure_window"

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)

        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, channelName)
            .setMethodCallHandler { call, result ->
                when (call.method) {
                    "enable" -> {
                        // runOnUiThread: window flags must be set on the UI
                        // thread, and a MethodChannel handler is not guaranteed
                        // to be there.
                        runOnUiThread {
                            window.addFlags(WindowManager.LayoutParams.FLAG_SECURE)
                        }
                        result.success(true)
                    }
                    "disable" -> {
                        runOnUiThread {
                            window.clearFlags(WindowManager.LayoutParams.FLAG_SECURE)
                        }
                        result.success(true)
                    }
                    else -> result.notImplemented()
                }
            }
    }
}
