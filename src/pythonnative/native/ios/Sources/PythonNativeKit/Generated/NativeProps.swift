import Foundation

// Generated from Python schemas. Regenerate instead of editing.
public struct ActivityIndicatorProps {
    public let values: [String: Any]
    public init(_ values: [String: Any]) throws {
        self.values = values
    }
    public var width: Any? { values["width"] }
    public var height: Any? { values["height"] }
    public var min_width: Any? { values["min_width"] }
    public var max_width: Any? { values["max_width"] }
    public var min_height: Any? { values["min_height"] }
    public var max_height: Any? { values["max_height"] }
    public var aspect_ratio: Double? { values["aspect_ratio"] as? Double }
    public var flex: Double? { values["flex"] as? Double }
    public var flex_grow: Double? { values["flex_grow"] as? Double }
    public var flex_shrink: Double? { values["flex_shrink"] as? Double }
    public var flex_basis: Any? { values["flex_basis"] }
    public var flex_direction: Any? { values["flex_direction"] }
    public var flex_wrap: Any? { values["flex_wrap"] }
    public var justify_content: Any? { values["justify_content"] }
    public var align_items: Any? { values["align_items"] }
    public var align_self: Any? { values["align_self"] }
    public var align_content: Any? { values["align_content"] }
    public var direction: Any? { values["direction"] }
    public var display: Any? { values["display"] }
    public var position: Any? { values["position"] }
    public var top: Any? { values["top"] }
    public var right: Any? { values["right"] }
    public var bottom: Any? { values["bottom"] }
    public var left: Any? { values["left"] }
    public var start: Any? { values["start"] }
    public var end: Any? { values["end"] }
    public var padding: Any? { values["padding"] }
    public var padding_top: Any? { values["padding_top"] }
    public var padding_bottom: Any? { values["padding_bottom"] }
    public var padding_left: Any? { values["padding_left"] }
    public var padding_right: Any? { values["padding_right"] }
    public var padding_start: Any? { values["padding_start"] }
    public var padding_end: Any? { values["padding_end"] }
    public var padding_horizontal: Any? { values["padding_horizontal"] }
    public var padding_vertical: Any? { values["padding_vertical"] }
    public var margin: Any? { values["margin"] }
    public var margin_top: Any? { values["margin_top"] }
    public var margin_bottom: Any? { values["margin_bottom"] }
    public var margin_left: Any? { values["margin_left"] }
    public var margin_right: Any? { values["margin_right"] }
    public var margin_start: Any? { values["margin_start"] }
    public var margin_end: Any? { values["margin_end"] }
    public var margin_horizontal: Any? { values["margin_horizontal"] }
    public var margin_vertical: Any? { values["margin_vertical"] }
    public var spacing: Double? { values["spacing"] as? Double }
    public var gap: Double? { values["gap"] as? Double }
    public var row_gap: Double? { values["row_gap"] as? Double }
    public var column_gap: Double? { values["column_gap"] as? Double }
    public var overflow: Any? { values["overflow"] }
    public var background_color: String? { values["background_color"] as? String }
    public var color: Any? { values["color"] }
    public var border_color: String? { values["border_color"] as? String }
    public var placeholder_color: String? { values["placeholder_color"] as? String }
    public var tint_color: String? { values["tint_color"] as? String }
    public var border_width: Double? { values["border_width"] as? Double }
    public var border_radius: Double? { values["border_radius"] as? Double }
    public var border_top_left_radius: Double? { values["border_top_left_radius"] as? Double }
    public var border_top_right_radius: Double? { values["border_top_right_radius"] as? Double }
    public var border_bottom_left_radius: Double? { values["border_bottom_left_radius"] as? Double }
    public var border_bottom_right_radius: Double? { values["border_bottom_right_radius"] as? Double }
    public var border_top_width: Double? { values["border_top_width"] as? Double }
    public var border_right_width: Double? { values["border_right_width"] as? Double }
    public var border_bottom_width: Double? { values["border_bottom_width"] as? Double }
    public var border_left_width: Double? { values["border_left_width"] as? Double }
    public var border_top_color: String? { values["border_top_color"] as? String }
    public var border_right_color: String? { values["border_right_color"] as? String }
    public var border_bottom_color: String? { values["border_bottom_color"] as? String }
    public var border_left_color: String? { values["border_left_color"] as? String }
    public var font_size: Double? { values["font_size"] as? Double }
    public var font_family: String? { values["font_family"] as? String }
    public var font_weight: Any? { values["font_weight"] }
    public var bold: Bool? { values["bold"] as? Bool }
    public var italic: Bool? { values["italic"] as? Bool }
    public var text_align: Any? { values["text_align"] }
    public var text_decoration: Any? { values["text_decoration"] }
    public var text_transform: Any? { values["text_transform"] }
    public var line_height: Double? { values["line_height"] as? Double }
    public var letter_spacing: Double? { values["letter_spacing"] as? Double }
    public var max_lines: Int? { values["max_lines"] as? Int }
    public var text_shadow_color: String? { values["text_shadow_color"] as? String }
    public var text_shadow_offset: Any? { values["text_shadow_offset"] }
    public var text_shadow_radius: Double? { values["text_shadow_radius"] as? Double }
    public var shadow_color: String? { values["shadow_color"] as? String }
    public var shadow_offset: Any? { values["shadow_offset"] }
    public var shadow_opacity: Double? { values["shadow_opacity"] as? Double }
    public var shadow_radius: Double? { values["shadow_radius"] as? Double }
    public var elevation: Double? { values["elevation"] as? Double }
    public var opacity: Double? { values["opacity"] as? Double }
    public var transform: Any? { values["transform"] }
    public var z_index: Int? { values["z_index"] as? Int }
    public var pointer_events: Any? { values["pointer_events"] }
    public var animating: Bool? { values["animating"] as? Bool }
    public var size: Any? { values["size"] }
    public var ref: Any? { values["ref"] }
    public var on_layout: Any? { values["on_layout"] }
}

public struct ButtonProps {
    public let values: [String: Any]
    public init(_ values: [String: Any]) throws {
        self.values = values
    }
    public var width: Any? { values["width"] }
    public var height: Any? { values["height"] }
    public var min_width: Any? { values["min_width"] }
    public var max_width: Any? { values["max_width"] }
    public var min_height: Any? { values["min_height"] }
    public var max_height: Any? { values["max_height"] }
    public var aspect_ratio: Double? { values["aspect_ratio"] as? Double }
    public var flex: Double? { values["flex"] as? Double }
    public var flex_grow: Double? { values["flex_grow"] as? Double }
    public var flex_shrink: Double? { values["flex_shrink"] as? Double }
    public var flex_basis: Any? { values["flex_basis"] }
    public var flex_direction: Any? { values["flex_direction"] }
    public var flex_wrap: Any? { values["flex_wrap"] }
    public var justify_content: Any? { values["justify_content"] }
    public var align_items: Any? { values["align_items"] }
    public var align_self: Any? { values["align_self"] }
    public var align_content: Any? { values["align_content"] }
    public var direction: Any? { values["direction"] }
    public var display: Any? { values["display"] }
    public var position: Any? { values["position"] }
    public var top: Any? { values["top"] }
    public var right: Any? { values["right"] }
    public var bottom: Any? { values["bottom"] }
    public var left: Any? { values["left"] }
    public var start: Any? { values["start"] }
    public var end: Any? { values["end"] }
    public var padding: Any? { values["padding"] }
    public var padding_top: Any? { values["padding_top"] }
    public var padding_bottom: Any? { values["padding_bottom"] }
    public var padding_left: Any? { values["padding_left"] }
    public var padding_right: Any? { values["padding_right"] }
    public var padding_start: Any? { values["padding_start"] }
    public var padding_end: Any? { values["padding_end"] }
    public var padding_horizontal: Any? { values["padding_horizontal"] }
    public var padding_vertical: Any? { values["padding_vertical"] }
    public var margin: Any? { values["margin"] }
    public var margin_top: Any? { values["margin_top"] }
    public var margin_bottom: Any? { values["margin_bottom"] }
    public var margin_left: Any? { values["margin_left"] }
    public var margin_right: Any? { values["margin_right"] }
    public var margin_start: Any? { values["margin_start"] }
    public var margin_end: Any? { values["margin_end"] }
    public var margin_horizontal: Any? { values["margin_horizontal"] }
    public var margin_vertical: Any? { values["margin_vertical"] }
    public var spacing: Double? { values["spacing"] as? Double }
    public var gap: Double? { values["gap"] as? Double }
    public var row_gap: Double? { values["row_gap"] as? Double }
    public var column_gap: Double? { values["column_gap"] as? Double }
    public var overflow: Any? { values["overflow"] }
    public var background_color: String? { values["background_color"] as? String }
    public var color: String? { values["color"] as? String }
    public var border_color: String? { values["border_color"] as? String }
    public var placeholder_color: String? { values["placeholder_color"] as? String }
    public var tint_color: String? { values["tint_color"] as? String }
    public var border_width: Double? { values["border_width"] as? Double }
    public var border_radius: Double? { values["border_radius"] as? Double }
    public var border_top_left_radius: Double? { values["border_top_left_radius"] as? Double }
    public var border_top_right_radius: Double? { values["border_top_right_radius"] as? Double }
    public var border_bottom_left_radius: Double? { values["border_bottom_left_radius"] as? Double }
    public var border_bottom_right_radius: Double? { values["border_bottom_right_radius"] as? Double }
    public var border_top_width: Double? { values["border_top_width"] as? Double }
    public var border_right_width: Double? { values["border_right_width"] as? Double }
    public var border_bottom_width: Double? { values["border_bottom_width"] as? Double }
    public var border_left_width: Double? { values["border_left_width"] as? Double }
    public var border_top_color: String? { values["border_top_color"] as? String }
    public var border_right_color: String? { values["border_right_color"] as? String }
    public var border_bottom_color: String? { values["border_bottom_color"] as? String }
    public var border_left_color: String? { values["border_left_color"] as? String }
    public var font_size: Double? { values["font_size"] as? Double }
    public var font_family: String? { values["font_family"] as? String }
    public var font_weight: Any? { values["font_weight"] }
    public var bold: Bool? { values["bold"] as? Bool }
    public var italic: Bool? { values["italic"] as? Bool }
    public var text_align: Any? { values["text_align"] }
    public var text_decoration: Any? { values["text_decoration"] }
    public var text_transform: Any? { values["text_transform"] }
    public var line_height: Double? { values["line_height"] as? Double }
    public var letter_spacing: Double? { values["letter_spacing"] as? Double }
    public var max_lines: Int? { values["max_lines"] as? Int }
    public var text_shadow_color: String? { values["text_shadow_color"] as? String }
    public var text_shadow_offset: Any? { values["text_shadow_offset"] }
    public var text_shadow_radius: Double? { values["text_shadow_radius"] as? Double }
    public var shadow_color: String? { values["shadow_color"] as? String }
    public var shadow_offset: Any? { values["shadow_offset"] }
    public var shadow_opacity: Double? { values["shadow_opacity"] as? Double }
    public var shadow_radius: Double? { values["shadow_radius"] as? Double }
    public var elevation: Double? { values["elevation"] as? Double }
    public var opacity: Double? { values["opacity"] as? Double }
    public var transform: Any? { values["transform"] }
    public var z_index: Int? { values["z_index"] as? Int }
    public var pointer_events: Any? { values["pointer_events"] }
    public var title: String? { values["title"] as? String }
    public var on_press: Any? { values["on_press"] }
    public var disabled: Bool? { values["disabled"] as? Bool }
    public var accessibility_label: Any? { values["accessibility_label"] }
    public var accessibility_hint: Any? { values["accessibility_hint"] }
    public var accessibility_role: Any? { values["accessibility_role"] }
    public var accessible: Any? { values["accessible"] }
    public var accessibility_state: Any? { values["accessibility_state"] }
    public var accessibility_live_region: Any? { values["accessibility_live_region"] }
    public var test_id: Any? { values["test_id"] }
    public var ref: Any? { values["ref"] }
    public var on_layout: Any? { values["on_layout"] }
}

public struct CheckboxProps {
    public let values: [String: Any]
    public init(_ values: [String: Any]) throws {
        self.values = values
    }
    public var width: Any? { values["width"] }
    public var height: Any? { values["height"] }
    public var min_width: Any? { values["min_width"] }
    public var max_width: Any? { values["max_width"] }
    public var min_height: Any? { values["min_height"] }
    public var max_height: Any? { values["max_height"] }
    public var aspect_ratio: Double? { values["aspect_ratio"] as? Double }
    public var flex: Double? { values["flex"] as? Double }
    public var flex_grow: Double? { values["flex_grow"] as? Double }
    public var flex_shrink: Double? { values["flex_shrink"] as? Double }
    public var flex_basis: Any? { values["flex_basis"] }
    public var flex_direction: Any? { values["flex_direction"] }
    public var flex_wrap: Any? { values["flex_wrap"] }
    public var justify_content: Any? { values["justify_content"] }
    public var align_items: Any? { values["align_items"] }
    public var align_self: Any? { values["align_self"] }
    public var align_content: Any? { values["align_content"] }
    public var direction: Any? { values["direction"] }
    public var display: Any? { values["display"] }
    public var position: Any? { values["position"] }
    public var top: Any? { values["top"] }
    public var right: Any? { values["right"] }
    public var bottom: Any? { values["bottom"] }
    public var left: Any? { values["left"] }
    public var start: Any? { values["start"] }
    public var end: Any? { values["end"] }
    public var padding: Any? { values["padding"] }
    public var padding_top: Any? { values["padding_top"] }
    public var padding_bottom: Any? { values["padding_bottom"] }
    public var padding_left: Any? { values["padding_left"] }
    public var padding_right: Any? { values["padding_right"] }
    public var padding_start: Any? { values["padding_start"] }
    public var padding_end: Any? { values["padding_end"] }
    public var padding_horizontal: Any? { values["padding_horizontal"] }
    public var padding_vertical: Any? { values["padding_vertical"] }
    public var margin: Any? { values["margin"] }
    public var margin_top: Any? { values["margin_top"] }
    public var margin_bottom: Any? { values["margin_bottom"] }
    public var margin_left: Any? { values["margin_left"] }
    public var margin_right: Any? { values["margin_right"] }
    public var margin_start: Any? { values["margin_start"] }
    public var margin_end: Any? { values["margin_end"] }
    public var margin_horizontal: Any? { values["margin_horizontal"] }
    public var margin_vertical: Any? { values["margin_vertical"] }
    public var spacing: Double? { values["spacing"] as? Double }
    public var gap: Double? { values["gap"] as? Double }
    public var row_gap: Double? { values["row_gap"] as? Double }
    public var column_gap: Double? { values["column_gap"] as? Double }
    public var overflow: Any? { values["overflow"] }
    public var background_color: String? { values["background_color"] as? String }
    public var color: Any? { values["color"] }
    public var border_color: String? { values["border_color"] as? String }
    public var placeholder_color: String? { values["placeholder_color"] as? String }
    public var tint_color: String? { values["tint_color"] as? String }
    public var border_width: Double? { values["border_width"] as? Double }
    public var border_radius: Double? { values["border_radius"] as? Double }
    public var border_top_left_radius: Double? { values["border_top_left_radius"] as? Double }
    public var border_top_right_radius: Double? { values["border_top_right_radius"] as? Double }
    public var border_bottom_left_radius: Double? { values["border_bottom_left_radius"] as? Double }
    public var border_bottom_right_radius: Double? { values["border_bottom_right_radius"] as? Double }
    public var border_top_width: Double? { values["border_top_width"] as? Double }
    public var border_right_width: Double? { values["border_right_width"] as? Double }
    public var border_bottom_width: Double? { values["border_bottom_width"] as? Double }
    public var border_left_width: Double? { values["border_left_width"] as? Double }
    public var border_top_color: String? { values["border_top_color"] as? String }
    public var border_right_color: String? { values["border_right_color"] as? String }
    public var border_bottom_color: String? { values["border_bottom_color"] as? String }
    public var border_left_color: String? { values["border_left_color"] as? String }
    public var font_size: Double? { values["font_size"] as? Double }
    public var font_family: String? { values["font_family"] as? String }
    public var font_weight: Any? { values["font_weight"] }
    public var bold: Bool? { values["bold"] as? Bool }
    public var italic: Bool? { values["italic"] as? Bool }
    public var text_align: Any? { values["text_align"] }
    public var text_decoration: Any? { values["text_decoration"] }
    public var text_transform: Any? { values["text_transform"] }
    public var line_height: Double? { values["line_height"] as? Double }
    public var letter_spacing: Double? { values["letter_spacing"] as? Double }
    public var max_lines: Int? { values["max_lines"] as? Int }
    public var text_shadow_color: String? { values["text_shadow_color"] as? String }
    public var text_shadow_offset: Any? { values["text_shadow_offset"] }
    public var text_shadow_radius: Double? { values["text_shadow_radius"] as? Double }
    public var shadow_color: String? { values["shadow_color"] as? String }
    public var shadow_offset: Any? { values["shadow_offset"] }
    public var shadow_opacity: Double? { values["shadow_opacity"] as? Double }
    public var shadow_radius: Double? { values["shadow_radius"] as? Double }
    public var elevation: Double? { values["elevation"] as? Double }
    public var opacity: Double? { values["opacity"] as? Double }
    public var transform: Any? { values["transform"] }
    public var z_index: Int? { values["z_index"] as? Int }
    public var pointer_events: Any? { values["pointer_events"] }
    public var value: Bool? { values["value"] as? Bool }
    public var on_change: Any? { values["on_change"] }
    public var label: Any? { values["label"] }
    public var disabled: Bool? { values["disabled"] as? Bool }
    public var accessibility_label: Any? { values["accessibility_label"] }
    public var accessibility_hint: Any? { values["accessibility_hint"] }
    public var accessible: Any? { values["accessible"] }
    public var accessibility_state: Any? { values["accessibility_state"] }
    public var accessibility_live_region: Any? { values["accessibility_live_region"] }
    public var test_id: Any? { values["test_id"] }
    public var ref: Any? { values["ref"] }
    public var on_layout: Any? { values["on_layout"] }
}

public struct ColumnProps {
    public let values: [String: Any]
    public init(_ values: [String: Any]) throws {
        self.values = values
    }
    public var width: Any? { values["width"] }
    public var height: Any? { values["height"] }
    public var min_width: Any? { values["min_width"] }
    public var max_width: Any? { values["max_width"] }
    public var min_height: Any? { values["min_height"] }
    public var max_height: Any? { values["max_height"] }
    public var aspect_ratio: Double? { values["aspect_ratio"] as? Double }
    public var flex: Double? { values["flex"] as? Double }
    public var flex_grow: Double? { values["flex_grow"] as? Double }
    public var flex_shrink: Double? { values["flex_shrink"] as? Double }
    public var flex_basis: Any? { values["flex_basis"] }
    public var flex_direction: Any? { values["flex_direction"] }
    public var flex_wrap: Any? { values["flex_wrap"] }
    public var justify_content: Any? { values["justify_content"] }
    public var align_items: Any? { values["align_items"] }
    public var align_self: Any? { values["align_self"] }
    public var align_content: Any? { values["align_content"] }
    public var direction: Any? { values["direction"] }
    public var display: Any? { values["display"] }
    public var position: Any? { values["position"] }
    public var top: Any? { values["top"] }
    public var right: Any? { values["right"] }
    public var bottom: Any? { values["bottom"] }
    public var left: Any? { values["left"] }
    public var start: Any? { values["start"] }
    public var end: Any? { values["end"] }
    public var padding: Any? { values["padding"] }
    public var padding_top: Any? { values["padding_top"] }
    public var padding_bottom: Any? { values["padding_bottom"] }
    public var padding_left: Any? { values["padding_left"] }
    public var padding_right: Any? { values["padding_right"] }
    public var padding_start: Any? { values["padding_start"] }
    public var padding_end: Any? { values["padding_end"] }
    public var padding_horizontal: Any? { values["padding_horizontal"] }
    public var padding_vertical: Any? { values["padding_vertical"] }
    public var margin: Any? { values["margin"] }
    public var margin_top: Any? { values["margin_top"] }
    public var margin_bottom: Any? { values["margin_bottom"] }
    public var margin_left: Any? { values["margin_left"] }
    public var margin_right: Any? { values["margin_right"] }
    public var margin_start: Any? { values["margin_start"] }
    public var margin_end: Any? { values["margin_end"] }
    public var margin_horizontal: Any? { values["margin_horizontal"] }
    public var margin_vertical: Any? { values["margin_vertical"] }
    public var spacing: Double? { values["spacing"] as? Double }
    public var gap: Double? { values["gap"] as? Double }
    public var row_gap: Double? { values["row_gap"] as? Double }
    public var column_gap: Double? { values["column_gap"] as? Double }
    public var overflow: Any? { values["overflow"] }
    public var background_color: String? { values["background_color"] as? String }
    public var color: String? { values["color"] as? String }
    public var border_color: String? { values["border_color"] as? String }
    public var placeholder_color: String? { values["placeholder_color"] as? String }
    public var tint_color: String? { values["tint_color"] as? String }
    public var border_width: Double? { values["border_width"] as? Double }
    public var border_radius: Double? { values["border_radius"] as? Double }
    public var border_top_left_radius: Double? { values["border_top_left_radius"] as? Double }
    public var border_top_right_radius: Double? { values["border_top_right_radius"] as? Double }
    public var border_bottom_left_radius: Double? { values["border_bottom_left_radius"] as? Double }
    public var border_bottom_right_radius: Double? { values["border_bottom_right_radius"] as? Double }
    public var border_top_width: Double? { values["border_top_width"] as? Double }
    public var border_right_width: Double? { values["border_right_width"] as? Double }
    public var border_bottom_width: Double? { values["border_bottom_width"] as? Double }
    public var border_left_width: Double? { values["border_left_width"] as? Double }
    public var border_top_color: String? { values["border_top_color"] as? String }
    public var border_right_color: String? { values["border_right_color"] as? String }
    public var border_bottom_color: String? { values["border_bottom_color"] as? String }
    public var border_left_color: String? { values["border_left_color"] as? String }
    public var font_size: Double? { values["font_size"] as? Double }
    public var font_family: String? { values["font_family"] as? String }
    public var font_weight: Any? { values["font_weight"] }
    public var bold: Bool? { values["bold"] as? Bool }
    public var italic: Bool? { values["italic"] as? Bool }
    public var text_align: Any? { values["text_align"] }
    public var text_decoration: Any? { values["text_decoration"] }
    public var text_transform: Any? { values["text_transform"] }
    public var line_height: Double? { values["line_height"] as? Double }
    public var letter_spacing: Double? { values["letter_spacing"] as? Double }
    public var max_lines: Int? { values["max_lines"] as? Int }
    public var text_shadow_color: String? { values["text_shadow_color"] as? String }
    public var text_shadow_offset: Any? { values["text_shadow_offset"] }
    public var text_shadow_radius: Double? { values["text_shadow_radius"] as? Double }
    public var shadow_color: String? { values["shadow_color"] as? String }
    public var shadow_offset: Any? { values["shadow_offset"] }
    public var shadow_opacity: Double? { values["shadow_opacity"] as? Double }
    public var shadow_radius: Double? { values["shadow_radius"] as? Double }
    public var elevation: Double? { values["elevation"] as? Double }
    public var opacity: Double? { values["opacity"] as? Double }
    public var transform: Any? { values["transform"] }
    public var z_index: Int? { values["z_index"] as? Int }
    public var pointer_events: Any? { values["pointer_events"] }
    public var gestures: Any? { values["gestures"] }
    public var hit_slop: Any? { values["hit_slop"] }
    public var on_layout: Any? { values["on_layout"] }
    public var accessibility_label: Any? { values["accessibility_label"] }
    public var accessibility_hint: Any? { values["accessibility_hint"] }
    public var accessibility_role: Any? { values["accessibility_role"] }
    public var accessible: Any? { values["accessible"] }
    public var accessibility_state: Any? { values["accessibility_state"] }
    public var accessibility_live_region: Any? { values["accessibility_live_region"] }
    public var test_id: Any? { values["test_id"] }
    public var ref: Any? { values["ref"] }
}

