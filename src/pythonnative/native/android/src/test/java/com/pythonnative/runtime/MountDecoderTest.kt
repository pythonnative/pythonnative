package com.pythonnative.runtime

import com.pythonnative.runtime.mount.MountDecoder
import com.pythonnative.runtime.mount.MountOp
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.nio.ByteBuffer
import java.nio.ByteOrder

/**
 * Decodes mount transactions that the host build of the renderer core
 * produced. To regenerate them, load the contracts for "android" into
 * `pythonnative.bridge.core.load_core()`, commit the ops each fixture
 * describes on surface 7 (a 320 by 480 viewport, every leaf measuring 40
 * by 20), and print each `mount_next()` buffer as hex.
 */
class MountDecoderTest {
    private fun bytes(hex: String): ByteBuffer {
        val out = ByteBuffer.allocateDirect(hex.length / 2)
        for (i in hex.indices step 2) out.put(hex.substring(i, i + 2).toInt(16).toByte())
        out.flip()
        return out
    }

    /** Create a View, a Text, and a View, insert them, and lay them out. */
    private val first = bytes(
        "504e4d540100000007000000000000000100000000000000010000000000000007000000010100000000000000040000" +
        "00566965770702000000100000006261636b67726f756e645f636f6c6f72050700000023666630303030070000007061" +
        "6464696e67030a00000000000000010200000000000000040000005465787407020000000400000074657874050a0000" +
        "0068c3a96c6c6f20e29c9309000000666f6e745f73697a65030e00000000000000010300000000000000040000005669" +
        "65770703000000070000006f70616369747904000000000000e03f050000007769647468033200000000000000060000" +
        "006865696768740300f2052a010000000301000000000000000300000000000000000000000301000000000000000200" +
        "00000000000000000000060200000000000000000000000000244000000000000024400000000000c072400000000000" +
        "00344006030000000000000000000000000024400000000000003e400000000000004940000000205fa0f241"
    )

    /** Remove the second View's only paint prop (it flattens away) and move it first. */
    private val second = bytes(
        "504e4d540100000007000000000000000200000000000000020000000000000003000000020300000000000000000702" +
        "000000050000007769647468033c00000000000000070000006f7061636974790001000000070000006f706163697479" +
        "0503000000000000000602000000000000000000000000002440000000205fa0f2410000000000c07240000000000000" +
        "0000"
    )

    /** Delete the Text. */
    private val third = bytes(
        "504e4d540100000007000000000000000300000000000000030000000000000001000000050200000000000000"
    )

    @Test fun headerCarriesSurfaceRevisionAndId() {
        val transaction = MountDecoder.decode(first)
        assertEquals(7L, transaction.surface)
        assertEquals(1L, transaction.revision)
        assertEquals(transaction.id, MountDecoder.idOf(first))
        assertEquals(MountDecoder.decode(second).id, MountDecoder.idOf(second))
        assertTrue(MountDecoder.idOf(second) > MountDecoder.idOf(first))
    }

    @Test fun createsCarryPropsWithUnicodeAndWideIntegers() {
        val ops = MountDecoder.decode(first).ops
        val creates = ops.filterIsInstance<MountOp.Create>()
        assertEquals(listOf(1L, 2L, 3L), creates.map { it.tag })
        assertEquals(listOf("View", "Text", "View"), creates.map { it.typeName })
        assertEquals("#ff0000", creates[0].props.getString("background_color"))
        assertEquals(10, creates[0].props.get("padding"))
        assertEquals("h\u00e9llo \u2713", creates[1].props.getString("text"))
        assertEquals(0.5, creates[2].props.getDouble("opacity"), 0.0)
        assertEquals(5_000_000_000L, creates[2].props.get("height"))
    }

    @Test fun insertsAndFramesFollowCreates() {
        val ops = MountDecoder.decode(first).ops
        assertEquals(listOf(MountOp.Insert(1, 3, 0), MountOp.Insert(1, 2, 0)), ops.filterIsInstance<MountOp.Insert>())
        val frames = ops.filterIsInstance<MountOp.Frame>()
        assertEquals(MountOp.Frame(2, 10.0, 10.0, 300.0, 20.0), frames[0])
        assertEquals(MountOp.Frame(3, 10.0, 30.0, 50.0, 5e9), frames[1])
        // No frame for the layout root.
        assertTrue(frames.none { it.tag == 1L })
    }

    @Test fun updatesNormalizeRemovedKeys() {
        val ops = MountDecoder.decode(second).ops
        val update = ops[0] as MountOp.Update
        assertEquals(3L, update.tag)
        assertFalse(update.recreate)
        assertEquals(listOf("opacity"), update.removed)
        assertEquals(60, update.changed.get("width"))
        assertTrue(update.changed.has("opacity") && update.changed.isNull("opacity"))
        // Without a paint prop the view only affects layout, so it flattens away.
        assertEquals(MountOp.Delete(3), ops[1])
        assertEquals(2L, (ops[2] as MountOp.Frame).tag)
    }

    @Test fun deletes() {
        assertEquals(listOf<MountOp>(MountOp.Delete(2)), MountDecoder.decode(third).ops)
    }

    @Test fun writesAndValues() {
        val buffer = ByteBuffer.allocate(256).order(ByteOrder.LITTLE_ENDIAN)
        fun string(value: String) {
            val data = value.toByteArray(Charsets.UTF_8)
            buffer.putInt(data.size)
            buffer.put(data)
        }
        buffer.putInt(3)
        buffer.putLong(5); string("opacity"); buffer.put(4); buffer.putDouble(0.25)
        buffer.putLong(5); string("background_color"); buffer.put(5); string("#80FF0000")
        buffer.putLong(6); string("translate_x"); buffer.put(0)
        buffer.flip()
        val writes = MountDecoder.decodeWrites(buffer)
        assertEquals(3, writes.size)
        assertEquals(0.25, writes[0].value as Double, 0.0)
        assertEquals("#80FF0000", writes[1].value)
        assertNull(writes[2].value)

        val value = ByteBuffer.allocate(64).order(ByteOrder.LITTLE_ENDIAN)
        value.put(7); value.putInt(2)
        value.putInt(1); value.put('a'.code.toByte()); value.put(6); value.putInt(2); value.put(2); value.put(0)
        value.putInt(1); value.put('b'.code.toByte()); value.put(3); value.putLong(-3)
        value.flip()
        val decoded = MountDecoder.decodeValue(value) as JSONObject
        assertEquals(true, decoded.getJSONArray("a").get(0))
        assertTrue(decoded.getJSONArray("a").isNull(1))
        assertEquals(-3, decoded.get("b"))
    }
}
