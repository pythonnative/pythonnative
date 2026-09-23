package com.pythonnative.generated

import org.json.JSONArray
import org.json.JSONObject

/** Executable generated contracts; the mount path doesn't interpret schema JSON. */
object PNContracts {
    const val fingerprint = "166f5173f9fabc1e15a071df2083d769de8c76d29c5276b57874948b38f55944"
    private data class Field(val matches: (Any) -> Boolean, val allowed: Boolean, val layout: Boolean,
                             val recreate: Boolean, val required: Boolean, val defaultValue: Any)
    const val LAYOUT = 1
    const val RECREATE = 2
    private fun match0(value: Any): Boolean {
        if (value !is JSONObject) return false
        for (key in value.keys()) {
            val item = value.get(key)
            val valid = when (key) {
                else -> true
            }
            if (!valid) return false
        }
        return true
    }
    private fun match1(value: Any): Boolean {
        return isInteger(value)
    }
    private fun match3(value: Any): Boolean {
        return value is String
    }
    private fun match2(value: Any): Boolean {
        if (value !is JSONArray) return false
        return (0 until value.length()).all { match3(value.get(it)) }
    }
    private fun match4(value: Any): Boolean {
        return (value == "left") || (value == "right")
    }
    private fun match5(value: Any): Boolean {
        return isBoolean(value)
    }
    private fun match6(value: Any): Boolean {
        return (value == "flex_start") || (value == "center") || (value == "flex_end") || (value == "stretch") || (value == "space_between") || (value == "space_around") || (value == "space_evenly")
    }
    private fun match7(value: Any): Boolean {
        return (value == "stretch") || (value == "flex_start") || (value == "center") || (value == "flex_end") || (value == "baseline") || (value == "auto") || (value == "start") || (value == "leading") || (value == "top") || (value == "end") || (value == "trailing") || (value == "bottom") || (value == "fill")
    }
    private fun match8(value: Any): Boolean {
        return isNumber(value)
    }
    private fun match10(value: Any): Boolean {
        if (value !is JSONObject) return false
        if (!value.has("dark")) return false
        if (!value.has("light")) return false
        for (key in value.keys()) {
            val item = value.get(key)
            val valid = when (key) {
                "dark" -> match3(item)
                "light" -> match3(item)
                else -> false
            }
            if (!valid) return false
        }
        return true
    }
    private fun match9(value: Any): Boolean {
        return match3(value) || match10(value)
    }
    private fun match11(value: Any): Boolean {
        return (value == "solid") || (value == "dashed") || (value == "dotted")
    }
    private fun match12(value: Any): Boolean {
        return match1(value) || match8(value) || match3(value)
    }
    private fun match14(value: Any): Boolean {
        return value == JSONObject.NULL
    }
    private fun match13(value: Any): Boolean {
        return match3(value) || match10(value) || match14(value)
    }
    private fun match15(value: Any): Boolean {
        return (value == "ltr") || (value == "rtl")
    }
    private fun match16(value: Any): Boolean {
        return (value == "flex") || (value == "none")
    }
    private fun match17(value: Any): Boolean {
        return (value == "row") || (value == "column") || (value == "row_reverse") || (value == "column_reverse")
    }
    private fun match18(value: Any): Boolean {
        return (value == "nowrap") || (value == "wrap") || (value == "wrap_reverse")
    }
    private fun match19(value: Any): Boolean {
        return (value == "normal") || (value == "bold") || (value == "100") || (value == "200") || (value == "300") || (value == "400") || (value == "500") || (value == "600") || (value == "700") || (value == "800") || (value == "900")
    }
    private fun match21(value: Any): Boolean {
        return true
    }
    private fun match20(value: Any): Boolean {
        if (value !is JSONArray) return false
        return (0 until value.length()).all { match21(value.get(it)) }
    }
    private fun match22(value: Any): Boolean {
        return (value == "flex_start") || (value == "center") || (value == "flex_end") || (value == "space_between") || (value == "space_around") || (value == "space_evenly") || (value == "start") || (value == "leading") || (value == "top") || (value == "end") || (value == "trailing") || (value == "bottom")
    }
    private fun match24(value: Any): Boolean {
        return (value == "auto")
    }
    private fun match25(value: Any): Boolean {
        if (value !is JSONObject) return false
        for (key in value.keys()) {
            val item = value.get(key)
            val valid = when (key) {
                "all" -> match12(item)
                "bottom" -> match12(item)
                "horizontal" -> match12(item)
                "left" -> match12(item)
                "right" -> match12(item)
                "top" -> match12(item)
                "vertical" -> match12(item)
                else -> false
            }
            if (!valid) return false
        }
        return true
    }
    private fun match23(value: Any): Boolean {
        return match1(value) || match8(value) || match3(value) || match24(value) || match25(value)
    }
    private fun match26(value: Any): Boolean {
        return match1(value) || match8(value) || match3(value) || match24(value)
    }
    private fun match27(value: Any): Boolean {
        return isBoolean(value)
    }
    private fun match28(value: Any): Boolean {
        return (value == "visible") || (value == "hidden") || (value == "scroll")
    }
    private fun match29(value: Any): Boolean {
        return match1(value) || match8(value) || match3(value) || match25(value)
    }
    private fun match30(value: Any): Boolean {
        return (value == "auto") || (value == "none") || (value == "box_none") || (value == "box_only")
    }
    private fun match31(value: Any): Boolean {
        return (value == "relative") || (value == "absolute")
    }
    private fun match33(value: Any): Boolean {
        if (value !is JSONObject) return false
        if (!value.has("height")) return false
        if (!value.has("width")) return false
        for (key in value.keys()) {
            val item = value.get(key)
            val valid = when (key) {
                "height" -> match8(item)
                "width" -> match8(item)
                else -> false
            }
            if (!valid) return false
        }
        return true
    }
    private fun match34(value: Any): Boolean {
        if (value !is JSONArray) return false
        return value.length() == 2 && match8(value.get(0)) && match8(value.get(1))
    }
    private fun match35(value: Any): Boolean {
        if (value !is JSONArray) return false
        return (0 until value.length()).all { match8(value.get(it)) }
    }
    private fun match32(value: Any): Boolean {
        return match33(value) || match34(value) || match35(value)
    }
    private fun match36(value: Any): Boolean {
        return (value == "small") || (value == "large")
    }
    private fun match37(value: Any): Boolean {
        return (value == "left") || (value == "center") || (value == "right") || (value == "justify") || (value == "start") || (value == "end")
    }
    private fun match38(value: Any): Boolean {
        return (value == "none") || (value == "underline") || (value == "line_through")
    }
    private fun match39(value: Any): Boolean {
        return (value == "none") || (value == "uppercase") || (value == "lowercase") || (value == "capitalize")
    }
    private fun match42(value: Any): Boolean {
        return match8(value) || match3(value)
    }
    private fun match41(value: Any): Boolean {
        if (value !is JSONObject) return false
        if (!value.has("rotate")) return false
        for (key in value.keys()) {
            val item = value.get(key)
            val valid = when (key) {
                "rotate" -> match42(item)
                else -> false
            }
            if (!valid) return false
        }
        return true
    }
    private fun match43(value: Any): Boolean {
        if (value !is JSONObject) return false
        if (!value.has("rotate_x")) return false
        for (key in value.keys()) {
            val item = value.get(key)
            val valid = when (key) {
                "rotate_x" -> match42(item)
                else -> false
            }
            if (!valid) return false
        }
        return true
    }
    private fun match44(value: Any): Boolean {
        if (value !is JSONObject) return false
        if (!value.has("rotate_y")) return false
        for (key in value.keys()) {
            val item = value.get(key)
            val valid = when (key) {
                "rotate_y" -> match42(item)
                else -> false
            }
            if (!valid) return false
        }
        return true
    }
    private fun match45(value: Any): Boolean {
        if (value !is JSONObject) return false
        if (!value.has("rotate_z")) return false
        for (key in value.keys()) {
            val item = value.get(key)
            val valid = when (key) {
                "rotate_z" -> match42(item)
                else -> false
            }
            if (!valid) return false
        }
        return true
    }
    private fun match46(value: Any): Boolean {
        if (value !is JSONObject) return false
        if (!value.has("scale")) return false
        for (key in value.keys()) {
            val item = value.get(key)
            val valid = when (key) {
                "scale" -> match8(item)
                else -> false
            }
            if (!valid) return false
        }
        return true
    }
    private fun match47(value: Any): Boolean {
        if (value !is JSONObject) return false
        if (!value.has("scale_x")) return false
        for (key in value.keys()) {
            val item = value.get(key)
            val valid = when (key) {
                "scale_x" -> match8(item)
                else -> false
            }
            if (!valid) return false
        }
        return true
    }
    private fun match48(value: Any): Boolean {
        if (value !is JSONObject) return false
        if (!value.has("scale_y")) return false
        for (key in value.keys()) {
            val item = value.get(key)
            val valid = when (key) {
                "scale_y" -> match8(item)
                else -> false
            }
            if (!valid) return false
        }
        return true
    }
    private fun match49(value: Any): Boolean {
        if (value !is JSONObject) return false
        for (key in value.keys()) {
            val item = value.get(key)
            val valid = when (key) {
                "translate_x" -> match8(item)
                "translate_y" -> match8(item)
                else -> false
            }
            if (!valid) return false
        }
        return true
    }
    private fun match50(value: Any): Boolean {
        if (value !is JSONObject) return false
        if (!value.has("skew_x")) return false
        for (key in value.keys()) {
            val item = value.get(key)
            val valid = when (key) {
                "skew_x" -> match42(item)
                else -> false
            }
            if (!valid) return false
        }
        return true
    }
    private fun match51(value: Any): Boolean {
        if (value !is JSONObject) return false
        if (!value.has("skew_y")) return false
        for (key in value.keys()) {
            val item = value.get(key)
            val valid = when (key) {
                "skew_y" -> match42(item)
                else -> false
            }
            if (!valid) return false
        }
        return true
    }
    private fun match52(value: Any): Boolean {
        if (value !is JSONObject) return false
        if (!value.has("perspective")) return false
        for (key in value.keys()) {
            val item = value.get(key)
            val valid = when (key) {
                "perspective" -> match8(item)
                else -> false
            }
            if (!valid) return false
        }
        return true
    }
    private fun match54(value: Any): Boolean {
        return true
    }
    private fun match53(value: Any): Boolean {
        if (value !is JSONObject) return false
        for (key in value.keys()) {
            val item = value.get(key)
            val valid = when (key) {
                else -> match54(item)
            }
            if (!valid) return false
        }
        return true
    }
    private fun match56(value: Any): Boolean {
        return match41(value) || match43(value) || match44(value) || match45(value) || match46(value) || match47(value) || match48(value) || match49(value) || match50(value) || match51(value) || match52(value) || match53(value)
    }
    private fun match55(value: Any): Boolean {
        if (value !is JSONArray) return false
        return (0 until value.length()).all { match56(value.get(it)) }
    }
    private fun match40(value: Any): Boolean {
        return match41(value) || match43(value) || match44(value) || match45(value) || match46(value) || match47(value) || match48(value) || match49(value) || match50(value) || match51(value) || match52(value) || match53(value) || match55(value)
    }
    private fun component0(): Map<String, Field> = mapOf(
        "_pn_animated_events" to field0,
        "_pn_edit_revision" to field1,
        "_pn_events" to field2,
        "_pn_header_slot" to field3,
        "_pn_layout" to field4,
        "_pn_list_key" to field5,
        "accessibility_role" to field6,
        "align_content" to field7,
        "align_items" to field8,
        "align_self" to field8,
        "animating" to field9,
        "aspect_ratio" to field10,
        "background_color" to field11,
        "bold" to field12,
        "border_bottom_color" to field13,
        "border_bottom_left_radius" to field14,
        "border_bottom_right_radius" to field14,
        "border_bottom_width" to field10,
        "border_color" to field13,
        "border_left_color" to field13,
        "border_left_width" to field10,
        "border_radius" to field14,
        "border_right_color" to field13,
        "border_right_width" to field10,
        "border_style" to field15,
        "border_top_color" to field13,
        "border_top_left_radius" to field14,
        "border_top_right_radius" to field14,
        "border_top_width" to field10,
        "border_width" to field10,
        "bottom" to field16,
        "color" to field17,
        "column_gap" to field10,
        "direction" to field18,
        "display" to field19,
        "elevation" to field14,
        "end" to field16,
        "flex" to field10,
        "flex_basis" to field16,
        "flex_direction" to field20,
        "flex_grow" to field10,
        "flex_shrink" to field10,
        "flex_wrap" to field21,
        "font_family" to field22,
        "font_size" to field10,
        "font_weight" to field23,
        "gap" to field10,
        "gestures" to field24,
        "height" to field16,
        "italic" to field12,
        "justify_content" to field25,
        "left" to field16,
        "letter_spacing" to field10,
        "line_height" to field10,
        "margin" to field26,
        "margin_bottom" to field27,
        "margin_end" to field27,
        "margin_horizontal" to field27,
        "margin_left" to field27,
        "margin_right" to field27,
        "margin_start" to field27,
        "margin_top" to field27,
        "margin_vertical" to field27,
        "max_height" to field16,
        "max_lines" to field28,
        "max_width" to field16,
        "min_height" to field16,
        "min_width" to field16,
        "on_layout" to field29,
        "opacity" to field30,
        "overflow" to field31,
        "padding" to field32,
        "padding_bottom" to field16,
        "padding_end" to field16,
        "padding_horizontal" to field16,
        "padding_left" to field16,
        "padding_right" to field16,
        "padding_start" to field16,
        "padding_top" to field16,
        "padding_vertical" to field16,
        "placeholder_color" to field13,
        "pointer_events" to field33,
        "position" to field34,
        "ref" to field35,
        "right" to field16,
        "row_gap" to field10,
        "shadow_color" to field13,
        "shadow_offset" to field36,
        "shadow_opacity" to field14,
        "shadow_radius" to field14,
        "size" to field37,
        "spacing" to field10,
        "start" to field16,
        "text_align" to field38,
        "text_decoration" to field39,
        "text_shadow_color" to field13,
        "text_shadow_offset" to field36,
        "text_shadow_radius" to field14,
        "text_transform" to field40,
        "tint_color" to field13,
        "top" to field16,
        "transform" to field41,
        "width" to field16,
        "z_index" to field42
    )
    private fun match57(value: Any): Boolean {
        return match3(value) || match14(value)
    }
    private fun match58(value: Any): Boolean {
        return match5(value) || match14(value)
    }
    private fun match59(value: Any): Boolean {
        return (value == "light") || (value == "dark") || (value == "regular") || (value == "prominent") || (value == "extra_light") || (value == "system_thin_material") || (value == "system_material") || (value == "system_thick_material") || (value == "system_chrome_material")
    }
    private fun component1(): Map<String, Field> = mapOf(
        "_pn_animated_events" to field0,
        "_pn_edit_revision" to field1,
        "_pn_events" to field2,
        "_pn_header_slot" to field3,
        "_pn_layout" to field4,
        "_pn_list_key" to field5,
        "accessibility_label" to field43,
        "accessibility_role" to field6,
        "accessible" to field44,
        "align_content" to field7,
        "align_items" to field8,
        "align_self" to field8,
        "aspect_ratio" to field10,
        "background_color" to field11,
        "blur_type" to field45,
        "bold" to field12,
        "border_bottom_color" to field13,
        "border_bottom_left_radius" to field14,
        "border_bottom_right_radius" to field14,
        "border_bottom_width" to field10,
        "border_color" to field13,
        "border_left_color" to field13,
        "border_left_width" to field10,
        "border_radius" to field14,
        "border_right_color" to field13,
        "border_right_width" to field10,
        "border_style" to field15,
        "border_top_color" to field13,
        "border_top_left_radius" to field14,
        "border_top_right_radius" to field14,
        "border_top_width" to field10,
        "border_width" to field10,
        "bottom" to field16,
        "color" to field11,
        "column_gap" to field10,
        "direction" to field18,
        "display" to field19,
        "elevation" to field14,
        "end" to field16,
        "flex" to field10,
        "flex_basis" to field16,
        "flex_direction" to field20,
        "flex_grow" to field10,
        "flex_shrink" to field10,
        "flex_wrap" to field21,
        "font_family" to field22,
        "font_size" to field10,
        "font_weight" to field23,
        "gap" to field10,
        "gestures" to field24,
        "height" to field16,
        "intensity" to field46,
        "italic" to field12,
        "justify_content" to field25,
        "left" to field16,
        "letter_spacing" to field10,
        "line_height" to field10,
        "margin" to field26,
        "margin_bottom" to field27,
        "margin_end" to field27,
        "margin_horizontal" to field27,
        "margin_left" to field27,
        "margin_right" to field27,
        "margin_start" to field27,
        "margin_top" to field27,
        "margin_vertical" to field27,
        "max_height" to field16,
        "max_lines" to field28,
        "max_width" to field16,
        "min_height" to field16,
        "min_width" to field16,
        "on_layout" to field29,
        "opacity" to field30,
        "overflow" to field31,
        "padding" to field32,
        "padding_bottom" to field16,
        "padding_end" to field16,
        "padding_horizontal" to field16,
        "padding_left" to field16,
        "padding_right" to field16,
        "padding_start" to field16,
        "padding_top" to field16,
        "padding_vertical" to field16,
        "placeholder_color" to field13,
        "pointer_events" to field33,
        "position" to field34,
        "ref" to field35,
        "right" to field16,
        "row_gap" to field10,
        "shadow_color" to field13,
        "shadow_offset" to field36,
        "shadow_opacity" to field14,
        "shadow_radius" to field14,
        "spacing" to field10,
        "start" to field16,
        "test_id" to field43,
        "text_align" to field38,
        "text_decoration" to field39,
        "text_shadow_color" to field13,
        "text_shadow_offset" to field36,
        "text_shadow_radius" to field14,
        "text_transform" to field40,
        "tint_color" to field13,
        "top" to field16,
        "transform" to field41,
        "width" to field16,
        "z_index" to field42
    )
    private fun match62(value: Any): Boolean {
        if (value !is JSONObject) return false
        if (!value.has("name")) return false
        for (key in value.keys()) {
            val item = value.get(key)
            val valid = when (key) {
                "label" -> match3(item)
                "name" -> match3(item)
                else -> false
            }
            if (!valid) return false
        }
        return true
    }
    private fun match61(value: Any): Boolean {
        if (value !is JSONArray) return false
        return (0 until value.length()).all { match62(value.get(it)) }
    }
    private fun match60(value: Any): Boolean {
        return match61(value) || match14(value)
    }
    private fun match64(value: Any): Boolean {
        return (value == "none") || (value == "polite") || (value == "assertive")
    }
    private fun match63(value: Any): Boolean {
        return match64(value) || match14(value)
    }
    private fun match68(value: Any): Boolean {
        return (value == "mixed")
    }
    private fun match67(value: Any): Boolean {
        return match5(value) || match68(value)
    }
    private fun match66(value: Any): Boolean {
        if (value !is JSONObject) return false
        for (key in value.keys()) {
            val item = value.get(key)
            val valid = when (key) {
                "busy" -> match5(item)
                "checked" -> match67(item)
                "disabled" -> match5(item)
                "expanded" -> match5(item)
                "selected" -> match5(item)
                else -> false
            }
            if (!valid) return false
        }
        return true
    }
    private fun match65(value: Any): Boolean {
        return match66(value) || match14(value)
    }
    private fun match70(value: Any): Boolean {
        if (value !is JSONObject) return false
        for (key in value.keys()) {
            val item = value.get(key)
            val valid = when (key) {
                "max" -> match8(item)
                "min" -> match8(item)
                "now" -> match8(item)
                "text" -> match3(item)
                else -> false
            }
            if (!valid) return false
        }
        return true
    }
    private fun match69(value: Any): Boolean {
        return match3(value) || match70(value) || match14(value)
    }
    private fun match72(value: Any): Boolean {
        return (value == "auto") || (value == "yes") || (value == "no") || (value == "no_hide_descendants")
    }
    private fun match71(value: Any): Boolean {
        return match72(value) || match14(value)
    }
    private fun match73(value: Any): Boolean {
        return match27(value) || match14(value)
    }
    private fun match74(value: Any): Boolean {
        return match27(value) || match14(value)
    }
    private fun component2(): Map<String, Field> = mapOf(
        "_pn_animated_events" to field0,
        "_pn_edit_revision" to field1,
        "_pn_events" to field2,
        "_pn_header_slot" to field3,
        "_pn_layout" to field4,
        "_pn_list_key" to field5,
        "accessibility_actions" to field47,
        "accessibility_hint" to field43,
        "accessibility_label" to field43,
        "accessibility_live_region" to field48,
        "accessibility_role" to field43,
        "accessibility_state" to field49,
        "accessibility_value" to field50,
        "accessible" to field44,
        "align_content" to field7,
        "align_items" to field8,
        "align_self" to field8,
        "aspect_ratio" to field10,
        "background_color" to field11,
        "bold" to field12,
        "border_bottom_color" to field13,
        "border_bottom_left_radius" to field14,
        "border_bottom_right_radius" to field14,
        "border_bottom_width" to field10,
        "border_color" to field13,
        "border_left_color" to field13,
        "border_left_width" to field10,
        "border_radius" to field14,
        "border_right_color" to field13,
        "border_right_width" to field10,
        "border_style" to field15,
        "border_top_color" to field13,
        "border_top_left_radius" to field14,
        "border_top_right_radius" to field14,
        "border_top_width" to field10,
        "border_width" to field10,
        "bottom" to field16,
        "color" to field11,
        "column_gap" to field10,
        "direction" to field18,
        "disabled" to field51,
        "display" to field19,
        "elevation" to field14,
        "end" to field16,
        "flex" to field10,
        "flex_basis" to field16,
        "flex_direction" to field20,
        "flex_grow" to field10,
        "flex_shrink" to field10,
        "flex_wrap" to field21,
        "font_family" to field22,
        "font_size" to field10,
        "font_weight" to field23,
        "gap" to field10,
        "gestures" to field24,
        "height" to field16,
        "important_for_accessibility" to field52,
        "italic" to field12,
        "justify_content" to field25,
        "left" to field16,
        "letter_spacing" to field10,
        "line_height" to field10,
        "margin" to field26,
        "margin_bottom" to field27,
        "margin_end" to field27,
        "margin_horizontal" to field27,
        "margin_left" to field27,
        "margin_right" to field27,
        "margin_start" to field27,
        "margin_top" to field27,
        "margin_vertical" to field27,
        "max_height" to field16,
        "max_lines" to field28,
        "max_width" to field16,
        "min_height" to field16,
        "min_width" to field16,
        "on_accessibility_action" to field53,
        "on_layout" to field29,
        "on_press" to field54,
        "opacity" to field30,
        "overflow" to field31,
        "padding" to field32,
        "padding_bottom" to field16,
        "padding_end" to field16,
        "padding_horizontal" to field16,
        "padding_left" to field16,
        "padding_right" to field16,
        "padding_start" to field16,
        "padding_top" to field16,
        "padding_vertical" to field16,
        "placeholder_color" to field13,
        "pointer_events" to field33,
        "position" to field34,
        "ref" to field35,
        "right" to field16,
        "row_gap" to field10,
        "shadow_color" to field13,
        "shadow_offset" to field36,
        "shadow_opacity" to field14,
        "shadow_radius" to field14,
        "spacing" to field10,
        "start" to field16,
        "test_id" to field43,
        "text_align" to field38,
        "text_decoration" to field39,
        "text_shadow_color" to field13,
        "text_shadow_offset" to field36,
        "text_shadow_radius" to field14,
        "text_transform" to field40,
        "tint_color" to field13,
        "title" to field55,
        "top" to field16,
        "transform" to field41,
        "width" to field16,
        "z_index" to field42
    )
    private fun match75(value: Any): Boolean {
        return match27(value) || match14(value)
    }
    private fun component3(): Map<String, Field> = mapOf(
        "_pn_animated_events" to field0,
        "_pn_edit_revision" to field1,
        "_pn_events" to field2,
        "_pn_header_slot" to field3,
        "_pn_layout" to field4,
        "_pn_list_key" to field5,
        "accessibility_actions" to field47,
        "accessibility_hint" to field43,
        "accessibility_label" to field43,
        "accessibility_live_region" to field48,
        "accessibility_role" to field6,
        "accessibility_state" to field49,
        "accessibility_value" to field50,
        "accessible" to field44,
        "align_content" to field7,
        "align_items" to field8,
        "align_self" to field8,
        "aspect_ratio" to field10,
        "background_color" to field11,
        "bold" to field12,
        "border_bottom_color" to field13,
        "border_bottom_left_radius" to field14,
        "border_bottom_right_radius" to field14,
        "border_bottom_width" to field10,
        "border_color" to field13,
        "border_left_color" to field13,
        "border_left_width" to field10,
        "border_radius" to field14,
        "border_right_color" to field13,
        "border_right_width" to field10,
        "border_style" to field15,
        "border_top_color" to field13,
        "border_top_left_radius" to field14,
        "border_top_right_radius" to field14,
        "border_top_width" to field10,
        "border_width" to field10,
        "bottom" to field16,
        "color" to field17,
        "column_gap" to field10,
        "direction" to field18,
        "disabled" to field51,
        "display" to field19,
        "elevation" to field14,
        "end" to field16,
        "flex" to field10,
        "flex_basis" to field16,
        "flex_direction" to field20,
        "flex_grow" to field10,
        "flex_shrink" to field10,
        "flex_wrap" to field21,
        "font_family" to field22,
        "font_size" to field10,
        "font_weight" to field23,
        "gap" to field10,
        "gestures" to field24,
        "height" to field16,
        "important_for_accessibility" to field52,
        "italic" to field12,
        "justify_content" to field25,
        "label" to field43,
        "left" to field16,
        "letter_spacing" to field10,
        "line_height" to field10,
        "margin" to field26,
        "margin_bottom" to field27,
        "margin_end" to field27,
        "margin_horizontal" to field27,
        "margin_left" to field27,
        "margin_right" to field27,
        "margin_start" to field27,
        "margin_top" to field27,
        "margin_vertical" to field27,
        "max_height" to field16,
        "max_lines" to field28,
        "max_width" to field16,
        "min_height" to field16,
        "min_width" to field16,
        "on_accessibility_action" to field53,
        "on_change" to field56,
        "on_layout" to field29,
        "opacity" to field30,
        "overflow" to field31,
        "padding" to field32,
        "padding_bottom" to field16,
        "padding_end" to field16,
        "padding_horizontal" to field16,
        "padding_left" to field16,
        "padding_right" to field16,
        "padding_start" to field16,
        "padding_top" to field16,
        "padding_vertical" to field16,
        "placeholder_color" to field13,
        "pointer_events" to field33,
        "position" to field34,
        "ref" to field35,
        "right" to field16,
        "row_gap" to field10,
        "shadow_color" to field13,
        "shadow_offset" to field36,
        "shadow_opacity" to field14,
        "shadow_radius" to field14,
        "spacing" to field10,
        "start" to field16,
        "test_id" to field43,
        "text_align" to field38,
        "text_decoration" to field39,
        "text_shadow_color" to field13,
        "text_shadow_offset" to field36,
        "text_shadow_radius" to field14,
        "text_transform" to field40,
        "tint_color" to field13,
        "top" to field16,
        "transform" to field41,
        "value" to field57,
        "width" to field16,
        "z_index" to field42
    )
    private fun match77(value: Any): Boolean {
        if (value !is JSONObject) return false
        for (key in value.keys()) {
            val item = value.get(key)
            val valid = when (key) {
                else -> match8(item)
            }
            if (!valid) return false
        }
        return true
    }
    private fun match76(value: Any): Boolean {
        return match8(value) || match77(value) || match14(value)
    }
    private fun component4(): Map<String, Field> = mapOf(
        "_pn_animated_events" to field0,
        "_pn_edit_revision" to field1,
        "_pn_events" to field2,
        "_pn_header_slot" to field3,
        "_pn_layout" to field4,
        "_pn_list_key" to field5,
        "accessibility_actions" to field47,
        "accessibility_hint" to field43,
        "accessibility_label" to field43,
        "accessibility_live_region" to field48,
        "accessibility_role" to field43,
        "accessibility_state" to field49,
        "accessibility_value" to field50,
        "accessible" to field44,
        "align_content" to field7,
        "align_items" to field8,
        "align_self" to field8,
        "aspect_ratio" to field10,
        "background_color" to field11,
        "bold" to field12,
        "border_bottom_color" to field13,
        "border_bottom_left_radius" to field14,
        "border_bottom_right_radius" to field14,
        "border_bottom_width" to field10,
        "border_color" to field13,
        "border_left_color" to field13,
        "border_left_width" to field10,
        "border_radius" to field14,
        "border_right_color" to field13,
        "border_right_width" to field10,
        "border_style" to field15,
        "border_top_color" to field13,
        "border_top_left_radius" to field14,
        "border_top_right_radius" to field14,
        "border_top_width" to field10,
        "border_width" to field10,
        "bottom" to field16,
        "color" to field11,
        "column_gap" to field10,
        "direction" to field18,
        "display" to field19,
        "elevation" to field14,
        "end" to field16,
        "flex" to field10,
        "flex_basis" to field16,
        "flex_direction" to field20,
        "flex_grow" to field10,
        "flex_shrink" to field10,
        "flex_wrap" to field21,
        "font_family" to field22,
        "font_size" to field10,
        "font_weight" to field23,
        "gap" to field10,
        "gestures" to field24,
        "height" to field16,
        "hit_slop" to field58,
        "important_for_accessibility" to field52,
        "italic" to field12,
        "justify_content" to field25,
        "left" to field16,
        "letter_spacing" to field10,
        "line_height" to field10,
        "margin" to field26,
        "margin_bottom" to field27,
        "margin_end" to field27,
        "margin_horizontal" to field27,
        "margin_left" to field27,
        "margin_right" to field27,
        "margin_start" to field27,
        "margin_top" to field27,
        "margin_vertical" to field27,
        "max_height" to field16,
        "max_lines" to field28,
        "max_width" to field16,
        "min_height" to field16,
        "min_width" to field16,
        "on_accessibility_action" to field53,
        "on_layout" to field29,
        "opacity" to field30,
        "overflow" to field31,
        "padding" to field32,
        "padding_bottom" to field16,
        "padding_end" to field16,
        "padding_horizontal" to field16,
        "padding_left" to field16,
        "padding_right" to field16,
        "padding_start" to field16,
        "padding_top" to field16,
        "padding_vertical" to field16,
        "placeholder_color" to field13,
        "pointer_events" to field33,
        "position" to field34,
        "ref" to field35,
        "right" to field16,
        "row_gap" to field10,
        "shadow_color" to field13,
        "shadow_offset" to field36,
        "shadow_opacity" to field14,
        "shadow_radius" to field14,
        "spacing" to field10,
        "start" to field16,
        "test_id" to field43,
        "text_align" to field38,
        "text_decoration" to field39,
        "text_shadow_color" to field13,
        "text_shadow_offset" to field36,
        "text_shadow_radius" to field14,
        "text_transform" to field40,
        "tint_color" to field13,
        "top" to field16,
        "transform" to field41,
        "width" to field16,
        "z_index" to field42
    )
    private fun match78(value: Any): Boolean {
        return (value == "date") || (value == "time") || (value == "datetime")
    }
    private fun component5(): Map<String, Field> = mapOf(
        "_pn_animated_events" to field0,
        "_pn_edit_revision" to field1,
        "_pn_events" to field2,
        "_pn_header_slot" to field3,
        "_pn_layout" to field4,
        "_pn_list_key" to field5,
        "accessibility_actions" to field47,
        "accessibility_label" to field43,
        "accessibility_live_region" to field48,
        "accessibility_role" to field6,
        "accessibility_state" to field49,
        "accessibility_value" to field50,
        "accessible" to field44,
        "align_content" to field7,
        "align_items" to field8,
        "align_self" to field8,
        "aspect_ratio" to field10,
        "background_color" to field11,
        "bold" to field12,
        "border_bottom_color" to field13,
        "border_bottom_left_radius" to field14,
        "border_bottom_right_radius" to field14,
        "border_bottom_width" to field10,
        "border_color" to field13,
        "border_left_color" to field13,
        "border_left_width" to field10,
        "border_radius" to field14,
        "border_right_color" to field13,
        "border_right_width" to field10,
        "border_style" to field15,
        "border_top_color" to field13,
        "border_top_left_radius" to field14,
        "border_top_right_radius" to field14,
        "border_top_width" to field10,
        "border_width" to field10,
        "bottom" to field16,
        "color" to field11,
        "column_gap" to field10,
        "direction" to field18,
        "disabled" to field51,
        "display" to field19,
        "elevation" to field14,
        "end" to field16,
        "flex" to field10,
        "flex_basis" to field16,
        "flex_direction" to field20,
        "flex_grow" to field10,
        "flex_shrink" to field10,
        "flex_wrap" to field21,
        "font_family" to field22,
        "font_size" to field10,
        "font_weight" to field23,
        "gap" to field10,
        "gestures" to field24,
        "height" to field16,
        "important_for_accessibility" to field52,
        "italic" to field12,
        "justify_content" to field25,
        "left" to field16,
        "letter_spacing" to field10,
        "line_height" to field10,
        "margin" to field26,
        "margin_bottom" to field27,
        "margin_end" to field27,
        "margin_horizontal" to field27,
        "margin_left" to field27,
        "margin_right" to field27,
        "margin_start" to field27,
        "margin_top" to field27,
        "margin_vertical" to field27,
        "max_height" to field16,
        "max_lines" to field28,
        "max_width" to field16,
        "maximum" to field43,
        "min_height" to field16,
        "min_width" to field16,
        "minimum" to field43,
        "mode" to field59,
        "on_accessibility_action" to field53,
        "on_change" to field53,
        "on_layout" to field29,
        "opacity" to field30,
        "overflow" to field31,
        "padding" to field32,
        "padding_bottom" to field16,
        "padding_end" to field16,
        "padding_horizontal" to field16,
        "padding_left" to field16,
        "padding_right" to field16,
        "padding_start" to field16,
        "padding_top" to field16,
        "padding_vertical" to field16,
        "placeholder_color" to field13,
        "pointer_events" to field33,
        "position" to field34,
        "ref" to field35,
        "right" to field16,
        "row_gap" to field10,
        "shadow_color" to field13,
        "shadow_offset" to field36,
        "shadow_opacity" to field14,
        "shadow_radius" to field14,
        "spacing" to field10,
        "start" to field16,
        "test_id" to field43,
        "text_align" to field38,
        "text_decoration" to field39,
        "text_shadow_color" to field13,
        "text_shadow_offset" to field36,
        "text_shadow_radius" to field14,
        "text_transform" to field40,
        "tint_color" to field13,
        "top" to field16,
        "transform" to field41,
        "value" to field60,
        "width" to field16,
        "z_index" to field42
    )
    private fun match79(value: Any): Boolean {
        return match8(value) || match14(value)
    }
    private fun match81(value: Any): Boolean {
        if (value !is JSONObject) return false
        for (key in value.keys()) {
            val item = value.get(key)
            val valid = when (key) {
                else -> match3(item)
            }
            if (!valid) return false
        }
        return true
    }
    private fun match80(value: Any): Boolean {
        return match81(value) || match14(value)
    }
    private fun match82(value: Any): Boolean {
        return match27(value) || match14(value)
    }
    private fun match84(value: Any): Boolean {
        return (value == "cover") || (value == "contain") || (value == "stretch") || (value == "center")
    }
    private fun match83(value: Any): Boolean {
        return match84(value) || match14(value)
    }
    private fun component6(): Map<String, Field> = mapOf(
        "_pn_animated_events" to field0,
        "_pn_edit_revision" to field1,
        "_pn_events" to field2,
        "_pn_header_slot" to field3,
        "_pn_layout" to field4,
        "_pn_list_key" to field5,
        "accessibility_actions" to field47,
        "accessibility_label" to field43,
        "accessibility_live_region" to field48,
        "accessibility_role" to field43,
        "accessibility_state" to field49,
        "accessibility_value" to field50,
        "accessible" to field44,
        "align_content" to field7,
        "align_items" to field8,
        "align_self" to field8,
        "aspect_ratio" to field10,
        "background_color" to field11,
        "blur_radius" to field61,
        "bold" to field12,
        "border_bottom_color" to field13,
        "border_bottom_left_radius" to field14,
        "border_bottom_right_radius" to field14,
        "border_bottom_width" to field10,
        "border_color" to field13,
        "border_left_color" to field13,
        "border_left_width" to field10,
        "border_radius" to field14,
        "border_right_color" to field13,
        "border_right_width" to field10,
        "border_style" to field15,
        "border_top_color" to field13,
        "border_top_left_radius" to field14,
        "border_top_right_radius" to field14,
        "border_top_width" to field10,
        "border_width" to field10,
        "bottom" to field16,
        "color" to field11,
        "column_gap" to field10,
        "default_source" to field43,
        "direction" to field18,
        "display" to field19,
        "elevation" to field14,
        "end" to field16,
        "fade_duration" to field61,
        "flex" to field10,
        "flex_basis" to field16,
        "flex_direction" to field20,
        "flex_grow" to field10,
        "flex_shrink" to field10,
        "flex_wrap" to field21,
        "font_family" to field22,
        "font_size" to field10,
        "font_weight" to field23,
        "gap" to field10,
        "gestures" to field24,
        "headers" to field62,
        "height" to field16,
        "important_for_accessibility" to field52,
        "italic" to field12,
        "justify_content" to field25,
        "left" to field16,
        "letter_spacing" to field10,
        "line_height" to field10,
        "margin" to field26,
        "margin_bottom" to field27,
        "margin_end" to field27,
        "margin_horizontal" to field27,
        "margin_left" to field27,
        "margin_right" to field27,
        "margin_start" to field27,
        "margin_top" to field27,
        "margin_vertical" to field27,
        "max_height" to field16,
        "max_lines" to field28,
        "max_width" to field16,
        "min_height" to field16,
        "min_width" to field16,
        "on_accessibility_action" to field53,
        "on_error" to field53,
        "on_layout" to field29,
        "on_load" to field63,
        "on_load_end" to field54,
        "on_load_start" to field54,
        "opacity" to field30,
        "overflow" to field31,
        "padding" to field32,
        "padding_bottom" to field16,
        "padding_end" to field16,
        "padding_horizontal" to field16,
        "padding_left" to field16,
        "padding_right" to field16,
        "padding_start" to field16,
        "padding_top" to field16,
        "padding_vertical" to field16,
        "placeholder_color" to field64,
        "pointer_events" to field33,
        "position" to field34,
        "ref" to field35,
        "right" to field16,
        "row_gap" to field10,
        "scale_type" to field65,
        "shadow_color" to field13,
        "shadow_offset" to field36,
        "shadow_opacity" to field14,
        "shadow_radius" to field14,
        "source" to field55,
        "spacing" to field10,
        "start" to field16,
        "test_id" to field43,
        "text_align" to field38,
        "text_decoration" to field39,
        "text_shadow_color" to field13,
        "text_shadow_offset" to field36,
        "text_shadow_radius" to field14,
        "text_transform" to field40,
        "tint_color" to field64,
        "top" to field16,
        "transform" to field41,
        "width" to field16,
        "z_index" to field42
    )
    private fun component7(): Map<String, Field> = mapOf(
        "_pn_animated_events" to field0,
        "_pn_edit_revision" to field1,
        "_pn_events" to field2,
        "_pn_header_slot" to field3,
        "_pn_layout" to field4,
        "_pn_list_key" to field5,
        "accessibility_actions" to field47,
        "accessibility_label" to field43,
        "accessibility_live_region" to field48,
        "accessibility_role" to field6,
        "accessibility_state" to field49,
        "accessibility_value" to field50,
        "accessible" to field44,
        "align_content" to field7,
        "align_items" to field8,
        "align_self" to field8,
        "aspect_ratio" to field10,
        "background_color" to field11,
        "bold" to field12,
        "border_bottom_color" to field13,
        "border_bottom_left_radius" to field14,
        "border_bottom_right_radius" to field14,
        "border_bottom_width" to field10,
        "border_color" to field13,
        "border_left_color" to field13,
        "border_left_width" to field10,
        "border_radius" to field14,
        "border_right_color" to field13,
        "border_right_width" to field10,
        "border_style" to field15,
        "border_top_color" to field13,
        "border_top_left_radius" to field14,
        "border_top_right_radius" to field14,
        "border_top_width" to field10,
        "border_width" to field10,
        "bottom" to field16,
        "color" to field11,
        "column_gap" to field10,
        "direction" to field18,
        "display" to field19,
        "elevation" to field14,
        "end" to field16,
        "flex" to field10,
        "flex_basis" to field16,
        "flex_direction" to field20,
        "flex_grow" to field10,
        "flex_shrink" to field10,
        "flex_wrap" to field21,
        "font_family" to field22,
        "font_size" to field10,
        "font_weight" to field23,
        "gap" to field10,
        "gestures" to field24,
        "height" to field16,
        "important_for_accessibility" to field52,
        "italic" to field12,
        "justify_content" to field25,
        "left" to field16,
        "letter_spacing" to field10,
        "line_height" to field10,
        "margin" to field26,
        "margin_bottom" to field27,
        "margin_end" to field27,
        "margin_horizontal" to field27,
        "margin_left" to field27,
        "margin_right" to field27,
        "margin_start" to field27,
        "margin_top" to field27,
        "margin_vertical" to field27,
        "max_height" to field16,
        "max_lines" to field28,
        "max_width" to field16,
        "min_height" to field16,
        "min_width" to field16,
        "on_accessibility_action" to field53,
        "on_layout" to field29,
        "opacity" to field30,
        "overflow" to field31,
        "padding" to field32,
        "padding_bottom" to field16,
        "padding_end" to field16,
        "padding_horizontal" to field16,
        "padding_left" to field16,
        "padding_right" to field16,
        "padding_start" to field16,
        "padding_top" to field16,
        "padding_vertical" to field16,
        "placeholder_color" to field13,
        "pointer_events" to field33,
        "position" to field34,
        "ref" to field35,
        "right" to field16,
        "row_gap" to field10,
        "scale_type" to field65,
        "shadow_color" to field13,
        "shadow_offset" to field36,
        "shadow_opacity" to field14,
        "shadow_radius" to field14,
        "source" to field55,
        "spacing" to field10,
        "start" to field16,
        "test_id" to field43,
        "text_align" to field38,
        "text_decoration" to field39,
        "text_shadow_color" to field13,
        "text_shadow_offset" to field36,
        "text_shadow_radius" to field14,
        "text_transform" to field40,
        "tint_color" to field13,
        "top" to field16,
        "transform" to field41,
        "width" to field16,
        "z_index" to field42
    )
    private fun match85(value: Any): Boolean {
        return (value == "padding") || (value == "position") || (value == "height")
    }
    private fun component8(): Map<String, Field> = mapOf(
        "_pn_animated_events" to field0,
        "_pn_edit_revision" to field1,
        "_pn_events" to field2,
        "_pn_header_slot" to field3,
        "_pn_layout" to field4,
        "_pn_list_key" to field5,
        "accessibility_role" to field6,
        "align_content" to field7,
        "align_items" to field8,
        "align_self" to field8,
        "aspect_ratio" to field10,
        "background_color" to field11,
        "behavior" to field66,
        "bold" to field12,
        "border_bottom_color" to field13,
        "border_bottom_left_radius" to field14,
        "border_bottom_right_radius" to field14,
        "border_bottom_width" to field10,
        "border_color" to field13,
        "border_left_color" to field13,
        "border_left_width" to field10,
        "border_radius" to field14,
        "border_right_color" to field13,
        "border_right_width" to field10,
        "border_style" to field15,
        "border_top_color" to field13,
        "border_top_left_radius" to field14,
        "border_top_right_radius" to field14,
        "border_top_width" to field10,
        "border_width" to field10,
        "bottom" to field16,
        "color" to field11,
        "column_gap" to field10,
        "direction" to field18,
        "display" to field19,
        "elevation" to field14,
        "end" to field16,
        "flex" to field10,
        "flex_basis" to field16,
        "flex_direction" to field20,
        "flex_grow" to field10,
        "flex_shrink" to field10,
        "flex_wrap" to field21,
        "font_family" to field22,
        "font_size" to field10,
        "font_weight" to field23,
        "gap" to field10,
        "gestures" to field24,
        "height" to field16,
        "italic" to field12,
        "justify_content" to field25,
        "keyboard_vertical_offset" to field67,
        "left" to field16,
        "letter_spacing" to field10,
        "line_height" to field10,
        "margin" to field26,
        "margin_bottom" to field27,
        "margin_end" to field27,
        "margin_horizontal" to field27,
        "margin_left" to field27,
        "margin_right" to field27,
        "margin_start" to field27,
        "margin_top" to field27,
        "margin_vertical" to field27,
        "max_height" to field16,
        "max_lines" to field28,
        "max_width" to field16,
        "min_height" to field16,
        "min_width" to field16,
        "on_layout" to field29,
        "opacity" to field30,
        "overflow" to field31,
        "padding" to field32,
        "padding_bottom" to field16,
        "padding_end" to field16,
        "padding_horizontal" to field16,
        "padding_left" to field16,
        "padding_right" to field16,
        "padding_start" to field16,
        "padding_top" to field16,
        "padding_vertical" to field16,
        "placeholder_color" to field13,
        "pointer_events" to field33,
        "position" to field34,
        "ref" to field35,
        "right" to field16,
        "row_gap" to field10,
        "shadow_color" to field13,
        "shadow_offset" to field36,
        "shadow_opacity" to field14,
        "shadow_radius" to field14,
        "spacing" to field10,
        "start" to field16,
        "text_align" to field38,
        "text_decoration" to field39,
        "text_shadow_color" to field13,
        "text_shadow_offset" to field36,
        "text_shadow_radius" to field14,
        "text_transform" to field40,
        "tint_color" to field13,
        "top" to field16,
        "transform" to field41,
        "width" to field16,
        "z_index" to field42
    )
    private fun match86(value: Any): Boolean {
        if (value !is JSONArray) return false
        return (0 until value.length()).all { match9(value.get(it)) }
    }
    private fun match87(value: Any): Boolean {
        return match35(value) || match14(value)
    }
    private fun component9(): Map<String, Field> = mapOf(
        "_pn_animated_events" to field0,
        "_pn_edit_revision" to field1,
        "_pn_events" to field2,
        "_pn_header_slot" to field3,
        "_pn_layout" to field4,
        "_pn_list_key" to field5,
        "accessibility_label" to field43,
        "accessibility_role" to field6,
        "accessible" to field44,
        "align_content" to field7,
        "align_items" to field8,
        "align_self" to field8,
        "aspect_ratio" to field10,
        "background_color" to field11,
        "bold" to field12,
        "border_bottom_color" to field13,
        "border_bottom_left_radius" to field14,
        "border_bottom_right_radius" to field14,
        "border_bottom_width" to field10,
        "border_color" to field13,
        "border_left_color" to field13,
        "border_left_width" to field10,
        "border_radius" to field14,
        "border_right_color" to field13,
        "border_right_width" to field10,
        "border_style" to field15,
        "border_top_color" to field13,
        "border_top_left_radius" to field14,
        "border_top_right_radius" to field14,
        "border_top_width" to field10,
        "border_width" to field10,
        "bottom" to field16,
        "color" to field11,
        "colors" to field68,
        "column_gap" to field10,
        "direction" to field18,
        "display" to field19,
        "elevation" to field14,
        "end" to field16,
        "end_point" to field69,
        "flex" to field10,
        "flex_basis" to field16,
        "flex_direction" to field20,
        "flex_grow" to field10,
        "flex_shrink" to field10,
        "flex_wrap" to field21,
        "font_family" to field22,
        "font_size" to field10,
        "font_weight" to field23,
        "gap" to field10,
        "gestures" to field24,
        "height" to field16,
        "italic" to field12,
        "justify_content" to field25,
        "left" to field16,
        "letter_spacing" to field10,
        "line_height" to field10,
        "locations" to field70,
        "margin" to field26,
        "margin_bottom" to field27,
        "margin_end" to field27,
        "margin_horizontal" to field27,
        "margin_left" to field27,
        "margin_right" to field27,
        "margin_start" to field27,
        "margin_top" to field27,
        "margin_vertical" to field27,
        "max_height" to field16,
        "max_lines" to field28,
        "max_width" to field16,
        "min_height" to field16,
        "min_width" to field16,
        "on_layout" to field29,
        "opacity" to field30,
        "overflow" to field31,
        "padding" to field32,
        "padding_bottom" to field16,
        "padding_end" to field16,
        "padding_horizontal" to field16,
        "padding_left" to field16,
        "padding_right" to field16,
        "padding_start" to field16,
        "padding_top" to field16,
        "padding_vertical" to field16,
        "placeholder_color" to field13,
        "pointer_events" to field33,
        "position" to field34,
        "ref" to field35,
        "right" to field16,
        "row_gap" to field10,
        "shadow_color" to field13,
        "shadow_offset" to field36,
        "shadow_opacity" to field14,
        "shadow_radius" to field14,
        "spacing" to field10,
        "start" to field16,
        "start_point" to field71,
        "test_id" to field43,
        "text_align" to field38,
        "text_decoration" to field39,
        "text_shadow_color" to field13,
        "text_shadow_offset" to field36,
        "text_shadow_radius" to field14,
        "text_transform" to field40,
        "tint_color" to field13,
        "top" to field16,
        "transform" to field41,
        "width" to field16,
        "z_index" to field42
    )
    private fun match88(value: Any): Boolean {
        return (value == "slide") || (value == "fade") || (value == "none")
    }
    private fun match89(value: Any): Boolean {
        return (value == "page_sheet") || (value == "form_sheet") || (value == "full_screen") || (value == "overlay")
    }
    private fun component10(): Map<String, Field> = mapOf(
        "_pn_animated_events" to field0,
        "_pn_edit_revision" to field1,
        "_pn_events" to field2,
        "_pn_header_slot" to field3,
        "_pn_layout" to field4,
        "_pn_list_key" to field5,
        "accessibility_role" to field6,
        "align_content" to field7,
        "align_items" to field8,
        "align_self" to field8,
        "animation_type" to field72,
        "aspect_ratio" to field10,
        "background_color" to field11,
        "bold" to field12,
        "border_bottom_color" to field13,
        "border_bottom_left_radius" to field14,
        "border_bottom_right_radius" to field14,
        "border_bottom_width" to field10,
        "border_color" to field13,
        "border_left_color" to field13,
        "border_left_width" to field10,
        "border_radius" to field14,
        "border_right_color" to field13,
        "border_right_width" to field10,
        "border_style" to field15,
        "border_top_color" to field13,
        "border_top_left_radius" to field14,
        "border_top_right_radius" to field14,
        "border_top_width" to field10,
        "border_width" to field10,
        "bottom" to field16,
        "color" to field11,
        "column_gap" to field10,
        "direction" to field18,
        "dismiss_on_backdrop" to field9,
        "display" to field19,
        "elevation" to field14,
        "end" to field16,
        "flex" to field10,
        "flex_basis" to field16,
        "flex_direction" to field20,
        "flex_grow" to field10,
        "flex_shrink" to field10,
        "flex_wrap" to field21,
        "font_family" to field22,
        "font_size" to field10,
        "font_weight" to field23,
        "gap" to field10,
        "gestures" to field24,
        "height" to field16,
        "italic" to field12,
        "justify_content" to field25,
        "left" to field16,
        "letter_spacing" to field10,
        "line_height" to field10,
        "margin" to field26,
        "margin_bottom" to field27,
        "margin_end" to field27,
        "margin_horizontal" to field27,
        "margin_left" to field27,
        "margin_right" to field27,
        "margin_start" to field27,
        "margin_top" to field27,
        "margin_vertical" to field27,
        "max_height" to field16,
        "max_lines" to field28,
        "max_width" to field16,
        "min_height" to field16,
        "min_width" to field16,
        "on_dismiss" to field54,
        "on_layout" to field29,
        "on_request_close" to field54,
        "on_show" to field54,
        "opacity" to field30,
        "overflow" to field31,
        "padding" to field32,
        "padding_bottom" to field16,
        "padding_end" to field16,
        "padding_horizontal" to field16,
        "padding_left" to field16,
        "padding_right" to field16,
        "padding_start" to field16,
        "padding_top" to field16,
        "padding_vertical" to field16,
        "placeholder_color" to field13,
        "pointer_events" to field33,
        "position" to field34,
        "presentation_style" to field73,
        "ref" to field35,
        "right" to field16,
        "row_gap" to field10,
        "shadow_color" to field13,
        "shadow_offset" to field36,
        "shadow_opacity" to field14,
        "shadow_radius" to field14,
        "spacing" to field10,
        "start" to field16,
        "status_bar_translucent" to field51,
        "text_align" to field38,
        "text_decoration" to field39,
        "text_shadow_color" to field13,
        "text_shadow_offset" to field36,
        "text_shadow_radius" to field14,
        "text_transform" to field40,
        "tint_color" to field13,
        "title" to field60,
        "top" to field16,
        "transform" to field41,
        "transparent" to field51,
        "visible" to field51,
        "width" to field16,
        "z_index" to field42
    )
    private fun match91(value: Any): Boolean {
        if (value !is JSONArray) return false
        return (0 until value.length()).all { match53(value.get(it)) }
    }
    private fun match90(value: Any): Boolean {
        return match91(value) || match14(value)
    }
    private fun match92(value: Any): Boolean {
        return match27(value) || match14(value)
    }
    private fun component11(): Map<String, Field> = mapOf(
        "_pn_animated_events" to field0,
        "_pn_edit_revision" to field1,
        "_pn_events" to field2,
        "_pn_header_slot" to field3,
        "_pn_layout" to field4,
        "_pn_list_key" to field5,
        "accessibility_actions" to field47,
        "accessibility_hint" to field43,
        "accessibility_label" to field43,
        "accessibility_live_region" to field48,
        "accessibility_role" to field6,
        "accessibility_state" to field49,
        "accessibility_value" to field50,
        "accessible" to field44,
        "align_content" to field7,
        "align_items" to field8,
        "align_self" to field8,
        "aspect_ratio" to field10,
        "background_color" to field11,
        "bold" to field12,
        "border_bottom_color" to field13,
        "border_bottom_left_radius" to field14,
        "border_bottom_right_radius" to field14,
        "border_bottom_width" to field10,
        "border_color" to field13,
        "border_left_color" to field13,
        "border_left_width" to field10,
        "border_radius" to field14,
        "border_right_color" to field13,
        "border_right_width" to field10,
        "border_style" to field15,
        "border_top_color" to field13,
        "border_top_left_radius" to field14,
        "border_top_right_radius" to field14,
        "border_top_width" to field10,
        "border_width" to field10,
        "bottom" to field16,
        "color" to field11,
        "column_gap" to field10,
        "direction" to field18,
        "disabled" to field51,
        "display" to field19,
        "elevation" to field14,
        "end" to field16,
        "flex" to field10,
        "flex_basis" to field16,
        "flex_direction" to field20,
        "flex_grow" to field10,
        "flex_shrink" to field10,
        "flex_wrap" to field21,
        "font_family" to field22,
        "font_size" to field10,
        "font_weight" to field23,
        "gap" to field10,
        "gestures" to field24,
        "height" to field16,
        "important_for_accessibility" to field52,
        "italic" to field12,
        "items" to field74,
        "justify_content" to field25,
        "left" to field16,
        "letter_spacing" to field10,
        "line_height" to field10,
        "margin" to field26,
        "margin_bottom" to field27,
        "margin_end" to field27,
        "margin_horizontal" to field27,
        "margin_left" to field27,
        "margin_right" to field27,
        "margin_start" to field27,
        "margin_top" to field27,
        "margin_vertical" to field27,
        "max_height" to field16,
        "max_lines" to field28,
        "max_width" to field16,
        "min_height" to field16,
        "min_width" to field16,
        "on_accessibility_action" to field53,
        "on_change" to field75,
        "on_layout" to field29,
        "opacity" to field30,
        "overflow" to field31,
        "padding" to field32,
        "padding_bottom" to field16,
        "padding_end" to field16,
        "padding_horizontal" to field16,
        "padding_left" to field16,
        "padding_right" to field16,
        "padding_start" to field16,
        "padding_top" to field16,
        "padding_vertical" to field16,
        "placeholder" to field76,
        "placeholder_color" to field13,
        "pointer_events" to field33,
        "position" to field34,
        "ref" to field35,
        "right" to field16,
        "row_gap" to field10,
        "shadow_color" to field13,
        "shadow_offset" to field36,
        "shadow_opacity" to field14,
        "shadow_radius" to field14,
        "spacing" to field10,
        "start" to field16,
        "test_id" to field43,
        "text_align" to field38,
        "text_decoration" to field39,
        "text_shadow_color" to field13,
        "text_shadow_offset" to field36,
        "text_shadow_radius" to field14,
        "text_transform" to field40,
        "tint_color" to field13,
        "top" to field16,
        "transform" to field41,
        "value" to field77,
        "width" to field16,
        "z_index" to field42
    )
    private fun component12(): Map<String, Field> = mapOf(
        "_pn_animated_events" to field0,
        "_pn_edit_revision" to field1,
        "_pn_events" to field2,
        "_pn_header_slot" to field3,
        "_pn_layout" to field4,
        "_pn_list_key" to field5,
        "accessibility_role" to field6,
        "align_content" to field7,
        "align_items" to field8,
        "align_self" to field8,
        "aspect_ratio" to field10,
        "background_color" to field11,
        "bold" to field12,
        "border_bottom_color" to field13,
        "border_bottom_left_radius" to field14,
        "border_bottom_right_radius" to field14,
        "border_bottom_width" to field10,
        "border_color" to field13,
        "border_left_color" to field13,
        "border_left_width" to field10,
        "border_radius" to field14,
        "border_right_color" to field13,
        "border_right_width" to field10,
        "border_style" to field15,
        "border_top_color" to field13,
        "border_top_left_radius" to field14,
        "border_top_right_radius" to field14,
        "border_top_width" to field10,
        "border_width" to field10,
        "bottom" to field16,
        "color" to field11,
        "column_gap" to field10,
        "direction" to field18,
        "display" to field19,
        "elevation" to field14,
        "end" to field16,
        "flex" to field10,
        "flex_basis" to field16,
        "flex_direction" to field20,
        "flex_grow" to field10,
        "flex_shrink" to field10,
        "flex_wrap" to field21,
        "font_family" to field22,
        "font_size" to field10,
        "font_weight" to field23,
        "gap" to field10,
        "gestures" to field24,
        "height" to field16,
        "italic" to field12,
        "justify_content" to field25,
        "left" to field16,
        "letter_spacing" to field10,
        "line_height" to field10,
        "margin" to field26,
        "margin_bottom" to field27,
        "margin_end" to field27,
        "margin_horizontal" to field27,
        "margin_left" to field27,
        "margin_right" to field27,
        "margin_start" to field27,
        "margin_top" to field27,
        "margin_vertical" to field27,
        "max_height" to field16,
        "max_lines" to field28,
        "max_width" to field16,
        "min_height" to field16,
        "min_width" to field16,
        "on_layout" to field29,
        "opacity" to field30,
        "overflow" to field31,
        "padding" to field32,
        "padding_bottom" to field16,
        "padding_end" to field16,
        "padding_horizontal" to field16,
        "padding_left" to field16,
        "padding_right" to field16,
        "padding_start" to field16,
        "padding_top" to field16,
        "padding_vertical" to field16,
        "placeholder_color" to field13,
        "pointer_events" to field33,
        "position" to field34,
        "ref" to field35,
        "right" to field16,
        "row_gap" to field10,
        "shadow_color" to field13,
        "shadow_offset" to field36,
        "shadow_opacity" to field14,
        "shadow_radius" to field14,
        "spacing" to field10,
        "start" to field16,
        "text_align" to field38,
        "text_decoration" to field39,
        "text_shadow_color" to field13,
        "text_shadow_offset" to field36,
        "text_shadow_radius" to field14,
        "text_transform" to field40,
        "tint_color" to field13,
        "top" to field16,
        "transform" to field41,
        "width" to field16,
        "z_index" to field42
    )
    private fun match94(value: Any): Boolean {
        if (value !is JSONObject) return false
        if (!value.has("color")) return false
        for (key in value.keys()) {
            val item = value.get(key)
            val valid = when (key) {
                "borderless" -> match5(item)
                "color" -> match9(item)
                "foreground" -> match5(item)
                "radius" -> match79(item)
                else -> false
            }
            if (!valid) return false
        }
        return true
    }
    private fun match93(value: Any): Boolean {
        return match94(value) || match14(value)
    }
    private fun component13(): Map<String, Field> = mapOf(
        "_pn_animated_events" to field0,
        "_pn_edit_revision" to field1,
        "_pn_events" to field2,
        "_pn_header_slot" to field3,
        "_pn_layout" to field4,
        "_pn_list_key" to field5,
        "accessibility_actions" to field47,
        "accessibility_hint" to field43,
        "accessibility_label" to field43,
        "accessibility_live_region" to field48,
        "accessibility_role" to field43,
        "accessibility_state" to field49,
        "accessibility_value" to field50,
        "accessible" to field44,
        "align_content" to field7,
        "align_items" to field8,
        "align_self" to field8,
        "android_ripple" to field78,
        "aspect_ratio" to field10,
        "background_color" to field11,
        "bold" to field12,
        "border_bottom_color" to field13,
        "border_bottom_left_radius" to field14,
        "border_bottom_right_radius" to field14,
        "border_bottom_width" to field10,
        "border_color" to field13,
        "border_left_color" to field13,
        "border_left_width" to field10,
        "border_radius" to field14,
        "border_right_color" to field13,
        "border_right_width" to field10,
        "border_style" to field15,
        "border_top_color" to field13,
        "border_top_left_radius" to field14,
        "border_top_right_radius" to field14,
        "border_top_width" to field10,
        "border_width" to field10,
        "bottom" to field16,
        "color" to field11,
        "column_gap" to field10,
        "delay_long_press" to field79,
        "direction" to field18,
        "disabled" to field51,
        "display" to field19,
        "elevation" to field14,
        "end" to field16,
        "flex" to field10,
        "flex_basis" to field16,
        "flex_direction" to field20,
        "flex_grow" to field10,
        "flex_shrink" to field10,
        "flex_wrap" to field21,
        "font_family" to field22,
        "font_size" to field10,
        "font_weight" to field23,
        "gap" to field10,
        "gestures" to field24,
        "height" to field16,
        "hit_slop" to field58,
        "important_for_accessibility" to field52,
        "italic" to field12,
        "justify_content" to field25,
        "left" to field16,
        "letter_spacing" to field10,
        "line_height" to field10,
        "margin" to field26,
        "margin_bottom" to field27,
        "margin_end" to field27,
        "margin_horizontal" to field27,
        "margin_left" to field27,
        "margin_right" to field27,
        "margin_start" to field27,
        "margin_top" to field27,
        "margin_vertical" to field27,
        "max_height" to field16,
        "max_lines" to field28,
        "max_width" to field16,
        "min_height" to field16,
        "min_width" to field16,
        "on_accessibility_action" to field53,
        "on_layout" to field29,
        "on_long_press" to field54,
        "on_press" to field54,
        "on_press_in" to field54,
        "on_press_out" to field54,
        "opacity" to field30,
        "overflow" to field31,
        "padding" to field32,
        "padding_bottom" to field16,
        "padding_end" to field16,
        "padding_horizontal" to field16,
        "padding_left" to field16,
        "padding_right" to field16,
        "padding_start" to field16,
        "padding_top" to field16,
        "padding_vertical" to field16,
        "placeholder_color" to field13,
        "pointer_events" to field33,
        "position" to field34,
        "pressed_opacity" to field80,
        "ref" to field35,
        "right" to field16,
        "row_gap" to field10,
        "shadow_color" to field13,
        "shadow_offset" to field36,
        "shadow_opacity" to field14,
        "shadow_radius" to field14,
        "spacing" to field10,
        "start" to field16,
        "test_id" to field43,
        "text_align" to field38,
        "text_decoration" to field39,
        "text_shadow_color" to field13,
        "text_shadow_offset" to field36,
        "text_shadow_radius" to field14,
        "text_transform" to field40,
        "tint_color" to field13,
        "top" to field16,
        "transform" to field41,
        "width" to field16,
        "z_index" to field42
    )
    private fun component14(): Map<String, Field> = mapOf(
        "_pn_animated_events" to field0,
        "_pn_edit_revision" to field1,
        "_pn_events" to field2,
        "_pn_header_slot" to field3,
        "_pn_layout" to field4,
        "_pn_list_key" to field5,
        "accessibility_role" to field6,
        "align_content" to field7,
        "align_items" to field8,
        "align_self" to field8,
        "aspect_ratio" to field10,
        "background_color" to field11,
        "bold" to field12,
        "border_bottom_color" to field13,
        "border_bottom_left_radius" to field14,
        "border_bottom_right_radius" to field14,
        "border_bottom_width" to field10,
        "border_color" to field13,
        "border_left_color" to field13,
        "border_left_width" to field10,
        "border_radius" to field14,
        "border_right_color" to field13,
        "border_right_width" to field10,
        "border_style" to field15,
        "border_top_color" to field13,
        "border_top_left_radius" to field14,
        "border_top_right_radius" to field14,
        "border_top_width" to field10,
        "border_width" to field10,
        "bottom" to field16,
        "color" to field17,
        "column_gap" to field10,
        "direction" to field18,
        "display" to field19,
        "elevation" to field14,
        "end" to field16,
        "flex" to field10,
        "flex_basis" to field16,
        "flex_direction" to field20,
        "flex_grow" to field10,
        "flex_shrink" to field10,
        "flex_wrap" to field21,
        "font_family" to field22,
        "font_size" to field10,
        "font_weight" to field23,
        "gap" to field10,
        "gestures" to field24,
        "height" to field16,
        "indeterminate" to field81,
        "italic" to field12,
        "justify_content" to field25,
        "left" to field16,
        "letter_spacing" to field10,
        "line_height" to field10,
        "margin" to field26,
        "margin_bottom" to field27,
        "margin_end" to field27,
        "margin_horizontal" to field27,
        "margin_left" to field27,
        "margin_right" to field27,
        "margin_start" to field27,
        "margin_top" to field27,
        "margin_vertical" to field27,
        "max_height" to field16,
        "max_lines" to field28,
        "max_width" to field16,
        "min_height" to field16,
        "min_width" to field16,
        "on_layout" to field29,
        "opacity" to field30,
        "overflow" to field31,
        "padding" to field32,
        "padding_bottom" to field16,
        "padding_end" to field16,
        "padding_horizontal" to field16,
        "padding_left" to field16,
        "padding_right" to field16,
        "padding_start" to field16,
        "padding_top" to field16,
        "padding_vertical" to field16,
        "placeholder_color" to field13,
        "pointer_events" to field33,
        "position" to field34,
        "ref" to field35,
        "right" to field16,
        "row_gap" to field10,
        "shadow_color" to field13,
        "shadow_offset" to field36,
        "shadow_opacity" to field14,
        "shadow_radius" to field14,
        "spacing" to field10,
        "start" to field16,
        "text_align" to field38,
        "text_decoration" to field39,
        "text_shadow_color" to field13,
        "text_shadow_offset" to field36,
        "text_shadow_radius" to field14,
        "text_transform" to field40,
        "tint_color" to field13,
        "top" to field16,
        "track_color" to field64,
        "transform" to field41,
        "value" to field82,
        "width" to field16,
        "z_index" to field42
    )
    private fun component15(): Map<String, Field> = mapOf(
        "_pn_animated_events" to field0,
        "_pn_edit_revision" to field1,
        "_pn_events" to field2,
        "_pn_header_slot" to field3,
        "_pn_layout" to field4,
        "_pn_list_key" to field5,
        "accessibility_role" to field6,
        "align_content" to field7,
        "align_items" to field8,
        "align_self" to field8,
        "aspect_ratio" to field10,
        "background_color" to field11,
        "bold" to field12,
        "border_bottom_color" to field13,
        "border_bottom_left_radius" to field14,
        "border_bottom_right_radius" to field14,
        "border_bottom_width" to field10,
        "border_color" to field13,
        "border_left_color" to field13,
        "border_left_width" to field10,
        "border_radius" to field14,
        "border_right_color" to field13,
        "border_right_width" to field10,
        "border_style" to field15,
        "border_top_color" to field13,
        "border_top_left_radius" to field14,
        "border_top_right_radius" to field14,
        "border_top_width" to field10,
        "border_width" to field10,
        "bottom" to field16,
        "color" to field11,
        "column_gap" to field10,
        "direction" to field18,
        "display" to field19,
        "elevation" to field14,
        "end" to field16,
        "flex" to field10,
        "flex_basis" to field16,
        "flex_direction" to field20,
        "flex_grow" to field10,
        "flex_shrink" to field10,
        "flex_wrap" to field21,
        "font_family" to field22,
        "font_size" to field10,
        "font_weight" to field23,
        "gap" to field10,
        "gestures" to field24,
        "height" to field16,
        "italic" to field12,
        "justify_content" to field25,
        "left" to field16,
        "letter_spacing" to field10,
        "line_height" to field10,
        "margin" to field26,
        "margin_bottom" to field27,
        "margin_end" to field27,
        "margin_horizontal" to field27,
        "margin_left" to field27,
        "margin_right" to field27,
        "margin_start" to field27,
        "margin_top" to field27,
        "margin_vertical" to field27,
        "max_height" to field16,
        "max_lines" to field28,
        "max_width" to field16,
        "min_height" to field16,
        "min_width" to field16,
        "on_layout" to field29,
        "on_refresh" to field54,
        "opacity" to field30,
        "overflow" to field31,
        "padding" to field32,
        "padding_bottom" to field16,
        "padding_end" to field16,
        "padding_horizontal" to field16,
        "padding_left" to field16,
        "padding_right" to field16,
        "padding_start" to field16,
        "padding_top" to field16,
        "padding_vertical" to field16,
        "placeholder_color" to field13,
        "pointer_events" to field33,
        "position" to field34,
        "ref" to field35,
        "refreshing" to field51,
        "right" to field16,
        "row_gap" to field10,
        "shadow_color" to field13,
        "shadow_offset" to field36,
        "shadow_opacity" to field14,
        "shadow_radius" to field14,
        "spacing" to field10,
        "start" to field16,
        "text_align" to field38,
        "text_decoration" to field39,
        "text_shadow_color" to field13,
        "text_shadow_offset" to field36,
        "text_shadow_radius" to field14,
        "text_transform" to field40,
        "tint_color" to field64,
        "top" to field16,
        "transform" to field41,
        "width" to field16,
        "z_index" to field42
    )
    private fun component16(): Map<String, Field> = mapOf(
        "_pn_animated_events" to field0,
        "_pn_edit_revision" to field1,
        "_pn_events" to field2,
        "_pn_header_slot" to field3,
        "_pn_layout" to field4,
        "_pn_list_key" to field5,
        "accessibility_actions" to field47,
        "accessibility_hint" to field43,
        "accessibility_label" to field43,
        "accessibility_live_region" to field48,
        "accessibility_role" to field43,
        "accessibility_state" to field49,
        "accessibility_value" to field50,
        "accessible" to field44,
        "align_content" to field7,
        "align_items" to field8,
        "align_self" to field8,
        "aspect_ratio" to field10,
        "background_color" to field11,
        "bold" to field12,
        "border_bottom_color" to field13,
        "border_bottom_left_radius" to field14,
        "border_bottom_right_radius" to field14,
        "border_bottom_width" to field10,
        "border_color" to field13,
        "border_left_color" to field13,
        "border_left_width" to field10,
        "border_radius" to field14,
        "border_right_color" to field13,
        "border_right_width" to field10,
        "border_style" to field15,
        "border_top_color" to field13,
        "border_top_left_radius" to field14,
        "border_top_right_radius" to field14,
        "border_top_width" to field10,
        "border_width" to field10,
        "bottom" to field16,
        "color" to field11,
        "column_gap" to field10,
        "direction" to field18,
        "display" to field19,
        "elevation" to field14,
        "end" to field16,
        "flex" to field10,
        "flex_basis" to field16,
        "flex_direction" to field20,
        "flex_grow" to field10,
        "flex_shrink" to field10,
        "flex_wrap" to field21,
        "font_family" to field22,
        "font_size" to field10,
        "font_weight" to field23,
        "gap" to field10,
        "gestures" to field24,
        "height" to field16,
        "hit_slop" to field58,
        "important_for_accessibility" to field52,
        "italic" to field12,
        "justify_content" to field25,
        "left" to field16,
        "letter_spacing" to field10,
        "line_height" to field10,
        "margin" to field26,
        "margin_bottom" to field27,
        "margin_end" to field27,
        "margin_horizontal" to field27,
        "margin_left" to field27,
        "margin_right" to field27,
        "margin_start" to field27,
        "margin_top" to field27,
        "margin_vertical" to field27,
        "max_height" to field16,
        "max_lines" to field28,
        "max_width" to field16,
        "min_height" to field16,
        "min_width" to field16,
        "on_accessibility_action" to field53,
        "on_layout" to field29,
        "opacity" to field30,
        "overflow" to field31,
        "padding" to field32,
        "padding_bottom" to field16,
        "padding_end" to field16,
        "padding_horizontal" to field16,
        "padding_left" to field16,
        "padding_right" to field16,
        "padding_start" to field16,
        "padding_top" to field16,
        "padding_vertical" to field16,
        "placeholder_color" to field13,
        "pointer_events" to field33,
        "position" to field34,
        "ref" to field35,
        "right" to field16,
        "row_gap" to field10,
        "shadow_color" to field13,
        "shadow_offset" to field36,
        "shadow_opacity" to field14,
        "shadow_radius" to field14,
        "spacing" to field10,
        "start" to field16,
        "test_id" to field43,
        "text_align" to field38,
        "text_decoration" to field39,
        "text_shadow_color" to field13,
        "text_shadow_offset" to field36,
        "text_shadow_radius" to field14,
        "text_transform" to field40,
        "tint_color" to field13,
        "top" to field16,
        "transform" to field41,
        "width" to field16,
        "z_index" to field42
    )
    private fun match97(value: Any): Boolean {
        return (value == "top") || (value == "left") || (value == "bottom") || (value == "right")
    }
    private fun match96(value: Any): Boolean {
        if (value !is JSONArray) return false
        return (0 until value.length()).all { match97(value.get(it)) }
    }
    private fun match95(value: Any): Boolean {
        return match96(value) || match14(value)
    }
    private fun component17(): Map<String, Field> = mapOf(
        "_pn_animated_events" to field0,
        "_pn_edit_revision" to field1,
        "_pn_events" to field2,
        "_pn_header_slot" to field3,
        "_pn_layout" to field4,
        "_pn_list_key" to field5,
        "accessibility_role" to field6,
        "align_content" to field7,
        "align_items" to field8,
        "align_self" to field8,
        "aspect_ratio" to field10,
        "background_color" to field11,
        "bold" to field12,
        "border_bottom_color" to field13,
        "border_bottom_left_radius" to field14,
        "border_bottom_right_radius" to field14,
        "border_bottom_width" to field10,
        "border_color" to field13,
        "border_left_color" to field13,
        "border_left_width" to field10,
        "border_radius" to field14,
        "border_right_color" to field13,
        "border_right_width" to field10,
        "border_style" to field15,
        "border_top_color" to field13,
        "border_top_left_radius" to field14,
        "border_top_right_radius" to field14,
        "border_top_width" to field10,
        "border_width" to field10,
        "bottom" to field16,
        "color" to field11,
        "column_gap" to field10,
        "direction" to field18,
        "display" to field19,
        "edges" to field83,
        "elevation" to field14,
        "end" to field16,
        "flex" to field10,
        "flex_basis" to field16,
        "flex_direction" to field20,
        "flex_grow" to field10,
        "flex_shrink" to field10,
        "flex_wrap" to field21,
        "font_family" to field22,
        "font_size" to field10,
        "font_weight" to field23,
        "gap" to field10,
        "gestures" to field24,
        "height" to field16,
        "italic" to field12,
        "justify_content" to field25,
        "left" to field16,
        "letter_spacing" to field10,
        "line_height" to field10,
        "margin" to field26,
        "margin_bottom" to field27,
        "margin_end" to field27,
        "margin_horizontal" to field27,
        "margin_left" to field27,
        "margin_right" to field27,
        "margin_start" to field27,
        "margin_top" to field27,
        "margin_vertical" to field27,
        "max_height" to field16,
        "max_lines" to field28,
        "max_width" to field16,
        "min_height" to field16,
        "min_width" to field16,
        "on_layout" to field29,
        "opacity" to field30,
        "overflow" to field31,
        "padding" to field32,
        "padding_bottom" to field16,
        "padding_end" to field16,
        "padding_horizontal" to field16,
        "padding_left" to field16,
        "padding_right" to field16,
        "padding_start" to field16,
        "padding_top" to field16,
        "padding_vertical" to field16,
        "placeholder_color" to field13,
        "pointer_events" to field33,
        "position" to field34,
        "ref" to field35,
        "right" to field16,
        "row_gap" to field10,
        "shadow_color" to field13,
        "shadow_offset" to field36,
        "shadow_opacity" to field14,
        "shadow_radius" to field14,
        "spacing" to field10,
        "start" to field16,
        "text_align" to field38,
        "text_decoration" to field39,
        "text_shadow_color" to field13,
        "text_shadow_offset" to field36,
        "text_shadow_radius" to field14,
        "text_transform" to field40,
        "tint_color" to field13,
        "top" to field16,
        "transform" to field41,
        "width" to field16,
        "z_index" to field42
    )
    private fun match98(value: Any): Boolean {
        return (value == "default") || (value == "none") || (value == "fade") || (value == "slide_from_right") || (value == "slide_from_bottom")
    }
    private fun match99(value: Any): Boolean {
        return (value == "card") || (value == "modal") || (value == "full_screen_modal") || (value == "form_sheet") || (value == "transparent_modal")
    }
    private fun match100(value: Any): Boolean {
        return match3(value) || match1(value)
    }
    private fun component18(): Map<String, Field> = mapOf(
        "_pn_animated_events" to field0,
        "_pn_edit_revision" to field1,
        "_pn_events" to field2,
        "_pn_header_slot" to field3,
        "_pn_layout" to field4,
        "_pn_list_key" to field5,
        "accessibility_actions" to field47,
        "accessibility_hint" to field43,
        "accessibility_label" to field43,
        "accessibility_live_region" to field48,
        "accessibility_role" to field43,
        "accessibility_state" to field49,
        "accessibility_value" to field50,
        "accessible" to field44,
        "active" to field84,
        "align_content" to field7,
        "align_items" to field8,
        "align_self" to field8,
        "animation" to field85,
        "aspect_ratio" to field10,
        "background_color" to field11,
        "bold" to field12,
        "border_bottom_color" to field13,
        "border_bottom_left_radius" to field14,
        "border_bottom_right_radius" to field14,
        "border_bottom_width" to field10,
        "border_color" to field13,
        "border_left_color" to field13,
        "border_left_width" to field10,
        "border_radius" to field14,
        "border_right_color" to field13,
        "border_right_width" to field10,
        "border_style" to field15,
        "border_top_color" to field13,
        "border_top_left_radius" to field14,
        "border_top_right_radius" to field14,
        "border_top_width" to field10,
        "border_width" to field10,
        "bottom" to field16,
        "color" to field11,
        "column_gap" to field10,
        "direction" to field18,
        "display" to field19,
        "elevation" to field14,
        "end" to field16,
        "flex" to field10,
        "flex_basis" to field16,
        "flex_direction" to field20,
        "flex_grow" to field10,
        "flex_shrink" to field10,
        "flex_wrap" to field21,
        "font_family" to field22,
        "font_size" to field10,
        "font_weight" to field23,
        "gap" to field10,
        "gesture_enabled" to field84,
        "gestures" to field24,
        "guarded" to field84,
        "header_back_title" to field5,
        "header_back_visible" to field84,
        "header_large_title" to field84,
        "header_shown" to field84,
        "header_style" to field86,
        "header_tint_color" to field5,
        "header_title_style" to field86,
        "height" to field16,
        "hit_slop" to field58,
        "important_for_accessibility" to field52,
        "italic" to field12,
        "justify_content" to field25,
        "lazy" to field84,
        "left" to field16,
        "letter_spacing" to field10,
        "line_height" to field10,
        "margin" to field26,
        "margin_bottom" to field27,
        "margin_end" to field27,
        "margin_horizontal" to field27,
        "margin_left" to field27,
        "margin_right" to field27,
        "margin_start" to field27,
        "margin_top" to field27,
        "margin_vertical" to field27,
        "max_height" to field16,
        "max_lines" to field28,
        "max_width" to field16,
        "min_height" to field16,
        "min_width" to field16,
        "on_accessibility_action" to field53,
        "on_layout" to field29,
        "opacity" to field30,
        "options" to field0,
        "overflow" to field31,
        "padding" to field32,
        "padding_bottom" to field16,
        "padding_end" to field16,
        "padding_horizontal" to field16,
        "padding_left" to field16,
        "padding_right" to field16,
        "padding_start" to field16,
        "padding_top" to field16,
        "padding_vertical" to field16,
        "placeholder_color" to field13,
        "pointer_events" to field33,
        "position" to field34,
        "presentation" to field87,
        "ref" to field35,
        "right" to field16,
        "route_key" to field5,
        "row_gap" to field10,
        "shadow_color" to field13,
        "shadow_offset" to field36,
        "shadow_opacity" to field14,
        "shadow_radius" to field14,
        "spacing" to field10,
        "start" to field16,
        "tab_bar_badge" to field88,
        "tab_bar_label" to field5,
        "test_id" to field43,
        "text_align" to field38,
        "text_decoration" to field39,
        "text_shadow_color" to field13,
        "text_shadow_offset" to field36,
        "text_shadow_radius" to field14,
        "text_transform" to field40,
        "tint_color" to field13,
        "title" to field5,
        "top" to field16,
        "transform" to field41,
        "unmount_on_blur" to field84,
        "width" to field16,
        "z_index" to field42
    )
    private fun component19(): Map<String, Field> = mapOf(
        "_pn_animated_events" to field0,
        "_pn_edit_revision" to field1,
        "_pn_events" to field2,
        "_pn_header_slot" to field3,
        "_pn_layout" to field4,
        "_pn_list_key" to field5,
        "accessibility_actions" to field47,
        "accessibility_hint" to field43,
        "accessibility_label" to field43,
        "accessibility_live_region" to field48,
        "accessibility_role" to field43,
        "accessibility_state" to field49,
        "accessibility_value" to field50,
        "accessible" to field44,
        "align_content" to field7,
        "align_items" to field8,
        "align_self" to field8,
        "aspect_ratio" to field10,
        "background_color" to field11,
        "bold" to field12,
        "border_bottom_color" to field13,
        "border_bottom_left_radius" to field14,
        "border_bottom_right_radius" to field14,
        "border_bottom_width" to field10,
        "border_color" to field13,
        "border_left_color" to field13,
        "border_left_width" to field10,
        "border_radius" to field14,
        "border_right_color" to field13,
        "border_right_width" to field10,
        "border_style" to field15,
        "border_top_color" to field13,
        "border_top_left_radius" to field14,
        "border_top_right_radius" to field14,
        "border_top_width" to field10,
        "border_width" to field10,
        "bottom" to field16,
        "color" to field11,
        "column_gap" to field10,
        "direction" to field18,
        "display" to field19,
        "elevation" to field14,
        "end" to field16,
        "flex" to field10,
        "flex_basis" to field16,
        "flex_direction" to field20,
        "flex_grow" to field10,
        "flex_shrink" to field10,
        "flex_wrap" to field21,
        "font_family" to field22,
        "font_size" to field10,
        "font_weight" to field23,
        "gap" to field10,
        "gestures" to field24,
        "height" to field16,
        "hit_slop" to field58,
        "important_for_accessibility" to field52,
        "italic" to field12,
        "justify_content" to field25,
        "left" to field16,
        "letter_spacing" to field10,
        "line_height" to field10,
        "margin" to field26,
        "margin_bottom" to field27,
        "margin_end" to field27,
        "margin_horizontal" to field27,
        "margin_left" to field27,
        "margin_right" to field27,
        "margin_start" to field27,
        "margin_top" to field27,
        "margin_vertical" to field27,
        "max_height" to field16,
        "max_lines" to field28,
        "max_width" to field16,
        "min_height" to field16,
        "min_width" to field16,
        "on_accessibility_action" to field53,
        "on_layout" to field29,
        "on_native_back" to field89,
        "opacity" to field30,
        "overflow" to field31,
        "padding" to field32,
        "padding_bottom" to field16,
        "padding_end" to field16,
        "padding_horizontal" to field16,
        "padding_left" to field16,
        "padding_right" to field16,
        "padding_start" to field16,
        "padding_top" to field16,
        "padding_vertical" to field16,
        "placeholder_color" to field13,
        "pointer_events" to field33,
        "position" to field34,
        "ref" to field35,
        "right" to field16,
        "row_gap" to field10,
        "shadow_color" to field13,
        "shadow_offset" to field36,
        "shadow_opacity" to field14,
        "shadow_radius" to field14,
        "spacing" to field10,
        "start" to field16,
        "test_id" to field43,
        "text_align" to field38,
        "text_decoration" to field39,
        "text_shadow_color" to field13,
        "text_shadow_offset" to field36,
        "text_shadow_radius" to field14,
        "text_transform" to field40,
        "tint_color" to field13,
        "top" to field16,
        "transform" to field41,
        "width" to field16,
        "z_index" to field42
    )
    private fun match101(value: Any): Boolean {
        return match25(value) || match14(value)
    }
    private fun match103(value: Any): Boolean {
        return (value == "normal") || (value == "fast")
    }
    private fun match102(value: Any): Boolean {
        return match103(value) || match8(value)
    }
    private fun match105(value: Any): Boolean {
        return (value == "none") || (value == "on_drag") || (value == "interactive")
    }
    private fun match104(value: Any): Boolean {
        return match105(value) || match14(value)
    }
    private fun match106(value: Any): Boolean {
        return (value == "never") || (value == "always") || (value == "handled")
    }
    private fun match107(value: Any): Boolean {
        return match27(value) || match14(value)
    }
    private fun match108(value: Any): Boolean {
        if (value !is JSONObject) return false
        for (key in value.keys()) {
            val item = value.get(key)
            val valid = when (key) {
                "accessibility_role" -> match3(item)
                "align_content" -> match6(item)
                "align_items" -> match7(item)
                "align_self" -> match7(item)
                "aspect_ratio" -> match8(item)
                "background_color" -> match9(item)
                "bold" -> match5(item)
                "border_bottom_color" -> match9(item)
                "border_bottom_left_radius" -> match8(item)
                "border_bottom_right_radius" -> match8(item)
                "border_bottom_width" -> match8(item)
                "border_color" -> match9(item)
                "border_left_color" -> match9(item)
                "border_left_width" -> match8(item)
                "border_radius" -> match8(item)
                "border_right_color" -> match9(item)
                "border_right_width" -> match8(item)
                "border_style" -> match11(item)
                "border_top_color" -> match9(item)
                "border_top_left_radius" -> match8(item)
                "border_top_right_radius" -> match8(item)
                "border_top_width" -> match8(item)
                "border_width" -> match8(item)
                "bottom" -> match12(item)
                "color" -> match9(item)
                "column_gap" -> match8(item)
                "direction" -> match15(item)
                "display" -> match16(item)
                "elevation" -> match8(item)
                "end" -> match12(item)
                "flex" -> match8(item)
                "flex_basis" -> match12(item)
                "flex_direction" -> match17(item)
                "flex_grow" -> match8(item)
                "flex_shrink" -> match8(item)
                "flex_wrap" -> match18(item)
                "font_family" -> match3(item)
                "font_size" -> match8(item)
                "font_weight" -> match19(item)
                "gap" -> match8(item)
                "height" -> match12(item)
                "italic" -> match5(item)
                "justify_content" -> match22(item)
                "left" -> match12(item)
                "letter_spacing" -> match8(item)
                "line_height" -> match8(item)
                "margin" -> match23(item)
                "margin_bottom" -> match26(item)
                "margin_end" -> match26(item)
                "margin_horizontal" -> match26(item)
                "margin_left" -> match26(item)
                "margin_right" -> match26(item)
                "margin_start" -> match26(item)
                "margin_top" -> match26(item)
                "margin_vertical" -> match26(item)
                "max_height" -> match12(item)
                "max_lines" -> match1(item)
                "max_width" -> match12(item)
                "min_height" -> match12(item)
                "min_width" -> match12(item)
                "on_layout" -> match27(item)
                "on_refresh" -> match74(item)
                "opacity" -> match8(item)
                "overflow" -> match28(item)
                "padding" -> match29(item)
                "padding_bottom" -> match12(item)
                "padding_end" -> match12(item)
                "padding_horizontal" -> match12(item)
                "padding_left" -> match12(item)
                "padding_right" -> match12(item)
                "padding_start" -> match12(item)
                "padding_top" -> match12(item)
                "padding_vertical" -> match12(item)
                "placeholder_color" -> match9(item)
                "pointer_events" -> match30(item)
                "position" -> match31(item)
                "ref" -> match21(item)
                "refreshing" -> match5(item)
                "right" -> match12(item)
                "row_gap" -> match8(item)
                "shadow_color" -> match9(item)
                "shadow_offset" -> match32(item)
                "shadow_opacity" -> match8(item)
                "shadow_radius" -> match8(item)
                "spacing" -> match8(item)
                "start" -> match12(item)
                "text_align" -> match37(item)
                "text_decoration" -> match38(item)
                "text_shadow_color" -> match9(item)
                "text_shadow_offset" -> match32(item)
                "text_shadow_radius" -> match8(item)
                "text_transform" -> match39(item)
                "tint_color" -> match13(item)
                "top" -> match12(item)
                "transform" -> match40(item)
                "width" -> match12(item)
                "z_index" -> match1(item)
                else -> false
            }
            if (!valid) return false
        }
        return true
    }
    private fun match109(value: Any): Boolean {
        return (value == "start") || (value == "center") || (value == "end")
    }
    private fun component20(): Map<String, Field> = mapOf(
        "_pn_animated_events" to field0,
        "_pn_edit_revision" to field1,
        "_pn_events" to field2,
        "_pn_header_slot" to field3,
        "_pn_layout" to field4,
        "_pn_list_key" to field5,
        "accessibility_role" to field6,
        "align_content" to field7,
        "align_items" to field8,
        "align_self" to field8,
        "aspect_ratio" to field10,
        "background_color" to field11,
        "bold" to field12,
        "border_bottom_color" to field13,
        "border_bottom_left_radius" to field14,
        "border_bottom_right_radius" to field14,
        "border_bottom_width" to field10,
        "border_color" to field13,
        "border_left_color" to field13,
        "border_left_width" to field10,
        "border_radius" to field14,
        "border_right_color" to field13,
        "border_right_width" to field10,
        "border_style" to field15,
        "border_top_color" to field13,
        "border_top_left_radius" to field14,
        "border_top_right_radius" to field14,
        "border_top_width" to field10,
        "border_width" to field10,
        "bottom" to field16,
        "bounces" to field9,
        "color" to field11,
        "column_gap" to field10,
        "content_inset" to field90,
        "deceleration_rate" to field91,
        "direction" to field18,
        "display" to field19,
        "elevation" to field14,
        "end" to field16,
        "flex" to field10,
        "flex_basis" to field16,
        "flex_direction" to field20,
        "flex_grow" to field10,
        "flex_shrink" to field10,
        "flex_wrap" to field21,
        "font_family" to field22,
        "font_size" to field10,
        "font_weight" to field23,
        "gap" to field10,
        "gestures" to field24,
        "height" to field16,
        "horizontal" to field51,
        "italic" to field12,
        "justify_content" to field25,
        "keyboard_dismiss_mode" to field92,
        "keyboard_should_persist_taps" to field93,
        "left" to field16,
        "letter_spacing" to field10,
        "line_height" to field10,
        "margin" to field26,
        "margin_bottom" to field27,
        "margin_end" to field27,
        "margin_horizontal" to field27,
        "margin_left" to field27,
        "margin_right" to field27,
        "margin_start" to field27,
        "margin_top" to field27,
        "margin_vertical" to field27,
        "max_height" to field16,
        "max_lines" to field28,
        "max_width" to field16,
        "min_height" to field16,
        "min_width" to field16,
        "on_layout" to field29,
        "on_momentum_scroll_end" to field94,
        "on_scroll" to field94,
        "on_scroll_begin_drag" to field94,
        "on_scroll_end_drag" to field94,
        "opacity" to field30,
        "overflow" to field31,
        "padding" to field32,
        "padding_bottom" to field16,
        "padding_end" to field16,
        "padding_horizontal" to field16,
        "padding_left" to field16,
        "padding_right" to field16,
        "padding_start" to field16,
        "padding_top" to field16,
        "padding_vertical" to field16,
        "paging_enabled" to field51,
        "placeholder_color" to field13,
        "pointer_events" to field33,
        "position" to field34,
        "ref" to field35,
        "refresh_control" to field95,
        "right" to field16,
        "row_gap" to field10,
        "scroll_enabled" to field9,
        "scroll_event_throttle" to field96,
        "shadow_color" to field13,
        "shadow_offset" to field36,
        "shadow_opacity" to field14,
        "shadow_radius" to field14,
        "shows_scroll_indicator" to field9,
        "snap_to_alignment" to field97,
        "snap_to_interval" to field61,
        "spacing" to field10,
        "start" to field16,
        "text_align" to field38,
        "text_decoration" to field39,
        "text_shadow_color" to field13,
        "text_shadow_offset" to field36,
        "text_shadow_radius" to field14,
        "text_transform" to field40,
        "tint_color" to field13,
        "top" to field16,
        "transform" to field41,
        "width" to field16,
        "z_index" to field42
    )
    private fun match110(value: Any): Boolean {
        return match27(value) || match14(value)
    }
    private fun match111(value: Any): Boolean {
        return match2(value) || match14(value)
    }
    private fun component21(): Map<String, Field> = mapOf(
        "_pn_animated_events" to field0,
        "_pn_edit_revision" to field1,
        "_pn_events" to field2,
        "_pn_header_slot" to field3,
        "_pn_layout" to field4,
        "_pn_list_key" to field5,
        "accessibility_actions" to field47,
        "accessibility_label" to field43,
        "accessibility_live_region" to field48,
        "accessibility_role" to field6,
        "accessibility_state" to field49,
        "accessibility_value" to field50,
        "accessible" to field44,
        "align_content" to field7,
        "align_items" to field8,
        "align_self" to field8,
        "aspect_ratio" to field10,
        "background_color" to field11,
        "bold" to field12,
        "border_bottom_color" to field13,
        "border_bottom_left_radius" to field14,
        "border_bottom_right_radius" to field14,
        "border_bottom_width" to field10,
        "border_color" to field13,
        "border_left_color" to field13,
        "border_left_width" to field10,
        "border_radius" to field14,
        "border_right_color" to field13,
        "border_right_width" to field10,
        "border_style" to field15,
        "border_top_color" to field13,
        "border_top_left_radius" to field14,
        "border_top_right_radius" to field14,
        "border_top_width" to field10,
        "border_width" to field10,
        "bottom" to field16,
        "color" to field11,
        "column_gap" to field10,
        "direction" to field18,
        "disabled" to field51,
        "display" to field19,
        "elevation" to field14,
        "end" to field16,
        "flex" to field10,
        "flex_basis" to field16,
        "flex_direction" to field20,
        "flex_grow" to field10,
        "flex_shrink" to field10,
        "flex_wrap" to field21,
        "font_family" to field22,
        "font_size" to field10,
        "font_weight" to field23,
        "gap" to field10,
        "gestures" to field24,
        "height" to field16,
        "important_for_accessibility" to field52,
        "italic" to field12,
        "justify_content" to field25,
        "left" to field16,
        "letter_spacing" to field10,
        "line_height" to field10,
        "margin" to field26,
        "margin_bottom" to field27,
        "margin_end" to field27,
        "margin_horizontal" to field27,
        "margin_left" to field27,
        "margin_right" to field27,
        "margin_start" to field27,
        "margin_top" to field27,
        "margin_vertical" to field27,
        "max_height" to field16,
        "max_lines" to field28,
        "max_width" to field16,
        "min_height" to field16,
        "min_width" to field16,
        "on_accessibility_action" to field53,
        "on_change" to field98,
        "on_layout" to field29,
        "opacity" to field30,
        "overflow" to field31,
        "padding" to field32,
        "padding_bottom" to field16,
        "padding_end" to field16,
        "padding_horizontal" to field16,
        "padding_left" to field16,
        "padding_right" to field16,
        "padding_start" to field16,
        "padding_top" to field16,
        "padding_vertical" to field16,
        "placeholder_color" to field13,
        "pointer_events" to field33,
        "position" to field34,
        "ref" to field35,
        "right" to field16,
        "row_gap" to field10,
        "segments" to field99,
        "selected_index" to field100,
        "shadow_color" to field13,
        "shadow_offset" to field36,
        "shadow_opacity" to field14,
        "shadow_radius" to field14,
        "spacing" to field10,
        "start" to field16,
        "test_id" to field43,
        "text_align" to field38,
        "text_decoration" to field39,
        "text_shadow_color" to field13,
        "text_shadow_offset" to field36,
        "text_shadow_radius" to field14,
        "text_transform" to field40,
        "tint_color" to field64,
        "top" to field16,
        "transform" to field41,
        "width" to field16,
        "z_index" to field42
    )
    private fun match112(value: Any): Boolean {
        return match27(value) || match14(value)
    }
    private fun component22(): Map<String, Field> = mapOf(
        "_pn_animated_events" to field0,
        "_pn_edit_revision" to field1,
        "_pn_events" to field2,
        "_pn_header_slot" to field3,
        "_pn_layout" to field4,
        "_pn_list_key" to field5,
        "accessibility_label" to field43,
        "accessibility_role" to field6,
        "align_content" to field7,
        "align_items" to field8,
        "align_self" to field8,
        "aspect_ratio" to field10,
        "background_color" to field11,
        "bold" to field12,
        "border_bottom_color" to field13,
        "border_bottom_left_radius" to field14,
        "border_bottom_right_radius" to field14,
        "border_bottom_width" to field10,
        "border_color" to field13,
        "border_left_color" to field13,
        "border_left_width" to field10,
        "border_radius" to field14,
        "border_right_color" to field13,
        "border_right_width" to field10,
        "border_style" to field15,
        "border_top_color" to field13,
        "border_top_left_radius" to field14,
        "border_top_right_radius" to field14,
        "border_top_width" to field10,
        "border_width" to field10,
        "bottom" to field16,
        "color" to field11,
        "column_gap" to field10,
        "direction" to field18,
        "disabled" to field51,
        "display" to field19,
        "elevation" to field14,
        "end" to field16,
        "flex" to field10,
        "flex_basis" to field16,
        "flex_direction" to field20,
        "flex_grow" to field10,
        "flex_shrink" to field10,
        "flex_wrap" to field21,
        "font_family" to field22,
        "font_size" to field10,
        "font_weight" to field23,
        "gap" to field10,
        "gestures" to field24,
        "height" to field16,
        "italic" to field12,
        "justify_content" to field25,
        "left" to field16,
        "letter_spacing" to field10,
        "line_height" to field10,
        "margin" to field26,
        "margin_bottom" to field27,
        "margin_end" to field27,
        "margin_horizontal" to field27,
        "margin_left" to field27,
        "margin_right" to field27,
        "margin_start" to field27,
        "margin_top" to field27,
        "margin_vertical" to field27,
        "max_height" to field16,
        "max_lines" to field28,
        "max_value" to field101,
        "max_width" to field16,
        "maximum_track_color" to field64,
        "min_height" to field16,
        "min_value" to field67,
        "min_width" to field16,
        "minimum_track_color" to field64,
        "on_change" to field102,
        "on_layout" to field29,
        "on_sliding_complete" to field102,
        "on_sliding_start" to field102,
        "opacity" to field30,
        "overflow" to field31,
        "padding" to field32,
        "padding_bottom" to field16,
        "padding_end" to field16,
        "padding_horizontal" to field16,
        "padding_left" to field16,
        "padding_right" to field16,
        "padding_start" to field16,
        "padding_top" to field16,
        "padding_vertical" to field16,
        "placeholder_color" to field13,
        "pointer_events" to field33,
        "position" to field34,
        "ref" to field35,
        "right" to field16,
        "row_gap" to field10,
        "shadow_color" to field13,
        "shadow_offset" to field36,
        "shadow_opacity" to field14,
        "shadow_radius" to field14,
        "spacing" to field10,
        "start" to field16,
        "step" to field67,
        "text_align" to field38,
        "text_decoration" to field39,
        "text_shadow_color" to field13,
        "text_shadow_offset" to field36,
        "text_shadow_radius" to field14,
        "text_transform" to field40,
        "thumb_color" to field64,
        "tint_color" to field13,
        "top" to field16,
        "transform" to field41,
        "value" to field82,
        "width" to field16,
        "z_index" to field42
    )
    private fun component23(): Map<String, Field> = mapOf(
        "_pn_animated_events" to field0,
        "_pn_edit_revision" to field1,
        "_pn_events" to field2,
        "_pn_header_slot" to field3,
        "_pn_layout" to field4,
        "_pn_list_key" to field5,
        "accessibility_role" to field6,
        "align_content" to field7,
        "align_items" to field8,
        "align_self" to field8,
        "aspect_ratio" to field10,
        "background_color" to field11,
        "bold" to field12,
        "border_bottom_color" to field13,
        "border_bottom_left_radius" to field14,
        "border_bottom_right_radius" to field14,
        "border_bottom_width" to field10,
        "border_color" to field13,
        "border_left_color" to field13,
        "border_left_width" to field10,
        "border_radius" to field14,
        "border_right_color" to field13,
        "border_right_width" to field10,
        "border_style" to field15,
        "border_top_color" to field13,
        "border_top_left_radius" to field14,
        "border_top_right_radius" to field14,
        "border_top_width" to field10,
        "border_width" to field10,
        "bottom" to field16,
        "color" to field11,
        "column_gap" to field10,
        "direction" to field18,
        "display" to field19,
        "elevation" to field14,
        "end" to field16,
        "flex" to field103,
        "flex_basis" to field16,
        "flex_direction" to field20,
        "flex_grow" to field10,
        "flex_shrink" to field10,
        "flex_wrap" to field21,
        "font_family" to field22,
        "font_size" to field10,
        "font_weight" to field23,
        "gap" to field10,
        "gestures" to field24,
        "height" to field16,
        "italic" to field12,
        "justify_content" to field25,
        "left" to field16,
        "letter_spacing" to field10,
        "line_height" to field10,
        "margin" to field26,
        "margin_bottom" to field27,
        "margin_end" to field27,
        "margin_horizontal" to field27,
        "margin_left" to field27,
        "margin_right" to field27,
        "margin_start" to field27,
        "margin_top" to field27,
        "margin_vertical" to field27,
        "max_height" to field16,
        "max_lines" to field28,
        "max_width" to field16,
        "min_height" to field16,
        "min_width" to field16,
        "on_layout" to field29,
        "opacity" to field30,
        "overflow" to field31,
        "padding" to field32,
        "padding_bottom" to field16,
        "padding_end" to field16,
        "padding_horizontal" to field16,
        "padding_left" to field16,
        "padding_right" to field16,
        "padding_start" to field16,
        "padding_top" to field16,
        "padding_vertical" to field16,
        "placeholder_color" to field13,
        "pointer_events" to field33,
        "position" to field34,
        "ref" to field35,
        "right" to field16,
        "row_gap" to field10,
        "shadow_color" to field13,
        "shadow_offset" to field36,
        "shadow_opacity" to field14,
        "shadow_radius" to field14,
        "size" to field61,
        "spacing" to field10,
        "start" to field16,
        "text_align" to field38,
        "text_decoration" to field39,
        "text_shadow_color" to field13,
        "text_shadow_offset" to field36,
        "text_shadow_radius" to field14,
        "text_transform" to field40,
        "tint_color" to field13,
        "top" to field16,
        "transform" to field41,
        "width" to field16,
        "z_index" to field42
    )
    private fun match114(value: Any): Boolean {
        return (value == "light") || (value == "dark") || (value == "default")
    }
    private fun match113(value: Any): Boolean {
        return match114(value) || match14(value)
    }
    private fun component24(): Map<String, Field> = mapOf(
        "_pn_animated_events" to field0,
        "_pn_edit_revision" to field1,
        "_pn_events" to field2,
        "_pn_header_slot" to field3,
        "_pn_layout" to field4,
        "_pn_list_key" to field5,
        "accessibility_role" to field6,
        "align_content" to field7,
        "align_items" to field8,
        "align_self" to field8,
        "animated" to field51,
        "aspect_ratio" to field10,
        "background_color" to field17,
        "bar_style" to field104,
        "bold" to field12,
        "border_bottom_color" to field13,
        "border_bottom_left_radius" to field14,
        "border_bottom_right_radius" to field14,
        "border_bottom_width" to field10,
        "border_color" to field13,
        "border_left_color" to field13,
        "border_left_width" to field10,
        "border_radius" to field14,
        "border_right_color" to field13,
        "border_right_width" to field10,
        "border_style" to field15,
        "border_top_color" to field13,
        "border_top_left_radius" to field14,
        "border_top_right_radius" to field14,
        "border_top_width" to field10,
        "border_width" to field10,
        "bottom" to field16,
        "color" to field11,
        "column_gap" to field10,
        "direction" to field18,
        "display" to field19,
        "elevation" to field14,
        "end" to field16,
        "flex" to field10,
        "flex_basis" to field16,
        "flex_direction" to field20,
        "flex_grow" to field10,
        "flex_shrink" to field10,
        "flex_wrap" to field21,
        "font_family" to field22,
        "font_size" to field10,
        "font_weight" to field23,
        "gap" to field10,
        "gestures" to field24,
        "height" to field16,
        "hidden" to field44,
        "italic" to field12,
        "justify_content" to field25,
        "left" to field16,
        "letter_spacing" to field10,
        "line_height" to field10,
        "margin" to field26,
        "margin_bottom" to field27,
        "margin_end" to field27,
        "margin_horizontal" to field27,
        "margin_left" to field27,
        "margin_right" to field27,
        "margin_start" to field27,
        "margin_top" to field27,
        "margin_vertical" to field27,
        "max_height" to field16,
        "max_lines" to field28,
        "max_width" to field16,
        "min_height" to field16,
        "min_width" to field16,
        "on_layout" to field29,
        "opacity" to field30,
        "overflow" to field31,
        "padding" to field32,
        "padding_bottom" to field16,
        "padding_end" to field16,
        "padding_horizontal" to field16,
        "padding_left" to field16,
        "padding_right" to field16,
        "padding_start" to field16,
        "padding_top" to field16,
        "padding_vertical" to field16,
        "placeholder_color" to field13,
        "pointer_events" to field33,
        "position" to field34,
        "ref" to field35,
        "right" to field16,
        "row_gap" to field10,
        "shadow_color" to field13,
        "shadow_offset" to field36,
        "shadow_opacity" to field14,
        "shadow_radius" to field14,
        "spacing" to field10,
        "start" to field16,
        "text_align" to field38,
        "text_decoration" to field39,
        "text_shadow_color" to field13,
        "text_shadow_offset" to field36,
        "text_shadow_radius" to field14,
        "text_transform" to field40,
        "tint_color" to field13,
        "top" to field16,
        "transform" to field41,
        "translucent" to field51,
        "width" to field16,
        "z_index" to field42
    )
    private fun match116(value: Any): Boolean {
        return (value == "nonzero") || (value == "evenodd")
    }
    private fun match115(value: Any): Boolean {
        return match116(value) || match14(value)
    }
    private fun match117(value: Any): Boolean {
        return (value == "meet") || (value == "slice") || (value == "none")
    }
    private fun match121(value: Any): Boolean {
        return (value == "path") || (value == "circle") || (value == "ellipse") || (value == "rect") || (value == "line") || (value == "polyline") || (value == "polygon")
    }
    private fun match123(value: Any): Boolean {
        return (value == "butt") || (value == "round") || (value == "square")
    }
    private fun match122(value: Any): Boolean {
        return match123(value) || match14(value)
    }
    private fun match125(value: Any): Boolean {
        return (value == "miter") || (value == "round") || (value == "bevel")
    }
    private fun match124(value: Any): Boolean {
        return match125(value) || match14(value)
    }
    private fun match120(value: Any): Boolean {
        if (value !is JSONObject) return false
        if (!value.has("kind")) return false
        for (key in value.keys()) {
            val item = value.get(key)
            val valid = when (key) {
                "cx" -> match79(item)
                "cy" -> match79(item)
                "d" -> match57(item)
                "fill" -> match13(item)
                "fill_opacity" -> match79(item)
                "fill_rule" -> match115(item)
                "height" -> match79(item)
                "kind" -> match121(item)
                "opacity" -> match79(item)
                "points" -> match57(item)
                "r" -> match79(item)
                "rx" -> match79(item)
                "ry" -> match79(item)
                "stroke" -> match13(item)
                "stroke_dasharray" -> match87(item)
                "stroke_linecap" -> match122(item)
                "stroke_linejoin" -> match124(item)
                "stroke_opacity" -> match79(item)
                "stroke_width" -> match79(item)
                "transform" -> match57(item)
                "width" -> match79(item)
                "x" -> match79(item)
                "x1" -> match79(item)
                "x2" -> match79(item)
                "y" -> match79(item)
                "y1" -> match79(item)
                "y2" -> match79(item)
                else -> false
            }
            if (!valid) return false
        }
        return true
    }
    private fun match119(value: Any): Boolean {
        if (value !is JSONArray) return false
        return (0 until value.length()).all { match120(value.get(it)) }
    }
    private fun match118(value: Any): Boolean {
        return match119(value) || match14(value)
    }
    private fun component25(): Map<String, Field> = mapOf(
        "_pn_animated_events" to field0,
        "_pn_edit_revision" to field1,
        "_pn_events" to field2,
        "_pn_header_slot" to field3,
        "_pn_layout" to field4,
        "_pn_list_key" to field5,
        "accessibility_actions" to field47,
        "accessibility_label" to field43,
        "accessibility_role" to field43,
        "accessibility_state" to field49,
        "accessibility_value" to field50,
        "accessible" to field44,
        "align_content" to field7,
        "align_items" to field8,
        "align_self" to field8,
        "aspect_ratio" to field10,
        "background_color" to field11,
        "bold" to field12,
        "border_bottom_color" to field13,
        "border_bottom_left_radius" to field14,
        "border_bottom_right_radius" to field14,
        "border_bottom_width" to field10,
        "border_color" to field13,
        "border_left_color" to field13,
        "border_left_width" to field10,
        "border_radius" to field14,
        "border_right_color" to field13,
        "border_right_width" to field10,
        "border_style" to field15,
        "border_top_color" to field13,
        "border_top_left_radius" to field14,
        "border_top_right_radius" to field14,
        "border_top_width" to field10,
        "border_width" to field10,
        "bottom" to field16,
        "color" to field11,
        "column_gap" to field10,
        "direction" to field18,
        "display" to field19,
        "elevation" to field14,
        "end" to field16,
        "fill" to field64,
        "fill_rule" to field105,
        "flex" to field10,
        "flex_basis" to field16,
        "flex_direction" to field20,
        "flex_grow" to field10,
        "flex_shrink" to field10,
        "flex_wrap" to field21,
        "font_family" to field22,
        "font_size" to field10,
        "font_weight" to field23,
        "gap" to field10,
        "gestures" to field24,
        "height" to field16,
        "important_for_accessibility" to field52,
        "italic" to field12,
        "justify_content" to field25,
        "left" to field16,
        "letter_spacing" to field10,
        "line_height" to field10,
        "margin" to field26,
        "margin_bottom" to field27,
        "margin_end" to field27,
        "margin_horizontal" to field27,
        "margin_left" to field27,
        "margin_right" to field27,
        "margin_start" to field27,
        "margin_top" to field27,
        "margin_vertical" to field27,
        "max_height" to field16,
        "max_lines" to field28,
        "max_width" to field16,
        "min_height" to field16,
        "min_width" to field16,
        "on_accessibility_action" to field53,
        "on_layout" to field29,
        "opacity" to field30,
        "overflow" to field31,
        "padding" to field32,
        "padding_bottom" to field16,
        "padding_end" to field16,
        "padding_horizontal" to field16,
        "padding_left" to field16,
        "padding_right" to field16,
        "padding_start" to field16,
        "padding_top" to field16,
        "padding_vertical" to field16,
        "placeholder_color" to field13,
        "pointer_events" to field33,
        "position" to field34,
        "preserve_aspect_ratio" to field106,
        "ref" to field35,
        "right" to field16,
        "row_gap" to field10,
        "shadow_color" to field13,
        "shadow_offset" to field36,
        "shadow_opacity" to field14,
        "shadow_radius" to field14,
        "shapes" to field107,
        "spacing" to field10,
        "start" to field16,
        "stroke" to field64,
        "stroke_linecap" to field108,
        "stroke_linejoin" to field109,
        "stroke_width" to field61,
        "test_id" to field43,
        "text_align" to field38,
        "text_decoration" to field39,
        "text_shadow_color" to field13,
        "text_shadow_offset" to field36,
        "text_shadow_radius" to field14,
        "text_transform" to field40,
        "tint_color" to field13,
        "top" to field16,
        "transform" to field41,
        "view_box" to field60,
        "width" to field16,
        "z_index" to field42
    )
    private fun component26(): Map<String, Field> = mapOf(
        "_pn_animated_events" to field0,
        "_pn_edit_revision" to field1,
        "_pn_events" to field2,
        "_pn_header_slot" to field3,
        "_pn_layout" to field4,
        "_pn_list_key" to field5,
        "accessibility_label" to field43,
        "accessibility_role" to field6,
        "align_content" to field7,
        "align_items" to field8,
        "align_self" to field8,
        "aspect_ratio" to field10,
        "background_color" to field11,
        "bold" to field12,
        "border_bottom_color" to field13,
        "border_bottom_left_radius" to field14,
        "border_bottom_right_radius" to field14,
        "border_bottom_width" to field10,
        "border_color" to field13,
        "border_left_color" to field13,
        "border_left_width" to field10,
        "border_radius" to field14,
        "border_right_color" to field13,
        "border_right_width" to field10,
        "border_style" to field15,
        "border_top_color" to field13,
        "border_top_left_radius" to field14,
        "border_top_right_radius" to field14,
        "border_top_width" to field10,
        "border_width" to field10,
        "bottom" to field16,
        "color" to field11,
        "column_gap" to field10,
        "direction" to field18,
        "disabled" to field51,
        "display" to field19,
        "elevation" to field14,
        "end" to field16,
        "flex" to field10,
        "flex_basis" to field16,
        "flex_direction" to field20,
        "flex_grow" to field10,
        "flex_shrink" to field10,
        "flex_wrap" to field21,
        "font_family" to field22,
        "font_size" to field10,
        "font_weight" to field23,
        "gap" to field10,
        "gestures" to field24,
        "height" to field16,
        "italic" to field12,
        "justify_content" to field25,
        "left" to field16,
        "letter_spacing" to field10,
        "line_height" to field10,
        "margin" to field26,
        "margin_bottom" to field27,
        "margin_end" to field27,
        "margin_horizontal" to field27,
        "margin_left" to field27,
        "margin_right" to field27,
        "margin_start" to field27,
        "margin_top" to field27,
        "margin_vertical" to field27,
        "max_height" to field16,
        "max_lines" to field28,
        "max_width" to field16,
        "min_height" to field16,
        "min_width" to field16,
        "on_change" to field56,
        "on_layout" to field29,
        "on_tint_color" to field64,
        "opacity" to field30,
        "overflow" to field31,
        "padding" to field32,
        "padding_bottom" to field16,
        "padding_end" to field16,
        "padding_horizontal" to field16,
        "padding_left" to field16,
        "padding_right" to field16,
        "padding_start" to field16,
        "padding_top" to field16,
        "padding_vertical" to field16,
        "placeholder_color" to field13,
        "pointer_events" to field33,
        "position" to field34,
        "ref" to field35,
        "right" to field16,
        "row_gap" to field10,
        "shadow_color" to field13,
        "shadow_offset" to field36,
        "shadow_opacity" to field14,
        "shadow_radius" to field14,
        "spacing" to field10,
        "start" to field16,
        "text_align" to field38,
        "text_decoration" to field39,
        "text_shadow_color" to field13,
        "text_shadow_offset" to field36,
        "text_shadow_radius" to field14,
        "text_transform" to field40,
        "thumb_color" to field64,
        "tint_color" to field13,
        "top" to field16,
        "transform" to field41,
        "value" to field57,
        "width" to field16,
        "z_index" to field42
    )
    private fun match128(value: Any): Boolean {
        if (value !is JSONObject) return false
        for (key in value.keys()) {
            val item = value.get(key)
            val valid = when (key) {
                "shapes" -> match119(item)
                "uri" -> match3(item)
                "view_box" -> match3(item)
                else -> false
            }
            if (!valid) return false
        }
        return true
    }
    private fun match127(value: Any): Boolean {
        if (value !is JSONObject) return false
        if (!value.has("name")) return false
        if (!value.has("title")) return false
        for (key in value.keys()) {
            val item = value.get(key)
            val valid = when (key) {
                "badge" -> match3(item)
                "icon" -> match128(item)
                "name" -> match3(item)
                "title" -> match3(item)
                else -> false
            }
            if (!valid) return false
        }
        return true
    }
    private fun match126(value: Any): Boolean {
        if (value !is JSONArray) return false
        return (0 until value.length()).all { match127(value.get(it)) }
    }
    private fun component27(): Map<String, Field> = mapOf(
        "_pn_animated_events" to field0,
        "_pn_edit_revision" to field1,
        "_pn_events" to field2,
        "_pn_header_slot" to field3,
        "_pn_layout" to field4,
        "_pn_list_key" to field5,
        "accessibility_actions" to field47,
        "accessibility_hint" to field43,
        "accessibility_label" to field43,
        "accessibility_live_region" to field48,
        "accessibility_role" to field43,
        "accessibility_state" to field49,
        "accessibility_value" to field50,
        "accessible" to field44,
        "active_tab" to field5,
        "align_content" to field7,
        "align_items" to field8,
        "align_self" to field8,
        "aspect_ratio" to field10,
        "background_color" to field11,
        "bold" to field12,
        "border_bottom_color" to field13,
        "border_bottom_left_radius" to field14,
        "border_bottom_right_radius" to field14,
        "border_bottom_width" to field10,
        "border_color" to field13,
        "border_left_color" to field13,
        "border_left_width" to field10,
        "border_radius" to field14,
        "border_right_color" to field13,
        "border_right_width" to field10,
        "border_style" to field15,
        "border_top_color" to field13,
        "border_top_left_radius" to field14,
        "border_top_right_radius" to field14,
        "border_top_width" to field10,
        "border_width" to field10,
        "bottom" to field16,
        "color" to field11,
        "column_gap" to field10,
        "direction" to field18,
        "display" to field19,
        "elevation" to field14,
        "end" to field16,
        "flex" to field10,
        "flex_basis" to field16,
        "flex_direction" to field20,
        "flex_grow" to field10,
        "flex_shrink" to field10,
        "flex_wrap" to field21,
        "font_family" to field22,
        "font_size" to field10,
        "font_weight" to field23,
        "gap" to field10,
        "gestures" to field24,
        "height" to field16,
        "hit_slop" to field58,
        "important_for_accessibility" to field52,
        "inactive_tint_color" to field5,
        "italic" to field12,
        "items" to field110,
        "justify_content" to field25,
        "left" to field16,
        "letter_spacing" to field10,
        "line_height" to field10,
        "margin" to field26,
        "margin_bottom" to field27,
        "margin_end" to field27,
        "margin_horizontal" to field27,
        "margin_left" to field27,
        "margin_right" to field27,
        "margin_start" to field27,
        "margin_top" to field27,
        "margin_vertical" to field27,
        "max_height" to field16,
        "max_lines" to field28,
        "max_width" to field16,
        "min_height" to field16,
        "min_width" to field16,
        "on_accessibility_action" to field53,
        "on_layout" to field29,
        "on_tab_select" to field111,
        "opacity" to field30,
        "overflow" to field31,
        "padding" to field32,
        "padding_bottom" to field16,
        "padding_end" to field16,
        "padding_horizontal" to field16,
        "padding_left" to field16,
        "padding_right" to field16,
        "padding_start" to field16,
        "padding_top" to field16,
        "padding_vertical" to field16,
        "placeholder_color" to field13,
        "pointer_events" to field33,
        "position" to field34,
        "ref" to field35,
        "right" to field16,
        "row_gap" to field10,
        "shadow_color" to field13,
        "shadow_offset" to field36,
        "shadow_opacity" to field14,
        "shadow_radius" to field14,
        "shows_labels" to field84,
        "spacing" to field10,
        "start" to field16,
        "test_id" to field43,
        "text_align" to field38,
        "text_decoration" to field39,
        "text_shadow_color" to field13,
        "text_shadow_offset" to field36,
        "text_shadow_radius" to field14,
        "text_transform" to field40,
        "tint_color" to field5,
        "top" to field16,
        "transform" to field41,
        "translucent" to field84,
        "width" to field16,
        "z_index" to field42
    )
    private fun match129(value: Any): Boolean {
        return (value == "head") || (value == "middle") || (value == "tail") || (value == "clip")
    }
    private fun component28(): Map<String, Field> = mapOf(
        "_pn_animated_events" to field0,
        "_pn_edit_revision" to field1,
        "_pn_events" to field2,
        "_pn_header_slot" to field3,
        "_pn_layout" to field4,
        "_pn_list_key" to field5,
        "accessibility_actions" to field47,
        "accessibility_hint" to field43,
        "accessibility_label" to field43,
        "accessibility_live_region" to field48,
        "accessibility_role" to field43,
        "accessibility_state" to field49,
        "accessibility_value" to field50,
        "accessible" to field44,
        "align_content" to field7,
        "align_items" to field8,
        "align_self" to field8,
        "allow_font_scaling" to field112,
        "aspect_ratio" to field10,
        "background_color" to field11,
        "bold" to field12,
        "border_bottom_color" to field13,
        "border_bottom_left_radius" to field14,
        "border_bottom_right_radius" to field14,
        "border_bottom_width" to field10,
        "border_color" to field13,
        "border_left_color" to field13,
        "border_left_width" to field10,
        "border_radius" to field14,
        "border_right_color" to field13,
        "border_right_width" to field10,
        "border_style" to field15,
        "border_top_color" to field13,
        "border_top_left_radius" to field14,
        "border_top_right_radius" to field14,
        "border_top_width" to field10,
        "border_width" to field10,
        "bottom" to field16,
        "color" to field11,
        "column_gap" to field10,
        "direction" to field18,
        "display" to field19,
        "elevation" to field14,
        "ellipsize_mode" to field113,
        "end" to field16,
        "flex" to field10,
        "flex_basis" to field16,
        "flex_direction" to field20,
        "flex_grow" to field10,
        "flex_shrink" to field10,
        "flex_wrap" to field21,
        "font_family" to field22,
        "font_size" to field10,
        "font_weight" to field23,
        "gap" to field10,
        "gestures" to field24,
        "height" to field16,
        "important_for_accessibility" to field52,
        "italic" to field12,
        "justify_content" to field25,
        "left" to field16,
        "letter_spacing" to field10,
        "line_height" to field10,
        "margin" to field26,
        "margin_bottom" to field27,
        "margin_end" to field27,
        "margin_horizontal" to field27,
        "margin_left" to field27,
        "margin_right" to field27,
        "margin_start" to field27,
        "margin_top" to field27,
        "margin_vertical" to field27,
        "max_height" to field16,
        "max_lines" to field28,
        "max_width" to field16,
        "min_height" to field16,
        "min_width" to field16,
        "on_accessibility_action" to field53,
        "on_layout" to field29,
        "on_press" to field54,
        "on_span_press" to field114,
        "opacity" to field30,
        "overflow" to field31,
        "padding" to field32,
        "padding_bottom" to field16,
        "padding_end" to field16,
        "padding_horizontal" to field16,
        "padding_left" to field16,
        "padding_right" to field16,
        "padding_start" to field16,
        "padding_top" to field16,
        "padding_vertical" to field16,
        "placeholder_color" to field13,
        "pointer_events" to field33,
        "position" to field34,
        "ref" to field35,
        "right" to field16,
        "row_gap" to field10,
        "selectable" to field51,
        "shadow_color" to field13,
        "shadow_offset" to field36,
        "shadow_opacity" to field14,
        "shadow_radius" to field14,
        "spacing" to field10,
        "spans" to field115,
        "start" to field16,
        "test_id" to field43,
        "text" to field116,
        "text_align" to field38,
        "text_decoration" to field39,
        "text_shadow_color" to field13,
        "text_shadow_offset" to field36,
        "text_shadow_radius" to field14,
        "text_transform" to field40,
        "tint_color" to field13,
        "top" to field16,
        "transform" to field41,
        "width" to field16,
        "z_index" to field42
    )
    private fun match131(value: Any): Boolean {
        return (value == "none") || (value == "sentences") || (value == "words") || (value == "characters")
    }
    private fun match130(value: Any): Boolean {
        return match131(value) || match14(value)
    }
    private fun match132(value: Any): Boolean {
        return (value == "default") || (value == "light") || (value == "dark")
    }
    private fun match134(value: Any): Boolean {
        return (value == "default") || (value == "email_address") || (value == "number_pad") || (value == "decimal_pad") || (value == "phone_pad") || (value == "url") || (value == "ascii") || (value == "numbers_and_punctuation") || (value == "web_search") || (value == "visible_password")
    }
    private fun match133(value: Any): Boolean {
        return match134(value) || match14(value)
    }
    private fun match135(value: Any): Boolean {
        return match1(value) || match14(value)
    }
    private fun match136(value: Any): Boolean {
        return match27(value) || match14(value)
    }
    private fun match137(value: Any): Boolean {
        return match27(value) || match14(value)
    }
    private fun match138(value: Any): Boolean {
        return match27(value) || match14(value)
    }
    private fun match140(value: Any): Boolean {
        return (value == "default") || (value == "done") || (value == "go") || (value == "next") || (value == "send") || (value == "search")
    }
    private fun match139(value: Any): Boolean {
        return match140(value) || match14(value)
    }
    private fun match142(value: Any): Boolean {
        if (value !is JSONObject) return false
        if (!value.has("end")) return false
        if (!value.has("start")) return false
        for (key in value.keys()) {
            val item = value.get(key)
            val valid = when (key) {
                "end" -> match1(item)
                "start" -> match1(item)
                else -> false
            }
            if (!valid) return false
        }
        return true
    }
    private fun match141(value: Any): Boolean {
        return match142(value) || match14(value)
    }
    private fun component29(): Map<String, Field> = mapOf(
        "_pn_animated_events" to field0,
        "_pn_edit_revision" to field1,
        "_pn_events" to field2,
        "_pn_header_slot" to field3,
        "_pn_layout" to field4,
        "_pn_list_key" to field5,
        "accessibility_actions" to field47,
        "accessibility_hint" to field43,
        "accessibility_label" to field43,
        "accessibility_live_region" to field48,
        "accessibility_role" to field6,
        "accessibility_state" to field49,
        "accessibility_value" to field50,
        "accessible" to field44,
        "align_content" to field7,
        "align_items" to field8,
        "align_self" to field8,
        "aspect_ratio" to field10,
        "auto_capitalize" to field117,
        "auto_correct" to field44,
        "auto_focus" to field51,
        "background_color" to field11,
        "blur_on_submit" to field44,
        "bold" to field12,
        "border_bottom_color" to field13,
        "border_bottom_left_radius" to field14,
        "border_bottom_right_radius" to field14,
        "border_bottom_width" to field10,
        "border_color" to field13,
        "border_left_color" to field13,
        "border_left_width" to field10,
        "border_radius" to field14,
        "border_right_color" to field13,
        "border_right_width" to field10,
        "border_style" to field15,
        "border_top_color" to field13,
        "border_top_left_radius" to field14,
        "border_top_right_radius" to field14,
        "border_top_width" to field10,
        "border_width" to field10,
        "bottom" to field16,
        "clear_button" to field51,
        "color" to field11,
        "column_gap" to field10,
        "direction" to field18,
        "display" to field19,
        "editable" to field9,
        "elevation" to field14,
        "end" to field16,
        "flex" to field10,
        "flex_basis" to field16,
        "flex_direction" to field20,
        "flex_grow" to field10,
        "flex_shrink" to field10,
        "flex_wrap" to field21,
        "font_family" to field22,
        "font_size" to field10,
        "font_weight" to field23,
        "gap" to field10,
        "gestures" to field24,
        "height" to field16,
        "important_for_accessibility" to field52,
        "italic" to field12,
        "justify_content" to field25,
        "keyboard_appearance" to field118,
        "keyboard_type" to field119,
        "left" to field16,
        "letter_spacing" to field10,
        "line_height" to field10,
        "margin" to field26,
        "margin_bottom" to field27,
        "margin_end" to field27,
        "margin_horizontal" to field27,
        "margin_left" to field27,
        "margin_right" to field27,
        "margin_start" to field27,
        "margin_top" to field27,
        "margin_vertical" to field27,
        "max_height" to field16,
        "max_length" to field120,
        "max_lines" to field28,
        "max_width" to field16,
        "min_height" to field16,
        "min_width" to field16,
        "multiline" to field121,
        "on_accessibility_action" to field53,
        "on_blur" to field54,
        "on_change" to field53,
        "on_content_size_change" to field122,
        "on_focus" to field54,
        "on_key_press" to field123,
        "on_layout" to field29,
        "on_selection_change" to field124,
        "on_submit" to field53,
        "opacity" to field30,
        "overflow" to field31,
        "padding" to field32,
        "padding_bottom" to field16,
        "padding_end" to field16,
        "padding_horizontal" to field16,
        "padding_left" to field16,
        "padding_right" to field16,
        "padding_start" to field16,
        "padding_top" to field16,
        "padding_vertical" to field16,
        "placeholder" to field43,
        "placeholder_color" to field64,
        "pointer_events" to field33,
        "position" to field34,
        "ref" to field35,
        "return_key_type" to field125,
        "right" to field16,
        "row_gap" to field10,
        "secure" to field51,
        "select_text_on_focus" to field51,
        "selection" to field126,
        "selection_color" to field64,
        "shadow_color" to field13,
        "shadow_offset" to field36,
        "shadow_opacity" to field14,
        "shadow_radius" to field14,
        "spacing" to field10,
        "start" to field16,
        "test_id" to field43,
        "text_align" to field38,
        "text_content_type" to field43,
        "text_decoration" to field39,
        "text_shadow_color" to field13,
        "text_shadow_offset" to field36,
        "text_shadow_radius" to field14,
        "text_transform" to field40,
        "tint_color" to field13,
        "top" to field16,
        "transform" to field41,
        "value" to field55,
        "width" to field16,
        "z_index" to field42
    )
    private fun component30(): Map<String, Field> = mapOf(
        "_pn_animated_events" to field0,
        "_pn_edit_revision" to field1,
        "_pn_events" to field2,
        "_pn_header_slot" to field3,
        "_pn_layout" to field4,
        "_pn_list_key" to field5,
        "accessibility_actions" to field47,
        "accessibility_hint" to field43,
        "accessibility_label" to field43,
        "accessibility_live_region" to field48,
        "accessibility_role" to field43,
        "accessibility_state" to field49,
        "accessibility_value" to field50,
        "accessible" to field44,
        "active_opacity" to field127,
        "align_content" to field7,
        "align_items" to field8,
        "align_self" to field8,
        "aspect_ratio" to field10,
        "background_color" to field11,
        "bold" to field12,
        "border_bottom_color" to field13,
        "border_bottom_left_radius" to field14,
        "border_bottom_right_radius" to field14,
        "border_bottom_width" to field10,
        "border_color" to field13,
        "border_left_color" to field13,
        "border_left_width" to field10,
        "border_radius" to field14,
        "border_right_color" to field13,
        "border_right_width" to field10,
        "border_style" to field15,
        "border_top_color" to field13,
        "border_top_left_radius" to field14,
        "border_top_right_radius" to field14,
        "border_top_width" to field10,
        "border_width" to field10,
        "bottom" to field16,
        "color" to field11,
        "column_gap" to field10,
        "direction" to field18,
        "disabled" to field51,
        "display" to field19,
        "elevation" to field14,
        "end" to field16,
        "flex" to field10,
        "flex_basis" to field16,
        "flex_direction" to field20,
        "flex_grow" to field10,
        "flex_shrink" to field10,
        "flex_wrap" to field21,
        "font_family" to field22,
        "font_size" to field10,
        "font_weight" to field23,
        "gap" to field10,
        "gestures" to field24,
        "height" to field16,
        "important_for_accessibility" to field52,
        "italic" to field12,
        "justify_content" to field25,
        "left" to field16,
        "letter_spacing" to field10,
        "line_height" to field10,
        "margin" to field26,
        "margin_bottom" to field27,
        "margin_end" to field27,
        "margin_horizontal" to field27,
        "margin_left" to field27,
        "margin_right" to field27,
        "margin_start" to field27,
        "margin_top" to field27,
        "margin_vertical" to field27,
        "max_height" to field16,
        "max_lines" to field28,
        "max_width" to field16,
        "min_height" to field16,
        "min_width" to field16,
        "on_accessibility_action" to field53,
        "on_layout" to field29,
        "on_long_press" to field54,
        "on_press" to field54,
        "opacity" to field30,
        "overflow" to field31,
        "padding" to field32,
        "padding_bottom" to field16,
        "padding_end" to field16,
        "padding_horizontal" to field16,
        "padding_left" to field16,
        "padding_right" to field16,
        "padding_start" to field16,
        "padding_top" to field16,
        "padding_vertical" to field16,
        "placeholder_color" to field13,
        "pointer_events" to field33,
        "position" to field34,
        "ref" to field35,
        "right" to field16,
        "row_gap" to field10,
        "shadow_color" to field13,
        "shadow_offset" to field36,
        "shadow_opacity" to field14,
        "shadow_radius" to field14,
        "spacing" to field10,
        "start" to field16,
        "test_id" to field43,
        "text_align" to field38,
        "text_decoration" to field39,
        "text_shadow_color" to field13,
        "text_shadow_offset" to field36,
        "text_shadow_radius" to field14,
        "text_transform" to field40,
        "tint_color" to field13,
        "top" to field16,
        "transform" to field41,
        "width" to field16,
        "z_index" to field42
    )
    private fun component31(): Map<String, Field> = mapOf(
        "_pn_animated_events" to field0,
        "_pn_edit_revision" to field1,
        "_pn_events" to field2,
        "_pn_header_slot" to field3,
        "_pn_layout" to field4,
        "_pn_list_key" to field5,
        "accessibility_actions" to field47,
        "accessibility_hint" to field43,
        "accessibility_label" to field43,
        "accessibility_live_region" to field48,
        "accessibility_role" to field43,
        "accessibility_state" to field49,
        "accessibility_value" to field50,
        "accessible" to field44,
        "align_content" to field7,
        "align_items" to field8,
        "align_self" to field8,
        "aspect_ratio" to field10,
        "background_color" to field11,
        "bold" to field12,
        "border_bottom_color" to field13,
        "border_bottom_left_radius" to field14,
        "border_bottom_right_radius" to field14,
        "border_bottom_width" to field10,
        "border_color" to field13,
        "border_left_color" to field13,
        "border_left_width" to field10,
        "border_radius" to field14,
        "border_right_color" to field13,
        "border_right_width" to field10,
        "border_style" to field15,
        "border_top_color" to field13,
        "border_top_left_radius" to field14,
        "border_top_right_radius" to field14,
        "border_top_width" to field10,
        "border_width" to field10,
        "bottom" to field16,
        "color" to field11,
        "column_gap" to field10,
        "direction" to field18,
        "display" to field19,
        "elevation" to field14,
        "end" to field16,
        "flex" to field10,
        "flex_basis" to field16,
        "flex_direction" to field20,
        "flex_grow" to field10,
        "flex_shrink" to field10,
        "flex_wrap" to field21,
        "font_family" to field22,
        "font_size" to field10,
        "font_weight" to field23,
        "gap" to field10,
        "gestures" to field24,
        "height" to field16,
        "hit_slop" to field58,
        "important_for_accessibility" to field52,
        "italic" to field12,
        "justify_content" to field25,
        "left" to field16,
        "letter_spacing" to field10,
        "line_height" to field10,
        "margin" to field26,
        "margin_bottom" to field27,
        "margin_end" to field27,
        "margin_horizontal" to field27,
        "margin_left" to field27,
        "margin_right" to field27,
        "margin_start" to field27,
        "margin_top" to field27,
        "margin_vertical" to field27,
        "max_height" to field16,
        "max_lines" to field28,
        "max_width" to field16,
        "min_height" to field16,
        "min_width" to field16,
        "on_accessibility_action" to field53,
        "on_layout" to field29,
        "opacity" to field30,
        "overflow" to field31,
        "padding" to field32,
        "padding_bottom" to field16,
        "padding_end" to field16,
        "padding_horizontal" to field16,
        "padding_left" to field16,
        "padding_right" to field16,
        "padding_start" to field16,
        "padding_top" to field16,
        "padding_vertical" to field16,
        "placeholder_color" to field13,
        "pointer_events" to field33,
        "position" to field34,
        "ref" to field35,
        "right" to field16,
        "row_gap" to field10,
        "shadow_color" to field13,
        "shadow_offset" to field36,
        "shadow_opacity" to field14,
        "shadow_radius" to field14,
        "spacing" to field10,
        "start" to field16,
        "test_id" to field43,
        "text_align" to field38,
        "text_decoration" to field39,
        "text_shadow_color" to field13,
        "text_shadow_offset" to field36,
        "text_shadow_radius" to field14,
        "text_transform" to field40,
        "tint_color" to field13,
        "top" to field16,
        "transform" to field41,
        "width" to field16,
        "z_index" to field42
    )
    private fun match144(value: Any): Boolean {
        if (value !is JSONArray) return false
        return (0 until value.length()).all { match20(value.get(it)) }
    }
    private fun match143(value: Any): Boolean {
        if (value !is JSONObject) return false
        if (!value.has("base")) return false
        if (!value.has("revision")) return false
        if (!value.has("changes")) return false
        for (key in value.keys()) {
            val item = value.get(key)
            val valid = when (key) {
                "base" -> match1(item)
                "changes" -> match144(item)
                "revision" -> match1(item)
                else -> false
            }
            if (!valid) return false
        }
        return true
    }
    private fun component32(): Map<String, Field> = mapOf(
        "_pn_animated_events" to field0,
        "_pn_edit_revision" to field1,
        "_pn_events" to field2,
        "_pn_header_slot" to field3,
        "_pn_layout" to field4,
        "_pn_list_key" to field5,
        "accessibility_actions" to field47,
        "accessibility_hint" to field43,
        "accessibility_label" to field43,
        "accessibility_live_region" to field48,
        "accessibility_role" to field43,
        "accessibility_state" to field49,
        "accessibility_value" to field50,
        "accessible" to field44,
        "align_content" to field7,
        "align_items" to field8,
        "align_self" to field8,
        "aspect_ratio" to field10,
        "background_color" to field11,
        "bold" to field12,
        "border_bottom_color" to field13,
        "border_bottom_left_radius" to field14,
        "border_bottom_right_radius" to field14,
        "border_bottom_width" to field10,
        "border_color" to field13,
        "border_left_color" to field13,
        "border_left_width" to field10,
        "border_radius" to field14,
        "border_right_color" to field13,
        "border_right_width" to field10,
        "border_style" to field15,
        "border_top_color" to field13,
        "border_top_left_radius" to field14,
        "border_top_right_radius" to field14,
        "border_top_width" to field10,
        "border_width" to field10,
        "bottom" to field16,
        "color" to field11,
        "column_gap" to field10,
        "dataset" to field128,
        "direction" to field18,
        "display" to field19,
        "elevation" to field14,
        "end" to field16,
        "flex" to field10,
        "flex_basis" to field16,
        "flex_direction" to field20,
        "flex_grow" to field10,
        "flex_shrink" to field10,
        "flex_wrap" to field21,
        "font_family" to field22,
        "font_size" to field10,
        "font_weight" to field23,
        "gap" to field10,
        "gestures" to field24,
        "height" to field16,
        "hit_slop" to field58,
        "horizontal" to field84,
        "important_for_accessibility" to field52,
        "italic" to field12,
        "justify_content" to field25,
        "left" to field16,
        "letter_spacing" to field10,
        "line_height" to field10,
        "margin" to field26,
        "margin_bottom" to field27,
        "margin_end" to field27,
        "margin_horizontal" to field27,
        "margin_left" to field27,
        "margin_right" to field27,
        "margin_start" to field27,
        "margin_top" to field27,
        "margin_vertical" to field27,
        "max_height" to field16,
        "max_lines" to field28,
        "max_width" to field16,
        "min_height" to field16,
        "min_width" to field16,
        "on_accessibility_action" to field53,
        "on_bind_row" to field129,
        "on_layout" to field29,
        "on_scroll" to field129,
        "on_window" to field129,
        "opacity" to field30,
        "overflow" to field31,
        "padding" to field32,
        "padding_bottom" to field16,
        "padding_end" to field16,
        "padding_horizontal" to field16,
        "padding_left" to field16,
        "padding_right" to field16,
        "padding_start" to field16,
        "padding_top" to field16,
        "padding_vertical" to field16,
        "placeholder_color" to field13,
        "pointer_events" to field33,
        "position" to field34,
        "ref" to field35,
        "refresh_control" to field95,
        "right" to field16,
        "row_gap" to field10,
        "shadow_color" to field13,
        "shadow_offset" to field36,
        "shadow_opacity" to field14,
        "shadow_radius" to field14,
        "shows_scroll_indicator" to field84,
        "spacing" to field10,
        "start" to field16,
        "test_id" to field43,
        "text_align" to field38,
        "text_decoration" to field39,
        "text_shadow_color" to field13,
        "text_shadow_offset" to field36,
        "text_shadow_radius" to field14,
        "text_transform" to field40,
        "tint_color" to field13,
        "top" to field16,
        "transform" to field41,
        "width" to field16,
        "z_index" to field42
    )
    private fun match145(value: Any): Boolean {
        return match27(value) || match14(value)
    }
    private fun component33(): Map<String, Field> = mapOf(
        "_pn_animated_events" to field0,
        "_pn_edit_revision" to field1,
        "_pn_events" to field2,
        "_pn_header_slot" to field3,
        "_pn_layout" to field4,
        "_pn_list_key" to field5,
        "accessibility_role" to field6,
        "align_content" to field7,
        "align_items" to field8,
        "align_self" to field8,
        "aspect_ratio" to field10,
        "background_color" to field11,
        "bold" to field12,
        "border_bottom_color" to field13,
        "border_bottom_left_radius" to field14,
        "border_bottom_right_radius" to field14,
        "border_bottom_width" to field10,
        "border_color" to field13,
        "border_left_color" to field13,
        "border_left_width" to field10,
        "border_radius" to field14,
        "border_right_color" to field13,
        "border_right_width" to field10,
        "border_style" to field15,
        "border_top_color" to field13,
        "border_top_left_radius" to field14,
        "border_top_right_radius" to field14,
        "border_top_width" to field10,
        "border_width" to field10,
        "bottom" to field16,
        "color" to field11,
        "column_gap" to field10,
        "direction" to field18,
        "display" to field19,
        "elevation" to field14,
        "end" to field16,
        "flex" to field10,
        "flex_basis" to field16,
        "flex_direction" to field20,
        "flex_grow" to field10,
        "flex_shrink" to field10,
        "flex_wrap" to field21,
        "font_family" to field22,
        "font_size" to field10,
        "font_weight" to field23,
        "gap" to field10,
        "gestures" to field24,
        "height" to field16,
        "html" to field43,
        "inject_javascript" to field43,
        "italic" to field12,
        "justify_content" to field25,
        "left" to field16,
        "letter_spacing" to field10,
        "line_height" to field10,
        "margin" to field26,
        "margin_bottom" to field27,
        "margin_end" to field27,
        "margin_horizontal" to field27,
        "margin_left" to field27,
        "margin_right" to field27,
        "margin_start" to field27,
        "margin_top" to field27,
        "margin_vertical" to field27,
        "max_height" to field16,
        "max_lines" to field28,
        "max_width" to field16,
        "min_height" to field16,
        "min_width" to field16,
        "on_error" to field53,
        "on_layout" to field29,
        "on_load" to field53,
        "on_load_start" to field53,
        "on_message" to field53,
        "on_navigation_state_change" to field130,
        "opacity" to field30,
        "overflow" to field31,
        "padding" to field32,
        "padding_bottom" to field16,
        "padding_end" to field16,
        "padding_horizontal" to field16,
        "padding_left" to field16,
        "padding_right" to field16,
        "padding_start" to field16,
        "padding_top" to field16,
        "padding_vertical" to field16,
        "placeholder_color" to field13,
        "pointer_events" to field33,
        "position" to field34,
        "ref" to field35,
        "right" to field16,
        "row_gap" to field10,
        "scroll_enabled" to field9,
        "shadow_color" to field13,
        "shadow_offset" to field36,
        "shadow_opacity" to field14,
        "shadow_radius" to field14,
        "spacing" to field10,
        "start" to field16,
        "text_align" to field38,
        "text_decoration" to field39,
        "text_shadow_color" to field13,
        "text_shadow_offset" to field36,
        "text_shadow_radius" to field14,
        "text_transform" to field40,
        "tint_color" to field13,
        "top" to field16,
        "transform" to field41,
        "url" to field131,
        "width" to field16,
        "z_index" to field42
    )
    private fun match146(value: Any): Boolean {
        if (value !is JSONObject) return false
        for (key in value.keys()) {
            val item = value.get(key)
            val valid = when (key) {
                else -> false
            }
            if (!valid) return false
        }
        return true
    }
    private fun match147(value: Any): Boolean {
        if (value !is JSONObject) return false
        for (key in value.keys()) {
            val item = value.get(key)
            val valid = when (key) {
                "animated" -> match5(item)
                else -> false
            }
            if (!valid) return false
        }
        return true
    }
    private fun match148(value: Any): Boolean {
        if (value !is JSONObject) return false
        for (key in value.keys()) {
            val item = value.get(key)
            val valid = when (key) {
                "animated" -> match5(item)
                "x" -> match8(item)
                "y" -> match8(item)
                else -> false
            }
            if (!valid) return false
        }
        return true
    }
    private fun match149(value: Any): Boolean {
        if (value !is JSONObject) return false
        if (!value.has("start")) return false
        for (key in value.keys()) {
            val item = value.get(key)
            val valid = when (key) {
                "end" -> match1(item)
                "start" -> match1(item)
                else -> false
            }
            if (!valid) return false
        }
        return true
    }
    private fun match150(value: Any): Boolean {
        if (value !is JSONObject) return false
        if (!value.has("index")) return false
        for (key in value.keys()) {
            val item = value.get(key)
            val valid = when (key) {
                "animated" -> match5(item)
                "index" -> match1(item)
                else -> false
            }
            if (!valid) return false
        }
        return true
    }
    private fun match151(value: Any): Boolean {
        if (value !is JSONObject) return false
        if (!value.has("script")) return false
        for (key in value.keys()) {
            val item = value.get(key)
            val valid = when (key) {
                "script" -> match3(item)
                else -> false
            }
            if (!valid) return false
        }
        return true
    }
    private fun match152(value: Any): Boolean {
        if (value !is JSONObject) return false
        if (!value.has("url")) return false
        for (key in value.keys()) {
            val item = value.get(key)
            val valid = when (key) {
                "url" -> match3(item)
                else -> false
            }
            if (!valid) return false
        }
        return true
    }
    private fun match153(value: Any): Boolean {
        if (value !is JSONObject) return false
        if (!value.has("message")) return false
        for (key in value.keys()) {
            val item = value.get(key)
            val valid = when (key) {
                "message" -> match3(item)
                else -> false
            }
            if (!valid) return false
        }
        return true
    }
    private fun match154(value: Any): Boolean {
        if (value !is JSONObject) return false
        if (!value.has("tag")) return false
        for (key in value.keys()) {
            val item = value.get(key)
            val valid = when (key) {
                "tag" -> match1(item)
                else -> false
            }
            if (!valid) return false
        }
        return true
    }
    private fun match155(value: Any): Boolean {
        if (value !is JSONObject) return false
        if (!value.has("title")) return false
        if (!value.has("message")) return false
        if (!value.has("buttons")) return false
        if (!value.has("style")) return false
        for (key in value.keys()) {
            val item = value.get(key)
            val valid = when (key) {
                "buttons" -> match91(item)
                "message" -> match57(item)
                "style" -> match3(item)
                "title" -> match3(item)
                else -> false
            }
            if (!valid) return false
        }
        return true
    }
    private fun match159(value: Any): Boolean {
        if (value !is JSONObject) return false
        if (!value.has("family")) return false
        if (!value.has("italic")) return false
        if (!value.has("path")) return false
        if (!value.has("postscript_name")) return false
        if (!value.has("weight")) return false
        for (key in value.keys()) {
            val item = value.get(key)
            val valid = when (key) {
                "family" -> match3(item)
                "italic" -> match5(item)
                "path" -> match3(item)
                "postscript_name" -> match3(item)
                "weight" -> match1(item)
                else -> false
            }
            if (!valid) return false
        }
        return true
    }
    private fun match158(value: Any): Boolean {
        if (value !is JSONArray) return false
        return (0 until value.length()).all { match159(value.get(it)) }
    }
    private fun match160(value: Any): Boolean {
        if (value !is JSONObject) return false
        for (key in value.keys()) {
            val item = value.get(key)
            val valid = when (key) {
                else -> match81(item)
            }
            if (!valid) return false
        }
        return true
    }
    private fun match157(value: Any): Boolean {
        if (value !is JSONObject) return false
        for (key in value.keys()) {
            val item = value.get(key)
            val valid = when (key) {
                "files" -> match2(item)
                "fonts" -> match158(item)
                "variants" -> match160(item)
                else -> false
            }
            if (!valid) return false
        }
        return true
    }
    private fun match156(value: Any): Boolean {
        if (value !is JSONObject) return false
        if (!value.has("overlay")) return false
        if (!value.has("manifest")) return false
        for (key in value.keys()) {
            val item = value.get(key)
            val valid = when (key) {
                "manifest" -> match157(item)
                "overlay" -> match57(item)
                else -> false
            }
            if (!valid) return false
        }
        return true
    }
    private fun match161(value: Any): Boolean {
        if (value !is JSONObject) return false
        if (!value.has("path")) return false
        for (key in value.keys()) {
            val item = value.get(key)
            val valid = when (key) {
                "path" -> match3(item)
                else -> false
            }
            if (!valid) return false
        }
        return true
    }
    private fun match162(value: Any): Boolean {
        if (value !is JSONObject) return false
        for (key in value.keys()) {
            val item = value.get(key)
            val valid = when (key) {
                "reason" -> match3(item)
                else -> false
            }
            if (!valid) return false
        }
        return true
    }
    private fun match163(value: Any): Boolean {
        if (value !is JSONObject) return false
        for (key in value.keys()) {
            val item = value.get(key)
            val valid = when (key) {
                "allow_editing" -> match5(item)
                "quality" -> match8(item)
                else -> false
            }
            if (!valid) return false
        }
        return true
    }
    private fun match164(value: Any): Boolean {
        if (value !is JSONObject) return false
        if (!value.has("text")) return false
        for (key in value.keys()) {
            val item = value.get(key)
            val valid = when (key) {
                "text" -> match3(item)
                else -> false
            }
            if (!valid) return false
        }
        return true
    }
    private fun match165(value: Any): Boolean {
        if (value !is JSONObject) return false
        for (key in value.keys()) {
            val item = value.get(key)
            val valid = when (key) {
                "style" -> match3(item)
                else -> false
            }
            if (!valid) return false
        }
        return true
    }
    private fun match166(value: Any): Boolean {
        if (value !is JSONObject) return false
        for (key in value.keys()) {
            val item = value.get(key)
            val valid = when (key) {
                "type" -> match3(item)
                else -> false
            }
            if (!valid) return false
        }
        return true
    }
    private fun match167(value: Any): Boolean {
        if (value !is JSONObject) return false
        for (key in value.keys()) {
            val item = value.get(key)
            val valid = when (key) {
                "duration_ms" -> match1(item)
                else -> false
            }
            if (!valid) return false
        }
        return true
    }
    private fun match168(value: Any): Boolean {
        if (value !is JSONObject) return false
        if (!value.has("uri")) return false
        for (key in value.keys()) {
            val item = value.get(key)
            val valid = when (key) {
                "uri" -> match3(item)
                else -> false
            }
            if (!valid) return false
        }
        return true
    }
    private fun match170(value: Any): Boolean {
        return (value == "balanced") || (value == "high")
    }
    private fun match169(value: Any): Boolean {
        if (value !is JSONObject) return false
        for (key in value.keys()) {
            val item = value.get(key)
            val valid = when (key) {
                "accuracy" -> match170(item)
                "timeout" -> match8(item)
                else -> false
            }
            if (!valid) return false
        }
        return true
    }
    private fun match171(value: Any): Boolean {
        if (value !is JSONObject) return false
        for (key in value.keys()) {
            val item = value.get(key)
            val valid = when (key) {
                "identifier" -> match3(item)
                else -> false
            }
            if (!valid) return false
        }
        return true
    }
    private fun match172(value: Any): Boolean {
        if (value !is JSONObject) return false
        if (!value.has("title")) return false
        for (key in value.keys()) {
            val item = value.get(key)
            val valid = when (key) {
                "body" -> match3(item)
                "delay_seconds" -> match8(item)
                "identifier" -> match3(item)
                "title" -> match3(item)
                else -> false
            }
            if (!valid) return false
        }
        return true
    }
    private fun match173(value: Any): Boolean {
        if (value !is JSONObject) return false
        if (!value.has("permission")) return false
        for (key in value.keys()) {
            val item = value.get(key)
            val valid = when (key) {
                "permission" -> match3(item)
                else -> false
            }
            if (!valid) return false
        }
        return true
    }
    private fun match174(value: Any): Boolean {
        if (value !is JSONObject) return false
        if (!value.has("key")) return false
        for (key in value.keys()) {
            val item = value.get(key)
            val valid = when (key) {
                "key" -> match3(item)
                else -> false
            }
            if (!valid) return false
        }
        return true
    }
    private fun match175(value: Any): Boolean {
        if (value !is JSONObject) return false
        if (!value.has("key")) return false
        if (!value.has("value")) return false
        for (key in value.keys()) {
            val item = value.get(key)
            val valid = when (key) {
                "key" -> match3(item)
                "value" -> match3(item)
                else -> false
            }
            if (!valid) return false
        }
        return true
    }
    private fun match176(value: Any): Boolean {
        if (value !is JSONObject) return false
        for (key in value.keys()) {
            val item = value.get(key)
            val valid = when (key) {
                "message" -> match57(item)
                "title" -> match57(item)
                "url" -> match57(item)
                else -> false
            }
            if (!valid) return false
        }
        return true
    }
    private fun match177(value: Any): Boolean {
        if (value !is JSONObject) return false
        if (!value.has("tag")) return false
        if (!value.has("script")) return false
        for (key in value.keys()) {
            val item = value.get(key)
            val valid = when (key) {
                "script" -> match3(item)
                "tag" -> match1(item)
                else -> false
            }
            if (!valid) return false
        }
        return true
    }
    private val field0 = Field(::match0, true, true, false, false, PNValues.defaultValue("null"))
    private val field1 = Field(::match1, true, true, false, false, PNValues.defaultValue("null"))
    private val field2 = Field(::match2, true, true, false, false, PNValues.defaultValue("null"))
    private val field3 = Field(::match4, true, true, false, false, PNValues.defaultValue("null"))
    private val field4 = Field(::match5, true, false, false, false, PNValues.defaultValue("null"))
    private val field5 = Field(::match3, true, true, false, false, PNValues.defaultValue("null"))
    private val field6 = Field(::match3, true, false, false, false, PNValues.defaultValue("null"))
    private val field7 = Field(::match6, true, true, false, false, PNValues.defaultValue("null"))
    private val field8 = Field(::match7, true, true, false, false, PNValues.defaultValue("null"))
    private val field9 = Field(::match5, true, false, false, false, PNValues.defaultValue("true"))
    private val field10 = Field(::match8, true, true, false, false, PNValues.defaultValue("null"))
    private val field11 = Field(::match9, true, false, false, false, PNValues.defaultValue("null"))
    private val field12 = Field(::match5, true, true, false, false, PNValues.defaultValue("null"))
    private val field13 = Field(::match9, true, false, false, false, PNValues.defaultValue("null"))
    private val field14 = Field(::match8, true, false, false, false, PNValues.defaultValue("null"))
    private val field15 = Field(::match11, true, false, false, false, PNValues.defaultValue("null"))
    private val field16 = Field(::match12, true, true, false, false, PNValues.defaultValue("null"))
    private val field17 = Field(::match13, true, false, false, false, PNValues.defaultValue("null"))
    private val field18 = Field(::match15, true, true, false, false, PNValues.defaultValue("null"))
    private val field19 = Field(::match16, true, true, false, false, PNValues.defaultValue("null"))
    private val field20 = Field(::match17, true, true, false, false, PNValues.defaultValue("null"))
    private val field21 = Field(::match18, true, true, false, false, PNValues.defaultValue("null"))
    private val field22 = Field(::match3, true, true, false, false, PNValues.defaultValue("null"))
    private val field23 = Field(::match19, true, true, false, false, PNValues.defaultValue("null"))
    private val field24 = Field(::match20, true, true, false, false, PNValues.defaultValue("null"))
    private val field25 = Field(::match22, true, true, false, false, PNValues.defaultValue("null"))
    private val field26 = Field(::match23, true, true, false, false, PNValues.defaultValue("null"))
    private val field27 = Field(::match26, true, true, false, false, PNValues.defaultValue("null"))
    private val field28 = Field(::match1, true, true, false, false, PNValues.defaultValue("null"))
    private val field29 = Field(::match27, true, false, false, false, PNValues.defaultValue("null"))
    private val field30 = Field(::match8, true, false, false, false, PNValues.defaultValue("null"))
    private val field31 = Field(::match28, true, false, false, false, PNValues.defaultValue("null"))
    private val field32 = Field(::match29, true, true, false, false, PNValues.defaultValue("null"))
    private val field33 = Field(::match30, true, false, false, false, PNValues.defaultValue("null"))
    private val field34 = Field(::match31, true, true, false, false, PNValues.defaultValue("null"))
    private val field35 = Field(::match21, true, false, false, false, PNValues.defaultValue("null"))
    private val field36 = Field(::match32, true, false, false, false, PNValues.defaultValue("null"))
    private val field37 = Field(::match36, true, false, false, false, PNValues.defaultValue("\"small\""))
    private val field38 = Field(::match37, true, false, false, false, PNValues.defaultValue("null"))
    private val field39 = Field(::match38, true, false, false, false, PNValues.defaultValue("null"))
    private val field40 = Field(::match39, true, true, false, false, PNValues.defaultValue("null"))
    private val field41 = Field(::match40, true, false, false, false, PNValues.defaultValue("null"))
    private val field42 = Field(::match1, true, false, false, false, PNValues.defaultValue("null"))
    private val field43 = Field(::match57, true, false, false, false, PNValues.defaultValue("null"))
    private val field44 = Field(::match58, true, false, false, false, PNValues.defaultValue("null"))
    private val field45 = Field(::match59, true, false, false, false, PNValues.defaultValue("\"regular\""))
    private val field46 = Field(::match8, true, false, false, false, PNValues.defaultValue("100.0"))
    private val field47 = Field(::match60, true, false, false, false, PNValues.defaultValue("null"))
    private val field48 = Field(::match63, true, false, false, false, PNValues.defaultValue("null"))
    private val field49 = Field(::match65, true, false, false, false, PNValues.defaultValue("null"))
    private val field50 = Field(::match69, true, false, false, false, PNValues.defaultValue("null"))
    private val field51 = Field(::match5, true, false, false, false, PNValues.defaultValue("false"))
    private val field52 = Field(::match71, true, false, false, false, PNValues.defaultValue("null"))
    private val field53 = Field(::match73, true, false, false, false, PNValues.defaultValue("null"))
    private val field54 = Field(::match74, true, false, false, false, PNValues.defaultValue("null"))
    private val field55 = Field(::match3, true, true, false, false, PNValues.defaultValue("\"\""))
    private val field56 = Field(::match75, true, false, false, false, PNValues.defaultValue("null"))
    private val field57 = Field(::match5, true, true, false, false, PNValues.defaultValue("false"))
    private val field58 = Field(::match76, true, false, false, false, PNValues.defaultValue("null"))
    private val field59 = Field(::match78, true, false, false, false, PNValues.defaultValue("\"date\""))
    private val field60 = Field(::match57, true, true, false, false, PNValues.defaultValue("null"))
    private val field61 = Field(::match79, true, false, false, false, PNValues.defaultValue("null"))
    private val field62 = Field(::match80, true, false, false, false, PNValues.defaultValue("null"))
    private val field63 = Field(::match82, true, false, false, false, PNValues.defaultValue("null"))
    private val field64 = Field(::match13, true, false, false, false, PNValues.defaultValue("null"))
    private val field65 = Field(::match83, true, false, false, false, PNValues.defaultValue("null"))
    private val field66 = Field(::match85, true, false, false, false, PNValues.defaultValue("\"padding\""))
    private val field67 = Field(::match8, true, false, false, false, PNValues.defaultValue("0.0"))
    private val field68 = Field(::match86, true, false, false, false, PNValues.defaultValue("null"))
    private val field69 = Field(::match34, true, false, false, false, PNValues.defaultValue("[0.0,1.0]"))
    private val field70 = Field(::match87, true, false, false, false, PNValues.defaultValue("null"))
    private val field71 = Field(::match34, true, false, false, false, PNValues.defaultValue("[0.0,0.0]"))
    private val field72 = Field(::match88, true, false, false, false, PNValues.defaultValue("\"slide\""))
    private val field73 = Field(::match89, true, false, false, false, PNValues.defaultValue("\"page_sheet\""))
    private val field74 = Field(::match90, true, false, false, false, PNValues.defaultValue("null"))
    private val field75 = Field(::match92, true, false, false, false, PNValues.defaultValue("null"))
    private val field76 = Field(::match3, true, false, false, false, PNValues.defaultValue("\"Select\\u2026\""))
    private val field77 = Field(::match54, true, true, false, false, PNValues.defaultValue("null"))
    private val field78 = Field(::match93, true, false, false, false, PNValues.defaultValue("null"))
    private val field79 = Field(::match8, true, false, false, false, PNValues.defaultValue("500"))
    private val field80 = Field(::match8, true, false, false, false, PNValues.defaultValue("0.6"))
    private val field81 = Field(::match5, true, false, true, false, PNValues.defaultValue("false"))
    private val field82 = Field(::match8, true, true, false, false, PNValues.defaultValue("0.0"))
    private val field83 = Field(::match95, true, false, false, false, PNValues.defaultValue("null"))
    private val field84 = Field(::match5, true, true, false, false, PNValues.defaultValue("null"))
    private val field85 = Field(::match98, true, true, false, false, PNValues.defaultValue("null"))
    private val field86 = Field(::match53, true, true, false, false, PNValues.defaultValue("null"))
    private val field87 = Field(::match99, true, true, false, false, PNValues.defaultValue("null"))
    private val field88 = Field(::match100, true, true, false, false, PNValues.defaultValue("null"))
    private val field89 = Field(::match27, true, true, false, false, PNValues.defaultValue("null"))
    private val field90 = Field(::match101, true, false, false, false, PNValues.defaultValue("null"))
    private val field91 = Field(::match102, true, false, false, false, PNValues.defaultValue("\"normal\""))
    private val field92 = Field(::match104, true, false, false, false, PNValues.defaultValue("null"))
    private val field93 = Field(::match106, true, false, false, false, PNValues.defaultValue("\"never\""))
    private val field94 = Field(::match107, true, false, false, false, PNValues.defaultValue("null"))
    private val field95 = Field(::match108, true, true, false, false, PNValues.defaultValue("null"))
    private val field96 = Field(::match8, true, false, false, false, PNValues.defaultValue("16"))
    private val field97 = Field(::match109, true, false, false, false, PNValues.defaultValue("\"start\""))
    private val field98 = Field(::match110, true, false, false, false, PNValues.defaultValue("null"))
    private val field99 = Field(::match111, true, false, false, false, PNValues.defaultValue("null"))
    private val field100 = Field(::match1, true, false, false, false, PNValues.defaultValue("0"))
    private val field101 = Field(::match8, true, false, false, false, PNValues.defaultValue("1.0"))
    private val field102 = Field(::match112, true, false, false, false, PNValues.defaultValue("null"))
    private val field103 = Field(::match79, true, true, false, false, PNValues.defaultValue("null"))
    private val field104 = Field(::match113, true, false, false, false, PNValues.defaultValue("null"))
    private val field105 = Field(::match115, true, false, false, false, PNValues.defaultValue("null"))
    private val field106 = Field(::match117, true, false, false, false, PNValues.defaultValue("\"meet\""))
    private val field107 = Field(::match118, true, false, false, false, PNValues.defaultValue("null"))
    private val field108 = Field(::match122, true, false, false, false, PNValues.defaultValue("null"))
    private val field109 = Field(::match124, true, false, false, false, PNValues.defaultValue("null"))
    private val field110 = Field(::match126, true, true, false, false, PNValues.defaultValue("null"))
    private val field111 = Field(::match27, true, true, false, false, PNValues.defaultValue("null"))
    private val field112 = Field(::match5, true, true, false, false, PNValues.defaultValue("true"))
    private val field113 = Field(::match129, true, true, false, false, PNValues.defaultValue("\"tail\""))
    private val field114 = Field(::match27, true, false, false, false, PNValues.defaultValue("null"))
    private val field115 = Field(::match20, true, true, false, false, PNValues.defaultValue("null"))
    private val field116 = Field(::match3, true, true, false, false, PNValues.defaultValue("null"))
    private val field117 = Field(::match130, true, false, false, false, PNValues.defaultValue("null"))
    private val field118 = Field(::match132, true, false, false, false, PNValues.defaultValue("\"default\""))
    private val field119 = Field(::match133, true, false, false, false, PNValues.defaultValue("null"))
    private val field120 = Field(::match135, true, false, false, false, PNValues.defaultValue("null"))
    private val field121 = Field(::match5, true, true, true, false, PNValues.defaultValue("false"))
    private val field122 = Field(::match136, true, false, false, false, PNValues.defaultValue("null"))
    private val field123 = Field(::match137, true, false, false, false, PNValues.defaultValue("null"))
    private val field124 = Field(::match138, true, false, false, false, PNValues.defaultValue("null"))
    private val field125 = Field(::match139, true, false, false, false, PNValues.defaultValue("null"))
    private val field126 = Field(::match141, true, false, false, false, PNValues.defaultValue("null"))
    private val field127 = Field(::match8, true, false, false, false, PNValues.defaultValue("0.2"))
    private val field128 = Field(::match143, true, true, false, true, PNValues.defaultValue("null"))
    private val field129 = Field(::match27, true, true, false, false, PNValues.defaultValue("null"))
    private val field130 = Field(::match145, true, false, false, false, PNValues.defaultValue("null"))
    private val field131 = Field(::match3, true, false, false, false, PNValues.defaultValue("\"\""))
    private val components: Map<String, Map<String, Field>> = mapOf(
        "ActivityIndicator" to component0(),
        "BlurView" to component1(),
        "Button" to component2(),
        "Checkbox" to component3(),
        "Column" to component4(),
        "DatePicker" to component5(),
        "Image" to component6(),
        "ImageBackground" to component7(),
        "KeyboardAvoidingView" to component8(),
        "LinearGradient" to component9(),
        "Modal" to component10(),
        "Picker" to component11(),
        "Portal" to component12(),
        "Pressable" to component13(),
        "ProgressBar" to component14(),
        "RefreshControl" to component15(),
        "Row" to component16(),
        "SafeAreaView" to component17(),
        "Screen" to component18(),
        "ScreenStack" to component19(),
        "ScrollView" to component20(),
        "SegmentedControl" to component21(),
        "Slider" to component22(),
        "Spacer" to component23(),
        "StatusBar" to component24(),
        "Svg" to component25(),
        "Switch" to component26(),
        "TabBar" to component27(),
        "Text" to component28(),
        "TextInput" to component29(),
        "TouchableOpacity" to component30(),
        "View" to component31(),
        "VirtualList" to component32(),
        "WebView" to component33()
    )
    private val commands: Map<String, (Any) -> Boolean> = mapOf(
        "ScreenStack.restore_stack" to ::match146,
        "ScrollView.flash_scroll_indicators" to ::match146,
        "ScrollView.get_scroll_offset" to ::match146,
        "ScrollView.scroll_to_end" to ::match147,
        "ScrollView.scroll_to_offset" to ::match148,
        "TextInput.blur" to ::match146,
        "TextInput.clear" to ::match146,
        "TextInput.focus" to ::match146,
        "TextInput.get_value" to ::match146,
        "TextInput.select_all" to ::match146,
        "TextInput.set_selection" to ::match149,
        "VirtualList.flash_scroll_indicators" to ::match146,
        "VirtualList.get_scroll_offset" to ::match146,
        "VirtualList.scroll_to_end" to ::match147,
        "VirtualList.scroll_to_index" to ::match150,
        "VirtualList.scroll_to_offset" to ::match148,
        "WebView.can_go_back" to ::match146,
        "WebView.can_go_forward" to ::match146,
        "WebView.get_url" to ::match146,
        "WebView.go_back" to ::match146,
        "WebView.go_forward" to ::match146,
        "WebView.inject_javascript" to ::match151,
        "WebView.load_url" to ::match152,
        "WebView.reload" to ::match146,
        "WebView.stop_loading" to ::match146
    )
    private val modules: Map<String, (Any) -> Boolean> = mapOf(
        "AccessibilityInfo.announce" to ::match153,
        "AccessibilityInfo.is_reduce_motion_enabled" to ::match146,
        "AccessibilityInfo.is_screen_reader_enabled" to ::match146,
        "AccessibilityInfo.set_accessibility_focus" to ::match154,
        "Alert.present" to ::match155,
        "Alert.show" to ::match155,
        "AppState.current_state" to ::match146,
        "Assets.configure" to ::match156,
        "Assets.exists" to ::match161,
        "Assets.read" to ::match161,
        "Battery.get_level" to ::match146,
        "Battery.get_state" to ::match146,
        "Biometrics.authenticate" to ::match162,
        "Biometrics.is_available" to ::match146,
        "Camera.pick_from_gallery" to ::match163,
        "Camera.take_photo" to ::match163,
        "Clipboard.get_string" to ::match146,
        "Clipboard.set_string" to ::match164,
        "Device.info" to ::match146,
        "Haptics.cancel" to ::match146,
        "Haptics.impact" to ::match165,
        "Haptics.notification" to ::match166,
        "Haptics.selection" to ::match146,
        "Haptics.vibrate" to ::match167,
        "Images.clear_cache" to ::match146,
        "Images.get_size" to ::match168,
        "Images.prefetch" to ::match168,
        "Keyboard.dismiss" to ::match146,
        "Keyboard.is_visible" to ::match146,
        "Linking.can_open_url" to ::match152,
        "Linking.open_settings" to ::match146,
        "Linking.open_url" to ::match152,
        "Localization.get_locales" to ::match146,
        "Localization.get_timezone" to ::match146,
        "Location.get_current" to ::match169,
        "NetInfo.fetch" to ::match146,
        "Notifications.cancel" to ::match171,
        "Notifications.get_device_token" to ::match146,
        "Notifications.request_permission" to ::match146,
        "Notifications.schedule" to ::match172,
        "Permissions.check" to ::match173,
        "Permissions.request" to ::match173,
        "SecureStore.clear" to ::match146,
        "SecureStore.delete_item" to ::match174,
        "SecureStore.get_item" to ::match174,
        "SecureStore.set_item" to ::match175,
        "Share.share" to ::match176,
        "Storage.all_keys" to ::match146,
        "Storage.clear" to ::match146,
        "Storage.delete" to ::match174,
        "Storage.get" to ::match174,
        "Storage.set" to ::match175,
        "WebViews.eval_js" to ::match177
    )
    private fun isBoolean(value: Any): Boolean = value is Boolean
    private fun isNumber(value: Any): Boolean = value is Number && value.toDouble().isFinite()
    private fun isInteger(value: Any): Boolean = value is Number && value.toDouble().isFinite() &&
        kotlin.math.abs(value.toDouble()) <= 9007199254740991.0 && value.toDouble() == value.toLong().toDouble()
    fun validate(name: String, props: JSONObject, partial: Boolean = false): Boolean {
        val fields = components[name] ?: return false
        if (!partial && fields.any { (key, field) -> field.required && !props.has(key) }) return false
        return props.keys().asSequence().all { key -> fields[key]?.let { it.allowed && it.matches(props.get(key)) } ?: false }
    }
    fun changes(name: String, keys: Iterable<String>): Int {
        val fields = components[name] ?: return LAYOUT or RECREATE
        var mask = 0
        for (key in keys) {
            if (fields[key]?.layout != false) mask = mask or LAYOUT
            if (fields[key]?.recreate == true) mask = mask or RECREATE
        }
        return mask
    }
    fun invalidatesLayout(name: String, changed: JSONObject): Boolean = changes(name, changed.keys().asSequence().asIterable()) and LAYOUT != 0
    fun validateRemoval(name: String, changed: JSONObject, removed: List<String>): Boolean {
        val fields = components[name] ?: return false
        return removed.toSet().size == removed.size && removed.all { key -> fields[key]?.let { !it.required && it.allowed && !changed.has(key) } ?: false }
    }
    fun requiresRecreation(name: String, changed: JSONObject, removed: List<String> = emptyList()): Boolean =
        changes(name, changed.keys().asSequence().asIterable() + removed) and RECREATE != 0
    fun normalize(name: String, changed: JSONObject, removed: List<String> = emptyList()): JSONObject {
        val result = JSONObject()
        for (key in changed.keys()) result.put(key, changed.get(key))
        for (key in removed) result.put(key, components[name]?.get(key)?.defaultValue ?: JSONObject.NULL)
        return result
    }
    fun validateCommand(name: String, method: String, args: JSONObject): Boolean = commands["$name.$method"]?.invoke(args) ?: false
    fun validateModule(name: String, method: String, args: JSONObject): Boolean {
        if (name in setOf("Host", "Layout", "Runtime")) return true
        return modules["$name.$method"]?.invoke(args) ?: false
    }
}