public struct DatePickerProps {
    public let values: [String: Any]
    public init(_ values: [String: Any]) throws {
        self.values = values
    }
    public var width: Any? { values["width"] }
    public var height: Any? { values["height"] }
    public var min_width: Any? { values["min_width"] }
    public var max_width: Any? { values["max_width"] }
    public var min_height: Any? { values["min_height"] }
    public var max_height: Any? { values["max_height"] }
    public var aspect_ratio: Double? { values["aspect_ratio"] as? Double }
    public var flex: Double? { values["flex"] as? Double }
    public var flex_grow: Double? { values["flex_grow"] as? Double }
    public var flex_shrink: Double? { values["flex_shrink"] as? Double }
    public var flex_basis: Any? { values["flex_basis"] }
    public var flex_direction: Any? { values["flex_direction"] }
    public var flex_wrap: Any? { values["flex_wrap"] }
    public var justify_content: Any? { values["justify_content"] }
    public var align_items: Any? { values["align_items"] }
    public var align_self: Any? { values["align_self"] }
    public var align_content: Any? { values["align_content"] }
    public var direction: Any? { values["direction"] }
    public var display: Any? { values["display"] }
    public var position: Any? { values["position"] }
    public var top: Any? { values["top"] }
    public var right: Any? { values["right"] }
    public var bottom: Any? { values["bottom"] }
    public var left: Any? { values["left"] }
    public var start: Any? { values["start"] }
    public var end: Any? { values["end"] }
    public var padding: Any? { values["padding"] }
    public var padding_top: Any? { values["padding_top"] }
    public var padding_bottom: Any? { values["padding_bottom"] }
    public var padding_left: Any? { values["padding_left"] }
    public var padding_right: Any? { values["padding_right"] }
    public var padding_start: Any? { values["padding_start"] }
    public var padding_end: Any? { values["padding_end"] }
    public var padding_horizontal: Any? { values["padding_horizontal"] }
    public var padding_vertical: Any? { values["padding_vertical"] }
    public var margin: Any? { values["margin"] }
    public var margin_top: Any? { values["margin_top"] }
    public var margin_bottom: Any? { values["margin_bottom"] }
    public var margin_left: Any? { values["margin_left"] }
    public var margin_right: Any? { values["margin_right"] }
    public var margin_start: Any? { values["margin_start"] }
    public var margin_end: Any? { values["margin_end"] }
    public var margin_horizontal: Any? { values["margin_horizontal"] }
    public var margin_vertical: Any? { values["margin_vertical"] }
    public var spacing: Double? { values["spacing"] as? Double }
    public var gap: Double? { values["gap"] as? Double }
    public var row_gap: Double? { values["row_gap"] as? Double }
    public var column_gap: Double? { values["column_gap"] as? Double }
    public var overflow: Any? { values["overflow"] }
    public var background_color: String? { values["background_color"] as? String }
    public var color: String? { values["color"] as? String }
    public var border_color: String? { values["border_color"] as? String }
    public var placeholder_color: String? { values["placeholder_color"] as? String }
    public var tint_color: String? { values["tint_color"] as? String }
    public var border_width: Double? { values["border_width"] as? Double }
    public var border_radius: Double? { values["border_radius"] as? Double }
    public var border_top_left_radius: Double? { values["border_top_left_radius"] as? Double }
    public var border_top_right_radius: Double? { values["border_top_right_radius"] as? Double }
    public var border_bottom_left_radius: Double? { values["border_bottom_left_radius"] as? Double }
    public var border_bottom_right_radius: Double? { values["border_bottom_right_radius"] as? Double }
    public var border_top_width: Double? { values["border_top_width"] as? Double }
    public var border_right_width: Double? { values["border_right_width"] as? Double }
    public var border_bottom_width: Double? { values["border_bottom_width"] as? Double }
    public var border_left_width: Double? { values["border_left_width"] as? Double }
    public var border_top_color: String? { values["border_top_color"] as? String }
    public var border_right_color: String? { values["border_right_color"] as? String }
    public var border_bottom_color: String? { values["border_bottom_color"] as? String }
    public var border_left_color: String? { values["border_left_color"] as? String }
    public var font_size: Double? { values["font_size"] as? Double }
    public var font_family: String? { values["font_family"] as? String }
    public var font_weight: Any? { values["font_weight"] }
    public var bold: Bool? { values["bold"] as? Bool }
    public var italic: Bool? { values["italic"] as? Bool }
    public var text_align: Any? { values["text_align"] }
    public var text_decoration: Any? { values["text_decoration"] }
    public var text_transform: Any? { values["text_transform"] }
    public var line_height: Double? { values["line_height"] as? Double }
    public var letter_spacing: Double? { values["letter_spacing"] as? Double }
    public var max_lines: Int? { values["max_lines"] as? Int }
    public var text_shadow_color: String? { values["text_shadow_color"] as? String }
    public var text_shadow_offset: Any? { values["text_shadow_offset"] }
    public var text_shadow_radius: Double? { values["text_shadow_radius"] as? Double }
    public var shadow_color: String? { values["shadow_color"] as? String }
    public var shadow_offset: Any? { values["shadow_offset"] }
    public var shadow_opacity: Double? { values["shadow_opacity"] as? Double }
    public var shadow_radius: Double? { values["shadow_radius"] as? Double }
    public var elevation: Double? { values["elevation"] as? Double }
    public var opacity: Double? { values["opacity"] as? Double }
    public var transform: Any? { values["transform"] }
    public var z_index: Int? { values["z_index"] as? Int }
    public var pointer_events: Any? { values["pointer_events"] }
    public var value: Any? { values["value"] }
    public var mode: Any? { values["mode"] }
    public var on_change: Any? { values["on_change"] }
    public var minimum: Any? { values["minimum"] }
    public var maximum: Any? { values["maximum"] }
    public var disabled: Bool? { values["disabled"] as? Bool }
    public var accessibility_label: Any? { values["accessibility_label"] }
    public var accessible: Any? { values["accessible"] }
    public var accessibility_state: Any? { values["accessibility_state"] }
    public var accessibility_live_region: Any? { values["accessibility_live_region"] }
    public var test_id: Any? { values["test_id"] }
    public var ref: Any? { values["ref"] }
    public var on_layout: Any? { values["on_layout"] }
}

public struct ErrorBoundaryProps {
    public let values: [String: Any]
    public init(_ values: [String: Any]) throws {
        self.values = values
    }
    public var width: Any? { values["width"] }
    public var height: Any? { values["height"] }
    public var min_width: Any? { values["min_width"] }
    public var max_width: Any? { values["max_width"] }
    public var min_height: Any? { values["min_height"] }
    public var max_height: Any? { values["max_height"] }
    public var aspect_ratio: Double? { values["aspect_ratio"] as? Double }
    public var flex: Double? { values["flex"] as? Double }
    public var flex_grow: Double? { values["flex_grow"] as? Double }
    public var flex_shrink: Double? { values["flex_shrink"] as? Double }
    public var flex_basis: Any? { values["flex_basis"] }
    public var flex_direction: Any? { values["flex_direction"] }
    public var flex_wrap: Any? { values["flex_wrap"] }
    public var justify_content: Any? { values["justify_content"] }
    public var align_items: Any? { values["align_items"] }
    public var align_self: Any? { values["align_self"] }
    public var align_content: Any? { values["align_content"] }
    public var direction: Any? { values["direction"] }
    public var display: Any? { values["display"] }
    public var position: Any? { values["position"] }
    public var top: Any? { values["top"] }
    public var right: Any? { values["right"] }
    public var bottom: Any? { values["bottom"] }
    public var left: Any? { values["left"] }
    public var start: Any? { values["start"] }
    public var end: Any? { values["end"] }
    public var padding: Any? { values["padding"] }
    public var padding_top: Any? { values["padding_top"] }
    public var padding_bottom: Any? { values["padding_bottom"] }
    public var padding_left: Any? { values["padding_left"] }
    public var padding_right: Any? { values["padding_right"] }
    public var padding_start: Any? { values["padding_start"] }
    public var padding_end: Any? { values["padding_end"] }
    public var padding_horizontal: Any? { values["padding_horizontal"] }
    public var padding_vertical: Any? { values["padding_vertical"] }
    public var margin: Any? { values["margin"] }
    public var margin_top: Any? { values["margin_top"] }
    public var margin_bottom: Any? { values["margin_bottom"] }
    public var margin_left: Any? { values["margin_left"] }
    public var margin_right: Any? { values["margin_right"] }
    public var margin_start: Any? { values["margin_start"] }
    public var margin_end: Any? { values["margin_end"] }
    public var margin_horizontal: Any? { values["margin_horizontal"] }
    public var margin_vertical: Any? { values["margin_vertical"] }
    public var spacing: Double? { values["spacing"] as? Double }
    public var gap: Double? { values["gap"] as? Double }
    public var row_gap: Double? { values["row_gap"] as? Double }
    public var column_gap: Double? { values["column_gap"] as? Double }
    public var overflow: Any? { values["overflow"] }
    public var background_color: String? { values["background_color"] as? String }
    public var color: String? { values["color"] as? String }
    public var border_color: String? { values["border_color"] as? String }
    public var placeholder_color: String? { values["placeholder_color"] as? String }
    public var tint_color: String? { values["tint_color"] as? String }
    public var border_width: Double? { values["border_width"] as? Double }
    public var border_radius: Double? { values["border_radius"] as? Double }
    public var border_top_left_radius: Double? { values["border_top_left_radius"] as? Double }
    public var border_top_right_radius: Double? { values["border_top_right_radius"] as? Double }
    public var border_bottom_left_radius: Double? { values["border_bottom_left_radius"] as? Double }
    public var border_bottom_right_radius: Double? { values["border_bottom_right_radius"] as? Double }
    public var border_top_width: Double? { values["border_top_width"] as? Double }
    public var border_right_width: Double? { values["border_right_width"] as? Double }
    public var border_bottom_width: Double? { values["border_bottom_width"] as? Double }
    public var border_left_width: Double? { values["border_left_width"] as? Double }
    public var border_top_color: String? { values["border_top_color"] as? String }
    public var border_right_color: String? { values["border_right_color"] as? String }
    public var border_bottom_color: String? { values["border_bottom_color"] as? String }
    public var border_left_color: String? { values["border_left_color"] as? String }
    public var font_size: Double? { values["font_size"] as? Double }
    public var font_family: String? { values["font_family"] as? String }
    public var font_weight: Any? { values["font_weight"] }
    public var bold: Bool? { values["bold"] as? Bool }
    public var italic: Bool? { values["italic"] as? Bool }
    public var text_align: Any? { values["text_align"] }
    public var text_decoration: Any? { values["text_decoration"] }
    public var text_transform: Any? { values["text_transform"] }
    public var line_height: Double? { values["line_height"] as? Double }
    public var letter_spacing: Double? { values["letter_spacing"] as? Double }
    public var max_lines: Int? { values["max_lines"] as? Int }
    public var text_shadow_color: String? { values["text_shadow_color"] as? String }
    public var text_shadow_offset: Any? { values["text_shadow_offset"] }
    public var text_shadow_radius: Double? { values["text_shadow_radius"] as? Double }
    public var shadow_color: String? { values["shadow_color"] as? String }
    public var shadow_offset: Any? { values["shadow_offset"] }
    public var shadow_opacity: Double? { values["shadow_opacity"] as? Double }
    public var shadow_radius: Double? { values["shadow_radius"] as? Double }
    public var elevation: Double? { values["elevation"] as? Double }
    public var opacity: Double? { values["opacity"] as? Double }
    public var transform: Any? { values["transform"] }
    public var z_index: Int? { values["z_index"] as? Int }
    public var pointer_events: Any? { values["pointer_events"] }
    public var fallback: Any? { values["fallback"] }
    public var on_error: Any? { values["on_error"] }
    public var ref: Any? { values["ref"] }
    public var on_layout: Any? { values["on_layout"] }
}

public struct FlatListProps {
    public let values: [String: Any]
    public init(_ values: [String: Any]) throws {
        self.values = values
    }
    public var width: Any? { values["width"] }
    public var height: Any? { values["height"] }
    public var min_width: Any? { values["min_width"] }
    public var max_width: Any? { values["max_width"] }
    public var min_height: Any? { values["min_height"] }
    public var max_height: Any? { values["max_height"] }
    public var aspect_ratio: Double? { values["aspect_ratio"] as? Double }
    public var flex: Double? { values["flex"] as? Double }
    public var flex_grow: Double? { values["flex_grow"] as? Double }
    public var flex_shrink: Double? { values["flex_shrink"] as? Double }
    public var flex_basis: Any? { values["flex_basis"] }
    public var flex_direction: Any? { values["flex_direction"] }
    public var flex_wrap: Any? { values["flex_wrap"] }
    public var justify_content: Any? { values["justify_content"] }
    public var align_items: Any? { values["align_items"] }
    public var align_self: Any? { values["align_self"] }
    public var align_content: Any? { values["align_content"] }
    public var direction: Any? { values["direction"] }
    public var display: Any? { values["display"] }
    public var position: Any? { values["position"] }
    public var top: Any? { values["top"] }
    public var right: Any? { values["right"] }
    public var bottom: Any? { values["bottom"] }
    public var left: Any? { values["left"] }
    public var start: Any? { values["start"] }
    public var end: Any? { values["end"] }
    public var padding: Any? { values["padding"] }
    public var padding_top: Any? { values["padding_top"] }
    public var padding_bottom: Any? { values["padding_bottom"] }
    public var padding_left: Any? { values["padding_left"] }
    public var padding_right: Any? { values["padding_right"] }
    public var padding_start: Any? { values["padding_start"] }
    public var padding_end: Any? { values["padding_end"] }
    public var padding_horizontal: Any? { values["padding_horizontal"] }
    public var padding_vertical: Any? { values["padding_vertical"] }
    public var margin: Any? { values["margin"] }
    public var margin_top: Any? { values["margin_top"] }
    public var margin_bottom: Any? { values["margin_bottom"] }
    public var margin_left: Any? { values["margin_left"] }
    public var margin_right: Any? { values["margin_right"] }
    public var margin_start: Any? { values["margin_start"] }
    public var margin_end: Any? { values["margin_end"] }
    public var margin_horizontal: Any? { values["margin_horizontal"] }
    public var margin_vertical: Any? { values["margin_vertical"] }
    public var spacing: Double? { values["spacing"] as? Double }
    public var gap: Double? { values["gap"] as? Double }
    public var row_gap: Double? { values["row_gap"] as? Double }
    public var column_gap: Double? { values["column_gap"] as? Double }
    public var overflow: Any? { values["overflow"] }
    public var background_color: String? { values["background_color"] as? String }
    public var color: String? { values["color"] as? String }
    public var border_color: String? { values["border_color"] as? String }
    public var placeholder_color: String? { values["placeholder_color"] as? String }
    public var tint_color: String? { values["tint_color"] as? String }
    public var border_width: Double? { values["border_width"] as? Double }
    public var border_radius: Double? { values["border_radius"] as? Double }
    public var border_top_left_radius: Double? { values["border_top_left_radius"] as? Double }
    public var border_top_right_radius: Double? { values["border_top_right_radius"] as? Double }
    public var border_bottom_left_radius: Double? { values["border_bottom_left_radius"] as? Double }
    public var border_bottom_right_radius: Double? { values["border_bottom_right_radius"] as? Double }
    public var border_top_width: Double? { values["border_top_width"] as? Double }
    public var border_right_width: Double? { values["border_right_width"] as? Double }
    public var border_bottom_width: Double? { values["border_bottom_width"] as? Double }
    public var border_left_width: Double? { values["border_left_width"] as? Double }
    public var border_top_color: String? { values["border_top_color"] as? String }
    public var border_right_color: String? { values["border_right_color"] as? String }
    public var border_bottom_color: String? { values["border_bottom_color"] as? String }
    public var border_left_color: String? { values["border_left_color"] as? String }
    public var font_size: Double? { values["font_size"] as? Double }
    public var font_family: String? { values["font_family"] as? String }
    public var font_weight: Any? { values["font_weight"] }
    public var bold: Bool? { values["bold"] as? Bool }
    public var italic: Bool? { values["italic"] as? Bool }
    public var text_align: Any? { values["text_align"] }
    public var text_decoration: Any? { values["text_decoration"] }
    public var text_transform: Any? { values["text_transform"] }
    public var line_height: Double? { values["line_height"] as? Double }
    public var letter_spacing: Double? { values["letter_spacing"] as? Double }
    public var max_lines: Int? { values["max_lines"] as? Int }
    public var text_shadow_color: String? { values["text_shadow_color"] as? String }
    public var text_shadow_offset: Any? { values["text_shadow_offset"] }
    public var text_shadow_radius: Double? { values["text_shadow_radius"] as? Double }
    public var shadow_color: String? { values["shadow_color"] as? String }
    public var shadow_offset: Any? { values["shadow_offset"] }
    public var shadow_opacity: Double? { values["shadow_opacity"] as? Double }
    public var shadow_radius: Double? { values["shadow_radius"] as? Double }
    public var elevation: Double? { values["elevation"] as? Double }
    public var opacity: Double? { values["opacity"] as? Double }
    public var transform: Any? { values["transform"] }
    public var z_index: Int? { values["z_index"] as? Int }
    public var pointer_events: Any? { values["pointer_events"] }
    public var data: Any? { values["data"] }
    public var render_item: Any? { values["render_item"] }
    public var key_extractor: Any? { values["key_extractor"] }
    public var item_height: Any? { values["item_height"] }
    public var get_item_height: Any? { values["get_item_height"] }
    public var estimated_item_height: Any? { values["estimated_item_height"] }
    public var separator_height: Double? { values["separator_height"] as? Double }
    public var refresh_control: Any? { values["refresh_control"] }
    public var horizontal: Bool? { values["horizontal"] as? Bool }
    public var num_columns: Int? { values["num_columns"] as? Int }
    public var list_header: Any? { values["list_header"] }
    public var list_footer: Any? { values["list_footer"] }
    public var list_empty: Any? { values["list_empty"] }
    public var on_end_reached: Any? { values["on_end_reached"] }
    public var on_end_reached_threshold: Double? { values["on_end_reached_threshold"] as? Double }
    public var on_viewable_items_changed: Any? { values["on_viewable_items_changed"] }
    public var on_scroll: Any? { values["on_scroll"] }
    public var shows_scroll_indicator: Bool? { values["shows_scroll_indicator"] as? Bool }
    public var content_container_style: Any? { values["content_container_style"] }
    public var ref: Any? { values["ref"] }
    public var on_layout: Any? { values["on_layout"] }
}

public struct FragmentProps {
    public let values: [String: Any]
    public init(_ values: [String: Any]) throws {
        self.values = values
    }
    public var width: Any? { values["width"] }
    public var height: Any? { values["height"] }
    public var min_width: Any? { values["min_width"] }
    public var max_width: Any? { values["max_width"] }
    public var min_height: Any? { values["min_height"] }
    public var max_height: Any? { values["max_height"] }
    public var aspect_ratio: Double? { values["aspect_ratio"] as? Double }
    public var flex: Double? { values["flex"] as? Double }
    public var flex_grow: Double? { values["flex_grow"] as? Double }
    public var flex_shrink: Double? { values["flex_shrink"] as? Double }
    public var flex_basis: Any? { values["flex_basis"] }
    public var flex_direction: Any? { values["flex_direction"] }
    public var flex_wrap: Any? { values["flex_wrap"] }
    public var justify_content: Any? { values["justify_content"] }
    public var align_items: Any? { values["align_items"] }
    public var align_self: Any? { values["align_self"] }
    public var align_content: Any? { values["align_content"] }
    public var direction: Any? { values["direction"] }
    public var display: Any? { values["display"] }
    public var position: Any? { values["position"] }
    public var top: Any? { values["top"] }
    public var right: Any? { values["right"] }
    public var bottom: Any? { values["bottom"] }
    public var left: Any? { values["left"] }
    public var start: Any? { values["start"] }
    public var end: Any? { values["end"] }
    public var padding: Any? { values["padding"] }
    public var padding_top: Any? { values["padding_top"] }
    public var padding_bottom: Any? { values["padding_bottom"] }
    public var padding_left: Any? { values["padding_left"] }
    public var padding_right: Any? { values["padding_right"] }
    public var padding_start: Any? { values["padding_start"] }
    public var padding_end: Any? { values["padding_end"] }
    public var padding_horizontal: Any? { values["padding_horizontal"] }
    public var padding_vertical: Any? { values["padding_vertical"] }
    public var margin: Any? { values["margin"] }
    public var margin_top: Any? { values["margin_top"] }
    public var margin_bottom: Any? { values["margin_bottom"] }
    public var margin_left: Any? { values["margin_left"] }
    public var margin_right: Any? { values["margin_right"] }
    public var margin_start: Any? { values["margin_start"] }
    public var margin_end: Any? { values["margin_end"] }
    public var margin_horizontal: Any? { values["margin_horizontal"] }
    public var margin_vertical: Any? { values["margin_vertical"] }
    public var spacing: Double? { values["spacing"] as? Double }
    public var gap: Double? { values["gap"] as? Double }
    public var row_gap: Double? { values["row_gap"] as? Double }
    public var column_gap: Double? { values["column_gap"] as? Double }
    public var overflow: Any? { values["overflow"] }
    public var background_color: String? { values["background_color"] as? String }
    public var color: String? { values["color"] as? String }
    public var border_color: String? { values["border_color"] as? String }
    public var placeholder_color: String? { values["placeholder_color"] as? String }
    public var tint_color: String? { values["tint_color"] as? String }
    public var border_width: Double? { values["border_width"] as? Double }
    public var border_radius: Double? { values["border_radius"] as? Double }
    public var border_top_left_radius: Double? { values["border_top_left_radius"] as? Double }
    public var border_top_right_radius: Double? { values["border_top_right_radius"] as? Double }
    public var border_bottom_left_radius: Double? { values["border_bottom_left_radius"] as? Double }
    public var border_bottom_right_radius: Double? { values["border_bottom_right_radius"] as? Double }
    public var border_top_width: Double? { values["border_top_width"] as? Double }
    public var border_right_width: Double? { values["border_right_width"] as? Double }
    public var border_bottom_width: Double? { values["border_bottom_width"] as? Double }
    public var border_left_width: Double? { values["border_left_width"] as? Double }
    public var border_top_color: String? { values["border_top_color"] as? String }
    public var border_right_color: String? { values["border_right_color"] as? String }
    public var border_bottom_color: String? { values["border_bottom_color"] as? String }
    public var border_left_color: String? { values["border_left_color"] as? String }
    public var font_size: Double? { values["font_size"] as? Double }
    public var font_family: String? { values["font_family"] as? String }
    public var font_weight: Any? { values["font_weight"] }
    public var bold: Bool? { values["bold"] as? Bool }
    public var italic: Bool? { values["italic"] as? Bool }
    public var text_align: Any? { values["text_align"] }
    public var text_decoration: Any? { values["text_decoration"] }
    public var text_transform: Any? { values["text_transform"] }
    public var line_height: Double? { values["line_height"] as? Double }
    public var letter_spacing: Double? { values["letter_spacing"] as? Double }
    public var max_lines: Int? { values["max_lines"] as? Int }
    public var text_shadow_color: String? { values["text_shadow_color"] as? String }
    public var text_shadow_offset: Any? { values["text_shadow_offset"] }
    public var text_shadow_radius: Double? { values["text_shadow_radius"] as? Double }
    public var shadow_color: String? { values["shadow_color"] as? String }
    public var shadow_offset: Any? { values["shadow_offset"] }
    public var shadow_opacity: Double? { values["shadow_opacity"] as? Double }
    public var shadow_radius: Double? { values["shadow_radius"] as? Double }
    public var elevation: Double? { values["elevation"] as? Double }
    public var opacity: Double? { values["opacity"] as? Double }
    public var transform: Any? { values["transform"] }
    public var z_index: Int? { values["z_index"] as? Int }
    public var pointer_events: Any? { values["pointer_events"] }
    public var ref: Any? { values["ref"] }
    public var on_layout: Any? { values["on_layout"] }
}

public struct ImageProps {
    public let values: [String: Any]
    public init(_ values: [String: Any]) throws {
        self.values = values
    }
    public var width: Any? { values["width"] }
    public var height: Any? { values["height"] }
    public var min_width: Any? { values["min_width"] }
    public var max_width: Any? { values["max_width"] }
    public var min_height: Any? { values["min_height"] }
    public var max_height: Any? { values["max_height"] }
    public var aspect_ratio: Double? { values["aspect_ratio"] as? Double }
    public var flex: Double? { values["flex"] as? Double }
    public var flex_grow: Double? { values["flex_grow"] as? Double }
    public var flex_shrink: Double? { values["flex_shrink"] as? Double }
    public var flex_basis: Any? { values["flex_basis"] }
    public var flex_direction: Any? { values["flex_direction"] }
    public var flex_wrap: Any? { values["flex_wrap"] }
    public var justify_content: Any? { values["justify_content"] }
    public var align_items: Any? { values["align_items"] }
    public var align_self: Any? { values["align_self"] }
    public var align_content: Any? { values["align_content"] }
    public var direction: Any? { values["direction"] }
    public var display: Any? { values["display"] }
    public var position: Any? { values["position"] }
    public var top: Any? { values["top"] }
    public var right: Any? { values["right"] }
    public var bottom: Any? { values["bottom"] }
    public var left: Any? { values["left"] }
    public var start: Any? { values["start"] }
    public var end: Any? { values["end"] }
    public var padding: Any? { values["padding"] }
    public var padding_top: Any? { values["padding_top"] }
    public var padding_bottom: Any? { values["padding_bottom"] }
    public var padding_left: Any? { values["padding_left"] }
    public var padding_right: Any? { values["padding_right"] }
    public var padding_start: Any? { values["padding_start"] }
    public var padding_end: Any? { values["padding_end"] }
    public var padding_horizontal: Any? { values["padding_horizontal"] }
    public var padding_vertical: Any? { values["padding_vertical"] }
    public var margin: Any? { values["margin"] }
    public var margin_top: Any? { values["margin_top"] }
    public var margin_bottom: Any? { values["margin_bottom"] }
    public var margin_left: Any? { values["margin_left"] }
    public var margin_right: Any? { values["margin_right"] }
    public var margin_start: Any? { values["margin_start"] }
    public var margin_end: Any? { values["margin_end"] }
    public var margin_horizontal: Any? { values["margin_horizontal"] }
    public var margin_vertical: Any? { values["margin_vertical"] }
    public var spacing: Double? { values["spacing"] as? Double }
    public var gap: Double? { values["gap"] as? Double }
    public var row_gap: Double? { values["row_gap"] as? Double }
    public var column_gap: Double? { values["column_gap"] as? Double }
    public var overflow: Any? { values["overflow"] }
    public var background_color: String? { values["background_color"] as? String }
    public var color: String? { values["color"] as? String }
    public var border_color: String? { values["border_color"] as? String }
    public var placeholder_color: Any? { values["placeholder_color"] }
    public var tint_color: Any? { values["tint_color"] }
    public var border_width: Double? { values["border_width"] as? Double }
    public var border_radius: Double? { values["border_radius"] as? Double }
    public var border_top_left_radius: Double? { values["border_top_left_radius"] as? Double }
    public var border_top_right_radius: Double? { values["border_top_right_radius"] as? Double }
    public var border_bottom_left_radius: Double? { values["border_bottom_left_radius"] as? Double }
    public var border_bottom_right_radius: Double? { values["border_bottom_right_radius"] as? Double }
    public var border_top_width: Double? { values["border_top_width"] as? Double }
    public var border_right_width: Double? { values["border_right_width"] as? Double }
    public var border_bottom_width: Double? { values["border_bottom_width"] as? Double }
    public var border_left_width: Double? { values["border_left_width"] as? Double }
    public var border_top_color: String? { values["border_top_color"] as? String }
    public var border_right_color: String? { values["border_right_color"] as? String }
    public var border_bottom_color: String? { values["border_bottom_color"] as? String }
    public var border_left_color: String? { values["border_left_color"] as? String }
    public var font_size: Double? { values["font_size"] as? Double }
    public var font_family: String? { values["font_family"] as? String }
    public var font_weight: Any? { values["font_weight"] }
    public var bold: Bool? { values["bold"] as? Bool }
    public var italic: Bool? { values["italic"] as? Bool }
    public var text_align: Any? { values["text_align"] }
    public var text_decoration: Any? { values["text_decoration"] }
    public var text_transform: Any? { values["text_transform"] }
    public var line_height: Double? { values["line_height"] as? Double }
    public var letter_spacing: Double? { values["letter_spacing"] as? Double }
    public var max_lines: Int? { values["max_lines"] as? Int }
    public var text_shadow_color: String? { values["text_shadow_color"] as? String }
    public var text_shadow_offset: Any? { values["text_shadow_offset"] }
    public var text_shadow_radius: Double? { values["text_shadow_radius"] as? Double }
    public var shadow_color: String? { values["shadow_color"] as? String }
    public var shadow_offset: Any? { values["shadow_offset"] }
    public var shadow_opacity: Double? { values["shadow_opacity"] as? Double }
    public var shadow_radius: Double? { values["shadow_radius"] as? Double }
    public var elevation: Double? { values["elevation"] as? Double }
    public var opacity: Double? { values["opacity"] as? Double }
    public var transform: Any? { values["transform"] }
    public var z_index: Int? { values["z_index"] as? Int }
    public var pointer_events: Any? { values["pointer_events"] }
    public var source: String? { values["source"] as? String }
    public var scale_type: Any? { values["scale_type"] }
    public var on_load: Any? { values["on_load"] }
    public var on_error: Any? { values["on_error"] }
    public var accessibility_label: Any? { values["accessibility_label"] }
    public var accessibility_role: Any? { values["accessibility_role"] }
    public var accessible: Any? { values["accessible"] }
    public var accessibility_state: Any? { values["accessibility_state"] }
    public var accessibility_live_region: Any? { values["accessibility_live_region"] }
    public var test_id: Any? { values["test_id"] }
    public var ref: Any? { values["ref"] }
    public var on_layout: Any? { values["on_layout"] }
}

