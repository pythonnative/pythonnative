package com.pythonnative.runtime.views

import android.content.Context
import android.widget.HorizontalScrollView
import androidx.core.widget.NestedScrollView

/**
 * Vertical scroll view whose fling velocity is scaled by [flingScale]
 * (`ScrollView.deceleration_rate`); the platform scroller's friction is
 * not exposed, so a shorter fling is expressed as a slower start.
 */
class PNNestedScrollView(context: Context) : NestedScrollView(context) {
    var flingScale: Float = 1f

    override fun fling(velocityY: Int) {
        super.fling((velocityY * flingScale).toInt())
    }
}

/** Horizontal counterpart of [PNNestedScrollView]. */
class PNHorizontalScrollView(context: Context) : HorizontalScrollView(context) {
    var flingScale: Float = 1f

    override fun fling(velocityX: Int) {
        super.fling((velocityX * flingScale).toInt())
    }
}
