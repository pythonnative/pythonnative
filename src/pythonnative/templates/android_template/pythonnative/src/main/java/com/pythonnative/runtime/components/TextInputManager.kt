package com.pythonnative.runtime.components

import android.content.Context
import android.os.Build
import android.text.Editable
import android.text.InputFilter
import android.text.InputType
import android.text.TextWatcher
import android.view.MotionEvent
import android.view.View
import android.view.inputmethod.EditorInfo
import android.view.inputmethod.InputMethodManager
import android.widget.EditText
import com.pythonnative.runtime.bridge.JsonUtil
import com.pythonnative.runtime.bridge.PNLog
import com.pythonnative.runtime.bridge.num
import com.pythonnative.runtime.bridge.str
import com.pythonnative.runtime.bridge.value
import com.pythonnative.runtime.views.PNEditText
import org.json.JSONObject
import kotlin.math.max
import kotlin.math.min

/**
 * `TextInput` element: an `EditText` reporting `on_change`, `on_submit`,
 * `on_focus`, `on_blur`, and `on_selection_change`, with keyboard type,
 * secure entry, return key, autofill, and clear-button props.
 */
class TextInputManager : ComponentManager() {
    override fun createView(context: Context, tag: Long, props: JSONObject): View {
        val et = PNEditText(context)
        // Default to single-line so Enter triggers the IME action instead of a newline.
        if (!JsonUtil.truthy(props.value("multiline"))) et.setSingleLine(true)
        bindListeners(et)
        return et
    }