public struct ImageBackgroundProps {
    public let values: [String: Any]
    public init(_ values: [String: Any]) throws {
        self.values = values
    }
    public var width: Any? { values["width"] }
    public var height: Any? { values["height"] }
    public var min_width: Any? { values["min_width"] }
    public var max_width: Any? { values["max_width"] }
    public var min_height: Any? { values["min_height"] }
    public var max_height: Any? { values["max_height"] }
    public var aspect_ratio: Double? { values["aspect_ratio"] as? Double }
    public var flex: Double? { values["flex"] as? Double }
    public var flex_grow: Double? { values["flex_grow"] as? Double }
    public var flex_shrink: Double? { values["flex_shrink"] as? Double }
    public var flex_basis: Any? { values["flex_basis"] }
    public var flex_direction: Any? { values["flex_direction"] }
    public var flex_wrap: Any? { values["flex_wrap"] }
    public var justify_content: Any? { values["justify_content"] }
    public var align_items: Any? { values["align_items"] }
    public var align_self: Any? { values["align_self"] }
    public var align_content: Any? { values["align_content"] }
    public var direction: Any? { values["direction"] }
    public var display: Any? { values["display"] }
    public var position: Any? { values["position"] }
    public var top: Any? { values["top"] }
    public var right: Any? { values["right"] }
    public var bottom: Any? { values["bottom"] }
    public var left: Any? { values["left"] }
    public var start: Any? { values["start"] }
    public var end: Any? { values["end"] }
    public var padding: Any? { values["padding"] }
    public var padding_top: Any? { values["padding_top"] }
    public var padding_bottom: Any? { values["padding_bottom"] }
    public var padding_left: Any? { values["padding_left"] }
    public var padding_right: Any? { values["padding_right"] }
    public var padding_start: Any? { values["padding_start"] }
    public var padding_end: Any? { values["padding_end"] }
    public var padding_horizontal: Any? { values["padding_horizontal"] }
    public var padding_vertical: Any? { values["padding_vertical"] }
    public var margin: Any? { values["margin"] }
    public var margin_top: Any? { values["margin_top"] }
    public var margin_bottom: Any? { values["margin_bottom"] }
    public var margin_left: Any? { values["margin_left"] }
    public var margin_right: Any? { values["margin_right"] }
    public var margin_start: Any? { values["margin_start"] }
    public var margin_end: Any? { values["margin_end"] }
    public var margin_horizontal: Any? { values["margin_horizontal"] }
    public var margin_vertical: Any? { values["margin_vertical"] }
    public var spacing: Double? { values["spacing"] as? Double }
    public var gap: Double? { values["gap"] as? Double }
    public var row_gap: Double? { values["row_gap"] as? Double }
    public var column_gap: Double? { values["column_gap"] as? Double }
    public var overflow: Any? { values["overflow"] }
    public var background_color: String? { values["background_color"] as? String }
    public var color: String? { values["color"] as? String }
    public var border_color: String? { values["border_color"] as? String }
    public var placeholder_color: String? { values["placeholder_color"] as? String }
    public var tint_color: String? { values["tint_color"] as? String }
    public var border_width: Double? { values["border_width"] as? Double }
    public var border_radius: Double? { values["border_radius"] as? Double }
    public var border_top_left_radius: Double? { values["border_top_left_radius"] as? Double }
    public var border_top_right_radius: Double? { values["border_top_right_radius"] as? Double }
    public var border_bottom_left_radius: Double? { values["border_bottom_left_radius"] as? Double }
    public var border_bottom_right_radius: Double? { values["border_bottom_right_radius"] as? Double }
    public var border_top_width: Double? { values["border_top_width"] as? Double }
    public var border_right_width: Double? { values["border_right_width"] as? Double }
    public var border_bottom_width: Double? { values["border_bottom_width"] as? Double }
    public var border_left_width: Double? { values["border_left_width"] as? Double }
    public var border_top_color: String? { values["border_top_color"] as? String }
    public var border_right_color: String? { values["border_right_color"] as? String }
    public var border_bottom_color: String? { values["border_bottom_color"] as? String }
    public var border_left_color: String? { values["border_left_color"] as? String }
    public var font_size: Double? { values["font_size"] as? Double }
    public var font_family: String? { values["font_family"] as? String }
    public var font_weight: Any? { values["font_weight"] }
    public var bold: Bool? { values["bold"] as? Bool }
    public var italic: Bool? { values["italic"] as? Bool }
    public var text_align: Any? { values["text_align"] }
    public var text_decoration: Any? { values["text_decoration"] }
    public var text_transform: Any? { values["text_transform"] }
    public var line_height: Double? { values["line_height"] as? Double }
    public var letter_spacing: Double? { values["letter_spacing"] as? Double }
    public var max_lines: Int? { values["max_lines"] as? Int }
    public var text_shadow_color: String? { values["text_shadow_color"] as? String }
    public var text_shadow_offset: Any? { values["text_shadow_offset"] }
    public var text_shadow_radius: Double? { values["text_shadow_radius"] as? Double }
    public var shadow_color: String? { values["shadow_color"] as? String }
    public var shadow_offset: Any? { values["shadow_offset"] }
    public var shadow_opacity: Double? { values["shadow_opacity"] as? Double }
    public var shadow_radius: Double? { values["shadow_radius"] as? Double }
    public var elevation: Double? { values["elevation"] as? Double }
    public var opacity: Double? { values["opacity"] as? Double }
    public var transform: Any? { values["transform"] }
    public var z_index: Int? { values["z_index"] as? Int }
    public var pointer_events: Any? { values["pointer_events"] }
    public var source: String? { values["source"] as? String }
    public var scale_type: Any? { values["scale_type"] }
    public var accessibility_label: Any? { values["accessibility_label"] }
    public var accessible: Any? { values["accessible"] }
    public var accessibility_state: Any? { values["accessibility_state"] }
    public var accessibility_live_region: Any? { values["accessibility_live_region"] }
    public var test_id: Any? { values["test_id"] }
    public var ref: Any? { values["ref"] }
    public var on_layout: Any? { values["on_layout"] }
}

public struct KeyboardAvoidingViewProps {
    public let values: [String: Any]
    public init(_ values: [String: Any]) throws {
        self.values = values
    }
    public var width: Any? { values["width"] }
    public var height: Any? { values["height"] }
    public var min_width: Any? { values["min_width"] }
    public var max_width: Any? { values["max_width"] }
    public var min_height: Any? { values["min_height"] }
    public var max_height: Any? { values["max_height"] }
    public var aspect_ratio: Double? { values["aspect_ratio"] as? Double }
    public var flex: Double? { values["flex"] as? Double }
    public var flex_grow: Double? { values["flex_grow"] as? Double }
    public var flex_shrink: Double? { values["flex_shrink"] as? Double }
    public var flex_basis: Any? { values["flex_basis"] }
    public var flex_direction: Any? { values["flex_direction"] }
    public var flex_wrap: Any? { values["flex_wrap"] }
    public var justify_content: Any? { values["justify_content"] }
    public var align_items: Any? { values["align_items"] }
    public var align_self: Any? { values["align_self"] }
    public var align_content: Any? { values["align_content"] }
    public var direction: Any? { values["direction"] }
    public var display: Any? { values["display"] }
    public var position: Any? { values["position"] }
    public var top: Any? { values["top"] }
    public var right: Any? { values["right"] }
    public var bottom: Any? { values["bottom"] }
    public var left: Any? { values["left"] }
    public var start: Any? { values["start"] }
    public var end: Any? { values["end"] }
    public var padding: Any? { values["padding"] }
    public var padding_top: Any? { values["padding_top"] }
    public var padding_bottom: Any? { values["padding_bottom"] }
    public var padding_left: Any? { values["padding_left"] }
    public var padding_right: Any? { values["padding_right"] }
    public var padding_start: Any? { values["padding_start"] }
    public var padding_end: Any? { values["padding_end"] }
    public var padding_horizontal: Any? { values["padding_horizontal"] }
    public var padding_vertical: Any? { values["padding_vertical"] }
    public var margin: Any? { values["margin"] }
    public var margin_top: Any? { values["margin_top"] }
    public var margin_bottom: Any? { values["margin_bottom"] }
    public var margin_left: Any? { values["margin_left"] }
    public var margin_right: Any? { values["margin_right"] }
    public var margin_start: Any? { values["margin_start"] }
    public var margin_end: Any? { values["margin_end"] }
    public var margin_horizontal: Any? { values["margin_horizontal"] }
    public var margin_vertical: Any? { values["margin_vertical"] }
    public var spacing: Double? { values["spacing"] as? Double }
    public var gap: Double? { values["gap"] as? Double }
    public var row_gap: Double? { values["row_gap"] as? Double }
    public var column_gap: Double? { values["column_gap"] as? Double }
    public var overflow: Any? { values["overflow"] }
    public var background_color: String? { values["background_color"] as? String }
    public var color: String? { values["color"] as? String }
    public var border_color: String? { values["border_color"] as? String }
    public var placeholder_color: String? { values["placeholder_color"] as? String }
    public var tint_color: String? { values["tint_color"] as? String }
    public var border_width: Double? { values["border_width"] as? Double }
    public var border_radius: Double? { values["border_radius"] as? Double }
    public var border_top_left_radius: Double? { values["border_top_left_radius"] as? Double }
    public var border_top_right_radius: Double? { values["border_top_right_radius"] as? Double }
    public var border_bottom_left_radius: Double? { values["border_bottom_left_radius"] as? Double }
    public var border_bottom_right_radius: Double? { values["border_bottom_right_radius"] as? Double }
    public var border_top_width: Double? { values["border_top_width"] as? Double }
    public var border_right_width: Double? { values["border_right_width"] as? Double }
    public var border_bottom_width: Double? { values["border_bottom_width"] as? Double }
    public var border_left_width: Double? { values["border_left_width"] as? Double }
    public var border_top_color: String? { values["border_top_color"] as? String }
    public var border_right_color: String? { values["border_right_color"] as? String }
    public var border_bottom_color: String? { values["border_bottom_color"] as? String }
    public var border_left_color: String? { values["border_left_color"] as? String }
    public var font_size: Double? { values["font_size"] as? Double }
    public var font_family: String? { values["font_family"] as? String }
    public var font_weight: Any? { values["font_weight"] }
    public var bold: Bool? { values["bold"] as? Bool }
    public var italic: Bool? { values["italic"] as? Bool }
    public var text_align: Any? { values["text_align"] }
    public var text_decoration: Any? { values["text_decoration"] }
    public var text_transform: Any? { values["text_transform"] }
    public var line_height: Double? { values["line_height"] as? Double }
    public var letter_spacing: Double? { values["letter_spacing"] as? Double }
    public var max_lines: Int? { values["max_lines"] as? Int }
    public var text_shadow_color: String? { values["text_shadow_color"] as? String }
    public var text_shadow_offset: Any? { values["text_shadow_offset"] }
    public var text_shadow_radius: Double? { values["text_shadow_radius"] as? Double }
    public var shadow_color: String? { values["shadow_color"] as? String }
    public var shadow_offset: Any? { values["shadow_offset"] }
    public var shadow_opacity: Double? { values["shadow_opacity"] as? Double }
    public var shadow_radius: Double? { values["shadow_radius"] as? Double }
    public var elevation: Double? { values["elevation"] as? Double }
    public var opacity: Double? { values["opacity"] as? Double }
    public var transform: Any? { values["transform"] }
    public var z_index: Int? { values["z_index"] as? Int }
    public var pointer_events: Any? { values["pointer_events"] }
    public var behavior: Any? { values["behavior"] }
    public var keyboard_vertical_offset: Double? { values["keyboard_vertical_offset"] as? Double }
    public var ref: Any? { values["ref"] }
    public var on_layout: Any? { values["on_layout"] }
}

public struct ModalProps {
    public let values: [String: Any]
    public init(_ values: [String: Any]) throws {
        self.values = values
    }
    public var width: Any? { values["width"] }
    public var height: Any? { values["height"] }
    public var min_width: Any? { values["min_width"] }
    public var max_width: Any? { values["max_width"] }
    public var min_height: Any? { values["min_height"] }
    public var max_height: Any? { values["max_height"] }
    public var aspect_ratio: Double? { values["aspect_ratio"] as? Double }
    public var flex: Double? { values["flex"] as? Double }
    public var flex_grow: Double? { values["flex_grow"] as? Double }
    public var flex_shrink: Double? { values["flex_shrink"] as? Double }
    public var flex_basis: Any? { values["flex_basis"] }
    public var flex_direction: Any? { values["flex_direction"] }
    public var flex_wrap: Any? { values["flex_wrap"] }
    public var justify_content: Any? { values["justify_content"] }
    public var align_items: Any? { values["align_items"] }
    public var align_self: Any? { values["align_self"] }
    public var align_content: Any? { values["align_content"] }
    public var direction: Any? { values["direction"] }
    public var display: Any? { values["display"] }
    public var position: Any? { values["position"] }
    public var top: Any? { values["top"] }
    public var right: Any? { values["right"] }
    public var bottom: Any? { values["bottom"] }
    public var left: Any? { values["left"] }
    public var start: Any? { values["start"] }
    public var end: Any? { values["end"] }
    public var padding: Any? { values["padding"] }
    public var padding_top: Any? { values["padding_top"] }
    public var padding_bottom: Any? { values["padding_bottom"] }
    public var padding_left: Any? { values["padding_left"] }
    public var padding_right: Any? { values["padding_right"] }
    public var padding_start: Any? { values["padding_start"] }
    public var padding_end: Any? { values["padding_end"] }
    public var padding_horizontal: Any? { values["padding_horizontal"] }
    public var padding_vertical: Any? { values["padding_vertical"] }
    public var margin: Any? { values["margin"] }
    public var margin_top: Any? { values["margin_top"] }
    public var margin_bottom: Any? { values["margin_bottom"] }
    public var margin_left: Any? { values["margin_left"] }
    public var margin_right: Any? { values["margin_right"] }
    public var margin_start: Any? { values["margin_start"] }
    public var margin_end: Any? { values["margin_end"] }
    public var margin_horizontal: Any? { values["margin_horizontal"] }
    public var margin_vertical: Any? { values["margin_vertical"] }
    public var spacing: Double? { values["spacing"] as? Double }
    public var gap: Double? { values["gap"] as? Double }
    public var row_gap: Double? { values["row_gap"] as? Double }
    public var column_gap: Double? { values["column_gap"] as? Double }
    public var overflow: Any? { values["overflow"] }
    public var background_color: String? { values["background_color"] as? String }
    public var color: String? { values["color"] as? String }
    public var border_color: String? { values["border_color"] as? String }
    public var placeholder_color: String? { values["placeholder_color"] as? String }
    public var tint_color: String? { values["tint_color"] as? String }
    public var border_width: Double? { values["border_width"] as? Double }
    public var border_radius: Double? { values["border_radius"] as? Double }
    public var border_top_left_radius: Double? { values["border_top_left_radius"] as? Double }
    public var border_top_right_radius: Double? { values["border_top_right_radius"] as? Double }
    public var border_bottom_left_radius: Double? { values["border_bottom_left_radius"] as? Double }
    public var border_bottom_right_radius: Double? { values["border_bottom_right_radius"] as? Double }
    public var border_top_width: Double? { values["border_top_width"] as? Double }
    public var border_right_width: Double? { values["border_right_width"] as? Double }
    public var border_bottom_width: Double? { values["border_bottom_width"] as? Double }
    public var border_left_width: Double? { values["border_left_width"] as? Double }
    public var border_top_color: String? { values["border_top_color"] as? String }
    public var border_right_color: String? { values["border_right_color"] as? String }
    public var border_bottom_color: String? { values["border_bottom_color"] as? String }
    public var border_left_color: String? { values["border_left_color"] as? String }
    public var font_size: Double? { values["font_size"] as? Double }
    public var font_family: String? { values["font_family"] as? String }
    public var font_weight: Any? { values["font_weight"] }
    public var bold: Bool? { values["bold"] as? Bool }
    public var italic: Bool? { values["italic"] as? Bool }
    public var text_align: Any? { values["text_align"] }
    public var text_decoration: Any? { values["text_decoration"] }
    public var text_transform: Any? { values["text_transform"] }
    public var line_height: Double? { values["line_height"] as? Double }
    public var letter_spacing: Double? { values["letter_spacing"] as? Double }
    public var max_lines: Int? { values["max_lines"] as? Int }
    public var text_shadow_color: String? { values["text_shadow_color"] as? String }
    public var text_shadow_offset: Any? { values["text_shadow_offset"] }
    public var text_shadow_radius: Double? { values["text_shadow_radius"] as? Double }
    public var shadow_color: String? { values["shadow_color"] as? String }
    public var shadow_offset: Any? { values["shadow_offset"] }
    public var shadow_opacity: Double? { values["shadow_opacity"] as? Double }
    public var shadow_radius: Double? { values["shadow_radius"] as? Double }
    public var elevation: Double? { values["elevation"] as? Double }
    public var opacity: Double? { values["opacity"] as? Double }
    public var transform: Any? { values["transform"] }
    public var z_index: Int? { values["z_index"] as? Int }
    public var pointer_events: Any? { values["pointer_events"] }
    public var visible: Bool? { values["visible"] as? Bool }
    public var on_dismiss: Any? { values["on_dismiss"] }
    public var on_show: Any? { values["on_show"] }
    public var title: Any? { values["title"] }
    public var animation_type: Any? { values["animation_type"] }
    public var transparent: Bool? { values["transparent"] as? Bool }
    public var presentation_style: Any? { values["presentation_style"] }
    public var dismiss_on_backdrop: Bool? { values["dismiss_on_backdrop"] as? Bool }
    public var ref: Any? { values["ref"] }
    public var on_layout: Any? { values["on_layout"] }
}

public struct PickerProps {
    public let values: [String: Any]
    public init(_ values: [String: Any]) throws {
        self.values = values
    }
    public var width: Any? { values["width"] }
    public var height: Any? { values["height"] }
    public var min_width: Any? { values["min_width"] }
    public var max_width: Any? { values["max_width"] }
    public var min_height: Any? { values["min_height"] }
    public var max_height: Any? { values["max_height"] }
    public var aspect_ratio: Double? { values["aspect_ratio"] as? Double }
    public var flex: Double? { values["flex"] as? Double }
    public var flex_grow: Double? { values["flex_grow"] as? Double }
    public var flex_shrink: Double? { values["flex_shrink"] as? Double }
    public var flex_basis: Any? { values["flex_basis"] }
    public var flex_direction: Any? { values["flex_direction"] }
    public var flex_wrap: Any? { values["flex_wrap"] }
    public var justify_content: Any? { values["justify_content"] }
    public var align_items: Any? { values["align_items"] }
    public var align_self: Any? { values["align_self"] }
    public var align_content: Any? { values["align_content"] }
    public var direction: Any? { values["direction"] }
    public var display: Any? { values["display"] }
    public var position: Any? { values["position"] }
    public var top: Any? { values["top"] }
    public var right: Any? { values["right"] }
    public var bottom: Any? { values["bottom"] }
    public var left: Any? { values["left"] }
    public var start: Any? { values["start"] }
    public var end: Any? { values["end"] }
    public var padding: Any? { values["padding"] }
    public var padding_top: Any? { values["padding_top"] }
    public var padding_bottom: Any? { values["padding_bottom"] }
    public var padding_left: Any? { values["padding_left"] }
    public var padding_right: Any? { values["padding_right"] }
    public var padding_start: Any? { values["padding_start"] }
    public var padding_end: Any? { values["padding_end"] }
    public var padding_horizontal: Any? { values["padding_horizontal"] }
    public var padding_vertical: Any? { values["padding_vertical"] }
    public var margin: Any? { values["margin"] }
    public var margin_top: Any? { values["margin_top"] }
    public var margin_bottom: Any? { values["margin_bottom"] }
    public var margin_left: Any? { values["margin_left"] }
    public var margin_right: Any? { values["margin_right"] }
    public var margin_start: Any? { values["margin_start"] }
    public var margin_end: Any? { values["margin_end"] }
    public var margin_horizontal: Any? { values["margin_horizontal"] }
    public var margin_vertical: Any? { values["margin_vertical"] }
    public var spacing: Double? { values["spacing"] as? Double }
    public var gap: Double? { values["gap"] as? Double }
    public var row_gap: Double? { values["row_gap"] as? Double }
    public var column_gap: Double? { values["column_gap"] as? Double }
    public var overflow: Any? { values["overflow"] }
    public var background_color: String? { values["background_color"] as? String }
    public var color: String? { values["color"] as? String }
    public var border_color: String? { values["border_color"] as? String }
    public var placeholder_color: String? { values["placeholder_color"] as? String }
    public var tint_color: String? { values["tint_color"] as? String }
    public var border_width: Double? { values["border_width"] as? Double }
    public var border_radius: Double? { values["border_radius"] as? Double }
    public var border_top_left_radius: Double? { values["border_top_left_radius"] as? Double }
    public var border_top_right_radius: Double? { values["border_top_right_radius"] as? Double }
    public var border_bottom_left_radius: Double? { values["border_bottom_left_radius"] as? Double }
    public var border_bottom_right_radius: Double? { values["border_bottom_right_radius"] as? Double }
    public var border_top_width: Double? { values["border_top_width"] as? Double }
    public var border_right_width: Double? { values["border_right_width"] as? Double }
    public var border_bottom_width: Double? { values["border_bottom_width"] as? Double }
    public var border_left_width: Double? { values["border_left_width"] as? Double }
    public var border_top_color: String? { values["border_top_color"] as? String }
    public var border_right_color: String? { values["border_right_color"] as? String }
    public var border_bottom_color: String? { values["border_bottom_color"] as? String }
    public var border_left_color: String? { values["border_left_color"] as? String }
    public var font_size: Double? { values["font_size"] as? Double }
    public var font_family: String? { values["font_family"] as? String }
    public var font_weight: Any? { values["font_weight"] }
    public var bold: Bool? { values["bold"] as? Bool }
    public var italic: Bool? { values["italic"] as? Bool }
    public var text_align: Any? { values["text_align"] }
    public var text_decoration: Any? { values["text_decoration"] }
    public var text_transform: Any? { values["text_transform"] }
    public var line_height: Double? { values["line_height"] as? Double }
    public var letter_spacing: Double? { values["letter_spacing"] as? Double }
    public var max_lines: Int? { values["max_lines"] as? Int }
    public var text_shadow_color: String? { values["text_shadow_color"] as? String }
    public var text_shadow_offset: Any? { values["text_shadow_offset"] }
    public var text_shadow_radius: Double? { values["text_shadow_radius"] as? Double }
    public var shadow_color: String? { values["shadow_color"] as? String }
    public var shadow_offset: Any? { values["shadow_offset"] }
    public var shadow_opacity: Double? { values["shadow_opacity"] as? Double }
    public var shadow_radius: Double? { values["shadow_radius"] as? Double }
    public var elevation: Double? { values["elevation"] as? Double }
    public var opacity: Double? { values["opacity"] as? Double }
    public var transform: Any? { values["transform"] }
    public var z_index: Int? { values["z_index"] as? Int }
    public var pointer_events: Any? { values["pointer_events"] }
    public var value: Any? { values["value"] }
    public var disabled: Bool? { values["disabled"] as? Bool }
    public var items: Any? { values["items"] }
    public var on_change: Any? { values["on_change"] }
    public var placeholder: String? { values["placeholder"] as? String }
    public var accessibility_label: Any? { values["accessibility_label"] }
    public var accessibility_hint: Any? { values["accessibility_hint"] }
    public var accessible: Any? { values["accessible"] }
    public var accessibility_state: Any? { values["accessibility_state"] }
    public var accessibility_live_region: Any? { values["accessibility_live_region"] }
    public var test_id: Any? { values["test_id"] }
    public var ref: Any? { values["ref"] }
    public var on_layout: Any? { values["on_layout"] }
}

