package com.pythonnative.runtime.components

import android.app.DatePickerDialog
import android.app.TimePickerDialog
import android.content.Context
import android.view.View
import android.widget.Button
import com.pythonnative.runtime.bridge.PNLog
import com.pythonnative.runtime.bridge.str
import com.pythonnative.runtime.bridge.value
import org.json.JSONObject
import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Locale

/**
 * `DatePicker` element: a trigger `Button` opening the native
 * `DatePickerDialog` (`mode` `"date"`), `TimePickerDialog` (`"time"`),
 * or a chained date-then-time flow (`"datetime"`). Values are ISO
 * strings; the confirmed value is reported through `on_change`.
 */
class DatePickerManager : ComponentManager() {
    override fun createView(context: Context, tag: Long, props: JSONObject): View {
        val btn = Button(context)
        btn.isAllCaps = false
        btn.setOnClickListener { v ->
            if (propsOf(v).value("enabled") == false) return@setOnClickListener
            openDialog(v as Button)
        }
        return btn
    }

    override fun applyProps(view: View, props: JSONObject, initial: Boolean) {
        val btn = view as Button
        if (props.has("enabled")) btn.isEnabled = props.value("enabled") != false
        if (props.has("value") || props.has("mode") || initial) refreshLabel(btn)
        ViewStyler.applyAccessibility(btn, props)
    }

    private fun mode(btn: Button): String = propsOf(btn).str("mode") ?: "date"

    private fun refreshLabel(btn: Button) {
        val value = propsOf(btn).str("value")
        btn.text = if (!value.isNullOrEmpty()) value else PLACEHOLDERS[mode(btn)] ?: "Select"
    }

    private fun openDialog(btn: Button) {
        val mode = mode(btn)
        val cal = parse(propsOf(btn).str("value"), mode)
        when (mode) {
            "time" -> openTime(btn, cal)
            "datetime" -> openDate(btn, cal, thenTime = true)
            else -> openDate(btn, cal, thenTime = false)
        }
    }

    private fun openDate(btn: Button, cal: Calendar, thenTime: Boolean) {
        val dialog = DatePickerDialog(
            btn.context,
            { _, year, month, day ->
                cal.set(Calendar.YEAR, year)
                cal.set(Calendar.MONTH, month)
                cal.set(Calendar.DAY_OF_MONTH, day)
                if (thenTime) openTime(btn, cal) else commit(btn, cal)
            },
            cal.get(Calendar.YEAR),
            cal.get(Calendar.MONTH),
            cal.get(Calendar.DAY_OF_MONTH),
        )
        try {
            val merged = propsOf(btn)
            merged.str("minimum")?.takeIf { it.isNotEmpty() }?.let { dialog.datePicker.minDate = parse(it, mode(btn)).timeInMillis }
            merged.str("maximum")?.takeIf { it.isNotEmpty() }?.let { dialog.datePicker.maxDate = parse(it, mode(btn)).timeInMillis }
        } catch (e: Exception) {
            PNLog.swallowed("DatePickerManager.minMax", e)
        }
        dialog.show()
    }

    private fun openTime(btn: Button, cal: Calendar) {
        TimePickerDialog(
            btn.context,
            { _, hour, minute ->
                cal.set(Calendar.HOUR_OF_DAY, hour)
                cal.set(Calendar.MINUTE, minute)
                commit(btn, cal)
            },
            cal.get(Calendar.HOUR_OF_DAY),
            cal.get(Calendar.MINUTE),
            true,
        ).show()
    }

    private fun format(mode: String): SimpleDateFormat = SimpleDateFormat(PATTERNS[mode] ?: PATTERNS["date"]!!, Locale.US)

    private fun parse(value: String?, mode: String): Calendar {
        val cal = Calendar.getInstance()
        if (!value.isNullOrEmpty()) {
            try {
                format(mode).parse(value)?.let { cal.time = it }
            } catch (e: Exception) {
                PNLog.swallowed("DatePickerManager.parse", e)
            }
        }
        return cal
    }

    private fun commit(btn: Button, cal: Calendar) {
        val iso = try {
            format(mode(btn)).format(cal.time)
        } catch (e: Exception) {
            return
        }
        propsOf(btn).put("value", iso)
        btn.text = iso
        fire(btn, "on_change", iso)
    }

    private companion object {
        val PATTERNS = mapOf("date" to "yyyy-MM-dd", "time" to "HH:mm", "datetime" to "yyyy-MM-dd'T'HH:mm")
        val PLACEHOLDERS = mapOf("date" to "Select date", "time" to "Select time", "datetime" to "Select date & time")
    }
}
