package com.pythonnative.runtime

import com.pythonnative.generated.PNContracts
import org.json.JSONArray
import org.junit.Assert.assertEquals
import org.junit.Test
import java.io.File

class ContractFixtureTest {
    @Test fun portableFixtures() {
        val root = generateSequence(File(System.getProperty("user.dir"))) { it.parentFile }
            .first { File(it, "tests/contracts/validation.json").exists() }
        val cases = JSONArray(File(root, "tests/contracts/validation.json").readText())
        for (i in 0 until cases.length()) {
            val item = cases.getJSONObject(i)
            assertEquals(item.getString("name"), item.getBoolean("valid"), PNContracts.matches(item.get("value"), item.getJSONObject("schema")))
        }
    }
}
