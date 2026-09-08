package com.pythonnative.runtime.views

import android.os.Build
import android.view.View
import android.view.accessibility.AccessibilityNodeInfo
import androidx.core.view.accessibility.AccessibilityNodeInfoCompat

/**
 * Accessibility delegate that exposes PythonNative's `test_id` and
 * `accessibility_state` props through the Android accessibility tree.
 *
 * `test_id` is surfaced as the node's view-id resource name, which
 * UI Automator-based tools (Maestro, UiAutomator2, Appium) match as
 * `resource-id`. State flags map onto the closest
 * [AccessibilityNodeInfo] equivalents so TalkBack announces them.
 * Fields left null are not applied.
 */
class PNAccessibilityDelegate : View.AccessibilityDelegate() {
    var testId: String? = null
    var stateDisabled: Boolean? = null
    var stateSelected: Boolean? = null
    var stateChecked: Boolean? = null
    var stateBusy: Boolean? = null
    var stateExpanded: Boolean? = null
    var role: String? = null

    override fun onInitializeAccessibilityNodeInfo(host: View, info: AccessibilityNodeInfo) {
        super.onInitializeAccessibilityNodeInfo(host, info)
        testId?.let { info.viewIdResourceName = it }
        stateDisabled?.let { info.isEnabled = !it }
        stateSelected?.let { info.isSelected = it }
        stateChecked?.let {
            info.isCheckable = true
            info.isChecked = it
        }
        role?.let { AccessibilityNodeInfoCompat.wrap(info).roleDescription = it }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            val states = mutableListOf<String>()
            if (stateBusy == true) states.add("busy")
            when (stateExpanded) {
                true -> states.add("expanded")
                false -> states.add("collapsed")
                null -> {}
            }
            if (states.isNotEmpty()) info.stateDescription = states.joinToString(", ")
        }
    }
}
