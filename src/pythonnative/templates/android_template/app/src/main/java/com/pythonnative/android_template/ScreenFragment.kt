package com.pythonnative.android_template

import com.pythonnative.runtime.screens.PNScreenFragment

/**
 * The app's screen fragment (named by `nav_graph.xml`). The start
 * destination has no `screen_path` argument, so it shows the entry
 * module from `pythonnative.toml` (staged into `R.string.pn_entry_module`);
 * pushed screens carry an explicit path.
 */
class ScreenFragment : PNScreenFragment() {
    override fun defaultPath(): String = getString(R.string.pn_entry_module)

    override fun defaultDevRoot(): String? =
        if (BuildConfig.DEBUG) "${requireContext().filesDir.absolutePath}/pythonnative_dev" else null
}
