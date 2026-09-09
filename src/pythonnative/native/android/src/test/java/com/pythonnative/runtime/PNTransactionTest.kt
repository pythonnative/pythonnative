package com.pythonnative.runtime

import com.pythonnative.runtime.bridge.JsonUtil
import com.pythonnative.runtime.bridge.Op
import com.pythonnative.runtime.bridge.PNTransaction
import com.pythonnative.runtime.bridge.value
import org.json.JSONObject
import org.json.JSONArray
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
        val ops = (JSONArray(json).let { array -> (0 until array.length()).map { PNTransaction.decodeOp(array.getJSONArray(it)) } })
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
