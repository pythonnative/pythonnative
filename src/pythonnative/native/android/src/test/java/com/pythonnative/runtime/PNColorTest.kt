package com.pythonnative.runtime

import com.pythonnative.runtime.components.PNColor
import org.json.JSONArray
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class PNColorTest {
    private fun hex(v: Int?): String = if (v == null) "null" else String.format("%08X", v)

    @Test
    fun parsesHexForms() {
        assertEquals("FFFF0000", hex(PNColor.parse("#f00")))
        assertEquals("FF112233", hex(PNColor.parse("#112233")))
        assertEquals("80112233", hex(PNColor.parse("#80112233")))
        assertEquals("FF112233", hex(PNColor.parse("112233")))
    }

    @Test
    fun parsesFunctionalForms() {
        assertEquals("FF0A141E", hex(PNColor.parse("rgb(10, 20, 30)")))
        assertEquals("800A141E", hex(PNColor.parse("rgba(10, 20, 30, 0.5)")))
    }

    @Test
    fun parsesNamedColors() {
        assertEquals("FF000000", hex(PNColor.parse("black")))
        assertEquals("FFFFFFFF", hex(PNColor.parse("White")))
        assertEquals("00000000", hex(PNColor.parse("transparent")))
    }

    @Test
    fun parsesIntegersAndArrays() {
        assertEquals("FF112233", hex(PNColor.parse(0x112233)))
        assertEquals("80112233", hex(PNColor.parse(0x80112233L)))
        assertEquals("FF0A141E", hex(PNColor.parse(JSONArray("[10, 20, 30]"))))
        assertEquals("800A141E", hex(PNColor.parse(JSONArray("[10, 20, 30, 0.5]"))))
    }

    @Test
    fun rejectsGarbage() {
        assertNull(PNColor.parse("not a color"))
        assertNull(PNColor.parse(null))
        assertEquals(7, PNColor.parseOr("nope", 7))
    }

    private val defaultProvider = PNColor.darkModeProvider

    @After
    fun restoreProvider() {
        PNColor.darkModeProvider = defaultProvider
    }

    @Test
    fun dynamicColorsPickTheVariantForTheScheme() {
        val dynamic = JSONObject("""{"light": "#ffffff", "dark": "#000000"}""")
        assertEquals("FFFFFFFF", hex(PNColor.parse(dynamic, dark = false)))
        assertEquals("FF000000", hex(PNColor.parse(dynamic, dark = true)))
        // Any accepted color form works inside the dictionary.
        val mixed = JSONObject().put("light", "rgb(10, 20, 30)").put("dark", JSONArray("[1, 2, 3]"))
        assertEquals("FF0A141E", hex(PNColor.parse(mixed, dark = false)))
        assertEquals("FF010203", hex(PNColor.parse(mixed, dark = true)))
        // Plain maps (module arguments) resolve too.
        assertEquals("FF000000", hex(PNColor.parse(mapOf("light" to "white", "dark" to "black"), dark = true)))
        assertTrue(PNColor.isDynamic(dynamic))
        assertFalse(PNColor.isDynamic("#fff"))
    }

    @Test
    fun dynamicColorsFallBackToTheOtherVariant() {
        assertEquals("FF112233", hex(PNColor.parse(JSONObject("""{"light": "#112233"}"""), dark = true)))
        assertEquals("FF112233", hex(PNColor.parse(JSONObject("""{"dark": "#112233"}"""), dark = false)))
        assertNull(PNColor.parse(JSONObject("""{"light": "nope", "dark": "nah"}"""), dark = false))
        assertNull(PNColor.parse(JSONObject("""{"other": "#fff"}"""), dark = true))
    }

    @Test
    fun parseUsesTheDarkModeProvider() {
        val dynamic = JSONObject("""{"light": "#ffffff", "dark": "#000000"}""")
        PNColor.darkModeProvider = { false }
        assertEquals("FFFFFFFF", hex(PNColor.parse(dynamic)))
        assertEquals(0xFFFFFFFF.toInt(), PNColor.parseOr(dynamic, 7))
        PNColor.darkModeProvider = { true }
        assertEquals("FF000000", hex(PNColor.parse(dynamic)))
        // A throwing provider degrades to light instead of failing the parse.
        PNColor.darkModeProvider = { throw IllegalStateException("no context") }
        assertFalse(PNColor.isDarkMode())
        assertEquals("FFFFFFFF", hex(PNColor.parse(dynamic)))
    }
}
