package com.pythonnative.runtime.bridge

import org.json.JSONArray
import org.json.JSONException
import org.json.JSONObject

/** One decoded mutation op. Geometry is in dp (points). */
sealed class Op {
    /** `["c", tag, "Type", {props}]` */
    data class Create(val tag: Long, val typeName: String, val props: JSONObject) : Op()

    /** `["u", tag, {changed}]` (a `null` value means the prop was removed) */
    data class Update(val tag: Long, val changed: JSONObject) : Op()

    /** `["i", parent, child, index]` (move-aware) */
    data class Insert(val parent: Long, val child: Long, val index: Int) : Op()

    /** `["d", tag]` */
    data class Destroy(val tag: Long) : Op()

    /** `["f", tag, x, y, w, h]` relative to the parent's content origin */
    data class Frame(val tag: Long, val x: Double, val y: Double, val width: Double, val height: Double) : Op()
}

/**
 * Decoder for the transaction wire format: a JSON array of ops, each an
 * array whose first element is a one-letter opcode.
 *
 * Decoding is isolated per op: a malformed entry is reported through
 * `onError` and skipped so the rest of the commit still applies.
 */
object PNTransaction {
    /** Decode `json`; invalid ops are skipped after `onError(index, error)`. */
    fun decode(json: String, onError: (Int, Throwable) -> Unit = { _, _ -> }): List<Op> {
        val array = JSONArray(json)
        val ops = ArrayList<Op>(array.length())
        for (i in 0 until array.length()) {
            try {
                val raw = array.get(i) as? JSONArray
                    ?: throw JSONException("op $i is not an array")
                ops.add(decodeOp(raw))
            } catch (e: Exception) {
                onError(i, e)
            }
        }
        return ops
    }

    /** Decode a single op array. */
    fun decodeOp(raw: JSONArray): Op {
        val code = raw.optString(0, "")
        return when (code) {
            "c" -> Op.Create(
                tag(raw, 1),
                raw.optString(2, ""),
                raw.optJSONObject(3) ?: JSONObject(),
            )
            "u" -> Op.Update(tag(raw, 1), raw.optJSONObject(2) ?: JSONObject())
            "i" -> Op.Insert(tag(raw, 1), tag(raw, 2), JsonUtil.toInt(raw.opt(3), 0))
            "d" -> Op.Destroy(tag(raw, 1))
            "f" -> Op.Frame(
                tag(raw, 1),
                JsonUtil.toDouble(raw.opt(2)),
                JsonUtil.toDouble(raw.opt(3)),
                JsonUtil.toDouble(raw.opt(4)),
                JsonUtil.toDouble(raw.opt(5)),
            )
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