public struct PortalProps {
    public let values: [String: Any]
    public init(_ values: [String: Any]) throws {
        self.values = values
    }
    public var width: Any? { values["width"] }
    public var height: Any? { values["height"] }
    public var min_width: Any? { values["min_width"] }
    public var max_width: Any? { values["max_width"] }
    public var min_height: Any? { values["min_height"] }
    public var max_height: Any? { values["max_height"] }
    public var aspect_ratio: Double? { values["aspect_ratio"] as? Double }
    public var flex: Double? { values["flex"] as? Double }
    public var flex_grow: Double? { values["flex_grow"] as? Double }
    public var flex_shrink: Double? { values["flex_shrink"] as? Double }
    public var flex_basis: Any? { values["flex_basis"] }
    public var flex_direction: Any? { values["flex_direction"] }
    public var flex_wrap: Any? { values["flex_wrap"] }
    public var justify_content: Any? { values["justify_content"] }
    public var align_items: Any? { values["align_items"] }
    public var align_self: Any? { values["align_self"] }
    public var align_content: Any? { values["align_content"] }
    public var direction: Any? { values["direction"] }
    public var display: Any? { values["display"] }
    public var position: Any? { values["position"] }
    public var top: Any? { values["top"] }
    public var right: Any? { values["right"] }
    public var bottom: Any? { values["bottom"] }
    public var left: Any? { values["left"] }
    public var start: Any? { values["start"] }
    public var end: Any? { values["end"] }
    public var padding: Any? { values["padding"] }
    public var padding_top: Any? { values["padding_top"] }
    public var padding_bottom: Any? { values["padding_bottom"] }
    public var padding_left: Any? { values["padding_left"] }
    public var padding_right: Any? { values["padding_right"] }
    public var padding_start: Any? { values["padding_start"] }
    public var padding_end: Any? { values["padding_end"] }
    public var padding_horizontal: Any? { values["padding_horizontal"] }
    public var padding_vertical: Any? { values["padding_vertical"] }
    public var margin: Any? { values["margin"] }
    public var margin_top: Any? { values["margin_top"] }
    public var margin_bottom: Any? { values["margin_bottom"] }
    public var margin_left: Any? { values["margin_left"] }
    public var margin_right: Any? { values["margin_right"] }
    public var margin_start: Any? { values["margin_start"] }
    public var margin_end: Any? { values["margin_end"] }
    public var margin_horizontal: Any? { values["margin_horizontal"] }
    public var margin_vertical: Any? { values["margin_vertical"] }
    public var spacing: Double? { values["spacing"] as? Double }
    public var gap: Double? { values["gap"] as? Double }
    public var row_gap: Double? { values["row_gap"] as? Double }
    public var column_gap: Double? { values["column_gap"] as? Double }
    public var overflow: Any? { values["overflow"] }
    public var background_color: String? { values["background_color"] as? String }
    public var color: String? { values["color"] as? String }
    public var border_color: String? { values["border_color"] as? String }
    public var placeholder_color: String? { values["placeholder_color"] as? String }
    public var tint_color: String? { values["tint_color"] as? String }
    public var border_width: Double? { values["border_width"] as? Double }
    public var border_radius: Double? { values["border_radius"] as? Double }
    public var border_top_left_radius: Double? { values["border_top_left_radius"] as? Double }
    public var border_top_right_radius: Double? { values["border_top_right_radius"] as? Double }
    public var border_bottom_left_radius: Double? { values["border_bottom_left_radius"] as? Double }
    public var border_bottom_right_radius: Double? { values["border_bottom_right_radius"] as? Double }
    public var border_top_width: Double? { values["border_top_width"] as? Double }
    public var border_right_width: Double? { values["border_right_width"] as? Double }
    public var border_bottom_width: Double? { values["border_bottom_width"] as? Double }
    public var border_left_width: Double? { values["border_left_width"] as? Double }
    public var border_top_color: String? { values["border_top_color"] as? String }
    public var border_right_color: String? { values["border_right_color"] as? String }
    public var border_bottom_color: String? { values["border_bottom_color"] as? String }
    public var border_left_color: String? { values["border_left_color"] as? String }
    public var font_size: Double? { values["font_size"] as? Double }
    public var font_family: String? { values["font_family"] as? String }
    public var font_weight: Any? { values["font_weight"] }
    public var bold: Bool? { values["bold"] as? Bool }
    public var italic: Bool? { values["italic"] as? Bool }
    public var text_align: Any? { values["text_align"] }
    public var text_decoration: Any? { values["text_decoration"] }
    public var text_transform: Any? { values["text_transform"] }
    public var line_height: Double? { values["line_height"] as? Double }
    public var letter_spacing: Double? { values["letter_spacing"] as? Double }
    public var max_lines: Int? { values["max_lines"] as? Int }
    public var text_shadow_color: String? { values["text_shadow_color"] as? String }
    public var text_shadow_offset: Any? { values["text_shadow_offset"] }
    public var text_shadow_radius: Double? { values["text_shadow_radius"] as? Double }
    public var shadow_color: String? { values["shadow_color"] as? String }
    public var shadow_offset: Any? { values["shadow_offset"] }
    public var shadow_opacity: Double? { values["shadow_opacity"] as? Double }
    public var shadow_radius: Double? { values["shadow_radius"] as? Double }
    public var elevation: Double? { values["elevation"] as? Double }
    public var opacity: Double? { values["opacity"] as? Double }
    public var transform: Any? { values["transform"] }
    public var z_index: Int? { values["z_index"] as? Int }
    public var pointer_events: Any? { values["pointer_events"] }
    public var ref: Any? { values["ref"] }
    public var on_layout: Any? { values["on_layout"] }
}

public struct PressableProps {
    public let values: [String: Any]
    public init(_ values: [String: Any]) throws {
        self.values = values
    }
    public var width: Any? { values["width"] }
    public var height: Any? { values["height"] }
    public var min_width: Any? { values["min_width"] }
    public var max_width: Any? { values["max_width"] }
    public var min_height: Any? { values["min_height"] }
    public var max_height: Any? { values["max_height"] }
    public var aspect_ratio: Double? { values["aspect_ratio"] as? Double }
    public var flex: Double? { values["flex"] as? Double }
    public var flex_grow: Double? { values["flex_grow"] as? Double }
    public var flex_shrink: Double? { values["flex_shrink"] as? Double }
    public var flex_basis: Any? { values["flex_basis"] }
    public var flex_direction: Any? { values["flex_direction"] }
    public var flex_wrap: Any? { values["flex_wrap"] }
    public var justify_content: Any? { values["justify_content"] }
    public var align_items: Any? { values["align_items"] }
    public var align_self: Any? { values["align_self"] }
    public var align_content: Any? { values["align_content"] }
    public var direction: Any? { values["direction"] }
    public var display: Any? { values["display"] }
    public var position: Any? { values["position"] }
    public var top: Any? { values["top"] }
    public var right: Any? { values["right"] }
    public var bottom: Any? { values["bottom"] }
    public var left: Any? { values["left"] }
    public var start: Any? { values["start"] }
    public var end: Any? { values["end"] }
    public var padding: Any? { values["padding"] }
    public var padding_top: Any? { values["padding_top"] }
    public var padding_bottom: Any? { values["padding_bottom"] }
    public var padding_left: Any? { values["padding_left"] }
    public var padding_right: Any? { values["padding_right"] }
    public var padding_start: Any? { values["padding_start"] }
    public var padding_end: Any? { values["padding_end"] }
    public var padding_horizontal: Any? { values["padding_horizontal"] }
    public var padding_vertical: Any? { values["padding_vertical"] }
    public var margin: Any? { values["margin"] }
    public var margin_top: Any? { values["margin_top"] }
    public var margin_bottom: Any? { values["margin_bottom"] }
    public var margin_left: Any? { values["margin_left"] }
    public var margin_right: Any? { values["margin_right"] }
    public var margin_start: Any? { values["margin_start"] }
    public var margin_end: Any? { values["margin_end"] }
    public var margin_horizontal: Any? { values["margin_horizontal"] }
    public var margin_vertical: Any? { values["margin_vertical"] }
    public var spacing: Double? { values["spacing"] as? Double }
    public var gap: Double? { values["gap"] as? Double }
    public var row_gap: Double? { values["row_gap"] as? Double }
    public var column_gap: Double? { values["column_gap"] as? Double }
    public var overflow: Any? { values["overflow"] }
    public var background_color: String? { values["background_color"] as? String }
    public var color: String? { values["color"] as? String }
    public var border_color: String? { values["border_color"] as? String }
    public var placeholder_color: String? { values["placeholder_color"] as? String }
    public var tint_color: String? { values["tint_color"] as? String }
    public var border_width: Double? { values["border_width"] as? Double }
    public var border_radius: Double? { values["border_radius"] as? Double }
    public var border_top_left_radius: Double? { values["border_top_left_radius"] as? Double }
    public var border_top_right_radius: Double? { values["border_top_right_radius"] as? Double }
    public var border_bottom_left_radius: Double? { values["border_bottom_left_radius"] as? Double }
    public var border_bottom_right_radius: Double? { values["border_bottom_right_radius"] as? Double }
    public var border_top_width: Double? { values["border_top_width"] as? Double }
    public var border_right_width: Double? { values["border_right_width"] as? Double }
    public var border_bottom_width: Double? { values["border_bottom_width"] as? Double }
    public var border_left_width: Double? { values["border_left_width"] as? Double }
    public var border_top_color: String? { values["border_top_color"] as? String }
    public var border_right_color: String? { values["border_right_color"] as? String }
    public var border_bottom_color: String? { values["border_bottom_color"] as? String }
    public var border_left_color: String? { values["border_left_color"] as? String }
    public var font_size: Double? { values["font_size"] as? Double }
    public var font_family: String? { values["font_family"] as? String }
    public var font_weight: Any? { values["font_weight"] }
    public var bold: Bool? { values["bold"] as? Bool }
    public var italic: Bool? { values["italic"] as? Bool }
    public var text_align: Any? { values["text_align"] }
    public var text_decoration: Any? { values["text_decoration"] }
    public var text_transform: Any? { values["text_transform"] }
    public var line_height: Double? { values["line_height"] as? Double }
    public var letter_spacing: Double? { values["letter_spacing"] as? Double }
    public var max_lines: Int? { values["max_lines"] as? Int }
    public var text_shadow_color: String? { values["text_shadow_color"] as? String }
    public var text_shadow_offset: Any? { values["text_shadow_offset"] }
    public var text_shadow_radius: Double? { values["text_shadow_radius"] as? Double }
    public var shadow_color: String? { values["shadow_color"] as? String }
    public var shadow_offset: Any? { values["shadow_offset"] }
    public var shadow_opacity: Double? { values["shadow_opacity"] as? Double }
    public var shadow_radius: Double? { values["shadow_radius"] as? Double }
    public var elevation: Double? { values["elevation"] as? Double }
    public var opacity: Double? { values["opacity"] as? Double }
    public var transform: Any? { values["transform"] }
    public var z_index: Int? { values["z_index"] as? Int }
    public var pointer_events: Any? { values["pointer_events"] }
    public var on_press: Any? { values["on_press"] }
    public var on_long_press: Any? { values["on_long_press"] }
    public var on_press_in: Any? { values["on_press_in"] }
    public var on_press_out: Any? { values["on_press_out"] }
    public var pressed_opacity: Double? { values["pressed_opacity"] as? Double }
    public var gestures: Any? { values["gestures"] }
    public var hit_slop: Any? { values["hit_slop"] }
    public var on_layout: Any? { values["on_layout"] }
    public var accessibility_label: Any? { values["accessibility_label"] }
    public var accessibility_hint: Any? { values["accessibility_hint"] }
    public var accessibility_role: Any? { values["accessibility_role"] }
    public var accessible: Any? { values["accessible"] }
    public var accessibility_state: Any? { values["accessibility_state"] }
    public var accessibility_live_region: Any? { values["accessibility_live_region"] }
    public var test_id: Any? { values["test_id"] }
    public var ref: Any? { values["ref"] }
}

public struct ProgressBarProps {
    public let values: [String: Any]
    public init(_ values: [String: Any]) throws {
        self.values = values
    }
    public var width: Any? { values["width"] }
    public var height: Any? { values["height"] }
    public var min_width: Any? { values["min_width"] }
    public var max_width: Any? { values["max_width"] }
    public var min_height: Any? { values["min_height"] }
    public var max_height: Any? { values["max_height"] }
    public var aspect_ratio: Double? { values["aspect_ratio"] as? Double }
    public var flex: Double? { values["flex"] as? Double }
    public var flex_grow: Double? { values["flex_grow"] as? Double }
    public var flex_shrink: Double? { values["flex_shrink"] as? Double }
    public var flex_basis: Any? { values["flex_basis"] }
    public var flex_direction: Any? { values["flex_direction"] }
    public var flex_wrap: Any? { values["flex_wrap"] }
    public var justify_content: Any? { values["justify_content"] }
    public var align_items: Any? { values["align_items"] }
    public var align_self: Any? { values["align_self"] }
    public var align_content: Any? { values["align_content"] }
    public var direction: Any? { values["direction"] }
    public var display: Any? { values["display"] }
    public var position: Any? { values["position"] }
    public var top: Any? { values["top"] }
    public var right: Any? { values["right"] }
    public var bottom: Any? { values["bottom"] }
    public var left: Any? { values["left"] }
    public var start: Any? { values["start"] }
    public var end: Any? { values["end"] }
    public var padding: Any? { values["padding"] }
    public var padding_top: Any? { values["padding_top"] }
    public var padding_bottom: Any? { values["padding_bottom"] }
    public var padding_left: Any? { values["padding_left"] }
    public var padding_right: Any? { values["padding_right"] }
    public var padding_start: Any? { values["padding_start"] }
    public var padding_end: Any? { values["padding_end"] }
    public var padding_horizontal: Any? { values["padding_horizontal"] }
    public var padding_vertical: Any? { values["padding_vertical"] }
    public var margin: Any? { values["margin"] }
    public var margin_top: Any? { values["margin_top"] }
    public var margin_bottom: Any? { values["margin_bottom"] }
    public var margin_left: Any? { values["margin_left"] }
    public var margin_right: Any? { values["margin_right"] }
    public var margin_start: Any? { values["margin_start"] }
    public var margin_end: Any? { values["margin_end"] }
    public var margin_horizontal: Any? { values["margin_horizontal"] }
    public var margin_vertical: Any? { values["margin_vertical"] }
    public var spacing: Double? { values["spacing"] as? Double }
    public var gap: Double? { values["gap"] as? Double }
    public var row_gap: Double? { values["row_gap"] as? Double }
    public var column_gap: Double? { values["column_gap"] as? Double }
    public var overflow: Any? { values["overflow"] }
    public var background_color: String? { values["background_color"] as? String }
    public var color: Any? { values["color"] }
    public var border_color: String? { values["border_color"] as? String }
    public var placeholder_color: String? { values["placeholder_color"] as? String }
    public var tint_color: String? { values["tint_color"] as? String }
    public var border_width: Double? { values["border_width"] as? Double }
    public var border_radius: Double? { values["border_radius"] as? Double }
    public var border_top_left_radius: Double? { values["border_top_left_radius"] as? Double }
    public var border_top_right_radius: Double? { values["border_top_right_radius"] as? Double }
    public var border_bottom_left_radius: Double? { values["border_bottom_left_radius"] as? Double }
    public var border_bottom_right_radius: Double? { values["border_bottom_right_radius"] as? Double }
    public var border_top_width: Double? { values["border_top_width"] as? Double }
    public var border_right_width: Double? { values["border_right_width"] as? Double }
    public var border_bottom_width: Double? { values["border_bottom_width"] as? Double }
    public var border_left_width: Double? { values["border_left_width"] as? Double }
    public var border_top_color: String? { values["border_top_color"] as? String }
    public var border_right_color: String? { values["border_right_color"] as? String }
    public var border_bottom_color: String? { values["border_bottom_color"] as? String }
    public var border_left_color: String? { values["border_left_color"] as? String }
    public var font_size: Double? { values["font_size"] as? Double }
    public var font_family: String? { values["font_family"] as? String }
    public var font_weight: Any? { values["font_weight"] }
    public var bold: Bool? { values["bold"] as? Bool }
    public var italic: Bool? { values["italic"] as? Bool }
    public var text_align: Any? { values["text_align"] }
    public var text_decoration: Any? { values["text_decoration"] }
    public var text_transform: Any? { values["text_transform"] }
    public var line_height: Double? { values["line_height"] as? Double }
    public var letter_spacing: Double? { values["letter_spacing"] as? Double }
    public var max_lines: Int? { values["max_lines"] as? Int }
    public var text_shadow_color: String? { values["text_shadow_color"] as? String }
    public var text_shadow_offset: Any? { values["text_shadow_offset"] }
    public var text_shadow_radius: Double? { values["text_shadow_radius"] as? Double }
    public var shadow_color: String? { values["shadow_color"] as? String }
    public var shadow_offset: Any? { values["shadow_offset"] }
    public var shadow_opacity: Double? { values["shadow_opacity"] as? Double }
    public var shadow_radius: Double? { values["shadow_radius"] as? Double }
    public var elevation: Double? { values["elevation"] as? Double }
    public var opacity: Double? { values["opacity"] as? Double }
    public var transform: Any? { values["transform"] }
    public var z_index: Int? { values["z_index"] as? Int }
    public var pointer_events: Any? { values["pointer_events"] }
    public var value: Double? { values["value"] as? Double }
    public var track_color: Any? { values["track_color"] }
    public var indeterminate: Bool? { values["indeterminate"] as? Bool }
    public var ref: Any? { values["ref"] }
    public var on_layout: Any? { values["on_layout"] }
}

public struct RefreshControlProps {
    public let values: [String: Any]
    public init(_ values: [String: Any]) throws {
        self.values = values
    }
    public var width: Any? { values["width"] }
    public var height: Any? { values["height"] }
    public var min_width: Any? { values["min_width"] }
    public var max_width: Any? { values["max_width"] }
    public var min_height: Any? { values["min_height"] }
    public var max_height: Any? { values["max_height"] }
    public var aspect_ratio: Double? { values["aspect_ratio"] as? Double }
    public var flex: Double? { values["flex"] as? Double }
    public var flex_grow: Double? { values["flex_grow"] as? Double }
    public var flex_shrink: Double? { values["flex_shrink"] as? Double }
    public var flex_basis: Any? { values["flex_basis"] }
    public var flex_direction: Any? { values["flex_direction"] }
    public var flex_wrap: Any? { values["flex_wrap"] }
    public var justify_content: Any? { values["justify_content"] }
    public var align_items: Any? { values["align_items"] }
    public var align_self: Any? { values["align_self"] }
    public var align_content: Any? { values["align_content"] }
    public var direction: Any? { values["direction"] }
    public var display: Any? { values["display"] }
    public var position: Any? { values["position"] }
    public var top: Any? { values["top"] }
    public var right: Any? { values["right"] }
    public var bottom: Any? { values["bottom"] }
    public var left: Any? { values["left"] }
    public var start: Any? { values["start"] }
    public var end: Any? { values["end"] }
    public var padding: Any? { values["padding"] }
    public var padding_top: Any? { values["padding_top"] }
    public var padding_bottom: Any? { values["padding_bottom"] }
    public var padding_left: Any? { values["padding_left"] }
    public var padding_right: Any? { values["padding_right"] }
    public var padding_start: Any? { values["padding_start"] }
    public var padding_end: Any? { values["padding_end"] }
    public var padding_horizontal: Any? { values["padding_horizontal"] }
    public var padding_vertical: Any? { values["padding_vertical"] }
    public var margin: Any? { values["margin"] }
    public var margin_top: Any? { values["margin_top"] }
    public var margin_bottom: Any? { values["margin_bottom"] }
    public var margin_left: Any? { values["margin_left"] }
    public var margin_right: Any? { values["margin_right"] }
    public var margin_start: Any? { values["margin_start"] }
    public var margin_end: Any? { values["margin_end"] }
    public var margin_horizontal: Any? { values["margin_horizontal"] }
    public var margin_vertical: Any? { values["margin_vertical"] }
    public var spacing: Double? { values["spacing"] as? Double }
    public var gap: Double? { values["gap"] as? Double }
    public var row_gap: Double? { values["row_gap"] as? Double }
    public var column_gap: Double? { values["column_gap"] as? Double }
    public var overflow: Any? { values["overflow"] }
    public var background_color: String? { values["background_color"] as? String }
    public var color: String? { values["color"] as? String }
    public var border_color: String? { values["border_color"] as? String }
    public var placeholder_color: String? { values["placeholder_color"] as? String }
    public var tint_color: Any? { values["tint_color"] }
    public var border_width: Double? { values["border_width"] as? Double }
    public var border_radius: Double? { values["border_radius"] as? Double }
    public var border_top_left_radius: Double? { values["border_top_left_radius"] as? Double }
    public var border_top_right_radius: Double? { values["border_top_right_radius"] as? Double }
    public var border_bottom_left_radius: Double? { values["border_bottom_left_radius"] as? Double }
    public var border_bottom_right_radius: Double? { values["border_bottom_right_radius"] as? Double }
    public var border_top_width: Double? { values["border_top_width"] as? Double }
    public var border_right_width: Double? { values["border_right_width"] as? Double }
    public var border_bottom_width: Double? { values["border_bottom_width"] as? Double }
    public var border_left_width: Double? { values["border_left_width"] as? Double }
    public var border_top_color: String? { values["border_top_color"] as? String }
    public var border_right_color: String? { values["border_right_color"] as? String }
    public var border_bottom_color: String? { values["border_bottom_color"] as? String }
    public var border_left_color: String? { values["border_left_color"] as? String }
    public var font_size: Double? { values["font_size"] as? Double }
    public var font_family: String? { values["font_family"] as? String }
    public var font_weight: Any? { values["font_weight"] }
    public var bold: Bool? { values["bold"] as? Bool }
    public var italic: Bool? { values["italic"] as? Bool }
    public var text_align: Any? { values["text_align"] }
    public var text_decoration: Any? { values["text_decoration"] }
    public var text_transform: Any? { values["text_transform"] }
    public var line_height: Double? { values["line_height"] as? Double }
    public var letter_spacing: Double? { values["letter_spacing"] as? Double }
    public var max_lines: Int? { values["max_lines"] as? Int }
    public var text_shadow_color: String? { values["text_shadow_color"] as? String }
    public var text_shadow_offset: Any? { values["text_shadow_offset"] }
    public var text_shadow_radius: Double? { values["text_shadow_radius"] as? Double }
    public var shadow_color: String? { values["shadow_color"] as? String }
    public var shadow_offset: Any? { values["shadow_offset"] }
    public var shadow_opacity: Double? { values["shadow_opacity"] as? Double }
    public var shadow_radius: Double? { values["shadow_radius"] as? Double }
    public var elevation: Double? { values["elevation"] as? Double }
    public var opacity: Double? { values["opacity"] as? Double }
    public var transform: Any? { values["transform"] }
    public var z_index: Int? { values["z_index"] as? Int }
    public var pointer_events: Any? { values["pointer_events"] }
    public var refreshing: Bool? { values["refreshing"] as? Bool }
    public var on_refresh: Any? { values["on_refresh"] }
    public var ref: Any? { values["ref"] }
    public var on_layout: Any? { values["on_layout"] }
}

public struct RowProps {
    public let values: [String: Any]
    public init(_ values: [String: Any]) throws {
        self.values = values
    }
    public var width: Any? { values["width"] }
    public var height: Any? { values["height"] }
    public var min_width: Any? { values["min_width"] }
    public var max_width: Any? { values["max_width"] }
    public var min_height: Any? { values["min_height"] }
    public var max_height: Any? { values["max_height"] }
    public var aspect_ratio: Double? { values["aspect_ratio"] as? Double }
    public var flex: Double? { values["flex"] as? Double }
    public var flex_grow: Double? { values["flex_grow"] as? Double }
    public var flex_shrink: Double? { values["flex_shrink"] as? Double }
    public var flex_basis: Any? { values["flex_basis"] }
    public var flex_direction: Any? { values["flex_direction"] }
    public var flex_wrap: Any? { values["flex_wrap"] }
    public var justify_content: Any? { values["justify_content"] }
    public var align_items: Any? { values["align_items"] }
    public var align_self: Any? { values["align_self"] }
    public var align_content: Any? { values["align_content"] }
    public var direction: Any? { values["direction"] }
    public var display: Any? { values["display"] }
    public var position: Any? { values["position"] }
    public var top: Any? { values["top"] }
    public var right: Any? { values["right"] }
    public var bottom: Any? { values["bottom"] }
    public var left: Any? { values["left"] }
    public var start: Any? { values["start"] }
    public var end: Any? { values["end"] }
    public var padding: Any? { values["padding"] }
    public var padding_top: Any? { values["padding_top"] }
    public var padding_bottom: Any? { values["padding_bottom"] }
    public var padding_left: Any? { values["padding_left"] }
    public var padding_right: Any? { values["padding_right"] }
    public var padding_start: Any? { values["padding_start"] }
    public var padding_end: Any? { values["padding_end"] }
    public var padding_horizontal: Any? { values["padding_horizontal"] }
    public var padding_vertical: Any? { values["padding_vertical"] }
    public var margin: Any? { values["margin"] }
    public var margin_top: Any? { values["margin_top"] }
    public var margin_bottom: Any? { values["margin_bottom"] }
    public var margin_left: Any? { values["margin_left"] }
    public var margin_right: Any? { values["margin_right"] }
    public var margin_start: Any? { values["margin_start"] }
    public var margin_end: Any? { values["margin_end"] }
    public var margin_horizontal: Any? { values["margin_horizontal"] }
    public var margin_vertical: Any? { values["margin_vertical"] }
    public var spacing: Double? { values["spacing"] as? Double }
    public var gap: Double? { values["gap"] as? Double }
    public var row_gap: Double? { values["row_gap"] as? Double }
    public var column_gap: Double? { values["column_gap"] as? Double }
    public var overflow: Any? { values["overflow"] }
    public var background_color: String? { values["background_color"] as? String }
    public var color: String? { values["color"] as? String }
    public var border_color: String? { values["border_color"] as? String }
    public var placeholder_color: String? { values["placeholder_color"] as? String }
    public var tint_color: String? { values["tint_color"] as? String }
    public var border_width: Double? { values["border_width"] as? Double }
    public var border_radius: Double? { values["border_radius"] as? Double }
    public var border_top_left_radius: Double? { values["border_top_left_radius"] as? Double }
    public var border_top_right_radius: Double? { values["border_top_right_radius"] as? Double }
    public var border_bottom_left_radius: Double? { values["border_bottom_left_radius"] as? Double }
    public var border_bottom_right_radius: Double? { values["border_bottom_right_radius"] as? Double }
    public var border_top_width: Double? { values["border_top_width"] as? Double }
    public var border_right_width: Double? { values["border_right_width"] as? Double }
    public var border_bottom_width: Double? { values["border_bottom_width"] as? Double }
    public var border_left_width: Double? { values["border_left_width"] as? Double }
    public var border_top_color: String? { values["border_top_color"] as? String }
    public var border_right_color: String? { values["border_right_color"] as? String }
    public var border_bottom_color: String? { values["border_bottom_color"] as? String }
    public var border_left_color: String? { values["border_left_color"] as? String }
    public var font_size: Double? { values["font_size"] as? Double }
    public var font_family: String? { values["font_family"] as? String }
    public var font_weight: Any? { values["font_weight"] }
    public var bold: Bool? { values["bold"] as? Bool }
    public var italic: Bool? { values["italic"] as? Bool }
    public var text_align: Any? { values["text_align"] }
    public var text_decoration: Any? { values["text_decoration"] }
    public var text_transform: Any? { values["text_transform"] }
    public var line_height: Double? { values["line_height"] as? Double }
    public var letter_spacing: Double? { values["letter_spacing"] as? Double }
    public var max_lines: Int? { values["max_lines"] as? Int }
    public var text_shadow_color: String? { values["text_shadow_color"] as? String }
    public var text_shadow_offset: Any? { values["text_shadow_offset"] }
    public var text_shadow_radius: Double? { values["text_shadow_radius"] as? Double }
    public var shadow_color: String? { values["shadow_color"] as? String }
    public var shadow_offset: Any? { values["shadow_offset"] }
    public var shadow_opacity: Double? { values["shadow_opacity"] as? Double }
    public var shadow_radius: Double? { values["shadow_radius"] as? Double }
    public var elevation: Double? { values["elevation"] as? Double }
    public var opacity: Double? { values["opacity"] as? Double }
    public var transform: Any? { values["transform"] }
    public var z_index: Int? { values["z_index"] as? Int }
    public var pointer_events: Any? { values["pointer_events"] }
    public var gestures: Any? { values["gestures"] }
    public var hit_slop: Any? { values["hit_slop"] }
    public var on_layout: Any? { values["on_layout"] }
    public var accessibility_label: Any? { values["accessibility_label"] }
    public var accessibility_hint: Any? { values["accessibility_hint"] }
    public var accessibility_role: Any? { values["accessibility_role"] }
    public var accessible: Any? { values["accessible"] }
    public var accessibility_state: Any? { values["accessibility_state"] }
    public var accessibility_live_region: Any? { values["accessibility_live_region"] }
    public var test_id: Any? { values["test_id"] }
    public var ref: Any? { values["ref"] }
}

