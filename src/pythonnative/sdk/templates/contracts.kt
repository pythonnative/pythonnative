package com.pythonnative.generated

import org.json.JSONArray
import org.json.JSONObject

/** Executable generated contracts; the mount path doesn't interpret schema JSON. */
object PNContracts {
    const val fingerprint = "{{fingerprint}}"
    private data class Field(val matches: (Any) -> Boolean, val allowed: Boolean, val layout: Boolean,
                             val recreate: Boolean, val required: Boolean, val defaultValue: Any)
    const val LAYOUT = 1
    const val RECREATE = 2
{{predicates}}
{{fields}}
    private val components: Map<String, Map<String, Field>> = mapOf(
{{components}}
    )
    private val commands: Map<String, (Any) -> Boolean> = mapOf(
{{commands}}
    )
    private val modules: Map<String, (Any) -> Boolean> = mapOf(
{{modules}}
    )
    private fun isBoolean(value: Any): Boolean = value is Boolean
    private fun isNumber(value: Any): Boolean = value is Number && value.toDouble().isFinite()
    private fun isInteger(value: Any): Boolean = value is Number && value.toDouble().isFinite() &&
        kotlin.math.abs(value.toDouble()) <= 9007199254740991.0 && value.toDouble() == value.toLong().toDouble()
    fun validate(name: String, props: JSONObject, partial: Boolean = false): Boolean {
        val fields = components[name] ?: return false
        if (!partial && fields.any { (key, field) -> field.required && !props.has(key) }) return false
        return props.keys().asSequence().all { key -> fields[key]?.let { it.allowed && it.matches(props.get(key)) } ?: false }
    }
    fun changes(name: String, keys: Iterable<String>): Int {
        val fields = components[name] ?: return LAYOUT or RECREATE
        var mask = 0
        for (key in keys) {
            if (fields[key]?.layout != false) mask = mask or LAYOUT
            if (fields[key]?.recreate == true) mask = mask or RECREATE
        }
        return mask
    }
    fun invalidatesLayout(name: String, changed: JSONObject): Boolean = changes(name, changed.keys().asSequence().asIterable()) and LAYOUT != 0
    fun validateRemoval(name: String, changed: JSONObject, removed: List<String>): Boolean {
        val fields = components[name] ?: return false
        return removed.toSet().size == removed.size && removed.all { key -> fields[key]?.let { !it.required && it.allowed && !changed.has(key) } ?: false }
    }
    fun requiresRecreation(name: String, changed: JSONObject, removed: List<String> = emptyList()): Boolean =
        changes(name, changed.keys().asSequence().asIterable() + removed) and RECREATE != 0
    fun normalize(name: String, changed: JSONObject, removed: List<String> = emptyList()): JSONObject {
        val result = JSONObject()
        for (key in changed.keys()) result.put(key, changed.get(key))
        for (key in removed) result.put(key, components[name]?.get(key)?.defaultValue ?: JSONObject.NULL)
        return result
    }
    fun validateCommand(name: String, method: String, args: JSONObject): Boolean = commands["$name.$method"]?.invoke(args) ?: false
    fun validateModule(name: String, method: String, args: JSONObject): Boolean {
        if (name in setOf("Host", "Layout", "Runtime")) return true
        return modules["$name.$method"]?.invoke(args) ?: false
    }
}
