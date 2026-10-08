package com.pythonnative.runtime.bridge

import org.json.JSONArray
import org.json.JSONException
import org.json.JSONObject

/**
 * One decoded mutation op. Geometry never travels as an op: Yoga runs beside
 * the widgets (`NativeLayout`), which applies frames after each commit.
 */
sealed class Op {
    /** `["c", tag, "Type", {props}]` */
    data class Create(val tag: Long, val typeName: String, val props: JSONObject) : Op()

    /** `["u", tag, {changed}, [removed]]`; null is an explicit value */
    data class Update(val tag: Long, val changed: JSONObject, val removed: List<String> = emptyList()) : Op()

    /** `["i", parent, child, index]` (move-aware) */
    data class Insert(val parent: Long, val child: Long, val index: Int) : Op()

    /** `["d", tag]` */
    data class Destroy(val tag: Long) : Op()
}

/** Decodes individual operations after CommitState validates the entire batch. */
object PNTransaction {
    /** Decode a single op array. */
    fun decodeOp(raw: JSONArray): Op {
        val code = raw.optString(0, "")
        return when (code) {
            "c" -> Op.Create(
                tag(raw, 1),
                raw.optString(2, ""),
                raw.optJSONObject(3) ?: JSONObject(),
            )
            "u" -> Op.Update(tag(raw, 1), raw.getJSONObject(2), raw.getJSONArray(3).let { removed ->
                (0 until removed.length()).map { removed.getString(it) }
            })
            "i" -> Op.Insert(tag(raw, 1), tag(raw, 2), JsonUtil.toInt(raw.opt(3), 0))
            "d" -> Op.Destroy(tag(raw, 1))
            else -> throw JSONException("unknown opcode '$code'")
        }
    }

    private fun tag(raw: JSONArray, index: Int): Long {
        val v = raw.opt(index) ?: throw JSONException("missing tag at $index")
        return when (v) {
            is Number -> v.toLong()
            is String -> v.toLongOrNull() ?: throw JSONException("bad tag '$v'")
            else -> throw JSONException("bad tag $v")
        }
    }
}
