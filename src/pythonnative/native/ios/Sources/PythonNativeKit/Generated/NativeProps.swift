import Foundation
import UIKit

open class PNViewProps {
    public let values: [String: Any]
    public init(_ values: [String: Any]) { self.values = values }
    public var has_width: Bool { values["width"] != nil }
    public private(set) lazy var `width`: PNViewWidth? = { guard let value = values["width"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewWidth.self, value) }()
    public var has_height: Bool { values["height"] != nil }
    public private(set) lazy var `height`: PNViewWidth? = { guard let value = values["height"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewWidth.self, value) }()
    public var has_min_width: Bool { values["min_width"] != nil }
    public private(set) lazy var `min_width`: PNViewWidth? = { guard let value = values["min_width"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewWidth.self, value) }()
    public var has_max_width: Bool { values["max_width"] != nil }
    public private(set) lazy var `max_width`: PNViewWidth? = { guard let value = values["max_width"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewWidth.self, value) }()
    public var has_min_height: Bool { values["min_height"] != nil }
    public private(set) lazy var `min_height`: PNViewWidth? = { guard let value = values["min_height"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewWidth.self, value) }()
    public var has_max_height: Bool { values["max_height"] != nil }
    public private(set) lazy var `max_height`: PNViewWidth? = { guard let value = values["max_height"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewWidth.self, value) }()
    public var has_aspect_ratio: Bool { values["aspect_ratio"] != nil }
    public private(set) lazy var `aspect_ratio`: Double? = { guard let value = values["aspect_ratio"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_flex_grow: Bool { values["flex_grow"] != nil }
    public private(set) lazy var `flex_grow`: Double? = { guard let value = values["flex_grow"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_flex_shrink: Bool { values["flex_shrink"] != nil }
    public private(set) lazy var `flex_shrink`: Double? = { guard let value = values["flex_shrink"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_flex_basis: Bool { values["flex_basis"] != nil }
    public private(set) lazy var `flex_basis`: PNViewWidth? = { guard let value = values["flex_basis"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewWidth.self, value) }()
    public var has_flex_direction: Bool { values["flex_direction"] != nil }
    public private(set) lazy var `flex_direction`: PNViewFlexDirection? = { guard let value = values["flex_direction"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewFlexDirection.self, value) }()
    public var has_flex_wrap: Bool { values["flex_wrap"] != nil }
    public private(set) lazy var `flex_wrap`: PNViewFlexWrap? = { guard let value = values["flex_wrap"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewFlexWrap.self, value) }()
    public var has_justify_content: Bool { values["justify_content"] != nil }
    public private(set) lazy var `justify_content`: PNViewJustifyContent? = { guard let value = values["justify_content"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewJustifyContent.self, value) }()
    public var has_align_items: Bool { values["align_items"] != nil }
    public private(set) lazy var `align_items`: PNViewAlignItems? = { guard let value = values["align_items"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewAlignItems.self, value) }()
    public var has_align_self: Bool { values["align_self"] != nil }
    public private(set) lazy var `align_self`: PNViewAlignItems? = { guard let value = values["align_self"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewAlignItems.self, value) }()
    public var has_align_content: Bool { values["align_content"] != nil }
    public private(set) lazy var `align_content`: PNViewAlignContent? = { guard let value = values["align_content"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewAlignContent.self, value) }()
    public var has_direction: Bool { values["direction"] != nil }
    public private(set) lazy var `direction`: PNViewDirection? = { guard let value = values["direction"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewDirection.self, value) }()
    public var has_display: Bool { values["display"] != nil }
    public private(set) lazy var `display`: PNViewDisplay? = { guard let value = values["display"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewDisplay.self, value) }()
    public var has_position: Bool { values["position"] != nil }
    public private(set) lazy var `position`: PNViewPosition? = { guard let value = values["position"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewPosition.self, value) }()
    public var has_top: Bool { values["top"] != nil }
    public private(set) lazy var `top`: PNViewWidth? = { guard let value = values["top"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewWidth.self, value) }()
    public var has_right: Bool { values["right"] != nil }
    public private(set) lazy var `right`: PNViewWidth? = { guard let value = values["right"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewWidth.self, value) }()
    public var has_bottom: Bool { values["bottom"] != nil }
    public private(set) lazy var `bottom`: PNViewWidth? = { guard let value = values["bottom"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewWidth.self, value) }()
    public var has_left: Bool { values["left"] != nil }
    public private(set) lazy var `left`: PNViewWidth? = { guard let value = values["left"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewWidth.self, value) }()
    public var has_start: Bool { values["start"] != nil }
    public private(set) lazy var `start`: PNViewWidth? = { guard let value = values["start"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewWidth.self, value) }()
    public var has_end: Bool { values["end"] != nil }
    public private(set) lazy var `end`: PNViewWidth? = { guard let value = values["end"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewWidth.self, value) }()
    public var has_padding: Bool { values["padding"] != nil }
    public private(set) lazy var `padding`: PNViewPadding? = { guard let value = values["padding"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewPadding.self, value) }()
    public var has_padding_top: Bool { values["padding_top"] != nil }
    public private(set) lazy var `padding_top`: PNViewWidth? = { guard let value = values["padding_top"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewWidth.self, value) }()
    public var has_padding_bottom: Bool { values["padding_bottom"] != nil }
    public private(set) lazy var `padding_bottom`: PNViewWidth? = { guard let value = values["padding_bottom"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewWidth.self, value) }()
    public var has_padding_left: Bool { values["padding_left"] != nil }
    public private(set) lazy var `padding_left`: PNViewWidth? = { guard let value = values["padding_left"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewWidth.self, value) }()
    public var has_padding_right: Bool { values["padding_right"] != nil }
    public private(set) lazy var `padding_right`: PNViewWidth? = { guard let value = values["padding_right"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewWidth.self, value) }()
    public var has_padding_start: Bool { values["padding_start"] != nil }
    public private(set) lazy var `padding_start`: PNViewWidth? = { guard let value = values["padding_start"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewWidth.self, value) }()
    public var has_padding_end: Bool { values["padding_end"] != nil }
    public private(set) lazy var `padding_end`: PNViewWidth? = { guard let value = values["padding_end"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewWidth.self, value) }()
    public var has_padding_horizontal: Bool { values["padding_horizontal"] != nil }
    public private(set) lazy var `padding_horizontal`: PNViewWidth? = { guard let value = values["padding_horizontal"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewWidth.self, value) }()
    public var has_padding_vertical: Bool { values["padding_vertical"] != nil }
    public private(set) lazy var `padding_vertical`: PNViewWidth? = { guard let value = values["padding_vertical"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewWidth.self, value) }()
    public var has_margin: Bool { values["margin"] != nil }
    public private(set) lazy var `margin`: PNViewMargin? = { guard let value = values["margin"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewMargin.self, value) }()
    public var has_margin_top: Bool { values["margin_top"] != nil }
    public private(set) lazy var `margin_top`: PNViewMarginTop? = { guard let value = values["margin_top"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewMarginTop.self, value) }()
    public var has_margin_bottom: Bool { values["margin_bottom"] != nil }
    public private(set) lazy var `margin_bottom`: PNViewMarginTop? = { guard let value = values["margin_bottom"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewMarginTop.self, value) }()
    public var has_margin_left: Bool { values["margin_left"] != nil }
    public private(set) lazy var `margin_left`: PNViewMarginTop? = { guard let value = values["margin_left"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewMarginTop.self, value) }()
    public var has_margin_right: Bool { values["margin_right"] != nil }
    public private(set) lazy var `margin_right`: PNViewMarginTop? = { guard let value = values["margin_right"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewMarginTop.self, value) }()
    public var has_margin_start: Bool { values["margin_start"] != nil }
    public private(set) lazy var `margin_start`: PNViewMarginTop? = { guard let value = values["margin_start"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewMarginTop.self, value) }()
    public var has_margin_end: Bool { values["margin_end"] != nil }
    public private(set) lazy var `margin_end`: PNViewMarginTop? = { guard let value = values["margin_end"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewMarginTop.self, value) }()
    public var has_margin_horizontal: Bool { values["margin_horizontal"] != nil }
    public private(set) lazy var `margin_horizontal`: PNViewMarginTop? = { guard let value = values["margin_horizontal"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewMarginTop.self, value) }()
    public var has_margin_vertical: Bool { values["margin_vertical"] != nil }
    public private(set) lazy var `margin_vertical`: PNViewMarginTop? = { guard let value = values["margin_vertical"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewMarginTop.self, value) }()
    public var has_spacing: Bool { values["spacing"] != nil }
    public private(set) lazy var `spacing`: Double? = { guard let value = values["spacing"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_gap: Bool { values["gap"] != nil }
    public private(set) lazy var `gap`: Double? = { guard let value = values["gap"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_row_gap: Bool { values["row_gap"] != nil }
    public private(set) lazy var `row_gap`: Double? = { guard let value = values["row_gap"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_column_gap: Bool { values["column_gap"] != nil }
    public private(set) lazy var `column_gap`: Double? = { guard let value = values["column_gap"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_overflow: Bool { values["overflow"] != nil }
    public private(set) lazy var `overflow`: PNViewOverflow? = { guard let value = values["overflow"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewOverflow.self, value) }()
    public var has_border_color: Bool { values["border_color"] != nil }
    public private(set) lazy var `border_color`: PNViewBorderColor? = { guard let value = values["border_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_border_width: Bool { values["border_width"] != nil }
    public private(set) lazy var `border_width`: Double? = { guard let value = values["border_width"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_border_style: Bool { values["border_style"] != nil }
    public private(set) lazy var `border_style`: PNViewBorderStyle? = { guard let value = values["border_style"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderStyle.self, value) }()
    public var has_border_radius: Bool { values["border_radius"] != nil }
    public private(set) lazy var `border_radius`: Double? = { guard let value = values["border_radius"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_border_top_left_radius: Bool { values["border_top_left_radius"] != nil }
    public private(set) lazy var `border_top_left_radius`: Double? = { guard let value = values["border_top_left_radius"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_border_top_right_radius: Bool { values["border_top_right_radius"] != nil }
    public private(set) lazy var `border_top_right_radius`: Double? = { guard let value = values["border_top_right_radius"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_border_bottom_left_radius: Bool { values["border_bottom_left_radius"] != nil }
    public private(set) lazy var `border_bottom_left_radius`: Double? = { guard let value = values["border_bottom_left_radius"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_border_bottom_right_radius: Bool { values["border_bottom_right_radius"] != nil }
    public private(set) lazy var `border_bottom_right_radius`: Double? = { guard let value = values["border_bottom_right_radius"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_border_top_width: Bool { values["border_top_width"] != nil }
    public private(set) lazy var `border_top_width`: Double? = { guard let value = values["border_top_width"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_border_right_width: Bool { values["border_right_width"] != nil }
    public private(set) lazy var `border_right_width`: Double? = { guard let value = values["border_right_width"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_border_bottom_width: Bool { values["border_bottom_width"] != nil }
    public private(set) lazy var `border_bottom_width`: Double? = { guard let value = values["border_bottom_width"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_border_left_width: Bool { values["border_left_width"] != nil }
    public private(set) lazy var `border_left_width`: Double? = { guard let value = values["border_left_width"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_border_top_color: Bool { values["border_top_color"] != nil }
    public private(set) lazy var `border_top_color`: PNViewBorderColor? = { guard let value = values["border_top_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_border_right_color: Bool { values["border_right_color"] != nil }
    public private(set) lazy var `border_right_color`: PNViewBorderColor? = { guard let value = values["border_right_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_border_bottom_color: Bool { values["border_bottom_color"] != nil }
    public private(set) lazy var `border_bottom_color`: PNViewBorderColor? = { guard let value = values["border_bottom_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_border_left_color: Bool { values["border_left_color"] != nil }
    public private(set) lazy var `border_left_color`: PNViewBorderColor? = { guard let value = values["border_left_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_font_size: Bool { values["font_size"] != nil }
    public private(set) lazy var `font_size`: Double? = { guard let value = values["font_size"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_font_family: Bool { values["font_family"] != nil }
    public private(set) lazy var `font_family`: String? = { guard let value = values["font_family"], !(value is NSNull) else { return nil }; return try! PNValues.decode(String.self, value) }()
    public var has_font_weight: Bool { values["font_weight"] != nil }
    public private(set) lazy var `font_weight`: PNViewFontWeight? = { guard let value = values["font_weight"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewFontWeight.self, value) }()
    public var has_bold: Bool { values["bold"] != nil }
    public private(set) lazy var `bold`: Bool? = { guard let value = values["bold"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_italic: Bool { values["italic"] != nil }
    public private(set) lazy var `italic`: Bool? = { guard let value = values["italic"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_text_align: Bool { values["text_align"] != nil }
    public private(set) lazy var `text_align`: PNViewTextAlign? = { guard let value = values["text_align"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewTextAlign.self, value) }()
    public var has_text_decoration: Bool { values["text_decoration"] != nil }
    public private(set) lazy var `text_decoration`: PNViewTextDecoration? = { guard let value = values["text_decoration"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewTextDecoration.self, value) }()
    public var has_text_transform: Bool { values["text_transform"] != nil }
    public private(set) lazy var `text_transform`: PNViewTextTransform? = { guard let value = values["text_transform"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewTextTransform.self, value) }()
    public var has_line_height: Bool { values["line_height"] != nil }
    public private(set) lazy var `line_height`: Double? = { guard let value = values["line_height"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_letter_spacing: Bool { values["letter_spacing"] != nil }
    public private(set) lazy var `letter_spacing`: Double? = { guard let value = values["letter_spacing"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_max_lines: Bool { values["max_lines"] != nil }
    public private(set) lazy var `max_lines`: Int64? = { guard let value = values["max_lines"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Int64.self, value) }()
    public var has_text_shadow_color: Bool { values["text_shadow_color"] != nil }
    public private(set) lazy var `text_shadow_color`: PNViewBorderColor? = { guard let value = values["text_shadow_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_text_shadow_offset: Bool { values["text_shadow_offset"] != nil }
    public private(set) lazy var `text_shadow_offset`: PNViewTextShadowOffset? = { guard let value = values["text_shadow_offset"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewTextShadowOffset.self, value) }()
    public var has_text_shadow_radius: Bool { values["text_shadow_radius"] != nil }
    public private(set) lazy var `text_shadow_radius`: Double? = { guard let value = values["text_shadow_radius"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_shadow_color: Bool { values["shadow_color"] != nil }
    public private(set) lazy var `shadow_color`: PNViewBorderColor? = { guard let value = values["shadow_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_shadow_offset: Bool { values["shadow_offset"] != nil }
    public private(set) lazy var `shadow_offset`: PNViewTextShadowOffset? = { guard let value = values["shadow_offset"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewTextShadowOffset.self, value) }()
    public var has_shadow_opacity: Bool { values["shadow_opacity"] != nil }
    public private(set) lazy var `shadow_opacity`: Double? = { guard let value = values["shadow_opacity"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_shadow_radius: Bool { values["shadow_radius"] != nil }
    public private(set) lazy var `shadow_radius`: Double? = { guard let value = values["shadow_radius"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_elevation: Bool { values["elevation"] != nil }
    public private(set) lazy var `elevation`: Double? = { guard let value = values["elevation"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_opacity: Bool { values["opacity"] != nil }
    public private(set) lazy var `opacity`: Double? = { guard let value = values["opacity"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_transform: Bool { values["transform"] != nil }
    public private(set) lazy var `transform`: PNViewTransform? = { guard let value = values["transform"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewTransform.self, value) }()
    public var has_z_index: Bool { values["z_index"] != nil }
    public private(set) lazy var `z_index`: Int64? = { guard let value = values["z_index"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Int64.self, value) }()
    public var has_pointer_events: Bool { values["pointer_events"] != nil }
    public private(set) lazy var `pointer_events`: PNViewPointerEvents? = { guard let value = values["pointer_events"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewPointerEvents.self, value) }()
    public var has_gestures: Bool { values["gestures"] != nil }
    public private(set) lazy var `gestures`: [PNJSONValue]? = { guard let value = values["gestures"], !(value is NSNull) else { return nil }; return try! PNValues.decode([PNJSONValue].self, value) }()
    public var has_hit_slop: Bool { values["hit_slop"] != nil }
    public private(set) lazy var `hit_slop`: PNViewHitSlop? = { guard let value = values["hit_slop"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewHitSlop.self, value) }()
    public var has_on_layout: Bool { values["on_layout"] != nil }
    public private(set) lazy var `on_layout`: Bool? = { guard let value = values["on_layout"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_accessibility_label: Bool { values["accessibility_label"] != nil }
    public private(set) lazy var `accessibility_label`: String? = { guard let value = values["accessibility_label"], !(value is NSNull) else { return nil }; return try! PNValues.decode(String.self, value) }()
    public var has_accessibility_hint: Bool { values["accessibility_hint"] != nil }
    public private(set) lazy var `accessibility_hint`: String? = { guard let value = values["accessibility_hint"], !(value is NSNull) else { return nil }; return try! PNValues.decode(String.self, value) }()
    public var has_accessible: Bool { values["accessible"] != nil }
    public private(set) lazy var `accessible`: Bool? = { guard let value = values["accessible"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_accessibility_state: Bool { values["accessibility_state"] != nil }
    public private(set) lazy var `accessibility_state`: PNAccessibilityState? = { guard let value = values["accessibility_state"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNAccessibilityState.self, value) }()
    public var has_accessibility_value: Bool { values["accessibility_value"] != nil }
    public private(set) lazy var `accessibility_value`: PNViewAccessibilityValue? = { guard let value = values["accessibility_value"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewAccessibilityValue.self, value) }()
    public var has_accessibility_actions: Bool { values["accessibility_actions"] != nil }
    public private(set) lazy var `accessibility_actions`: [PNAccessibilityAction]? = { guard let value = values["accessibility_actions"], !(value is NSNull) else { return nil }; return try! PNValues.decode([PNAccessibilityAction].self, value) }()
    public var has_on_accessibility_action: Bool { values["on_accessibility_action"] != nil }
    public private(set) lazy var `on_accessibility_action`: Bool? = { guard let value = values["on_accessibility_action"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_accessibility_live_region: Bool { values["accessibility_live_region"] != nil }
    public private(set) lazy var `accessibility_live_region`: PNViewAccessibilityLiveRegion? = { guard let value = values["accessibility_live_region"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewAccessibilityLiveRegion.self, value) }()
    public var has_important_for_accessibility: Bool { values["important_for_accessibility"] != nil }
    public private(set) lazy var `important_for_accessibility`: PNViewImportantForAccessibility? = { guard let value = values["important_for_accessibility"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewImportantForAccessibility.self, value) }()
    public var has_test_id: Bool { values["test_id"] != nil }
    public private(set) lazy var `test_id`: String? = { guard let value = values["test_id"], !(value is NSNull) else { return nil }; return try! PNValues.decode(String.self, value) }()
    public var has__pn_layout: Bool { values["_pn_layout"] != nil }
    public private(set) lazy var `_pn_layout`: Bool? = { guard let value = values["_pn_layout"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has__pn_events: Bool { values["_pn_events"] != nil }
    public private(set) lazy var `_pn_events`: [String]? = { guard let value = values["_pn_events"], !(value is NSNull) else { return nil }; return try! PNValues.decode([String].self, value) }()
    public var has__pn_animated_events: Bool { values["_pn_animated_events"] != nil }
    public private(set) lazy var `_pn_animated_events`: [String: PNJSONValue]? = { guard let value = values["_pn_animated_events"], !(value is NSNull) else { return nil }; return try! PNValues.decode([String: PNJSONValue].self, value) }()
    public var has__pn_list_key: Bool { values["_pn_list_key"] != nil }
    public private(set) lazy var `_pn_list_key`: String? = { guard let value = values["_pn_list_key"], !(value is NSNull) else { return nil }; return try! PNValues.decode(String.self, value) }()
    public var has__pn_header_slot: Bool { values["_pn_header_slot"] != nil }
    public private(set) lazy var `_pn_header_slot`: PNViewPnHeaderSlot? = { guard let value = values["_pn_header_slot"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewPnHeaderSlot.self, value) }()
    public var has__pn_edit_revision: Bool { values["_pn_edit_revision"] != nil }
    public private(set) lazy var `_pn_edit_revision`: Int64? = { guard let value = values["_pn_edit_revision"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Int64.self, value) }()
}

public final class ActivityIndicatorProps: PNViewProps, PNNativeProps {
    public init(_ values: [String: Any], partial: Bool = true, validated: Bool = false) throws {
        guard validated || PNContracts.validate("ActivityIndicator", partial ? values.filter { !($0.value is NSNull) } : values, partial: partial) else { throw NativeDecodeError.invalid("ActivityIndicator props") }
        super.init(values)
    }
    public var has_flex: Bool { values["flex"] != nil }
    public private(set) lazy var `flex`: Double? = { guard let value = values["flex"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_background_color: Bool { values["background_color"] != nil }
    public private(set) lazy var `background_color`: PNViewBorderColor? = { guard let value = values["background_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_color: Bool { values["color"] != nil }
    public private(set) lazy var `color`: PNActivityIndicatorColor? = { guard let value = values["color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNActivityIndicatorColor.self, value) }()
    public var has_placeholder_color: Bool { values["placeholder_color"] != nil }
    public private(set) lazy var `placeholder_color`: PNViewBorderColor? = { guard let value = values["placeholder_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_tint_color: Bool { values["tint_color"] != nil }
    public private(set) lazy var `tint_color`: PNViewBorderColor? = { guard let value = values["tint_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_animating: Bool { values["animating"] != nil }
    public private(set) lazy var `animating`: Bool? = { guard let value = values["animating"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_size: Bool { values["size"] != nil }
    public private(set) lazy var `size`: PNActivityIndicatorSize? = { guard let value = values["size"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNActivityIndicatorSize.self, value) }()
    public var has_accessibility_role: Bool { values["accessibility_role"] != nil }
    public private(set) lazy var `accessibility_role`: String? = { guard let value = values["accessibility_role"], !(value is NSNull) else { return nil }; return try! PNValues.decode(String.self, value) }()
}

public final class BlurViewProps: PNViewProps, PNNativeProps {
    public init(_ values: [String: Any], partial: Bool = true, validated: Bool = false) throws {
        guard validated || PNContracts.validate("BlurView", partial ? values.filter { !($0.value is NSNull) } : values, partial: partial) else { throw NativeDecodeError.invalid("BlurView props") }
        super.init(values)
    }
    public var has_flex: Bool { values["flex"] != nil }
    public private(set) lazy var `flex`: Double? = { guard let value = values["flex"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_background_color: Bool { values["background_color"] != nil }
    public private(set) lazy var `background_color`: PNViewBorderColor? = { guard let value = values["background_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_color: Bool { values["color"] != nil }
    public private(set) lazy var `color`: PNViewBorderColor? = { guard let value = values["color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_placeholder_color: Bool { values["placeholder_color"] != nil }
    public private(set) lazy var `placeholder_color`: PNViewBorderColor? = { guard let value = values["placeholder_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_tint_color: Bool { values["tint_color"] != nil }
    public private(set) lazy var `tint_color`: PNViewBorderColor? = { guard let value = values["tint_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_blur_type: Bool { values["blur_type"] != nil }
    public private(set) lazy var `blur_type`: PNBlurViewBlurType? = { guard let value = values["blur_type"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNBlurViewBlurType.self, value) }()
    public var has_intensity: Bool { values["intensity"] != nil }
    public private(set) lazy var `intensity`: Double? = { guard let value = values["intensity"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_accessibility_role: Bool { values["accessibility_role"] != nil }
    public private(set) lazy var `accessibility_role`: String? = { guard let value = values["accessibility_role"], !(value is NSNull) else { return nil }; return try! PNValues.decode(String.self, value) }()
}

public final class ButtonProps: PNViewProps, PNNativeProps {
    public init(_ values: [String: Any], partial: Bool = true, validated: Bool = false) throws {
        guard validated || PNContracts.validate("Button", partial ? values.filter { !($0.value is NSNull) } : values, partial: partial) else { throw NativeDecodeError.invalid("Button props") }
        super.init(values)
    }
    public var has_flex: Bool { values["flex"] != nil }
    public private(set) lazy var `flex`: Double? = { guard let value = values["flex"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_background_color: Bool { values["background_color"] != nil }
    public private(set) lazy var `background_color`: PNViewBorderColor? = { guard let value = values["background_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_color: Bool { values["color"] != nil }
    public private(set) lazy var `color`: PNViewBorderColor? = { guard let value = values["color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_placeholder_color: Bool { values["placeholder_color"] != nil }
    public private(set) lazy var `placeholder_color`: PNViewBorderColor? = { guard let value = values["placeholder_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_tint_color: Bool { values["tint_color"] != nil }
    public private(set) lazy var `tint_color`: PNViewBorderColor? = { guard let value = values["tint_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_title: Bool { values["title"] != nil }
    public private(set) lazy var `title`: String? = { guard let value = values["title"], !(value is NSNull) else { return nil }; return try! PNValues.decode(String.self, value) }()
    public var has_on_press: Bool { values["on_press"] != nil }
    public private(set) lazy var `on_press`: Bool? = { guard let value = values["on_press"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_disabled: Bool { values["disabled"] != nil }
    public private(set) lazy var `disabled`: Bool? = { guard let value = values["disabled"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_accessibility_role: Bool { values["accessibility_role"] != nil }
    public private(set) lazy var `accessibility_role`: String? = { guard let value = values["accessibility_role"], !(value is NSNull) else { return nil }; return try! PNValues.decode(String.self, value) }()
}

public final class CheckboxProps: PNViewProps, PNNativeProps {
    public init(_ values: [String: Any], partial: Bool = true, validated: Bool = false) throws {
        guard validated || PNContracts.validate("Checkbox", partial ? values.filter { !($0.value is NSNull) } : values, partial: partial) else { throw NativeDecodeError.invalid("Checkbox props") }
        super.init(values)
    }
    public var has_flex: Bool { values["flex"] != nil }
    public private(set) lazy var `flex`: Double? = { guard let value = values["flex"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_background_color: Bool { values["background_color"] != nil }
    public private(set) lazy var `background_color`: PNViewBorderColor? = { guard let value = values["background_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_color: Bool { values["color"] != nil }
    public private(set) lazy var `color`: PNActivityIndicatorColor? = { guard let value = values["color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNActivityIndicatorColor.self, value) }()
    public var has_placeholder_color: Bool { values["placeholder_color"] != nil }
    public private(set) lazy var `placeholder_color`: PNViewBorderColor? = { guard let value = values["placeholder_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_tint_color: Bool { values["tint_color"] != nil }
    public private(set) lazy var `tint_color`: PNViewBorderColor? = { guard let value = values["tint_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_value: Bool { values["value"] != nil }
    public private(set) lazy var `value`: Bool? = { guard let value = values["value"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_on_change: Bool { values["on_change"] != nil }
    public private(set) lazy var `on_change`: Bool? = { guard let value = values["on_change"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_label: Bool { values["label"] != nil }
    public private(set) lazy var `label`: String? = { guard let value = values["label"], !(value is NSNull) else { return nil }; return try! PNValues.decode(String.self, value) }()
    public var has_disabled: Bool { values["disabled"] != nil }
    public private(set) lazy var `disabled`: Bool? = { guard let value = values["disabled"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_accessibility_role: Bool { values["accessibility_role"] != nil }
    public private(set) lazy var `accessibility_role`: String? = { guard let value = values["accessibility_role"], !(value is NSNull) else { return nil }; return try! PNValues.decode(String.self, value) }()
}

public final class ColumnProps: PNViewProps, PNNativeProps {
    public init(_ values: [String: Any], partial: Bool = true, validated: Bool = false) throws {
        guard validated || PNContracts.validate("Column", partial ? values.filter { !($0.value is NSNull) } : values, partial: partial) else { throw NativeDecodeError.invalid("Column props") }
        super.init(values)
    }
    public var has_flex: Bool { values["flex"] != nil }
    public private(set) lazy var `flex`: Double? = { guard let value = values["flex"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_background_color: Bool { values["background_color"] != nil }
    public private(set) lazy var `background_color`: PNViewBorderColor? = { guard let value = values["background_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_color: Bool { values["color"] != nil }
    public private(set) lazy var `color`: PNViewBorderColor? = { guard let value = values["color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_placeholder_color: Bool { values["placeholder_color"] != nil }
    public private(set) lazy var `placeholder_color`: PNViewBorderColor? = { guard let value = values["placeholder_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_tint_color: Bool { values["tint_color"] != nil }
    public private(set) lazy var `tint_color`: PNViewBorderColor? = { guard let value = values["tint_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_accessibility_role: Bool { values["accessibility_role"] != nil }
    public private(set) lazy var `accessibility_role`: String? = { guard let value = values["accessibility_role"], !(value is NSNull) else { return nil }; return try! PNValues.decode(String.self, value) }()
}

public final class DatePickerProps: PNViewProps, PNNativeProps {
    public init(_ values: [String: Any], partial: Bool = true, validated: Bool = false) throws {
        guard validated || PNContracts.validate("DatePicker", partial ? values.filter { !($0.value is NSNull) } : values, partial: partial) else { throw NativeDecodeError.invalid("DatePicker props") }
        super.init(values)
    }
    public var has_flex: Bool { values["flex"] != nil }
    public private(set) lazy var `flex`: Double? = { guard let value = values["flex"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_background_color: Bool { values["background_color"] != nil }
    public private(set) lazy var `background_color`: PNViewBorderColor? = { guard let value = values["background_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_color: Bool { values["color"] != nil }
    public private(set) lazy var `color`: PNViewBorderColor? = { guard let value = values["color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_placeholder_color: Bool { values["placeholder_color"] != nil }
    public private(set) lazy var `placeholder_color`: PNViewBorderColor? = { guard let value = values["placeholder_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_tint_color: Bool { values["tint_color"] != nil }
    public private(set) lazy var `tint_color`: PNViewBorderColor? = { guard let value = values["tint_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_value: Bool { values["value"] != nil }
    public private(set) lazy var `value`: String? = { guard let value = values["value"], !(value is NSNull) else { return nil }; return try! PNValues.decode(String.self, value) }()
    public var has_mode: Bool { values["mode"] != nil }
    public private(set) lazy var `mode`: PNDatePickerMode? = { guard let value = values["mode"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNDatePickerMode.self, value) }()
    public var has_on_change: Bool { values["on_change"] != nil }
    public private(set) lazy var `on_change`: Bool? = { guard let value = values["on_change"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_minimum: Bool { values["minimum"] != nil }
    public private(set) lazy var `minimum`: String? = { guard let value = values["minimum"], !(value is NSNull) else { return nil }; return try! PNValues.decode(String.self, value) }()
    public var has_maximum: Bool { values["maximum"] != nil }
    public private(set) lazy var `maximum`: String? = { guard let value = values["maximum"], !(value is NSNull) else { return nil }; return try! PNValues.decode(String.self, value) }()
    public var has_disabled: Bool { values["disabled"] != nil }
    public private(set) lazy var `disabled`: Bool? = { guard let value = values["disabled"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_accessibility_role: Bool { values["accessibility_role"] != nil }
    public private(set) lazy var `accessibility_role`: String? = { guard let value = values["accessibility_role"], !(value is NSNull) else { return nil }; return try! PNValues.decode(String.self, value) }()
}

public final class ImageProps: PNViewProps, PNNativeProps {
    public init(_ values: [String: Any], partial: Bool = true, validated: Bool = false) throws {
        guard validated || PNContracts.validate("Image", partial ? values.filter { !($0.value is NSNull) } : values, partial: partial) else { throw NativeDecodeError.invalid("Image props") }
        super.init(values)
    }
    public var has_flex: Bool { values["flex"] != nil }
    public private(set) lazy var `flex`: Double? = { guard let value = values["flex"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_background_color: Bool { values["background_color"] != nil }
    public private(set) lazy var `background_color`: PNViewBorderColor? = { guard let value = values["background_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_color: Bool { values["color"] != nil }
    public private(set) lazy var `color`: PNViewBorderColor? = { guard let value = values["color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_placeholder_color: Bool { values["placeholder_color"] != nil }
    public private(set) lazy var `placeholder_color`: PNActivityIndicatorColor? = { guard let value = values["placeholder_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNActivityIndicatorColor.self, value) }()
    public var has_tint_color: Bool { values["tint_color"] != nil }
    public private(set) lazy var `tint_color`: PNActivityIndicatorColor? = { guard let value = values["tint_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNActivityIndicatorColor.self, value) }()
    public var has_source: Bool { values["source"] != nil }
    public private(set) lazy var `source`: String? = { guard let value = values["source"], !(value is NSNull) else { return nil }; return try! PNValues.decode(String.self, value) }()
    public var has_default_source: Bool { values["default_source"] != nil }
    public private(set) lazy var `default_source`: String? = { guard let value = values["default_source"], !(value is NSNull) else { return nil }; return try! PNValues.decode(String.self, value) }()
    public var has_scale_type: Bool { values["scale_type"] != nil }
    public private(set) lazy var `scale_type`: PNImageScaleType? = { guard let value = values["scale_type"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNImageScaleType.self, value) }()
    public var has_blur_radius: Bool { values["blur_radius"] != nil }
    public private(set) lazy var `blur_radius`: Double? = { guard let value = values["blur_radius"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_on_load_start: Bool { values["on_load_start"] != nil }
    public private(set) lazy var `on_load_start`: Bool? = { guard let value = values["on_load_start"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_on_load: Bool { values["on_load"] != nil }
    public private(set) lazy var `on_load`: Bool? = { guard let value = values["on_load"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_on_load_end: Bool { values["on_load_end"] != nil }
    public private(set) lazy var `on_load_end`: Bool? = { guard let value = values["on_load_end"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_on_error: Bool { values["on_error"] != nil }
    public private(set) lazy var `on_error`: Bool? = { guard let value = values["on_error"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_fade_duration: Bool { values["fade_duration"] != nil }
    public private(set) lazy var `fade_duration`: Double? = { guard let value = values["fade_duration"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_headers: Bool { values["headers"] != nil }
    public private(set) lazy var `headers`: [String: String]? = { guard let value = values["headers"], !(value is NSNull) else { return nil }; return try! PNValues.decode([String: String].self, value) }()
    public var has_accessibility_role: Bool { values["accessibility_role"] != nil }
    public private(set) lazy var `accessibility_role`: String? = { guard let value = values["accessibility_role"], !(value is NSNull) else { return nil }; return try! PNValues.decode(String.self, value) }()
}

public final class ImageBackgroundProps: PNViewProps, PNNativeProps {
    public init(_ values: [String: Any], partial: Bool = true, validated: Bool = false) throws {
        guard validated || PNContracts.validate("ImageBackground", partial ? values.filter { !($0.value is NSNull) } : values, partial: partial) else { throw NativeDecodeError.invalid("ImageBackground props") }
        super.init(values)
    }
    public var has_flex: Bool { values["flex"] != nil }
    public private(set) lazy var `flex`: Double? = { guard let value = values["flex"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_background_color: Bool { values["background_color"] != nil }
    public private(set) lazy var `background_color`: PNViewBorderColor? = { guard let value = values["background_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_color: Bool { values["color"] != nil }
    public private(set) lazy var `color`: PNViewBorderColor? = { guard let value = values["color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_placeholder_color: Bool { values["placeholder_color"] != nil }
    public private(set) lazy var `placeholder_color`: PNViewBorderColor? = { guard let value = values["placeholder_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_tint_color: Bool { values["tint_color"] != nil }
    public private(set) lazy var `tint_color`: PNViewBorderColor? = { guard let value = values["tint_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_source: Bool { values["source"] != nil }
    public private(set) lazy var `source`: String? = { guard let value = values["source"], !(value is NSNull) else { return nil }; return try! PNValues.decode(String.self, value) }()
    public var has_scale_type: Bool { values["scale_type"] != nil }
    public private(set) lazy var `scale_type`: PNImageScaleType? = { guard let value = values["scale_type"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNImageScaleType.self, value) }()
    public var has_accessibility_role: Bool { values["accessibility_role"] != nil }
    public private(set) lazy var `accessibility_role`: String? = { guard let value = values["accessibility_role"], !(value is NSNull) else { return nil }; return try! PNValues.decode(String.self, value) }()
}

public final class KeyboardAvoidingViewProps: PNViewProps, PNNativeProps {
    public init(_ values: [String: Any], partial: Bool = true, validated: Bool = false) throws {
        guard validated || PNContracts.validate("KeyboardAvoidingView", partial ? values.filter { !($0.value is NSNull) } : values, partial: partial) else { throw NativeDecodeError.invalid("KeyboardAvoidingView props") }
        super.init(values)
    }
    public var has_flex: Bool { values["flex"] != nil }
    public private(set) lazy var `flex`: Double? = { guard let value = values["flex"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_background_color: Bool { values["background_color"] != nil }
    public private(set) lazy var `background_color`: PNViewBorderColor? = { guard let value = values["background_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_color: Bool { values["color"] != nil }
    public private(set) lazy var `color`: PNViewBorderColor? = { guard let value = values["color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_placeholder_color: Bool { values["placeholder_color"] != nil }
    public private(set) lazy var `placeholder_color`: PNViewBorderColor? = { guard let value = values["placeholder_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_tint_color: Bool { values["tint_color"] != nil }
    public private(set) lazy var `tint_color`: PNViewBorderColor? = { guard let value = values["tint_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_behavior: Bool { values["behavior"] != nil }
    public private(set) lazy var `behavior`: PNKeyboardAvoidingViewBehavior? = { guard let value = values["behavior"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNKeyboardAvoidingViewBehavior.self, value) }()
    public var has_keyboard_vertical_offset: Bool { values["keyboard_vertical_offset"] != nil }
    public private(set) lazy var `keyboard_vertical_offset`: Double? = { guard let value = values["keyboard_vertical_offset"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_accessibility_role: Bool { values["accessibility_role"] != nil }
    public private(set) lazy var `accessibility_role`: String? = { guard let value = values["accessibility_role"], !(value is NSNull) else { return nil }; return try! PNValues.decode(String.self, value) }()
}

public final class LinearGradientProps: PNViewProps, PNNativeProps {
    public init(_ values: [String: Any], partial: Bool = true, validated: Bool = false) throws {
        guard validated || PNContracts.validate("LinearGradient", partial ? values.filter { !($0.value is NSNull) } : values, partial: partial) else { throw NativeDecodeError.invalid("LinearGradient props") }
        super.init(values)
    }
    public var has_flex: Bool { values["flex"] != nil }
    public private(set) lazy var `flex`: Double? = { guard let value = values["flex"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_background_color: Bool { values["background_color"] != nil }
    public private(set) lazy var `background_color`: PNViewBorderColor? = { guard let value = values["background_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_color: Bool { values["color"] != nil }
    public private(set) lazy var `color`: PNViewBorderColor? = { guard let value = values["color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_placeholder_color: Bool { values["placeholder_color"] != nil }
    public private(set) lazy var `placeholder_color`: PNViewBorderColor? = { guard let value = values["placeholder_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_tint_color: Bool { values["tint_color"] != nil }
    public private(set) lazy var `tint_color`: PNViewBorderColor? = { guard let value = values["tint_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_colors: Bool { values["colors"] != nil }
    public private(set) lazy var `colors`: [PNViewBorderColor]? = { guard let value = values["colors"], !(value is NSNull) else { return nil }; return try! PNValues.decode([PNViewBorderColor].self, value) }()
    public var has_locations: Bool { values["locations"] != nil }
    public private(set) lazy var `locations`: [Double]? = { guard let value = values["locations"], !(value is NSNull) else { return nil }; return try! PNValues.decode([Double].self, value) }()
    public var has_start_point: Bool { values["start_point"] != nil }
    public private(set) lazy var `start_point`: PNPNViewTextShadowOffset1? = { guard let value = values["start_point"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNPNViewTextShadowOffset1.self, value) }()
    public var has_end_point: Bool { values["end_point"] != nil }
    public private(set) lazy var `end_point`: PNPNViewTextShadowOffset1? = { guard let value = values["end_point"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNPNViewTextShadowOffset1.self, value) }()
    public var has_accessibility_role: Bool { values["accessibility_role"] != nil }
    public private(set) lazy var `accessibility_role`: String? = { guard let value = values["accessibility_role"], !(value is NSNull) else { return nil }; return try! PNValues.decode(String.self, value) }()
}

public final class ModalProps: PNViewProps, PNNativeProps {
    public init(_ values: [String: Any], partial: Bool = true, validated: Bool = false) throws {
        guard validated || PNContracts.validate("Modal", partial ? values.filter { !($0.value is NSNull) } : values, partial: partial) else { throw NativeDecodeError.invalid("Modal props") }
        super.init(values)
    }
    public var has_flex: Bool { values["flex"] != nil }
    public private(set) lazy var `flex`: Double? = { guard let value = values["flex"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_background_color: Bool { values["background_color"] != nil }
    public private(set) lazy var `background_color`: PNViewBorderColor? = { guard let value = values["background_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_color: Bool { values["color"] != nil }
    public private(set) lazy var `color`: PNViewBorderColor? = { guard let value = values["color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_placeholder_color: Bool { values["placeholder_color"] != nil }
    public private(set) lazy var `placeholder_color`: PNViewBorderColor? = { guard let value = values["placeholder_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_tint_color: Bool { values["tint_color"] != nil }
    public private(set) lazy var `tint_color`: PNViewBorderColor? = { guard let value = values["tint_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_visible: Bool { values["visible"] != nil }
    public private(set) lazy var `visible`: Bool? = { guard let value = values["visible"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_on_dismiss: Bool { values["on_dismiss"] != nil }
    public private(set) lazy var `on_dismiss`: Bool? = { guard let value = values["on_dismiss"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_on_show: Bool { values["on_show"] != nil }
    public private(set) lazy var `on_show`: Bool? = { guard let value = values["on_show"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_on_request_close: Bool { values["on_request_close"] != nil }
    public private(set) lazy var `on_request_close`: Bool? = { guard let value = values["on_request_close"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_title: Bool { values["title"] != nil }
    public private(set) lazy var `title`: String? = { guard let value = values["title"], !(value is NSNull) else { return nil }; return try! PNValues.decode(String.self, value) }()
    public var has_animation_type: Bool { values["animation_type"] != nil }
    public private(set) lazy var `animation_type`: PNModalAnimationType? = { guard let value = values["animation_type"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNModalAnimationType.self, value) }()
    public var has_transparent: Bool { values["transparent"] != nil }
    public private(set) lazy var `transparent`: Bool? = { guard let value = values["transparent"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_presentation_style: Bool { values["presentation_style"] != nil }
    public private(set) lazy var `presentation_style`: PNModalPresentationStyle? = { guard let value = values["presentation_style"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNModalPresentationStyle.self, value) }()
    public var has_dismiss_on_backdrop: Bool { values["dismiss_on_backdrop"] != nil }
    public private(set) lazy var `dismiss_on_backdrop`: Bool? = { guard let value = values["dismiss_on_backdrop"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_status_bar_translucent: Bool { values["status_bar_translucent"] != nil }
    public private(set) lazy var `status_bar_translucent`: Bool? = { guard let value = values["status_bar_translucent"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_accessibility_role: Bool { values["accessibility_role"] != nil }
    public private(set) lazy var `accessibility_role`: String? = { guard let value = values["accessibility_role"], !(value is NSNull) else { return nil }; return try! PNValues.decode(String.self, value) }()
}

public final class PickerProps: PNViewProps, PNNativeProps {
    public init(_ values: [String: Any], partial: Bool = true, validated: Bool = false) throws {
        guard validated || PNContracts.validate("Picker", partial ? values.filter { !($0.value is NSNull) } : values, partial: partial) else { throw NativeDecodeError.invalid("Picker props") }
        super.init(values)
    }
    public var has_flex: Bool { values["flex"] != nil }
    public private(set) lazy var `flex`: Double? = { guard let value = values["flex"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_background_color: Bool { values["background_color"] != nil }
    public private(set) lazy var `background_color`: PNViewBorderColor? = { guard let value = values["background_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_color: Bool { values["color"] != nil }
    public private(set) lazy var `color`: PNViewBorderColor? = { guard let value = values["color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_placeholder_color: Bool { values["placeholder_color"] != nil }
    public private(set) lazy var `placeholder_color`: PNViewBorderColor? = { guard let value = values["placeholder_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_tint_color: Bool { values["tint_color"] != nil }
    public private(set) lazy var `tint_color`: PNViewBorderColor? = { guard let value = values["tint_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_value: Bool { values["value"] != nil }
    public private(set) lazy var `value`: PNJSONValue? = { guard let value = values["value"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNJSONValue.self, value) }()
    public var has_disabled: Bool { values["disabled"] != nil }
    public private(set) lazy var `disabled`: Bool? = { guard let value = values["disabled"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_items: Bool { values["items"] != nil }
    public private(set) lazy var `items`: [[String: PNJSONValue]]? = { guard let value = values["items"], !(value is NSNull) else { return nil }; return try! PNValues.decode([[String: PNJSONValue]].self, value) }()
    public var has_on_change: Bool { values["on_change"] != nil }
    public private(set) lazy var `on_change`: Bool? = { guard let value = values["on_change"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_placeholder: Bool { values["placeholder"] != nil }
    public private(set) lazy var `placeholder`: String? = { guard let value = values["placeholder"], !(value is NSNull) else { return nil }; return try! PNValues.decode(String.self, value) }()
    public var has_accessibility_role: Bool { values["accessibility_role"] != nil }
    public private(set) lazy var `accessibility_role`: String? = { guard let value = values["accessibility_role"], !(value is NSNull) else { return nil }; return try! PNValues.decode(String.self, value) }()
}

public final class PortalProps: PNViewProps, PNNativeProps {
    public init(_ values: [String: Any], partial: Bool = true, validated: Bool = false) throws {
        guard validated || PNContracts.validate("Portal", partial ? values.filter { !($0.value is NSNull) } : values, partial: partial) else { throw NativeDecodeError.invalid("Portal props") }
        super.init(values)
    }
    public var has_flex: Bool { values["flex"] != nil }
    public private(set) lazy var `flex`: Double? = { guard let value = values["flex"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_background_color: Bool { values["background_color"] != nil }
    public private(set) lazy var `background_color`: PNViewBorderColor? = { guard let value = values["background_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_color: Bool { values["color"] != nil }
    public private(set) lazy var `color`: PNViewBorderColor? = { guard let value = values["color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_placeholder_color: Bool { values["placeholder_color"] != nil }
    public private(set) lazy var `placeholder_color`: PNViewBorderColor? = { guard let value = values["placeholder_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_tint_color: Bool { values["tint_color"] != nil }
    public private(set) lazy var `tint_color`: PNViewBorderColor? = { guard let value = values["tint_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_accessibility_role: Bool { values["accessibility_role"] != nil }
    public private(set) lazy var `accessibility_role`: String? = { guard let value = values["accessibility_role"], !(value is NSNull) else { return nil }; return try! PNValues.decode(String.self, value) }()
}

public final class PressableProps: PNViewProps, PNNativeProps {
    public init(_ values: [String: Any], partial: Bool = true, validated: Bool = false) throws {
        guard validated || PNContracts.validate("Pressable", partial ? values.filter { !($0.value is NSNull) } : values, partial: partial) else { throw NativeDecodeError.invalid("Pressable props") }
        super.init(values)
    }
    public var has_flex: Bool { values["flex"] != nil }
    public private(set) lazy var `flex`: Double? = { guard let value = values["flex"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_background_color: Bool { values["background_color"] != nil }
    public private(set) lazy var `background_color`: PNViewBorderColor? = { guard let value = values["background_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_color: Bool { values["color"] != nil }
    public private(set) lazy var `color`: PNViewBorderColor? = { guard let value = values["color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_placeholder_color: Bool { values["placeholder_color"] != nil }
    public private(set) lazy var `placeholder_color`: PNViewBorderColor? = { guard let value = values["placeholder_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_tint_color: Bool { values["tint_color"] != nil }
    public private(set) lazy var `tint_color`: PNViewBorderColor? = { guard let value = values["tint_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_on_press: Bool { values["on_press"] != nil }
    public private(set) lazy var `on_press`: Bool? = { guard let value = values["on_press"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_on_long_press: Bool { values["on_long_press"] != nil }
    public private(set) lazy var `on_long_press`: Bool? = { guard let value = values["on_long_press"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_on_press_in: Bool { values["on_press_in"] != nil }
    public private(set) lazy var `on_press_in`: Bool? = { guard let value = values["on_press_in"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_on_press_out: Bool { values["on_press_out"] != nil }
    public private(set) lazy var `on_press_out`: Bool? = { guard let value = values["on_press_out"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_disabled: Bool { values["disabled"] != nil }
    public private(set) lazy var `disabled`: Bool? = { guard let value = values["disabled"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_delay_long_press: Bool { values["delay_long_press"] != nil }
    public private(set) lazy var `delay_long_press`: Double? = { guard let value = values["delay_long_press"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_pressed_opacity: Bool { values["pressed_opacity"] != nil }
    public private(set) lazy var `pressed_opacity`: Double? = { guard let value = values["pressed_opacity"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_android_ripple: Bool { values["android_ripple"] != nil }
    public private(set) lazy var `android_ripple`: PNRipple? = { guard let value = values["android_ripple"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNRipple.self, value) }()
    public var has_accessibility_role: Bool { values["accessibility_role"] != nil }
    public private(set) lazy var `accessibility_role`: String? = { guard let value = values["accessibility_role"], !(value is NSNull) else { return nil }; return try! PNValues.decode(String.self, value) }()
}

public final class ProgressBarProps: PNViewProps, PNNativeProps {
    public init(_ values: [String: Any], partial: Bool = true, validated: Bool = false) throws {
        guard validated || PNContracts.validate("ProgressBar", partial ? values.filter { !($0.value is NSNull) } : values, partial: partial) else { throw NativeDecodeError.invalid("ProgressBar props") }
        super.init(values)
    }
    public var has_flex: Bool { values["flex"] != nil }
    public private(set) lazy var `flex`: Double? = { guard let value = values["flex"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_background_color: Bool { values["background_color"] != nil }
    public private(set) lazy var `background_color`: PNViewBorderColor? = { guard let value = values["background_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_color: Bool { values["color"] != nil }
    public private(set) lazy var `color`: PNActivityIndicatorColor? = { guard let value = values["color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNActivityIndicatorColor.self, value) }()
    public var has_placeholder_color: Bool { values["placeholder_color"] != nil }
    public private(set) lazy var `placeholder_color`: PNViewBorderColor? = { guard let value = values["placeholder_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_tint_color: Bool { values["tint_color"] != nil }
    public private(set) lazy var `tint_color`: PNViewBorderColor? = { guard let value = values["tint_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_value: Bool { values["value"] != nil }
    public private(set) lazy var `value`: Double? = { guard let value = values["value"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_track_color: Bool { values["track_color"] != nil }
    public private(set) lazy var `track_color`: PNActivityIndicatorColor? = { guard let value = values["track_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNActivityIndicatorColor.self, value) }()
    public var has_indeterminate: Bool { values["indeterminate"] != nil }
    public private(set) lazy var `indeterminate`: Bool? = { guard let value = values["indeterminate"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_accessibility_role: Bool { values["accessibility_role"] != nil }
    public private(set) lazy var `accessibility_role`: String? = { guard let value = values["accessibility_role"], !(value is NSNull) else { return nil }; return try! PNValues.decode(String.self, value) }()
}

public final class RefreshControlProps: PNViewProps, PNNativeProps {
    public init(_ values: [String: Any], partial: Bool = true, validated: Bool = false) throws {
        guard validated || PNContracts.validate("RefreshControl", partial ? values.filter { !($0.value is NSNull) } : values, partial: partial) else { throw NativeDecodeError.invalid("RefreshControl props") }
        super.init(values)
    }
    public var has_flex: Bool { values["flex"] != nil }
    public private(set) lazy var `flex`: Double? = { guard let value = values["flex"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_background_color: Bool { values["background_color"] != nil }
    public private(set) lazy var `background_color`: PNViewBorderColor? = { guard let value = values["background_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_color: Bool { values["color"] != nil }
    public private(set) lazy var `color`: PNViewBorderColor? = { guard let value = values["color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_placeholder_color: Bool { values["placeholder_color"] != nil }
    public private(set) lazy var `placeholder_color`: PNViewBorderColor? = { guard let value = values["placeholder_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_tint_color: Bool { values["tint_color"] != nil }
    public private(set) lazy var `tint_color`: PNActivityIndicatorColor? = { guard let value = values["tint_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNActivityIndicatorColor.self, value) }()
    public var has_refreshing: Bool { values["refreshing"] != nil }
    public private(set) lazy var `refreshing`: Bool? = { guard let value = values["refreshing"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_on_refresh: Bool { values["on_refresh"] != nil }
    public private(set) lazy var `on_refresh`: Bool? = { guard let value = values["on_refresh"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_accessibility_role: Bool { values["accessibility_role"] != nil }
    public private(set) lazy var `accessibility_role`: String? = { guard let value = values["accessibility_role"], !(value is NSNull) else { return nil }; return try! PNValues.decode(String.self, value) }()
}

public final class RowProps: PNViewProps, PNNativeProps {
    public init(_ values: [String: Any], partial: Bool = true, validated: Bool = false) throws {
        guard validated || PNContracts.validate("Row", partial ? values.filter { !($0.value is NSNull) } : values, partial: partial) else { throw NativeDecodeError.invalid("Row props") }
        super.init(values)
    }
    public var has_flex: Bool { values["flex"] != nil }
    public private(set) lazy var `flex`: Double? = { guard let value = values["flex"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_background_color: Bool { values["background_color"] != nil }
    public private(set) lazy var `background_color`: PNViewBorderColor? = { guard let value = values["background_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_color: Bool { values["color"] != nil }
    public private(set) lazy var `color`: PNViewBorderColor? = { guard let value = values["color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_placeholder_color: Bool { values["placeholder_color"] != nil }
    public private(set) lazy var `placeholder_color`: PNViewBorderColor? = { guard let value = values["placeholder_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_tint_color: Bool { values["tint_color"] != nil }
    public private(set) lazy var `tint_color`: PNViewBorderColor? = { guard let value = values["tint_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_accessibility_role: Bool { values["accessibility_role"] != nil }
    public private(set) lazy var `accessibility_role`: String? = { guard let value = values["accessibility_role"], !(value is NSNull) else { return nil }; return try! PNValues.decode(String.self, value) }()
}

public final class SafeAreaViewProps: PNViewProps, PNNativeProps {
    public init(_ values: [String: Any], partial: Bool = true, validated: Bool = false) throws {
        guard validated || PNContracts.validate("SafeAreaView", partial ? values.filter { !($0.value is NSNull) } : values, partial: partial) else { throw NativeDecodeError.invalid("SafeAreaView props") }
        super.init(values)
    }
    public var has_flex: Bool { values["flex"] != nil }
    public private(set) lazy var `flex`: Double? = { guard let value = values["flex"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_background_color: Bool { values["background_color"] != nil }
    public private(set) lazy var `background_color`: PNViewBorderColor? = { guard let value = values["background_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_color: Bool { values["color"] != nil }
    public private(set) lazy var `color`: PNViewBorderColor? = { guard let value = values["color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_placeholder_color: Bool { values["placeholder_color"] != nil }
    public private(set) lazy var `placeholder_color`: PNViewBorderColor? = { guard let value = values["placeholder_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_tint_color: Bool { values["tint_color"] != nil }
    public private(set) lazy var `tint_color`: PNViewBorderColor? = { guard let value = values["tint_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_edges: Bool { values["edges"] != nil }
    public private(set) lazy var `edges`: [PNSafeAreaViewEdgesItem]? = { guard let value = values["edges"], !(value is NSNull) else { return nil }; return try! PNValues.decode([PNSafeAreaViewEdgesItem].self, value) }()
    public var has_accessibility_role: Bool { values["accessibility_role"] != nil }
    public private(set) lazy var `accessibility_role`: String? = { guard let value = values["accessibility_role"], !(value is NSNull) else { return nil }; return try! PNValues.decode(String.self, value) }()
}

public final class ScreenProps: PNViewProps, PNNativeProps {
    public init(_ values: [String: Any], partial: Bool = true, validated: Bool = false) throws {
        guard validated || PNContracts.validate("Screen", partial ? values.filter { !($0.value is NSNull) } : values, partial: partial) else { throw NativeDecodeError.invalid("Screen props") }
        super.init(values)
    }
    public var has_flex: Bool { values["flex"] != nil }
    public private(set) lazy var `flex`: Double? = { guard let value = values["flex"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_background_color: Bool { values["background_color"] != nil }
    public private(set) lazy var `background_color`: PNViewBorderColor? = { guard let value = values["background_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_color: Bool { values["color"] != nil }
    public private(set) lazy var `color`: PNViewBorderColor? = { guard let value = values["color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_placeholder_color: Bool { values["placeholder_color"] != nil }
    public private(set) lazy var `placeholder_color`: PNViewBorderColor? = { guard let value = values["placeholder_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_tint_color: Bool { values["tint_color"] != nil }
    public private(set) lazy var `tint_color`: PNViewBorderColor? = { guard let value = values["tint_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_accessibility_role: Bool { values["accessibility_role"] != nil }
    public private(set) lazy var `accessibility_role`: String? = { guard let value = values["accessibility_role"], !(value is NSNull) else { return nil }; return try! PNValues.decode(String.self, value) }()
    public var has_route_key: Bool { values["route_key"] != nil }
    public private(set) lazy var `route_key`: String? = { guard let value = values["route_key"], !(value is NSNull) else { return nil }; return try! PNValues.decode(String.self, value) }()
    public var has_title: Bool { values["title"] != nil }
    public private(set) lazy var `title`: String? = { guard let value = values["title"], !(value is NSNull) else { return nil }; return try! PNValues.decode(String.self, value) }()
    public var has_active: Bool { values["active"] != nil }
    public private(set) lazy var `active`: Bool? = { guard let value = values["active"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_options: Bool { values["options"] != nil }
    public private(set) lazy var `options`: [String: PNJSONValue]? = { guard let value = values["options"], !(value is NSNull) else { return nil }; return try! PNValues.decode([String: PNJSONValue].self, value) }()
    public var has_guarded: Bool { values["guarded"] != nil }
    public private(set) lazy var `guarded`: Bool? = { guard let value = values["guarded"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_header_shown: Bool { values["header_shown"] != nil }
    public private(set) lazy var `header_shown`: Bool? = { guard let value = values["header_shown"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_header_large_title: Bool { values["header_large_title"] != nil }
    public private(set) lazy var `header_large_title`: Bool? = { guard let value = values["header_large_title"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_header_back_title: Bool { values["header_back_title"] != nil }
    public private(set) lazy var `header_back_title`: String? = { guard let value = values["header_back_title"], !(value is NSNull) else { return nil }; return try! PNValues.decode(String.self, value) }()
    public var has_header_back_visible: Bool { values["header_back_visible"] != nil }
    public private(set) lazy var `header_back_visible`: Bool? = { guard let value = values["header_back_visible"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_header_tint_color: Bool { values["header_tint_color"] != nil }
    public private(set) lazy var `header_tint_color`: String? = { guard let value = values["header_tint_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(String.self, value) }()
    public var has_header_style: Bool { values["header_style"] != nil }
    public private(set) lazy var `header_style`: [String: PNJSONValue]? = { guard let value = values["header_style"], !(value is NSNull) else { return nil }; return try! PNValues.decode([String: PNJSONValue].self, value) }()
    public var has_header_title_style: Bool { values["header_title_style"] != nil }
    public private(set) lazy var `header_title_style`: [String: PNJSONValue]? = { guard let value = values["header_title_style"], !(value is NSNull) else { return nil }; return try! PNValues.decode([String: PNJSONValue].self, value) }()
    public var has_presentation: Bool { values["presentation"] != nil }
    public private(set) lazy var `presentation`: PNScreenPresentation? = { guard let value = values["presentation"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNScreenPresentation.self, value) }()
    public var has_gesture_enabled: Bool { values["gesture_enabled"] != nil }
    public private(set) lazy var `gesture_enabled`: Bool? = { guard let value = values["gesture_enabled"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_animation: Bool { values["animation"] != nil }
    public private(set) lazy var `animation`: PNScreenAnimation? = { guard let value = values["animation"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNScreenAnimation.self, value) }()
    public var has_tab_bar_badge: Bool { values["tab_bar_badge"] != nil }
    public private(set) lazy var `tab_bar_badge`: PNScreenTabBarBadge? = { guard let value = values["tab_bar_badge"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNScreenTabBarBadge.self, value) }()
    public var has_tab_bar_label: Bool { values["tab_bar_label"] != nil }
    public private(set) lazy var `tab_bar_label`: String? = { guard let value = values["tab_bar_label"], !(value is NSNull) else { return nil }; return try! PNValues.decode(String.self, value) }()
    public var has_lazy: Bool { values["lazy"] != nil }
    public private(set) lazy var `lazy`: Bool? = { guard let value = values["lazy"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_unmount_on_blur: Bool { values["unmount_on_blur"] != nil }
    public private(set) lazy var `unmount_on_blur`: Bool? = { guard let value = values["unmount_on_blur"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
}

public final class ScreenStackProps: PNViewProps, PNNativeProps {
    public init(_ values: [String: Any], partial: Bool = true, validated: Bool = false) throws {
        guard validated || PNContracts.validate("ScreenStack", partial ? values.filter { !($0.value is NSNull) } : values, partial: partial) else { throw NativeDecodeError.invalid("ScreenStack props") }
        super.init(values)
    }
    public var has_flex: Bool { values["flex"] != nil }
    public private(set) lazy var `flex`: Double? = { guard let value = values["flex"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_background_color: Bool { values["background_color"] != nil }
    public private(set) lazy var `background_color`: PNViewBorderColor? = { guard let value = values["background_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_color: Bool { values["color"] != nil }
    public private(set) lazy var `color`: PNViewBorderColor? = { guard let value = values["color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_placeholder_color: Bool { values["placeholder_color"] != nil }
    public private(set) lazy var `placeholder_color`: PNViewBorderColor? = { guard let value = values["placeholder_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_tint_color: Bool { values["tint_color"] != nil }
    public private(set) lazy var `tint_color`: PNViewBorderColor? = { guard let value = values["tint_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_accessibility_role: Bool { values["accessibility_role"] != nil }
    public private(set) lazy var `accessibility_role`: String? = { guard let value = values["accessibility_role"], !(value is NSNull) else { return nil }; return try! PNValues.decode(String.self, value) }()
    public var has_on_native_back: Bool { values["on_native_back"] != nil }
    public private(set) lazy var `on_native_back`: Bool? = { guard let value = values["on_native_back"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
}

public final class ScrollViewProps: PNViewProps, PNNativeProps {
    public init(_ values: [String: Any], partial: Bool = true, validated: Bool = false) throws {
        guard validated || PNContracts.validate("ScrollView", partial ? values.filter { !($0.value is NSNull) } : values, partial: partial) else { throw NativeDecodeError.invalid("ScrollView props") }
        super.init(values)
    }
    public var has_flex: Bool { values["flex"] != nil }
    public private(set) lazy var `flex`: Double? = { guard let value = values["flex"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_background_color: Bool { values["background_color"] != nil }
    public private(set) lazy var `background_color`: PNViewBorderColor? = { guard let value = values["background_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_color: Bool { values["color"] != nil }
    public private(set) lazy var `color`: PNViewBorderColor? = { guard let value = values["color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_placeholder_color: Bool { values["placeholder_color"] != nil }
    public private(set) lazy var `placeholder_color`: PNViewBorderColor? = { guard let value = values["placeholder_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_tint_color: Bool { values["tint_color"] != nil }
    public private(set) lazy var `tint_color`: PNViewBorderColor? = { guard let value = values["tint_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_horizontal: Bool { values["horizontal"] != nil }
    public private(set) lazy var `horizontal`: Bool? = { guard let value = values["horizontal"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_refresh_control: Bool { values["refresh_control"] != nil }
    public private(set) lazy var `refresh_control`: PNScrollViewRefreshControl? = { guard let value = values["refresh_control"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNScrollViewRefreshControl.self, value) }()
    public var has_content_inset: Bool { values["content_inset"] != nil }
    public private(set) lazy var `content_inset`: PNEdgeInsets? = { guard let value = values["content_inset"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNEdgeInsets.self, value) }()
    public var has_scroll_enabled: Bool { values["scroll_enabled"] != nil }
    public private(set) lazy var `scroll_enabled`: Bool? = { guard let value = values["scroll_enabled"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_scroll_event_throttle: Bool { values["scroll_event_throttle"] != nil }
    public private(set) lazy var `scroll_event_throttle`: Double? = { guard let value = values["scroll_event_throttle"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_on_scroll: Bool { values["on_scroll"] != nil }
    public private(set) lazy var `on_scroll`: Bool? = { guard let value = values["on_scroll"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_on_scroll_begin_drag: Bool { values["on_scroll_begin_drag"] != nil }
    public private(set) lazy var `on_scroll_begin_drag`: Bool? = { guard let value = values["on_scroll_begin_drag"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_on_scroll_end_drag: Bool { values["on_scroll_end_drag"] != nil }
    public private(set) lazy var `on_scroll_end_drag`: Bool? = { guard let value = values["on_scroll_end_drag"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_on_momentum_scroll_end: Bool { values["on_momentum_scroll_end"] != nil }
    public private(set) lazy var `on_momentum_scroll_end`: Bool? = { guard let value = values["on_momentum_scroll_end"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_shows_scroll_indicator: Bool { values["shows_scroll_indicator"] != nil }
    public private(set) lazy var `shows_scroll_indicator`: Bool? = { guard let value = values["shows_scroll_indicator"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_paging_enabled: Bool { values["paging_enabled"] != nil }
    public private(set) lazy var `paging_enabled`: Bool? = { guard let value = values["paging_enabled"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_bounces: Bool { values["bounces"] != nil }
    public private(set) lazy var `bounces`: Bool? = { guard let value = values["bounces"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_keyboard_dismiss_mode: Bool { values["keyboard_dismiss_mode"] != nil }
    public private(set) lazy var `keyboard_dismiss_mode`: PNScrollViewKeyboardDismissMode? = { guard let value = values["keyboard_dismiss_mode"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNScrollViewKeyboardDismissMode.self, value) }()
    public var has_keyboard_should_persist_taps: Bool { values["keyboard_should_persist_taps"] != nil }
    public private(set) lazy var `keyboard_should_persist_taps`: PNScrollViewKeyboardShouldPersistTaps? = { guard let value = values["keyboard_should_persist_taps"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNScrollViewKeyboardShouldPersistTaps.self, value) }()
    public var has_snap_to_interval: Bool { values["snap_to_interval"] != nil }
    public private(set) lazy var `snap_to_interval`: Double? = { guard let value = values["snap_to_interval"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_snap_to_alignment: Bool { values["snap_to_alignment"] != nil }
    public private(set) lazy var `snap_to_alignment`: PNScrollViewSnapToAlignment? = { guard let value = values["snap_to_alignment"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNScrollViewSnapToAlignment.self, value) }()
    public var has_deceleration_rate: Bool { values["deceleration_rate"] != nil }
    public private(set) lazy var `deceleration_rate`: PNScrollViewDecelerationRate? = { guard let value = values["deceleration_rate"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNScrollViewDecelerationRate.self, value) }()
    public var has_accessibility_role: Bool { values["accessibility_role"] != nil }
    public private(set) lazy var `accessibility_role`: String? = { guard let value = values["accessibility_role"], !(value is NSNull) else { return nil }; return try! PNValues.decode(String.self, value) }()
}

public final class SegmentedControlProps: PNViewProps, PNNativeProps {
    public init(_ values: [String: Any], partial: Bool = true, validated: Bool = false) throws {
        guard validated || PNContracts.validate("SegmentedControl", partial ? values.filter { !($0.value is NSNull) } : values, partial: partial) else { throw NativeDecodeError.invalid("SegmentedControl props") }
        super.init(values)
    }
    public var has_flex: Bool { values["flex"] != nil }
    public private(set) lazy var `flex`: Double? = { guard let value = values["flex"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_background_color: Bool { values["background_color"] != nil }
    public private(set) lazy var `background_color`: PNViewBorderColor? = { guard let value = values["background_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_color: Bool { values["color"] != nil }
    public private(set) lazy var `color`: PNViewBorderColor? = { guard let value = values["color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_placeholder_color: Bool { values["placeholder_color"] != nil }
    public private(set) lazy var `placeholder_color`: PNViewBorderColor? = { guard let value = values["placeholder_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_tint_color: Bool { values["tint_color"] != nil }
    public private(set) lazy var `tint_color`: PNActivityIndicatorColor? = { guard let value = values["tint_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNActivityIndicatorColor.self, value) }()
    public var has_segments: Bool { values["segments"] != nil }
    public private(set) lazy var `segments`: [String]? = { guard let value = values["segments"], !(value is NSNull) else { return nil }; return try! PNValues.decode([String].self, value) }()
    public var has_selected_index: Bool { values["selected_index"] != nil }
    public private(set) lazy var `selected_index`: Int64? = { guard let value = values["selected_index"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Int64.self, value) }()
    public var has_on_change: Bool { values["on_change"] != nil }
    public private(set) lazy var `on_change`: Bool? = { guard let value = values["on_change"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_disabled: Bool { values["disabled"] != nil }
    public private(set) lazy var `disabled`: Bool? = { guard let value = values["disabled"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_accessibility_role: Bool { values["accessibility_role"] != nil }
    public private(set) lazy var `accessibility_role`: String? = { guard let value = values["accessibility_role"], !(value is NSNull) else { return nil }; return try! PNValues.decode(String.self, value) }()
}

public final class SliderProps: PNViewProps, PNNativeProps {
    public init(_ values: [String: Any], partial: Bool = true, validated: Bool = false) throws {
        guard validated || PNContracts.validate("Slider", partial ? values.filter { !($0.value is NSNull) } : values, partial: partial) else { throw NativeDecodeError.invalid("Slider props") }
        super.init(values)
    }
    public var has_flex: Bool { values["flex"] != nil }
    public private(set) lazy var `flex`: Double? = { guard let value = values["flex"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_background_color: Bool { values["background_color"] != nil }
    public private(set) lazy var `background_color`: PNViewBorderColor? = { guard let value = values["background_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_color: Bool { values["color"] != nil }
    public private(set) lazy var `color`: PNViewBorderColor? = { guard let value = values["color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_placeholder_color: Bool { values["placeholder_color"] != nil }
    public private(set) lazy var `placeholder_color`: PNViewBorderColor? = { guard let value = values["placeholder_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_tint_color: Bool { values["tint_color"] != nil }
    public private(set) lazy var `tint_color`: PNViewBorderColor? = { guard let value = values["tint_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_value: Bool { values["value"] != nil }
    public private(set) lazy var `value`: Double? = { guard let value = values["value"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_min_value: Bool { values["min_value"] != nil }
    public private(set) lazy var `min_value`: Double? = { guard let value = values["min_value"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_max_value: Bool { values["max_value"] != nil }
    public private(set) lazy var `max_value`: Double? = { guard let value = values["max_value"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_on_change: Bool { values["on_change"] != nil }
    public private(set) lazy var `on_change`: Bool? = { guard let value = values["on_change"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_disabled: Bool { values["disabled"] != nil }
    public private(set) lazy var `disabled`: Bool? = { guard let value = values["disabled"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_step: Bool { values["step"] != nil }
    public private(set) lazy var `step`: Double? = { guard let value = values["step"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_minimum_track_color: Bool { values["minimum_track_color"] != nil }
    public private(set) lazy var `minimum_track_color`: PNActivityIndicatorColor? = { guard let value = values["minimum_track_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNActivityIndicatorColor.self, value) }()
    public var has_maximum_track_color: Bool { values["maximum_track_color"] != nil }
    public private(set) lazy var `maximum_track_color`: PNActivityIndicatorColor? = { guard let value = values["maximum_track_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNActivityIndicatorColor.self, value) }()
    public var has_thumb_color: Bool { values["thumb_color"] != nil }
    public private(set) lazy var `thumb_color`: PNActivityIndicatorColor? = { guard let value = values["thumb_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNActivityIndicatorColor.self, value) }()
    public var has_on_sliding_start: Bool { values["on_sliding_start"] != nil }
    public private(set) lazy var `on_sliding_start`: Bool? = { guard let value = values["on_sliding_start"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_on_sliding_complete: Bool { values["on_sliding_complete"] != nil }
    public private(set) lazy var `on_sliding_complete`: Bool? = { guard let value = values["on_sliding_complete"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_accessibility_role: Bool { values["accessibility_role"] != nil }
    public private(set) lazy var `accessibility_role`: String? = { guard let value = values["accessibility_role"], !(value is NSNull) else { return nil }; return try! PNValues.decode(String.self, value) }()
}

public final class SpacerProps: PNViewProps, PNNativeProps {
    public init(_ values: [String: Any], partial: Bool = true, validated: Bool = false) throws {
        guard validated || PNContracts.validate("Spacer", partial ? values.filter { !($0.value is NSNull) } : values, partial: partial) else { throw NativeDecodeError.invalid("Spacer props") }
        super.init(values)
    }
    public var has_flex: Bool { values["flex"] != nil }
    public private(set) lazy var `flex`: Double? = { guard let value = values["flex"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_background_color: Bool { values["background_color"] != nil }
    public private(set) lazy var `background_color`: PNViewBorderColor? = { guard let value = values["background_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_color: Bool { values["color"] != nil }
    public private(set) lazy var `color`: PNViewBorderColor? = { guard let value = values["color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_placeholder_color: Bool { values["placeholder_color"] != nil }
    public private(set) lazy var `placeholder_color`: PNViewBorderColor? = { guard let value = values["placeholder_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_tint_color: Bool { values["tint_color"] != nil }
    public private(set) lazy var `tint_color`: PNViewBorderColor? = { guard let value = values["tint_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_size: Bool { values["size"] != nil }
    public private(set) lazy var `size`: Double? = { guard let value = values["size"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_accessibility_role: Bool { values["accessibility_role"] != nil }
    public private(set) lazy var `accessibility_role`: String? = { guard let value = values["accessibility_role"], !(value is NSNull) else { return nil }; return try! PNValues.decode(String.self, value) }()
}

public final class StatusBarProps: PNViewProps, PNNativeProps {
    public init(_ values: [String: Any], partial: Bool = true, validated: Bool = false) throws {
        guard validated || PNContracts.validate("StatusBar", partial ? values.filter { !($0.value is NSNull) } : values, partial: partial) else { throw NativeDecodeError.invalid("StatusBar props") }
        super.init(values)
    }
    public var has_flex: Bool { values["flex"] != nil }
    public private(set) lazy var `flex`: Double? = { guard let value = values["flex"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_background_color: Bool { values["background_color"] != nil }
    public private(set) lazy var `background_color`: PNActivityIndicatorColor? = { guard let value = values["background_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNActivityIndicatorColor.self, value) }()
    public var has_color: Bool { values["color"] != nil }
    public private(set) lazy var `color`: PNViewBorderColor? = { guard let value = values["color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_placeholder_color: Bool { values["placeholder_color"] != nil }
    public private(set) lazy var `placeholder_color`: PNViewBorderColor? = { guard let value = values["placeholder_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_tint_color: Bool { values["tint_color"] != nil }
    public private(set) lazy var `tint_color`: PNViewBorderColor? = { guard let value = values["tint_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_bar_style: Bool { values["bar_style"] != nil }
    public private(set) lazy var `bar_style`: PNStatusBarBarStyle? = { guard let value = values["bar_style"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNStatusBarBarStyle.self, value) }()
    public var has_hidden: Bool { values["hidden"] != nil }
    public private(set) lazy var `hidden`: Bool? = { guard let value = values["hidden"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_translucent: Bool { values["translucent"] != nil }
    public private(set) lazy var `translucent`: Bool? = { guard let value = values["translucent"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_animated: Bool { values["animated"] != nil }
    public private(set) lazy var `animated`: Bool? = { guard let value = values["animated"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_accessibility_role: Bool { values["accessibility_role"] != nil }
    public private(set) lazy var `accessibility_role`: String? = { guard let value = values["accessibility_role"], !(value is NSNull) else { return nil }; return try! PNValues.decode(String.self, value) }()
}

public final class SvgProps: PNViewProps, PNNativeProps {
    public init(_ values: [String: Any], partial: Bool = true, validated: Bool = false) throws {
        guard validated || PNContracts.validate("Svg", partial ? values.filter { !($0.value is NSNull) } : values, partial: partial) else { throw NativeDecodeError.invalid("Svg props") }
        super.init(values)
    }
    public var has_flex: Bool { values["flex"] != nil }
    public private(set) lazy var `flex`: Double? = { guard let value = values["flex"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_background_color: Bool { values["background_color"] != nil }
    public private(set) lazy var `background_color`: PNViewBorderColor? = { guard let value = values["background_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_color: Bool { values["color"] != nil }
    public private(set) lazy var `color`: PNViewBorderColor? = { guard let value = values["color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_placeholder_color: Bool { values["placeholder_color"] != nil }
    public private(set) lazy var `placeholder_color`: PNViewBorderColor? = { guard let value = values["placeholder_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_tint_color: Bool { values["tint_color"] != nil }
    public private(set) lazy var `tint_color`: PNViewBorderColor? = { guard let value = values["tint_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_shapes: Bool { values["shapes"] != nil }
    public private(set) lazy var `shapes`: [PNSvgShape]? = { guard let value = values["shapes"], !(value is NSNull) else { return nil }; return try! PNValues.decode([PNSvgShape].self, value) }()
    public var has_view_box: Bool { values["view_box"] != nil }
    public private(set) lazy var `view_box`: String? = { guard let value = values["view_box"], !(value is NSNull) else { return nil }; return try! PNValues.decode(String.self, value) }()
    public var has_preserve_aspect_ratio: Bool { values["preserve_aspect_ratio"] != nil }
    public private(set) lazy var `preserve_aspect_ratio`: PNSvgPreserveAspectRatio? = { guard let value = values["preserve_aspect_ratio"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNSvgPreserveAspectRatio.self, value) }()
    public var has_fill: Bool { values["fill"] != nil }
    public private(set) lazy var `fill`: PNActivityIndicatorColor? = { guard let value = values["fill"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNActivityIndicatorColor.self, value) }()
    public var has_stroke: Bool { values["stroke"] != nil }
    public private(set) lazy var `stroke`: PNActivityIndicatorColor? = { guard let value = values["stroke"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNActivityIndicatorColor.self, value) }()
    public var has_stroke_width: Bool { values["stroke_width"] != nil }
    public private(set) lazy var `stroke_width`: Double? = { guard let value = values["stroke_width"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_stroke_linecap: Bool { values["stroke_linecap"] != nil }
    public private(set) lazy var `stroke_linecap`: PNPNSvgShapeStrokeLinecap? = { guard let value = values["stroke_linecap"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNPNSvgShapeStrokeLinecap.self, value) }()
    public var has_stroke_linejoin: Bool { values["stroke_linejoin"] != nil }
    public private(set) lazy var `stroke_linejoin`: PNPNSvgShapeStrokeLinejoin? = { guard let value = values["stroke_linejoin"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNPNSvgShapeStrokeLinejoin.self, value) }()
    public var has_fill_rule: Bool { values["fill_rule"] != nil }
    public private(set) lazy var `fill_rule`: PNPNSvgShapeFillRule? = { guard let value = values["fill_rule"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNPNSvgShapeFillRule.self, value) }()
    public var has_accessibility_role: Bool { values["accessibility_role"] != nil }
    public private(set) lazy var `accessibility_role`: String? = { guard let value = values["accessibility_role"], !(value is NSNull) else { return nil }; return try! PNValues.decode(String.self, value) }()
}

public final class SwitchProps: PNViewProps, PNNativeProps {
    public init(_ values: [String: Any], partial: Bool = true, validated: Bool = false) throws {
        guard validated || PNContracts.validate("Switch", partial ? values.filter { !($0.value is NSNull) } : values, partial: partial) else { throw NativeDecodeError.invalid("Switch props") }
        super.init(values)
    }
    public var has_flex: Bool { values["flex"] != nil }
    public private(set) lazy var `flex`: Double? = { guard let value = values["flex"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_background_color: Bool { values["background_color"] != nil }
    public private(set) lazy var `background_color`: PNViewBorderColor? = { guard let value = values["background_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_color: Bool { values["color"] != nil }
    public private(set) lazy var `color`: PNViewBorderColor? = { guard let value = values["color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_placeholder_color: Bool { values["placeholder_color"] != nil }
    public private(set) lazy var `placeholder_color`: PNViewBorderColor? = { guard let value = values["placeholder_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_tint_color: Bool { values["tint_color"] != nil }
    public private(set) lazy var `tint_color`: PNViewBorderColor? = { guard let value = values["tint_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_value: Bool { values["value"] != nil }
    public private(set) lazy var `value`: Bool? = { guard let value = values["value"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_on_change: Bool { values["on_change"] != nil }
    public private(set) lazy var `on_change`: Bool? = { guard let value = values["on_change"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_disabled: Bool { values["disabled"] != nil }
    public private(set) lazy var `disabled`: Bool? = { guard let value = values["disabled"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_on_tint_color: Bool { values["on_tint_color"] != nil }
    public private(set) lazy var `on_tint_color`: PNActivityIndicatorColor? = { guard let value = values["on_tint_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNActivityIndicatorColor.self, value) }()
    public var has_thumb_color: Bool { values["thumb_color"] != nil }
    public private(set) lazy var `thumb_color`: PNActivityIndicatorColor? = { guard let value = values["thumb_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNActivityIndicatorColor.self, value) }()
    public var has_accessibility_role: Bool { values["accessibility_role"] != nil }
    public private(set) lazy var `accessibility_role`: String? = { guard let value = values["accessibility_role"], !(value is NSNull) else { return nil }; return try! PNValues.decode(String.self, value) }()
}

public final class TabBarProps: PNViewProps, PNNativeProps {
    public init(_ values: [String: Any], partial: Bool = true, validated: Bool = false) throws {
        guard validated || PNContracts.validate("TabBar", partial ? values.filter { !($0.value is NSNull) } : values, partial: partial) else { throw NativeDecodeError.invalid("TabBar props") }
        super.init(values)
    }
    public var has_flex: Bool { values["flex"] != nil }
    public private(set) lazy var `flex`: Double? = { guard let value = values["flex"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_background_color: Bool { values["background_color"] != nil }
    public private(set) lazy var `background_color`: PNViewBorderColor? = { guard let value = values["background_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_color: Bool { values["color"] != nil }
    public private(set) lazy var `color`: PNViewBorderColor? = { guard let value = values["color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_placeholder_color: Bool { values["placeholder_color"] != nil }
    public private(set) lazy var `placeholder_color`: PNViewBorderColor? = { guard let value = values["placeholder_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_tint_color: Bool { values["tint_color"] != nil }
    public private(set) lazy var `tint_color`: String? = { guard let value = values["tint_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(String.self, value) }()
    public var has_accessibility_role: Bool { values["accessibility_role"] != nil }
    public private(set) lazy var `accessibility_role`: String? = { guard let value = values["accessibility_role"], !(value is NSNull) else { return nil }; return try! PNValues.decode(String.self, value) }()
    public var has_items: Bool { values["items"] != nil }
    public private(set) lazy var `items`: [PNTabBarItemsItem]? = { guard let value = values["items"], !(value is NSNull) else { return nil }; return try! PNValues.decode([PNTabBarItemsItem].self, value) }()
    public var has_active_tab: Bool { values["active_tab"] != nil }
    public private(set) lazy var `active_tab`: String? = { guard let value = values["active_tab"], !(value is NSNull) else { return nil }; return try! PNValues.decode(String.self, value) }()
    public var has_on_tab_select: Bool { values["on_tab_select"] != nil }
    public private(set) lazy var `on_tab_select`: Bool? = { guard let value = values["on_tab_select"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_inactive_tint_color: Bool { values["inactive_tint_color"] != nil }
    public private(set) lazy var `inactive_tint_color`: String? = { guard let value = values["inactive_tint_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(String.self, value) }()
    public var has_translucent: Bool { values["translucent"] != nil }
    public private(set) lazy var `translucent`: Bool? = { guard let value = values["translucent"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_shows_labels: Bool { values["shows_labels"] != nil }
    public private(set) lazy var `shows_labels`: Bool? = { guard let value = values["shows_labels"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
}

public final class TextProps: PNViewProps, PNNativeProps {
    public init(_ values: [String: Any], partial: Bool = true, validated: Bool = false) throws {
        guard validated || PNContracts.validate("Text", partial ? values.filter { !($0.value is NSNull) } : values, partial: partial) else { throw NativeDecodeError.invalid("Text props") }
        super.init(values)
    }
    public var has_flex: Bool { values["flex"] != nil }
    public private(set) lazy var `flex`: Double? = { guard let value = values["flex"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_background_color: Bool { values["background_color"] != nil }
    public private(set) lazy var `background_color`: PNViewBorderColor? = { guard let value = values["background_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_color: Bool { values["color"] != nil }
    public private(set) lazy var `color`: PNViewBorderColor? = { guard let value = values["color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_placeholder_color: Bool { values["placeholder_color"] != nil }
    public private(set) lazy var `placeholder_color`: PNViewBorderColor? = { guard let value = values["placeholder_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_tint_color: Bool { values["tint_color"] != nil }
    public private(set) lazy var `tint_color`: PNViewBorderColor? = { guard let value = values["tint_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_on_press: Bool { values["on_press"] != nil }
    public private(set) lazy var `on_press`: Bool? = { guard let value = values["on_press"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_ellipsize_mode: Bool { values["ellipsize_mode"] != nil }
    public private(set) lazy var `ellipsize_mode`: PNTextEllipsizeMode? = { guard let value = values["ellipsize_mode"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNTextEllipsizeMode.self, value) }()
    public var has_selectable: Bool { values["selectable"] != nil }
    public private(set) lazy var `selectable`: Bool? = { guard let value = values["selectable"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_allow_font_scaling: Bool { values["allow_font_scaling"] != nil }
    public private(set) lazy var `allow_font_scaling`: Bool? = { guard let value = values["allow_font_scaling"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_accessibility_role: Bool { values["accessibility_role"] != nil }
    public private(set) lazy var `accessibility_role`: String? = { guard let value = values["accessibility_role"], !(value is NSNull) else { return nil }; return try! PNValues.decode(String.self, value) }()
    public var has_on_span_press: Bool { values["on_span_press"] != nil }
    public private(set) lazy var `on_span_press`: Bool? = { guard let value = values["on_span_press"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_text: Bool { values["text"] != nil }
    public private(set) lazy var `text`: String? = { guard let value = values["text"], !(value is NSNull) else { return nil }; return try! PNValues.decode(String.self, value) }()
    public var has_spans: Bool { values["spans"] != nil }
    public private(set) lazy var `spans`: [PNJSONValue]? = { guard let value = values["spans"], !(value is NSNull) else { return nil }; return try! PNValues.decode([PNJSONValue].self, value) }()
}

public final class TextInputProps: PNViewProps, PNNativeProps {
    public init(_ values: [String: Any], partial: Bool = true, validated: Bool = false) throws {
        guard validated || PNContracts.validate("TextInput", partial ? values.filter { !($0.value is NSNull) } : values, partial: partial) else { throw NativeDecodeError.invalid("TextInput props") }
        super.init(values)
    }
    public var has_flex: Bool { values["flex"] != nil }
    public private(set) lazy var `flex`: Double? = { guard let value = values["flex"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_background_color: Bool { values["background_color"] != nil }
    public private(set) lazy var `background_color`: PNViewBorderColor? = { guard let value = values["background_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_color: Bool { values["color"] != nil }
    public private(set) lazy var `color`: PNViewBorderColor? = { guard let value = values["color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_placeholder_color: Bool { values["placeholder_color"] != nil }
    public private(set) lazy var `placeholder_color`: PNActivityIndicatorColor? = { guard let value = values["placeholder_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNActivityIndicatorColor.self, value) }()
    public var has_tint_color: Bool { values["tint_color"] != nil }
    public private(set) lazy var `tint_color`: PNViewBorderColor? = { guard let value = values["tint_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_value: Bool { values["value"] != nil }
    public private(set) lazy var `value`: String? = { guard let value = values["value"], !(value is NSNull) else { return nil }; return try! PNValues.decode(String.self, value) }()
    public var has_placeholder: Bool { values["placeholder"] != nil }
    public private(set) lazy var `placeholder`: String? = { guard let value = values["placeholder"], !(value is NSNull) else { return nil }; return try! PNValues.decode(String.self, value) }()
    public var has_on_change: Bool { values["on_change"] != nil }
    public private(set) lazy var `on_change`: Bool? = { guard let value = values["on_change"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_on_selection_change: Bool { values["on_selection_change"] != nil }
    public private(set) lazy var `on_selection_change`: Bool? = { guard let value = values["on_selection_change"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_on_submit: Bool { values["on_submit"] != nil }
    public private(set) lazy var `on_submit`: Bool? = { guard let value = values["on_submit"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_on_key_press: Bool { values["on_key_press"] != nil }
    public private(set) lazy var `on_key_press`: Bool? = { guard let value = values["on_key_press"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_on_content_size_change: Bool { values["on_content_size_change"] != nil }
    public private(set) lazy var `on_content_size_change`: Bool? = { guard let value = values["on_content_size_change"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_selection: Bool { values["selection"] != nil }
    public private(set) lazy var `selection`: PNSelection? = { guard let value = values["selection"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNSelection.self, value) }()
    public var has_secure: Bool { values["secure"] != nil }
    public private(set) lazy var `secure`: Bool? = { guard let value = values["secure"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_multiline: Bool { values["multiline"] != nil }
    public private(set) lazy var `multiline`: Bool? = { guard let value = values["multiline"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_keyboard_type: Bool { values["keyboard_type"] != nil }
    public private(set) lazy var `keyboard_type`: PNTextInputKeyboardType? = { guard let value = values["keyboard_type"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNTextInputKeyboardType.self, value) }()
    public var has_keyboard_appearance: Bool { values["keyboard_appearance"] != nil }
    public private(set) lazy var `keyboard_appearance`: PNTextInputKeyboardAppearance? = { guard let value = values["keyboard_appearance"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNTextInputKeyboardAppearance.self, value) }()
    public var has_auto_capitalize: Bool { values["auto_capitalize"] != nil }
    public private(set) lazy var `auto_capitalize`: PNTextInputAutoCapitalize? = { guard let value = values["auto_capitalize"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNTextInputAutoCapitalize.self, value) }()
    public var has_auto_correct: Bool { values["auto_correct"] != nil }
    public private(set) lazy var `auto_correct`: Bool? = { guard let value = values["auto_correct"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_auto_focus: Bool { values["auto_focus"] != nil }
    public private(set) lazy var `auto_focus`: Bool? = { guard let value = values["auto_focus"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_select_text_on_focus: Bool { values["select_text_on_focus"] != nil }
    public private(set) lazy var `select_text_on_focus`: Bool? = { guard let value = values["select_text_on_focus"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_blur_on_submit: Bool { values["blur_on_submit"] != nil }
    public private(set) lazy var `blur_on_submit`: Bool? = { guard let value = values["blur_on_submit"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_return_key_type: Bool { values["return_key_type"] != nil }
    public private(set) lazy var `return_key_type`: PNTextInputReturnKeyType? = { guard let value = values["return_key_type"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNTextInputReturnKeyType.self, value) }()
    public var has_max_length: Bool { values["max_length"] != nil }
    public private(set) lazy var `max_length`: Int64? = { guard let value = values["max_length"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Int64.self, value) }()
    public var has_editable: Bool { values["editable"] != nil }
    public private(set) lazy var `editable`: Bool? = { guard let value = values["editable"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_clear_button: Bool { values["clear_button"] != nil }
    public private(set) lazy var `clear_button`: Bool? = { guard let value = values["clear_button"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_on_focus: Bool { values["on_focus"] != nil }
    public private(set) lazy var `on_focus`: Bool? = { guard let value = values["on_focus"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_on_blur: Bool { values["on_blur"] != nil }
    public private(set) lazy var `on_blur`: Bool? = { guard let value = values["on_blur"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_selection_color: Bool { values["selection_color"] != nil }
    public private(set) lazy var `selection_color`: PNActivityIndicatorColor? = { guard let value = values["selection_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNActivityIndicatorColor.self, value) }()
    public var has_text_content_type: Bool { values["text_content_type"] != nil }
    public private(set) lazy var `text_content_type`: String? = { guard let value = values["text_content_type"], !(value is NSNull) else { return nil }; return try! PNValues.decode(String.self, value) }()
    public var has_accessibility_role: Bool { values["accessibility_role"] != nil }
    public private(set) lazy var `accessibility_role`: String? = { guard let value = values["accessibility_role"], !(value is NSNull) else { return nil }; return try! PNValues.decode(String.self, value) }()
}

public final class TouchableOpacityProps: PNViewProps, PNNativeProps {
    public init(_ values: [String: Any], partial: Bool = true, validated: Bool = false) throws {
        guard validated || PNContracts.validate("TouchableOpacity", partial ? values.filter { !($0.value is NSNull) } : values, partial: partial) else { throw NativeDecodeError.invalid("TouchableOpacity props") }
        super.init(values)
    }
    public var has_flex: Bool { values["flex"] != nil }
    public private(set) lazy var `flex`: Double? = { guard let value = values["flex"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_background_color: Bool { values["background_color"] != nil }
    public private(set) lazy var `background_color`: PNViewBorderColor? = { guard let value = values["background_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_color: Bool { values["color"] != nil }
    public private(set) lazy var `color`: PNViewBorderColor? = { guard let value = values["color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_placeholder_color: Bool { values["placeholder_color"] != nil }
    public private(set) lazy var `placeholder_color`: PNViewBorderColor? = { guard let value = values["placeholder_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_tint_color: Bool { values["tint_color"] != nil }
    public private(set) lazy var `tint_color`: PNViewBorderColor? = { guard let value = values["tint_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_on_press: Bool { values["on_press"] != nil }
    public private(set) lazy var `on_press`: Bool? = { guard let value = values["on_press"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_on_long_press: Bool { values["on_long_press"] != nil }
    public private(set) lazy var `on_long_press`: Bool? = { guard let value = values["on_long_press"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_active_opacity: Bool { values["active_opacity"] != nil }
    public private(set) lazy var `active_opacity`: Double? = { guard let value = values["active_opacity"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_disabled: Bool { values["disabled"] != nil }
    public private(set) lazy var `disabled`: Bool? = { guard let value = values["disabled"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_accessibility_role: Bool { values["accessibility_role"] != nil }
    public private(set) lazy var `accessibility_role`: String? = { guard let value = values["accessibility_role"], !(value is NSNull) else { return nil }; return try! PNValues.decode(String.self, value) }()
}

public final class ViewProps: PNViewProps, PNNativeProps {
    public init(_ values: [String: Any], partial: Bool = true, validated: Bool = false) throws {
        guard validated || PNContracts.validate("View", partial ? values.filter { !($0.value is NSNull) } : values, partial: partial) else { throw NativeDecodeError.invalid("View props") }
        super.init(values)
    }
    public var has_flex: Bool { values["flex"] != nil }
    public private(set) lazy var `flex`: Double? = { guard let value = values["flex"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_background_color: Bool { values["background_color"] != nil }
    public private(set) lazy var `background_color`: PNViewBorderColor? = { guard let value = values["background_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_color: Bool { values["color"] != nil }
    public private(set) lazy var `color`: PNViewBorderColor? = { guard let value = values["color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_placeholder_color: Bool { values["placeholder_color"] != nil }
    public private(set) lazy var `placeholder_color`: PNViewBorderColor? = { guard let value = values["placeholder_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_tint_color: Bool { values["tint_color"] != nil }
    public private(set) lazy var `tint_color`: PNViewBorderColor? = { guard let value = values["tint_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_accessibility_role: Bool { values["accessibility_role"] != nil }
    public private(set) lazy var `accessibility_role`: String? = { guard let value = values["accessibility_role"], !(value is NSNull) else { return nil }; return try! PNValues.decode(String.self, value) }()
}

public final class VirtualListProps: PNViewProps, PNNativeProps {
    public init(_ values: [String: Any], partial: Bool = true, validated: Bool = false) throws {
        guard validated || PNContracts.validate("VirtualList", partial ? values.filter { !($0.value is NSNull) } : values, partial: partial) else { throw NativeDecodeError.invalid("VirtualList props") }
        super.init(values)
    }
    public var has_flex: Bool { values["flex"] != nil }
    public private(set) lazy var `flex`: Double? = { guard let value = values["flex"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_background_color: Bool { values["background_color"] != nil }
    public private(set) lazy var `background_color`: PNViewBorderColor? = { guard let value = values["background_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_color: Bool { values["color"] != nil }
    public private(set) lazy var `color`: PNViewBorderColor? = { guard let value = values["color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_placeholder_color: Bool { values["placeholder_color"] != nil }
    public private(set) lazy var `placeholder_color`: PNViewBorderColor? = { guard let value = values["placeholder_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_tint_color: Bool { values["tint_color"] != nil }
    public private(set) lazy var `tint_color`: PNViewBorderColor? = { guard let value = values["tint_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_accessibility_role: Bool { values["accessibility_role"] != nil }
    public private(set) lazy var `accessibility_role`: String? = { guard let value = values["accessibility_role"], !(value is NSNull) else { return nil }; return try! PNValues.decode(String.self, value) }()
    public var has_dataset: Bool { values["dataset"] != nil }
    public private(set) lazy var `dataset`: PNVirtualListDataset? = { guard let value = values["dataset"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNVirtualListDataset.self, value) }()
    public var has_on_bind_row: Bool { values["on_bind_row"] != nil }
    public private(set) lazy var `on_bind_row`: Bool? = { guard let value = values["on_bind_row"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_on_window: Bool { values["on_window"] != nil }
    public private(set) lazy var `on_window`: Bool? = { guard let value = values["on_window"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_on_scroll: Bool { values["on_scroll"] != nil }
    public private(set) lazy var `on_scroll`: Bool? = { guard let value = values["on_scroll"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_horizontal: Bool { values["horizontal"] != nil }
    public private(set) lazy var `horizontal`: Bool? = { guard let value = values["horizontal"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_shows_scroll_indicator: Bool { values["shows_scroll_indicator"] != nil }
    public private(set) lazy var `shows_scroll_indicator`: Bool? = { guard let value = values["shows_scroll_indicator"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_refresh_control: Bool { values["refresh_control"] != nil }
    public private(set) lazy var `refresh_control`: PNScrollViewRefreshControl? = { guard let value = values["refresh_control"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNScrollViewRefreshControl.self, value) }()
}

public final class WebViewProps: PNViewProps, PNNativeProps {
    public init(_ values: [String: Any], partial: Bool = true, validated: Bool = false) throws {
        guard validated || PNContracts.validate("WebView", partial ? values.filter { !($0.value is NSNull) } : values, partial: partial) else { throw NativeDecodeError.invalid("WebView props") }
        super.init(values)
    }
    public var has_flex: Bool { values["flex"] != nil }
    public private(set) lazy var `flex`: Double? = { guard let value = values["flex"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Double.self, value) }()
    public var has_background_color: Bool { values["background_color"] != nil }
    public private(set) lazy var `background_color`: PNViewBorderColor? = { guard let value = values["background_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_color: Bool { values["color"] != nil }
    public private(set) lazy var `color`: PNViewBorderColor? = { guard let value = values["color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_placeholder_color: Bool { values["placeholder_color"] != nil }
    public private(set) lazy var `placeholder_color`: PNViewBorderColor? = { guard let value = values["placeholder_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_tint_color: Bool { values["tint_color"] != nil }
    public private(set) lazy var `tint_color`: PNViewBorderColor? = { guard let value = values["tint_color"], !(value is NSNull) else { return nil }; return try! PNValues.decode(PNViewBorderColor.self, value) }()
    public var has_url: Bool { values["url"] != nil }
    public private(set) lazy var `url`: String? = { guard let value = values["url"], !(value is NSNull) else { return nil }; return try! PNValues.decode(String.self, value) }()
    public var has_html: Bool { values["html"] != nil }
    public private(set) lazy var `html`: String? = { guard let value = values["html"], !(value is NSNull) else { return nil }; return try! PNValues.decode(String.self, value) }()
    public var has_on_load: Bool { values["on_load"] != nil }
    public private(set) lazy var `on_load`: Bool? = { guard let value = values["on_load"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_on_load_start: Bool { values["on_load_start"] != nil }
    public private(set) lazy var `on_load_start`: Bool? = { guard let value = values["on_load_start"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_on_error: Bool { values["on_error"] != nil }
    public private(set) lazy var `on_error`: Bool? = { guard let value = values["on_error"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_on_message: Bool { values["on_message"] != nil }
    public private(set) lazy var `on_message`: Bool? = { guard let value = values["on_message"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_on_navigation_state_change: Bool { values["on_navigation_state_change"] != nil }
    public private(set) lazy var `on_navigation_state_change`: Bool? = { guard let value = values["on_navigation_state_change"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_inject_javascript: Bool { values["inject_javascript"] != nil }
    public private(set) lazy var `inject_javascript`: String? = { guard let value = values["inject_javascript"], !(value is NSNull) else { return nil }; return try! PNValues.decode(String.self, value) }()
    public var has_scroll_enabled: Bool { values["scroll_enabled"] != nil }
    public private(set) lazy var `scroll_enabled`: Bool? = { guard let value = values["scroll_enabled"], !(value is NSNull) else { return nil }; return try! PNValues.decode(Bool.self, value) }()
    public var has_accessibility_role: Bool { values["accessibility_role"] != nil }
    public private(set) lazy var `accessibility_role`: String? = { guard let value = values["accessibility_role"], !(value is NSNull) else { return nil }; return try! PNValues.decode(String.self, value) }()
}

public enum PNComponentEvents {
    public enum ActivityIndicator {
        @discardableResult public static func `on_layout`(_ view: UIView, _ argument0: PNLayoutEvent) -> String? { PNEvents.emitIfWired(view, "on_layout", [PNValues.encode(argument0)]) }
    }
    public enum BlurView {
        @discardableResult public static func `on_layout`(_ view: UIView, _ argument0: PNLayoutEvent) -> String? { PNEvents.emitIfWired(view, "on_layout", [PNValues.encode(argument0)]) }
    }
    public enum Button {
        @discardableResult public static func `on_press`(_ view: UIView) -> String? { PNEvents.emitIfWired(view, "on_press", []) }
        @discardableResult public static func `on_accessibility_action`(_ view: UIView, _ argument0: String) -> String? { PNEvents.emitIfWired(view, "on_accessibility_action", [PNValues.encode(argument0)]) }
        @discardableResult public static func `on_layout`(_ view: UIView, _ argument0: PNLayoutEvent) -> String? { PNEvents.emitIfWired(view, "on_layout", [PNValues.encode(argument0)]) }
    }
    public enum Checkbox {
        @discardableResult public static func `on_change`(_ view: UIView, _ argument0: Bool) -> String? { PNEvents.emitIfWired(view, "on_change", [PNValues.encode(argument0)]) }
        @discardableResult public static func `on_accessibility_action`(_ view: UIView, _ argument0: String) -> String? { PNEvents.emitIfWired(view, "on_accessibility_action", [PNValues.encode(argument0)]) }
        @discardableResult public static func `on_layout`(_ view: UIView, _ argument0: PNLayoutEvent) -> String? { PNEvents.emitIfWired(view, "on_layout", [PNValues.encode(argument0)]) }
    }
    public enum Column {
        @discardableResult public static func `on_layout`(_ view: UIView, _ argument0: PNLayoutEvent) -> String? { PNEvents.emitIfWired(view, "on_layout", [PNValues.encode(argument0)]) }
        @discardableResult public static func `on_accessibility_action`(_ view: UIView, _ argument0: String) -> String? { PNEvents.emitIfWired(view, "on_accessibility_action", [PNValues.encode(argument0)]) }
    }
    public enum DatePicker {
        @discardableResult public static func `on_change`(_ view: UIView, _ argument0: String) -> String? { PNEvents.emitIfWired(view, "on_change", [PNValues.encode(argument0)]) }
        @discardableResult public static func `on_accessibility_action`(_ view: UIView, _ argument0: String) -> String? { PNEvents.emitIfWired(view, "on_accessibility_action", [PNValues.encode(argument0)]) }
        @discardableResult public static func `on_layout`(_ view: UIView, _ argument0: PNLayoutEvent) -> String? { PNEvents.emitIfWired(view, "on_layout", [PNValues.encode(argument0)]) }
    }
    public enum Image {
        @discardableResult public static func `on_load_start`(_ view: UIView) -> String? { PNEvents.emitIfWired(view, "on_load_start", []) }
        @discardableResult public static func `on_load`(_ view: UIView, _ argument0: PNImageLoadEvent) -> String? { PNEvents.emitIfWired(view, "on_load", [PNValues.encode(argument0)]) }
        @discardableResult public static func `on_load_end`(_ view: UIView) -> String? { PNEvents.emitIfWired(view, "on_load_end", []) }
        @discardableResult public static func `on_error`(_ view: UIView, _ argument0: String) -> String? { PNEvents.emitIfWired(view, "on_error", [PNValues.encode(argument0)]) }
        @discardableResult public static func `on_accessibility_action`(_ view: UIView, _ argument0: String) -> String? { PNEvents.emitIfWired(view, "on_accessibility_action", [PNValues.encode(argument0)]) }
        @discardableResult public static func `on_layout`(_ view: UIView, _ argument0: PNLayoutEvent) -> String? { PNEvents.emitIfWired(view, "on_layout", [PNValues.encode(argument0)]) }
    }
    public enum ImageBackground {
        @discardableResult public static func `on_accessibility_action`(_ view: UIView, _ argument0: String) -> String? { PNEvents.emitIfWired(view, "on_accessibility_action", [PNValues.encode(argument0)]) }
        @discardableResult public static func `on_layout`(_ view: UIView, _ argument0: PNLayoutEvent) -> String? { PNEvents.emitIfWired(view, "on_layout", [PNValues.encode(argument0)]) }
    }
    public enum KeyboardAvoidingView {
        @discardableResult public static func `on_layout`(_ view: UIView, _ argument0: PNLayoutEvent) -> String? { PNEvents.emitIfWired(view, "on_layout", [PNValues.encode(argument0)]) }
    }
    public enum LinearGradient {
        @discardableResult public static func `on_layout`(_ view: UIView, _ argument0: PNLayoutEvent) -> String? { PNEvents.emitIfWired(view, "on_layout", [PNValues.encode(argument0)]) }
    }
    public enum Modal {
        @discardableResult public static func `on_dismiss`(_ view: UIView) -> String? { PNEvents.emitIfWired(view, "on_dismiss", []) }
        @discardableResult public static func `on_show`(_ view: UIView) -> String? { PNEvents.emitIfWired(view, "on_show", []) }
        @discardableResult public static func `on_request_close`(_ view: UIView) -> String? { PNEvents.emitIfWired(view, "on_request_close", []) }
        @discardableResult public static func `on_layout`(_ view: UIView, _ argument0: PNLayoutEvent) -> String? { PNEvents.emitIfWired(view, "on_layout", [PNValues.encode(argument0)]) }
    }
    public enum Picker {
        @discardableResult public static func `on_change`(_ view: UIView, _ argument0: PNJSONValue) -> String? { PNEvents.emitIfWired(view, "on_change", [PNValues.encode(argument0)]) }
        @discardableResult public static func `on_accessibility_action`(_ view: UIView, _ argument0: String) -> String? { PNEvents.emitIfWired(view, "on_accessibility_action", [PNValues.encode(argument0)]) }
        @discardableResult public static func `on_layout`(_ view: UIView, _ argument0: PNLayoutEvent) -> String? { PNEvents.emitIfWired(view, "on_layout", [PNValues.encode(argument0)]) }
    }
    public enum Portal {
        @discardableResult public static func `on_layout`(_ view: UIView, _ argument0: PNLayoutEvent) -> String? { PNEvents.emitIfWired(view, "on_layout", [PNValues.encode(argument0)]) }
    }
    public enum Pressable {
        @discardableResult public static func `on_press`(_ view: UIView) -> String? { PNEvents.emitIfWired(view, "on_press", []) }
        @discardableResult public static func `on_long_press`(_ view: UIView) -> String? { PNEvents.emitIfWired(view, "on_long_press", []) }
        @discardableResult public static func `on_press_in`(_ view: UIView) -> String? { PNEvents.emitIfWired(view, "on_press_in", []) }
        @discardableResult public static func `on_press_out`(_ view: UIView) -> String? { PNEvents.emitIfWired(view, "on_press_out", []) }
        @discardableResult public static func `on_layout`(_ view: UIView, _ argument0: PNLayoutEvent) -> String? { PNEvents.emitIfWired(view, "on_layout", [PNValues.encode(argument0)]) }
        @discardableResult public static func `on_accessibility_action`(_ view: UIView, _ argument0: String) -> String? { PNEvents.emitIfWired(view, "on_accessibility_action", [PNValues.encode(argument0)]) }
    }
    public enum ProgressBar {
        @discardableResult public static func `on_layout`(_ view: UIView, _ argument0: PNLayoutEvent) -> String? { PNEvents.emitIfWired(view, "on_layout", [PNValues.encode(argument0)]) }
    }
    public enum RefreshControl {
        @discardableResult public static func `on_refresh`(_ view: UIView) -> String? { PNEvents.emitIfWired(view, "on_refresh", []) }
        @discardableResult public static func `on_layout`(_ view: UIView, _ argument0: PNLayoutEvent) -> String? { PNEvents.emitIfWired(view, "on_layout", [PNValues.encode(argument0)]) }
    }
    public enum Row {
        @discardableResult public static func `on_layout`(_ view: UIView, _ argument0: PNLayoutEvent) -> String? { PNEvents.emitIfWired(view, "on_layout", [PNValues.encode(argument0)]) }
        @discardableResult public static func `on_accessibility_action`(_ view: UIView, _ argument0: String) -> String? { PNEvents.emitIfWired(view, "on_accessibility_action", [PNValues.encode(argument0)]) }
    }
    public enum SafeAreaView {
        @discardableResult public static func `on_layout`(_ view: UIView, _ argument0: PNLayoutEvent) -> String? { PNEvents.emitIfWired(view, "on_layout", [PNValues.encode(argument0)]) }
    }
    public enum Screen {
        @discardableResult public static func `on_layout`(_ view: UIView, _ argument0: PNLayoutEvent) -> String? { PNEvents.emitIfWired(view, "on_layout", [PNValues.encode(argument0)]) }
        @discardableResult public static func `on_accessibility_action`(_ view: UIView, _ argument0: String) -> String? { PNEvents.emitIfWired(view, "on_accessibility_action", [PNValues.encode(argument0)]) }
    }
    public enum ScreenStack {
        @discardableResult public static func `on_layout`(_ view: UIView, _ argument0: PNLayoutEvent) -> String? { PNEvents.emitIfWired(view, "on_layout", [PNValues.encode(argument0)]) }
        @discardableResult public static func `on_accessibility_action`(_ view: UIView, _ argument0: String) -> String? { PNEvents.emitIfWired(view, "on_accessibility_action", [PNValues.encode(argument0)]) }
        @discardableResult public static func `on_native_back`(_ view: UIView, _ argument0: Int64) -> String? { PNEvents.emitIfWired(view, "on_native_back", [PNValues.encode(argument0)]) }
    }
    public enum ScrollView {
        @discardableResult public static func `on_scroll`(_ view: UIView, _ argument0: PNScrollEvent) -> String? { PNEvents.emitIfWired(view, "on_scroll", [PNValues.encode(argument0)]) }
        @discardableResult public static func `on_scroll_begin_drag`(_ view: UIView, _ argument0: PNScrollEvent) -> String? { PNEvents.emitIfWired(view, "on_scroll_begin_drag", [PNValues.encode(argument0)]) }
        @discardableResult public static func `on_scroll_end_drag`(_ view: UIView, _ argument0: PNScrollEvent) -> String? { PNEvents.emitIfWired(view, "on_scroll_end_drag", [PNValues.encode(argument0)]) }
        @discardableResult public static func `on_momentum_scroll_end`(_ view: UIView, _ argument0: PNScrollEvent) -> String? { PNEvents.emitIfWired(view, "on_momentum_scroll_end", [PNValues.encode(argument0)]) }
        @discardableResult public static func `on_layout`(_ view: UIView, _ argument0: PNLayoutEvent) -> String? { PNEvents.emitIfWired(view, "on_layout", [PNValues.encode(argument0)]) }
        @discardableResult public static func `on_refresh`(_ view: UIView) -> String? { PNEvents.emitIfWired(view, "on_refresh", []) }
    }
    public enum SegmentedControl {
        @discardableResult public static func `on_change`(_ view: UIView, _ argument0: Int64) -> String? { PNEvents.emitIfWired(view, "on_change", [PNValues.encode(argument0)]) }
        @discardableResult public static func `on_accessibility_action`(_ view: UIView, _ argument0: String) -> String? { PNEvents.emitIfWired(view, "on_accessibility_action", [PNValues.encode(argument0)]) }
        @discardableResult public static func `on_layout`(_ view: UIView, _ argument0: PNLayoutEvent) -> String? { PNEvents.emitIfWired(view, "on_layout", [PNValues.encode(argument0)]) }
    }
    public enum Slider {
        @discardableResult public static func `on_change`(_ view: UIView, _ argument0: Double) -> String? { PNEvents.emitIfWired(view, "on_change", [PNValues.encode(argument0)]) }
        @discardableResult public static func `on_sliding_start`(_ view: UIView, _ argument0: Double) -> String? { PNEvents.emitIfWired(view, "on_sliding_start", [PNValues.encode(argument0)]) }
        @discardableResult public static func `on_sliding_complete`(_ view: UIView, _ argument0: Double) -> String? { PNEvents.emitIfWired(view, "on_sliding_complete", [PNValues.encode(argument0)]) }
        @discardableResult public static func `on_layout`(_ view: UIView, _ argument0: PNLayoutEvent) -> String? { PNEvents.emitIfWired(view, "on_layout", [PNValues.encode(argument0)]) }
    }
    public enum Spacer {
        @discardableResult public static func `on_layout`(_ view: UIView, _ argument0: PNLayoutEvent) -> String? { PNEvents.emitIfWired(view, "on_layout", [PNValues.encode(argument0)]) }
    }
    public enum StatusBar {
        @discardableResult public static func `on_layout`(_ view: UIView, _ argument0: PNLayoutEvent) -> String? { PNEvents.emitIfWired(view, "on_layout", [PNValues.encode(argument0)]) }
    }
    public enum Svg {
        @discardableResult public static func `on_accessibility_action`(_ view: UIView, _ argument0: String) -> String? { PNEvents.emitIfWired(view, "on_accessibility_action", [PNValues.encode(argument0)]) }
        @discardableResult public static func `on_layout`(_ view: UIView, _ argument0: PNLayoutEvent) -> String? { PNEvents.emitIfWired(view, "on_layout", [PNValues.encode(argument0)]) }
    }
    public enum Switch {
        @discardableResult public static func `on_change`(_ view: UIView, _ argument0: Bool) -> String? { PNEvents.emitIfWired(view, "on_change", [PNValues.encode(argument0)]) }
        @discardableResult public static func `on_layout`(_ view: UIView, _ argument0: PNLayoutEvent) -> String? { PNEvents.emitIfWired(view, "on_layout", [PNValues.encode(argument0)]) }
    }
    public enum TabBar {
        @discardableResult public static func `on_layout`(_ view: UIView, _ argument0: PNLayoutEvent) -> String? { PNEvents.emitIfWired(view, "on_layout", [PNValues.encode(argument0)]) }
        @discardableResult public static func `on_accessibility_action`(_ view: UIView, _ argument0: String) -> String? { PNEvents.emitIfWired(view, "on_accessibility_action", [PNValues.encode(argument0)]) }
        @discardableResult public static func `on_tab_select`(_ view: UIView, _ argument0: String) -> String? { PNEvents.emitIfWired(view, "on_tab_select", [PNValues.encode(argument0)]) }
    }
    public enum Text {
        @discardableResult public static func `on_press`(_ view: UIView) -> String? { PNEvents.emitIfWired(view, "on_press", []) }
        @discardableResult public static func `on_accessibility_action`(_ view: UIView, _ argument0: String) -> String? { PNEvents.emitIfWired(view, "on_accessibility_action", [PNValues.encode(argument0)]) }
        @discardableResult public static func `on_layout`(_ view: UIView, _ argument0: PNLayoutEvent) -> String? { PNEvents.emitIfWired(view, "on_layout", [PNValues.encode(argument0)]) }
        @discardableResult public static func `on_span_press`(_ view: UIView, _ argument0: Int64) -> String? { PNEvents.emitIfWired(view, "on_span_press", [PNValues.encode(argument0)]) }
    }
    public enum TextInput {
        @discardableResult public static func `on_change`(_ view: UIView, _ argument0: String) -> String? { PNEvents.emitIfWired(view, "on_change", [PNValues.encode(argument0)]) }
        @discardableResult public static func `on_selection_change`(_ view: UIView, _ argument0: PNSelectionEvent) -> String? { PNEvents.emitIfWired(view, "on_selection_change", [PNValues.encode(argument0)]) }
        @discardableResult public static func `on_submit`(_ view: UIView, _ argument0: String) -> String? { PNEvents.emitIfWired(view, "on_submit", [PNValues.encode(argument0)]) }
        @discardableResult public static func `on_key_press`(_ view: UIView, _ argument0: PNKeyPressEvent) -> String? { PNEvents.emitIfWired(view, "on_key_press", [PNValues.encode(argument0)]) }
        @discardableResult public static func `on_content_size_change`(_ view: UIView, _ argument0: PNContentSizeEvent) -> String? { PNEvents.emitIfWired(view, "on_content_size_change", [PNValues.encode(argument0)]) }
        @discardableResult public static func `on_focus`(_ view: UIView) -> String? { PNEvents.emitIfWired(view, "on_focus", []) }
        @discardableResult public static func `on_blur`(_ view: UIView) -> String? { PNEvents.emitIfWired(view, "on_blur", []) }
        @discardableResult public static func `on_accessibility_action`(_ view: UIView, _ argument0: String) -> String? { PNEvents.emitIfWired(view, "on_accessibility_action", [PNValues.encode(argument0)]) }
        @discardableResult public static func `on_layout`(_ view: UIView, _ argument0: PNLayoutEvent) -> String? { PNEvents.emitIfWired(view, "on_layout", [PNValues.encode(argument0)]) }
    }
    public enum TouchableOpacity {
        @discardableResult public static func `on_press`(_ view: UIView) -> String? { PNEvents.emitIfWired(view, "on_press", []) }
        @discardableResult public static func `on_long_press`(_ view: UIView) -> String? { PNEvents.emitIfWired(view, "on_long_press", []) }
        @discardableResult public static func `on_accessibility_action`(_ view: UIView, _ argument0: String) -> String? { PNEvents.emitIfWired(view, "on_accessibility_action", [PNValues.encode(argument0)]) }
        @discardableResult public static func `on_layout`(_ view: UIView, _ argument0: PNLayoutEvent) -> String? { PNEvents.emitIfWired(view, "on_layout", [PNValues.encode(argument0)]) }
    }
    public enum View {
        @discardableResult public static func `on_layout`(_ view: UIView, _ argument0: PNLayoutEvent) -> String? { PNEvents.emitIfWired(view, "on_layout", [PNValues.encode(argument0)]) }
        @discardableResult public static func `on_accessibility_action`(_ view: UIView, _ argument0: String) -> String? { PNEvents.emitIfWired(view, "on_accessibility_action", [PNValues.encode(argument0)]) }
    }
    public enum VirtualList {
        @discardableResult public static func `on_layout`(_ view: UIView, _ argument0: PNLayoutEvent) -> String? { PNEvents.emitIfWired(view, "on_layout", [PNValues.encode(argument0)]) }
        @discardableResult public static func `on_accessibility_action`(_ view: UIView, _ argument0: String) -> String? { PNEvents.emitIfWired(view, "on_accessibility_action", [PNValues.encode(argument0)]) }
        @discardableResult public static func `on_bind_row`(_ view: UIView, _ arguments: [Any?] = []) -> String? { PNEvents.emitIfWired(view, "on_bind_row", arguments) }
        @discardableResult public static func `on_window`(_ view: UIView, _ arguments: [Any?] = []) -> String? { PNEvents.emitIfWired(view, "on_window", arguments) }
        @discardableResult public static func `on_scroll`(_ view: UIView, _ arguments: [Any?] = []) -> String? { PNEvents.emitIfWired(view, "on_scroll", arguments) }
        @discardableResult public static func `on_refresh`(_ view: UIView) -> String? { PNEvents.emitIfWired(view, "on_refresh", []) }
    }
    public enum WebView {
        @discardableResult public static func `on_load`(_ view: UIView, _ argument0: String) -> String? { PNEvents.emitIfWired(view, "on_load", [PNValues.encode(argument0)]) }
        @discardableResult public static func `on_load_start`(_ view: UIView, _ argument0: String) -> String? { PNEvents.emitIfWired(view, "on_load_start", [PNValues.encode(argument0)]) }
        @discardableResult public static func `on_error`(_ view: UIView, _ argument0: String) -> String? { PNEvents.emitIfWired(view, "on_error", [PNValues.encode(argument0)]) }
        @discardableResult public static func `on_message`(_ view: UIView, _ argument0: String) -> String? { PNEvents.emitIfWired(view, "on_message", [PNValues.encode(argument0)]) }
        @discardableResult public static func `on_navigation_state_change`(_ view: UIView, _ argument0: PNWebNavigationEvent) -> String? { PNEvents.emitIfWired(view, "on_navigation_state_change", [PNValues.encode(argument0)]) }
        @discardableResult public static func `on_layout`(_ view: UIView, _ argument0: PNLayoutEvent) -> String? { PNEvents.emitIfWired(view, "on_layout", [PNValues.encode(argument0)]) }
    }
}