public struct SafeAreaViewProps {
    public let values: [String: Any]
    public init(_ values: [String: Any]) throws {
        self.values = values
    }
    public var width: Any? { values["width"] }
    public var height: Any? { values["height"] }
    public var min_width: Any? { values["min_width"] }
    public var max_width: Any? { values["max_width"] }
    public var min_height: Any? { values["min_height"] }
    public var max_height: Any? { values["max_height"] }
    public var aspect_ratio: Double? { values["aspect_ratio"] as? Double }
    public var flex: Double? { values["flex"] as? Double }
    public var flex_grow: Double? { values["flex_grow"] as? Double }
    public var flex_shrink: Double? { values["flex_shrink"] as? Double }
    public var flex_basis: Any? { values["flex_basis"] }
    public var flex_direction: Any? { values["flex_direction"] }
    public var flex_wrap: Any? { values["flex_wrap"] }
    public var justify_content: Any? { values["justify_content"] }
    public var align_items: Any? { values["align_items"] }
    public var align_self: Any? { values["align_self"] }
    public var align_content: Any? { values["align_content"] }
    public var direction: Any? { values["direction"] }
    public var display: Any? { values["display"] }
    public var position: Any? { values["position"] }
    public var top: Any? { values["top"] }
    public var right: Any? { values["right"] }
    public var bottom: Any? { values["bottom"] }
    public var left: Any? { values["left"] }
    public var start: Any? { values["start"] }
    public var end: Any? { values["end"] }
    public var padding: Any? { values["padding"] }
    public var padding_top: Any? { values["padding_top"] }
    public var padding_bottom: Any? { values["padding_bottom"] }
    public var padding_left: Any? { values["padding_left"] }
    public var padding_right: Any? { values["padding_right"] }
    public var padding_start: Any? { values["padding_start"] }
    public var padding_end: Any? { values["padding_end"] }
    public var padding_horizontal: Any? { values["padding_horizontal"] }
    public var padding_vertical: Any? { values["padding_vertical"] }
    public var margin: Any? { values["margin"] }
    public var margin_top: Any? { values["margin_top"] }
    public var margin_bottom: Any? { values["margin_bottom"] }
    public var margin_left: Any? { values["margin_left"] }
    public var margin_right: Any? { values["margin_right"] }
    public var margin_start: Any? { values["margin_start"] }
    public var margin_end: Any? { values["margin_end"] }
    public var margin_horizontal: Any? { values["margin_horizontal"] }
    public var margin_vertical: Any? { values["margin_vertical"] }
    public var spacing: Double? { values["spacing"] as? Double }
    public var gap: Double? { values["gap"] as? Double }
    public var row_gap: Double? { values["row_gap"] as? Double }
    public var column_gap: Double? { values["column_gap"] as? Double }
    public var overflow: Any? { values["overflow"] }
    public var background_color: String? { values["background_color"] as? String }
    public var color: String? { values["color"] as? String }
    public var border_color: String? { values["border_color"] as? String }
    public var placeholder_color: String? { values["placeholder_color"] as? String }
    public var tint_color: String? { values["tint_color"] as? String }
    public var border_width: Double? { values["border_width"] as? Double }
    public var border_radius: Double? { values["border_radius"] as? Double }
    public var border_top_left_radius: Double? { values["border_top_left_radius"] as? Double }
    public var border_top_right_radius: Double? { values["border_top_right_radius"] as? Double }
    public var border_bottom_left_radius: Double? { values["border_bottom_left_radius"] as? Double }
    public var border_bottom_right_radius: Double? { values["border_bottom_right_radius"] as? Double }
    public var border_top_width: Double? { values["border_top_width"] as? Double }
    public var border_right_width: Double? { values["border_right_width"] as? Double }
    public var border_bottom_width: Double? { values["border_bottom_width"] as? Double }
    public var border_left_width: Double? { values["border_left_width"] as? Double }
    public var border_top_color: String? { values["border_top_color"] as? String }
    public var border_right_color: String? { values["border_right_color"] as? String }
    public var border_bottom_color: String? { values["border_bottom_color"] as? String }
    public var border_left_color: String? { values["border_left_color"] as? String }
    public var font_size: Double? { values["font_size"] as? Double }
    public var font_family: String? { values["font_family"] as? String }
    public var font_weight: Any? { values["font_weight"] }
    public var bold: Bool? { values["bold"] as? Bool }
    public var italic: Bool? { values["italic"] as? Bool }
    public var text_align: Any? { values["text_align"] }
    public var text_decoration: Any? { values["text_decoration"] }
    public var text_transform: Any? { values["text_transform"] }
    public var line_height: Double? { values["line_height"] as? Double }
    public var letter_spacing: Double? { values["letter_spacing"] as? Double }
    public var max_lines: Int? { values["max_lines"] as? Int }
    public var text_shadow_color: String? { values["text_shadow_color"] as? String }
    public var text_shadow_offset: Any? { values["text_shadow_offset"] }
    public var text_shadow_radius: Double? { values["text_shadow_radius"] as? Double }
    public var shadow_color: String? { values["shadow_color"] as? String }
    public var shadow_offset: Any? { values["shadow_offset"] }
    public var shadow_opacity: Double? { values["shadow_opacity"] as? Double }
    public var shadow_radius: Double? { values["shadow_radius"] as? Double }
    public var elevation: Double? { values["elevation"] as? Double }
    public var opacity: Double? { values["opacity"] as? Double }
    public var transform: Any? { values["transform"] }
    public var z_index: Int? { values["z_index"] as? Int }
    public var pointer_events: Any? { values["pointer_events"] }
    public var edges: Any? { values["edges"] }
    public var ref: Any? { values["ref"] }
    public var on_layout: Any? { values["on_layout"] }
}

public struct ScreenProps {
    public let values: [String: Any]
    public init(_ values: [String: Any]) throws {
        self.values = values
    }
    public var width: Any? { values["width"] }
    public var height: Any? { values["height"] }
    public var min_width: Any? { values["min_width"] }
    public var max_width: Any? { values["max_width"] }
    public var min_height: Any? { values["min_height"] }
    public var max_height: Any? { values["max_height"] }
    public var aspect_ratio: Double? { values["aspect_ratio"] as? Double }
    public var flex: Double? { values["flex"] as? Double }
    public var flex_grow: Double? { values["flex_grow"] as? Double }
    public var flex_shrink: Double? { values["flex_shrink"] as? Double }
    public var flex_basis: Any? { values["flex_basis"] }
    public var flex_direction: Any? { values["flex_direction"] }
    public var flex_wrap: Any? { values["flex_wrap"] }
    public var justify_content: Any? { values["justify_content"] }
    public var align_items: Any? { values["align_items"] }
    public var align_self: Any? { values["align_self"] }
    public var align_content: Any? { values["align_content"] }
    public var direction: Any? { values["direction"] }
    public var display: Any? { values["display"] }
    public var position: Any? { values["position"] }
    public var top: Any? { values["top"] }
    public var right: Any? { values["right"] }
    public var bottom: Any? { values["bottom"] }
    public var left: Any? { values["left"] }
    public var start: Any? { values["start"] }
    public var end: Any? { values["end"] }
    public var padding: Any? { values["padding"] }
    public var padding_top: Any? { values["padding_top"] }
    public var padding_bottom: Any? { values["padding_bottom"] }
    public var padding_left: Any? { values["padding_left"] }
    public var padding_right: Any? { values["padding_right"] }
    public var padding_start: Any? { values["padding_start"] }
    public var padding_end: Any? { values["padding_end"] }
    public var padding_horizontal: Any? { values["padding_horizontal"] }
    public var padding_vertical: Any? { values["padding_vertical"] }
    public var margin: Any? { values["margin"] }
    public var margin_top: Any? { values["margin_top"] }
    public var margin_bottom: Any? { values["margin_bottom"] }
    public var margin_left: Any? { values["margin_left"] }
    public var margin_right: Any? { values["margin_right"] }
    public var margin_start: Any? { values["margin_start"] }
    public var margin_end: Any? { values["margin_end"] }
    public var margin_horizontal: Any? { values["margin_horizontal"] }
    public var margin_vertical: Any? { values["margin_vertical"] }
    public var spacing: Double? { values["spacing"] as? Double }
    public var gap: Double? { values["gap"] as? Double }
    public var row_gap: Double? { values["row_gap"] as? Double }
    public var column_gap: Double? { values["column_gap"] as? Double }
    public var overflow: Any? { values["overflow"] }
    public var background_color: String? { values["background_color"] as? String }
    public var color: String? { values["color"] as? String }
    public var border_color: String? { values["border_color"] as? String }
    public var placeholder_color: String? { values["placeholder_color"] as? String }
    public var tint_color: String? { values["tint_color"] as? String }
    public var border_width: Double? { values["border_width"] as? Double }
    public var border_radius: Double? { values["border_radius"] as? Double }
    public var border_top_left_radius: Double? { values["border_top_left_radius"] as? Double }
    public var border_top_right_radius: Double? { values["border_top_right_radius"] as? Double }
    public var border_bottom_left_radius: Double? { values["border_bottom_left_radius"] as? Double }
    public var border_bottom_right_radius: Double? { values["border_bottom_right_radius"] as? Double }
    public var border_top_width: Double? { values["border_top_width"] as? Double }
    public var border_right_width: Double? { values["border_right_width"] as? Double }
    public var border_bottom_width: Double? { values["border_bottom_width"] as? Double }
    public var border_left_width: Double? { values["border_left_width"] as? Double }
    public var border_top_color: String? { values["border_top_color"] as? String }
    public var border_right_color: String? { values["border_right_color"] as? String }
    public var border_bottom_color: String? { values["border_bottom_color"] as? String }
    public var border_left_color: String? { values["border_left_color"] as? String }
    public var font_size: Double? { values["font_size"] as? Double }
    public var font_family: String? { values["font_family"] as? String }
    public var font_weight: Any? { values["font_weight"] }
    public var bold: Bool? { values["bold"] as? Bool }
    public var italic: Bool? { values["italic"] as? Bool }
    public var text_align: Any? { values["text_align"] }
    public var text_decoration: Any? { values["text_decoration"] }
    public var text_transform: Any? { values["text_transform"] }
    public var line_height: Double? { values["line_height"] as? Double }
    public var letter_spacing: Double? { values["letter_spacing"] as? Double }
    public var max_lines: Int? { values["max_lines"] as? Int }
    public var text_shadow_color: String? { values["text_shadow_color"] as? String }
    public var text_shadow_offset: Any? { values["text_shadow_offset"] }
    public var text_shadow_radius: Double? { values["text_shadow_radius"] as? Double }
    public var shadow_color: String? { values["shadow_color"] as? String }
    public var shadow_offset: Any? { values["shadow_offset"] }
    public var shadow_opacity: Double? { values["shadow_opacity"] as? Double }
    public var shadow_radius: Double? { values["shadow_radius"] as? Double }
    public var elevation: Double? { values["elevation"] as? Double }
    public var opacity: Double? { values["opacity"] as? Double }
    public var transform: Any? { values["transform"] }
    public var z_index: Int? { values["z_index"] as? Int }
    public var pointer_events: Any? { values["pointer_events"] }
    public var gestures: Any? { values["gestures"] }
    public var hit_slop: Any? { values["hit_slop"] }
    public var on_layout: Any? { values["on_layout"] }
    public var accessibility_label: Any? { values["accessibility_label"] }
    public var accessibility_hint: Any? { values["accessibility_hint"] }
    public var accessibility_role: Any? { values["accessibility_role"] }
    public var accessible: Any? { values["accessible"] }
    public var accessibility_state: Any? { values["accessibility_state"] }
    public var accessibility_live_region: Any? { values["accessibility_live_region"] }
    public var test_id: Any? { values["test_id"] }
    public var ref: Any? { values["ref"] }
    public var route_key: String? { values["route_key"] as? String }
    public var title: String? { values["title"] as? String }
    public var active: Bool? { values["active"] as? Bool }
}

public struct ScreenStackProps {
    public let values: [String: Any]
    public init(_ values: [String: Any]) throws {
        self.values = values
    }
    public var width: Any? { values["width"] }
    public var height: Any? { values["height"] }
    public var min_width: Any? { values["min_width"] }
    public var max_width: Any? { values["max_width"] }
    public var min_height: Any? { values["min_height"] }
    public var max_height: Any? { values["max_height"] }
    public var aspect_ratio: Double? { values["aspect_ratio"] as? Double }
    public var flex: Double? { values["flex"] as? Double }
    public var flex_grow: Double? { values["flex_grow"] as? Double }
    public var flex_shrink: Double? { values["flex_shrink"] as? Double }
    public var flex_basis: Any? { values["flex_basis"] }
    public var flex_direction: Any? { values["flex_direction"] }
    public var flex_wrap: Any? { values["flex_wrap"] }
    public var justify_content: Any? { values["justify_content"] }
    public var align_items: Any? { values["align_items"] }
    public var align_self: Any? { values["align_self"] }
    public var align_content: Any? { values["align_content"] }
    public var direction: Any? { values["direction"] }
    public var display: Any? { values["display"] }
    public var position: Any? { values["position"] }
    public var top: Any? { values["top"] }
    public var right: Any? { values["right"] }
    public var bottom: Any? { values["bottom"] }
    public var left: Any? { values["left"] }
    public var start: Any? { values["start"] }
    public var end: Any? { values["end"] }
    public var padding: Any? { values["padding"] }
    public var padding_top: Any? { values["padding_top"] }
    public var padding_bottom: Any? { values["padding_bottom"] }
    public var padding_left: Any? { values["padding_left"] }
    public var padding_right: Any? { values["padding_right"] }
    public var padding_start: Any? { values["padding_start"] }
    public var padding_end: Any? { values["padding_end"] }
    public var padding_horizontal: Any? { values["padding_horizontal"] }
    public var padding_vertical: Any? { values["padding_vertical"] }
    public var margin: Any? { values["margin"] }
    public var margin_top: Any? { values["margin_top"] }
    public var margin_bottom: Any? { values["margin_bottom"] }
    public var margin_left: Any? { values["margin_left"] }
    public var margin_right: Any? { values["margin_right"] }
    public var margin_start: Any? { values["margin_start"] }
    public var margin_end: Any? { values["margin_end"] }
    public var margin_horizontal: Any? { values["margin_horizontal"] }
    public var margin_vertical: Any? { values["margin_vertical"] }
    public var spacing: Double? { values["spacing"] as? Double }
    public var gap: Double? { values["gap"] as? Double }
    public var row_gap: Double? { values["row_gap"] as? Double }
    public var column_gap: Double? { values["column_gap"] as? Double }
    public var overflow: Any? { values["overflow"] }
    public var background_color: String? { values["background_color"] as? String }
    public var color: String? { values["color"] as? String }
    public var border_color: String? { values["border_color"] as? String }
    public var placeholder_color: String? { values["placeholder_color"] as? String }
    public var tint_color: String? { values["tint_color"] as? String }
    public var border_width: Double? { values["border_width"] as? Double }
    public var border_radius: Double? { values["border_radius"] as? Double }
    public var border_top_left_radius: Double? { values["border_top_left_radius"] as? Double }
    public var border_top_right_radius: Double? { values["border_top_right_radius"] as? Double }
    public var border_bottom_left_radius: Double? { values["border_bottom_left_radius"] as? Double }
    public var border_bottom_right_radius: Double? { values["border_bottom_right_radius"] as? Double }
    public var border_top_width: Double? { values["border_top_width"] as? Double }
    public var border_right_width: Double? { values["border_right_width"] as? Double }
    public var border_bottom_width: Double? { values["border_bottom_width"] as? Double }
    public var border_left_width: Double? { values["border_left_width"] as? Double }
    public var border_top_color: String? { values["border_top_color"] as? String }
    public var border_right_color: String? { values["border_right_color"] as? String }
    public var border_bottom_color: String? { values["border_bottom_color"] as? String }
    public var border_left_color: String? { values["border_left_color"] as? String }
    public var font_size: Double? { values["font_size"] as? Double }
    public var font_family: String? { values["font_family"] as? String }
    public var font_weight: Any? { values["font_weight"] }
    public var bold: Bool? { values["bold"] as? Bool }
    public var italic: Bool? { values["italic"] as? Bool }
    public var text_align: Any? { values["text_align"] }
    public var text_decoration: Any? { values["text_decoration"] }
    public var text_transform: Any? { values["text_transform"] }
    public var line_height: Double? { values["line_height"] as? Double }
    public var letter_spacing: Double? { values["letter_spacing"] as? Double }
    public var max_lines: Int? { values["max_lines"] as? Int }
    public var text_shadow_color: String? { values["text_shadow_color"] as? String }
    public var text_shadow_offset: Any? { values["text_shadow_offset"] }
    public var text_shadow_radius: Double? { values["text_shadow_radius"] as? Double }
    public var shadow_color: String? { values["shadow_color"] as? String }
    public var shadow_offset: Any? { values["shadow_offset"] }
    public var shadow_opacity: Double? { values["shadow_opacity"] as? Double }
    public var shadow_radius: Double? { values["shadow_radius"] as? Double }
    public var elevation: Double? { values["elevation"] as? Double }
    public var opacity: Double? { values["opacity"] as? Double }
    public var transform: Any? { values["transform"] }
    public var z_index: Int? { values["z_index"] as? Int }
    public var pointer_events: Any? { values["pointer_events"] }
    public var gestures: Any? { values["gestures"] }
    public var hit_slop: Any? { values["hit_slop"] }
    public var on_layout: Any? { values["on_layout"] }
    public var accessibility_label: Any? { values["accessibility_label"] }
    public var accessibility_hint: Any? { values["accessibility_hint"] }
    public var accessibility_role: Any? { values["accessibility_role"] }
    public var accessible: Any? { values["accessible"] }
    public var accessibility_state: Any? { values["accessibility_state"] }
    public var accessibility_live_region: Any? { values["accessibility_live_region"] }
    public var test_id: Any? { values["test_id"] }
    public var ref: Any? { values["ref"] }
    public var on_native_back: Any? { values["on_native_back"] }
}

public struct ScrollViewProps {
    public let values: [String: Any]
    public init(_ values: [String: Any]) throws {
        self.values = values
    }
    public var width: Any? { values["width"] }
    public var height: Any? { values["height"] }
    public var min_width: Any? { values["min_width"] }
    public var max_width: Any? { values["max_width"] }
    public var min_height: Any? { values["min_height"] }
    public var max_height: Any? { values["max_height"] }
    public var aspect_ratio: Double? { values["aspect_ratio"] as? Double }
    public var flex: Double? { values["flex"] as? Double }
    public var flex_grow: Double? { values["flex_grow"] as? Double }
    public var flex_shrink: Double? { values["flex_shrink"] as? Double }
    public var flex_basis: Any? { values["flex_basis"] }
    public var flex_direction: Any? { values["flex_direction"] }
    public var flex_wrap: Any? { values["flex_wrap"] }
    public var justify_content: Any? { values["justify_content"] }
    public var align_items: Any? { values["align_items"] }
    public var align_self: Any? { values["align_self"] }
    public var align_content: Any? { values["align_content"] }
    public var direction: Any? { values["direction"] }
    public var display: Any? { values["display"] }
    public var position: Any? { values["position"] }
    public var top: Any? { values["top"] }
    public var right: Any? { values["right"] }
    public var bottom: Any? { values["bottom"] }
    public var left: Any? { values["left"] }
    public var start: Any? { values["start"] }
    public var end: Any? { values["end"] }
    public var padding: Any? { values["padding"] }
    public var padding_top: Any? { values["padding_top"] }
    public var padding_bottom: Any? { values["padding_bottom"] }
    public var padding_left: Any? { values["padding_left"] }
    public var padding_right: Any? { values["padding_right"] }
    public var padding_start: Any? { values["padding_start"] }
    public var padding_end: Any? { values["padding_end"] }
    public var padding_horizontal: Any? { values["padding_horizontal"] }
    public var padding_vertical: Any? { values["padding_vertical"] }
    public var margin: Any? { values["margin"] }
    public var margin_top: Any? { values["margin_top"] }
    public var margin_bottom: Any? { values["margin_bottom"] }
    public var margin_left: Any? { values["margin_left"] }
    public var margin_right: Any? { values["margin_right"] }
    public var margin_start: Any? { values["margin_start"] }
    public var margin_end: Any? { values["margin_end"] }
    public var margin_horizontal: Any? { values["margin_horizontal"] }
    public var margin_vertical: Any? { values["margin_vertical"] }
    public var spacing: Double? { values["spacing"] as? Double }
    public var gap: Double? { values["gap"] as? Double }
    public var row_gap: Double? { values["row_gap"] as? Double }
    public var column_gap: Double? { values["column_gap"] as? Double }
    public var overflow: Any? { values["overflow"] }
    public var background_color: String? { values["background_color"] as? String }
    public var color: String? { values["color"] as? String }
    public var border_color: String? { values["border_color"] as? String }
    public var placeholder_color: String? { values["placeholder_color"] as? String }
    public var tint_color: String? { values["tint_color"] as? String }
    public var border_width: Double? { values["border_width"] as? Double }
    public var border_radius: Double? { values["border_radius"] as? Double }
    public var border_top_left_radius: Double? { values["border_top_left_radius"] as? Double }
    public var border_top_right_radius: Double? { values["border_top_right_radius"] as? Double }
    public var border_bottom_left_radius: Double? { values["border_bottom_left_radius"] as? Double }
    public var border_bottom_right_radius: Double? { values["border_bottom_right_radius"] as? Double }
    public var border_top_width: Double? { values["border_top_width"] as? Double }
    public var border_right_width: Double? { values["border_right_width"] as? Double }
    public var border_bottom_width: Double? { values["border_bottom_width"] as? Double }
    public var border_left_width: Double? { values["border_left_width"] as? Double }
    public var border_top_color: String? { values["border_top_color"] as? String }
    public var border_right_color: String? { values["border_right_color"] as? String }
    public var border_bottom_color: String? { values["border_bottom_color"] as? String }
    public var border_left_color: String? { values["border_left_color"] as? String }
    public var font_size: Double? { values["font_size"] as? Double }
    public var font_family: String? { values["font_family"] as? String }
    public var font_weight: Any? { values["font_weight"] }
    public var bold: Bool? { values["bold"] as? Bool }
    public var italic: Bool? { values["italic"] as? Bool }
    public var text_align: Any? { values["text_align"] }
    public var text_decoration: Any? { values["text_decoration"] }
    public var text_transform: Any? { values["text_transform"] }
    public var line_height: Double? { values["line_height"] as? Double }
    public var letter_spacing: Double? { values["letter_spacing"] as? Double }
    public var max_lines: Int? { values["max_lines"] as? Int }
    public var text_shadow_color: String? { values["text_shadow_color"] as? String }
    public var text_shadow_offset: Any? { values["text_shadow_offset"] }
    public var text_shadow_radius: Double? { values["text_shadow_radius"] as? Double }
    public var shadow_color: String? { values["shadow_color"] as? String }
    public var shadow_offset: Any? { values["shadow_offset"] }
    public var shadow_opacity: Double? { values["shadow_opacity"] as? Double }
    public var shadow_radius: Double? { values["shadow_radius"] as? Double }
    public var elevation: Double? { values["elevation"] as? Double }
    public var opacity: Double? { values["opacity"] as? Double }
    public var transform: Any? { values["transform"] }
    public var z_index: Int? { values["z_index"] as? Int }
    public var pointer_events: Any? { values["pointer_events"] }
    public var refresh_control: Any? { values["refresh_control"] }
    public var scroll_axis: Any? { values["scroll_axis"] }
    public var on_scroll: Any? { values["on_scroll"] }
    public var shows_scroll_indicator: Bool? { values["shows_scroll_indicator"] as? Bool }
    public var paging_enabled: Bool? { values["paging_enabled"] as? Bool }
    public var bounces: Bool? { values["bounces"] as? Bool }
    public var content_container_style: Any? { values["content_container_style"] }
    public var keyboard_dismiss_mode: Any? { values["keyboard_dismiss_mode"] }
    public var ref: Any? { values["ref"] }
    public var on_layout: Any? { values["on_layout"] }
}

