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
              ["u", 1, {"opacity": 0.5}, ["background_color"]],
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
        assertEquals(listOf("background_color"), update.removed)
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

    @Test
    fun eventsEmittedWhileACommitAppliesCarryThatCommitsIdentity() {
        val state = com.pythonnative.runtime.bridge.CommitState()
        // A view that emits during its own creation (an image starting to
        // load) is born in the applying revision; Python drops events that
        // claim an older one.
        val during = state.stampedAs("app-1", 1, 1) { org.json.JSONObject(state.event(org.json.JSONArray())) }
        assertEquals("app-1", during.getString("application"))
        assertEquals(1, during.getInt("surface"))
        assertEquals(1, during.getInt("revision"))
        val after = org.json.JSONObject(state.event(org.json.JSONArray()))
        assertEquals("", after.getString("application"))
        assertEquals(0, after.getInt("revision"))
        assertEquals(during.getInt("sequence") + 1, after.getInt("sequence"))
    }

    @Test
    fun webViewScriptResultsAreStringifiedLikeIosAndTheBrowser() {
        val stringify = com.pythonnative.runtime.components.WebViewsModule::stringify
        assertEquals("", stringify(null))
        assertEquals("", stringify("null"))
        assertEquals("hi", stringify("\"hi\""))
        assertEquals("42", stringify("42"))
        assertEquals("4.5", stringify("4.5"))
        assertEquals("true", stringify("true"))
        assertEquals("[1,2]", stringify("[1,2]"))
    }
}
