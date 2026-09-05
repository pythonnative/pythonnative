package com.pythonnative.runtime

import com.pythonnative.runtime.components.PNColor
import org.json.JSONArray
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
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
}
