package com.pythonnative.runtime.bridge

import android.util.Log
import com.pythonnative.runtime.components.BuiltinComponents
import com.pythonnative.runtime.components.ComponentManager
import com.pythonnative.runtime.modules.BuiltinModules
import com.pythonnative.runtime.modules.NativeModule
import com.pythonnative.runtime.plugins.GeneratedPlugins

/**
 * A native extension: registers component managers and native modules.
 *
 * `pn build` generates a call to each plugin entry's `register` in
 * `plugins/GeneratedPlugins.kt`.
 */
interface PNPlugin {
    fun register(registry: PNRegistry)
}

/**
 * Registry of component managers (by element type) and native modules
 * (by module name). Built-ins are registered on first use, followed by
 * the generated plugin registrations.
 */
object PNRegistry {
    private val componentFactories = HashMap<String, () -> ComponentManager>()
    private val managers = HashMap<String, ComponentManager>()
    private val moduleFactories = HashMap<String, () -> NativeModule>()
    private val modules = HashMap<String, NativeModule>()
    private var builtinsRegistered = false

    /** Register (or override) the manager factory for element type `name`. */
    fun registerComponent(name: String, factory: () -> ComponentManager) {
        componentFactories[name] = factory
        managers.remove(name)
    }

    /**
     * Register a native module. The factory is invoked once to read the
     * module's `name`; the same instance then serves every call.
     */
    fun registerModule(factory: () -> NativeModule) {
        val module = factory()
        moduleFactories[module.name] = factory
        modules[module.name] = module
    }

    /** The manager for element type `name`, or `null` when unknown. */
    fun managerFor(name: String): ComponentManager? {
        ensureBuiltins()
        managers[name]?.let { return it }
        val factory = componentFactories[name] ?: return null
        val manager = factory()
        managers[name] = manager
        return manager
    }

    /** The module named `name`, or `null`. */
    fun module(name: String): NativeModule? {
        ensureBuiltins()
        return modules[name]
    }

    /** Registered element type names. */
    fun componentNames(): Set<String> {
        ensureBuiltins()
        return componentFactories.keys
    }

    /** Register built-in components and modules plus generated plugins (idempotent). */
    fun ensureBuiltins() {
        if (builtinsRegistered) return
        builtinsRegistered = true
        BuiltinComponents.register(this)
        BuiltinModules.register(this)
        try {
            GeneratedPlugins.registerAll(this)
        } catch (e: Exception) {
            Log.e(PNLog.TAG, "plugin registration failed", e)
        }
    }
}