    private fun bindListeners(et: PNEditText) {
        et.addTextChangedListener(object : TextWatcher {
            override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) {}
            override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) {}
            override fun afterTextChanged(s: Editable?) {
                if (stateOf(et)["suppress"] == true) return
                fire(et, "on_change", s?.toString() ?: "")
            }
        })
        et.setOnFocusChangeListener { v, hasFocus -> fire(v, if (hasFocus) "on_focus" else "on_blur") }
        et.onSelectionChangedListener = { start, end ->
            if (hasEvent(et, "on_selection_change")) {
                fire(et, "on_selection_change", mapOf("start" to start, "end" to end))
            }
        }
        installEditorAction(et)
    }

    override fun applyProps(view: View, props: JSONObject, initial: Boolean) {
        val et = view as EditText
        val state = stateOf(et)
        val merged = propsOf(et)
        if (props.has("value")) {
            val incoming = props.str("value") ?: ""
            if (et.text.toString() != incoming) {
                val selStart = et.selectionStart
                val selEnd = et.selectionEnd
                state["suppress"] = true
                try {
                    et.setText(incoming)
                    val maxPos = incoming.length
                    val start = max(0, min(selStart, maxPos))
                    val end = max(0, min(selEnd, maxPos))
                    if (start == end) et.setSelection(start) else et.setSelection(start, end)
                } catch (e: Exception) {
                    PNLog.swallowed("TextInputManager.value", e)
                } finally {
                    state["suppress"] = false
                }
            }
        }
        if (props.has("placeholder")) et.hint = props.str("placeholder") ?: ""
        PNColor.parse(props.value("placeholder_color"))?.let { et.setHintTextColor(it) }
        props.num("font_size")?.let { et.textSize = it.toFloat() }
        PNColor.parse(props.value("color"))?.let { et.setTextColor(it) }
        if (listOf("font_family", "font_weight", "italic", "bold").any { props.has(it) }) {
            TextStyle.applyTypeface(et, merged)
        }
        if (listOf("multiline", "secure", "secure_text_entry", "keyboard_type", "auto_capitalize", "auto_correct").any { props.has(it) }) {
            applyInputType(et, merged)
        }
        if (props.has("max_length")) {
            val limit = props.num("max_length")
            et.filters = if (limit != null) arrayOf<InputFilter>(InputFilter.LengthFilter(limit.toInt())) else arrayOf()
        }
        if (JsonUtil.truthy(props.value("auto_focus"))) et.requestFocus()
        if (props.has("editable")) {
            // Only present when False (read-only); removal restores editing.
            val editable = props.value("editable") != false
            et.isFocusable = editable
            et.isFocusableInTouchMode = editable
            et.isCursorVisible = editable
            et.isLongClickable = editable
        }
        PNColor.parse(props.value("selection_color"))?.let { et.highlightColor = it }
        props.str("text_content_type")?.let { applyAutofill(et, it) }
        if (props.has("clear_button")) applyClearButton(et, JsonUtil.truthy(props.value("clear_button")))
        props.str("return_key_type")?.let { et.imeOptions = imeAction(it) }
        if (props.has("text_align")) {
            et.gravity = when (props.str("text_align")) {
                "center" -> android.view.Gravity.CENTER_HORIZONTAL or (et.gravity and android.view.Gravity.VERTICAL_GRAVITY_MASK)
                "right", "end" -> android.view.Gravity.END or (et.gravity and android.view.Gravity.VERTICAL_GRAVITY_MASK)
                else -> android.view.Gravity.START or (et.gravity and android.view.Gravity.VERTICAL_GRAVITY_MASK)
            }
        }
        ViewStyler.apply(et, props)
    }

    private fun applyInputType(et: EditText, merged: JSONObject) {
        var base = InputType.TYPE_CLASS_TEXT
        val secure = JsonUtil.truthy(merged.value("secure")) || JsonUtil.truthy(merged.value("secure_text_entry"))
        if (secure) {
            base = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD
        } else {
            when (merged.str("keyboard_type")) {
                "email_address", "email" -> base = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_EMAIL_ADDRESS
                "number_pad", "numeric" -> base = InputType.TYPE_CLASS_NUMBER
                "decimal_pad", "decimal" -> base = InputType.TYPE_CLASS_NUMBER or InputType.TYPE_NUMBER_FLAG_DECIMAL
                "phone_pad", "phone" -> base = InputType.TYPE_CLASS_PHONE
                "url" -> base = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_URI
            }
            when (merged.str("auto_capitalize")) {
                "sentences" -> base = base or InputType.TYPE_TEXT_FLAG_CAP_SENTENCES
                "words" -> base = base or InputType.TYPE_TEXT_FLAG_CAP_WORDS
                "characters" -> base = base or InputType.TYPE_TEXT_FLAG_CAP_CHARACTERS
            }
            if (merged.value("auto_correct") == false) base = base or InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS
        }
        if (JsonUtil.truthy(merged.value("multiline"))) {
            base = base or InputType.TYPE_TEXT_FLAG_MULTI_LINE
            et.setSingleLine(false)
        } else {
            et.setSingleLine(true)
        }
        et.inputType = base
    }

    private fun imeAction(type: String): Int = when (type) {
        "default" -> EditorInfo.IME_ACTION_UNSPECIFIED
        "go" -> EditorInfo.IME_ACTION_GO
        "next" -> EditorInfo.IME_ACTION_NEXT
        "search" -> EditorInfo.IME_ACTION_SEARCH
        "send" -> EditorInfo.IME_ACTION_SEND
        "previous" -> EditorInfo.IME_ACTION_PREVIOUS
        else -> EditorInfo.IME_ACTION_DONE // done, google, join, route, yahoo
    }

    /**
     * Single-line inputs always dismiss the keyboard on the action key and
     * fire `on_submit` first. Multi-line inputs only consume the action
     * when an `on_submit` handler exists; otherwise Enter inserts a newline.
     */
    private fun installEditorAction(et: EditText) {
        et.setOnEditorActionListener { v, _, _ ->
            val multiline = JsonUtil.truthy(propsOf(v).value("multiline"))
            val hasSubmit = hasEvent(v, "on_submit")
            if (multiline && !hasSubmit) return@setOnEditorActionListener false
            if (hasSubmit) fire(v, "on_submit", v.text.toString())
            if (!multiline && propsOf(v).value("blur_on_submit") != false) blur(v)
            true
        }
    }

    private fun applyAutofill(et: EditText, contentType: String) {
        if (Build.VERSION.SDK_INT < 26) return
        val hint = when (contentType) {
            "username" -> View.AUTOFILL_HINT_USERNAME
            "password" -> View.AUTOFILL_HINT_PASSWORD
            "new_password" -> "newPassword"
            "email", "email_address" -> View.AUTOFILL_HINT_EMAIL_ADDRESS
            "name" -> View.AUTOFILL_HINT_NAME
            "given_name" -> "personGivenName"
            "family_name" -> "personFamilyName"
            "telephone", "phone", "phone_number" -> View.AUTOFILL_HINT_PHONE
            "postal_code" -> View.AUTOFILL_HINT_POSTAL_CODE
            "street_address" -> View.AUTOFILL_HINT_POSTAL_ADDRESS
            "credit_card_number" -> View.AUTOFILL_HINT_CREDIT_CARD_NUMBER
            "one_time_code" -> "smsOTPCode"
            else -> null
        } ?: return
        et.setAutofillHints(hint)
    }

    private fun applyClearButton(et: EditText, enabled: Boolean) {
        val state = stateOf(et)
        if (!enabled) {
            et.setCompoundDrawablesWithIntrinsicBounds(0, 0, 0, 0)
            return
        }
        et.setCompoundDrawablesWithIntrinsicBounds(0, 0, android.R.drawable.ic_menu_close_clear_cancel, 0)
        if (state["clear_bound"] == true) return
        state["clear_bound"] = true
        et.setOnTouchListener { v, event ->
            if (event.action == MotionEvent.ACTION_UP) {
                val right = (v as EditText).compoundDrawables.getOrNull(2)
                if (right != null) {
                    val threshold = v.width - v.paddingRight - right.bounds.width()
                    if (event.x >= threshold) {
                        v.setText("")
                        v.performClick()
                        return@setOnTouchListener true
                    }
                }
            }
            false
        }
    }

    override fun command(view: View, name: String, args: JSONObject): Any? {
        val et = view as? EditText ?: return null
        when (name) {
            "focus" -> {
                et.requestFocus()
                imm(et)?.showSoftInput(et, InputMethodManager.SHOW_IMPLICIT)
            }
            "blur" -> blur(et)
            "clear" -> et.setText("")
            "select_all" -> et.selectAll()
            "set_selection" -> {
                val start = JsonUtil.toInt(args.opt("start"))
                val end = JsonUtil.toInt(args.opt("end"), start)
                val len = et.text.length
                et.setSelection(start.coerceIn(0, len), end.coerceIn(0, len))
            }
            "is_focused" -> return et.isFocused
            "get_value" -> return et.text.toString()
        }
        return null
    }

    private fun blur(view: View) {
        view.clearFocus()
        imm(view)?.hideSoftInputFromWindow(view.windowToken, 0)
    }

    private fun imm(view: View): InputMethodManager? =
        view.context.getSystemService(Context.INPUT_METHOD_SERVICE) as? InputMethodManager
}
