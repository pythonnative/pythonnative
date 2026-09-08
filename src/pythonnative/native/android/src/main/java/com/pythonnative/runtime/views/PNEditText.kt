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

    override fun onSelectionChanged(selStart: Int, selEnd: Int) {
        super.onSelectionChanged(selStart, selEnd)
        onSelectionChangedListener?.invoke(selStart, selEnd)
    }
}
