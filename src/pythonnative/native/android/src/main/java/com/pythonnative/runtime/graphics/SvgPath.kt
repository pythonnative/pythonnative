package com.pythonnative.runtime.graphics

import android.graphics.Matrix
import android.graphics.Path
import kotlin.math.PI
import kotlin.math.abs
import kotlin.math.atan2
import kotlin.math.cos
import kotlin.math.sin
import kotlin.math.sqrt
import kotlin.math.tan

/**
 * Parser for the SVG path `d` attribute producing an [android.graphics.Path].
 *
 * Supports every command in SVG 1.1 (`M L H V C S Q T A Z`, absolute and
 * relative), implicit repeated coordinates, and arc flags run together
 * (`a9 9 0 11-6.2-8.5`), which is how minified icon sets write them.
 * Elliptical arcs are converted to `arcTo` sweeps on the equivalent
 * transformed ellipse.
 */
object SvgPath {
    private sealed class Token {
        class Command(val letter: Char) : Token()
        class Number(val value: Float) : Token()
    }

    /** Parse `d`; `null` when the string is empty or has no valid drawing commands. */
    fun parse(d: String): Path? {
        val tokens = tokenize(d)
        if (tokens.isEmpty()) return null
        val path = Path()
        var index = 0
        var current = floatArrayOf(0f, 0f)
        var start = floatArrayOf(0f, 0f)
        var lastControl: FloatArray? = null
        var lastCommand = 'M'
        var drew = false

        fun number(): Float? {
            val token = tokens.getOrNull(index) as? Token.Number ?: return null
            index++
            return token.value
        }
        fun numbers(count: Int): FloatArray? {
            val out = FloatArray(count)
            for (i in 0 until count) out[i] = number() ?: return null
            return out
        }
        fun hasNumber() = tokens.getOrNull(index) is Token.Number

        while (index < tokens.size) {
            val token = tokens[index]
            val letter: Char
            if (token is Token.Command) {
                letter = token.letter
                index++
            } else {
                // Implicit repeat; a repeated M becomes L.
                letter = when (lastCommand) {
                    'M' -> 'L'
                    'm' -> 'l'
                    else -> lastCommand
                }
            }
            val relative = letter.isLowerCase()
            val upper = letter.uppercaseChar()
            fun abs(x: Float, y: Float): FloatArray =
                if (relative) floatArrayOf(current[0] + x, current[1] + y) else floatArrayOf(x, y)

            when (upper) {
                'M' -> {
                    val values = numbers(2) ?: return finish(path, drew)
                    current = abs(values[0], values[1])
                    start = current
                    path.moveTo(current[0], current[1])
                    lastControl = null
                }
                'L' -> {
                    val values = numbers(2) ?: return finish(path, drew)
                    current = abs(values[0], values[1])
                    path.lineTo(current[0], current[1])
                    drew = true
                    lastControl = null
                }
                'H' -> {
                    val x = number() ?: return finish(path, drew)
                    current = floatArrayOf(if (relative) current[0] + x else x, current[1])
                    path.lineTo(current[0], current[1])
                    drew = true
                    lastControl = null
                }
                'V' -> {
                    val y = number() ?: return finish(path, drew)
                    current = floatArrayOf(current[0], if (relative) current[1] + y else y)
                    path.lineTo(current[0], current[1])
                    drew = true
                    lastControl = null
                }
                'C' -> {
                    val values = numbers(6) ?: return finish(path, drew)
                    val c1 = abs(values[0], values[1])
                    val c2 = abs(values[2], values[3])
                    val end = abs(values[4], values[5])
                    path.cubicTo(c1[0], c1[1], c2[0], c2[1], end[0], end[1])
                    lastControl = c2
                    current = end
                    drew = true
                }
                'S' -> {
                    val values = numbers(4) ?: return finish(path, drew)
                    val c1 = reflect(current, if (lastCommand.uppercaseChar() in "CS") lastControl else null)
                    val c2 = abs(values[0], values[1])
                    val end = abs(values[2], values[3])
                    path.cubicTo(c1[0], c1[1], c2[0], c2[1], end[0], end[1])
                    lastControl = c2
                    current = end
                    drew = true
                }
                'Q' -> {
                    val values = numbers(4) ?: return finish(path, drew)
                    val c = abs(values[0], values[1])
                    val end = abs(values[2], values[3])
                    path.quadTo(c[0], c[1], end[0], end[1])
                    lastControl = c
                    current = end
                    drew = true
                }
                'T' -> {
                    val values = numbers(2) ?: return finish(path, drew)
                    val c = reflect(current, if (lastCommand.uppercaseChar() in "QT") lastControl else null)
                    val end = abs(values[0], values[1])
                    path.quadTo(c[0], c[1], end[0], end[1])
                    lastControl = c
                    current = end
                    drew = true
                }
                'A' -> {
                    val values = numbers(7) ?: return finish(path, drew)
                    val end = abs(values[5], values[6])
                    arc(path, current, values[0], values[1], values[2], values[3] != 0f, values[4] != 0f, end)
                    current = end
                    lastControl = null
                    drew = true
                }
                'Z' -> {
                    path.close()
                    current = start
                    lastControl = null
                    drew = true
                }
                else -> return finish(path, drew)
            }
            lastCommand = letter
            if (upper == 'Z' && hasNumber()) {
                // Numbers after Z with no command are invalid; stop.
                return finish(path, drew)
            }
        }
        return finish(path, drew)
    }

