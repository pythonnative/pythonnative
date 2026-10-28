package com.pythonnative.runtime.modules

import android.app.Activity
import android.app.Dialog
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.ColorDrawable
import android.text.SpannableStringBuilder
import android.text.Spanned
import android.text.style.BackgroundColorSpan
import android.text.style.ForegroundColorSpan
import android.text.style.StyleSpan
import android.view.Gravity
import android.view.View
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import com.pythonnative.runtime.PNBridge
import org.json.JSONArray
import org.json.JSONObject

/**
 * The development error screen, independent of the view registry, Yoga,
 * and the failed surface.
 *
 * It renders the report `Host.show_error` sends (the shape of
 * `pythonnative.errors.ErrorReport.to_dict` plus `screen`): the error type
 * and message, the phase, the component stack, and the frames. Application
 * frames show their source excerpt, and each run of framework frames
 * collapses into one row that expands. Tapping an application frame's title
 * sends the `open_in_editor` host event; Reload sends `reload`.
 */
internal object ErrorOverlay {
    internal var visible: Dialog? = null
        private set

    private val BACKGROUND = Color.rgb(28, 28, 30)
    private val SECONDARY = Color.rgb(158, 158, 158)
    private val MESSAGE = Color.rgb(255, 166, 178)
    private val LINK = Color.rgb(115, 179, 255)
    private val FAILING_LINE = Color.argb(72, 255, 77, 89)

