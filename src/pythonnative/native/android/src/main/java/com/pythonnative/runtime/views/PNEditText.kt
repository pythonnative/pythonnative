package com.pythonnative.runtime.views

import android.content.Context
import androidx.appcompat.widget.AppCompatEditText

/**
 * `EditText` that reports selection changes, which the platform only
 * exposes through a protected override.
 */
class PNEditText(context: Context) : AppCompatEditText(context) {
    /** Called with `(start, end)` whenever the selection or cursor moves. */
    var onSelectionChangedListener: ((Int, Int) -> Unit)? = null

    var onCompositionEnded: (() -> Unit)? = null
    override fun onCreateInputConnection(info: android.view.inputmethod.EditorInfo): android.view.inputmethod.InputConnection? {
        val connection = super.onCreateInputConnection(info) ?: return null
        return object : android.view.inputmethod.InputConnectionWrapper(connection, false) {
            override fun finishComposingText(): Boolean {
                val result = super.finishComposingText()
                onCompositionEnded?.invoke()
                return result
            }
            override fun commitText(text: CharSequence?, newCursorPosition: Int): Boolean {
                val result = super.commitText(text, newCursorPosition)
                onCompositionEnded?.invoke()
                return result
            }
        }
    }

    override fun onSelectionChanged(selStart: Int, selEnd: Int) {
        super.onSelectionChanged(selStart, selEnd)
        onSelectionChangedListener?.invoke(selStart, selEnd)
    }
}