    private fun finish(path: Path, drew: Boolean): Path? = if (drew) path else null

    private fun reflect(current: FloatArray, control: FloatArray?): FloatArray {
        if (control == null) return current
        return floatArrayOf(2 * current[0] - control[0], 2 * current[1] - control[1])
    }

    /** Append an SVG elliptical arc from `from` to `to` (endpoint parameterization). */
    private fun arc(path: Path, from: FloatArray, rxIn: Float, ryIn: Float, rotationDeg: Float, largeArc: Boolean, sweep: Boolean, to: FloatArray) {
        val x1 = from[0].toDouble(); val y1 = from[1].toDouble()
        val x2 = to[0].toDouble(); val y2 = to[1].toDouble()
        if (x1 == x2 && y1 == y2) return
        var rx = abs(rxIn.toDouble()); var ry = abs(ryIn.toDouble())
        if (rx == 0.0 || ry == 0.0) {
            path.lineTo(to[0], to[1])
            return
        }
        val phi = rotationDeg * PI / 180.0
        val cosPhi = cos(phi); val sinPhi = sin(phi)
        val dx = (x1 - x2) / 2.0; val dy = (y1 - y2) / 2.0
        val x1p = cosPhi * dx + sinPhi * dy
        val y1p = -sinPhi * dx + cosPhi * dy
        val lambda = (x1p * x1p) / (rx * rx) + (y1p * y1p) / (ry * ry)
        if (lambda > 1) {
            val s = sqrt(lambda)
            rx *= s; ry *= s
        }
        val sign = if (largeArc == sweep) -1.0 else 1.0
        val num = rx * rx * ry * ry - rx * rx * y1p * y1p - ry * ry * x1p * x1p
        val den = rx * rx * y1p * y1p + ry * ry * x1p * x1p
        val coefficient = if (den == 0.0) 0.0 else sign * sqrt(maxOf(0.0, num / den))
        val cxp = coefficient * (rx * y1p / ry)
        val cyp = coefficient * -(ry * x1p / rx)
        val cx = cosPhi * cxp - sinPhi * cyp + (x1 + x2) / 2.0
        val cy = sinPhi * cxp + cosPhi * cyp + (y1 + y2) / 2.0
        val startAngle = atan2((y1p - cyp) / ry, (x1p - cxp) / rx)
        val endAngle = atan2((-y1p - cyp) / ry, (-x1p - cxp) / rx)
        var delta = endAngle - startAngle
        if (sweep && delta < 0) delta += 2 * PI
        else if (!sweep && delta > 0) delta -= 2 * PI

        // Approximate with cubic Béziers in segments of at most 90 degrees so
        // the arc stays part of the current contour (arcTo would start a new one).
        val segments = maxOf(1, Math.ceil(abs(delta) / (PI / 2) - 1e-9).toInt())
        val step = delta / segments
        val k = 4.0 / 3.0 * tan(step / 4.0)
        var theta = startAngle
        fun point(angle: Double): DoubleArray {
            val ex = rx * cos(angle); val ey = ry * sin(angle)
            return doubleArrayOf(cosPhi * ex - sinPhi * ey + cx, sinPhi * ex + cosPhi * ey + cy)
        }
        fun derivative(angle: Double): DoubleArray {
            val ex = -rx * sin(angle); val ey = ry * cos(angle)
            return doubleArrayOf(cosPhi * ex - sinPhi * ey, sinPhi * ex + cosPhi * ey)
        }
        for (i in 0 until segments) {
            val next = theta + step
            val p0 = point(theta); val d0 = derivative(theta)
            val p3 = if (i == segments - 1) doubleArrayOf(x2, y2) else point(next)
            val d3 = derivative(next)
            path.cubicTo(
                (p0[0] + k * d0[0]).toFloat(), (p0[1] + k * d0[1]).toFloat(),
                (p3[0] - k * d3[0]).toFloat(), (p3[1] - k * d3[1]).toFloat(),
                p3[0].toFloat(), p3[1].toFloat(),
            )
            theta = next
        }
    }