public struct SectionListProps {
    public let values: [String: Any]
    public init(_ values: [String: Any]) throws {
        self.values = values
    }
    public var width: Any? { values["width"] }
    public var height: Any? { values["height"] }
    public var min_width: Any? { values["min_width"] }
    public var max_width: Any? { values["max_width"] }
    public var min_height: Any? { values["min_height"] }
    public var max_height: Any? { values["max_height"] }
    public var aspect_ratio: Double? { values["aspect_ratio"] as? Double }
    public var flex: Double? { values["flex"] as? Double }
    public var flex_grow: Double? { values["flex_grow"] as? Double }
    public var flex_shrink: Double? { values["flex_shrink"] as? Double }
    public var flex_basis: Any? { values["flex_basis"] }
    public var flex_direction: Any? { values["flex_direction"] }
    public var flex_wrap: Any? { values["flex_wrap"] }
    public var justify_content: Any? { values["justify_content"] }
    public var align_items: Any? { values["align_items"] }
    public var align_self: Any? { values["align_self"] }
    public var align_content: Any? { values["align_content"] }
    public var direction: Any? { values["direction"] }
    public var display: Any? { values["display"] }
    public var position: Any? { values["position"] }
    public var top: Any? { values["top"] }
    public var right: Any? { values["right"] }
    public var bottom: Any? { values["bottom"] }
    public var left: Any? { values["left"] }
    public var start: Any? { values["start"] }
    public var end: Any? { values["end"] }
    public var padding: Any? { values["padding"] }
    public var padding_top: Any? { values["padding_top"] }
    public var padding_bottom: Any? { values["padding_bottom"] }
    public var padding_left: Any? { values["padding_left"] }
    public var padding_right: Any? { values["padding_right"] }
    public var padding_start: Any? { values["padding_start"] }
    public var padding_end: Any? { values["padding_end"] }
    public var padding_horizontal: Any? { values["padding_horizontal"] }
    public var padding_vertical: Any? { values["padding_vertical"] }
    public var margin: Any? { values["margin"] }
    public var margin_top: Any? { values["margin_top"] }
    public var margin_bottom: Any? { values["margin_bottom"] }
    public var margin_left: Any? { values["margin_left"] }
    public var margin_right: Any? { values["margin_right"] }
    public var margin_start: Any? { values["margin_start"] }
    public var margin_end: Any? { values["margin_end"] }
    public var margin_horizontal: Any? { values["margin_horizontal"] }
    public var margin_vertical: Any? { values["margin_vertical"] }
    public var spacing: Double? { values["spacing"] as? Double }
    public var gap: Double? { values["gap"] as? Double }
    public var row_gap: Double? { values["row_gap"] as? Double }
    public var column_gap: Double? { values["column_gap"] as? Double }
    public var overflow: Any? { values["overflow"] }
    public var background_color: String? { values["background_color"] as? String }
    public var color: String? { values["color"] as? String }
    public var border_color: String? { values["border_color"] as? String }
    public var placeholder_color: String? { values["placeholder_color"] as? String }
    public var tint_color: String? { values["tint_color"] as? String }
    public var border_width: Double? { values["border_width"] as? Double }
    public var border_radius: Double? { values["border_radius"] as? Double }
    public var border_top_left_radius: Double? { values["border_top_left_radius"] as? Double }
    public var border_top_right_radius: Double? { values["border_top_right_radius"] as? Double }
    public var border_bottom_left_radius: Double? { values["border_bottom_left_radius"] as? Double }
    public var border_bottom_right_radius: Double? { values["border_bottom_right_radius"] as? Double }
    public var border_top_width: Double? { values["border_top_width"] as? Double }
    public var border_right_width: Double? { values["border_right_width"] as? Double }
    public var border_bottom_width: Double? { values["border_bottom_width"] as? Double }
    public var border_left_width: Double? { values["border_left_width"] as? Double }
    public var border_top_color: String? { values["border_top_color"] as? String }
    public var border_right_color: String? { values["border_right_color"] as? String }
    public var border_bottom_color: String? { values["border_bottom_color"] as? String }
    public var border_left_color: String? { values["border_left_color"] as? String }
    public var font_size: Double? { values["font_size"] as? Double }
    public var font_family: String? { values["font_family"] as? String }
    public var font_weight: Any? { values["font_weight"] }
    public var bold: Bool? { values["bold"] as? Bool }
    public var italic: Bool? { values["italic"] as? Bool }
    public var text_align: Any? { values["text_align"] }
    public var text_decoration: Any? { values["text_decoration"] }
    public var text_transform: Any? { values["text_transform"] }
    public var line_height: Double? { values["line_height"] as? Double }
    public var letter_spacing: Double? { values["letter_spacing"] as? Double }
    public var max_lines: Int? { values["max_lines"] as? Int }
    public var text_shadow_color: String? { values["text_shadow_color"] as? String }
    public var text_shadow_offset: Any? { values["text_shadow_offset"] }
    public var text_shadow_radius: Double? { values["text_shadow_radius"] as? Double }
    public var shadow_color: String? { values["shadow_color"] as? String }
    public var shadow_offset: Any? { values["shadow_offset"] }
    public var shadow_opacity: Double? { values["shadow_opacity"] as? Double }
    public var shadow_radius: Double? { values["shadow_radius"] as? Double }
    public var elevation: Double? { values["elevation"] as? Double }
    public var opacity: Double? { values["opacity"] as? Double }
    public var transform: Any? { values["transform"] }
    public var z_index: Int? { values["z_index"] as? Int }
    public var pointer_events: Any? { values["pointer_events"] }
    public var sections: Any? { values["sections"] }
    public var render_item: Any? { values["render_item"] }
    public var render_section_header: Any? { values["render_section_header"] }
    public var key_extractor: Any? { values["key_extractor"] }
    public var item_height: Any? { values["item_height"] }
    public var get_item_height: Any? { values["get_item_height"] }
    public var estimated_item_height: Any? { values["estimated_item_height"] }
    public var section_header_height: Any? { values["section_header_height"] }
    public var separator_height: Double? { values["separator_height"] as? Double }
    public var refresh_control: Any? { values["refresh_control"] }
    public var list_header: Any? { values["list_header"] }
    public var list_footer: Any? { values["list_footer"] }
    public var list_empty: Any? { values["list_empty"] }
    public var on_end_reached: Any? { values["on_end_reached"] }
    public var on_end_reached_threshold: Double? { values["on_end_reached_threshold"] as? Double }
    public var on_scroll: Any? { values["on_scroll"] }
    public var ref: Any? { values["ref"] }
    public var on_layout: Any? { values["on_layout"] }
}

public struct SegmentedControlProps {
    public let values: [String: Any]
    public init(_ values: [String: Any]) throws {
        self.values = values
    }
    public var width: Any? { values["width"] }
    public var height: Any? { values["height"] }
    public var min_width: Any? { values["min_width"] }
    public var max_width: Any? { values["max_width"] }
    public var min_height: Any? { values["min_height"] }
    public var max_height: Any? { values["max_height"] }
    public var aspect_ratio: Double? { values["aspect_ratio"] as? Double }
    public var flex: Double? { values["flex"] as? Double }
    public var flex_grow: Double? { values["flex_grow"] as? Double }
    public var flex_shrink: Double? { values["flex_shrink"] as? Double }
    public var flex_basis: Any? { values["flex_basis"] }
    public var flex_direction: Any? { values["flex_direction"] }
    public var flex_wrap: Any? { values["flex_wrap"] }
    public var justify_content: Any? { values["justify_content"] }
    public var align_items: Any? { values["align_items"] }
    public var align_self: Any? { values["align_self"] }
    public var align_content: Any? { values["align_content"] }
    public var direction: Any? { values["direction"] }
    public var display: Any? { values["display"] }
    public var position: Any? { values["position"] }
    public var top: Any? { values["top"] }
    public var right: Any? { values["right"] }
    public var bottom: Any? { values["bottom"] }
    public var left: Any? { values["left"] }
    public var start: Any? { values["start"] }
    public var end: Any? { values["end"] }
    public var padding: Any? { values["padding"] }
    public var padding_top: Any? { values["padding_top"] }
    public var padding_bottom: Any? { values["padding_bottom"] }
    public var padding_left: Any? { values["padding_left"] }
    public var padding_right: Any? { values["padding_right"] }
    public var padding_start: Any? { values["padding_start"] }
    public var padding_end: Any? { values["padding_end"] }
    public var padding_horizontal: Any? { values["padding_horizontal"] }
    public var padding_vertical: Any? { values["padding_vertical"] }
    public var margin: Any? { values["margin"] }
    public var margin_top: Any? { values["margin_top"] }
    public var margin_bottom: Any? { values["margin_bottom"] }
    public var margin_left: Any? { values["margin_left"] }
    public var margin_right: Any? { values["margin_right"] }
    public var margin_start: Any? { values["margin_start"] }
    public var margin_end: Any? { values["margin_end"] }
    public var margin_horizontal: Any? { values["margin_horizontal"] }
    public var margin_vertical: Any? { values["margin_vertical"] }
    public var spacing: Double? { values["spacing"] as? Double }
    public var gap: Double? { values["gap"] as? Double }
    public var row_gap: Double? { values["row_gap"] as? Double }
    public var column_gap: Double? { values["column_gap"] as? Double }
    public var overflow: Any? { values["overflow"] }
    public var background_color: String? { values["background_color"] as? String }
    public var color: String? { values["color"] as? String }
    public var border_color: String? { values["border_color"] as? String }
    public var placeholder_color: String? { values["placeholder_color"] as? String }
    public var tint_color: Any? { values["tint_color"] }
    public var border_width: Double? { values["border_width"] as? Double }
    public var border_radius: Double? { values["border_radius"] as? Double }
    public var border_top_left_radius: Double? { values["border_top_left_radius"] as? Double }
    public var border_top_right_radius: Double? { values["border_top_right_radius"] as? Double }
    public var border_bottom_left_radius: Double? { values["border_bottom_left_radius"] as? Double }
    public var border_bottom_right_radius: Double? { values["border_bottom_right_radius"] as? Double }
    public var border_top_width: Double? { values["border_top_width"] as? Double }
    public var border_right_width: Double? { values["border_right_width"] as? Double }
    public var border_bottom_width: Double? { values["border_bottom_width"] as? Double }
    public var border_left_width: Double? { values["border_left_width"] as? Double }
    public var border_top_color: String? { values["border_top_color"] as? String }
    public var border_right_color: String? { values["border_right_color"] as? String }
    public var border_bottom_color: String? { values["border_bottom_color"] as? String }
    public var border_left_color: String? { values["border_left_color"] as? String }
    public var font_size: Double? { values["font_size"] as? Double }
    public var font_family: String? { values["font_family"] as? String }
    public var font_weight: Any? { values["font_weight"] }
    public var bold: Bool? { values["bold"] as? Bool }
    public var italic: Bool? { values["italic"] as? Bool }
    public var text_align: Any? { values["text_align"] }
    public var text_decoration: Any? { values["text_decoration"] }
    public var text_transform: Any? { values["text_transform"] }
    public var line_height: Double? { values["line_height"] as? Double }
    public var letter_spacing: Double? { values["letter_spacing"] as? Double }
    public var max_lines: Int? { values["max_lines"] as? Int }
    public var text_shadow_color: String? { values["text_shadow_color"] as? String }
    public var text_shadow_offset: Any? { values["text_shadow_offset"] }
    public var text_shadow_radius: Double? { values["text_shadow_radius"] as? Double }
    public var shadow_color: String? { values["shadow_color"] as? String }
    public var shadow_offset: Any? { values["shadow_offset"] }
    public var shadow_opacity: Double? { values["shadow_opacity"] as? Double }
    public var shadow_radius: Double? { values["shadow_radius"] as? Double }
    public var elevation: Double? { values["elevation"] as? Double }
    public var opacity: Double? { values["opacity"] as? Double }
    public var transform: Any? { values["transform"] }
    public var z_index: Int? { values["z_index"] as? Int }
    public var pointer_events: Any? { values["pointer_events"] }
    public var segments: Any? { values["segments"] }
    public var selected_index: Int? { values["selected_index"] as? Int }
    public var on_change: Any? { values["on_change"] }
    public var disabled: Bool? { values["disabled"] as? Bool }
    public var accessibility_label: Any? { values["accessibility_label"] }
    public var accessible: Any? { values["accessible"] }
    public var accessibility_state: Any? { values["accessibility_state"] }
    public var accessibility_live_region: Any? { values["accessibility_live_region"] }
    public var test_id: Any? { values["test_id"] }
    public var ref: Any? { values["ref"] }
    public var on_layout: Any? { values["on_layout"] }
}

public struct SliderProps {
    public let values: [String: Any]
    public init(_ values: [String: Any]) throws {
        self.values = values
    }
    public var width: Any? { values["width"] }
    public var height: Any? { values["height"] }
    public var min_width: Any? { values["min_width"] }
    public var max_width: Any? { values["max_width"] }
    public var min_height: Any? { values["min_height"] }
    public var max_height: Any? { values["max_height"] }
    public var aspect_ratio: Double? { values["aspect_ratio"] as? Double }
    public var flex: Double? { values["flex"] as? Double }
    public var flex_grow: Double? { values["flex_grow"] as? Double }
    public var flex_shrink: Double? { values["flex_shrink"] as? Double }
    public var flex_basis: Any? { values["flex_basis"] }
    public var flex_direction: Any? { values["flex_direction"] }
    public var flex_wrap: Any? { values["flex_wrap"] }
    public var justify_content: Any? { values["justify_content"] }
    public var align_items: Any? { values["align_items"] }
    public var align_self: Any? { values["align_self"] }
    public var align_content: Any? { values["align_content"] }
    public var direction: Any? { values["direction"] }
    public var display: Any? { values["display"] }
    public var position: Any? { values["position"] }
    public var top: Any? { values["top"] }
    public var right: Any? { values["right"] }
    public var bottom: Any? { values["bottom"] }
    public var left: Any? { values["left"] }
    public var start: Any? { values["start"] }
    public var end: Any? { values["end"] }
    public var padding: Any? { values["padding"] }
    public var padding_top: Any? { values["padding_top"] }
    public var padding_bottom: Any? { values["padding_bottom"] }
    public var padding_left: Any? { values["padding_left"] }
    public var padding_right: Any? { values["padding_right"] }
    public var padding_start: Any? { values["padding_start"] }
    public var padding_end: Any? { values["padding_end"] }
    public var padding_horizontal: Any? { values["padding_horizontal"] }
    public var padding_vertical: Any? { values["padding_vertical"] }
    public var margin: Any? { values["margin"] }
    public var margin_top: Any? { values["margin_top"] }
    public var margin_bottom: Any? { values["margin_bottom"] }
    public var margin_left: Any? { values["margin_left"] }
    public var margin_right: Any? { values["margin_right"] }
    public var margin_start: Any? { values["margin_start"] }
    public var margin_end: Any? { values["margin_end"] }
    public var margin_horizontal: Any? { values["margin_horizontal"] }
    public var margin_vertical: Any? { values["margin_vertical"] }
    public var spacing: Double? { values["spacing"] as? Double }
    public var gap: Double? { values["gap"] as? Double }
    public var row_gap: Double? { values["row_gap"] as? Double }
    public var column_gap: Double? { values["column_gap"] as? Double }
    public var overflow: Any? { values["overflow"] }
    public var background_color: String? { values["background_color"] as? String }
    public var color: String? { values["color"] as? String }
    public var border_color: String? { values["border_color"] as? String }
    public var placeholder_color: String? { values["placeholder_color"] as? String }
    public var tint_color: String? { values["tint_color"] as? String }
    public var border_width: Double? { values["border_width"] as? Double }
    public var border_radius: Double? { values["border_radius"] as? Double }
    public var border_top_left_radius: Double? { values["border_top_left_radius"] as? Double }
    public var border_top_right_radius: Double? { values["border_top_right_radius"] as? Double }
    public var border_bottom_left_radius: Double? { values["border_bottom_left_radius"] as? Double }
    public var border_bottom_right_radius: Double? { values["border_bottom_right_radius"] as? Double }
    public var border_top_width: Double? { values["border_top_width"] as? Double }
    public var border_right_width: Double? { values["border_right_width"] as? Double }
    public var border_bottom_width: Double? { values["border_bottom_width"] as? Double }
    public var border_left_width: Double? { values["border_left_width"] as? Double }
    public var border_top_color: String? { values["border_top_color"] as? String }
    public var border_right_color: String? { values["border_right_color"] as? String }
    public var border_bottom_color: String? { values["border_bottom_color"] as? String }
    public var border_left_color: String? { values["border_left_color"] as? String }
    public var font_size: Double? { values["font_size"] as? Double }
    public var font_family: String? { values["font_family"] as? String }
    public var font_weight: Any? { values["font_weight"] }
    public var bold: Bool? { values["bold"] as? Bool }
    public var italic: Bool? { values["italic"] as? Bool }
    public var text_align: Any? { values["text_align"] }
    public var text_decoration: Any? { values["text_decoration"] }
    public var text_transform: Any? { values["text_transform"] }
    public var line_height: Double? { values["line_height"] as? Double }
    public var letter_spacing: Double? { values["letter_spacing"] as? Double }
    public var max_lines: Int? { values["max_lines"] as? Int }
    public var text_shadow_color: String? { values["text_shadow_color"] as? String }
    public var text_shadow_offset: Any? { values["text_shadow_offset"] }
    public var text_shadow_radius: Double? { values["text_shadow_radius"] as? Double }
    public var shadow_color: String? { values["shadow_color"] as? String }
    public var shadow_offset: Any? { values["shadow_offset"] }
    public var shadow_opacity: Double? { values["shadow_opacity"] as? Double }
    public var shadow_radius: Double? { values["shadow_radius"] as? Double }
    public var elevation: Double? { values["elevation"] as? Double }
    public var opacity: Double? { values["opacity"] as? Double }
    public var transform: Any? { values["transform"] }
    public var z_index: Int? { values["z_index"] as? Int }
    public var pointer_events: Any? { values["pointer_events"] }
    public var value: Double? { values["value"] as? Double }
    public var min_value: Double? { values["min_value"] as? Double }
    public var max_value: Double? { values["max_value"] as? Double }
    public var on_change: Any? { values["on_change"] }
    public var accessibility_label: Any? { values["accessibility_label"] }
    public var ref: Any? { values["ref"] }
    public var on_layout: Any? { values["on_layout"] }
}

public struct SpacerProps {
    public let values: [String: Any]
    public init(_ values: [String: Any]) throws {
        self.values = values
    }
    public var width: Any? { values["width"] }
    public var height: Any? { values["height"] }
    public var min_width: Any? { values["min_width"] }
    public var max_width: Any? { values["max_width"] }
    public var min_height: Any? { values["min_height"] }
    public var max_height: Any? { values["max_height"] }
    public var aspect_ratio: Double? { values["aspect_ratio"] as? Double }
    public var flex: Any? { values["flex"] }
    public var flex_grow: Double? { values["flex_grow"] as? Double }
    public var flex_shrink: Double? { values["flex_shrink"] as? Double }
    public var flex_basis: Any? { values["flex_basis"] }
    public var flex_direction: Any? { values["flex_direction"] }
    public var flex_wrap: Any? { values["flex_wrap"] }
    public var justify_content: Any? { values["justify_content"] }
    public var align_items: Any? { values["align_items"] }
    public var align_self: Any? { values["align_self"] }
    public var align_content: Any? { values["align_content"] }
    public var direction: Any? { values["direction"] }
    public var display: Any? { values["display"] }
    public var position: Any? { values["position"] }
    public var top: Any? { values["top"] }
    public var right: Any? { values["right"] }
    public var bottom: Any? { values["bottom"] }
    public var left: Any? { values["left"] }
    public var start: Any? { values["start"] }
    public var end: Any? { values["end"] }
    public var padding: Any? { values["padding"] }
    public var padding_top: Any? { values["padding_top"] }
    public var padding_bottom: Any? { values["padding_bottom"] }
    public var padding_left: Any? { values["padding_left"] }
    public var padding_right: Any? { values["padding_right"] }
    public var padding_start: Any? { values["padding_start"] }
    public var padding_end: Any? { values["padding_end"] }
    public var padding_horizontal: Any? { values["padding_horizontal"] }
    public var padding_vertical: Any? { values["padding_vertical"] }
    public var margin: Any? { values["margin"] }
    public var margin_top: Any? { values["margin_top"] }
    public var margin_bottom: Any? { values["margin_bottom"] }
    public var margin_left: Any? { values["margin_left"] }
    public var margin_right: Any? { values["margin_right"] }
    public var margin_start: Any? { values["margin_start"] }
    public var margin_end: Any? { values["margin_end"] }
    public var margin_horizontal: Any? { values["margin_horizontal"] }
    public var margin_vertical: Any? { values["margin_vertical"] }
    public var spacing: Double? { values["spacing"] as? Double }
    public var gap: Double? { values["gap"] as? Double }
    public var row_gap: Double? { values["row_gap"] as? Double }
    public var column_gap: Double? { values["column_gap"] as? Double }
    public var overflow: Any? { values["overflow"] }
    public var background_color: String? { values["background_color"] as? String }
    public var color: String? { values["color"] as? String }
    public var border_color: String? { values["border_color"] as? String }
    public var placeholder_color: String? { values["placeholder_color"] as? String }
    public var tint_color: String? { values["tint_color"] as? String }
    public var border_width: Double? { values["border_width"] as? Double }
    public var border_radius: Double? { values["border_radius"] as? Double }
    public var border_top_left_radius: Double? { values["border_top_left_radius"] as? Double }
    public var border_top_right_radius: Double? { values["border_top_right_radius"] as? Double }
    public var border_bottom_left_radius: Double? { values["border_bottom_left_radius"] as? Double }
    public var border_bottom_right_radius: Double? { values["border_bottom_right_radius"] as? Double }
    public var border_top_width: Double? { values["border_top_width"] as? Double }
    public var border_right_width: Double? { values["border_right_width"] as? Double }
    public var border_bottom_width: Double? { values["border_bottom_width"] as? Double }
    public var border_left_width: Double? { values["border_left_width"] as? Double }
    public var border_top_color: String? { values["border_top_color"] as? String }
    public var border_right_color: String? { values["border_right_color"] as? String }
    public var border_bottom_color: String? { values["border_bottom_color"] as? String }
    public var border_left_color: String? { values["border_left_color"] as? String }
    public var font_size: Double? { values["font_size"] as? Double }
    public var font_family: String? { values["font_family"] as? String }
    public var font_weight: Any? { values["font_weight"] }
    public var bold: Bool? { values["bold"] as? Bool }
    public var italic: Bool? { values["italic"] as? Bool }
    public var text_align: Any? { values["text_align"] }
    public var text_decoration: Any? { values["text_decoration"] }
    public var text_transform: Any? { values["text_transform"] }
    public var line_height: Double? { values["line_height"] as? Double }
    public var letter_spacing: Double? { values["letter_spacing"] as? Double }
    public var max_lines: Int? { values["max_lines"] as? Int }
    public var text_shadow_color: String? { values["text_shadow_color"] as? String }
    public var text_shadow_offset: Any? { values["text_shadow_offset"] }
    public var text_shadow_radius: Double? { values["text_shadow_radius"] as? Double }
    public var shadow_color: String? { values["shadow_color"] as? String }
    public var shadow_offset: Any? { values["shadow_offset"] }
    public var shadow_opacity: Double? { values["shadow_opacity"] as? Double }
    public var shadow_radius: Double? { values["shadow_radius"] as? Double }
    public var elevation: Double? { values["elevation"] as? Double }
    public var opacity: Double? { values["opacity"] as? Double }
    public var transform: Any? { values["transform"] }
    public var z_index: Int? { values["z_index"] as? Int }
    public var pointer_events: Any? { values["pointer_events"] }
    public var size: Any? { values["size"] }
    public var ref: Any? { values["ref"] }
    public var on_layout: Any? { values["on_layout"] }
}

