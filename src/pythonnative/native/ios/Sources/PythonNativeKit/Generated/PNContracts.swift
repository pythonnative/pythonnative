import Foundation
import CoreFoundation

/// Executable generated contracts. No schema JSON is interpreted on the mount path.
public enum PNContracts {
    public static let fingerprint = "166f5173f9fabc1e15a071df2083d769de8c76d29c5276b57874948b38f55944"
    private struct Field {
        let matches: (Any) -> Bool
        let allowed: Bool
        let layout: Bool
        let recreate: Bool
        let required: Bool
        let defaultValue: Any
        init(_ matches: @escaping (Any) -> Bool, _ allowed: Bool, _ layout: Bool, _ recreate: Bool, _ required: Bool, _ defaultValue: Any) {
            self.matches = matches; self.allowed = allowed; self.layout = layout
            self.recreate = recreate; self.required = required; self.defaultValue = defaultValue
        }
    }
    public struct ChangeMask: OptionSet {
        public let rawValue: Int
        public init(rawValue: Int) { self.rawValue = rawValue }
        public static let layout = ChangeMask(rawValue: 1)
        public static let recreate = ChangeMask(rawValue: 2)
    }
    private static func match0(_ value: Any) -> Bool {
        guard let value = value as? [String: Any] else { return false }
        for (key, item) in value {
            let valid: Bool
            switch key {
            default: valid = true
            }
            if !valid { return false }
        }
        return true
    }
    private static func match1(_ value: Any) -> Bool {
        return isInteger(value)
    }
    private static func match3(_ value: Any) -> Bool {
        return value is String
    }
    private static func match2(_ value: Any) -> Bool {
        guard let value = value as? [Any] else { return false }
        return value.allSatisfy { match3($0) }
    }
    private static func match4(_ value: Any) -> Bool {
        return ((value as? String) == "left") || ((value as? String) == "right")
    }
    private static func match5(_ value: Any) -> Bool {
        return isBoolean(value)
    }
    private static func match6(_ value: Any) -> Bool {
        return ((value as? String) == "flex_start") || ((value as? String) == "center") || ((value as? String) == "flex_end") || ((value as? String) == "stretch") || ((value as? String) == "space_between") || ((value as? String) == "space_around") || ((value as? String) == "space_evenly")
    }
    private static func match7(_ value: Any) -> Bool {
        return ((value as? String) == "stretch") || ((value as? String) == "flex_start") || ((value as? String) == "center") || ((value as? String) == "flex_end") || ((value as? String) == "baseline") || ((value as? String) == "auto") || ((value as? String) == "start") || ((value as? String) == "leading") || ((value as? String) == "top") || ((value as? String) == "end") || ((value as? String) == "trailing") || ((value as? String) == "bottom") || ((value as? String) == "fill")
    }
    private static func match8(_ value: Any) -> Bool {
        return isNumber(value)
    }
    private static func match10(_ value: Any) -> Bool {
        guard let value = value as? [String: Any] else { return false }
        guard value["dark"] != nil else { return false }
        guard value["light"] != nil else { return false }
        for (key, item) in value {
            let valid: Bool
            switch key {
            case "dark": valid = match3(item)
            case "light": valid = match3(item)
            default: valid = false
            }
            if !valid { return false }
        }
        return true
    }
    private static func match9(_ value: Any) -> Bool {
        return match3(value) || match10(value)
    }
    private static func match11(_ value: Any) -> Bool {
        return ((value as? String) == "solid") || ((value as? String) == "dashed") || ((value as? String) == "dotted")
    }
    private static func match12(_ value: Any) -> Bool {
        return match1(value) || match8(value) || match3(value)
    }
    private static func match14(_ value: Any) -> Bool {
        return value is NSNull
    }
    private static func match13(_ value: Any) -> Bool {
        return match3(value) || match10(value) || match14(value)
    }
    private static func match15(_ value: Any) -> Bool {
        return ((value as? String) == "ltr") || ((value as? String) == "rtl")
    }
    private static func match16(_ value: Any) -> Bool {
        return ((value as? String) == "flex") || ((value as? String) == "none")
    }
    private static func match17(_ value: Any) -> Bool {
        return ((value as? String) == "row") || ((value as? String) == "column") || ((value as? String) == "row_reverse") || ((value as? String) == "column_reverse")
    }
    private static func match18(_ value: Any) -> Bool {
        return ((value as? String) == "nowrap") || ((value as? String) == "wrap") || ((value as? String) == "wrap_reverse")
    }
    private static func match19(_ value: Any) -> Bool {
        return ((value as? String) == "normal") || ((value as? String) == "bold") || ((value as? String) == "100") || ((value as? String) == "200") || ((value as? String) == "300") || ((value as? String) == "400") || ((value as? String) == "500") || ((value as? String) == "600") || ((value as? String) == "700") || ((value as? String) == "800") || ((value as? String) == "900")
    }
    private static func match21(_ value: Any) -> Bool {
        return true
    }
    private static func match20(_ value: Any) -> Bool {
        guard let value = value as? [Any] else { return false }
        return value.allSatisfy { match21($0) }
    }
    private static func match22(_ value: Any) -> Bool {
        return ((value as? String) == "flex_start") || ((value as? String) == "center") || ((value as? String) == "flex_end") || ((value as? String) == "space_between") || ((value as? String) == "space_around") || ((value as? String) == "space_evenly") || ((value as? String) == "start") || ((value as? String) == "leading") || ((value as? String) == "top") || ((value as? String) == "end") || ((value as? String) == "trailing") || ((value as? String) == "bottom")
    }
    private static func match24(_ value: Any) -> Bool {
        return ((value as? String) == "auto")
    }
    private static func match25(_ value: Any) -> Bool {
        guard let value = value as? [String: Any] else { return false }
        for (key, item) in value {
            let valid: Bool
            switch key {
            case "all": valid = match12(item)
            case "bottom": valid = match12(item)
            case "horizontal": valid = match12(item)
            case "left": valid = match12(item)
            case "right": valid = match12(item)
            case "top": valid = match12(item)
            case "vertical": valid = match12(item)
            default: valid = false
            }
            if !valid { return false }
        }
        return true
    }
    private static func match23(_ value: Any) -> Bool {
        return match1(value) || match8(value) || match3(value) || match24(value) || match25(value)
    }
    private static func match26(_ value: Any) -> Bool {
        return match1(value) || match8(value) || match3(value) || match24(value)
    }
    private static func match27(_ value: Any) -> Bool {
        return isBoolean(value)
    }
    private static func match28(_ value: Any) -> Bool {
        return ((value as? String) == "visible") || ((value as? String) == "hidden") || ((value as? String) == "scroll")
    }
    private static func match29(_ value: Any) -> Bool {
        return match1(value) || match8(value) || match3(value) || match25(value)
    }
    private static func match30(_ value: Any) -> Bool {
        return ((value as? String) == "auto") || ((value as? String) == "none") || ((value as? String) == "box_none") || ((value as? String) == "box_only")
    }
    private static func match31(_ value: Any) -> Bool {
        return ((value as? String) == "relative") || ((value as? String) == "absolute")
    }
    private static func match33(_ value: Any) -> Bool {
        guard let value = value as? [String: Any] else { return false }
        guard value["height"] != nil else { return false }
        guard value["width"] != nil else { return false }
        for (key, item) in value {
            let valid: Bool
            switch key {
            case "height": valid = match8(item)
            case "width": valid = match8(item)
            default: valid = false
            }
            if !valid { return false }
        }
        return true
    }
    private static func match34(_ value: Any) -> Bool {
        guard let value = value as? [Any] else { return false }
        return value.count == 2 && match8(value[0]) && match8(value[1])
    }
    private static func match35(_ value: Any) -> Bool {
        guard let value = value as? [Any] else { return false }
        return value.allSatisfy { match8($0) }
    }
    private static func match32(_ value: Any) -> Bool {
        return match33(value) || match34(value) || match35(value)
    }
    private static func match36(_ value: Any) -> Bool {
        return ((value as? String) == "small") || ((value as? String) == "large")
    }
    private static func match37(_ value: Any) -> Bool {
        return ((value as? String) == "left") || ((value as? String) == "center") || ((value as? String) == "right") || ((value as? String) == "justify") || ((value as? String) == "start") || ((value as? String) == "end")
    }
    private static func match38(_ value: Any) -> Bool {
        return ((value as? String) == "none") || ((value as? String) == "underline") || ((value as? String) == "line_through")
    }
    private static func match39(_ value: Any) -> Bool {
        return ((value as? String) == "none") || ((value as? String) == "uppercase") || ((value as? String) == "lowercase") || ((value as? String) == "capitalize")
    }
    private static func match42(_ value: Any) -> Bool {
        return match8(value) || match3(value)
    }
    private static func match41(_ value: Any) -> Bool {
        guard let value = value as? [String: Any] else { return false }
        guard value["rotate"] != nil else { return false }
        for (key, item) in value {
            let valid: Bool
            switch key {
            case "rotate": valid = match42(item)
            default: valid = false
            }
            if !valid { return false }
        }
        return true
    }
    private static func match43(_ value: Any) -> Bool {
        guard let value = value as? [String: Any] else { return false }
        guard value["rotate_x"] != nil else { return false }
        for (key, item) in value {
            let valid: Bool
            switch key {
            case "rotate_x": valid = match42(item)
            default: valid = false
            }
            if !valid { return false }
        }
        return true
    }
    private static func match44(_ value: Any) -> Bool {
        guard let value = value as? [String: Any] else { return false }
        guard value["rotate_y"] != nil else { return false }
        for (key, item) in value {
            let valid: Bool
            switch key {
            case "rotate_y": valid = match42(item)
            default: valid = false
            }
            if !valid { return false }
        }
        return true
    }
    private static func match45(_ value: Any) -> Bool {
        guard let value = value as? [String: Any] else { return false }
        guard value["rotate_z"] != nil else { return false }
        for (key, item) in value {
            let valid: Bool
            switch key {
            case "rotate_z": valid = match42(item)
            default: valid = false
            }
            if !valid { return false }
        }
        return true
    }
    private static func match46(_ value: Any) -> Bool {
        guard let value = value as? [String: Any] else { return false }
        guard value["scale"] != nil else { return false }
        for (key, item) in value {
            let valid: Bool
            switch key {
            case "scale": valid = match8(item)
            default: valid = false
            }
            if !valid { return false }
        }
        return true
    }
    private static func match47(_ value: Any) -> Bool {
        guard let value = value as? [String: Any] else { return false }
        guard value["scale_x"] != nil else { return false }
        for (key, item) in value {
            let valid: Bool
            switch key {
            case "scale_x": valid = match8(item)
            default: valid = false
            }
            if !valid { return false }
        }
        return true
    }
    private static func match48(_ value: Any) -> Bool {
        guard let value = value as? [String: Any] else { return false }
        guard value["scale_y"] != nil else { return false }
        for (key, item) in value {
            let valid: Bool
            switch key {
            case "scale_y": valid = match8(item)
            default: valid = false
            }
            if !valid { return false }
        }
        return true
    }
    private static func match49(_ value: Any) -> Bool {
        guard let value = value as? [String: Any] else { return false }
        for (key, item) in value {
            let valid: Bool
            switch key {
            case "translate_x": valid = match8(item)
            case "translate_y": valid = match8(item)
            default: valid = false
            }
            if !valid { return false }
        }
        return true
    }
    private static func match50(_ value: Any) -> Bool {
        guard let value = value as? [String: Any] else { return false }
        guard value["skew_x"] != nil else { return false }
        for (key, item) in value {
            let valid: Bool
            switch key {
            case "skew_x": valid = match42(item)
            default: valid = false
            }
            if !valid { return false }
        }
        return true
    }
    private static func match51(_ value: Any) -> Bool {
        guard let value = value as? [String: Any] else { return false }
        guard value["skew_y"] != nil else { return false }
        for (key, item) in value {
            let valid: Bool
            switch key {
            case "skew_y": valid = match42(item)
            default: valid = false
            }
            if !valid { return false }
        }
        return true
    }
    private static func match52(_ value: Any) -> Bool {
        guard let value = value as? [String: Any] else { return false }
        guard value["perspective"] != nil else { return false }
        for (key, item) in value {
            let valid: Bool
            switch key {
            case "perspective": valid = match8(item)
            default: valid = false
            }
            if !valid { return false }
        }
        return true
    }
    private static func match54(_ value: Any) -> Bool {
        return true
    }
    private static func match53(_ value: Any) -> Bool {
        guard let value = value as? [String: Any] else { return false }
        for (key, item) in value {
            let valid: Bool
            switch key {
            default: valid = match54(item)
            }
            if !valid { return false }
        }
        return true
    }
    private static func match56(_ value: Any) -> Bool {
        return match41(value) || match43(value) || match44(value) || match45(value) || match46(value) || match47(value) || match48(value) || match49(value) || match50(value) || match51(value) || match52(value) || match53(value)
    }
    private static func match55(_ value: Any) -> Bool {
        guard let value = value as? [Any] else { return false }
        return value.allSatisfy { match56($0) }
    }
    private static func match40(_ value: Any) -> Bool {
        return match41(value) || match43(value) || match44(value) || match45(value) || match46(value) || match47(value) || match48(value) || match49(value) || match50(value) || match51(value) || match52(value) || match53(value) || match55(value)
    }
    private static func component0() -> [String: Field] { [
        "_pn_animated_events": field0,
        "_pn_edit_revision": field1,
        "_pn_events": field2,
        "_pn_header_slot": field3,
        "_pn_layout": field4,
        "_pn_list_key": field5,
        "accessibility_role": field6,
        "align_content": field7,
        "align_items": field8,
        "align_self": field8,
        "animating": field9,
        "aspect_ratio": field10,
        "background_color": field11,
        "bold": field12,
        "border_bottom_color": field13,
        "border_bottom_left_radius": field14,
        "border_bottom_right_radius": field14,
        "border_bottom_width": field10,
        "border_color": field13,
        "border_left_color": field13,
        "border_left_width": field10,
        "border_radius": field14,
        "border_right_color": field13,
        "border_right_width": field10,
        "border_style": field15,
        "border_top_color": field13,
        "border_top_left_radius": field14,
        "border_top_right_radius": field14,
        "border_top_width": field10,
        "border_width": field10,
        "bottom": field16,
        "color": field17,
        "column_gap": field10,
        "direction": field18,
        "display": field19,
        "elevation": field14,
        "end": field16,
        "flex": field10,
        "flex_basis": field16,
        "flex_direction": field20,
        "flex_grow": field10,
        "flex_shrink": field10,
        "flex_wrap": field21,
        "font_family": field22,
        "font_size": field10,
        "font_weight": field23,
        "gap": field10,
        "gestures": field24,
        "height": field16,
        "italic": field12,
        "justify_content": field25,
        "left": field16,
        "letter_spacing": field10,
        "line_height": field10,
        "margin": field26,
        "margin_bottom": field27,
        "margin_end": field27,
        "margin_horizontal": field27,
        "margin_left": field27,
        "margin_right": field27,
        "margin_start": field27,
        "margin_top": field27,
        "margin_vertical": field27,
        "max_height": field16,
        "max_lines": field28,
        "max_width": field16,
        "min_height": field16,
        "min_width": field16,
        "on_layout": field29,
        "opacity": field30,
        "overflow": field31,
        "padding": field32,
        "padding_bottom": field16,
        "padding_end": field16,
        "padding_horizontal": field16,
        "padding_left": field16,
        "padding_right": field16,
        "padding_start": field16,
        "padding_top": field16,
        "padding_vertical": field16,
        "placeholder_color": field13,
        "pointer_events": field33,
        "position": field34,
        "ref": field35,
        "right": field16,
        "row_gap": field10,
        "shadow_color": field13,
        "shadow_offset": field36,
        "shadow_opacity": field14,
        "shadow_radius": field14,
        "size": field37,
        "spacing": field10,
        "start": field16,
        "text_align": field38,
        "text_decoration": field39,
        "text_shadow_color": field13,
        "text_shadow_offset": field36,
        "text_shadow_radius": field14,
        "text_transform": field40,
        "tint_color": field13,
        "top": field16,
        "transform": field41,
        "width": field16,
        "z_index": field42
    ] }
    private static func match57(_ value: Any) -> Bool {
        return match3(value) || match14(value)
    }
    private static func match58(_ value: Any) -> Bool {
        return match5(value) || match14(value)
    }
    private static func match59(_ value: Any) -> Bool {
        return ((value as? String) == "light") || ((value as? String) == "dark") || ((value as? String) == "regular") || ((value as? String) == "prominent") || ((value as? String) == "extra_light") || ((value as? String) == "system_thin_material") || ((value as? String) == "system_material") || ((value as? String) == "system_thick_material") || ((value as? String) == "system_chrome_material")
    }
    private static func component1() -> [String: Field] { [
        "_pn_animated_events": field0,
        "_pn_edit_revision": field1,
        "_pn_events": field2,
        "_pn_header_slot": field3,
        "_pn_layout": field4,
        "_pn_list_key": field5,
        "accessibility_label": field43,
        "accessibility_role": field6,
        "accessible": field44,
        "align_content": field7,
        "align_items": field8,
        "align_self": field8,
        "aspect_ratio": field10,
        "background_color": field11,
        "blur_type": field45,
        "bold": field12,
        "border_bottom_color": field13,
        "border_bottom_left_radius": field14,
        "border_bottom_right_radius": field14,
        "border_bottom_width": field10,
        "border_color": field13,
        "border_left_color": field13,
        "border_left_width": field10,
        "border_radius": field14,
        "border_right_color": field13,
        "border_right_width": field10,
        "border_style": field15,
        "border_top_color": field13,
        "border_top_left_radius": field14,
        "border_top_right_radius": field14,
        "border_top_width": field10,
        "border_width": field10,
        "bottom": field16,
        "color": field11,
        "column_gap": field10,
        "direction": field18,
        "display": field19,
        "elevation": field14,
        "end": field16,
        "flex": field10,
        "flex_basis": field16,
        "flex_direction": field20,
        "flex_grow": field10,
        "flex_shrink": field10,
        "flex_wrap": field21,
        "font_family": field22,
        "font_size": field10,
        "font_weight": field23,
        "gap": field10,
        "gestures": field24,
        "height": field16,
        "intensity": field46,
        "italic": field12,
        "justify_content": field25,
        "left": field16,
        "letter_spacing": field10,
        "line_height": field10,
        "margin": field26,
        "margin_bottom": field27,
        "margin_end": field27,
        "margin_horizontal": field27,
        "margin_left": field27,
        "margin_right": field27,
        "margin_start": field27,
        "margin_top": field27,
        "margin_vertical": field27,
        "max_height": field16,
        "max_lines": field28,
        "max_width": field16,
        "min_height": field16,
        "min_width": field16,
        "on_layout": field29,
        "opacity": field30,
        "overflow": field31,
        "padding": field32,
        "padding_bottom": field16,
        "padding_end": field16,
        "padding_horizontal": field16,
        "padding_left": field16,
        "padding_right": field16,
        "padding_start": field16,
        "padding_top": field16,
        "padding_vertical": field16,
        "placeholder_color": field13,
        "pointer_events": field33,
        "position": field34,
        "ref": field35,
        "right": field16,
        "row_gap": field10,
        "shadow_color": field13,
        "shadow_offset": field36,
        "shadow_opacity": field14,
        "shadow_radius": field14,
        "spacing": field10,
        "start": field16,
        "test_id": field43,
        "text_align": field38,
        "text_decoration": field39,
        "text_shadow_color": field13,
        "text_shadow_offset": field36,
        "text_shadow_radius": field14,
        "text_transform": field40,
        "tint_color": field13,
        "top": field16,
        "transform": field41,
        "width": field16,
        "z_index": field42
    ] }
    private static func match62(_ value: Any) -> Bool {
        guard let value = value as? [String: Any] else { return false }
        guard value["name"] != nil else { return false }
        for (key, item) in value {
            let valid: Bool
            switch key {
            case "label": valid = match3(item)
            case "name": valid = match3(item)
            default: valid = false
            }
            if !valid { return false }
        }
        return true
    }
    private static func match61(_ value: Any) -> Bool {
        guard let value = value as? [Any] else { return false }
        return value.allSatisfy { match62($0) }
    }
    private static func match60(_ value: Any) -> Bool {
        return match61(value) || match14(value)
    }
    private static func match64(_ value: Any) -> Bool {
        return ((value as? String) == "none") || ((value as? String) == "polite") || ((value as? String) == "assertive")
    }
    private static func match63(_ value: Any) -> Bool {
        return match64(value) || match14(value)
    }
    private static func match68(_ value: Any) -> Bool {
        return ((value as? String) == "mixed")
    }
    private static func match67(_ value: Any) -> Bool {
        return match5(value) || match68(value)
    }
    private static func match66(_ value: Any) -> Bool {
        guard let value = value as? [String: Any] else { return false }
        for (key, item) in value {
            let valid: Bool
            switch key {
            case "busy": valid = match5(item)
            case "checked": valid = match67(item)
            case "disabled": valid = match5(item)
            case "expanded": valid = match5(item)
            case "selected": valid = match5(item)
            default: valid = false
            }
            if !valid { return false }
        }
        return true
    }
    private static func match65(_ value: Any) -> Bool {
        return match66(value) || match14(value)
    }
    private static func match70(_ value: Any) -> Bool {
        guard let value = value as? [String: Any] else { return false }
        for (key, item) in value {
            let valid: Bool
            switch key {
            case "max": valid = match8(item)
            case "min": valid = match8(item)
            case "now": valid = match8(item)
            case "text": valid = match3(item)
            default: valid = false
            }
            if !valid { return false }
        }
        return true
    }
    private static func match69(_ value: Any) -> Bool {
        return match3(value) || match70(value) || match14(value)
    }
    private static func match72(_ value: Any) -> Bool {
        return ((value as? String) == "auto") || ((value as? String) == "yes") || ((value as? String) == "no") || ((value as? String) == "no_hide_descendants")
    }
    private static func match71(_ value: Any) -> Bool {
        return match72(value) || match14(value)
    }
    private static func match73(_ value: Any) -> Bool {
        return match27(value) || match14(value)
    }
    private static func match74(_ value: Any) -> Bool {
        return match27(value) || match14(value)
    }
    private static func component2() -> [String: Field] { [
        "_pn_animated_events": field0,
        "_pn_edit_revision": field1,
        "_pn_events": field2,
        "_pn_header_slot": field3,
        "_pn_layout": field4,
        "_pn_list_key": field5,
        "accessibility_actions": field47,
        "accessibility_hint": field43,
        "accessibility_label": field43,
        "accessibility_live_region": field48,
        "accessibility_role": field43,
        "accessibility_state": field49,
        "accessibility_value": field50,
        "accessible": field44,
        "align_content": field7,
        "align_items": field8,
        "align_self": field8,
        "aspect_ratio": field10,
        "background_color": field11,
        "bold": field12,
        "border_bottom_color": field13,
        "border_bottom_left_radius": field14,
        "border_bottom_right_radius": field14,
        "border_bottom_width": field10,
        "border_color": field13,
        "border_left_color": field13,
        "border_left_width": field10,
        "border_radius": field14,
        "border_right_color": field13,
        "border_right_width": field10,
        "border_style": field15,
        "border_top_color": field13,
        "border_top_left_radius": field14,
        "border_top_right_radius": field14,
        "border_top_width": field10,
        "border_width": field10,
        "bottom": field16,
        "color": field11,
        "column_gap": field10,
        "direction": field18,
        "disabled": field51,
        "display": field19,
        "elevation": field14,
        "end": field16,
        "flex": field10,
        "flex_basis": field16,
        "flex_direction": field20,
        "flex_grow": field10,
        "flex_shrink": field10,
        "flex_wrap": field21,
        "font_family": field22,
        "font_size": field10,
        "font_weight": field23,
        "gap": field10,
        "gestures": field24,
        "height": field16,
        "important_for_accessibility": field52,
        "italic": field12,
        "justify_content": field25,
        "left": field16,
        "letter_spacing": field10,
        "line_height": field10,
        "margin": field26,
        "margin_bottom": field27,
        "margin_end": field27,
        "margin_horizontal": field27,
        "margin_left": field27,
        "margin_right": field27,
        "margin_start": field27,
        "margin_top": field27,
        "margin_vertical": field27,
        "max_height": field16,
        "max_lines": field28,
        "max_width": field16,
        "min_height": field16,
        "min_width": field16,
        "on_accessibility_action": field53,
        "on_layout": field29,
        "on_press": field54,
        "opacity": field30,
        "overflow": field31,
        "padding": field32,
        "padding_bottom": field16,
        "padding_end": field16,
        "padding_horizontal": field16,
        "padding_left": field16,
        "padding_right": field16,
        "padding_start": field16,
        "padding_top": field16,
        "padding_vertical": field16,
        "placeholder_color": field13,
        "pointer_events": field33,
        "position": field34,
        "ref": field35,
        "right": field16,
        "row_gap": field10,
        "shadow_color": field13,
        "shadow_offset": field36,
        "shadow_opacity": field14,
        "shadow_radius": field14,
        "spacing": field10,
        "start": field16,
        "test_id": field43,
        "text_align": field38,
        "text_decoration": field39,
        "text_shadow_color": field13,
        "text_shadow_offset": field36,
        "text_shadow_radius": field14,
        "text_transform": field40,
        "tint_color": field13,
        "title": field55,
        "top": field16,
        "transform": field41,
        "width": field16,
        "z_index": field42
    ] }
    private static func match75(_ value: Any) -> Bool {
        return match27(value) || match14(value)
    }
    private static func component3() -> [String: Field] { [
        "_pn_animated_events": field0,
        "_pn_edit_revision": field1,
        "_pn_events": field2,
        "_pn_header_slot": field3,
        "_pn_layout": field4,
        "_pn_list_key": field5,
        "accessibility_actions": field47,
        "accessibility_hint": field43,
        "accessibility_label": field43,
        "accessibility_live_region": field48,
        "accessibility_role": field6,
        "accessibility_state": field49,
        "accessibility_value": field50,
        "accessible": field44,
        "align_content": field7,
        "align_items": field8,
        "align_self": field8,
        "aspect_ratio": field10,
        "background_color": field11,
        "bold": field12,
        "border_bottom_color": field13,
        "border_bottom_left_radius": field14,
        "border_bottom_right_radius": field14,
        "border_bottom_width": field10,
        "border_color": field13,
        "border_left_color": field13,
        "border_left_width": field10,
        "border_radius": field14,
        "border_right_color": field13,
        "border_right_width": field10,
        "border_style": field15,
        "border_top_color": field13,
        "border_top_left_radius": field14,
        "border_top_right_radius": field14,
        "border_top_width": field10,
        "border_width": field10,
        "bottom": field16,
        "color": field17,
        "column_gap": field10,
        "direction": field18,
        "disabled": field51,
        "display": field19,
        "elevation": field14,
        "end": field16,
        "flex": field10,
        "flex_basis": field16,
        "flex_direction": field20,
        "flex_grow": field10,
        "flex_shrink": field10,
        "flex_wrap": field21,
        "font_family": field22,
        "font_size": field10,
        "font_weight": field23,
        "gap": field10,
        "gestures": field24,
        "height": field16,
        "important_for_accessibility": field52,
        "italic": field12,
        "justify_content": field25,
        "label": field43,
        "left": field16,
        "letter_spacing": field10,
        "line_height": field10,
        "margin": field26,
        "margin_bottom": field27,
        "margin_end": field27,
        "margin_horizontal": field27,
        "margin_left": field27,
        "margin_right": field27,
        "margin_start": field27,
        "margin_top": field27,
        "margin_vertical": field27,
        "max_height": field16,
        "max_lines": field28,
        "max_width": field16,
        "min_height": field16,
        "min_width": field16,
        "on_accessibility_action": field53,
        "on_change": field56,
        "on_layout": field29,
        "opacity": field30,
        "overflow": field31,
        "padding": field32,
        "padding_bottom": field16,
        "padding_end": field16,
        "padding_horizontal": field16,
        "padding_left": field16,
        "padding_right": field16,
        "padding_start": field16,
        "padding_top": field16,
        "padding_vertical": field16,
        "placeholder_color": field13,
        "pointer_events": field33,
        "position": field34,
        "ref": field35,
        "right": field16,
        "row_gap": field10,
        "shadow_color": field13,
        "shadow_offset": field36,
        "shadow_opacity": field14,
        "shadow_radius": field14,
        "spacing": field10,
        "start": field16,
        "test_id": field43,
        "text_align": field38,
        "text_decoration": field39,
        "text_shadow_color": field13,
        "text_shadow_offset": field36,
        "text_shadow_radius": field14,
        "text_transform": field40,
        "tint_color": field13,
        "top": field16,
        "transform": field41,
        "value": field57,
        "width": field16,
        "z_index": field42
    ] }
    private static func match77(_ value: Any) -> Bool {
        guard let value = value as? [String: Any] else { return false }
        for (key, item) in value {
            let valid: Bool
            switch key {
            default: valid = match8(item)
            }
            if !valid { return false }
        }
        return true
    }
    private static func match76(_ value: Any) -> Bool {
        return match8(value) || match77(value) || match14(value)
    }
    private static func component4() -> [String: Field] { [
        "_pn_animated_events": field0,
        "_pn_edit_revision": field1,
        "_pn_events": field2,
        "_pn_header_slot": field3,
        "_pn_layout": field4,
        "_pn_list_key": field5,
        "accessibility_actions": field47,
        "accessibility_hint": field43,
        "accessibility_label": field43,
        "accessibility_live_region": field48,
        "accessibility_role": field43,
        "accessibility_state": field49,
        "accessibility_value": field50,
        "accessible": field44,
        "align_content": field7,
        "align_items": field8,
        "align_self": field8,
        "aspect_ratio": field10,
        "background_color": field11,
        "bold": field12,
        "border_bottom_color": field13,
        "border_bottom_left_radius": field14,
        "border_bottom_right_radius": field14,
        "border_bottom_width": field10,
        "border_color": field13,
        "border_left_color": field13,
        "border_left_width": field10,
        "border_radius": field14,
        "border_right_color": field13,
        "border_right_width": field10,
        "border_style": field15,
        "border_top_color": field13,
        "border_top_left_radius": field14,
        "border_top_right_radius": field14,
        "border_top_width": field10,
        "border_width": field10,
        "bottom": field16,
        "color": field11,
        "column_gap": field10,
        "direction": field18,
        "display": field19,
        "elevation": field14,
        "end": field16,
        "flex": field10,
        "flex_basis": field16,
        "flex_direction": field20,
        "flex_grow": field10,
        "flex_shrink": field10,
        "flex_wrap": field21,
        "font_family": field22,
        "font_size": field10,
        "font_weight": field23,
        "gap": field10,
        "gestures": field24,
        "height": field16,
        "hit_slop": field58,
        "important_for_accessibility": field52,
        "italic": field12,
        "justify_content": field25,
        "left": field16,
        "letter_spacing": field10,
        "line_height": field10,
        "margin": field26,
        "margin_bottom": field27,
        "margin_end": field27,
        "margin_horizontal": field27,
        "margin_left": field27,
        "margin_right": field27,
        "margin_start": field27,
        "margin_top": field27,
        "margin_vertical": field27,
        "max_height": field16,
        "max_lines": field28,
        "max_width": field16,
        "min_height": field16,
        "min_width": field16,
        "on_accessibility_action": field53,
        "on_layout": field29,
        "opacity": field30,
        "overflow": field31,
        "padding": field32,
        "padding_bottom": field16,
        "padding_end": field16,
        "padding_horizontal": field16,
        "padding_left": field16,
        "padding_right": field16,
        "padding_start": field16,
        "padding_top": field16,
        "padding_vertical": field16,
        "placeholder_color": field13,
        "pointer_events": field33,
        "position": field34,
        "ref": field35,
        "right": field16,
        "row_gap": field10,
        "shadow_color": field13,
        "shadow_offset": field36,
        "shadow_opacity": field14,
        "shadow_radius": field14,
        "spacing": field10,
        "start": field16,
        "test_id": field43,
        "text_align": field38,
        "text_decoration": field39,
        "text_shadow_color": field13,
        "text_shadow_offset": field36,
        "text_shadow_radius": field14,
        "text_transform": field40,
        "tint_color": field13,
        "top": field16,
        "transform": field41,
        "width": field16,
        "z_index": field42
    ] }
    private static func match78(_ value: Any) -> Bool {
        return ((value as? String) == "date") || ((value as? String) == "time") || ((value as? String) == "datetime")
    }
    private static func component5() -> [String: Field] { [
        "_pn_animated_events": field0,
        "_pn_edit_revision": field1,
        "_pn_events": field2,
        "_pn_header_slot": field3,
        "_pn_layout": field4,
        "_pn_list_key": field5,
        "accessibility_actions": field47,
        "accessibility_label": field43,
        "accessibility_live_region": field48,
        "accessibility_role": field6,
        "accessibility_state": field49,
        "accessibility_value": field50,
        "accessible": field44,
        "align_content": field7,
        "align_items": field8,
        "align_self": field8,
        "aspect_ratio": field10,
        "background_color": field11,
        "bold": field12,
        "border_bottom_color": field13,
        "border_bottom_left_radius": field14,
        "border_bottom_right_radius": field14,
        "border_bottom_width": field10,
        "border_color": field13,
        "border_left_color": field13,
        "border_left_width": field10,
        "border_radius": field14,
        "border_right_color": field13,
        "border_right_width": field10,
        "border_style": field15,
        "border_top_color": field13,
        "border_top_left_radius": field14,
        "border_top_right_radius": field14,
        "border_top_width": field10,
        "border_width": field10,
        "bottom": field16,
        "color": field11,
        "column_gap": field10,
        "direction": field18,
        "disabled": field51,
        "display": field19,
        "elevation": field14,
        "end": field16,
        "flex": field10,
        "flex_basis": field16,
        "flex_direction": field20,
        "flex_grow": field10,
        "flex_shrink": field10,
        "flex_wrap": field21,
        "font_family": field22,
        "font_size": field10,
        "font_weight": field23,
        "gap": field10,
        "gestures": field24,
        "height": field16,
        "important_for_accessibility": field52,
        "italic": field12,
        "justify_content": field25,
        "left": field16,
        "letter_spacing": field10,
        "line_height": field10,
        "margin": field26,
        "margin_bottom": field27,
        "margin_end": field27,
        "margin_horizontal": field27,
        "margin_left": field27,
        "margin_right": field27,
        "margin_start": field27,
        "margin_top": field27,
        "margin_vertical": field27,
        "max_height": field16,
        "max_lines": field28,
        "max_width": field16,
        "maximum": field43,
        "min_height": field16,
        "min_width": field16,
        "minimum": field43,
        "mode": field59,
        "on_accessibility_action": field53,
        "on_change": field53,
        "on_layout": field29,
        "opacity": field30,
        "overflow": field31,
        "padding": field32,
        "padding_bottom": field16,
        "padding_end": field16,
        "padding_horizontal": field16,
        "padding_left": field16,
        "padding_right": field16,
        "padding_start": field16,
        "padding_top": field16,
        "padding_vertical": field16,
        "placeholder_color": field13,
        "pointer_events": field33,
        "position": field34,
        "ref": field35,
        "right": field16,
        "row_gap": field10,
        "shadow_color": field13,
        "shadow_offset": field36,
        "shadow_opacity": field14,
        "shadow_radius": field14,
        "spacing": field10,
        "start": field16,
        "test_id": field43,
        "text_align": field38,
        "text_decoration": field39,
        "text_shadow_color": field13,
        "text_shadow_offset": field36,
        "text_shadow_radius": field14,
        "text_transform": field40,
        "tint_color": field13,
        "top": field16,
        "transform": field41,
        "value": field60,
        "width": field16,
        "z_index": field42
    ] }
    private static func match79(_ value: Any) -> Bool {
        return match8(value) || match14(value)
    }
    private static func match81(_ value: Any) -> Bool {
        guard let value = value as? [String: Any] else { return false }
        for (key, item) in value {
            let valid: Bool
            switch key {
            default: valid = match3(item)
            }
            if !valid { return false }
        }
        return true
    }
    private static func match80(_ value: Any) -> Bool {
        return match81(value) || match14(value)
    }
    private static func match82(_ value: Any) -> Bool {
        return match27(value) || match14(value)
    }
    private static func match84(_ value: Any) -> Bool {
        return ((value as? String) == "cover") || ((value as? String) == "contain") || ((value as? String) == "stretch") || ((value as? String) == "center")
    }
    private static func match83(_ value: Any) -> Bool {
        return match84(value) || match14(value)
    }
    private static func component6() -> [String: Field] { [
        "_pn_animated_events": field0,
        "_pn_edit_revision": field1,
        "_pn_events": field2,
        "_pn_header_slot": field3,
        "_pn_layout": field4,
        "_pn_list_key": field5,
        "accessibility_actions": field47,
        "accessibility_label": field43,
        "accessibility_live_region": field48,
        "accessibility_role": field43,
        "accessibility_state": field49,
        "accessibility_value": field50,
        "accessible": field44,
        "align_content": field7,
        "align_items": field8,
        "align_self": field8,
        "aspect_ratio": field10,
        "background_color": field11,
        "blur_radius": field61,
        "bold": field12,
        "border_bottom_color": field13,
        "border_bottom_left_radius": field14,
        "border_bottom_right_radius": field14,
        "border_bottom_width": field10,
        "border_color": field13,
        "border_left_color": field13,
        "border_left_width": field10,
        "border_radius": field14,
        "border_right_color": field13,
        "border_right_width": field10,
        "border_style": field15,
        "border_top_color": field13,
        "border_top_left_radius": field14,
        "border_top_right_radius": field14,
        "border_top_width": field10,
        "border_width": field10,
        "bottom": field16,
        "color": field11,
        "column_gap": field10,
        "default_source": field43,
        "direction": field18,
        "display": field19,
        "elevation": field14,
        "end": field16,
        "fade_duration": field61,
        "flex": field10,
        "flex_basis": field16,
        "flex_direction": field20,
        "flex_grow": field10,
        "flex_shrink": field10,
        "flex_wrap": field21,
        "font_family": field22,
        "font_size": field10,
        "font_weight": field23,
        "gap": field10,
        "gestures": field24,
        "headers": field62,
        "height": field16,
        "important_for_accessibility": field52,
        "italic": field12,
        "justify_content": field25,
        "left": field16,
        "letter_spacing": field10,
        "line_height": field10,
        "margin": field26,
        "margin_bottom": field27,
        "margin_end": field27,
        "margin_horizontal": field27,
        "margin_left": field27,
        "margin_right": field27,
        "margin_start": field27,
        "margin_top": field27,
        "margin_vertical": field27,
        "max_height": field16,
        "max_lines": field28,
        "max_width": field16,
        "min_height": field16,
        "min_width": field16,
        "on_accessibility_action": field53,
        "on_error": field53,
        "on_layout": field29,
        "on_load": field63,
        "on_load_end": field54,
        "on_load_start": field54,
        "opacity": field30,
        "overflow": field31,
        "padding": field32,
        "padding_bottom": field16,
        "padding_end": field16,
        "padding_horizontal": field16,
        "padding_left": field16,
        "padding_right": field16,
        "padding_start": field16,
        "padding_top": field16,
        "padding_vertical": field16,
        "placeholder_color": field64,
        "pointer_events": field33,
        "position": field34,
        "ref": field35,
        "right": field16,
        "row_gap": field10,
        "scale_type": field65,
        "shadow_color": field13,
        "shadow_offset": field36,
        "shadow_opacity": field14,
        "shadow_radius": field14,
        "source": field55,
        "spacing": field10,
        "start": field16,
        "test_id": field43,
        "text_align": field38,
        "text_decoration": field39,
        "text_shadow_color": field13,
        "text_shadow_offset": field36,
        "text_shadow_radius": field14,
        "text_transform": field40,
        "tint_color": field64,
        "top": field16,
        "transform": field41,
        "width": field16,
        "z_index": field42
    ] }
    private static func component7() -> [String: Field] { [
        "_pn_animated_events": field0,
        "_pn_edit_revision": field1,
        "_pn_events": field2,
        "_pn_header_slot": field3,
        "_pn_layout": field4,
        "_pn_list_key": field5,
        "accessibility_actions": field47,
        "accessibility_label": field43,
        "accessibility_live_region": field48,
        "accessibility_role": field6,
        "accessibility_state": field49,
        "accessibility_value": field50,
        "accessible": field44,
        "align_content": field7,
        "align_items": field8,
        "align_self": field8,
        "aspect_ratio": field10,
        "background_color": field11,
        "bold": field12,
        "border_bottom_color": field13,
        "border_bottom_left_radius": field14,
        "border_bottom_right_radius": field14,
        "border_bottom_width": field10,
        "border_color": field13,
        "border_left_color": field13,
        "border_left_width": field10,
        "border_radius": field14,
        "border_right_color": field13,
        "border_right_width": field10,
        "border_style": field15,
        "border_top_color": field13,
        "border_top_left_radius": field14,
        "border_top_right_radius": field14,
        "border_top_width": field10,
        "border_width": field10,
        "bottom": field16,
        "color": field11,
        "column_gap": field10,
        "direction": field18,
        "display": field19,
        "elevation": field14,
        "end": field16,
        "flex": field10,
        "flex_basis": field16,
        "flex_direction": field20,
        "flex_grow": field10,
        "flex_shrink": field10,
        "flex_wrap": field21,
        "font_family": field22,
        "font_size": field10,
        "font_weight": field23,
        "gap": field10,
        "gestures": field24,
        "height": field16,
        "important_for_accessibility": field52,
        "italic": field12,
        "justify_content": field25,
        "left": field16,
        "letter_spacing": field10,
        "line_height": field10,
        "margin": field26,
        "margin_bottom": field27,
        "margin_end": field27,
        "margin_horizontal": field27,
        "margin_left": field27,
        "margin_right": field27,
        "margin_start": field27,
        "margin_top": field27,
        "margin_vertical": field27,
        "max_height": field16,
        "max_lines": field28,
        "max_width": field16,
        "min_height": field16,
        "min_width": field16,
        "on_accessibility_action": field53,
        "on_layout": field29,
        "opacity": field30,
        "overflow": field31,
        "padding": field32,
        "padding_bottom": field16,
        "padding_end": field16,
        "padding_horizontal": field16,
        "padding_left": field16,
        "padding_right": field16,
        "padding_start": field16,
        "padding_top": field16,
        "padding_vertical": field16,
        "placeholder_color": field13,
        "pointer_events": field33,
        "position": field34,
        "ref": field35,
        "right": field16,
        "row_gap": field10,
        "scale_type": field65,
        "shadow_color": field13,
        "shadow_offset": field36,
        "shadow_opacity": field14,
        "shadow_radius": field14,
        "source": field55,
        "spacing": field10,
        "start": field16,
        "test_id": field43,
        "text_align": field38,
        "text_decoration": field39,
        "text_shadow_color": field13,
        "text_shadow_offset": field36,
        "text_shadow_radius": field14,
        "text_transform": field40,
        "tint_color": field13,
        "top": field16,
        "transform": field41,
        "width": field16,
        "z_index": field42
    ] }
    private static func match85(_ value: Any) -> Bool {
        return ((value as? String) == "padding") || ((value as? String) == "position") || ((value as? String) == "height")
    }
    private static func component8() -> [String: Field] { [
        "_pn_animated_events": field0,
        "_pn_edit_revision": field1,
        "_pn_events": field2,
        "_pn_header_slot": field3,
        "_pn_layout": field4,
        "_pn_list_key": field5,
        "accessibility_role": field6,
        "align_content": field7,
        "align_items": field8,
        "align_self": field8,
        "aspect_ratio": field10,
        "background_color": field11,
        "behavior": field66,
        "bold": field12,
        "border_bottom_color": field13,
        "border_bottom_left_radius": field14,
        "border_bottom_right_radius": field14,
        "border_bottom_width": field10,
        "border_color": field13,
        "border_left_color": field13,
        "border_left_width": field10,
        "border_radius": field14,
        "border_right_color": field13,
        "border_right_width": field10,
        "border_style": field15,
        "border_top_color": field13,
        "border_top_left_radius": field14,
        "border_top_right_radius": field14,
        "border_top_width": field10,
        "border_width": field10,
        "bottom": field16,
        "color": field11,
        "column_gap": field10,
        "direction": field18,
        "display": field19,
        "elevation": field14,
        "end": field16,
        "flex": field10,
        "flex_basis": field16,
        "flex_direction": field20,
        "flex_grow": field10,
        "flex_shrink": field10,
        "flex_wrap": field21,
        "font_family": field22,
        "font_size": field10,
        "font_weight": field23,
        "gap": field10,
        "gestures": field24,
        "height": field16,
        "italic": field12,
        "justify_content": field25,
        "keyboard_vertical_offset": field67,
        "left": field16,
        "letter_spacing": field10,
        "line_height": field10,
        "margin": field26,
        "margin_bottom": field27,
        "margin_end": field27,
        "margin_horizontal": field27,
        "margin_left": field27,
        "margin_right": field27,
        "margin_start": field27,
        "margin_top": field27,
        "margin_vertical": field27,
        "max_height": field16,
        "max_lines": field28,
        "max_width": field16,
        "min_height": field16,
        "min_width": field16,
        "on_layout": field29,
        "opacity": field30,
        "overflow": field31,
        "padding": field32,
        "padding_bottom": field16,
        "padding_end": field16,
        "padding_horizontal": field16,
        "padding_left": field16,
        "padding_right": field16,
        "padding_start": field16,
        "padding_top": field16,
        "padding_vertical": field16,
        "placeholder_color": field13,
        "pointer_events": field33,
        "position": field34,
        "ref": field35,
        "right": field16,
        "row_gap": field10,
        "shadow_color": field13,
        "shadow_offset": field36,
        "shadow_opacity": field14,
        "shadow_radius": field14,
        "spacing": field10,
        "start": field16,
        "text_align": field38,
        "text_decoration": field39,
        "text_shadow_color": field13,
        "text_shadow_offset": field36,
        "text_shadow_radius": field14,
        "text_transform": field40,
        "tint_color": field13,
        "top": field16,
        "transform": field41,
        "width": field16,
        "z_index": field42
    ] }
    private static func match86(_ value: Any) -> Bool {
        guard let value = value as? [Any] else { return false }
        return value.allSatisfy { match9($0) }
    }
    private static func match87(_ value: Any) -> Bool {
        return match35(value) || match14(value)
    }
    private static func component9() -> [String: Field] { [
        "_pn_animated_events": field0,
        "_pn_edit_revision": field1,
        "_pn_events": field2,
        "_pn_header_slot": field3,
        "_pn_layout": field4,
        "_pn_list_key": field5,
        "accessibility_label": field43,
        "accessibility_role": field6,
        "accessible": field44,
        "align_content": field7,
        "align_items": field8,
        "align_self": field8,
        "aspect_ratio": field10,
        "background_color": field11,
        "bold": field12,
        "border_bottom_color": field13,
        "border_bottom_left_radius": field14,
        "border_bottom_right_radius": field14,
        "border_bottom_width": field10,
        "border_color": field13,
        "border_left_color": field13,
        "border_left_width": field10,
        "border_radius": field14,
        "border_right_color": field13,
        "border_right_width": field10,
        "border_style": field15,
        "border_top_color": field13,
        "border_top_left_radius": field14,
        "border_top_right_radius": field14,
        "border_top_width": field10,
        "border_width": field10,
        "bottom": field16,
        "color": field11,
        "colors": field68,
        "column_gap": field10,
        "direction": field18,
        "display": field19,
        "elevation": field14,
        "end": field16,
        "end_point": field69,
        "flex": field10,
        "flex_basis": field16,
        "flex_direction": field20,
        "flex_grow": field10,
        "flex_shrink": field10,
        "flex_wrap": field21,
        "font_family": field22,
        "font_size": field10,
        "font_weight": field23,
        "gap": field10,
        "gestures": field24,
        "height": field16,
        "italic": field12,
        "justify_content": field25,
        "left": field16,
        "letter_spacing": field10,
        "line_height": field10,
        "locations": field70,
        "margin": field26,
        "margin_bottom": field27,
        "margin_end": field27,
        "margin_horizontal": field27,
        "margin_left": field27,
        "margin_right": field27,
        "margin_start": field27,
        "margin_top": field27,
        "margin_vertical": field27,
        "max_height": field16,
        "max_lines": field28,
        "max_width": field16,
        "min_height": field16,
        "min_width": field16,
        "on_layout": field29,
        "opacity": field30,
        "overflow": field31,
        "padding": field32,
        "padding_bottom": field16,
        "padding_end": field16,
        "padding_horizontal": field16,
        "padding_left": field16,
        "padding_right": field16,
        "padding_start": field16,
        "padding_top": field16,
        "padding_vertical": field16,
        "placeholder_color": field13,
        "pointer_events": field33,
        "position": field34,
        "ref": field35,
        "right": field16,
        "row_gap": field10,
        "shadow_color": field13,
        "shadow_offset": field36,
        "shadow_opacity": field14,
        "shadow_radius": field14,
        "spacing": field10,
        "start": field16,
        "start_point": field71,
        "test_id": field43,
        "text_align": field38,
        "text_decoration": field39,
        "text_shadow_color": field13,
        "text_shadow_offset": field36,
        "text_shadow_radius": field14,
        "text_transform": field40,
        "tint_color": field13,
        "top": field16,
        "transform": field41,
        "width": field16,
        "z_index": field42
    ] }
    private static func match88(_ value: Any) -> Bool {
        return ((value as? String) == "slide") || ((value as? String) == "fade") || ((value as? String) == "none")
    }
    private static func match89(_ value: Any) -> Bool {
        return ((value as? String) == "page_sheet") || ((value as? String) == "form_sheet") || ((value as? String) == "full_screen") || ((value as? String) == "overlay")
    }
    private static func component10() -> [String: Field] { [
        "_pn_animated_events": field0,
        "_pn_edit_revision": field1,
        "_pn_events": field2,
        "_pn_header_slot": field3,
        "_pn_layout": field4,
        "_pn_list_key": field5,
        "accessibility_role": field6,
        "align_content": field7,
        "align_items": field8,
        "align_self": field8,
        "animation_type": field72,
        "aspect_ratio": field10,
        "background_color": field11,
        "bold": field12,
        "border_bottom_color": field13,
        "border_bottom_left_radius": field14,
        "border_bottom_right_radius": field14,
        "border_bottom_width": field10,
        "border_color": field13,
        "border_left_color": field13,
        "border_left_width": field10,
        "border_radius": field14,
        "border_right_color": field13,
        "border_right_width": field10,
        "border_style": field15,
        "border_top_color": field13,
        "border_top_left_radius": field14,
        "border_top_right_radius": field14,
        "border_top_width": field10,
        "border_width": field10,
        "bottom": field16,
        "color": field11,
        "column_gap": field10,
        "direction": field18,
        "dismiss_on_backdrop": field9,
        "display": field19,
        "elevation": field14,
        "end": field16,
        "flex": field10,
        "flex_basis": field16,
        "flex_direction": field20,
        "flex_grow": field10,
        "flex_shrink": field10,
        "flex_wrap": field21,
        "font_family": field22,
        "font_size": field10,
        "font_weight": field23,
        "gap": field10,
        "gestures": field24,
        "height": field16,
        "italic": field12,
        "justify_content": field25,
        "left": field16,
        "letter_spacing": field10,
        "line_height": field10,
        "margin": field26,
        "margin_bottom": field27,
        "margin_end": field27,
        "margin_horizontal": field27,
        "margin_left": field27,
        "margin_right": field27,
        "margin_start": field27,
        "margin_top": field27,
        "margin_vertical": field27,
        "max_height": field16,
        "max_lines": field28,
        "max_width": field16,
        "min_height": field16,
        "min_width": field16,
        "on_dismiss": field54,
        "on_layout": field29,
        "on_request_close": field54,
        "on_show": field54,
        "opacity": field30,
        "overflow": field31,
        "padding": field32,
        "padding_bottom": field16,
        "padding_end": field16,
        "padding_horizontal": field16,
        "padding_left": field16,
        "padding_right": field16,
        "padding_start": field16,
        "padding_top": field16,
        "padding_vertical": field16,
        "placeholder_color": field13,
        "pointer_events": field33,
        "position": field34,
        "presentation_style": field73,
        "ref": field35,
        "right": field16,
        "row_gap": field10,
        "shadow_color": field13,
        "shadow_offset": field36,
        "shadow_opacity": field14,
        "shadow_radius": field14,
        "spacing": field10,
        "start": field16,
        "status_bar_translucent": field51,
        "text_align": field38,
        "text_decoration": field39,
        "text_shadow_color": field13,
        "text_shadow_offset": field36,
        "text_shadow_radius": field14,
        "text_transform": field40,
        "tint_color": field13,
        "title": field60,
        "top": field16,
        "transform": field41,
        "transparent": field51,
        "visible": field51,
        "width": field16,
        "z_index": field42
    ] }
    private static func match91(_ value: Any) -> Bool {
        guard let value = value as? [Any] else { return false }
        return value.allSatisfy { match53($0) }
    }
    private static func match90(_ value: Any) -> Bool {
        return match91(value) || match14(value)
    }
    private static func match92(_ value: Any) -> Bool {
        return match27(value) || match14(value)
    }
    private static func component11() -> [String: Field] { [
        "_pn_animated_events": field0,
        "_pn_edit_revision": field1,
        "_pn_events": field2,
        "_pn_header_slot": field3,
        "_pn_layout": field4,
        "_pn_list_key": field5,
        "accessibility_actions": field47,
        "accessibility_hint": field43,
        "accessibility_label": field43,
        "accessibility_live_region": field48,
        "accessibility_role": field6,
        "accessibility_state": field49,
        "accessibility_value": field50,
        "accessible": field44,
        "align_content": field7,
        "align_items": field8,
        "align_self": field8,
        "aspect_ratio": field10,
        "background_color": field11,
        "bold": field12,
        "border_bottom_color": field13,
        "border_bottom_left_radius": field14,
        "border_bottom_right_radius": field14,
        "border_bottom_width": field10,
        "border_color": field13,
        "border_left_color": field13,
        "border_left_width": field10,
        "border_radius": field14,
        "border_right_color": field13,
        "border_right_width": field10,
        "border_style": field15,
        "border_top_color": field13,
        "border_top_left_radius": field14,
        "border_top_right_radius": field14,
        "border_top_width": field10,
        "border_width": field10,
        "bottom": field16,
        "color": field11,
        "column_gap": field10,
        "direction": field18,
        "disabled": field51,
        "display": field19,
        "elevation": field14,
        "end": field16,
        "flex": field10,
        "flex_basis": field16,
        "flex_direction": field20,
        "flex_grow": field10,
        "flex_shrink": field10,
        "flex_wrap": field21,
        "font_family": field22,
        "font_size": field10,
        "font_weight": field23,
        "gap": field10,
        "gestures": field24,
        "height": field16,
        "important_for_accessibility": field52,
        "italic": field12,
        "items": field74,
        "justify_content": field25,
        "left": field16,
        "letter_spacing": field10,
        "line_height": field10,
        "margin": field26,
        "margin_bottom": field27,
        "margin_end": field27,
        "margin_horizontal": field27,
        "margin_left": field27,
        "margin_right": field27,
        "margin_start": field27,
        "margin_top": field27,
        "margin_vertical": field27,
        "max_height": field16,
        "max_lines": field28,
        "max_width": field16,
        "min_height": field16,
        "min_width": field16,
        "on_accessibility_action": field53,
        "on_change": field75,
        "on_layout": field29,
        "opacity": field30,
        "overflow": field31,
        "padding": field32,
        "padding_bottom": field16,
        "padding_end": field16,
        "padding_horizontal": field16,
        "padding_left": field16,
        "padding_right": field16,
        "padding_start": field16,
        "padding_top": field16,
        "padding_vertical": field16,
        "placeholder": field76,
        "placeholder_color": field13,
        "pointer_events": field33,
        "position": field34,
        "ref": field35,
        "right": field16,
        "row_gap": field10,
        "shadow_color": field13,
        "shadow_offset": field36,
        "shadow_opacity": field14,
        "shadow_radius": field14,
        "spacing": field10,
        "start": field16,
        "test_id": field43,
        "text_align": field38,
        "text_decoration": field39,
        "text_shadow_color": field13,
        "text_shadow_offset": field36,
        "text_shadow_radius": field14,
        "text_transform": field40,
        "tint_color": field13,
        "top": field16,
        "transform": field41,
        "value": field77,
        "width": field16,
        "z_index": field42
    ] }
    private static func component12() -> [String: Field] { [
        "_pn_animated_events": field0,
        "_pn_edit_revision": field1,
        "_pn_events": field2,
        "_pn_header_slot": field3,
        "_pn_layout": field4,
        "_pn_list_key": field5,
        "accessibility_role": field6,
        "align_content": field7,
        "align_items": field8,
        "align_self": field8,
        "aspect_ratio": field10,
        "background_color": field11,
        "bold": field12,
        "border_bottom_color": field13,
        "border_bottom_left_radius": field14,
        "border_bottom_right_radius": field14,
        "border_bottom_width": field10,
        "border_color": field13,
        "border_left_color": field13,
        "border_left_width": field10,
        "border_radius": field14,
        "border_right_color": field13,
        "border_right_width": field10,
        "border_style": field15,
        "border_top_color": field13,
        "border_top_left_radius": field14,
        "border_top_right_radius": field14,
        "border_top_width": field10,
        "border_width": field10,
        "bottom": field16,
        "color": field11,
        "column_gap": field10,
        "direction": field18,
        "display": field19,
        "elevation": field14,
        "end": field16,
        "flex": field10,
        "flex_basis": field16,
        "flex_direction": field20,
        "flex_grow": field10,
        "flex_shrink": field10,
        "flex_wrap": field21,
        "font_family": field22,
        "font_size": field10,
        "font_weight": field23,
        "gap": field10,
        "gestures": field24,
        "height": field16,
        "italic": field12,
        "justify_content": field25,
        "left": field16,
        "letter_spacing": field10,
        "line_height": field10,
        "margin": field26,
        "margin_bottom": field27,
        "margin_end": field27,
        "margin_horizontal": field27,
        "margin_left": field27,
        "margin_right": field27,
        "margin_start": field27,
        "margin_top": field27,
        "margin_vertical": field27,
        "max_height": field16,
        "max_lines": field28,
        "max_width": field16,
        "min_height": field16,
        "min_width": field16,
        "on_layout": field29,
        "opacity": field30,
        "overflow": field31,
        "padding": field32,
        "padding_bottom": field16,
        "padding_end": field16,
        "padding_horizontal": field16,
        "padding_left": field16,
        "padding_right": field16,
        "padding_start": field16,
        "padding_top": field16,
        "padding_vertical": field16,
        "placeholder_color": field13,
        "pointer_events": field33,
        "position": field34,
        "ref": field35,
        "right": field16,
        "row_gap": field10,
        "shadow_color": field13,
        "shadow_offset": field36,
        "shadow_opacity": field14,
        "shadow_radius": field14,
        "spacing": field10,
        "start": field16,
        "text_align": field38,
        "text_decoration": field39,
        "text_shadow_color": field13,
        "text_shadow_offset": field36,
        "text_shadow_radius": field14,
        "text_transform": field40,
        "tint_color": field13,
        "top": field16,
        "transform": field41,
        "width": field16,
        "z_index": field42
    ] }
    private static func match94(_ value: Any) -> Bool {
        guard let value = value as? [String: Any] else { return false }
        guard value["color"] != nil else { return false }
        for (key, item) in value {
            let valid: Bool
            switch key {
            case "borderless": valid = match5(item)
            case "color": valid = match9(item)
            case "foreground": valid = match5(item)
            case "radius": valid = match79(item)
            default: valid = false
            }
            if !valid { return false }
        }
        return true
    }
    private static func match93(_ value: Any) -> Bool {
        return match94(value) || match14(value)
    }
    private static func component13() -> [String: Field] { [
        "_pn_animated_events": field0,
        "_pn_edit_revision": field1,
        "_pn_events": field2,
        "_pn_header_slot": field3,
        "_pn_layout": field4,
        "_pn_list_key": field5,
        "accessibility_actions": field47,
        "accessibility_hint": field43,
        "accessibility_label": field43,
        "accessibility_live_region": field48,
        "accessibility_role": field43,
        "accessibility_state": field49,
        "accessibility_value": field50,
        "accessible": field44,
        "align_content": field7,
        "align_items": field8,
        "align_self": field8,
        "android_ripple": field78,
        "aspect_ratio": field10,
        "background_color": field11,
        "bold": field12,
        "border_bottom_color": field13,
        "border_bottom_left_radius": field14,
        "border_bottom_right_radius": field14,
        "border_bottom_width": field10,
        "border_color": field13,
        "border_left_color": field13,
        "border_left_width": field10,
        "border_radius": field14,
        "border_right_color": field13,
        "border_right_width": field10,
        "border_style": field15,
        "border_top_color": field13,
        "border_top_left_radius": field14,
        "border_top_right_radius": field14,
        "border_top_width": field10,
        "border_width": field10,
        "bottom": field16,
        "color": field11,
        "column_gap": field10,
        "delay_long_press": field79,
        "direction": field18,
        "disabled": field51,
        "display": field19,
        "elevation": field14,
        "end": field16,
        "flex": field10,
        "flex_basis": field16,
        "flex_direction": field20,
        "flex_grow": field10,
        "flex_shrink": field10,
        "flex_wrap": field21,
        "font_family": field22,
        "font_size": field10,
        "font_weight": field23,
        "gap": field10,
        "gestures": field24,
        "height": field16,
        "hit_slop": field58,
        "important_for_accessibility": field52,
        "italic": field12,
        "justify_content": field25,
        "left": field16,
        "letter_spacing": field10,
        "line_height": field10,
        "margin": field26,
        "margin_bottom": field27,
        "margin_end": field27,
        "margin_horizontal": field27,
        "margin_left": field27,
        "margin_right": field27,
        "margin_start": field27,
        "margin_top": field27,
        "margin_vertical": field27,
        "max_height": field16,
        "max_lines": field28,
        "max_width": field16,
        "min_height": field16,
        "min_width": field16,
        "on_accessibility_action": field53,
        "on_layout": field29,
        "on_long_press": field54,
        "on_press": field54,
        "on_press_in": field54,
        "on_press_out": field54,
        "opacity": field30,
        "overflow": field31,
        "padding": field32,
        "padding_bottom": field16,
        "padding_end": field16,
        "padding_horizontal": field16,
        "padding_left": field16,
        "padding_right": field16,
        "padding_start": field16,
        "padding_top": field16,
        "padding_vertical": field16,
        "placeholder_color": field13,
        "pointer_events": field33,
        "position": field34,
        "pressed_opacity": field80,
        "ref": field35,
        "right": field16,
        "row_gap": field10,
        "shadow_color": field13,
        "shadow_offset": field36,
        "shadow_opacity": field14,
        "shadow_radius": field14,
        "spacing": field10,
        "start": field16,
        "test_id": field43,
        "text_align": field38,
        "text_decoration": field39,
        "text_shadow_color": field13,
        "text_shadow_offset": field36,
        "text_shadow_radius": field14,
        "text_transform": field40,
        "tint_color": field13,
        "top": field16,
        "transform": field41,
        "width": field16,
        "z_index": field42
    ] }
    private static func component14() -> [String: Field] { [
        "_pn_animated_events": field0,
        "_pn_edit_revision": field1,
        "_pn_events": field2,
        "_pn_header_slot": field3,
        "_pn_layout": field4,
        "_pn_list_key": field5,
        "accessibility_role": field6,
        "align_content": field7,
        "align_items": field8,
        "align_self": field8,
        "aspect_ratio": field10,
        "background_color": field11,
        "bold": field12,
        "border_bottom_color": field13,
        "border_bottom_left_radius": field14,
        "border_bottom_right_radius": field14,
        "border_bottom_width": field10,
        "border_color": field13,
        "border_left_color": field13,
        "border_left_width": field10,
        "border_radius": field14,
        "border_right_color": field13,
        "border_right_width": field10,
        "border_style": field15,
        "border_top_color": field13,
        "border_top_left_radius": field14,
        "border_top_right_radius": field14,
        "border_top_width": field10,
        "border_width": field10,
        "bottom": field16,
        "color": field17,
        "column_gap": field10,
        "direction": field18,
        "display": field19,
        "elevation": field14,
        "end": field16,
        "flex": field10,
        "flex_basis": field16,
        "flex_direction": field20,
        "flex_grow": field10,
        "flex_shrink": field10,
        "flex_wrap": field21,
        "font_family": field22,
        "font_size": field10,
        "font_weight": field23,
        "gap": field10,
        "gestures": field24,
        "height": field16,
        "indeterminate": field81,
        "italic": field12,
        "justify_content": field25,
        "left": field16,
        "letter_spacing": field10,
        "line_height": field10,
        "margin": field26,
        "margin_bottom": field27,
        "margin_end": field27,
        "margin_horizontal": field27,
        "margin_left": field27,
        "margin_right": field27,
        "margin_start": field27,
        "margin_top": field27,
        "margin_vertical": field27,
        "max_height": field16,
        "max_lines": field28,
        "max_width": field16,
        "min_height": field16,
        "min_width": field16,
        "on_layout": field29,
        "opacity": field30,
        "overflow": field31,
        "padding": field32,
        "padding_bottom": field16,
        "padding_end": field16,
        "padding_horizontal": field16,
        "padding_left": field16,
        "padding_right": field16,
        "padding_start": field16,
        "padding_top": field16,
        "padding_vertical": field16,
        "placeholder_color": field13,
        "pointer_events": field33,
        "position": field34,
        "ref": field35,
        "right": field16,
        "row_gap": field10,
        "shadow_color": field13,
        "shadow_offset": field36,
        "shadow_opacity": field14,
        "shadow_radius": field14,
        "spacing": field10,
        "start": field16,
        "text_align": field38,
        "text_decoration": field39,
        "text_shadow_color": field13,
        "text_shadow_offset": field36,
        "text_shadow_radius": field14,
        "text_transform": field40,
        "tint_color": field13,
        "top": field16,
        "track_color": field64,
        "transform": field41,
        "value": field82,
        "width": field16,
        "z_index": field42
    ] }
    private static func component15() -> [String: Field] { [
        "_pn_animated_events": field0,
        "_pn_edit_revision": field1,
        "_pn_events": field2,
        "_pn_header_slot": field3,
        "_pn_layout": field4,
        "_pn_list_key": field5,
        "accessibility_role": field6,
        "align_content": field7,
        "align_items": field8,
        "align_self": field8,
        "aspect_ratio": field10,
        "background_color": field11,
        "bold": field12,
        "border_bottom_color": field13,
        "border_bottom_left_radius": field14,
        "border_bottom_right_radius": field14,
        "border_bottom_width": field10,
        "border_color": field13,
        "border_left_color": field13,
        "border_left_width": field10,
        "border_radius": field14,
        "border_right_color": field13,
        "border_right_width": field10,
        "border_style": field15,
        "border_top_color": field13,
        "border_top_left_radius": field14,
        "border_top_right_radius": field14,
        "border_top_width": field10,
        "border_width": field10,
        "bottom": field16,
        "color": field11,
        "column_gap": field10,
        "direction": field18,
        "display": field19,
        "elevation": field14,
        "end": field16,
        "flex": field10,
        "flex_basis": field16,
        "flex_direction": field20,
        "flex_grow": field10,
        "flex_shrink": field10,
        "flex_wrap": field21,
        "font_family": field22,
        "font_size": field10,
        "font_weight": field23,
        "gap": field10,
        "gestures": field24,
        "height": field16,
        "italic": field12,
        "justify_content": field25,
        "left": field16,
        "letter_spacing": field10,
        "line_height": field10,
        "margin": field26,
        "margin_bottom": field27,
        "margin_end": field27,
        "margin_horizontal": field27,
        "margin_left": field27,
        "margin_right": field27,
        "margin_start": field27,
        "margin_top": field27,
        "margin_vertical": field27,
        "max_height": field16,
        "max_lines": field28,
        "max_width": field16,
        "min_height": field16,
        "min_width": field16,
        "on_layout": field29,
        "on_refresh": field54,
        "opacity": field30,
        "overflow": field31,
        "padding": field32,
        "padding_bottom": field16,
        "padding_end": field16,
        "padding_horizontal": field16,
        "padding_left": field16,
        "padding_right": field16,
        "padding_start": field16,
        "padding_top": field16,
        "padding_vertical": field16,
        "placeholder_color": field13,
        "pointer_events": field33,
        "position": field34,
        "ref": field35,
        "refreshing": field51,
        "right": field16,
        "row_gap": field10,
        "shadow_color": field13,
        "shadow_offset": field36,
        "shadow_opacity": field14,
        "shadow_radius": field14,
        "spacing": field10,
        "start": field16,
        "text_align": field38,
        "text_decoration": field39,
        "text_shadow_color": field13,
        "text_shadow_offset": field36,
        "text_shadow_radius": field14,
        "text_transform": field40,
        "tint_color": field64,
        "top": field16,
        "transform": field41,
        "width": field16,
        "z_index": field42
    ] }
    private static func component16() -> [String: Field] { [
        "_pn_animated_events": field0,
        "_pn_edit_revision": field1,
        "_pn_events": field2,
        "_pn_header_slot": field3,
        "_pn_layout": field4,
        "_pn_list_key": field5,
        "accessibility_actions": field47,
        "accessibility_hint": field43,
        "accessibility_label": field43,
        "accessibility_live_region": field48,
        "accessibility_role": field43,
        "accessibility_state": field49,
        "accessibility_value": field50,
        "accessible": field44,
        "align_content": field7,
        "align_items": field8,
        "align_self": field8,
        "aspect_ratio": field10,
        "background_color": field11,
        "bold": field12,
        "border_bottom_color": field13,
        "border_bottom_left_radius": field14,
        "border_bottom_right_radius": field14,
        "border_bottom_width": field10,
        "border_color": field13,
        "border_left_color": field13,
        "border_left_width": field10,
        "border_radius": field14,
        "border_right_color": field13,
        "border_right_width": field10,
        "border_style": field15,
        "border_top_color": field13,
        "border_top_left_radius": field14,
        "border_top_right_radius": field14,
        "border_top_width": field10,
        "border_width": field10,
        "bottom": field16,
        "color": field11,
        "column_gap": field10,
        "direction": field18,
        "display": field19,
        "elevation": field14,
        "end": field16,
        "flex": field10,
        "flex_basis": field16,
        "flex_direction": field20,
        "flex_grow": field10,
        "flex_shrink": field10,
        "flex_wrap": field21,
        "font_family": field22,
        "font_size": field10,
        "font_weight": field23,
        "gap": field10,
        "gestures": field24,
        "height": field16,
        "hit_slop": field58,
        "important_for_accessibility": field52,
        "italic": field12,
        "justify_content": field25,
        "left": field16,
        "letter_spacing": field10,
        "line_height": field10,
        "margin": field26,
        "margin_bottom": field27,
        "margin_end": field27,
        "margin_horizontal": field27,
        "margin_left": field27,
        "margin_right": field27,
        "margin_start": field27,
        "margin_top": field27,
        "margin_vertical": field27,
        "max_height": field16,
        "max_lines": field28,
        "max_width": field16,
        "min_height": field16,
        "min_width": field16,
        "on_accessibility_action": field53,
        "on_layout": field29,
        "opacity": field30,
        "overflow": field31,
        "padding": field32,
        "padding_bottom": field16,
        "padding_end": field16,
        "padding_horizontal": field16,
        "padding_left": field16,
        "padding_right": field16,
        "padding_start": field16,
        "padding_top": field16,
        "padding_vertical": field16,
        "placeholder_color": field13,
        "pointer_events": field33,
        "position": field34,
        "ref": field35,
        "right": field16,
        "row_gap": field10,
        "shadow_color": field13,
        "shadow_offset": field36,
        "shadow_opacity": field14,
        "shadow_radius": field14,
        "spacing": field10,
        "start": field16,
        "test_id": field43,
        "text_align": field38,
        "text_decoration": field39,
        "text_shadow_color": field13,
        "text_shadow_offset": field36,
        "text_shadow_radius": field14,
        "text_transform": field40,
        "tint_color": field13,
        "top": field16,
        "transform": field41,
        "width": field16,
        "z_index": field42
    ] }
    private static func match97(_ value: Any) -> Bool {
        return ((value as? String) == "top") || ((value as? String) == "left") || ((value as? String) == "bottom") || ((value as? String) == "right")
    }
    private static func match96(_ value: Any) -> Bool {
        guard let value = value as? [Any] else { return false }
        return value.allSatisfy { match97($0) }
    }
    private static func match95(_ value: Any) -> Bool {
        return match96(value) || match14(value)
    }
    private static func component17() -> [String: Field] { [
        "_pn_animated_events": field0,
        "_pn_edit_revision": field1,
        "_pn_events": field2,
        "_pn_header_slot": field3,
        "_pn_layout": field4,
        "_pn_list_key": field5,
        "accessibility_role": field6,
        "align_content": field7,
        "align_items": field8,
        "align_self": field8,
        "aspect_ratio": field10,
        "background_color": field11,
        "bold": field12,
        "border_bottom_color": field13,
        "border_bottom_left_radius": field14,
        "border_bottom_right_radius": field14,
        "border_bottom_width": field10,
        "border_color": field13,
        "border_left_color": field13,
        "border_left_width": field10,
        "border_radius": field14,
        "border_right_color": field13,
        "border_right_width": field10,
        "border_style": field15,
        "border_top_color": field13,
        "border_top_left_radius": field14,
        "border_top_right_radius": field14,
        "border_top_width": field10,
        "border_width": field10,
        "bottom": field16,
        "color": field11,
        "column_gap": field10,
        "direction": field18,
        "display": field19,
        "edges": field83,
        "elevation": field14,
        "end": field16,
        "flex": field10,
        "flex_basis": field16,
        "flex_direction": field20,
        "flex_grow": field10,
        "flex_shrink": field10,
        "flex_wrap": field21,
        "font_family": field22,
        "font_size": field10,
        "font_weight": field23,
        "gap": field10,
        "gestures": field24,
        "height": field16,
        "italic": field12,
        "justify_content": field25,
        "left": field16,
        "letter_spacing": field10,
        "line_height": field10,
        "margin": field26,
        "margin_bottom": field27,
        "margin_end": field27,
        "margin_horizontal": field27,
        "margin_left": field27,
        "margin_right": field27,
        "margin_start": field27,
        "margin_top": field27,
        "margin_vertical": field27,
        "max_height": field16,
        "max_lines": field28,
        "max_width": field16,
        "min_height": field16,
        "min_width": field16,
        "on_layout": field29,
        "opacity": field30,
        "overflow": field31,
        "padding": field32,
        "padding_bottom": field16,
        "padding_end": field16,
        "padding_horizontal": field16,
        "padding_left": field16,
        "padding_right": field16,
        "padding_start": field16,
        "padding_top": field16,
        "padding_vertical": field16,
        "placeholder_color": field13,
        "pointer_events": field33,
        "position": field34,
        "ref": field35,
        "right": field16,
        "row_gap": field10,
        "shadow_color": field13,
        "shadow_offset": field36,
        "shadow_opacity": field14,
        "shadow_radius": field14,
        "spacing": field10,
        "start": field16,
        "text_align": field38,
        "text_decoration": field39,
        "text_shadow_color": field13,
        "text_shadow_offset": field36,
        "text_shadow_radius": field14,
        "text_transform": field40,
        "tint_color": field13,
        "top": field16,
        "transform": field41,
        "width": field16,
        "z_index": field42
    ] }
    private static func match98(_ value: Any) -> Bool {
        return ((value as? String) == "default") || ((value as? String) == "none") || ((value as? String) == "fade") || ((value as? String) == "slide_from_right") || ((value as? String) == "slide_from_bottom")
    }
    private static func match99(_ value: Any) -> Bool {
        return ((value as? String) == "card") || ((value as? String) == "modal") || ((value as? String) == "full_screen_modal") || ((value as? String) == "form_sheet") || ((value as? String) == "transparent_modal")
    }
    private static func match100(_ value: Any) -> Bool {
        return match3(value) || match1(value)
    }
    private static func component18() -> [String: Field] { [
        "_pn_animated_events": field0,
        "_pn_edit_revision": field1,
        "_pn_events": field2,
        "_pn_header_slot": field3,
        "_pn_layout": field4,
        "_pn_list_key": field5,
        "accessibility_actions": field47,
        "accessibility_hint": field43,
        "accessibility_label": field43,
        "accessibility_live_region": field48,
        "accessibility_role": field43,
        "accessibility_state": field49,
        "accessibility_value": field50,
        "accessible": field44,
        "active": field84,
        "align_content": field7,
        "align_items": field8,
        "align_self": field8,
        "animation": field85,
        "aspect_ratio": field10,
        "background_color": field11,
        "bold": field12,
        "border_bottom_color": field13,
        "border_bottom_left_radius": field14,
        "border_bottom_right_radius": field14,
        "border_bottom_width": field10,
        "border_color": field13,
        "border_left_color": field13,
        "border_left_width": field10,
        "border_radius": field14,
        "border_right_color": field13,
        "border_right_width": field10,
        "border_style": field15,
        "border_top_color": field13,
        "border_top_left_radius": field14,
        "border_top_right_radius": field14,
        "border_top_width": field10,
        "border_width": field10,
        "bottom": field16,
        "color": field11,
        "column_gap": field10,
        "direction": field18,
        "display": field19,
        "elevation": field14,
        "end": field16,
        "flex": field10,
        "flex_basis": field16,
        "flex_direction": field20,
        "flex_grow": field10,
        "flex_shrink": field10,
        "flex_wrap": field21,
        "font_family": field22,
        "font_size": field10,
        "font_weight": field23,
        "gap": field10,
        "gesture_enabled": field84,
        "gestures": field24,
        "guarded": field84,
        "header_back_title": field5,
        "header_back_visible": field84,
        "header_large_title": field84,
        "header_shown": field84,
        "header_style": field86,
        "header_tint_color": field5,
        "header_title_style": field86,
        "height": field16,
        "hit_slop": field58,
        "important_for_accessibility": field52,
        "italic": field12,
        "justify_content": field25,
        "lazy": field84,
        "left": field16,
        "letter_spacing": field10,
        "line_height": field10,
        "margin": field26,
        "margin_bottom": field27,
        "margin_end": field27,
        "margin_horizontal": field27,
        "margin_left": field27,
        "margin_right": field27,
        "margin_start": field27,
        "margin_top": field27,
        "margin_vertical": field27,
        "max_height": field16,
        "max_lines": field28,
        "max_width": field16,
        "min_height": field16,
        "min_width": field16,
        "on_accessibility_action": field53,
        "on_layout": field29,
        "opacity": field30,
        "options": field0,
        "overflow": field31,
        "padding": field32,
        "padding_bottom": field16,
        "padding_end": field16,
        "padding_horizontal": field16,
        "padding_left": field16,
        "padding_right": field16,
        "padding_start": field16,
        "padding_top": field16,
        "padding_vertical": field16,
        "placeholder_color": field13,
        "pointer_events": field33,
        "position": field34,
        "presentation": field87,
        "ref": field35,
        "right": field16,
        "route_key": field5,
        "row_gap": field10,
        "shadow_color": field13,
        "shadow_offset": field36,
        "shadow_opacity": field14,
        "shadow_radius": field14,
        "spacing": field10,
        "start": field16,
        "tab_bar_badge": field88,
        "tab_bar_label": field5,
        "test_id": field43,
        "text_align": field38,
        "text_decoration": field39,
        "text_shadow_color": field13,
        "text_shadow_offset": field36,
        "text_shadow_radius": field14,
        "text_transform": field40,
        "tint_color": field13,
        "title": field5,
        "top": field16,
        "transform": field41,
        "unmount_on_blur": field84,
        "width": field16,
        "z_index": field42
    ] }
    private static func component19() -> [String: Field] { [
        "_pn_animated_events": field0,
        "_pn_edit_revision": field1,
        "_pn_events": field2,
        "_pn_header_slot": field3,
        "_pn_layout": field4,
        "_pn_list_key": field5,
        "accessibility_actions": field47,
        "accessibility_hint": field43,
        "accessibility_label": field43,
        "accessibility_live_region": field48,
        "accessibility_role": field43,
        "accessibility_state": field49,
        "accessibility_value": field50,
        "accessible": field44,
        "align_content": field7,
        "align_items": field8,
        "align_self": field8,
        "aspect_ratio": field10,
        "background_color": field11,
        "bold": field12,
        "border_bottom_color": field13,
        "border_bottom_left_radius": field14,
        "border_bottom_right_radius": field14,
        "border_bottom_width": field10,
        "border_color": field13,
        "border_left_color": field13,
        "border_left_width": field10,
        "border_radius": field14,
        "border_right_color": field13,
        "border_right_width": field10,
        "border_style": field15,
        "border_top_color": field13,
        "border_top_left_radius": field14,
        "border_top_right_radius": field14,
        "border_top_width": field10,
        "border_width": field10,
        "bottom": field16,
        "color": field11,
        "column_gap": field10,
        "direction": field18,
        "display": field19,
        "elevation": field14,
        "end": field16,
        "flex": field10,
        "flex_basis": field16,
        "flex_direction": field20,
        "flex_grow": field10,
        "flex_shrink": field10,
        "flex_wrap": field21,
        "font_family": field22,
        "font_size": field10,
        "font_weight": field23,
        "gap": field10,
        "gestures": field24,
        "height": field16,
        "hit_slop": field58,
        "important_for_accessibility": field52,
        "italic": field12,
        "justify_content": field25,
        "left": field16,
        "letter_spacing": field10,
        "line_height": field10,
        "margin": field26,
        "margin_bottom": field27,
        "margin_end": field27,
        "margin_horizontal": field27,
        "margin_left": field27,
        "margin_right": field27,
        "margin_start": field27,
        "margin_top": field27,
        "margin_vertical": field27,
        "max_height": field16,
        "max_lines": field28,
        "max_width": field16,
        "min_height": field16,
        "min_width": field16,
        "on_accessibility_action": field53,
        "on_layout": field29,
        "on_native_back": field89,
        "opacity": field30,
        "overflow": field31,
        "padding": field32,
        "padding_bottom": field16,
        "padding_end": field16,
        "padding_horizontal": field16,
        "padding_left": field16,
        "padding_right": field16,
        "padding_start": field16,
        "padding_top": field16,
        "padding_vertical": field16,
        "placeholder_color": field13,
        "pointer_events": field33,
        "position": field34,
        "ref": field35,
        "right": field16,
        "row_gap": field10,
        "shadow_color": field13,
        "shadow_offset": field36,
        "shadow_opacity": field14,
        "shadow_radius": field14,
        "spacing": field10,
        "start": field16,
        "test_id": field43,
        "text_align": field38,
        "text_decoration": field39,
        "text_shadow_color": field13,
        "text_shadow_offset": field36,
        "text_shadow_radius": field14,
        "text_transform": field40,
        "tint_color": field13,
        "top": field16,
        "transform": field41,
        "width": field16,
        "z_index": field42
    ] }
    private static func match101(_ value: Any) -> Bool {
        return match25(value) || match14(value)
    }
    private static func match103(_ value: Any) -> Bool {
        return ((value as? String) == "normal") || ((value as? String) == "fast")
    }
    private static func match102(_ value: Any) -> Bool {
        return match103(value) || match8(value)
    }
    private static func match105(_ value: Any) -> Bool {
        return ((value as? String) == "none") || ((value as? String) == "on_drag") || ((value as? String) == "interactive")
    }
    private static func match104(_ value: Any) -> Bool {
        return match105(value) || match14(value)
    }
    private static func match106(_ value: Any) -> Bool {
        return ((value as? String) == "never") || ((value as? String) == "always") || ((value as? String) == "handled")
    }
    private static func match107(_ value: Any) -> Bool {
        return match27(value) || match14(value)
    }
    private static func match108(_ value: Any) -> Bool {
        guard let value = value as? [String: Any] else { return false }
        for (key, item) in value {
            let valid: Bool
            switch key {
            case "accessibility_role": valid = match3(item)
            case "align_content": valid = match6(item)
            case "align_items": valid = match7(item)
            case "align_self": valid = match7(item)
            case "aspect_ratio": valid = match8(item)
            case "background_color": valid = match9(item)
            case "bold": valid = match5(item)
            case "border_bottom_color": valid = match9(item)
            case "border_bottom_left_radius": valid = match8(item)
            case "border_bottom_right_radius": valid = match8(item)
            case "border_bottom_width": valid = match8(item)
            case "border_color": valid = match9(item)
            case "border_left_color": valid = match9(item)
            case "border_left_width": valid = match8(item)
            case "border_radius": valid = match8(item)
            case "border_right_color": valid = match9(item)
            case "border_right_width": valid = match8(item)
            case "border_style": valid = match11(item)
            case "border_top_color": valid = match9(item)
            case "border_top_left_radius": valid = match8(item)
            case "border_top_right_radius": valid = match8(item)
            case "border_top_width": valid = match8(item)
            case "border_width": valid = match8(item)
            case "bottom": valid = match12(item)
            case "color": valid = match9(item)
            case "column_gap": valid = match8(item)
            case "direction": valid = match15(item)
            case "display": valid = match16(item)
            case "elevation": valid = match8(item)
            case "end": valid = match12(item)
            case "flex": valid = match8(item)
            case "flex_basis": valid = match12(item)
            case "flex_direction": valid = match17(item)
            case "flex_grow": valid = match8(item)
            case "flex_shrink": valid = match8(item)
            case "flex_wrap": valid = match18(item)
            case "font_family": valid = match3(item)
            case "font_size": valid = match8(item)
            case "font_weight": valid = match19(item)
            case "gap": valid = match8(item)
            case "height": valid = match12(item)
            case "italic": valid = match5(item)
            case "justify_content": valid = match22(item)
            case "left": valid = match12(item)
            case "letter_spacing": valid = match8(item)
            case "line_height": valid = match8(item)
            case "margin": valid = match23(item)
            case "margin_bottom": valid = match26(item)
            case "margin_end": valid = match26(item)
            case "margin_horizontal": valid = match26(item)
            case "margin_left": valid = match26(item)
            case "margin_right": valid = match26(item)
            case "margin_start": valid = match26(item)
            case "margin_top": valid = match26(item)
            case "margin_vertical": valid = match26(item)
            case "max_height": valid = match12(item)
            case "max_lines": valid = match1(item)
            case "max_width": valid = match12(item)
            case "min_height": valid = match12(item)
            case "min_width": valid = match12(item)
            case "on_layout": valid = match27(item)
            case "on_refresh": valid = match74(item)
            case "opacity": valid = match8(item)
            case "overflow": valid = match28(item)
            case "padding": valid = match29(item)
            case "padding_bottom": valid = match12(item)
            case "padding_end": valid = match12(item)
            case "padding_horizontal": valid = match12(item)
            case "padding_left": valid = match12(item)
            case "padding_right": valid = match12(item)
            case "padding_start": valid = match12(item)
            case "padding_top": valid = match12(item)
            case "padding_vertical": valid = match12(item)
            case "placeholder_color": valid = match9(item)
            case "pointer_events": valid = match30(item)
            case "position": valid = match31(item)
            case "ref": valid = match21(item)
            case "refreshing": valid = match5(item)
            case "right": valid = match12(item)
            case "row_gap": valid = match8(item)
            case "shadow_color": valid = match9(item)
            case "shadow_offset": valid = match32(item)
            case "shadow_opacity": valid = match8(item)
            case "shadow_radius": valid = match8(item)
            case "spacing": valid = match8(item)
            case "start": valid = match12(item)
            case "text_align": valid = match37(item)
            case "text_decoration": valid = match38(item)
            case "text_shadow_color": valid = match9(item)
            case "text_shadow_offset": valid = match32(item)
            case "text_shadow_radius": valid = match8(item)
            case "text_transform": valid = match39(item)
            case "tint_color": valid = match13(item)
            case "top": valid = match12(item)
            case "transform": valid = match40(item)
            case "width": valid = match12(item)
            case "z_index": valid = match1(item)
            default: valid = false
            }
            if !valid { return false }
        }
        return true
    }
    private static func match109(_ value: Any) -> Bool {
        return ((value as? String) == "start") || ((value as? String) == "center") || ((value as? String) == "end")
    }
    private static func component20() -> [String: Field] { [
        "_pn_animated_events": field0,
        "_pn_edit_revision": field1,
        "_pn_events": field2,
        "_pn_header_slot": field3,
        "_pn_layout": field4,
        "_pn_list_key": field5,
        "accessibility_role": field6,
        "align_content": field7,
        "align_items": field8,
        "align_self": field8,
        "aspect_ratio": field10,
        "background_color": field11,
        "bold": field12,
        "border_bottom_color": field13,
        "border_bottom_left_radius": field14,
        "border_bottom_right_radius": field14,
        "border_bottom_width": field10,
        "border_color": field13,
        "border_left_color": field13,
        "border_left_width": field10,
        "border_radius": field14,
        "border_right_color": field13,
        "border_right_width": field10,
        "border_style": field15,
        "border_top_color": field13,
        "border_top_left_radius": field14,
        "border_top_right_radius": field14,
        "border_top_width": field10,
        "border_width": field10,
        "bottom": field16,
        "bounces": field9,
        "color": field11,
        "column_gap": field10,
        "content_inset": field90,
        "deceleration_rate": field91,
        "direction": field18,
        "display": field19,
        "elevation": field14,
        "end": field16,
        "flex": field10,
        "flex_basis": field16,
        "flex_direction": field20,
        "flex_grow": field10,
        "flex_shrink": field10,
        "flex_wrap": field21,
        "font_family": field22,
        "font_size": field10,
        "font_weight": field23,
        "gap": field10,
        "gestures": field24,
        "height": field16,
        "horizontal": field51,
        "italic": field12,
        "justify_content": field25,
        "keyboard_dismiss_mode": field92,
        "keyboard_should_persist_taps": field93,
        "left": field16,
        "letter_spacing": field10,
        "line_height": field10,
        "margin": field26,
        "margin_bottom": field27,
        "margin_end": field27,
        "margin_horizontal": field27,
        "margin_left": field27,
        "margin_right": field27,
        "margin_start": field27,
        "margin_top": field27,
        "margin_vertical": field27,
        "max_height": field16,
        "max_lines": field28,
        "max_width": field16,
        "min_height": field16,
        "min_width": field16,
        "on_layout": field29,
        "on_momentum_scroll_end": field94,
        "on_scroll": field94,
        "on_scroll_begin_drag": field94,
        "on_scroll_end_drag": field94,
        "opacity": field30,
        "overflow": field31,
        "padding": field32,
        "padding_bottom": field16,
        "padding_end": field16,
        "padding_horizontal": field16,
        "padding_left": field16,
        "padding_right": field16,
        "padding_start": field16,
        "padding_top": field16,
        "padding_vertical": field16,
        "paging_enabled": field51,
        "placeholder_color": field13,
        "pointer_events": field33,
        "position": field34,
        "ref": field35,
        "refresh_control": field95,
        "right": field16,
        "row_gap": field10,
        "scroll_enabled": field9,
        "scroll_event_throttle": field96,
        "shadow_color": field13,
        "shadow_offset": field36,
        "shadow_opacity": field14,
        "shadow_radius": field14,
        "shows_scroll_indicator": field9,
        "snap_to_alignment": field97,
        "snap_to_interval": field61,
        "spacing": field10,
        "start": field16,
        "text_align": field38,
        "text_decoration": field39,
        "text_shadow_color": field13,
        "text_shadow_offset": field36,
        "text_shadow_radius": field14,
        "text_transform": field40,
        "tint_color": field13,
        "top": field16,
        "transform": field41,
        "width": field16,
        "z_index": field42
    ] }
    private static func match110(_ value: Any) -> Bool {
        return match27(value) || match14(value)
    }
    private static func match111(_ value: Any) -> Bool {
        return match2(value) || match14(value)
    }
    private static func component21() -> [String: Field] { [
        "_pn_animated_events": field0,
        "_pn_edit_revision": field1,
        "_pn_events": field2,
        "_pn_header_slot": field3,
        "_pn_layout": field4,
        "_pn_list_key": field5,
        "accessibility_actions": field47,
        "accessibility_label": field43,
        "accessibility_live_region": field48,
        "accessibility_role": field6,
        "accessibility_state": field49,
        "accessibility_value": field50,
        "accessible": field44,
        "align_content": field7,
        "align_items": field8,
        "align_self": field8,
        "aspect_ratio": field10,
        "background_color": field11,
        "bold": field12,
        "border_bottom_color": field13,
        "border_bottom_left_radius": field14,
        "border_bottom_right_radius": field14,
        "border_bottom_width": field10,
        "border_color": field13,
        "border_left_color": field13,
        "border_left_width": field10,
        "border_radius": field14,
        "border_right_color": field13,
        "border_right_width": field10,
        "border_style": field15,
        "border_top_color": field13,
        "border_top_left_radius": field14,
        "border_top_right_radius": field14,
        "border_top_width": field10,
        "border_width": field10,
        "bottom": field16,
        "color": field11,
        "column_gap": field10,
        "direction": field18,
        "disabled": field51,
        "display": field19,
        "elevation": field14,
        "end": field16,
        "flex": field10,
        "flex_basis": field16,
        "flex_direction": field20,
        "flex_grow": field10,
        "flex_shrink": field10,
        "flex_wrap": field21,
        "font_family": field22,
        "font_size": field10,
        "font_weight": field23,
        "gap": field10,
        "gestures": field24,
        "height": field16,
        "important_for_accessibility": field52,
        "italic": field12,
        "justify_content": field25,
        "left": field16,
        "letter_spacing": field10,
        "line_height": field10,
        "margin": field26,
        "margin_bottom": field27,
        "margin_end": field27,
        "margin_horizontal": field27,
        "margin_left": field27,
        "margin_right": field27,
        "margin_start": field27,
        "margin_top": field27,
        "margin_vertical": field27,
        "max_height": field16,
        "max_lines": field28,
        "max_width": field16,
        "min_height": field16,
        "min_width": field16,
        "on_accessibility_action": field53,
        "on_change": field98,
        "on_layout": field29,
        "opacity": field30,
        "overflow": field31,
        "padding": field32,
        "padding_bottom": field16,
        "padding_end": field16,
        "padding_horizontal": field16,
        "padding_left": field16,
        "padding_right": field16,
        "padding_start": field16,
        "padding_top": field16,
        "padding_vertical": field16,
        "placeholder_color": field13,
        "pointer_events": field33,
        "position": field34,
        "ref": field35,
        "right": field16,
        "row_gap": field10,
        "segments": field99,
        "selected_index": field100,
        "shadow_color": field13,
        "shadow_offset": field36,
        "shadow_opacity": field14,
        "shadow_radius": field14,
        "spacing": field10,
        "start": field16,
        "test_id": field43,
        "text_align": field38,
        "text_decoration": field39,
        "text_shadow_color": field13,
        "text_shadow_offset": field36,
        "text_shadow_radius": field14,
        "text_transform": field40,
        "tint_color": field64,
        "top": field16,
        "transform": field41,
        "width": field16,
        "z_index": field42
    ] }
    private static func match112(_ value: Any) -> Bool {
        return match27(value) || match14(value)
    }
    private static func component22() -> [String: Field] { [
        "_pn_animated_events": field0,
        "_pn_edit_revision": field1,
        "_pn_events": field2,
        "_pn_header_slot": field3,
        "_pn_layout": field4,
        "_pn_list_key": field5,
        "accessibility_label": field43,
        "accessibility_role": field6,
        "align_content": field7,
        "align_items": field8,
        "align_self": field8,
        "aspect_ratio": field10,
        "background_color": field11,
        "bold": field12,
        "border_bottom_color": field13,
        "border_bottom_left_radius": field14,
        "border_bottom_right_radius": field14,
        "border_bottom_width": field10,
        "border_color": field13,
        "border_left_color": field13,
        "border_left_width": field10,
        "border_radius": field14,
        "border_right_color": field13,
        "border_right_width": field10,
        "border_style": field15,
        "border_top_color": field13,
        "border_top_left_radius": field14,
        "border_top_right_radius": field14,
        "border_top_width": field10,
        "border_width": field10,
        "bottom": field16,
        "color": field11,
        "column_gap": field10,
        "direction": field18,
        "disabled": field51,
        "display": field19,
        "elevation": field14,
        "end": field16,
        "flex": field10,
        "flex_basis": field16,
        "flex_direction": field20,
        "flex_grow": field10,
        "flex_shrink": field10,
        "flex_wrap": field21,
        "font_family": field22,
        "font_size": field10,
        "font_weight": field23,
        "gap": field10,
        "gestures": field24,
        "height": field16,
        "italic": field12,
        "justify_content": field25,
        "left": field16,
        "letter_spacing": field10,
        "line_height": field10,
        "margin": field26,
        "margin_bottom": field27,
        "margin_end": field27,
        "margin_horizontal": field27,
        "margin_left": field27,
        "margin_right": field27,
        "margin_start": field27,
        "margin_top": field27,
        "margin_vertical": field27,
        "max_height": field16,
        "max_lines": field28,
        "max_value": field101,
        "max_width": field16,
        "maximum_track_color": field64,
        "min_height": field16,
        "min_value": field67,
        "min_width": field16,
        "minimum_track_color": field64,
        "on_change": field102,
        "on_layout": field29,
        "on_sliding_complete": field102,
        "on_sliding_start": field102,
        "opacity": field30,
        "overflow": field31,
        "padding": field32,
        "padding_bottom": field16,
        "padding_end": field16,
        "padding_horizontal": field16,
        "padding_left": field16,
        "padding_right": field16,
        "padding_start": field16,
        "padding_top": field16,
        "padding_vertical": field16,
        "placeholder_color": field13,
        "pointer_events": field33,
        "position": field34,
        "ref": field35,
        "right": field16,
        "row_gap": field10,
        "shadow_color": field13,
        "shadow_offset": field36,
        "shadow_opacity": field14,
        "shadow_radius": field14,
        "spacing": field10,
        "start": field16,
        "step": field67,
        "text_align": field38,
        "text_decoration": field39,
        "text_shadow_color": field13,
        "text_shadow_offset": field36,
        "text_shadow_radius": field14,
        "text_transform": field40,
        "thumb_color": field64,
        "tint_color": field13,
        "top": field16,
        "transform": field41,
        "value": field82,
        "width": field16,
        "z_index": field42
    ] }
    private static func component23() -> [String: Field] { [
        "_pn_animated_events": field0,
        "_pn_edit_revision": field1,
        "_pn_events": field2,
        "_pn_header_slot": field3,
        "_pn_layout": field4,
        "_pn_list_key": field5,
        "accessibility_role": field6,
        "align_content": field7,
        "align_items": field8,
        "align_self": field8,
        "aspect_ratio": field10,
        "background_color": field11,
        "bold": field12,
        "border_bottom_color": field13,
        "border_bottom_left_radius": field14,
        "border_bottom_right_radius": field14,
        "border_bottom_width": field10,
        "border_color": field13,
        "border_left_color": field13,
        "border_left_width": field10,
        "border_radius": field14,
        "border_right_color": field13,
        "border_right_width": field10,
        "border_style": field15,
        "border_top_color": field13,
        "border_top_left_radius": field14,
        "border_top_right_radius": field14,
        "border_top_width": field10,
        "border_width": field10,
        "bottom": field16,
        "color": field11,
        "column_gap": field10,
        "direction": field18,
        "display": field19,
        "elevation": field14,
        "end": field16,
        "flex": field103,
        "flex_basis": field16,
        "flex_direction": field20,
        "flex_grow": field10,
        "flex_shrink": field10,
        "flex_wrap": field21,
        "font_family": field22,
        "font_size": field10,
        "font_weight": field23,
        "gap": field10,
        "gestures": field24,
        "height": field16,
        "italic": field12,
        "justify_content": field25,
        "left": field16,
        "letter_spacing": field10,
        "line_height": field10,
        "margin": field26,
        "margin_bottom": field27,
        "margin_end": field27,
        "margin_horizontal": field27,
        "margin_left": field27,
        "margin_right": field27,
        "margin_start": field27,
        "margin_top": field27,
        "margin_vertical": field27,
        "max_height": field16,
        "max_lines": field28,
        "max_width": field16,
        "min_height": field16,
        "min_width": field16,
        "on_layout": field29,
        "opacity": field30,
        "overflow": field31,
        "padding": field32,
        "padding_bottom": field16,
        "padding_end": field16,
        "padding_horizontal": field16,
        "padding_left": field16,
        "padding_right": field16,
        "padding_start": field16,
        "padding_top": field16,
        "padding_vertical": field16,
        "placeholder_color": field13,
        "pointer_events": field33,
        "position": field34,
        "ref": field35,
        "right": field16,
        "row_gap": field10,
        "shadow_color": field13,
        "shadow_offset": field36,
        "shadow_opacity": field14,
        "shadow_radius": field14,
        "size": field61,
        "spacing": field10,
        "start": field16,
        "text_align": field38,
        "text_decoration": field39,
        "text_shadow_color": field13,
        "text_shadow_offset": field36,
        "text_shadow_radius": field14,
        "text_transform": field40,
        "tint_color": field13,
        "top": field16,
        "transform": field41,
        "width": field16,
        "z_index": field42
    ] }
    private static func match114(_ value: Any) -> Bool {
        return ((value as? String) == "light") || ((value as? String) == "dark") || ((value as? String) == "default")
    }
    private static func match113(_ value: Any) -> Bool {
        return match114(value) || match14(value)
    }
    private static func component24() -> [String: Field] { [
        "_pn_animated_events": field0,
        "_pn_edit_revision": field1,
        "_pn_events": field2,
        "_pn_header_slot": field3,
        "_pn_layout": field4,
        "_pn_list_key": field5,
        "accessibility_role": field6,
        "align_content": field7,
        "align_items": field8,
        "align_self": field8,
        "animated": field51,
        "aspect_ratio": field10,
        "background_color": field17,
        "bar_style": field104,
        "bold": field12,
        "border_bottom_color": field13,
        "border_bottom_left_radius": field14,
        "border_bottom_right_radius": field14,
        "border_bottom_width": field10,
        "border_color": field13,
        "border_left_color": field13,
        "border_left_width": field10,
        "border_radius": field14,
        "border_right_color": field13,
        "border_right_width": field10,
        "border_style": field15,
        "border_top_color": field13,
        "border_top_left_radius": field14,
        "border_top_right_radius": field14,
        "border_top_width": field10,
        "border_width": field10,
        "bottom": field16,
        "color": field11,
        "column_gap": field10,
        "direction": field18,
        "display": field19,
        "elevation": field14,
        "end": field16,
        "flex": field10,
        "flex_basis": field16,
        "flex_direction": field20,
        "flex_grow": field10,
        "flex_shrink": field10,
        "flex_wrap": field21,
        "font_family": field22,
        "font_size": field10,
        "font_weight": field23,
        "gap": field10,
        "gestures": field24,
        "height": field16,
        "hidden": field44,
        "italic": field12,
        "justify_content": field25,
        "left": field16,
        "letter_spacing": field10,
        "line_height": field10,
        "margin": field26,
        "margin_bottom": field27,
        "margin_end": field27,
        "margin_horizontal": field27,
        "margin_left": field27,
        "margin_right": field27,
        "margin_start": field27,
        "margin_top": field27,
        "margin_vertical": field27,
        "max_height": field16,
        "max_lines": field28,
        "max_width": field16,
        "min_height": field16,
        "min_width": field16,
        "on_layout": field29,
        "opacity": field30,
        "overflow": field31,
        "padding": field32,
        "padding_bottom": field16,
        "padding_end": field16,
        "padding_horizontal": field16,
        "padding_left": field16,
        "padding_right": field16,
        "padding_start": field16,
        "padding_top": field16,
        "padding_vertical": field16,
        "placeholder_color": field13,
        "pointer_events": field33,
        "position": field34,
        "ref": field35,
        "right": field16,
        "row_gap": field10,
        "shadow_color": field13,
        "shadow_offset": field36,
        "shadow_opacity": field14,
        "shadow_radius": field14,
        "spacing": field10,
        "start": field16,
        "text_align": field38,
        "text_decoration": field39,
        "text_shadow_color": field13,
        "text_shadow_offset": field36,
        "text_shadow_radius": field14,
        "text_transform": field40,
        "tint_color": field13,
        "top": field16,
        "transform": field41,
        "translucent": field51,
        "width": field16,
        "z_index": field42
    ] }
    private static func match116(_ value: Any) -> Bool {
        return ((value as? String) == "nonzero") || ((value as? String) == "evenodd")
    }
    private static func match115(_ value: Any) -> Bool {
        return match116(value) || match14(value)
    }
    private static func match117(_ value: Any) -> Bool {
        return ((value as? String) == "meet") || ((value as? String) == "slice") || ((value as? String) == "none")
    }
    private static func match121(_ value: Any) -> Bool {
        return ((value as? String) == "path") || ((value as? String) == "circle") || ((value as? String) == "ellipse") || ((value as? String) == "rect") || ((value as? String) == "line") || ((value as? String) == "polyline") || ((value as? String) == "polygon")
    }
    private static func match123(_ value: Any) -> Bool {
        return ((value as? String) == "butt") || ((value as? String) == "round") || ((value as? String) == "square")
    }
    private static func match122(_ value: Any) -> Bool {
        return match123(value) || match14(value)
    }
    private static func match125(_ value: Any) -> Bool {
        return ((value as? String) == "miter") || ((value as? String) == "round") || ((value as? String) == "bevel")
    }
    private static func match124(_ value: Any) -> Bool {
        return match125(value) || match14(value)
    }
    private static func match120(_ value: Any) -> Bool {
        guard let value = value as? [String: Any] else { return false }
        guard value["kind"] != nil else { return false }
        for (key, item) in value {
            let valid: Bool
            switch key {
            case "cx": valid = match79(item)
            case "cy": valid = match79(item)
            case "d": valid = match57(item)
            case "fill": valid = match13(item)
            case "fill_opacity": valid = match79(item)
            case "fill_rule": valid = match115(item)
            case "height": valid = match79(item)
            case "kind": valid = match121(item)
            case "opacity": valid = match79(item)
            case "points": valid = match57(item)
            case "r": valid = match79(item)
            case "rx": valid = match79(item)
            case "ry": valid = match79(item)
            case "stroke": valid = match13(item)
            case "stroke_dasharray": valid = match87(item)
            case "stroke_linecap": valid = match122(item)
            case "stroke_linejoin": valid = match124(item)
            case "stroke_opacity": valid = match79(item)
            case "stroke_width": valid = match79(item)
            case "transform": valid = match57(item)
            case "width": valid = match79(item)
            case "x": valid = match79(item)
            case "x1": valid = match79(item)
            case "x2": valid = match79(item)
            case "y": valid = match79(item)
            case "y1": valid = match79(item)
            case "y2": valid = match79(item)
            default: valid = false
            }
            if !valid { return false }
        }
        return true
    }
    private static func match119(_ value: Any) -> Bool {
        guard let value = value as? [Any] else { return false }
        return value.allSatisfy { match120($0) }
    }
    private static func match118(_ value: Any) -> Bool {
        return match119(value) || match14(value)
    }
    private static func component25() -> [String: Field] { [
        "_pn_animated_events": field0,
        "_pn_edit_revision": field1,
        "_pn_events": field2,
        "_pn_header_slot": field3,
        "_pn_layout": field4,
        "_pn_list_key": field5,
        "accessibility_actions": field47,
        "accessibility_label": field43,
        "accessibility_role": field43,
        "accessibility_state": field49,
        "accessibility_value": field50,
        "accessible": field44,
        "align_content": field7,
        "align_items": field8,
        "align_self": field8,
        "aspect_ratio": field10,
        "background_color": field11,
        "bold": field12,
        "border_bottom_color": field13,
        "border_bottom_left_radius": field14,
        "border_bottom_right_radius": field14,
        "border_bottom_width": field10,
        "border_color": field13,
        "border_left_color": field13,
        "border_left_width": field10,
        "border_radius": field14,
        "border_right_color": field13,
        "border_right_width": field10,
        "border_style": field15,
        "border_top_color": field13,
        "border_top_left_radius": field14,
        "border_top_right_radius": field14,
        "border_top_width": field10,
        "border_width": field10,
        "bottom": field16,
        "color": field11,
        "column_gap": field10,
        "direction": field18,
        "display": field19,
        "elevation": field14,
        "end": field16,
        "fill": field64,
        "fill_rule": field105,
        "flex": field10,
        "flex_basis": field16,
        "flex_direction": field20,
        "flex_grow": field10,
        "flex_shrink": field10,
        "flex_wrap": field21,
        "font_family": field22,
        "font_size": field10,
        "font_weight": field23,
        "gap": field10,
        "gestures": field24,
        "height": field16,
        "important_for_accessibility": field52,
        "italic": field12,
        "justify_content": field25,
        "left": field16,
        "letter_spacing": field10,
        "line_height": field10,
        "margin": field26,
        "margin_bottom": field27,
        "margin_end": field27,
        "margin_horizontal": field27,
        "margin_left": field27,
        "margin_right": field27,
        "margin_start": field27,
        "margin_top": field27,
        "margin_vertical": field27,
        "max_height": field16,
        "max_lines": field28,
        "max_width": field16,
        "min_height": field16,
        "min_width": field16,
        "on_accessibility_action": field53,
        "on_layout": field29,
        "opacity": field30,
        "overflow": field31,
        "padding": field32,
        "padding_bottom": field16,
        "padding_end": field16,
        "padding_horizontal": field16,
        "padding_left": field16,
        "padding_right": field16,
        "padding_start": field16,
        "padding_top": field16,
        "padding_vertical": field16,
        "placeholder_color": field13,
        "pointer_events": field33,
        "position": field34,
        "preserve_aspect_ratio": field106,
        "ref": field35,
        "right": field16,
        "row_gap": field10,
        "shadow_color": field13,
        "shadow_offset": field36,
        "shadow_opacity": field14,
        "shadow_radius": field14,
        "shapes": field107,
        "spacing": field10,
        "start": field16,
        "stroke": field64,
        "stroke_linecap": field108,
        "stroke_linejoin": field109,
        "stroke_width": field61,
        "test_id": field43,
        "text_align": field38,
        "text_decoration": field39,
        "text_shadow_color": field13,
        "text_shadow_offset": field36,
        "text_shadow_radius": field14,
        "text_transform": field40,
        "tint_color": field13,
        "top": field16,
        "transform": field41,
        "view_box": field60,
        "width": field16,
        "z_index": field42
    ] }
    private static func component26() -> [String: Field] { [
        "_pn_animated_events": field0,
        "_pn_edit_revision": field1,
        "_pn_events": field2,
        "_pn_header_slot": field3,
        "_pn_layout": field4,
        "_pn_list_key": field5,
        "accessibility_label": field43,
        "accessibility_role": field6,
        "align_content": field7,
        "align_items": field8,
        "align_self": field8,
        "aspect_ratio": field10,
        "background_color": field11,
        "bold": field12,
        "border_bottom_color": field13,
        "border_bottom_left_radius": field14,
        "border_bottom_right_radius": field14,
        "border_bottom_width": field10,
        "border_color": field13,
        "border_left_color": field13,
        "border_left_width": field10,
        "border_radius": field14,
        "border_right_color": field13,
        "border_right_width": field10,
        "border_style": field15,
        "border_top_color": field13,
        "border_top_left_radius": field14,
        "border_top_right_radius": field14,
        "border_top_width": field10,
        "border_width": field10,
        "bottom": field16,
        "color": field11,
        "column_gap": field10,
        "direction": field18,
        "disabled": field51,
        "display": field19,
        "elevation": field14,
        "end": field16,
        "flex": field10,
        "flex_basis": field16,
        "flex_direction": field20,
        "flex_grow": field10,
        "flex_shrink": field10,
        "flex_wrap": field21,
        "font_family": field22,
        "font_size": field10,
        "font_weight": field23,
        "gap": field10,
        "gestures": field24,
        "height": field16,
        "italic": field12,
        "justify_content": field25,
        "left": field16,
        "letter_spacing": field10,
        "line_height": field10,
        "margin": field26,
        "margin_bottom": field27,
        "margin_end": field27,
        "margin_horizontal": field27,
        "margin_left": field27,
        "margin_right": field27,
        "margin_start": field27,
        "margin_top": field27,
        "margin_vertical": field27,
        "max_height": field16,
        "max_lines": field28,
        "max_width": field16,
        "min_height": field16,
        "min_width": field16,
        "on_change": field56,
        "on_layout": field29,
        "on_tint_color": field64,
        "opacity": field30,
        "overflow": field31,
        "padding": field32,
        "padding_bottom": field16,
        "padding_end": field16,
        "padding_horizontal": field16,
        "padding_left": field16,
        "padding_right": field16,
        "padding_start": field16,
        "padding_top": field16,
        "padding_vertical": field16,
        "placeholder_color": field13,
        "pointer_events": field33,
        "position": field34,
        "ref": field35,
        "right": field16,
        "row_gap": field10,
        "shadow_color": field13,
        "shadow_offset": field36,
        "shadow_opacity": field14,
        "shadow_radius": field14,
        "spacing": field10,
        "start": field16,
        "text_align": field38,
        "text_decoration": field39,
        "text_shadow_color": field13,
        "text_shadow_offset": field36,
        "text_shadow_radius": field14,
        "text_transform": field40,
        "thumb_color": field64,
        "tint_color": field13,
        "top": field16,
        "transform": field41,
        "value": field57,
        "width": field16,
        "z_index": field42
    ] }
    private static func match128(_ value: Any) -> Bool {
        guard let value = value as? [String: Any] else { return false }
        for (key, item) in value {
            let valid: Bool
            switch key {
            case "shapes": valid = match119(item)
            case "uri": valid = match3(item)
            case "view_box": valid = match3(item)
            default: valid = false
            }
            if !valid { return false }
        }
        return true
    }
    private static func match127(_ value: Any) -> Bool {
        guard let value = value as? [String: Any] else { return false }
        guard value["name"] != nil else { return false }
        guard value["title"] != nil else { return false }
        for (key, item) in value {
            let valid: Bool
            switch key {
            case "badge": valid = match3(item)
            case "icon": valid = match128(item)
            case "name": valid = match3(item)
            case "title": valid = match3(item)
            default: valid = false
            }
            if !valid { return false }
        }
        return true
    }
    private static func match126(_ value: Any) -> Bool {
        guard let value = value as? [Any] else { return false }
        return value.allSatisfy { match127($0) }
    }
    private static func component27() -> [String: Field] { [
        "_pn_animated_events": field0,
        "_pn_edit_revision": field1,
        "_pn_events": field2,
        "_pn_header_slot": field3,
        "_pn_layout": field4,
        "_pn_list_key": field5,
        "accessibility_actions": field47,
        "accessibility_hint": field43,
        "accessibility_label": field43,
        "accessibility_live_region": field48,
        "accessibility_role": field43,
        "accessibility_state": field49,
        "accessibility_value": field50,
        "accessible": field44,
        "active_tab": field5,
        "align_content": field7,
        "align_items": field8,
        "align_self": field8,
        "aspect_ratio": field10,
        "background_color": field11,
        "bold": field12,
        "border_bottom_color": field13,
        "border_bottom_left_radius": field14,
        "border_bottom_right_radius": field14,
        "border_bottom_width": field10,
        "border_color": field13,
        "border_left_color": field13,
        "border_left_width": field10,
        "border_radius": field14,
        "border_right_color": field13,
        "border_right_width": field10,
        "border_style": field15,
        "border_top_color": field13,
        "border_top_left_radius": field14,
        "border_top_right_radius": field14,
        "border_top_width": field10,
        "border_width": field10,
        "bottom": field16,
        "color": field11,
        "column_gap": field10,
        "direction": field18,
        "display": field19,
        "elevation": field14,
        "end": field16,
        "flex": field10,
        "flex_basis": field16,
        "flex_direction": field20,
        "flex_grow": field10,
        "flex_shrink": field10,
        "flex_wrap": field21,
        "font_family": field22,
        "font_size": field10,
        "font_weight": field23,
        "gap": field10,
        "gestures": field24,
        "height": field16,
        "hit_slop": field58,
        "important_for_accessibility": field52,
        "inactive_tint_color": field5,
        "italic": field12,
        "items": field110,
        "justify_content": field25,
        "left": field16,
        "letter_spacing": field10,
        "line_height": field10,
        "margin": field26,
        "margin_bottom": field27,
        "margin_end": field27,
        "margin_horizontal": field27,
        "margin_left": field27,
        "margin_right": field27,
        "margin_start": field27,
        "margin_top": field27,
        "margin_vertical": field27,
        "max_height": field16,
        "max_lines": field28,
        "max_width": field16,
        "min_height": field16,
        "min_width": field16,
        "on_accessibility_action": field53,
        "on_layout": field29,
        "on_tab_select": field111,
        "opacity": field30,
        "overflow": field31,
        "padding": field32,
        "padding_bottom": field16,
        "padding_end": field16,
        "padding_horizontal": field16,
        "padding_left": field16,
        "padding_right": field16,
        "padding_start": field16,
        "padding_top": field16,
        "padding_vertical": field16,
        "placeholder_color": field13,
        "pointer_events": field33,
        "position": field34,
        "ref": field35,
        "right": field16,
        "row_gap": field10,
        "shadow_color": field13,
        "shadow_offset": field36,
        "shadow_opacity": field14,
        "shadow_radius": field14,
        "shows_labels": field84,
        "spacing": field10,
        "start": field16,
        "test_id": field43,
        "text_align": field38,
        "text_decoration": field39,
        "text_shadow_color": field13,
        "text_shadow_offset": field36,
        "text_shadow_radius": field14,
        "text_transform": field40,
        "tint_color": field5,
        "top": field16,
        "transform": field41,
        "translucent": field84,
        "width": field16,
        "z_index": field42
    ] }
    private static func match129(_ value: Any) -> Bool {
        return ((value as? String) == "head") || ((value as? String) == "middle") || ((value as? String) == "tail") || ((value as? String) == "clip")
    }
    private static func component28() -> [String: Field] { [
        "_pn_animated_events": field0,
        "_pn_edit_revision": field1,
        "_pn_events": field2,
        "_pn_header_slot": field3,
        "_pn_layout": field4,
        "_pn_list_key": field5,
        "accessibility_actions": field47,
        "accessibility_hint": field43,
        "accessibility_label": field43,
        "accessibility_live_region": field48,
        "accessibility_role": field43,
        "accessibility_state": field49,
        "accessibility_value": field50,
        "accessible": field44,
        "align_content": field7,
        "align_items": field8,
        "align_self": field8,
        "allow_font_scaling": field112,
        "aspect_ratio": field10,
        "background_color": field11,
        "bold": field12,
        "border_bottom_color": field13,
        "border_bottom_left_radius": field14,
        "border_bottom_right_radius": field14,
        "border_bottom_width": field10,
        "border_color": field13,
        "border_left_color": field13,
        "border_left_width": field10,
        "border_radius": field14,
        "border_right_color": field13,
        "border_right_width": field10,
        "border_style": field15,
        "border_top_color": field13,
        "border_top_left_radius": field14,
        "border_top_right_radius": field14,
        "border_top_width": field10,
        "border_width": field10,
        "bottom": field16,
        "color": field11,
        "column_gap": field10,
        "direction": field18,
        "display": field19,
        "elevation": field14,
        "ellipsize_mode": field113,
        "end": field16,
        "flex": field10,
        "flex_basis": field16,
        "flex_direction": field20,
        "flex_grow": field10,
        "flex_shrink": field10,
        "flex_wrap": field21,
        "font_family": field22,
        "font_size": field10,
        "font_weight": field23,
        "gap": field10,
        "gestures": field24,
        "height": field16,
        "important_for_accessibility": field52,
        "italic": field12,
        "justify_content": field25,
        "left": field16,
        "letter_spacing": field10,
        "line_height": field10,
        "margin": field26,
        "margin_bottom": field27,
        "margin_end": field27,
        "margin_horizontal": field27,
        "margin_left": field27,
        "margin_right": field27,
        "margin_start": field27,
        "margin_top": field27,
        "margin_vertical": field27,
        "max_height": field16,
        "max_lines": field28,
        "max_width": field16,
        "min_height": field16,
        "min_width": field16,
        "on_accessibility_action": field53,
        "on_layout": field29,
        "on_press": field54,
        "on_span_press": field114,
        "opacity": field30,
        "overflow": field31,
        "padding": field32,
        "padding_bottom": field16,
        "padding_end": field16,
        "padding_horizontal": field16,
        "padding_left": field16,
        "padding_right": field16,
        "padding_start": field16,
        "padding_top": field16,
        "padding_vertical": field16,
        "placeholder_color": field13,
        "pointer_events": field33,
        "position": field34,
        "ref": field35,
        "right": field16,
        "row_gap": field10,
        "selectable": field51,
        "shadow_color": field13,
        "shadow_offset": field36,
        "shadow_opacity": field14,
        "shadow_radius": field14,
        "spacing": field10,
        "spans": field115,
        "start": field16,
        "test_id": field43,
        "text": field116,
        "text_align": field38,
        "text_decoration": field39,
        "text_shadow_color": field13,
        "text_shadow_offset": field36,
        "text_shadow_radius": field14,
        "text_transform": field40,
        "tint_color": field13,
        "top": field16,
        "transform": field41,
        "width": field16,
        "z_index": field42
    ] }
    private static func match131(_ value: Any) -> Bool {
        return ((value as? String) == "none") || ((value as? String) == "sentences") || ((value as? String) == "words") || ((value as? String) == "characters")
    }
    private static func match130(_ value: Any) -> Bool {
        return match131(value) || match14(value)
    }
    private static func match132(_ value: Any) -> Bool {
        return ((value as? String) == "default") || ((value as? String) == "light") || ((value as? String) == "dark")
    }
    private static func match134(_ value: Any) -> Bool {
        return ((value as? String) == "default") || ((value as? String) == "email_address") || ((value as? String) == "number_pad") || ((value as? String) == "decimal_pad") || ((value as? String) == "phone_pad") || ((value as? String) == "url") || ((value as? String) == "ascii") || ((value as? String) == "numbers_and_punctuation") || ((value as? String) == "web_search") || ((value as? String) == "visible_password")
    }
    private static func match133(_ value: Any) -> Bool {
        return match134(value) || match14(value)
    }
    private static func match135(_ value: Any) -> Bool {
        return match1(value) || match14(value)
    }
    private static func match136(_ value: Any) -> Bool {
        return match27(value) || match14(value)
    }
    private static func match137(_ value: Any) -> Bool {
        return match27(value) || match14(value)
    }
    private static func match138(_ value: Any) -> Bool {
        return match27(value) || match14(value)
    }
    private static func match140(_ value: Any) -> Bool {
        return ((value as? String) == "default") || ((value as? String) == "done") || ((value as? String) == "go") || ((value as? String) == "next") || ((value as? String) == "send") || ((value as? String) == "search")
    }
    private static func match139(_ value: Any) -> Bool {
        return match140(value) || match14(value)
    }
    private static func match142(_ value: Any) -> Bool {
        guard let value = value as? [String: Any] else { return false }
        guard value["end"] != nil else { return false }
        guard value["start"] != nil else { return false }
        for (key, item) in value {
            let valid: Bool
            switch key {
            case "end": valid = match1(item)
            case "start": valid = match1(item)
            default: valid = false
            }
            if !valid { return false }
        }
        return true
    }
    private static func match141(_ value: Any) -> Bool {
        return match142(value) || match14(value)
    }
    private static func component29() -> [String: Field] { [
        "_pn_animated_events": field0,
        "_pn_edit_revision": field1,
        "_pn_events": field2,
        "_pn_header_slot": field3,
        "_pn_layout": field4,
        "_pn_list_key": field5,
        "accessibility_actions": field47,
        "accessibility_hint": field43,
        "accessibility_label": field43,
        "accessibility_live_region": field48,
        "accessibility_role": field6,
        "accessibility_state": field49,
        "accessibility_value": field50,
        "accessible": field44,
        "align_content": field7,
        "align_items": field8,
        "align_self": field8,
        "aspect_ratio": field10,
        "auto_capitalize": field117,
        "auto_correct": field44,
        "auto_focus": field51,
        "background_color": field11,
        "blur_on_submit": field44,
        "bold": field12,
        "border_bottom_color": field13,
        "border_bottom_left_radius": field14,
        "border_bottom_right_radius": field14,
        "border_bottom_width": field10,
        "border_color": field13,
        "border_left_color": field13,
        "border_left_width": field10,
        "border_radius": field14,
        "border_right_color": field13,
        "border_right_width": field10,
        "border_style": field15,
        "border_top_color": field13,
        "border_top_left_radius": field14,
        "border_top_right_radius": field14,
        "border_top_width": field10,
        "border_width": field10,
        "bottom": field16,
        "clear_button": field51,
        "color": field11,
        "column_gap": field10,
        "direction": field18,
        "display": field19,
        "editable": field9,
        "elevation": field14,
        "end": field16,
        "flex": field10,
        "flex_basis": field16,
        "flex_direction": field20,
        "flex_grow": field10,
        "flex_shrink": field10,
        "flex_wrap": field21,
        "font_family": field22,
        "font_size": field10,
        "font_weight": field23,
        "gap": field10,
        "gestures": field24,
        "height": field16,
        "important_for_accessibility": field52,
        "italic": field12,
        "justify_content": field25,
        "keyboard_appearance": field118,
        "keyboard_type": field119,
        "left": field16,
        "letter_spacing": field10,
        "line_height": field10,
        "margin": field26,
        "margin_bottom": field27,
        "margin_end": field27,
        "margin_horizontal": field27,
        "margin_left": field27,
        "margin_right": field27,
        "margin_start": field27,
        "margin_top": field27,
        "margin_vertical": field27,
        "max_height": field16,
        "max_length": field120,
        "max_lines": field28,
        "max_width": field16,
        "min_height": field16,
        "min_width": field16,
        "multiline": field121,
        "on_accessibility_action": field53,
        "on_blur": field54,
        "on_change": field53,
        "on_content_size_change": field122,
        "on_focus": field54,
        "on_key_press": field123,
        "on_layout": field29,
        "on_selection_change": field124,
        "on_submit": field53,
        "opacity": field30,
        "overflow": field31,
        "padding": field32,
        "padding_bottom": field16,
        "padding_end": field16,
        "padding_horizontal": field16,
        "padding_left": field16,
        "padding_right": field16,
        "padding_start": field16,
        "padding_top": field16,
        "padding_vertical": field16,
        "placeholder": field43,
        "placeholder_color": field64,
        "pointer_events": field33,
        "position": field34,
        "ref": field35,
        "return_key_type": field125,
        "right": field16,
        "row_gap": field10,
        "secure": field51,
        "select_text_on_focus": field51,
        "selection": field126,
        "selection_color": field64,
        "shadow_color": field13,
        "shadow_offset": field36,
        "shadow_opacity": field14,
        "shadow_radius": field14,
        "spacing": field10,
        "start": field16,
        "test_id": field43,
        "text_align": field38,
        "text_content_type": field43,
        "text_decoration": field39,
        "text_shadow_color": field13,
        "text_shadow_offset": field36,
        "text_shadow_radius": field14,
        "text_transform": field40,
        "tint_color": field13,
        "top": field16,
        "transform": field41,
        "value": field55,
        "width": field16,
        "z_index": field42
    ] }
    private static func component30() -> [String: Field] { [
        "_pn_animated_events": field0,
        "_pn_edit_revision": field1,
        "_pn_events": field2,
        "_pn_header_slot": field3,
        "_pn_layout": field4,
        "_pn_list_key": field5,
        "accessibility_actions": field47,
        "accessibility_hint": field43,
        "accessibility_label": field43,
        "accessibility_live_region": field48,
        "accessibility_role": field43,
        "accessibility_state": field49,
        "accessibility_value": field50,
        "accessible": field44,
        "active_opacity": field127,
        "align_content": field7,
        "align_items": field8,
        "align_self": field8,
        "aspect_ratio": field10,
        "background_color": field11,
        "bold": field12,
        "border_bottom_color": field13,
        "border_bottom_left_radius": field14,
        "border_bottom_right_radius": field14,
        "border_bottom_width": field10,
        "border_color": field13,
        "border_left_color": field13,
        "border_left_width": field10,
        "border_radius": field14,
        "border_right_color": field13,
        "border_right_width": field10,
        "border_style": field15,
        "border_top_color": field13,
        "border_top_left_radius": field14,
        "border_top_right_radius": field14,
        "border_top_width": field10,
        "border_width": field10,
        "bottom": field16,
        "color": field11,
        "column_gap": field10,
        "direction": field18,
        "disabled": field51,
        "display": field19,
        "elevation": field14,
        "end": field16,
        "flex": field10,
        "flex_basis": field16,
        "flex_direction": field20,
        "flex_grow": field10,
        "flex_shrink": field10,
        "flex_wrap": field21,
        "font_family": field22,
        "font_size": field10,
        "font_weight": field23,
        "gap": field10,
        "gestures": field24,
        "height": field16,
        "important_for_accessibility": field52,
        "italic": field12,
        "justify_content": field25,
        "left": field16,
        "letter_spacing": field10,
        "line_height": field10,
        "margin": field26,
        "margin_bottom": field27,
        "margin_end": field27,
        "margin_horizontal": field27,
        "margin_left": field27,
        "margin_right": field27,
        "margin_start": field27,
        "margin_top": field27,
        "margin_vertical": field27,
        "max_height": field16,
        "max_lines": field28,
        "max_width": field16,
        "min_height": field16,
        "min_width": field16,
        "on_accessibility_action": field53,
        "on_layout": field29,
        "on_long_press": field54,
        "on_press": field54,
        "opacity": field30,
        "overflow": field31,
        "padding": field32,
        "padding_bottom": field16,
        "padding_end": field16,
        "padding_horizontal": field16,
        "padding_left": field16,
        "padding_right": field16,
        "padding_start": field16,
        "padding_top": field16,
        "padding_vertical": field16,
        "placeholder_color": field13,
        "pointer_events": field33,
        "position": field34,
        "ref": field35,
        "right": field16,
        "row_gap": field10,
        "shadow_color": field13,
        "shadow_offset": field36,
        "shadow_opacity": field14,
        "shadow_radius": field14,
        "spacing": field10,
        "start": field16,
        "test_id": field43,
        "text_align": field38,
        "text_decoration": field39,
        "text_shadow_color": field13,
        "text_shadow_offset": field36,
        "text_shadow_radius": field14,
        "text_transform": field40,
        "tint_color": field13,
        "top": field16,
        "transform": field41,
        "width": field16,
        "z_index": field42
    ] }
    private static func component31() -> [String: Field] { [
        "_pn_animated_events": field0,
        "_pn_edit_revision": field1,
        "_pn_events": field2,
        "_pn_header_slot": field3,
        "_pn_layout": field4,
        "_pn_list_key": field5,
        "accessibility_actions": field47,
        "accessibility_hint": field43,
        "accessibility_label": field43,
        "accessibility_live_region": field48,
        "accessibility_role": field43,
        "accessibility_state": field49,
        "accessibility_value": field50,
        "accessible": field44,
        "align_content": field7,
        "align_items": field8,
        "align_self": field8,
        "aspect_ratio": field10,
        "background_color": field11,
        "bold": field12,
        "border_bottom_color": field13,
        "border_bottom_left_radius": field14,
        "border_bottom_right_radius": field14,
        "border_bottom_width": field10,
        "border_color": field13,
        "border_left_color": field13,
        "border_left_width": field10,
        "border_radius": field14,
        "border_right_color": field13,
        "border_right_width": field10,
        "border_style": field15,
        "border_top_color": field13,
        "border_top_left_radius": field14,
        "border_top_right_radius": field14,
        "border_top_width": field10,
        "border_width": field10,
        "bottom": field16,
        "color": field11,
        "column_gap": field10,
        "direction": field18,
        "display": field19,
        "elevation": field14,
        "end": field16,
        "flex": field10,
        "flex_basis": field16,
        "flex_direction": field20,
        "flex_grow": field10,
        "flex_shrink": field10,
        "flex_wrap": field21,
        "font_family": field22,
        "font_size": field10,
        "font_weight": field23,
        "gap": field10,
        "gestures": field24,
        "height": field16,
        "hit_slop": field58,
        "important_for_accessibility": field52,
        "italic": field12,
        "justify_content": field25,
        "left": field16,
        "letter_spacing": field10,
        "line_height": field10,
        "margin": field26,
        "margin_bottom": field27,
        "margin_end": field27,
        "margin_horizontal": field27,
        "margin_left": field27,
        "margin_right": field27,
        "margin_start": field27,
        "margin_top": field27,
        "margin_vertical": field27,
        "max_height": field16,
        "max_lines": field28,
        "max_width": field16,
        "min_height": field16,
        "min_width": field16,
        "on_accessibility_action": field53,
        "on_layout": field29,
        "opacity": field30,
        "overflow": field31,
        "padding": field32,
        "padding_bottom": field16,
        "padding_end": field16,
        "padding_horizontal": field16,
        "padding_left": field16,
        "padding_right": field16,
        "padding_start": field16,
        "padding_top": field16,
        "padding_vertical": field16,
        "placeholder_color": field13,
        "pointer_events": field33,
        "position": field34,
        "ref": field35,
        "right": field16,
        "row_gap": field10,
        "shadow_color": field13,
        "shadow_offset": field36,
        "shadow_opacity": field14,
        "shadow_radius": field14,
        "spacing": field10,
        "start": field16,
        "test_id": field43,
        "text_align": field38,
        "text_decoration": field39,
        "text_shadow_color": field13,
        "text_shadow_offset": field36,
        "text_shadow_radius": field14,
        "text_transform": field40,
        "tint_color": field13,
        "top": field16,
        "transform": field41,
        "width": field16,
        "z_index": field42
    ] }
    private static func match144(_ value: Any) -> Bool {
        guard let value = value as? [Any] else { return false }
        return value.allSatisfy { match20($0) }
    }
    private static func match143(_ value: Any) -> Bool {
        guard let value = value as? [String: Any] else { return false }
        guard value["base"] != nil else { return false }
        guard value["revision"] != nil else { return false }
        guard value["changes"] != nil else { return false }
        for (key, item) in value {
            let valid: Bool
            switch key {
            case "base": valid = match1(item)
            case "changes": valid = match144(item)
            case "revision": valid = match1(item)
            default: valid = false
            }
            if !valid { return false }
        }
        return true
    }
    private static func component32() -> [String: Field] { [
        "_pn_animated_events": field0,
        "_pn_edit_revision": field1,
        "_pn_events": field2,
        "_pn_header_slot": field3,
        "_pn_layout": field4,
        "_pn_list_key": field5,
        "accessibility_actions": field47,
        "accessibility_hint": field43,
        "accessibility_label": field43,
        "accessibility_live_region": field48,
        "accessibility_role": field43,
        "accessibility_state": field49,
        "accessibility_value": field50,
        "accessible": field44,
        "align_content": field7,
        "align_items": field8,
        "align_self": field8,
        "aspect_ratio": field10,
        "background_color": field11,
        "bold": field12,
        "border_bottom_color": field13,
        "border_bottom_left_radius": field14,
        "border_bottom_right_radius": field14,
        "border_bottom_width": field10,
        "border_color": field13,
        "border_left_color": field13,
        "border_left_width": field10,
        "border_radius": field14,
        "border_right_color": field13,
        "border_right_width": field10,
        "border_style": field15,
        "border_top_color": field13,
        "border_top_left_radius": field14,
        "border_top_right_radius": field14,
        "border_top_width": field10,
        "border_width": field10,
        "bottom": field16,
        "color": field11,
        "column_gap": field10,
        "dataset": field128,
        "direction": field18,
        "display": field19,
        "elevation": field14,
        "end": field16,
        "flex": field10,
        "flex_basis": field16,
        "flex_direction": field20,
        "flex_grow": field10,
        "flex_shrink": field10,
        "flex_wrap": field21,
        "font_family": field22,
        "font_size": field10,
        "font_weight": field23,
        "gap": field10,
        "gestures": field24,
        "height": field16,
        "hit_slop": field58,
        "horizontal": field84,
        "important_for_accessibility": field52,
        "italic": field12,
        "justify_content": field25,
        "left": field16,
        "letter_spacing": field10,
        "line_height": field10,
        "margin": field26,
        "margin_bottom": field27,
        "margin_end": field27,
        "margin_horizontal": field27,
        "margin_left": field27,
        "margin_right": field27,
        "margin_start": field27,
        "margin_top": field27,
        "margin_vertical": field27,
        "max_height": field16,
        "max_lines": field28,
        "max_width": field16,
        "min_height": field16,
        "min_width": field16,
        "on_accessibility_action": field53,
        "on_bind_row": field129,
        "on_layout": field29,
        "on_scroll": field129,
        "on_window": field129,
        "opacity": field30,
        "overflow": field31,
        "padding": field32,
        "padding_bottom": field16,
        "padding_end": field16,
        "padding_horizontal": field16,
        "padding_left": field16,
        "padding_right": field16,
        "padding_start": field16,
        "padding_top": field16,
        "padding_vertical": field16,
        "placeholder_color": field13,
        "pointer_events": field33,
        "position": field34,
        "ref": field35,
        "refresh_control": field95,
        "right": field16,
        "row_gap": field10,
        "shadow_color": field13,
        "shadow_offset": field36,
        "shadow_opacity": field14,
        "shadow_radius": field14,
        "shows_scroll_indicator": field84,
        "spacing": field10,
        "start": field16,
        "test_id": field43,
        "text_align": field38,
        "text_decoration": field39,
        "text_shadow_color": field13,
        "text_shadow_offset": field36,
        "text_shadow_radius": field14,
        "text_transform": field40,
        "tint_color": field13,
        "top": field16,
        "transform": field41,
        "width": field16,
        "z_index": field42
    ] }
    private static func match145(_ value: Any) -> Bool {
        return match27(value) || match14(value)
    }
    private static func component33() -> [String: Field] { [
        "_pn_animated_events": field0,
        "_pn_edit_revision": field1,
        "_pn_events": field2,
        "_pn_header_slot": field3,
        "_pn_layout": field4,
        "_pn_list_key": field5,
        "accessibility_role": field6,
        "align_content": field7,
        "align_items": field8,
        "align_self": field8,
        "aspect_ratio": field10,
        "background_color": field11,
        "bold": field12,
        "border_bottom_color": field13,
        "border_bottom_left_radius": field14,
        "border_bottom_right_radius": field14,
        "border_bottom_width": field10,
        "border_color": field13,
        "border_left_color": field13,
        "border_left_width": field10,
        "border_radius": field14,
        "border_right_color": field13,
        "border_right_width": field10,
        "border_style": field15,
        "border_top_color": field13,
        "border_top_left_radius": field14,
        "border_top_right_radius": field14,
        "border_top_width": field10,
        "border_width": field10,
        "bottom": field16,
        "color": field11,
        "column_gap": field10,
        "direction": field18,
        "display": field19,
        "elevation": field14,
        "end": field16,
        "flex": field10,
        "flex_basis": field16,
        "flex_direction": field20,
        "flex_grow": field10,
        "flex_shrink": field10,
        "flex_wrap": field21,
        "font_family": field22,
        "font_size": field10,
        "font_weight": field23,
        "gap": field10,
        "gestures": field24,
        "height": field16,
        "html": field43,
        "inject_javascript": field43,
        "italic": field12,
        "justify_content": field25,
        "left": field16,
        "letter_spacing": field10,
        "line_height": field10,
        "margin": field26,
        "margin_bottom": field27,
        "margin_end": field27,
        "margin_horizontal": field27,
        "margin_left": field27,
        "margin_right": field27,
        "margin_start": field27,
        "margin_top": field27,
        "margin_vertical": field27,
        "max_height": field16,
        "max_lines": field28,
        "max_width": field16,
        "min_height": field16,
        "min_width": field16,
        "on_error": field53,
        "on_layout": field29,
        "on_load": field53,
        "on_load_start": field53,
        "on_message": field53,
        "on_navigation_state_change": field130,
        "opacity": field30,
        "overflow": field31,
        "padding": field32,
        "padding_bottom": field16,
        "padding_end": field16,
        "padding_horizontal": field16,
        "padding_left": field16,
        "padding_right": field16,
        "padding_start": field16,
        "padding_top": field16,
        "padding_vertical": field16,
        "placeholder_color": field13,
        "pointer_events": field33,
        "position": field34,
        "ref": field35,
        "right": field16,
        "row_gap": field10,
        "scroll_enabled": field9,
        "shadow_color": field13,
        "shadow_offset": field36,
        "shadow_opacity": field14,
        "shadow_radius": field14,
        "spacing": field10,
        "start": field16,
        "text_align": field38,
        "text_decoration": field39,
        "text_shadow_color": field13,
        "text_shadow_offset": field36,
        "text_shadow_radius": field14,
        "text_transform": field40,
        "tint_color": field13,
        "top": field16,
        "transform": field41,
        "url": field131,
        "width": field16,
        "z_index": field42
    ] }
    private static func match146(_ value: Any) -> Bool {
        guard let value = value as? [String: Any] else { return false }
        for (key, item) in value {
            let valid: Bool
            switch key {
            default: valid = false
            }
            if !valid { return false }
        }
        return true
    }
    private static func match147(_ value: Any) -> Bool {
        guard let value = value as? [String: Any] else { return false }
        for (key, item) in value {
            let valid: Bool
            switch key {
            case "animated": valid = match5(item)
            default: valid = false
            }
            if !valid { return false }
        }
        return true
    }
    private static func match148(_ value: Any) -> Bool {
        guard let value = value as? [String: Any] else { return false }
        for (key, item) in value {
            let valid: Bool
            switch key {
            case "animated": valid = match5(item)
            case "x": valid = match8(item)
            case "y": valid = match8(item)
            default: valid = false
            }
            if !valid { return false }
        }
        return true
    }
    private static func match149(_ value: Any) -> Bool {
        guard let value = value as? [String: Any] else { return false }
        guard value["start"] != nil else { return false }
        for (key, item) in value {
            let valid: Bool
            switch key {
            case "end": valid = match1(item)
            case "start": valid = match1(item)
            default: valid = false
            }
            if !valid { return false }
        }
        return true
    }
    private static func match150(_ value: Any) -> Bool {
        guard let value = value as? [String: Any] else { return false }
        guard value["index"] != nil else { return false }
        for (key, item) in value {
            let valid: Bool
            switch key {
            case "animated": valid = match5(item)
            case "index": valid = match1(item)
            default: valid = false
            }
            if !valid { return false }
        }
        return true
    }
    private static func match151(_ value: Any) -> Bool {
        guard let value = value as? [String: Any] else { return false }
        guard value["script"] != nil else { return false }
        for (key, item) in value {
            let valid: Bool
            switch key {
            case "script": valid = match3(item)
            default: valid = false
            }
            if !valid { return false }
        }
        return true
    }
    private static func match152(_ value: Any) -> Bool {
        guard let value = value as? [String: Any] else { return false }
        guard value["url"] != nil else { return false }
        for (key, item) in value {
            let valid: Bool
            switch key {
            case "url": valid = match3(item)
            default: valid = false
            }
            if !valid { return false }
        }
        return true
    }
    private static func match153(_ value: Any) -> Bool {
        guard let value = value as? [String: Any] else { return false }
        guard value["message"] != nil else { return false }
        for (key, item) in value {
            let valid: Bool
            switch key {
            case "message": valid = match3(item)
            default: valid = false
            }
            if !valid { return false }
        }
        return true
    }
    private static func match154(_ value: Any) -> Bool {
        guard let value = value as? [String: Any] else { return false }
        guard value["tag"] != nil else { return false }
        for (key, item) in value {
            let valid: Bool
            switch key {
            case "tag": valid = match1(item)
            default: valid = false
            }
            if !valid { return false }
        }
        return true
    }
    private static func match155(_ value: Any) -> Bool {
        guard let value = value as? [String: Any] else { return false }
        guard value["title"] != nil else { return false }
        guard value["message"] != nil else { return false }
        guard value["buttons"] != nil else { return false }
        guard value["style"] != nil else { return false }
        for (key, item) in value {
            let valid: Bool
            switch key {
            case "buttons": valid = match91(item)
            case "message": valid = match57(item)
            case "style": valid = match3(item)
            case "title": valid = match3(item)
            default: valid = false
            }
            if !valid { return false }
        }
        return true
    }
    private static func match159(_ value: Any) -> Bool {
        guard let value = value as? [String: Any] else { return false }
        guard value["family"] != nil else { return false }
        guard value["italic"] != nil else { return false }
        guard value["path"] != nil else { return false }
        guard value["postscript_name"] != nil else { return false }
        guard value["weight"] != nil else { return false }
        for (key, item) in value {
            let valid: Bool
            switch key {
            case "family": valid = match3(item)
            case "italic": valid = match5(item)
            case "path": valid = match3(item)
            case "postscript_name": valid = match3(item)
            case "weight": valid = match1(item)
            default: valid = false
            }
            if !valid { return false }
        }
        return true
    }
    private static func match158(_ value: Any) -> Bool {
        guard let value = value as? [Any] else { return false }
        return value.allSatisfy { match159($0) }
    }
    private static func match160(_ value: Any) -> Bool {
        guard let value = value as? [String: Any] else { return false }
        for (key, item) in value {
            let valid: Bool
            switch key {
            default: valid = match81(item)
            }
            if !valid { return false }
        }
        return true
    }
    private static func match157(_ value: Any) -> Bool {
        guard let value = value as? [String: Any] else { return false }
        for (key, item) in value {
            let valid: Bool
            switch key {
            case "files": valid = match2(item)
            case "fonts": valid = match158(item)
            case "variants": valid = match160(item)
            default: valid = false
            }
            if !valid { return false }
        }
        return true
    }
    private static func match156(_ value: Any) -> Bool {
        guard let value = value as? [String: Any] else { return false }
        guard value["overlay"] != nil else { return false }
        guard value["manifest"] != nil else { return false }
        for (key, item) in value {
            let valid: Bool
            switch key {
            case "manifest": valid = match157(item)
            case "overlay": valid = match57(item)
            default: valid = false
            }
            if !valid { return false }
        }
        return true
    }
    private static func match161(_ value: Any) -> Bool {
        guard let value = value as? [String: Any] else { return false }
        guard value["path"] != nil else { return false }
        for (key, item) in value {
            let valid: Bool
            switch key {
            case "path": valid = match3(item)
            default: valid = false
            }
            if !valid { return false }
        }
        return true
    }
    private static func match162(_ value: Any) -> Bool {
        guard let value = value as? [String: Any] else { return false }
        for (key, item) in value {
            let valid: Bool
            switch key {
            case "reason": valid = match3(item)
            default: valid = false
            }
            if !valid { return false }
        }
        return true
    }
    private static func match163(_ value: Any) -> Bool {
        guard let value = value as? [String: Any] else { return false }
        for (key, item) in value {
            let valid: Bool
            switch key {
            case "allow_editing": valid = match5(item)
            case "quality": valid = match8(item)
            default: valid = false
            }
            if !valid { return false }
        }
        return true
    }
    private static func match164(_ value: Any) -> Bool {
        guard let value = value as? [String: Any] else { return false }
        guard value["text"] != nil else { return false }
        for (key, item) in value {
            let valid: Bool
            switch key {
            case "text": valid = match3(item)
            default: valid = false
            }
            if !valid { return false }
        }
        return true
    }
    private static func match165(_ value: Any) -> Bool {
        guard let value = value as? [String: Any] else { return false }
        for (key, item) in value {
            let valid: Bool
            switch key {
            case "style": valid = match3(item)
            default: valid = false
            }
            if !valid { return false }
        }
        return true
    }
    private static func match166(_ value: Any) -> Bool {
        guard let value = value as? [String: Any] else { return false }
        for (key, item) in value {
            let valid: Bool
            switch key {
            case "type": valid = match3(item)
            default: valid = false
            }
            if !valid { return false }
        }
        return true
    }
    private static func match167(_ value: Any) -> Bool {
        guard let value = value as? [String: Any] else { return false }
        for (key, item) in value {
            let valid: Bool
            switch key {
            case "duration_ms": valid = match1(item)
            default: valid = false
            }
            if !valid { return false }
        }
        return true
    }
    private static func match168(_ value: Any) -> Bool {
        guard let value = value as? [String: Any] else { return false }
        guard value["uri"] != nil else { return false }
        for (key, item) in value {
            let valid: Bool
            switch key {
            case "uri": valid = match3(item)
            default: valid = false
            }
            if !valid { return false }
        }
        return true
    }
    private static func match170(_ value: Any) -> Bool {
        return ((value as? String) == "balanced") || ((value as? String) == "high")
    }
    private static func match169(_ value: Any) -> Bool {
        guard let value = value as? [String: Any] else { return false }
        for (key, item) in value {
            let valid: Bool
            switch key {
            case "accuracy": valid = match170(item)
            case "timeout": valid = match8(item)
            default: valid = false
            }
            if !valid { return false }
        }
        return true
    }
    private static func match171(_ value: Any) -> Bool {
        guard let value = value as? [String: Any] else { return false }
        for (key, item) in value {
            let valid: Bool
            switch key {
            case "identifier": valid = match3(item)
            default: valid = false
            }
            if !valid { return false }
        }
        return true
    }
    private static func match172(_ value: Any) -> Bool {
        guard let value = value as? [String: Any] else { return false }
        guard value["title"] != nil else { return false }
        for (key, item) in value {
            let valid: Bool
            switch key {
            case "body": valid = match3(item)
            case "delay_seconds": valid = match8(item)
            case "identifier": valid = match3(item)
            case "title": valid = match3(item)
            default: valid = false
            }
            if !valid { return false }
        }
        return true
    }
    private static func match173(_ value: Any) -> Bool {
        guard let value = value as? [String: Any] else { return false }
        guard value["permission"] != nil else { return false }
        for (key, item) in value {
            let valid: Bool
            switch key {
            case "permission": valid = match3(item)
            default: valid = false
            }
            if !valid { return false }
        }
        return true
    }
    private static func match174(_ value: Any) -> Bool {
        guard let value = value as? [String: Any] else { return false }
        guard value["key"] != nil else { return false }
        for (key, item) in value {
            let valid: Bool
            switch key {
            case "key": valid = match3(item)
            default: valid = false
            }
            if !valid { return false }
        }
        return true
    }
    private static func match175(_ value: Any) -> Bool {
        guard let value = value as? [String: Any] else { return false }
        guard value["key"] != nil else { return false }
        guard value["value"] != nil else { return false }
        for (key, item) in value {
            let valid: Bool
            switch key {
            case "key": valid = match3(item)
            case "value": valid = match3(item)
            default: valid = false
            }
            if !valid { return false }
        }
        return true
    }
    private static func match176(_ value: Any) -> Bool {
        guard let value = value as? [String: Any] else { return false }
        for (key, item) in value {
            let valid: Bool
            switch key {
            case "message": valid = match57(item)
            case "title": valid = match57(item)
            case "url": valid = match57(item)
            default: valid = false
            }
            if !valid { return false }
        }
        return true
    }
    private static func match177(_ value: Any) -> Bool {
        guard let value = value as? [String: Any] else { return false }
        guard value["tag"] != nil else { return false }
        guard value["script"] != nil else { return false }
        for (key, item) in value {
            let valid: Bool
            switch key {
            case "script": valid = match3(item)
            case "tag": valid = match1(item)
            default: valid = false
            }
            if !valid { return false }
        }
        return true
    }
    private static let field0 = Field(match0, true, true, false, false, PNValues.defaultValue("null"))
    private static let field1 = Field(match1, true, true, false, false, PNValues.defaultValue("null"))
    private static let field2 = Field(match2, true, true, false, false, PNValues.defaultValue("null"))
    private static let field3 = Field(match4, true, true, false, false, PNValues.defaultValue("null"))
    private static let field4 = Field(match5, true, false, false, false, PNValues.defaultValue("null"))
    private static let field5 = Field(match3, true, true, false, false, PNValues.defaultValue("null"))
    private static let field6 = Field(match3, true, false, false, false, PNValues.defaultValue("null"))
    private static let field7 = Field(match6, true, true, false, false, PNValues.defaultValue("null"))
    private static let field8 = Field(match7, true, true, false, false, PNValues.defaultValue("null"))
    private static let field9 = Field(match5, true, false, false, false, PNValues.defaultValue("true"))
    private static let field10 = Field(match8, true, true, false, false, PNValues.defaultValue("null"))
    private static let field11 = Field(match9, true, false, false, false, PNValues.defaultValue("null"))
    private static let field12 = Field(match5, true, true, false, false, PNValues.defaultValue("null"))
    private static let field13 = Field(match9, true, false, false, false, PNValues.defaultValue("null"))
    private static let field14 = Field(match8, true, false, false, false, PNValues.defaultValue("null"))
    private static let field15 = Field(match11, true, false, false, false, PNValues.defaultValue("null"))
    private static let field16 = Field(match12, true, true, false, false, PNValues.defaultValue("null"))
    private static let field17 = Field(match13, true, false, false, false, PNValues.defaultValue("null"))
    private static let field18 = Field(match15, true, true, false, false, PNValues.defaultValue("null"))
    private static let field19 = Field(match16, true, true, false, false, PNValues.defaultValue("null"))
    private static let field20 = Field(match17, true, true, false, false, PNValues.defaultValue("null"))
    private static let field21 = Field(match18, true, true, false, false, PNValues.defaultValue("null"))
    private static let field22 = Field(match3, true, true, false, false, PNValues.defaultValue("null"))
    private static let field23 = Field(match19, true, true, false, false, PNValues.defaultValue("null"))
    private static let field24 = Field(match20, true, true, false, false, PNValues.defaultValue("null"))
    private static let field25 = Field(match22, true, true, false, false, PNValues.defaultValue("null"))
    private static let field26 = Field(match23, true, true, false, false, PNValues.defaultValue("null"))
    private static let field27 = Field(match26, true, true, false, false, PNValues.defaultValue("null"))
    private static let field28 = Field(match1, true, true, false, false, PNValues.defaultValue("null"))
    private static let field29 = Field(match27, true, false, false, false, PNValues.defaultValue("null"))
    private static let field30 = Field(match8, true, false, false, false, PNValues.defaultValue("null"))
    private static let field31 = Field(match28, true, false, false, false, PNValues.defaultValue("null"))
    private static let field32 = Field(match29, true, true, false, false, PNValues.defaultValue("null"))
    private static let field33 = Field(match30, true, false, false, false, PNValues.defaultValue("null"))
    private static let field34 = Field(match31, true, true, false, false, PNValues.defaultValue("null"))
    private static let field35 = Field(match21, true, false, false, false, PNValues.defaultValue("null"))
    private static let field36 = Field(match32, true, false, false, false, PNValues.defaultValue("null"))
    private static let field37 = Field(match36, true, false, false, false, PNValues.defaultValue("\"small\""))
    private static let field38 = Field(match37, true, false, false, false, PNValues.defaultValue("null"))
    private static let field39 = Field(match38, true, false, false, false, PNValues.defaultValue("null"))
    private static let field40 = Field(match39, true, true, false, false, PNValues.defaultValue("null"))
    private static let field41 = Field(match40, true, false, false, false, PNValues.defaultValue("null"))
    private static let field42 = Field(match1, true, false, false, false, PNValues.defaultValue("null"))
    private static let field43 = Field(match57, true, false, false, false, PNValues.defaultValue("null"))
    private static let field44 = Field(match58, true, false, false, false, PNValues.defaultValue("null"))
    private static let field45 = Field(match59, true, false, false, false, PNValues.defaultValue("\"regular\""))
    private static let field46 = Field(match8, true, false, false, false, PNValues.defaultValue("100.0"))
    private static let field47 = Field(match60, true, false, false, false, PNValues.defaultValue("null"))
    private static let field48 = Field(match63, true, false, false, false, PNValues.defaultValue("null"))
    private static let field49 = Field(match65, true, false, false, false, PNValues.defaultValue("null"))
    private static let field50 = Field(match69, true, false, false, false, PNValues.defaultValue("null"))
    private static let field51 = Field(match5, true, false, false, false, PNValues.defaultValue("false"))
    private static let field52 = Field(match71, true, false, false, false, PNValues.defaultValue("null"))
    private static let field53 = Field(match73, true, false, false, false, PNValues.defaultValue("null"))
    private static let field54 = Field(match74, true, false, false, false, PNValues.defaultValue("null"))
    private static let field55 = Field(match3, true, true, false, false, PNValues.defaultValue("\"\""))
    private static let field56 = Field(match75, true, false, false, false, PNValues.defaultValue("null"))
    private static let field57 = Field(match5, true, true, false, false, PNValues.defaultValue("false"))
    private static let field58 = Field(match76, true, false, false, false, PNValues.defaultValue("null"))
    private static let field59 = Field(match78, true, false, false, false, PNValues.defaultValue("\"date\""))
    private static let field60 = Field(match57, true, true, false, false, PNValues.defaultValue("null"))
    private static let field61 = Field(match79, true, false, false, false, PNValues.defaultValue("null"))
    private static let field62 = Field(match80, true, false, false, false, PNValues.defaultValue("null"))
    private static let field63 = Field(match82, true, false, false, false, PNValues.defaultValue("null"))
    private static let field64 = Field(match13, true, false, false, false, PNValues.defaultValue("null"))
    private static let field65 = Field(match83, true, false, false, false, PNValues.defaultValue("null"))
    private static let field66 = Field(match85, true, false, false, false, PNValues.defaultValue("\"padding\""))
    private static let field67 = Field(match8, true, false, false, false, PNValues.defaultValue("0.0"))
    private static let field68 = Field(match86, true, false, false, false, PNValues.defaultValue("null"))
    private static let field69 = Field(match34, true, false, false, false, PNValues.defaultValue("[0.0,1.0]"))
    private static let field70 = Field(match87, true, false, false, false, PNValues.defaultValue("null"))
    private static let field71 = Field(match34, true, false, false, false, PNValues.defaultValue("[0.0,0.0]"))
    private static let field72 = Field(match88, true, false, false, false, PNValues.defaultValue("\"slide\""))
    private static let field73 = Field(match89, true, false, false, false, PNValues.defaultValue("\"page_sheet\""))
    private static let field74 = Field(match90, true, false, false, false, PNValues.defaultValue("null"))
    private static let field75 = Field(match92, true, false, false, false, PNValues.defaultValue("null"))
    private static let field76 = Field(match3, true, false, false, false, PNValues.defaultValue("\"Select\\u2026\""))
    private static let field77 = Field(match54, true, true, false, false, PNValues.defaultValue("null"))
    private static let field78 = Field(match93, true, false, false, false, PNValues.defaultValue("null"))
    private static let field79 = Field(match8, true, false, false, false, PNValues.defaultValue("500"))
    private static let field80 = Field(match8, true, false, false, false, PNValues.defaultValue("0.6"))
    private static let field81 = Field(match5, true, false, true, false, PNValues.defaultValue("false"))
    private static let field82 = Field(match8, true, true, false, false, PNValues.defaultValue("0.0"))
    private static let field83 = Field(match95, true, false, false, false, PNValues.defaultValue("null"))
    private static let field84 = Field(match5, true, true, false, false, PNValues.defaultValue("null"))
    private static let field85 = Field(match98, true, true, false, false, PNValues.defaultValue("null"))
    private static let field86 = Field(match53, true, true, false, false, PNValues.defaultValue("null"))
    private static let field87 = Field(match99, true, true, false, false, PNValues.defaultValue("null"))
    private static let field88 = Field(match100, true, true, false, false, PNValues.defaultValue("null"))
    private static let field89 = Field(match27, true, true, false, false, PNValues.defaultValue("null"))
    private static let field90 = Field(match101, true, false, false, false, PNValues.defaultValue("null"))
    private static let field91 = Field(match102, true, false, false, false, PNValues.defaultValue("\"normal\""))
    private static let field92 = Field(match104, true, false, false, false, PNValues.defaultValue("null"))
    private static let field93 = Field(match106, true, false, false, false, PNValues.defaultValue("\"never\""))
    private static let field94 = Field(match107, true, false, false, false, PNValues.defaultValue("null"))
    private static let field95 = Field(match108, true, true, false, false, PNValues.defaultValue("null"))
    private static let field96 = Field(match8, true, false, false, false, PNValues.defaultValue("16"))
    private static let field97 = Field(match109, true, false, false, false, PNValues.defaultValue("\"start\""))
    private static let field98 = Field(match110, true, false, false, false, PNValues.defaultValue("null"))
    private static let field99 = Field(match111, true, false, false, false, PNValues.defaultValue("null"))
    private static let field100 = Field(match1, true, false, false, false, PNValues.defaultValue("0"))
    private static let field101 = Field(match8, true, false, false, false, PNValues.defaultValue("1.0"))
    private static let field102 = Field(match112, true, false, false, false, PNValues.defaultValue("null"))
    private static let field103 = Field(match79, true, true, false, false, PNValues.defaultValue("null"))
    private static let field104 = Field(match113, true, false, false, false, PNValues.defaultValue("null"))
    private static let field105 = Field(match115, true, false, false, false, PNValues.defaultValue("null"))
    private static let field106 = Field(match117, true, false, false, false, PNValues.defaultValue("\"meet\""))
    private static let field107 = Field(match118, true, false, false, false, PNValues.defaultValue("null"))
    private static let field108 = Field(match122, true, false, false, false, PNValues.defaultValue("null"))
    private static let field109 = Field(match124, true, false, false, false, PNValues.defaultValue("null"))
    private static let field110 = Field(match126, true, true, false, false, PNValues.defaultValue("null"))
    private static let field111 = Field(match27, true, true, false, false, PNValues.defaultValue("null"))
    private static let field112 = Field(match5, true, true, false, false, PNValues.defaultValue("true"))
    private static let field113 = Field(match129, true, true, false, false, PNValues.defaultValue("\"tail\""))
    private static let field114 = Field(match27, true, false, false, false, PNValues.defaultValue("null"))
    private static let field115 = Field(match20, true, true, false, false, PNValues.defaultValue("null"))
    private static let field116 = Field(match3, true, true, false, false, PNValues.defaultValue("null"))
    private static let field117 = Field(match130, true, false, false, false, PNValues.defaultValue("null"))
    private static let field118 = Field(match132, true, false, false, false, PNValues.defaultValue("\"default\""))
    private static let field119 = Field(match133, true, false, false, false, PNValues.defaultValue("null"))
    private static let field120 = Field(match135, true, false, false, false, PNValues.defaultValue("null"))
    private static let field121 = Field(match5, true, true, true, false, PNValues.defaultValue("false"))
    private static let field122 = Field(match136, true, false, false, false, PNValues.defaultValue("null"))
    private static let field123 = Field(match137, true, false, false, false, PNValues.defaultValue("null"))
    private static let field124 = Field(match138, true, false, false, false, PNValues.defaultValue("null"))
    private static let field125 = Field(match139, true, false, false, false, PNValues.defaultValue("null"))
    private static let field126 = Field(match141, true, false, false, false, PNValues.defaultValue("null"))
    private static let field127 = Field(match8, true, false, false, false, PNValues.defaultValue("0.2"))
    private static let field128 = Field(match143, true, true, false, true, PNValues.defaultValue("null"))
    private static let field129 = Field(match27, true, true, false, false, PNValues.defaultValue("null"))
    private static let field130 = Field(match145, true, false, false, false, PNValues.defaultValue("null"))
    private static let field131 = Field(match3, true, false, false, false, PNValues.defaultValue("\"\""))
    private static let components: [String: [String: Field]] = [
        "ActivityIndicator": component0(),
        "BlurView": component1(),
        "Button": component2(),
        "Checkbox": component3(),
        "Column": component4(),
        "DatePicker": component5(),
        "Image": component6(),
        "ImageBackground": component7(),
        "KeyboardAvoidingView": component8(),
        "LinearGradient": component9(),
        "Modal": component10(),
        "Picker": component11(),
        "Portal": component12(),
        "Pressable": component13(),
        "ProgressBar": component14(),
        "RefreshControl": component15(),
        "Row": component16(),
        "SafeAreaView": component17(),
        "Screen": component18(),
        "ScreenStack": component19(),
        "ScrollView": component20(),
        "SegmentedControl": component21(),
        "Slider": component22(),
        "Spacer": component23(),
        "StatusBar": component24(),
        "Svg": component25(),
        "Switch": component26(),
        "TabBar": component27(),
        "Text": component28(),
        "TextInput": component29(),
        "TouchableOpacity": component30(),
        "View": component31(),
        "VirtualList": component32(),
        "WebView": component33()
    ]
    private static let commands: [String: (Any) -> Bool] = [
        "ScreenStack.restore_stack": match146,
        "ScrollView.flash_scroll_indicators": match146,
        "ScrollView.get_scroll_offset": match146,
        "ScrollView.scroll_to_end": match147,
        "ScrollView.scroll_to_offset": match148,
        "TextInput.blur": match146,
        "TextInput.clear": match146,
        "TextInput.focus": match146,
        "TextInput.get_value": match146,
        "TextInput.select_all": match146,
        "TextInput.set_selection": match149,
        "VirtualList.flash_scroll_indicators": match146,
        "VirtualList.get_scroll_offset": match146,
        "VirtualList.scroll_to_end": match147,
        "VirtualList.scroll_to_index": match150,
        "VirtualList.scroll_to_offset": match148,
        "WebView.can_go_back": match146,
        "WebView.can_go_forward": match146,
        "WebView.get_url": match146,
        "WebView.go_back": match146,
        "WebView.go_forward": match146,
        "WebView.inject_javascript": match151,
        "WebView.load_url": match152,
        "WebView.reload": match146,
        "WebView.stop_loading": match146
    ]
    private static let modules: [String: (Any) -> Bool] = [
        "AccessibilityInfo.announce": match153,
        "AccessibilityInfo.is_reduce_motion_enabled": match146,
        "AccessibilityInfo.is_screen_reader_enabled": match146,
        "AccessibilityInfo.set_accessibility_focus": match154,
        "Alert.present": match155,
        "Alert.show": match155,
        "AppState.current_state": match146,
        "Assets.configure": match156,
        "Assets.exists": match161,
        "Assets.read": match161,
        "Battery.get_level": match146,
        "Battery.get_state": match146,
        "Biometrics.authenticate": match162,
        "Biometrics.is_available": match146,
        "Camera.pick_from_gallery": match163,
        "Camera.take_photo": match163,
        "Clipboard.get_string": match146,
        "Clipboard.set_string": match164,
        "Device.info": match146,
        "Haptics.cancel": match146,
        "Haptics.impact": match165,
        "Haptics.notification": match166,
        "Haptics.selection": match146,
        "Haptics.vibrate": match167,
        "Images.clear_cache": match146,
        "Images.get_size": match168,
        "Images.prefetch": match168,
        "Keyboard.dismiss": match146,
        "Keyboard.is_visible": match146,
        "Linking.can_open_url": match152,
        "Linking.open_settings": match146,
        "Linking.open_url": match152,
        "Localization.get_locales": match146,
        "Localization.get_timezone": match146,
        "Location.get_current": match169,
        "NetInfo.fetch": match146,
        "Notifications.cancel": match171,
        "Notifications.get_device_token": match146,
        "Notifications.request_permission": match146,
        "Notifications.schedule": match172,
        "Permissions.check": match173,
        "Permissions.request": match173,
        "SecureStore.clear": match146,
        "SecureStore.delete_item": match174,
        "SecureStore.get_item": match174,
        "SecureStore.set_item": match175,
        "Share.share": match176,
        "Storage.all_keys": match146,
        "Storage.clear": match146,
        "Storage.delete": match174,
        "Storage.get": match174,
        "Storage.set": match175,
        "WebViews.eval_js": match177
    ]
    private static func isBoolean(_ value: Any) -> Bool {
        (value as? NSNumber).map { CFGetTypeID($0) == CFBooleanGetTypeID() } ?? false
    }
    private static func isNumber(_ value: Any) -> Bool {
        (value as? NSNumber).map { CFGetTypeID($0) != CFBooleanGetTypeID() && $0.doubleValue.isFinite } ?? false
    }
    private static func isInteger(_ value: Any) -> Bool {
        guard isNumber(value), let number = value as? NSNumber else { return false }
        return abs(number.doubleValue) <= 9_007_199_254_740_991 && number.doubleValue.rounded() == number.doubleValue
    }
    public static func validate(_ name: String, _ props: [String: Any], partial: Bool = false) -> Bool {
        guard let fields = components[name] else { return false }
        if !partial && fields.contains(where: { $0.value.required && props[$0.key] == nil }) { return false }
        return props.allSatisfy { key, value in fields[key].map { $0.allowed && $0.matches(value) } ?? false }
    }
    public static func changes(_ name: String, _ keys: Set<String>) -> ChangeMask {
        guard let fields = components[name] else { return [.layout, .recreate] }
        var mask: ChangeMask = []
        for key in keys {
            if fields[key]?.layout ?? true { mask.insert(.layout) }
            if fields[key]?.recreate ?? false { mask.insert(.recreate) }
        }
        return mask
    }
    public static func invalidatesLayout(_ name: String, _ changed: [String: Any]) -> Bool {
        changes(name, Set(changed.keys)).contains(.layout)
    }
    public static func validateRemoval(_ name: String, _ changed: [String: Any], _ removed: [String]) -> Bool {
        guard let fields = components[name] else { return false }
        return Set(removed).count == removed.count && removed.allSatisfy { key in
            fields[key].map { !$0.required && $0.allowed && changed[key] == nil } ?? false
        }
    }
    public static func requiresRecreation(_ name: String, _ changed: [String: Any], removed: [String] = []) -> Bool {
        changes(name, Set(changed.keys).union(removed)).contains(.recreate)
    }
    public static func normalize(_ name: String, _ changed: [String: Any], removed: [String] = []) -> [String: Any] {
        var result = changed
        for key in removed { result[key] = components[name]?[key]?.defaultValue ?? NSNull() }
        return result
    }
    public static func validateCommand(_ name: String, _ method: String, _ args: [String: Any]) -> Bool {
        commands[name + "." + method]?(args) ?? false
    }
    public static func validateModule(_ name: String, _ method: String, _ args: [String: Any]) -> Bool {
        if ["Host", "Layout", "Runtime"].contains(name) { return true }
        return modules[name + "." + method]?(args) ?? false
    }
}
