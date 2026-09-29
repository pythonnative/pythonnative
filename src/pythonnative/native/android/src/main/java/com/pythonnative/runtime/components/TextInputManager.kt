package com.pythonnative.runtime.components

import com.pythonnative.runtime.PNBridge

import com.pythonnative.generated.*

import android.content.Context
import android.os.Build
import android.text.Editable
import android.text.InputFilter
import android.text.InputType
import android.text.TextWatcher
import android.view.KeyEvent
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
 * `on_focus`, `on_blur`, `on_selection_change` (`{start, end}`),
 * `on_key_press` (`{key}`: the typed character, `"Backspace"`, or
 * `"Enter"`, derived from text-watcher diffs plus hardware key events),
 * and `on_content_size_change` (`{width, height}` in dp, multiline),
 * with keyboard type, secure entry, return key, autofill, and
 * clear-button props.
 *
 * `selection` is controlled: a new `{start, end}` is applied when it
 * differs from the current selection and never fights the user's own
 * cursor moves. `select_text_on_focus` selects all on focus.
 * `blur_on_submit` defaults to `true` for single-line inputs and `false`
 * for multiline. `keyboard_appearance` is accepted and ignored: Android
 * IMEs pick their own theme. `keyboard_type` extras: `ascii` is a plain
 * text keyboard (Android has no ASCII-only hint), `numbers_and_punctuation`
 * a signed decimal number pad, `web_search` a web-edit keyboard with a
 * search action, `visible_password` a password field without masking.
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
        et.onCompositionEnded = {
            val pending = stateOf(et).remove("pending_value") as? JSONObject
            if (pending != null) applyProps(et, pending, false)
        }
        et.addTextChangedListener(object : TextWatcher {
            override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) {}
            override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) {
                if (stateOf(et)["suppress"] == true || !hasEvent(et, "on_key_press")) return
                keyFor(s, start, before, count)?.let { PNComponentEvents.TextInput.on_key_press(et, PNKeyPressEvent(it)) }
            }
            override fun afterTextChanged(s: Editable?) {
                if (stateOf(et)["suppress"] == true) return
                fire(et, "on_change", s?.toString() ?: "")
                PNBridge.registry.tagOf(et)?.let { com.pythonnative.runtime.layout.NativeLayout.invalidate(it) }
                reportContentSize(et)
            }
        })
        et.setOnKeyListener { v, keyCode, event ->
            // Soft keyboards mostly edit through the InputConnection (caught by
            // the text watcher); hardware keys and a backspace on empty text
            // arrive here. Only the empty-text backspace is reported to avoid
            // doubling up with the watcher.
            if (event.action == KeyEvent.ACTION_DOWN && keyCode == KeyEvent.KEYCODE_DEL && (v as EditText).text.isEmpty() && hasEvent(v, "on_key_press")) {
                PNComponentEvents.TextInput.on_key_press(v, PNKeyPressEvent("Backspace"))
            }
            false
        }
        et.setOnFocusChangeListener { v, hasFocus ->
            fire(v, if (hasFocus) "on_focus" else "on_blur")
            if (hasFocus && TextInputProps(propsOf(v)).select_text_on_focus == true) (v as EditText).post { v.selectAll() }
        }
        et.onSelectionChangedListener = { start, end ->
            if (hasEvent(et, "on_selection_change")) {
                PNComponentEvents.TextInput.on_selection_change(et, PNSelectionEvent(start.toLong(), end.toLong()))
            }
        }
        et.addOnLayoutChangeListener { v, _, _, _, _, _, _, _, _ -> reportContentSize(v as EditText) }
        installEditorAction(et)
    }

    /** Fire `on_content_size_change` when the multiline content size changed. */
    private fun reportContentSize(et: EditText) {
        if (!hasEvent(et, "on_content_size_change")) return
        val layout = et.layout ?: return
        val width = dp(et.width)
        val height = dp(layout.height + et.compoundPaddingTop + et.compoundPaddingBottom)
        val state = stateOf(et)
        val last = state["content_size"] as? Pair<*, *>
        if (last != null && last.first == width && last.second == height) return
        state["content_size"] = width to height
        PNComponentEvents.TextInput.on_content_size_change(et, PNContentSizeEvent(width, height))
    }

    override fun applyProps(view: View, props: JSONObject, initial: Boolean) {
        val typed = TextInputProps(props, validated = true)

        val et = view as EditText
        val state = stateOf(et)
        val merged = propsOf(et)
        if (typed.has_value) {
            val incoming = typed.value ?: ""
            val acknowledged = props.optLong("_pn_edit_revision", 0)
            val edited = (state["edit_revision"] as? Number)?.toLong() ?: 0L
            if (acknowledged >= edited && android.view.inputmethod.BaseInputConnection.getComposingSpanStart(et.text) >= 0) {
                state["pending_value"] = JSONObject().put("value", incoming).put("_pn_edit_revision", acknowledged)
            }
            if (et.text.toString() != incoming && acknowledged >= edited && android.view.inputmethod.BaseInputConnection.getComposingSpanStart(et.text) < 0) {
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
        if (typed.has_selection) applySelection(et, typed.selection)
        if (typed.has_placeholder) et.hint = typed.placeholder ?: ""
        PNColor.parse(props.value("placeholder_color"))?.let { et.setHintTextColor(it) }
        typed.font_size?.let { et.textSize = it.toFloat() }
        PNColor.parse(props.value("color"))?.let { et.setTextColor(it) }
        if (listOf("font_family", "font_weight", "italic", "bold").any { props.has(it) }) {
            TextStyle.applyTypeface(et, merged)
        }
        if (listOf("multiline", "secure", "secure_text_entry", "keyboard_type", "auto_capitalize", "auto_correct").any { props.has(it) }) {
            applyInputType(et, merged)
        }
        if (typed.has_max_length) {
            val limit = props.num("max_length")
            et.filters = if (limit != null) arrayOf<InputFilter>(InputFilter.LengthFilter(limit.toInt())) else arrayOf()
        }
        if ((typed.auto_focus ?: false)) et.requestFocus()
        if (typed.has_editable) {
            // Only present when False (read-only); removal restores editing.
            val editable = props.value("editable") != false
            et.isFocusable = editable
            et.isFocusableInTouchMode = editable
            et.isCursorVisible = editable
            et.isLongClickable = editable
        }
        PNColor.parse(props.value("selection_color"))?.let { et.highlightColor = it }
        typed.text_content_type?.let { applyAutofill(et, it) }
        if (typed.has_clear_button) applyClearButton(et, (typed.clear_button ?: false))
        if (typed.has_return_key_type || typed.has_keyboard_type) {
            val mergedTyped = TextInputProps(merged, validated = true)
            val action = mergedTyped.return_key_type?.rawValue?.let { imeAction(it) }
                ?: if (mergedTyped.keyboard_type?.rawValue == "web_search") EditorInfo.IME_ACTION_SEARCH else null
            if (action != null) et.imeOptions = action
        }
        // keyboard_appearance: no Android equivalent (the IME themes itself).
        if (typed.has_text_align) {
            et.gravity = when (typed.text_align?.rawValue) {
                "center" -> android.view.Gravity.CENTER_HORIZONTAL or (et.gravity and android.view.Gravity.VERTICAL_GRAVITY_MASK)
                "right", "end" -> android.view.Gravity.END or (et.gravity and android.view.Gravity.VERTICAL_GRAVITY_MASK)
                else -> android.view.Gravity.START or (et.gravity and android.view.Gravity.VERTICAL_GRAVITY_MASK)
            }
        }
        ViewStyler.apply(et, props)
    }

    /** Apply a controlled `selection` when it differs from the current one. */
    private fun applySelection(et: EditText, selection: PNSelection?) {
        if (selection == null) return
        val length = et.text?.length ?: 0
        val start = selection.start.toInt().coerceIn(0, length)
        val end = selection.end.toInt().coerceIn(0, length)
        if (et.selectionStart == start && et.selectionEnd == end) return
        try {
            et.setSelection(start, end)
        } catch (e: Exception) {
            PNLog.swallowed("TextInputManager.selection", e)
        }
    }

    private fun applyInputType(et: EditText, merged: JSONObject) {
        var base = InputType.TYPE_CLASS_TEXT
        val secure = JsonUtil.truthy(merged.value("secure")) || JsonUtil.truthy(merged.value("secure_text_entry"))
        if (secure) {
            base = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD
        } else {
            base = inputTypeFor(merged.str("keyboard_type"))
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

    /**
     * `InputType` class and variation for a `keyboard_type`. `ascii` has
     * no Android hint and yields a plain text keyboard; `web_search` also
     * gets `IME_ACTION_SEARCH` unless `return_key_type` says otherwise.
     */
    fun inputTypeFor(keyboardType: String?): Int = when (keyboardType) {
        "email_address", "email" -> InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_EMAIL_ADDRESS
        "number_pad", "numeric" -> InputType.TYPE_CLASS_NUMBER
        "decimal_pad", "decimal" -> InputType.TYPE_CLASS_NUMBER or InputType.TYPE_NUMBER_FLAG_DECIMAL
        "numbers_and_punctuation" -> InputType.TYPE_CLASS_NUMBER or InputType.TYPE_NUMBER_FLAG_SIGNED or InputType.TYPE_NUMBER_FLAG_DECIMAL
        "phone_pad", "phone" -> InputType.TYPE_CLASS_PHONE
        "url" -> InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_URI
        "web_search" -> InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_WEB_EDIT_TEXT
        "visible_password" -> InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_VISIBLE_PASSWORD
        else -> InputType.TYPE_CLASS_TEXT // default, ascii
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
     * The action key fires `on_key_press("Enter")` and `on_submit`, then
     * blurs when `blur_on_submit` (default: single-line only) is set.
     * Multi-line inputs only consume the action when `on_submit` or
     * `blur_on_submit` asks for it; otherwise Enter inserts a newline.
     */
    private fun installEditorAction(et: EditText) {
        et.setOnEditorActionListener { v, _, _ ->
            val typed = TextInputProps(propsOf(v))
            val multiline = typed.multiline == true
            val hasSubmit = hasEvent(v, "on_submit")
            val blurOnSubmit = typed.blur_on_submit ?: !multiline
            if (multiline && !hasSubmit && !blurOnSubmit) return@setOnEditorActionListener false
            if (hasEvent(v, "on_key_press")) PNComponentEvents.TextInput.on_key_press(v, PNKeyPressEvent("Enter"))
            if (hasSubmit) fire(v, "on_submit", v.text.toString())
            if (blurOnSubmit) blur(v)
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

    companion object {
        /**
         * The `on_key_press` key for one text-watcher change: the inserted
         * character (or `"Enter"` for a newline), `"Backspace"` for a
         * single-character deletion, `null` for replacements, pastes, and
         * IME compositions longer than one character.
         */
        fun keyFor(text: CharSequence?, start: Int, before: Int, count: Int): String? {
            if (before == 0 && count == 1 && text != null && start < text.length) {
                val ch = text[start]
                return if (ch == '\n') "Enter" else ch.toString()
            }
            if (before == 1 && count == 0) return "Backspace"
            return null
        }
    }
}