public struct StatusBarProps {
    public let values: [String: Any]
    public init(_ values: [String: Any]) throws {
        self.values = values
    }
    public var width: Any? { values["width"] }
    public var height: Any? { values["height"] }
    public var min_width: Any? { values["min_width"] }
    public var max_width: Any? { values["max_width"] }
    public var min_height: Any? { values["min_height"] }
    public var max_height: Any? { values["max_height"] }
    public var aspect_ratio: Double? { values["aspect_ratio"] as? Double }
    public var flex: Double? { values["flex"] as? Double }
    public var flex_grow: Double? { values["flex_grow"] as? Double }
    public var flex_shrink: Double? { values["flex_shrink"] as? Double }
    public var flex_basis: Any? { values["flex_basis"] }
    public var flex_direction: Any? { values["flex_direction"] }
    public var flex_wrap: Any? { values["flex_wrap"] }
    public var justify_content: Any? { values["justify_content"] }
    public var align_items: Any? { values["align_items"] }
    public var align_self: Any? { values["align_self"] }
    public var align_content: Any? { values["align_content"] }
    public var direction: Any? { values["direction"] }
    public var display: Any? { values["display"] }
    public var position: Any? { values["position"] }
    public var top: Any? { values["top"] }
    public var right: Any? { values["right"] }
    public var bottom: Any? { values["bottom"] }
    public var left: Any? { values["left"] }
    public var start: Any? { values["start"] }
    public var end: Any? { values["end"] }
    public var padding: Any? { values["padding"] }
    public var padding_top: Any? { values["padding_top"] }
    public var padding_bottom: Any? { values["padding_bottom"] }
    public var padding_left: Any? { values["padding_left"] }
    public var padding_right: Any? { values["padding_right"] }
    public var padding_start: Any? { values["padding_start"] }
    public var padding_end: Any? { values["padding_end"] }
    public var padding_horizontal: Any? { values["padding_horizontal"] }
    public var padding_vertical: Any? { values["padding_vertical"] }
    public var margin: Any? { values["margin"] }
    public var margin_top: Any? { values["margin_top"] }
    public var margin_bottom: Any? { values["margin_bottom"] }
    public var margin_left: Any? { values["margin_left"] }
    public var margin_right: Any? { values["margin_right"] }
    public var margin_start: Any? { values["margin_start"] }
    public var margin_end: Any? { values["margin_end"] }
    public var margin_horizontal: Any? { values["margin_horizontal"] }
    public var margin_vertical: Any? { values["margin_vertical"] }
    public var spacing: Double? { values["spacing"] as? Double }
    public var gap: Double? { values["gap"] as? Double }
    public var row_gap: Double? { values["row_gap"] as? Double }
    public var column_gap: Double? { values["column_gap"] as? Double }
    public var overflow: Any? { values["overflow"] }
    public var background_color: Any? { values["background_color"] }
    public var color: String? { values["color"] as? String }
    public var border_color: String? { values["border_color"] as? String }
    public var placeholder_color: String? { values["placeholder_color"] as? String }
    public var tint_color: String? { values["tint_color"] as? String }
    public var border_width: Double? { values["border_width"] as? Double }
    public var border_radius: Double? { values["border_radius"] as? Double }
    public var border_top_left_radius: Double? { values["border_top_left_radius"] as? Double }
    public var border_top_right_radius: Double? { values["border_top_right_radius"] as? Double }
    public var border_bottom_left_radius: Double? { values["border_bottom_left_radius"] as? Double }
    public var border_bottom_right_radius: Double? { values["border_bottom_right_radius"] as? Double }
    public var border_top_width: Double? { values["border_top_width"] as? Double }
    public var border_right_width: Double? { values["border_right_width"] as? Double }
    public var border_bottom_width: Double? { values["border_bottom_width"] as? Double }
    public var border_left_width: Double? { values["border_left_width"] as? Double }
    public var border_top_color: String? { values["border_top_color"] as? String }
    public var border_right_color: String? { values["border_right_color"] as? String }
    public var border_bottom_color: String? { values["border_bottom_color"] as? String }
    public var border_left_color: String? { values["border_left_color"] as? String }
    public var font_size: Double? { values["font_size"] as? Double }
    public var font_family: String? { values["font_family"] as? String }
    public var font_weight: Any? { values["font_weight"] }
    public var bold: Bool? { values["bold"] as? Bool }
    public var italic: Bool? { values["italic"] as? Bool }
    public var text_align: Any? { values["text_align"] }
    public var text_decoration: Any? { values["text_decoration"] }
    public var text_transform: Any? { values["text_transform"] }
    public var line_height: Double? { values["line_height"] as? Double }
    public var letter_spacing: Double? { values["letter_spacing"] as? Double }
    public var max_lines: Int? { values["max_lines"] as? Int }
    public var text_shadow_color: String? { values["text_shadow_color"] as? String }
    public var text_shadow_offset: Any? { values["text_shadow_offset"] }
    public var text_shadow_radius: Double? { values["text_shadow_radius"] as? Double }
    public var shadow_color: String? { values["shadow_color"] as? String }
    public var shadow_offset: Any? { values["shadow_offset"] }
    public var shadow_opacity: Double? { values["shadow_opacity"] as? Double }
    public var shadow_radius: Double? { values["shadow_radius"] as? Double }
    public var elevation: Double? { values["elevation"] as? Double }
    public var opacity: Double? { values["opacity"] as? Double }
    public var transform: Any? { values["transform"] }
    public var z_index: Int? { values["z_index"] as? Int }
    public var pointer_events: Any? { values["pointer_events"] }
    public var bar_style: Any? { values["bar_style"] }
    public var hidden: Any? { values["hidden"] }
    public var ref: Any? { values["ref"] }
    public var on_layout: Any? { values["on_layout"] }
}

public struct SuspenseProps {
    public let values: [String: Any]
    public init(_ values: [String: Any]) throws {
        self.values = values
    }
    public var width: Any? { values["width"] }
    public var height: Any? { values["height"] }
    public var min_width: Any? { values["min_width"] }
    public var max_width: Any? { values["max_width"] }
    public var min_height: Any? { values["min_height"] }
    public var max_height: Any? { values["max_height"] }
    public var aspect_ratio: Double? { values["aspect_ratio"] as? Double }
    public var flex: Double? { values["flex"] as? Double }
    public var flex_grow: Double? { values["flex_grow"] as? Double }
    public var flex_shrink: Double? { values["flex_shrink"] as? Double }
    public var flex_basis: Any? { values["flex_basis"] }
    public var flex_direction: Any? { values["flex_direction"] }
    public var flex_wrap: Any? { values["flex_wrap"] }
    public var justify_content: Any? { values["justify_content"] }
    public var align_items: Any? { values["align_items"] }
    public var align_self: Any? { values["align_self"] }
    public var align_content: Any? { values["align_content"] }
    public var direction: Any? { values["direction"] }
    public var display: Any? { values["display"] }
    public var position: Any? { values["position"] }
    public var top: Any? { values["top"] }
    public var right: Any? { values["right"] }
    public var bottom: Any? { values["bottom"] }
    public var left: Any? { values["left"] }
    public var start: Any? { values["start"] }
    public var end: Any? { values["end"] }
    public var padding: Any? { values["padding"] }
    public var padding_top: Any? { values["padding_top"] }
    public var padding_bottom: Any? { values["padding_bottom"] }
    public var padding_left: Any? { values["padding_left"] }
    public var padding_right: Any? { values["padding_right"] }
    public var padding_start: Any? { values["padding_start"] }
    public var padding_end: Any? { values["padding_end"] }
    public var padding_horizontal: Any? { values["padding_horizontal"] }
    public var padding_vertical: Any? { values["padding_vertical"] }
    public var margin: Any? { values["margin"] }
    public var margin_top: Any? { values["margin_top"] }
    public var margin_bottom: Any? { values["margin_bottom"] }
    public var margin_left: Any? { values["margin_left"] }
    public var margin_right: Any? { values["margin_right"] }
    public var margin_start: Any? { values["margin_start"] }
    public var margin_end: Any? { values["margin_end"] }
    public var margin_horizontal: Any? { values["margin_horizontal"] }
    public var margin_vertical: Any? { values["margin_vertical"] }
    public var spacing: Double? { values["spacing"] as? Double }
    public var gap: Double? { values["gap"] as? Double }
    public var row_gap: Double? { values["row_gap"] as? Double }
    public var column_gap: Double? { values["column_gap"] as? Double }
    public var overflow: Any? { values["overflow"] }
    public var background_color: String? { values["background_color"] as? String }
    public var color: String? { values["color"] as? String }
    public var border_color: String? { values["border_color"] as? String }
    public var placeholder_color: String? { values["placeholder_color"] as? String }
    public var tint_color: String? { values["tint_color"] as? String }
    public var border_width: Double? { values["border_width"] as? Double }
    public var border_radius: Double? { values["border_radius"] as? Double }
    public var border_top_left_radius: Double? { values["border_top_left_radius"] as? Double }
    public var border_top_right_radius: Double? { values["border_top_right_radius"] as? Double }
    public var border_bottom_left_radius: Double? { values["border_bottom_left_radius"] as? Double }
    public var border_bottom_right_radius: Double? { values["border_bottom_right_radius"] as? Double }
    public var border_top_width: Double? { values["border_top_width"] as? Double }
    public var border_right_width: Double? { values["border_right_width"] as? Double }
    public var border_bottom_width: Double? { values["border_bottom_width"] as? Double }
    public var border_left_width: Double? { values["border_left_width"] as? Double }
    public var border_top_color: String? { values["border_top_color"] as? String }
    public var border_right_color: String? { values["border_right_color"] as? String }
    public var border_bottom_color: String? { values["border_bottom_color"] as? String }
    public var border_left_color: String? { values["border_left_color"] as? String }
    public var font_size: Double? { values["font_size"] as? Double }
    public var font_family: String? { values["font_family"] as? String }
    public var font_weight: Any? { values["font_weight"] }
    public var bold: Bool? { values["bold"] as? Bool }
    public var italic: Bool? { values["italic"] as? Bool }
    public var text_align: Any? { values["text_align"] }
    public var text_decoration: Any? { values["text_decoration"] }
    public var text_transform: Any? { values["text_transform"] }
    public var line_height: Double? { values["line_height"] as? Double }
    public var letter_spacing: Double? { values["letter_spacing"] as? Double }
    public var max_lines: Int? { values["max_lines"] as? Int }
    public var text_shadow_color: String? { values["text_shadow_color"] as? String }
    public var text_shadow_offset: Any? { values["text_shadow_offset"] }
    public var text_shadow_radius: Double? { values["text_shadow_radius"] as? Double }
    public var shadow_color: String? { values["shadow_color"] as? String }
    public var shadow_offset: Any? { values["shadow_offset"] }
    public var shadow_opacity: Double? { values["shadow_opacity"] as? Double }
    public var shadow_radius: Double? { values["shadow_radius"] as? Double }
    public var elevation: Double? { values["elevation"] as? Double }
    public var opacity: Double? { values["opacity"] as? Double }
    public var transform: Any? { values["transform"] }
    public var z_index: Int? { values["z_index"] as? Int }
    public var pointer_events: Any? { values["pointer_events"] }
    public var fallback: Any? { values["fallback"] }
    public var ref: Any? { values["ref"] }
    public var on_layout: Any? { values["on_layout"] }
}

public struct SwitchProps {
    public let values: [String: Any]
    public init(_ values: [String: Any]) throws {
        self.values = values
    }
    public var width: Any? { values["width"] }
    public var height: Any? { values["height"] }
    public var min_width: Any? { values["min_width"] }
    public var max_width: Any? { values["max_width"] }
    public var min_height: Any? { values["min_height"] }
    public var max_height: Any? { values["max_height"] }
    public var aspect_ratio: Double? { values["aspect_ratio"] as? Double }
    public var flex: Double? { values["flex"] as? Double }
    public var flex_grow: Double? { values["flex_grow"] as? Double }
    public var flex_shrink: Double? { values["flex_shrink"] as? Double }
    public var flex_basis: Any? { values["flex_basis"] }
    public var flex_direction: Any? { values["flex_direction"] }
    public var flex_wrap: Any? { values["flex_wrap"] }
    public var justify_content: Any? { values["justify_content"] }
    public var align_items: Any? { values["align_items"] }
    public var align_self: Any? { values["align_self"] }
    public var align_content: Any? { values["align_content"] }
    public var direction: Any? { values["direction"] }
    public var display: Any? { values["display"] }
    public var position: Any? { values["position"] }
    public var top: Any? { values["top"] }
    public var right: Any? { values["right"] }
    public var bottom: Any? { values["bottom"] }
    public var left: Any? { values["left"] }
    public var start: Any? { values["start"] }
    public var end: Any? { values["end"] }
    public var padding: Any? { values["padding"] }
    public var padding_top: Any? { values["padding_top"] }
    public var padding_bottom: Any? { values["padding_bottom"] }
    public var padding_left: Any? { values["padding_left"] }
    public var padding_right: Any? { values["padding_right"] }
    public var padding_start: Any? { values["padding_start"] }
    public var padding_end: Any? { values["padding_end"] }
    public var padding_horizontal: Any? { values["padding_horizontal"] }
    public var padding_vertical: Any? { values["padding_vertical"] }
    public var margin: Any? { values["margin"] }
    public var margin_top: Any? { values["margin_top"] }
    public var margin_bottom: Any? { values["margin_bottom"] }
    public var margin_left: Any? { values["margin_left"] }
    public var margin_right: Any? { values["margin_right"] }
    public var margin_start: Any? { values["margin_start"] }
    public var margin_end: Any? { values["margin_end"] }
    public var margin_horizontal: Any? { values["margin_horizontal"] }
    public var margin_vertical: Any? { values["margin_vertical"] }
    public var spacing: Double? { values["spacing"] as? Double }
    public var gap: Double? { values["gap"] as? Double }
    public var row_gap: Double? { values["row_gap"] as? Double }
    public var column_gap: Double? { values["column_gap"] as? Double }
    public var overflow: Any? { values["overflow"] }
    public var background_color: String? { values["background_color"] as? String }
    public var color: String? { values["color"] as? String }
    public var border_color: String? { values["border_color"] as? String }
    public var placeholder_color: String? { values["placeholder_color"] as? String }
    public var tint_color: String? { values["tint_color"] as? String }
    public var border_width: Double? { values["border_width"] as? Double }
    public var border_radius: Double? { values["border_radius"] as? Double }
    public var border_top_left_radius: Double? { values["border_top_left_radius"] as? Double }
    public var border_top_right_radius: Double? { values["border_top_right_radius"] as? Double }
    public var border_bottom_left_radius: Double? { values["border_bottom_left_radius"] as? Double }
    public var border_bottom_right_radius: Double? { values["border_bottom_right_radius"] as? Double }
    public var border_top_width: Double? { values["border_top_width"] as? Double }
    public var border_right_width: Double? { values["border_right_width"] as? Double }
    public var border_bottom_width: Double? { values["border_bottom_width"] as? Double }
    public var border_left_width: Double? { values["border_left_width"] as? Double }
    public var border_top_color: String? { values["border_top_color"] as? String }
    public var border_right_color: String? { values["border_right_color"] as? String }
    public var border_bottom_color: String? { values["border_bottom_color"] as? String }
    public var border_left_color: String? { values["border_left_color"] as? String }
    public var font_size: Double? { values["font_size"] as? Double }
    public var font_family: String? { values["font_family"] as? String }
    public var font_weight: Any? { values["font_weight"] }
    public var bold: Bool? { values["bold"] as? Bool }
    public var italic: Bool? { values["italic"] as? Bool }
    public var text_align: Any? { values["text_align"] }
    public var text_decoration: Any? { values["text_decoration"] }
    public var text_transform: Any? { values["text_transform"] }
    public var line_height: Double? { values["line_height"] as? Double }
    public var letter_spacing: Double? { values["letter_spacing"] as? Double }
    public var max_lines: Int? { values["max_lines"] as? Int }
    public var text_shadow_color: String? { values["text_shadow_color"] as? String }
    public var text_shadow_offset: Any? { values["text_shadow_offset"] }
    public var text_shadow_radius: Double? { values["text_shadow_radius"] as? Double }
    public var shadow_color: String? { values["shadow_color"] as? String }
    public var shadow_offset: Any? { values["shadow_offset"] }
    public var shadow_opacity: Double? { values["shadow_opacity"] as? Double }
    public var shadow_radius: Double? { values["shadow_radius"] as? Double }
    public var elevation: Double? { values["elevation"] as? Double }
    public var opacity: Double? { values["opacity"] as? Double }
    public var transform: Any? { values["transform"] }
    public var z_index: Int? { values["z_index"] as? Int }
    public var pointer_events: Any? { values["pointer_events"] }
    public var value: Bool? { values["value"] as? Bool }
    public var on_change: Any? { values["on_change"] }
    public var accessibility_label: Any? { values["accessibility_label"] }
    public var ref: Any? { values["ref"] }
    public var on_layout: Any? { values["on_layout"] }
}

public struct TextProps {
    public let values: [String: Any]
    public init(_ values: [String: Any]) throws {
        self.values = values
    }
    public var width: Any? { values["width"] }
    public var height: Any? { values["height"] }
    public var min_width: Any? { values["min_width"] }
    public var max_width: Any? { values["max_width"] }
    public var min_height: Any? { values["min_height"] }
    public var max_height: Any? { values["max_height"] }
    public var aspect_ratio: Double? { values["aspect_ratio"] as? Double }
    public var flex: Double? { values["flex"] as? Double }
    public var flex_grow: Double? { values["flex_grow"] as? Double }
    public var flex_shrink: Double? { values["flex_shrink"] as? Double }
    public var flex_basis: Any? { values["flex_basis"] }
    public var flex_direction: Any? { values["flex_direction"] }
    public var flex_wrap: Any? { values["flex_wrap"] }
    public var justify_content: Any? { values["justify_content"] }
    public var align_items: Any? { values["align_items"] }
    public var align_self: Any? { values["align_self"] }
    public var align_content: Any? { values["align_content"] }
    public var direction: Any? { values["direction"] }
    public var display: Any? { values["display"] }
    public var position: Any? { values["position"] }
    public var top: Any? { values["top"] }
    public var right: Any? { values["right"] }
    public var bottom: Any? { values["bottom"] }
    public var left: Any? { values["left"] }
    public var start: Any? { values["start"] }
    public var end: Any? { values["end"] }
    public var padding: Any? { values["padding"] }
    public var padding_top: Any? { values["padding_top"] }
    public var padding_bottom: Any? { values["padding_bottom"] }
    public var padding_left: Any? { values["padding_left"] }
    public var padding_right: Any? { values["padding_right"] }
    public var padding_start: Any? { values["padding_start"] }
    public var padding_end: Any? { values["padding_end"] }
    public var padding_horizontal: Any? { values["padding_horizontal"] }
    public var padding_vertical: Any? { values["padding_vertical"] }
    public var margin: Any? { values["margin"] }
    public var margin_top: Any? { values["margin_top"] }
    public var margin_bottom: Any? { values["margin_bottom"] }
    public var margin_left: Any? { values["margin_left"] }
    public var margin_right: Any? { values["margin_right"] }
    public var margin_start: Any? { values["margin_start"] }
    public var margin_end: Any? { values["margin_end"] }
    public var margin_horizontal: Any? { values["margin_horizontal"] }
    public var margin_vertical: Any? { values["margin_vertical"] }
    public var spacing: Double? { values["spacing"] as? Double }
    public var gap: Double? { values["gap"] as? Double }
    public var row_gap: Double? { values["row_gap"] as? Double }
    public var column_gap: Double? { values["column_gap"] as? Double }
    public var overflow: Any? { values["overflow"] }
    public var background_color: String? { values["background_color"] as? String }
    public var color: String? { values["color"] as? String }
    public var border_color: String? { values["border_color"] as? String }
    public var placeholder_color: String? { values["placeholder_color"] as? String }
    public var tint_color: String? { values["tint_color"] as? String }
    public var border_width: Double? { values["border_width"] as? Double }
    public var border_radius: Double? { values["border_radius"] as? Double }
    public var border_top_left_radius: Double? { values["border_top_left_radius"] as? Double }
    public var border_top_right_radius: Double? { values["border_top_right_radius"] as? Double }
    public var border_bottom_left_radius: Double? { values["border_bottom_left_radius"] as? Double }
    public var border_bottom_right_radius: Double? { values["border_bottom_right_radius"] as? Double }
    public var border_top_width: Double? { values["border_top_width"] as? Double }
    public var border_right_width: Double? { values["border_right_width"] as? Double }
    public var border_bottom_width: Double? { values["border_bottom_width"] as? Double }
    public var border_left_width: Double? { values["border_left_width"] as? Double }
    public var border_top_color: String? { values["border_top_color"] as? String }
    public var border_right_color: String? { values["border_right_color"] as? String }
    public var border_bottom_color: String? { values["border_bottom_color"] as? String }
    public var border_left_color: String? { values["border_left_color"] as? String }
    public var font_size: Double? { values["font_size"] as? Double }
    public var font_family: String? { values["font_family"] as? String }
    public var font_weight: Any? { values["font_weight"] }
    public var bold: Bool? { values["bold"] as? Bool }
    public var italic: Bool? { values["italic"] as? Bool }
    public var text_align: Any? { values["text_align"] }
    public var text_decoration: Any? { values["text_decoration"] }
    public var text_transform: Any? { values["text_transform"] }
    public var line_height: Double? { values["line_height"] as? Double }
    public var letter_spacing: Double? { values["letter_spacing"] as? Double }
    public var max_lines: Int? { values["max_lines"] as? Int }
    public var text_shadow_color: String? { values["text_shadow_color"] as? String }
    public var text_shadow_offset: Any? { values["text_shadow_offset"] }
    public var text_shadow_radius: Double? { values["text_shadow_radius"] as? Double }
    public var shadow_color: String? { values["shadow_color"] as? String }
    public var shadow_offset: Any? { values["shadow_offset"] }
    public var shadow_opacity: Double? { values["shadow_opacity"] as? Double }
    public var shadow_radius: Double? { values["shadow_radius"] as? Double }
    public var elevation: Double? { values["elevation"] as? Double }
    public var opacity: Double? { values["opacity"] as? Double }
    public var transform: Any? { values["transform"] }
    public var z_index: Int? { values["z_index"] as? Int }
    public var pointer_events: Any? { values["pointer_events"] }
    public var accessibility_label: Any? { values["accessibility_label"] }
    public var accessibility_hint: Any? { values["accessibility_hint"] }
    public var accessibility_role: Any? { values["accessibility_role"] }
    public var accessible: Any? { values["accessible"] }
    public var accessibility_state: Any? { values["accessibility_state"] }
    public var accessibility_live_region: Any? { values["accessibility_live_region"] }
    public var test_id: Any? { values["test_id"] }
    public var ref: Any? { values["ref"] }
    public var on_layout: Any? { values["on_layout"] }
    public var text: String? { values["text"] as? String }
    public var spans: Any? { values["spans"] }
}

public struct TextInputProps {
    public let values: [String: Any]
    public init(_ values: [String: Any]) throws {
        self.values = values
    }
    public var width: Any? { values["width"] }
    public var height: Any? { values["height"] }
    public var min_width: Any? { values["min_width"] }
    public var max_width: Any? { values["max_width"] }
    public var min_height: Any? { values["min_height"] }
    public var max_height: Any? { values["max_height"] }
    public var aspect_ratio: Double? { values["aspect_ratio"] as? Double }
    public var flex: Double? { values["flex"] as? Double }
    public var flex_grow: Double? { values["flex_grow"] as? Double }
    public var flex_shrink: Double? { values["flex_shrink"] as? Double }
    public var flex_basis: Any? { values["flex_basis"] }
    public var flex_direction: Any? { values["flex_direction"] }
    public var flex_wrap: Any? { values["flex_wrap"] }
    public var justify_content: Any? { values["justify_content"] }
    public var align_items: Any? { values["align_items"] }
    public var align_self: Any? { values["align_self"] }
    public var align_content: Any? { values["align_content"] }
    public var direction: Any? { values["direction"] }
    public var display: Any? { values["display"] }
    public var position: Any? { values["position"] }
    public var top: Any? { values["top"] }
    public var right: Any? { values["right"] }
    public var bottom: Any? { values["bottom"] }
    public var left: Any? { values["left"] }
    public var start: Any? { values["start"] }
    public var end: Any? { values["end"] }
    public var padding: Any? { values["padding"] }
    public var padding_top: Any? { values["padding_top"] }
    public var padding_bottom: Any? { values["padding_bottom"] }
    public var padding_left: Any? { values["padding_left"] }
    public var padding_right: Any? { values["padding_right"] }
    public var padding_start: Any? { values["padding_start"] }
    public var padding_end: Any? { values["padding_end"] }
    public var padding_horizontal: Any? { values["padding_horizontal"] }
    public var padding_vertical: Any? { values["padding_vertical"] }
    public var margin: Any? { values["margin"] }
    public var margin_top: Any? { values["margin_top"] }
    public var margin_bottom: Any? { values["margin_bottom"] }
    public var margin_left: Any? { values["margin_left"] }
    public var margin_right: Any? { values["margin_right"] }
    public var margin_start: Any? { values["margin_start"] }
    public var margin_end: Any? { values["margin_end"] }
    public var margin_horizontal: Any? { values["margin_horizontal"] }
    public var margin_vertical: Any? { values["margin_vertical"] }
    public var spacing: Double? { values["spacing"] as? Double }
    public var gap: Double? { values["gap"] as? Double }
    public var row_gap: Double? { values["row_gap"] as? Double }
    public var column_gap: Double? { values["column_gap"] as? Double }
    public var overflow: Any? { values["overflow"] }
    public var background_color: String? { values["background_color"] as? String }
    public var color: String? { values["color"] as? String }
    public var border_color: String? { values["border_color"] as? String }
    public var placeholder_color: Any? { values["placeholder_color"] }
    public var tint_color: String? { values["tint_color"] as? String }
    public var border_width: Double? { values["border_width"] as? Double }
    public var border_radius: Double? { values["border_radius"] as? Double }
    public var border_top_left_radius: Double? { values["border_top_left_radius"] as? Double }
    public var border_top_right_radius: Double? { values["border_top_right_radius"] as? Double }
    public var border_bottom_left_radius: Double? { values["border_bottom_left_radius"] as? Double }
    public var border_bottom_right_radius: Double? { values["border_bottom_right_radius"] as? Double }
    public var border_top_width: Double? { values["border_top_width"] as? Double }
    public var border_right_width: Double? { values["border_right_width"] as? Double }
    public var border_bottom_width: Double? { values["border_bottom_width"] as? Double }
    public var border_left_width: Double? { values["border_left_width"] as? Double }
    public var border_top_color: String? { values["border_top_color"] as? String }
    public var border_right_color: String? { values["border_right_color"] as? String }
    public var border_bottom_color: String? { values["border_bottom_color"] as? String }
    public var border_left_color: String? { values["border_left_color"] as? String }
    public var font_size: Double? { values["font_size"] as? Double }
    public var font_family: String? { values["font_family"] as? String }
    public var font_weight: Any? { values["font_weight"] }
    public var bold: Bool? { values["bold"] as? Bool }
    public var italic: Bool? { values["italic"] as? Bool }
    public var text_align: Any? { values["text_align"] }
    public var text_decoration: Any? { values["text_decoration"] }
    public var text_transform: Any? { values["text_transform"] }
    public var line_height: Double? { values["line_height"] as? Double }
    public var letter_spacing: Double? { values["letter_spacing"] as? Double }
    public var max_lines: Int? { values["max_lines"] as? Int }
    public var text_shadow_color: String? { values["text_shadow_color"] as? String }
    public var text_shadow_offset: Any? { values["text_shadow_offset"] }
    public var text_shadow_radius: Double? { values["text_shadow_radius"] as? Double }
    public var shadow_color: String? { values["shadow_color"] as? String }
    public var shadow_offset: Any? { values["shadow_offset"] }
    public var shadow_opacity: Double? { values["shadow_opacity"] as? Double }
    public var shadow_radius: Double? { values["shadow_radius"] as? Double }
    public var elevation: Double? { values["elevation"] as? Double }
    public var opacity: Double? { values["opacity"] as? Double }
    public var transform: Any? { values["transform"] }
    public var z_index: Int? { values["z_index"] as? Int }
    public var pointer_events: Any? { values["pointer_events"] }
    public var value: String? { values["value"] as? String }
    public var placeholder: Any? { values["placeholder"] }
    public var on_change: Any? { values["on_change"] }
    public var on_submit: Any? { values["on_submit"] }
    public var secure: Bool? { values["secure"] as? Bool }
    public var multiline: Bool? { values["multiline"] as? Bool }
    public var keyboard_type: Any? { values["keyboard_type"] }
    public var auto_capitalize: Any? { values["auto_capitalize"] }
    public var auto_correct: Any? { values["auto_correct"] }
    public var auto_focus: Bool? { values["auto_focus"] as? Bool }
    public var return_key_type: Any? { values["return_key_type"] }
    public var max_length: Any? { values["max_length"] }
    public var editable: Bool? { values["editable"] as? Bool }
    public var clear_button: Bool? { values["clear_button"] as? Bool }
    public var on_focus: Any? { values["on_focus"] }
    public var on_blur: Any? { values["on_blur"] }
    public var selection_color: Any? { values["selection_color"] }
    public var text_content_type: Any? { values["text_content_type"] }
    public var accessibility_label: Any? { values["accessibility_label"] }
    public var accessibility_hint: Any? { values["accessibility_hint"] }
    public var accessible: Any? { values["accessible"] }
    public var accessibility_state: Any? { values["accessibility_state"] }
    public var accessibility_live_region: Any? { values["accessibility_live_region"] }
    public var test_id: Any? { values["test_id"] }
    public var ref: Any? { values["ref"] }
    public var on_layout: Any? { values["on_layout"] }
}

