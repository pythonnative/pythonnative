package com.pythonnative.runtime.screens

import android.os.Bundle
import androidx.fragment.app.Fragment
import androidx.fragment.app.FragmentActivity
import androidx.fragment.app.FragmentManager
import androidx.navigation.NavController
import androidx.navigation.NavOptions
import androidx.navigation.fragment.NavHostFragment
import com.pythonnative.runtime.bridge.PNLog

/**
 * Stack navigation over the app's `NavHostFragment`. The nav graph is
 * expected to contain a single fragment destination (the app's
 * `PNScreenFragment` subclass) taking `screen_path` / `args_json` /
 * `title` arguments; every push navigates to that destination.
 */
object Navigator {
    /** Locate the `NavHostFragment` anywhere in the activity's fragment tree. */
    fun navController(activity: FragmentActivity): NavController? {
        return findNavHost(activity.supportFragmentManager)?.navController
    }

    private fun findNavHost(fm: FragmentManager): NavHostFragment? {
        for (fragment in fm.fragments) {
            if (fragment is NavHostFragment) return fragment
            val nested = findNavHost(fragment.childFragmentManager)
            if (nested != null) return nested
        }
        return null
    }

    private fun args(screenPath: String, argsJson: String?, title: String?): Bundle {
        val bundle = Bundle()
        bundle.putString(PNScreenFragment.ARG_PATH, screenPath)
        if (argsJson != null) bundle.putString(PNScreenFragment.ARG_ARGS, argsJson)
        if (title != null) bundle.putString(PNScreenFragment.ARG_TITLE, title)
        return bundle
    }

    @JvmStatic
    fun push(activity: FragmentActivity, screenPath: String, argsJson: String?, title: String? = null): Boolean {
        val nav = navController(activity) ?: return false
        return try {
            nav.navigate(nav.graph.startDestinationId, args(screenPath, argsJson, title))
            true
        } catch (e: Exception) {
            PNLog.rateLimited("nav-push", "push failed", e)
            false
        }
    }

    @JvmStatic
    fun pop(activity: FragmentActivity, count: Int = 1): Boolean {
        val nav = navController(activity) ?: run {
            activity.finish()
            return true
        }
        var popped = false
        for (i in 0 until count) {
            if (!nav.popBackStack()) {
                if (!popped) activity.finish()
                break
            }
            popped = true
        }
        return popped
    }

    /** Pop everything above the start destination. */
    @JvmStatic
    fun popToRoot(activity: FragmentActivity): Boolean {
        val nav = navController(activity) ?: return false
        return nav.popBackStack(nav.graph.startDestinationId, false)
    }

    /** Replace the current screen with a new one (pop current, push new). */
    @JvmStatic
    fun replace(activity: FragmentActivity, screenPath: String, argsJson: String?, title: String? = null): Boolean {
        val nav = navController(activity) ?: return false
        val current = nav.currentBackStackEntry?.destination?.id ?: nav.graph.startDestinationId
        return try {
            val options = NavOptions.Builder().setPopUpTo(current, true).build()
            nav.navigate(nav.graph.startDestinationId, args(screenPath, argsJson, title), options)
            true
        } catch (e: Exception) {
            PNLog.rateLimited("nav-replace", "replace failed", e)
            false
        }
    }

    /** Rebuild the whole stack from `screens` (`Triple(path, argsJson, title)`). */
    @JvmStatic
    fun reset(activity: FragmentActivity, screens: List<Triple<String, String?, String?>>): Boolean {
        val nav = navController(activity) ?: return false
        if (screens.isEmpty()) return popToRoot(activity)
        return try {
            val root = nav.graph.startDestinationId
            val (firstPath, firstArgs, firstTitle) = screens[0]
            val options = NavOptions.Builder().setPopUpTo(root, true).build()
            nav.navigate(root, args(firstPath, firstArgs, firstTitle), options)
            for (i in 1 until screens.size) {
                val (path, argsJson, title) = screens[i]
                nav.navigate(root, args(path, argsJson, title))
            }
            true
        } catch (e: Exception) {
            PNLog.rateLimited("nav-reset", "reset failed", e)
            false
        }
    }

    /** The fragment currently shown by the nav host, if any. */
    fun currentFragment(activity: FragmentActivity): Fragment? =
        findNavHost(activity.supportFragmentManager)?.childFragmentManager?.primaryNavigationFragment
}
