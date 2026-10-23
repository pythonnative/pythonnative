package com.pythonnative.runtime.mount

import org.json.JSONArray
import org.json.JSONObject
import java.nio.ByteBuffer
import java.nio.ByteOrder

/** One op of a mount transaction (see `include/pn_core.h`). */
sealed class MountOp {
    /** Destroy every view of the surface (a new application replaced the old one). */
    object Reset : MountOp()

    /** Create a view with its initial props. */
    data class Create(val tag: Long, val typeName: String, val props: JSONObject) : MountOp()

    /** Apply changed props; removed keys arrive in `changed` with their defaults (or null). */
    data class Update(
        val tag: Long,
        val changed: JSONObject,
        val removed: List<String> = emptyList(),
        val recreate: Boolean = false,
    ) : MountOp()

    /** Ensure `child` sits at `index` under `parent`, moving it from any other parent. */
    data class Insert(val parent: Long, val child: Long, val index: Int) : MountOp()

    /** Destroy a view and detach it from its parent. */
    data class Delete(val tag: Long) : MountOp()

    /** Position a view relative to its mounted parent, in dp. */
    data class Frame(val tag: Long, val x: Double, val y: Double, val width: Double, val height: Double) : MountOp()

    /** Run a view command; the result goes back to Python under `callId`. */
    data class Command(val tag: Long, val name: String, val args: JSONObject, val callId: Long) : MountOp()
}

/** A decoded transaction. */
class MountTransaction(val surface: Long, val revision: Long, val id: Long, val ops: List<MountOp>)

/** An animated prop write produced by the core's animator. */
data class AnimatedWrite(val tag: Long, val prop: String, val value: Any?)

/**
 * Decodes the core's little-endian binary formats into the `org.json`
 * values the component managers already consume.
 */
object MountDecoder {
    private const val MAGIC = 0x544D4E50 // "PNMT"

    /** The transaction id in a transaction's header, without decoding the ops. */
    fun idOf(buffer: ByteBuffer): Long = buffer.duplicate().order(ByteOrder.LITTLE_ENDIAN).getLong(24)

    fun decode(source: ByteBuffer): MountTransaction {
        val buffer = source.duplicate().order(ByteOrder.LITTLE_ENDIAN)
        buffer.position(0)
        require(buffer.int == MAGIC) { "Not a mount transaction" }
        buffer.short
        buffer.short
        val surface = buffer.long
        val revision = buffer.long
        val id = buffer.long
        val count = buffer.int
        val ops = ArrayList<MountOp>(count)
        repeat(count) {
            ops.add(
                when (val code = buffer.get().toInt()) {
                    0 -> MountOp.Reset
                    1 -> {
                        val tag = buffer.long
                        val type = string(buffer)
                        MountOp.Create(tag, type, value(buffer) as? JSONObject ?: JSONObject())
                    }
                    2 -> {
                        val tag = buffer.long
                        val flags = buffer.get().toInt()
                        val changed = value(buffer) as? JSONObject ?: JSONObject()
                        val removed = List(buffer.int) { string(buffer) }
                        MountOp.Update(tag, changed, removed, flags and 1 != 0)
                    }
                    3 -> MountOp.Insert(buffer.long, buffer.long, buffer.int)
                    5 -> MountOp.Delete(buffer.long)
                    6 -> MountOp.Frame(buffer.long, buffer.double, buffer.double, buffer.double, buffer.double)
                    7 -> {
                        val tag = buffer.long
                        val name = string(buffer)
                        val args = value(buffer) as? JSONObject ?: JSONObject()
                        MountOp.Command(tag, name, args, buffer.long)
                    }
                    else -> throw IllegalArgumentException("Unknown mount op $code")
                },
            )
        }
        return MountTransaction(surface, revision, id, ops)
    }

    fun decodeWrites(source: ByteBuffer): List<AnimatedWrite> {
        val buffer = source.duplicate().order(ByteOrder.LITTLE_ENDIAN)
        buffer.position(0)
        return List(buffer.int) {
            val tag = buffer.long
            val prop = string(buffer)
            AnimatedWrite(tag, prop, plain(value(buffer)))
        }
    }

    /** Decode one encoded value: `JSONObject.NULL` for null, `Int` when it fits, else `Long`. */
    fun decodeValue(source: ByteBuffer): Any {
        val buffer = source.duplicate().order(ByteOrder.LITTLE_ENDIAN)
        buffer.position(0)
        return value(buffer)
    }

    private fun plain(value: Any): Any? = if (value === JSONObject.NULL) null else value

    private fun string(buffer: ByteBuffer): String {
        val length = buffer.int
        val bytes = ByteArray(length)
        buffer.get(bytes)
        return String(bytes, Charsets.UTF_8)
    }

    private fun value(buffer: ByteBuffer): Any = when (val kind = buffer.get().toInt()) {
        0 -> JSONObject.NULL
        1 -> false
        2 -> true
        3 -> {
            val number = buffer.long
            if (number in Int.MIN_VALUE..Int.MAX_VALUE) number.toInt() else number
        }
        4 -> buffer.double
        5 -> string(buffer)
        6 -> {
            val array = JSONArray()
            repeat(buffer.int) { array.put(value(buffer)) }
            array
        }
        7 -> {
            val obj = JSONObject()
            repeat(buffer.int) {
                val key = string(buffer)
                obj.put(key, value(buffer))
            }
            obj
        }
        else -> throw IllegalArgumentException("Unknown value kind $kind")
    }
}