public struct TouchableOpacityProps {
    public let values: [String: Any]
    public init(_ values: [String: Any]) throws {
        self.values = values
    }
    public var width: Any? { values["width"] }
    public var height: Any? { values["height"] }
    public var min_width: Any? { values["min_width"] }
    public var max_width: Any? { values["max_width"] }
    public var min_height: Any? { values["min_height"] }
    public var max_height: Any? { values["max_height"] }
    public var aspect_ratio: Double? { values["aspect_ratio"] as? Double }
    public var flex: Double? { values["flex"] as? Double }
    public var flex_grow: Double? { values["flex_grow"] as? Double }
    public var flex_shrink: Double? { values["flex_shrink"] as? Double }
    public var flex_basis: Any? { values["flex_basis"] }
    public var flex_direction: Any? { values["flex_direction"] }
    public var flex_wrap: Any? { values["flex_wrap"] }
    public var justify_content: Any? { values["justify_content"] }
    public var align_items: Any? { values["align_items"] }
    public var align_self: Any? { values["align_self"] }
    public var align_content: Any? { values["align_content"] }
    public var direction: Any? { values["direction"] }
    public var display: Any? { values["display"] }
    public var position: Any? { values["position"] }
    public var top: Any? { values["top"] }
    public var right: Any? { values["right"] }
    public var bottom: Any? { values["bottom"] }
    public var left: Any? { values["left"] }
    public var start: Any? { values["start"] }
    public var end: Any? { values["end"] }
    public var padding: Any? { values["padding"] }
    public var padding_top: Any? { values["padding_top"] }
    public var padding_bottom: Any? { values["padding_bottom"] }
    public var padding_left: Any? { values["padding_left"] }
    public var padding_right: Any? { values["padding_right"] }
    public var padding_start: Any? { values["padding_start"] }
    public var padding_end: Any? { values["padding_end"] }
    public var padding_horizontal: Any? { values["padding_horizontal"] }
    public var padding_vertical: Any? { values["padding_vertical"] }
    public var margin: Any? { values["margin"] }
    public var margin_top: Any? { values["margin_top"] }
    public var margin_bottom: Any? { values["margin_bottom"] }
    public var margin_left: Any? { values["margin_left"] }
    public var margin_right: Any? { values["margin_right"] }
    public var margin_start: Any? { values["margin_start"] }
    public var margin_end: Any? { values["margin_end"] }
    public var margin_horizontal: Any? { values["margin_horizontal"] }
    public var margin_vertical: Any? { values["margin_vertical"] }
    public var spacing: Double? { values["spacing"] as? Double }
    public var gap: Double? { values["gap"] as? Double }
    public var row_gap: Double? { values["row_gap"] as? Double }
    public var column_gap: Double? { values["column_gap"] as? Double }
    public var overflow: Any? { values["overflow"] }
    public var background_color: String? { values["background_color"] as? String }
    public var color: String? { values["color"] as? String }
    public var border_color: String? { values["border_color"] as? String }
    public var placeholder_color: String? { values["placeholder_color"] as? String }
    public var tint_color: String? { values["tint_color"] as? String }
    public var border_width: Double? { values["border_width"] as? Double }
    public var border_radius: Double? { values["border_radius"] as? Double }
    public var border_top_left_radius: Double? { values["border_top_left_radius"] as? Double }
    public var border_top_right_radius: Double? { values["border_top_right_radius"] as? Double }
    public var border_bottom_left_radius: Double? { values["border_bottom_left_radius"] as? Double }
    public var border_bottom_right_radius: Double? { values["border_bottom_right_radius"] as? Double }
    public var border_top_width: Double? { values["border_top_width"] as? Double }
    public var border_right_width: Double? { values["border_right_width"] as? Double }
    public var border_bottom_width: Double? { values["border_bottom_width"] as? Double }
    public var border_left_width: Double? { values["border_left_width"] as? Double }
    public var border_top_color: String? { values["border_top_color"] as? String }
    public var border_right_color: String? { values["border_right_color"] as? String }
    public var border_bottom_color: String? { values["border_bottom_color"] as? String }
    public var border_left_color: String? { values["border_left_color"] as? String }
    public var font_size: Double? { values["font_size"] as? Double }
    public var font_family: String? { values["font_family"] as? String }
    public var font_weight: Any? { values["font_weight"] }
    public var bold: Bool? { values["bold"] as? Bool }
    public var italic: Bool? { values["italic"] as? Bool }
    public var text_align: Any? { values["text_align"] }
    public var text_decoration: Any? { values["text_decoration"] }
    public var text_transform: Any? { values["text_transform"] }
    public var line_height: Double? { values["line_height"] as? Double }
    public var letter_spacing: Double? { values["letter_spacing"] as? Double }
    public var max_lines: Int? { values["max_lines"] as? Int }
    public var text_shadow_color: String? { values["text_shadow_color"] as? String }
    public var text_shadow_offset: Any? { values["text_shadow_offset"] }
    public var text_shadow_radius: Double? { values["text_shadow_radius"] as? Double }
    public var shadow_color: String? { values["shadow_color"] as? String }
    public var shadow_offset: Any? { values["shadow_offset"] }
    public var shadow_opacity: Double? { values["shadow_opacity"] as? Double }
    public var shadow_radius: Double? { values["shadow_radius"] as? Double }
    public var elevation: Double? { values["elevation"] as? Double }
    public var opacity: Double? { values["opacity"] as? Double }
    public var transform: Any? { values["transform"] }
    public var z_index: Int? { values["z_index"] as? Int }
    public var pointer_events: Any? { values["pointer_events"] }
    public var on_press: Any? { values["on_press"] }
    public var on_long_press: Any? { values["on_long_press"] }
    public var active_opacity: Double? { values["active_opacity"] as? Double }
    public var disabled: Bool? { values["disabled"] as? Bool }
    public var accessibility_label: Any? { values["accessibility_label"] }
    public var accessibility_hint: Any? { values["accessibility_hint"] }
    public var accessibility_role: Any? { values["accessibility_role"] }
    public var accessible: Any? { values["accessible"] }
    public var accessibility_state: Any? { values["accessibility_state"] }
    public var accessibility_live_region: Any? { values["accessibility_live_region"] }
    public var test_id: Any? { values["test_id"] }
    public var ref: Any? { values["ref"] }
    public var on_layout: Any? { values["on_layout"] }
}

public struct ViewProps {
    public let values: [String: Any]
    public init(_ values: [String: Any]) throws {
        self.values = values
    }
    public var width: Any? { values["width"] }
    public var height: Any? { values["height"] }
    public var min_width: Any? { values["min_width"] }
    public var max_width: Any? { values["max_width"] }
    public var min_height: Any? { values["min_height"] }
    public var max_height: Any? { values["max_height"] }
    public var aspect_ratio: Double? { values["aspect_ratio"] as? Double }
    public var flex: Double? { values["flex"] as? Double }
    public var flex_grow: Double? { values["flex_grow"] as? Double }
    public var flex_shrink: Double? { values["flex_shrink"] as? Double }
    public var flex_basis: Any? { values["flex_basis"] }
    public var flex_direction: Any? { values["flex_direction"] }
    public var flex_wrap: Any? { values["flex_wrap"] }
    public var justify_content: Any? { values["justify_content"] }
    public var align_items: Any? { values["align_items"] }
    public var align_self: Any? { values["align_self"] }
    public var align_content: Any? { values["align_content"] }
    public var direction: Any? { values["direction"] }
    public var display: Any? { values["display"] }
    public var position: Any? { values["position"] }
    public var top: Any? { values["top"] }
    public var right: Any? { values["right"] }
    public var bottom: Any? { values["bottom"] }
    public var left: Any? { values["left"] }
    public var start: Any? { values["start"] }
    public var end: Any? { values["end"] }
    public var padding: Any? { values["padding"] }
    public var padding_top: Any? { values["padding_top"] }
    public var padding_bottom: Any? { values["padding_bottom"] }
    public var padding_left: Any? { values["padding_left"] }
    public var padding_right: Any? { values["padding_right"] }
    public var padding_start: Any? { values["padding_start"] }
    public var padding_end: Any? { values["padding_end"] }
    public var padding_horizontal: Any? { values["padding_horizontal"] }
    public var padding_vertical: Any? { values["padding_vertical"] }
    public var margin: Any? { values["margin"] }
    public var margin_top: Any? { values["margin_top"] }
    public var margin_bottom: Any? { values["margin_bottom"] }
    public var margin_left: Any? { values["margin_left"] }
    public var margin_right: Any? { values["margin_right"] }
    public var margin_start: Any? { values["margin_start"] }
    public var margin_end: Any? { values["margin_end"] }
    public var margin_horizontal: Any? { values["margin_horizontal"] }
    public var margin_vertical: Any? { values["margin_vertical"] }
    public var spacing: Double? { values["spacing"] as? Double }
    public var gap: Double? { values["gap"] as? Double }
    public var row_gap: Double? { values["row_gap"] as? Double }
    public var column_gap: Double? { values["column_gap"] as? Double }
    public var overflow: Any? { values["overflow"] }
    public var background_color: String? { values["background_color"] as? String }
    public var color: String? { values["color"] as? String }
    public var border_color: String? { values["border_color"] as? String }
    public var placeholder_color: String? { values["placeholder_color"] as? String }
    public var tint_color: String? { values["tint_color"] as? String }
    public var border_width: Double? { values["border_width"] as? Double }
    public var border_radius: Double? { values["border_radius"] as? Double }
    public var border_top_left_radius: Double? { values["border_top_left_radius"] as? Double }
    public var border_top_right_radius: Double? { values["border_top_right_radius"] as? Double }
    public var border_bottom_left_radius: Double? { values["border_bottom_left_radius"] as? Double }
    public var border_bottom_right_radius: Double? { values["border_bottom_right_radius"] as? Double }
    public var border_top_width: Double? { values["border_top_width"] as? Double }
    public var border_right_width: Double? { values["border_right_width"] as? Double }
    public var border_bottom_width: Double? { values["border_bottom_width"] as? Double }
    public var border_left_width: Double? { values["border_left_width"] as? Double }
    public var border_top_color: String? { values["border_top_color"] as? String }
    public var border_right_color: String? { values["border_right_color"] as? String }
    public var border_bottom_color: String? { values["border_bottom_color"] as? String }
    public var border_left_color: String? { values["border_left_color"] as? String }
    public var font_size: Double? { values["font_size"] as? Double }
    public var font_family: String? { values["font_family"] as? String }
    public var font_weight: Any? { values["font_weight"] }
    public var bold: Bool? { values["bold"] as? Bool }
    public var italic: Bool? { values["italic"] as? Bool }
    public var text_align: Any? { values["text_align"] }
    public var text_decoration: Any? { values["text_decoration"] }
    public var text_transform: Any? { values["text_transform"] }
    public var line_height: Double? { values["line_height"] as? Double }
    public var letter_spacing: Double? { values["letter_spacing"] as? Double }
    public var max_lines: Int? { values["max_lines"] as? Int }
    public var text_shadow_color: String? { values["text_shadow_color"] as? String }
    public var text_shadow_offset: Any? { values["text_shadow_offset"] }
    public var text_shadow_radius: Double? { values["text_shadow_radius"] as? Double }
    public var shadow_color: String? { values["shadow_color"] as? String }
    public var shadow_offset: Any? { values["shadow_offset"] }
    public var shadow_opacity: Double? { values["shadow_opacity"] as? Double }
    public var shadow_radius: Double? { values["shadow_radius"] as? Double }
    public var elevation: Double? { values["elevation"] as? Double }
    public var opacity: Double? { values["opacity"] as? Double }
    public var transform: Any? { values["transform"] }
    public var z_index: Int? { values["z_index"] as? Int }
    public var pointer_events: Any? { values["pointer_events"] }
    public var gestures: Any? { values["gestures"] }
    public var hit_slop: Any? { values["hit_slop"] }
    public var on_layout: Any? { values["on_layout"] }
    public var accessibility_label: Any? { values["accessibility_label"] }
    public var accessibility_hint: Any? { values["accessibility_hint"] }
    public var accessibility_role: Any? { values["accessibility_role"] }
    public var accessible: Any? { values["accessible"] }
    public var accessibility_state: Any? { values["accessibility_state"] }
    public var accessibility_live_region: Any? { values["accessibility_live_region"] }
    public var test_id: Any? { values["test_id"] }
    public var ref: Any? { values["ref"] }
}

public struct VirtualListProps {
    public let values: [String: Any]
    public init(_ values: [String: Any]) throws {
        self.values = values
    }
    public var width: Any? { values["width"] }
    public var height: Any? { values["height"] }
    public var min_width: Any? { values["min_width"] }
    public var max_width: Any? { values["max_width"] }
    public var min_height: Any? { values["min_height"] }
    public var max_height: Any? { values["max_height"] }
    public var aspect_ratio: Double? { values["aspect_ratio"] as? Double }
    public var flex: Double? { values["flex"] as? Double }
    public var flex_grow: Double? { values["flex_grow"] as? Double }
    public var flex_shrink: Double? { values["flex_shrink"] as? Double }
    public var flex_basis: Any? { values["flex_basis"] }
    public var flex_direction: Any? { values["flex_direction"] }
    public var flex_wrap: Any? { values["flex_wrap"] }
    public var justify_content: Any? { values["justify_content"] }
    public var align_items: Any? { values["align_items"] }
    public var align_self: Any? { values["align_self"] }
    public var align_content: Any? { values["align_content"] }
    public var direction: Any? { values["direction"] }
    public var display: Any? { values["display"] }
    public var position: Any? { values["position"] }
    public var top: Any? { values["top"] }
    public var right: Any? { values["right"] }
    public var bottom: Any? { values["bottom"] }
    public var left: Any? { values["left"] }
    public var start: Any? { values["start"] }
    public var end: Any? { values["end"] }
    public var padding: Any? { values["padding"] }
    public var padding_top: Any? { values["padding_top"] }
    public var padding_bottom: Any? { values["padding_bottom"] }
    public var padding_left: Any? { values["padding_left"] }
    public var padding_right: Any? { values["padding_right"] }
    public var padding_start: Any? { values["padding_start"] }
    public var padding_end: Any? { values["padding_end"] }
    public var padding_horizontal: Any? { values["padding_horizontal"] }
    public var padding_vertical: Any? { values["padding_vertical"] }
    public var margin: Any? { values["margin"] }
    public var margin_top: Any? { values["margin_top"] }
    public var margin_bottom: Any? { values["margin_bottom"] }
    public var margin_left: Any? { values["margin_left"] }
    public var margin_right: Any? { values["margin_right"] }
    public var margin_start: Any? { values["margin_start"] }
    public var margin_end: Any? { values["margin_end"] }
    public var margin_horizontal: Any? { values["margin_horizontal"] }
    public var margin_vertical: Any? { values["margin_vertical"] }
    public var spacing: Double? { values["spacing"] as? Double }
    public var gap: Double? { values["gap"] as? Double }
    public var row_gap: Double? { values["row_gap"] as? Double }
    public var column_gap: Double? { values["column_gap"] as? Double }
    public var overflow: Any? { values["overflow"] }
    public var background_color: String? { values["background_color"] as? String }
    public var color: String? { values["color"] as? String }
    public var border_color: String? { values["border_color"] as? String }
    public var placeholder_color: String? { values["placeholder_color"] as? String }
    public var tint_color: String? { values["tint_color"] as? String }
    public var border_width: Double? { values["border_width"] as? Double }
    public var border_radius: Double? { values["border_radius"] as? Double }
    public var border_top_left_radius: Double? { values["border_top_left_radius"] as? Double }
    public var border_top_right_radius: Double? { values["border_top_right_radius"] as? Double }
    public var border_bottom_left_radius: Double? { values["border_bottom_left_radius"] as? Double }
    public var border_bottom_right_radius: Double? { values["border_bottom_right_radius"] as? Double }
    public var border_top_width: Double? { values["border_top_width"] as? Double }
    public var border_right_width: Double? { values["border_right_width"] as? Double }
    public var border_bottom_width: Double? { values["border_bottom_width"] as? Double }
    public var border_left_width: Double? { values["border_left_width"] as? Double }
    public var border_top_color: String? { values["border_top_color"] as? String }
    public var border_right_color: String? { values["border_right_color"] as? String }
    public var border_bottom_color: String? { values["border_bottom_color"] as? String }
    public var border_left_color: String? { values["border_left_color"] as? String }
    public var font_size: Double? { values["font_size"] as? Double }
    public var font_family: String? { values["font_family"] as? String }
    public var font_weight: Any? { values["font_weight"] }
    public var bold: Bool? { values["bold"] as? Bool }
    public var italic: Bool? { values["italic"] as? Bool }
    public var text_align: Any? { values["text_align"] }
    public var text_decoration: Any? { values["text_decoration"] }
    public var text_transform: Any? { values["text_transform"] }
    public var line_height: Double? { values["line_height"] as? Double }
    public var letter_spacing: Double? { values["letter_spacing"] as? Double }
    public var max_lines: Int? { values["max_lines"] as? Int }
    public var text_shadow_color: String? { values["text_shadow_color"] as? String }
    public var text_shadow_offset: Any? { values["text_shadow_offset"] }
    public var text_shadow_radius: Double? { values["text_shadow_radius"] as? Double }
    public var shadow_color: String? { values["shadow_color"] as? String }
    public var shadow_offset: Any? { values["shadow_offset"] }
    public var shadow_opacity: Double? { values["shadow_opacity"] as? Double }
    public var shadow_radius: Double? { values["shadow_radius"] as? Double }
    public var elevation: Double? { values["elevation"] as? Double }
    public var opacity: Double? { values["opacity"] as? Double }
    public var transform: Any? { values["transform"] }
    public var z_index: Int? { values["z_index"] as? Int }
    public var pointer_events: Any? { values["pointer_events"] }
    public var gestures: Any? { values["gestures"] }
    public var hit_slop: Any? { values["hit_slop"] }
    public var on_layout: Any? { values["on_layout"] }
    public var accessibility_label: Any? { values["accessibility_label"] }
    public var accessibility_hint: Any? { values["accessibility_hint"] }
    public var accessibility_role: Any? { values["accessibility_role"] }
    public var accessible: Any? { values["accessible"] }
    public var accessibility_state: Any? { values["accessibility_state"] }
    public var accessibility_live_region: Any? { values["accessibility_live_region"] }
    public var test_id: Any? { values["test_id"] }
    public var ref: Any? { values["ref"] }
    public var keys: Any? { values["keys"] }
    public var revision: Int? { values["revision"] as? Int }
    public var count: Int? { values["count"] as? Int }
    public var estimated_item_size: Double? { values["estimated_item_size"] as? Double }
    public var on_bind_row: Any? { values["on_bind_row"] }
}

public struct WebViewProps {
    public let values: [String: Any]
    public init(_ values: [String: Any]) throws {
        self.values = values
    }
    public var width: Any? { values["width"] }
    public var height: Any? { values["height"] }
    public var min_width: Any? { values["min_width"] }
    public var max_width: Any? { values["max_width"] }
    public var min_height: Any? { values["min_height"] }
    public var max_height: Any? { values["max_height"] }
    public var aspect_ratio: Double? { values["aspect_ratio"] as? Double }
    public var flex: Double? { values["flex"] as? Double }
    public var flex_grow: Double? { values["flex_grow"] as? Double }
    public var flex_shrink: Double? { values["flex_shrink"] as? Double }
    public var flex_basis: Any? { values["flex_basis"] }
    public var flex_direction: Any? { values["flex_direction"] }
    public var flex_wrap: Any? { values["flex_wrap"] }
    public var justify_content: Any? { values["justify_content"] }
    public var align_items: Any? { values["align_items"] }
    public var align_self: Any? { values["align_self"] }
    public var align_content: Any? { values["align_content"] }
    public var direction: Any? { values["direction"] }
    public var display: Any? { values["display"] }
    public var position: Any? { values["position"] }
    public var top: Any? { values["top"] }
    public var right: Any? { values["right"] }
    public var bottom: Any? { values["bottom"] }
    public var left: Any? { values["left"] }
    public var start: Any? { values["start"] }
    public var end: Any? { values["end"] }
    public var padding: Any? { values["padding"] }
    public var padding_top: Any? { values["padding_top"] }
    public var padding_bottom: Any? { values["padding_bottom"] }
    public var padding_left: Any? { values["padding_left"] }
    public var padding_right: Any? { values["padding_right"] }
    public var padding_start: Any? { values["padding_start"] }
    public var padding_end: Any? { values["padding_end"] }
    public var padding_horizontal: Any? { values["padding_horizontal"] }
    public var padding_vertical: Any? { values["padding_vertical"] }
    public var margin: Any? { values["margin"] }
    public var margin_top: Any? { values["margin_top"] }
    public var margin_bottom: Any? { values["margin_bottom"] }
    public var margin_left: Any? { values["margin_left"] }
    public var margin_right: Any? { values["margin_right"] }
    public var margin_start: Any? { values["margin_start"] }
    public var margin_end: Any? { values["margin_end"] }
    public var margin_horizontal: Any? { values["margin_horizontal"] }
    public var margin_vertical: Any? { values["margin_vertical"] }
    public var spacing: Double? { values["spacing"] as? Double }
    public var gap: Double? { values["gap"] as? Double }
    public var row_gap: Double? { values["row_gap"] as? Double }
    public var column_gap: Double? { values["column_gap"] as? Double }
    public var overflow: Any? { values["overflow"] }
    public var background_color: String? { values["background_color"] as? String }
    public var color: String? { values["color"] as? String }
    public var border_color: String? { values["border_color"] as? String }
    public var placeholder_color: String? { values["placeholder_color"] as? String }
    public var tint_color: String? { values["tint_color"] as? String }
    public var border_width: Double? { values["border_width"] as? Double }
    public var border_radius: Double? { values["border_radius"] as? Double }
    public var border_top_left_radius: Double? { values["border_top_left_radius"] as? Double }
    public var border_top_right_radius: Double? { values["border_top_right_radius"] as? Double }
    public var border_bottom_left_radius: Double? { values["border_bottom_left_radius"] as? Double }
    public var border_bottom_right_radius: Double? { values["border_bottom_right_radius"] as? Double }
    public var border_top_width: Double? { values["border_top_width"] as? Double }
    public var border_right_width: Double? { values["border_right_width"] as? Double }
    public var border_bottom_width: Double? { values["border_bottom_width"] as? Double }
    public var border_left_width: Double? { values["border_left_width"] as? Double }
    public var border_top_color: String? { values["border_top_color"] as? String }
    public var border_right_color: String? { values["border_right_color"] as? String }
    public var border_bottom_color: String? { values["border_bottom_color"] as? String }
    public var border_left_color: String? { values["border_left_color"] as? String }
    public var font_size: Double? { values["font_size"] as? Double }
    public var font_family: String? { values["font_family"] as? String }
    public var font_weight: Any? { values["font_weight"] }
    public var bold: Bool? { values["bold"] as? Bool }
    public var italic: Bool? { values["italic"] as? Bool }
    public var text_align: Any? { values["text_align"] }
    public var text_decoration: Any? { values["text_decoration"] }
    public var text_transform: Any? { values["text_transform"] }
    public var line_height: Double? { values["line_height"] as? Double }
    public var letter_spacing: Double? { values["letter_spacing"] as? Double }
    public var max_lines: Int? { values["max_lines"] as? Int }
    public var text_shadow_color: String? { values["text_shadow_color"] as? String }
    public var text_shadow_offset: Any? { values["text_shadow_offset"] }
    public var text_shadow_radius: Double? { values["text_shadow_radius"] as? Double }
    public var shadow_color: String? { values["shadow_color"] as? String }
    public var shadow_offset: Any? { values["shadow_offset"] }
    public var shadow_opacity: Double? { values["shadow_opacity"] as? Double }
    public var shadow_radius: Double? { values["shadow_radius"] as? Double }
    public var elevation: Double? { values["elevation"] as? Double }
    public var opacity: Double? { values["opacity"] as? Double }
    public var transform: Any? { values["transform"] }
    public var z_index: Int? { values["z_index"] as? Int }
    public var pointer_events: Any? { values["pointer_events"] }
    public var url: String? { values["url"] as? String }
    public var html: Any? { values["html"] }
    public var on_load: Any? { values["on_load"] }
    public var on_message: Any? { values["on_message"] }
    public var on_navigation_state_change: Any? { values["on_navigation_state_change"] }
    public var inject_javascript: Any? { values["inject_javascript"] }
    public var scroll_enabled: Bool? { values["scroll_enabled"] as? Bool }
    public var ref: Any? { values["ref"] }
    public var on_layout: Any? { values["on_layout"] }
}

public enum NativeDecodeError: Error { case invalid(String) }
