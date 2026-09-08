package com.pythonnative.runtime

import com.pythonnative.runtime.bridge.JsonUtil
import com.pythonnative.runtime.bridge.Op
import com.pythonnative.runtime.bridge.PNTransaction
import com.pythonnative.runtime.bridge.value
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class PNTransactionTest {
    @Test
    fun decodesEveryOpcode() {
        val json = """
            [
              ["c", 1, "View", {"background_color": "#fff"}],
              ["u", 1, {"opacity": 0.5, "background_color": null}],
              ["i", 1, 2, 0],
              ["f", 2, 10, 20.5, 100, 40],
              ["d", 2]
            ]
        """.trimIndent()
        val ops = PNTransaction.decode(json)
        assertEquals(5, ops.size)
        val create = ops[0] as Op.Create
        assertEquals(1L, create.tag)
        assertEquals("View", create.typeName)
        assertEquals("#fff", create.props.getString("background_color"))
        val update = ops[1] as Op.Update
        assertEquals(0.5, update.changed.getDouble("opacity"), 1e-9)
        assertTrue(update.changed.isNull("background_color"))
        assertEquals(Op.Insert(1, 2, 0), ops[2])
        assertEquals(Op.Frame(2, 10.0, 20.5, 100.0, 40.0), ops[3])
        assertEquals(Op.Destroy(2), ops[4])
    }

    @Test
    fun infinityStringsBecomeInfinity() {
        val ops = PNTransaction.decode("""[["f", 1, 0, 0, "inf", "-inf"]]""")
        val frame = ops[0] as Op.Frame
        assertEquals(Double.POSITIVE_INFINITY, frame.width, 0.0)
        assertEquals(Double.NEGATIVE_INFINITY, frame.height, 0.0)
        assertEquals(Double.POSITIVE_INFINITY, JsonUtil.toDouble("Infinity"), 0.0)
    }

    @Test
    fun malformedOpsAreIsolated() {
        val errors = ArrayList<Int>()
        val ops = PNTransaction.decode(
            """[["c", 1, "View", {}], ["zz", 1], "not-an-array", ["i"], ["d", 1]]""",
        ) { index, _ -> errors.add(index) }
        assertEquals(listOf(1, 2, 3), errors)
        assertEquals(2, ops.size)
        assertTrue(ops[0] is Op.Create)
        assertEquals(Op.Destroy(1), ops[1])
    }

    @Test
    fun mergeKeepsExplicitNulls() {
        val target = JSONObject("""{"a": 1, "b": 2}""")
        JsonUtil.merge(target, JSONObject("""{"b": null, "c": "x"}"""))
        assertEquals(1, target.getInt("a"))
        assertTrue(target.isNull("b"))
        assertNull(target.value("b"))
        assertEquals("x", target.getString("c"))
    }

    @Test
    fun encodesResultsAsJson() {
        assertNull(JsonUtil.encode(null))
        assertEquals("\"hi\"", JsonUtil.encode("hi"))
        assertEquals("true", JsonUtil.encode(true))
        assertEquals("""{"x":1.5}""", JsonUtil.encode(mapOf("x" to 1.5)))
        assertEquals("[1,2]", JsonUtil.encode(listOf(1, 2)))
    }
}