    fun show(report: JSONObject) {
        dismiss()
        val activity = PNBridge.activity() ?: return
        val screen = report.optLong("screen")
        val text = report.optString("text")
        val density = activity.resources.displayMetrics.density
        fun dp(value: Int) = (value * density).toInt()

        val content = LinearLayout(activity).apply { orientation = LinearLayout.VERTICAL }
        val level = report.optString("level", "error")
        val type = report.optString("type").ifEmpty { report.optString("title", "Python error") }
        content.addView(label(activity, type, 22f, Color.WHITE, bold = true).apply {
            isFocusable = true
            accessibilityHeading(this)
        })
        report.optString("message").takeIf { it.isNotEmpty() }?.let {
            content.addView(label(activity, it, 16f, MESSAGE).apply { setPadding(0, dp(4), 0, 0) })
        }
        report.optString("phase").takeIf { it.isNotEmpty() }?.let {
            val kind = if (level == "warning") "Warning" else "Error"
            content.addView(label(activity, "$kind during $it", 13f, SECONDARY).apply { setPadding(0, dp(4), 0, 0) })
        }

        val components = objects(report.optJSONArray("component_stack"))
        if (components.isNotEmpty()) {
            content.addView(section(activity, "Component stack", dp(16)))
            val lines = components.joinToString("\n") { component ->
                val name = "<${component.optString("name", "?")}>"
                val file = component.optString("file").takeIf { !component.isNull("file") && it.isNotEmpty() }
                val line = component.optInt("line", 0)
                if (file != null && line > 0) "$name ($file:$line)" else name
            }
            content.addView(label(activity, lines, 12f, Color.WHITE, mono = true))
        }

        val frames = objects(report.optJSONArray("frames"))
        if (frames.isNotEmpty()) {
            content.addView(section(activity, "Call stack", dp(16)))
            val run = ArrayList<JSONObject>()
            fun flush() {
                if (run.isNotEmpty()) content.addView(frameworkGroup(activity, run.toList(), dp(6)))
                run.clear()
            }
            for (frame in frames) {
                if (frame.optBoolean("framework")) { run.add(frame); continue }
                flush()
                content.addView(appFrame(activity, screen, frame, dp(6)))
            }
            flush()
        } else if (text.isNotEmpty()) {
            content.addView(section(activity, "Traceback", dp(16)))
            content.addView(label(activity, text, 12f, MESSAGE, mono = true).apply { setTextIsSelectable(true) })
        }

        val dialog = Dialog(activity)
        val panel = LinearLayout(activity).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(16), dp(16), dp(16), dp(8))
            setBackgroundColor(BACKGROUND)
        }
        panel.addView(ScrollView(activity).apply {
            contentDescription = "pn-error-trace"
            addView(content)
        }, LinearLayout.LayoutParams(-1, 0, 1f))
        val actions = LinearLayout(activity).apply { orientation = LinearLayout.HORIZONTAL }
        actions.addView(button(activity, "Dismiss", "pn-error-dismiss") { dismiss() }, LinearLayout.LayoutParams(0, -2, 1f))
        actions.addView(button(activity, "Copy", "pn-error-copy") { view ->
            val clipboard = activity.getSystemService(Context.CLIPBOARD_SERVICE) as? ClipboardManager
            clipboard?.setPrimaryClip(ClipData.newPlainText("Traceback", text))
            (view as Button).text = "Copied"
            view.postDelayed({ view.text = "Copy" }, 1500)
        }, LinearLayout.LayoutParams(0, -2, 1f))
        actions.addView(button(activity, "Reload", "pn-error-reload") {
            PNBridge.callPython("host", screen, "reload", "{}")
        }, LinearLayout.LayoutParams(0, -2, 1f))
        panel.addView(actions, LinearLayout.LayoutParams(-1, -2))
        dialog.setContentView(panel)
        dialog.window?.setBackgroundDrawable(ColorDrawable(BACKGROUND))
        dialog.show()
        dialog.window?.setLayout(-1, -1)
        visible = dialog
    }

    fun dismiss() { visible?.dismiss(); visible = null }

    /** An application frame: its tappable title and its source excerpt. */
    private fun appFrame(activity: Activity, screen: Long, frame: JSONObject, gap: Int): View {
        val file = frame.optString("file")
        val line = frame.optInt("line")
        val column = LinearLayout(activity).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(0, gap, 0, gap)
        }
        column.addView(label(activity, frame.optString("title", "$file:$line"), 13f, LINK, mono = true, bold = true).apply {
            isClickable = true
            isFocusable = true
            contentDescription = "Open ${frame.optString("title")} in your editor"
            setOnClickListener {
                PNBridge.callPython("host", screen, "open_in_editor", JSONObject().put("file", file).put("line", line).toString())
            }
        })
        frame.optString("excerpt").takeIf { it.isNotEmpty() }?.let { source ->
            column.addView(label(activity, "", 12f, SECONDARY, mono = true).apply { setText(excerpt(source), TextView.BufferType.SPANNABLE) })
        }
        return column
    }

    /** One row for a run of framework frames that expands to their titles. */
    private fun frameworkGroup(activity: Activity, frames: List<JSONObject>, gap: Int): View {
        val column = LinearLayout(activity).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(0, gap, 0, gap)
        }
        val detail = label(activity, frames.joinToString("\n") { it.optString("title") }, 11f, SECONDARY, mono = true).apply {
            visibility = View.GONE
        }
        val count = frames.size
        column.addView(label(activity, "$count framework frame${if (count == 1) "" else "s"}", 13f, SECONDARY).apply {
            tag = "pn-error-framework-frames"
            isClickable = true
            isFocusable = true
            setOnClickListener { detail.visibility = if (detail.visibility == View.GONE) View.VISIBLE else View.GONE }
        })
        column.addView(detail)
        return column
    }

    /** The excerpt with its failing line (the one starting with `>`) highlighted. */
    internal fun excerpt(excerpt: String): CharSequence {
        val builder = SpannableStringBuilder()
        val lines = excerpt.split("\n")
        for ((index, line) in lines.withIndex()) {
            val start = builder.length
            builder.append(line)
            if (line.startsWith(">")) {
                val end = builder.length
                builder.setSpan(BackgroundColorSpan(FAILING_LINE), start, end, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
                builder.setSpan(ForegroundColorSpan(Color.WHITE), start, end, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
                builder.setSpan(StyleSpan(Typeface.BOLD), start, end, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
            }
            if (index < lines.size - 1) builder.append("\n")
        }
        return builder
    }

    private fun objects(array: JSONArray?): List<JSONObject> =
        if (array == null) emptyList() else (0 until array.length()).mapNotNull { array.optJSONObject(it) }

    private fun label(activity: Activity, text: String, size: Float, color: Int, mono: Boolean = false, bold: Boolean = false) =
        TextView(activity).apply {
            this.text = text
            textSize = size
            setTextColor(color)
            typeface = Typeface.create(if (mono) Typeface.MONOSPACE else Typeface.DEFAULT, if (bold) Typeface.BOLD else Typeface.NORMAL)
        }

    private fun section(activity: Activity, title: String, top: Int) =
        label(activity, title.uppercase(), 12f, SECONDARY, bold = true).apply {
            setPadding(0, top, 0, top / 4)
            accessibilityHeading(this)
        }

    private fun button(activity: Activity, title: String, description: String, action: (View) -> Unit) =
        Button(activity).apply {
            text = title
            contentDescription = description
            gravity = Gravity.CENTER
            setOnClickListener(action)
        }

    private fun accessibilityHeading(view: View) {
        if (android.os.Build.VERSION.SDK_INT >= 28) view.isAccessibilityHeading = true
    }
}
