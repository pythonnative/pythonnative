package com.pythonnative.generated

import org.json.JSONArray
import org.json.JSONObject

/** Generated contract metadata shared by built-ins and extension managers. */
object PNContracts {
    const val fingerprint = "{{fingerprint}}"
    private val document = JSONObject(listOf({{specification}}).joinToString(""))
    private val components = document.getJSONObject("components")
    private val modules = document.getJSONObject("modules")

    fun validate(name: String, props: JSONObject, partial: Boolean = false): Boolean {
        val schema = components.optJSONObject(name) ?: return false
        val fields = schema.getJSONObject("props")
        val required = schema.optJSONArray("required") ?: JSONArray()
        if (!partial) for (i in 0 until required.length()) if (!props.has(required.getString(i))) return false
        for (key in props.keys()) {
            val field = fields.optJSONObject(key) ?: return false
            val platforms = field.optJSONObject("native")?.optJSONArray("platforms")
            if (platforms != null && (0 until platforms.length()).none { platforms.getString(it) == "android" }) return false
            if (partial && props.isNull(key)) {
                if ((0 until required.length()).any { required.getString(it) == key }) return false
                continue
            }
            if (!matches(props.get(key), field)) return false
        }
        return true
    }

    fun invalidatesLayout(name: String, changed: JSONObject): Boolean {
        val fields = components.optJSONObject(name)?.optJSONObject("props") ?: return true
        return changed.keys().asSequence().any { fields.optJSONObject(it)?.optJSONObject("native")?.optBoolean("invalidates_layout", true) ?: true }
    }

    fun requiresRecreation(name: String, changed: JSONObject): Boolean {
        val schema = components.optJSONObject(name) ?: return true
        val fields = schema.getJSONObject("props")
        val defaults = schema.optJSONObject("defaults") ?: JSONObject()
        return changed.keys().asSequence().any { key ->
            fields.optJSONObject(key)?.optJSONObject("native")?.optBoolean("recreate", false) == true ||
                (changed.isNull(key) && defaults.isNull(key))
        }
    }

    fun normalize(name: String, changed: JSONObject): JSONObject {
        val defaults = components.optJSONObject(name)?.optJSONObject("defaults") ?: JSONObject()
        val result = JSONObject()
        for (key in changed.keys()) result.put(key, if (changed.isNull(key)) defaults.opt(key) ?: JSONObject.NULL else changed.get(key))
        return result
    }

    fun validateCommand(name: String, method: String, args: JSONObject): Boolean =
        components.optJSONObject(name)?.optJSONObject("commands")?.optJSONObject(method)?.let { validateArguments(it, args) } ?: false

    fun validateModule(name: String, method: String, args: JSONObject): Boolean {
        val module = modules.optJSONObject(name) ?: return name in setOf("Host", "Layout", "Runtime")
        return module.optJSONObject("methods")?.optJSONObject(method)?.let { validateArguments(it, args) } ?: false
    }

    private fun validateArguments(command: JSONObject, args: JSONObject): Boolean = matches(args,
        JSONObject().put("type", "object").put("properties", command.getJSONObject("arguments"))
            .put("required", command.optJSONArray("required") ?: JSONArray(command.getJSONObject("arguments").keys().asSequence().toList()))
            .put("additionalProperties", false))

    fun matches(value: Any, schema: JSONObject): Boolean {
        schema.optJSONArray("anyOf")?.let { alternatives ->
            return (0 until alternatives.length()).any { matches(value, alternatives.getJSONObject(it)) }
        }
        schema.optJSONArray("enum")?.let { values -> return (0 until values.length()).any { val item = values.get(it); if (item is Number && value is Number) item.toDouble() == value.toDouble() else item == value } }
        return when (schema.optString("type")) {
            "null" -> value == JSONObject.NULL
            "string" -> value is String
            "boolean" -> value is Boolean
            "integer" -> value is Number && value.toDouble().isFinite() && kotlin.math.abs(value.toDouble()) <= 9007199254740991.0 && value.toDouble() == value.toLong().toDouble()
            "number" -> value is Number && value.toDouble().isFinite()
            "array" -> value is JSONArray && (0 until value.length()).all { matches(value.get(it), schema.optJSONObject("items") ?: JSONObject()) }
            "object" -> {
                if (value !is JSONObject) false else {
                    val fields = schema.optJSONObject("properties") ?: JSONObject()
                    val required = schema.optJSONArray("required") ?: JSONArray()
                    (0 until required.length()).all { value.has(required.getString(it)) } && value.keys().asSequence().all { key ->
                        val field = fields.optJSONObject(key) ?: schema.optJSONObject("additionalProperties")
                        if (field != null) matches(value.get(key), field) else schema.opt("additionalProperties") != false
                    }
                }
            }
            "event" -> value is Boolean
            else -> true
        }
    }
}
