package com.pythonnative.runtime.views

import android.os.Build
import android.os.Bundle
import android.view.View
import android.view.accessibility.AccessibilityNodeInfo
import androidx.core.view.accessibility.AccessibilityNodeInfoCompat
import com.pythonnative.runtime.R
import com.pythonnative.runtime.bridge.PNLog
import com.pythonnative.runtime.components.PNEvents

/**
 * Accessibility delegate that exposes PythonNative's `test_id`,
 * `accessibility_state`, `accessibility_value`, and
 * `accessibility_actions` props through the Android accessibility tree.
 *
 * `test_id` is surfaced as the node's view-id resource name, which
 * UI Automator-based tools (Maestro, UiAutomator2, Appium) match as
 * `resource-id`. State flags map onto the closest
 * [AccessibilityNodeInfo] equivalents so TalkBack announces them. A
 * numeric value becomes range info and a textual one the state
 * description. Actions follow React Native: the standard names
 * (`activate`, `longpress`, `increment`, `decrement`, `expand`,
 * `collapse`) reuse the framework action ids, everything else gets a
 * custom action from a fixed id pool, and performing any of them fires
 * `on_accessibility_action(name)` instead of the default behavior.
 * Fields left null are not applied.
 */
class PNAccessibilityDelegate : View.AccessibilityDelegate() {
    /** One `{name, label}` entry of `accessibility_actions`. */
    data class Action(val name: String, val label: String?)

    var testId: String? = null
    var stateDisabled: Boolean? = null
    var stateSelected: Boolean? = null
    var stateChecked: Boolean? = null
    var stateBusy: Boolean? = null
    var stateExpanded: Boolean? = null
    var role: String? = null
    var valueMin: Double? = null
    var valueMax: Double? = null
    var valueNow: Double? = null
    var valueText: String? = null
    var actions: List<Action> = emptyList()
        set(value) {
            field = value
            actionIds = assignIds(value)
        }

    /** Action id to action name for the current [actions]. */
    private var actionIds: Map<Int, String> = emptyMap()

    override fun onInitializeAccessibilityNodeInfo(host: View, info: AccessibilityNodeInfo) {
        super.onInitializeAccessibilityNodeInfo(host, info)
        val compat = AccessibilityNodeInfoCompat.wrap(info)
        testId?.let { info.viewIdResourceName = it }
        stateDisabled?.let { info.isEnabled = !it }
        stateSelected?.let { info.isSelected = it }
        stateChecked?.let {
            info.isCheckable = true
            info.isChecked = it
        }
        role?.let { compat.roleDescription = it }
        val min = valueMin
        val max = valueMax
        val now = valueNow
        if (now != null) {
            val lo = min ?: 0.0
            val hi = max ?: kotlin.math.max(lo, now)
            compat.rangeInfo = AccessibilityNodeInfoCompat.RangeInfoCompat.obtain(
                AccessibilityNodeInfoCompat.RangeInfoCompat.RANGE_TYPE_FLOAT, lo.toFloat(), hi.toFloat(), now.toFloat(),
            )
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            val states = mutableListOf<String>()
            valueText?.takeIf { it.isNotEmpty() }?.let { states.add(it) }
            if (stateBusy == true) states.add("busy")
            when (stateExpanded) {
                true -> states.add("expanded")
                false -> states.add("collapsed")
                null -> {}
            }
            if (states.isNotEmpty()) info.stateDescription = states.joinToString(", ")
        }
        for ((id, name) in actionIds) {
            val label = actions.firstOrNull { it.name == name }?.label ?: name
            compat.addAction(AccessibilityNodeInfoCompat.AccessibilityActionCompat(id, label))
        }
    }

    override fun performAccessibilityAction(host: View, action: Int, args: Bundle?): Boolean {
        val name = actionIds[action]
        if (name != null) {
            PNEvents.fire(host, "on_accessibility_action", name)
            return true
        }
        return super.performAccessibilityAction(host, action, args)
    }

    companion object {
        /** React Native's standard action names and the framework actions they map to. */
        val STANDARD_ACTIONS: Map<String, Int> = mapOf(
            "activate" to AccessibilityNodeInfoCompat.ACTION_CLICK,
            "longpress" to AccessibilityNodeInfoCompat.ACTION_LONG_CLICK,
            "increment" to AccessibilityNodeInfoCompat.ACTION_SCROLL_FORWARD,
            "decrement" to AccessibilityNodeInfoCompat.ACTION_SCROLL_BACKWARD,
            "expand" to AccessibilityNodeInfoCompat.ACTION_EXPAND,
            "collapse" to AccessibilityNodeInfoCompat.ACTION_COLLAPSE,
        )

        /** Resource ids reserved for custom actions (`res/values/pn_ids.xml`). */
        val CUSTOM_ACTION_IDS: IntArray = intArrayOf(
            R.id.pn_accessibility_action_0, R.id.pn_accessibility_action_1, R.id.pn_accessibility_action_2, R.id.pn_accessibility_action_3,
            R.id.pn_accessibility_action_4, R.id.pn_accessibility_action_5, R.id.pn_accessibility_action_6, R.id.pn_accessibility_action_7,
            R.id.pn_accessibility_action_8, R.id.pn_accessibility_action_9, R.id.pn_accessibility_action_10, R.id.pn_accessibility_action_11,
            R.id.pn_accessibility_action_12, R.id.pn_accessibility_action_13, R.id.pn_accessibility_action_14, R.id.pn_accessibility_action_15,
        )

        /**
         * Map each action to an id: standard names take their framework id,
         * custom names draw from [CUSTOM_ACTION_IDS] in order (`ids` lets
         * tests supply a pool). Actions beyond the pool are dropped with a
         * one-time warning.
         */
        fun assignIds(actions: List<Action>, ids: IntArray = CUSTOM_ACTION_IDS): Map<Int, String> {
            val out = LinkedHashMap<Int, String>()
            var next = 0
            for (action in actions) {
                val standard = STANDARD_ACTIONS[action.name]
                if (standard != null) {
                    out[standard] = action.name
                } else if (next < ids.size) {
                    out[ids[next++]] = action.name
                } else {
                    PNLog.once("a11y-actions", "accessibility_actions: more than ${ids.size} custom actions on one view; extra actions ignored")
                }
            }
            return out
        }
    }
}
