package com.pythonnative.runtime.modules

import android.app.Dialog
import android.graphics.Color
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import com.pythonnative.runtime.PNBridge

/** Independent of the view registry, Yoga, and the failed surface. */
internal object ErrorOverlay {
    private var visible: Dialog? = null
    fun show(screen: Long, title: String, trace: String) {
        dismiss()
        val activity = PNBridge.activity() ?: return
        val dialog = Dialog(activity)
        val panel = LinearLayout(activity).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(24, 24, 24, 24)
            setBackgroundColor(Color.rgb(28, 28, 30))
        }
        panel.addView(TextView(activity).apply { text = title; textSize = 18f; setTextColor(Color.WHITE) })
        val detail = TextView(activity).apply {
            text = trace; textSize = 13f; setTextColor(Color.rgb(255, 166, 178)); setTextIsSelectable(true)
            contentDescription = "pn-error-trace"
        }
        panel.addView(ScrollView(activity).apply { addView(detail) }, LinearLayout.LayoutParams(-1, 0, 1f))
        panel.addView(Button(activity).apply {
            text = "Reload"; contentDescription = "pn-error-reload"
            setOnClickListener { PNBridge.callPython("host", screen, "reload", "{}") }
        })
        panel.addView(Button(activity).apply {
            text = "Dismiss"; contentDescription = "pn-error-dismiss"
            setOnClickListener { dismiss() }
        })
        dialog.setContentView(panel); dialog.show()
        dialog.window?.setLayout(-1, -1)
        visible = dialog
    }
    fun dismiss() { visible?.dismiss(); visible = null }
}
