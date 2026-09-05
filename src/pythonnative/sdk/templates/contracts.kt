package com.pythonnative.generated

import org.json.JSONArray
import org.json.JSONObject

/** Generated contract metadata shared by built-ins and extension managers. */
object PNContracts {
    const val fingerprint = "{{fingerprint}}"
    private val components = JSONObject(listOf({{specification}}).joinToString("")).getJSONObject("components")

    fun validate(name: String, props: JSONObject, partial: Boolean = false): Boolean {
        val schema = components.optJSONObject(name) ?: return true
        val fields = schema.getJSONObject("props")
        val required = schema.optJSONArray("required") ?: JSONArray()
        if (!partial) for (i in 0 until required.length()) if (!props.has(required.getString(i))) return false
        for (key in props.keys()) {
            if (partial && props.isNull(key)) continue
            val field = fields.optJSONObject(key) ?: continue
            if (!matches(props.get(key), field)) return false
        }
        return true
    }

    fun invalidatesLayout(name: String, changed: JSONObject): Boolean {
        val fields = components.optJSONObject(name)?.optJSONObject("props") ?: return true
        return changed.keys().asSequence().any { fields.optJSONObject(it)?.optJSONObject("native")?.optBoolean("invalidates_layout", true) ?: true }
    }

    private fun matches(value: Any, schema: JSONObject): Boolean {
        schema.optJSONArray("anyOf")?.let { alternatives ->
            return (0 until alternatives.length()).any { matches(value, alternatives.getJSONObject(it)) }
        }
        schema.optJSONArray("enum")?.let { values -> return (0 until values.length()).any { values.get(it).toString() == value.toString() } }
        return when (schema.optString("type")) {
            "null" -> value == JSONObject.NULL
            "string" -> value is String
            "boolean" -> value is Boolean
            "integer" -> value is Number && value.toDouble() == value.toLong().toDouble()
            "number" -> value is Number && value.toDouble().isFinite()
            "array" -> value is JSONArray && (0 until value.length()).all { matches(value.get(it), schema.optJSONObject("items") ?: JSONObject()) }
            "object" -> value is JSONObject
            "event" -> value is Boolean || value == JSONObject.NULL
            else -> true
        }
    }
}
