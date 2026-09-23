package com.pythonnative.runtime

import com.pythonnative.generated.PNValidationFixtures
import org.json.JSONArray
import org.junit.Assert.assertEquals
import org.junit.Test
import java.io.File

class ContractFixtureTest {
    @Test fun sharedListTrace() {
        val store = com.pythonnative.runtime.components.ListStore()
        val cases = JSONArray(com.pythonnative.generated.PNListFixtures.trace)
        for (i in 0 until cases.length()) {
            val item = cases.getJSONObject(i)
            val packet = item.getJSONObject("packet")
            if (item.getBoolean("valid")) store.publish(store.prepare(packet))
            else org.junit.Assert.assertThrows(Exception::class.java) { store.prepare(packet) }
            val keys = item.getJSONArray("keys")
            assertEquals(item.getString("name"), (0 until keys.length()).map { keys.getString(it) }, store.keys)
            assertEquals(item.getLong("revision"), store.revision)
        }
    }

    @Test fun portableFixtures() {
        val root = generateSequence(File(System.getProperty("user.dir"))) { it.parentFile }
            .first { File(it, "tests/contracts/validation.json").exists() }
        val cases = JSONArray(File(root, "tests/contracts/validation.json").readText())
        for (i in 0 until cases.length()) {
            val item = cases.getJSONObject(i)
            assertEquals(item.getString("name"), item.getBoolean("valid"), PNValidationFixtures.matches(i, item.get("value")))
        }
    }
}
