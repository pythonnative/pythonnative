package com.pythonnative.runtime

import com.pythonnative.runtime.modules.ModuleEnvelope
import com.pythonnative.runtime.modules.Promise
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class PromiseTest {
    @Test
    fun decodesCallEnvelope() {
        val (callId, args) = ModuleEnvelope.decodeCall("""{"call_id": 7, "args": {"url": "x"}}""")
        assertEquals(7L, callId)
        assertEquals("x", args.getString("url"))
        val (emptyId, emptyArgs) = ModuleEnvelope.decodeCall("")
        assertEquals(0L, emptyId)
        assertEquals(0, emptyArgs.length())
    }

    @Test
    fun encodesResultEnvelopes() {
        assertEquals("""{"ok":true,"value":3}""", ModuleEnvelope.ok(3))
        val err = JSONObject(ModuleEnvelope.error("boom", "code_x"))
        assertFalse(err.getBoolean("ok"))
        assertEquals("boom", err.getString("error"))
        assertEquals("code_x", err.getString("code"))
        assertEquals("""{"pending":true}""", ModuleEnvelope.pending())
        val event = JSONObject(ModuleEnvelope.event("change", mapOf("state" to "active")))
        assertEquals("change", event.getString("event"))
        assertEquals("active", event.getJSONObject("payload").getString("state"))
    }

    @Test
    fun synchronousSettlementIsReturnedInline() {
        val posted = ArrayList<Runnable>()
        val promise = Promise(1, "Test") { posted.add(it) }
        promise.resolve(mapOf("a" to 1))
        assertTrue(promise.isSettled)
        assertEquals("""{"ok":true,"value":{"a":1}}""", promise.markReturned())
        assertTrue(posted.isEmpty())
    }

    @Test
    fun asynchronousSettlementIsPosted() {
        val posted = ArrayList<Runnable>()
        val promise = Promise(9, "Test") { posted.add(it) }
        assertEquals("""{"pending":true}""", promise.markReturned())
        promise.resolve("later")
        assertEquals(1, posted.size)
        // Second settlement is ignored.
        promise.reject("nope")
        assertEquals(1, posted.size)
    }

    @Test
    fun rejectionEnvelopeCarriesCode() {
        val promise = Promise(2, "Test") { }
        promise.reject("bad", "bad_request")
        val obj = JSONObject(promise.markReturned())
        assertFalse(obj.getBoolean("ok"))
        assertEquals("bad_request", obj.getString("code"))
    }

    @Test
    fun settledEnvelopesCarryCallId() {
        val ok = JSONObject(ModuleEnvelope.settled(5, true))
        assertEquals(5L, ok.getLong("call_id"))
        assertTrue(ok.getBoolean("ok"))
        val err = JSONObject(ModuleEnvelope.settledError(6, "x", null))
        assertEquals(6L, err.getLong("call_id"))
        assertFalse(err.has("code"))
    }
}
