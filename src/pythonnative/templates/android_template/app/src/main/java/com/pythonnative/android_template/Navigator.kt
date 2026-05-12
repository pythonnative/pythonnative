package com.pythonnative.android_template

import android.os.Bundle
import androidx.core.os.bundleOf
import androidx.fragment.app.FragmentActivity
import androidx.navigation.fragment.NavHostFragment

object Navigator {
    @JvmStatic
    fun push(activity: FragmentActivity, screenPath: String, argsJson: String?) {
        val navHost = activity.supportFragmentManager.findFragmentById(R.id.nav_host_fragment) as NavHostFragment
        val navController = navHost.navController
        val args = Bundle()
        args.putString("screen_path", screenPath)
        if (argsJson != null) {
            args.putString("args_json", argsJson)
        }
        navController.navigate(R.id.screenFragment, args)
    }

    @JvmStatic
    fun pop(activity: FragmentActivity) {
        val navHost = activity.supportFragmentManager.findFragmentById(R.id.nav_host_fragment) as NavHostFragment
        navHost.navController.popBackStack()
    }

    /**
     * Pop every fragment off the back stack except the start destination.
     *
     * Used by the declarative
     * [`Stack.reset`][pythonnative.navigation._DeclarativeNavHandle.reset]
     * call so navigators can return the user to the initial screen
     * without manually popping one screen at a time.
     */
    @JvmStatic
    fun popToRoot(activity: FragmentActivity) {
        val navHost = activity.supportFragmentManager.findFragmentById(R.id.nav_host_fragment) as NavHostFragment
        val navController = navHost.navController
        // popBackStack(destination, inclusive=false) pops everything ABOVE the destination.
        val startDestination = navController.graph.startDestinationId
        navController.popBackStack(startDestination, false)
    }
}