    private fun tokenize(text: String): List<Token> {
        val tokens = ArrayList<Token>()
        var index = 0
        // Inside an arc the 4th and 5th of every 7 numbers are single-digit
        // flags that may be run together ("1 0 01 5 5").
        var arcMode = false
        var arcCount = 0
        while (index < text.length) {
            val ch = text[index]
            if (ch == ' ' || ch == ',' || ch == '\n' || ch == '\t' || ch == '\r') {
                index++
                continue
            }
            if (ch.isLetter() && ch != 'e' && ch != 'E') {
                tokens.add(Token.Command(ch))
                arcMode = ch == 'A' || ch == 'a'
                arcCount = 0
                index++
                continue
            }
            if (arcMode && (arcCount % 7 == 3 || arcCount % 7 == 4) && (ch == '0' || ch == '1')) {
                tokens.add(Token.Number(if (ch == '1') 1f else 0f))
                arcCount++
                index++
                continue
            }
            val end = numberEnd(text, index)
            if (end == index) return tokens
            val value = text.substring(index, end).toFloatOrNull() ?: return tokens
            tokens.add(Token.Number(value))
            index = end
            if (arcMode) arcCount++
        }
        return tokens
    }

    /** Index just past the number starting at `start` (handles "-.5", "1e-3", "1.5.5" -> "1.5"). */
    private fun numberEnd(text: String, start: Int): Int {
        var i = start
        if (i < text.length && (text[i] == '+' || text[i] == '-')) i++
        var digits = 0
        var seenDot = false
        while (i < text.length) {
            val c = text[i]
            if (c.isDigit()) { digits++; i++ }
            else if (c == '.' && !seenDot) { seenDot = true; i++ }
            else break
        }
        if (digits == 0) return start
        if (i < text.length && (text[i] == 'e' || text[i] == 'E')) {
            var j = i + 1
            if (j < text.length && (text[j] == '+' || text[j] == '-')) j++
            var expDigits = 0
            while (j < text.length && text[j].isDigit()) { expDigits++; j++ }
            if (expDigits > 0) i = j
        }
        return i
    }
}

/** Parser for the SVG `transform` attribute producing an [android.graphics.Matrix]. */
object SvgTransform {
    private val call = Regex("""([a-zA-Z]+)\s*\(([^)]*)\)""")

    /** Parse `text`; `null` when it contains an unknown function or malformed arguments. */
    fun parse(text: String): Matrix? {
        val matrix = Matrix()
        var matched = false
        for (match in call.findAll(text)) {
            matched = true
            val name = match.groupValues[1]
            val args = match.groupValues[2].split(Regex("[\\s,]+")).filter { it.isNotEmpty() }.map { it.toFloatOrNull() ?: return null }
            val step = Matrix()
            when (name) {
                "translate" -> {
                    if (args.isEmpty()) return null
                    step.setTranslate(args[0], args.getOrElse(1) { 0f })
                }
                "scale" -> {
                    if (args.isEmpty()) return null
                    step.setScale(args[0], args.getOrElse(1) { args[0] })
                }
                "rotate" -> {
                    if (args.isEmpty()) return null
                    if (args.size >= 3) step.setRotate(args[0], args[1], args[2]) else step.setRotate(args[0])
                }
                "skewX" -> {
                    if (args.isEmpty()) return null
                    step.setSkew(tan(Math.toRadians(args[0].toDouble())).toFloat(), 0f)
                }
                "skewY" -> {
                    if (args.isEmpty()) return null
                    step.setSkew(0f, tan(Math.toRadians(args[0].toDouble())).toFloat())
                }
                "matrix" -> {
                    if (args.size != 6) return null
                    // SVG matrix(a b c d e f) maps to [a c e; b d f; 0 0 1].
                    step.setValues(floatArrayOf(args[0], args[2], args[4], args[1], args[3], args[5], 0f, 0f, 1f))
                }
                else -> return null
            }
            // Transforms apply left to right: later functions nest inside earlier ones.
            matrix.preConcat(step)
        }
        return if (matched) matrix else null
    }
}
