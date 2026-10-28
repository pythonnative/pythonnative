package com.pythonnative.runtime.components

import android.content.Context
import android.content.res.Configuration
import android.util.TypedValue

/**
 * Theme attribute lookups shared by the managers that draw chrome
 * (tab bars, modals, screen backgrounds, toolbars). Every helper reads
 * the attribute from the context's theme so light and dark themes are
 * honored automatically, and falls back to a plain color only when the
 * theme defines nothing.
 */
object PNTheme {
    /** Resolve theme attribute `attr` to an ARGB color, or `null` when the theme lacks it. */
    fun color(context: Context, attr: Int): Int? {
        val value = TypedValue()
        if (!context.theme.resolveAttribute(attr, value, true)) return null
        return try {
            when {
                value.resourceId != 0 -> context.getColor(value.resourceId)
                value.type >= TypedValue.TYPE_FIRST_COLOR_INT && value.type <= TypedValue.TYPE_LAST_COLOR_INT -> value.data
                else -> null
            }
        } catch (_: Exception) {
            null
        }
    }

    /** The first of `attrs` the theme resolves, or `fallback`. */
    fun color(context: Context, attrs: IntArray, fallback: Int): Int {
        for (attr in attrs) color(context, attr)?.let { return it }
        return fallback
    }

    /** Whether the context's configuration is in night mode. */
    fun isDark(context: Context): Boolean =
        context.resources.configuration.uiMode and Configuration.UI_MODE_NIGHT_MASK == Configuration.UI_MODE_NIGHT_YES

    /** Material `colorSurface`, then `android:colorBackground`, then white or near-black by UI mode. */
    fun surface(context: Context): Int = color(
        context,
        intArrayOf(com.google.android.material.R.attr.colorSurface, android.R.attr.colorBackground),
        if (isDark(context)) DARK_FALLBACK else LIGHT_FALLBACK,
    )

    /** `android:colorBackground` (the window background), then a UI-mode fallback. */
    fun background(context: Context): Int = color(
        context,
        intArrayOf(android.R.attr.colorBackground, com.google.android.material.R.attr.colorSurface),
        if (isDark(context)) DARK_FALLBACK else LIGHT_FALLBACK,
    )

    /** `android:textColorPrimary`, then black or white by UI mode. */
    fun textPrimary(context: Context): Int = color(
        context,
        intArrayOf(android.R.attr.textColorPrimary),
        if (isDark(context)) 0xFFFFFFFF.toInt() else 0xFF000000.toInt(),
    )

    /** `colorControlNormal` (icon tint), then the primary text color. */
    fun controlNormal(context: Context): Int =
        color(context, androidx.appcompat.R.attr.colorControlNormal) ?: textPrimary(context)

    private const val LIGHT_FALLBACK = 0xFFFFFFFF.toInt()
    private const val DARK_FALLBACK = 0xFF121212.toInt()
}
