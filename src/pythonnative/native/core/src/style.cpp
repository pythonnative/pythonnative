#include "style.h"

#include <cmath>
#include <cstdlib>
#include <string>
#include <unordered_map>

namespace pn {

namespace {

enum class Key : uint8_t {
    Direction, FlexDirection, JustifyContent, AlignItems, AlignSelf, AlignContent, Position, FlexWrap, Display,
    Overflow, Width, Height, MinWidth, MinHeight, MaxWidth, MaxHeight, FlexBasis, Flex, FlexGrow, FlexShrink,
    AspectRatio, Margin, Padding, Border, Inset, Gap,
};

struct Spec {
    Key key;
    int edge;  // YGEdge or YGGutter for edge families, -1 otherwise
};

const std::unordered_map<std::string_view, Spec>& specs() {
    static const std::unordered_map<std::string_view, Spec> table = {
        {"direction", {Key::Direction, -1}},
        {"flex_direction", {Key::FlexDirection, -1}},
        {"justify_content", {Key::JustifyContent, -1}},
        {"align_items", {Key::AlignItems, -1}},
        {"align_self", {Key::AlignSelf, -1}},
        {"align_content", {Key::AlignContent, -1}},
        {"position", {Key::Position, -1}},
        {"flex_wrap", {Key::FlexWrap, -1}},
        {"display", {Key::Display, -1}},
        // `overflow` only clips; Yoga lays out scrolling containers by their contract.
        {"width", {Key::Width, -1}},
        {"height", {Key::Height, -1}},
        {"min_width", {Key::MinWidth, -1}},
        {"min_height", {Key::MinHeight, -1}},
        {"max_width", {Key::MaxWidth, -1}},
        {"max_height", {Key::MaxHeight, -1}},
        {"flex_basis", {Key::FlexBasis, -1}},
        {"flex", {Key::Flex, -1}},
        {"flex_grow", {Key::FlexGrow, -1}},
        {"flex_shrink", {Key::FlexShrink, -1}},
        {"aspect_ratio", {Key::AspectRatio, -1}},
        {"margin_left", {Key::Margin, YGEdgeLeft}},
        {"margin_top", {Key::Margin, YGEdgeTop}},
        {"margin_right", {Key::Margin, YGEdgeRight}},
        {"margin_bottom", {Key::Margin, YGEdgeBottom}},
        {"margin_start", {Key::Margin, YGEdgeStart}},
        {"margin_end", {Key::Margin, YGEdgeEnd}},
        {"margin_horizontal", {Key::Margin, YGEdgeHorizontal}},
        {"margin_vertical", {Key::Margin, YGEdgeVertical}},
        {"margin", {Key::Margin, YGEdgeAll}},
        {"padding_left", {Key::Padding, YGEdgeLeft}},
        {"padding_top", {Key::Padding, YGEdgeTop}},
        {"padding_right", {Key::Padding, YGEdgeRight}},
        {"padding_bottom", {Key::Padding, YGEdgeBottom}},
        {"padding_start", {Key::Padding, YGEdgeStart}},
        {"padding_end", {Key::Padding, YGEdgeEnd}},
        {"padding_horizontal", {Key::Padding, YGEdgeHorizontal}},
        {"padding_vertical", {Key::Padding, YGEdgeVertical}},
        {"padding", {Key::Padding, YGEdgeAll}},
        {"border_left_width", {Key::Border, YGEdgeLeft}},
        {"border_top_width", {Key::Border, YGEdgeTop}},
        {"border_right_width", {Key::Border, YGEdgeRight}},
        {"border_bottom_width", {Key::Border, YGEdgeBottom}},
        {"border_start_width", {Key::Border, YGEdgeStart}},
        {"border_end_width", {Key::Border, YGEdgeEnd}},
        {"border_horizontal_width", {Key::Border, YGEdgeHorizontal}},
        {"border_vertical_width", {Key::Border, YGEdgeVertical}},
        {"border_width", {Key::Border, YGEdgeAll}},
        {"left", {Key::Inset, YGEdgeLeft}},
        {"top", {Key::Inset, YGEdgeTop}},
        {"right", {Key::Inset, YGEdgeRight}},
        {"bottom", {Key::Inset, YGEdgeBottom}},
        {"start", {Key::Inset, YGEdgeStart}},
        {"end", {Key::Inset, YGEdgeEnd}},
        {"gap", {Key::Gap, YGGutterAll}},
        {"row_gap", {Key::Gap, YGGutterRow}},
        {"column_gap", {Key::Gap, YGGutterColumn}},
    };
    return table;
}

/// A dimension: a number, "auto", "N%", or a numeric string.
struct Length {
    enum class Unit : uint8_t { Point, Percent, Auto } unit = Unit::Point;
    float amount = 0;
};

bool length(const Value& value, Length& out, bool allow_auto) {
    if (value.is_number()) {
        out = {Length::Unit::Point, static_cast<float>(value.as_double())};
        return true;
    }
    if (!value.is_string()) return false;
    const std::string& text = value.as_string();
    if (text == "auto") {
        out = {Length::Unit::Auto, 0};
        return allow_auto;
    }
    if (text.empty()) return false;
    char* end = nullptr;
    float amount = std::strtof(text.c_str(), &end);
    if (end == text.c_str()) return false;
    bool percent = text.back() == '%';
    out = {percent ? Length::Unit::Percent : Length::Unit::Point, amount};
    return true;
}

bool number(const Value& value, float& out) {
    Length parsed;
    if (!length(value, parsed, false) || parsed.unit != Length::Unit::Point) return false;
    out = parsed.amount;
    return true;
}

template <typename Enum>
bool choice(const Value& value, std::initializer_list<std::pair<std::string_view, Enum>> names, Enum& out) {
    if (!value.is_string()) return false;
    for (const auto& [name, item] : names) {
        if (value.as_string() == name) {
            out = item;
            return true;
        }
    }
    return false;
}

bool align(const Value& value, YGAlign& out) {
    return choice<YGAlign>(value,
                           {{"auto", YGAlignAuto},
                            {"flex_start", YGAlignFlexStart},
                            {"center", YGAlignCenter},
                            {"flex_end", YGAlignFlexEnd},
                            {"stretch", YGAlignStretch},
                            {"baseline", YGAlignBaseline},
                            {"space_between", YGAlignSpaceBetween},
                            {"space_around", YGAlignSpaceAround},
                            {"space_evenly", YGAlignSpaceEvenly}},
                           out);
}

void reset(YGNodeRef node, const Spec& spec) {
    YGEdge edge = static_cast<YGEdge>(spec.edge);
    switch (spec.key) {
        case Key::Direction: YGNodeStyleSetDirection(node, YGDirectionInherit); break;
        case Key::FlexDirection: YGNodeStyleSetFlexDirection(node, YGFlexDirectionColumn); break;
        case Key::JustifyContent: YGNodeStyleSetJustifyContent(node, YGJustifyFlexStart); break;
        case Key::AlignItems: YGNodeStyleSetAlignItems(node, YGAlignStretch); break;
        case Key::AlignSelf: YGNodeStyleSetAlignSelf(node, YGAlignAuto); break;
        case Key::AlignContent: YGNodeStyleSetAlignContent(node, YGAlignFlexStart); break;
        case Key::Position: YGNodeStyleSetPositionType(node, YGPositionTypeRelative); break;
        case Key::FlexWrap: YGNodeStyleSetFlexWrap(node, YGWrapNoWrap); break;
        case Key::Display: YGNodeStyleSetDisplay(node, YGDisplayFlex); break;
        case Key::Overflow: YGNodeStyleSetOverflow(node, YGOverflowVisible); break;
        case Key::Width: YGNodeStyleSetWidthAuto(node); break;
        case Key::Height: YGNodeStyleSetHeightAuto(node); break;
        case Key::FlexBasis: YGNodeStyleSetFlexBasisAuto(node); break;
        case Key::MinWidth: YGNodeStyleSetMinWidth(node, YGUndefined); break;
        case Key::MinHeight: YGNodeStyleSetMinHeight(node, YGUndefined); break;
        case Key::MaxWidth: YGNodeStyleSetMaxWidth(node, YGUndefined); break;
        case Key::MaxHeight: YGNodeStyleSetMaxHeight(node, YGUndefined); break;
        case Key::Flex: YGNodeStyleSetFlex(node, YGUndefined); break;
        case Key::FlexGrow: YGNodeStyleSetFlexGrow(node, YGUndefined); break;
        case Key::FlexShrink: YGNodeStyleSetFlexShrink(node, YGUndefined); break;
        case Key::AspectRatio: YGNodeStyleSetAspectRatio(node, YGUndefined); break;
        case Key::Margin: YGNodeStyleSetMargin(node, edge, YGUndefined); break;
        case Key::Padding: YGNodeStyleSetPadding(node, edge, YGUndefined); break;
        case Key::Border: YGNodeStyleSetBorder(node, edge, YGUndefined); break;
        case Key::Inset: YGNodeStyleSetPosition(node, edge, YGUndefined); break;
        case Key::Gap: YGNodeStyleSetGap(node, static_cast<YGGutter>(spec.edge), YGUndefined); break;
    }
}

}  // namespace

bool is_layout_style(std::string_view key) {
    return specs().count(key) != 0;
}

bool apply_style(YGNodeRef node, std::string_view key, const Value* value) {
    auto found = specs().find(key);
    if (found == specs().end()) return false;
    const Spec& spec = found->second;
    if (value == nullptr || value->is_null()) {
        reset(node, spec);
        return true;
    }
    YGEdge edge = static_cast<YGEdge>(spec.edge);
    Length size;
    float amount = 0;
    switch (spec.key) {
        case Key::Direction: {
            YGDirection direction;
            if (!choice<YGDirection>(*value, {{"inherit", YGDirectionInherit}, {"ltr", YGDirectionLTR}, {"rtl", YGDirectionRTL}},
                                     direction)) return false;
            YGNodeStyleSetDirection(node, direction);
            return true;
        }
        case Key::FlexDirection: {
            YGFlexDirection direction;
            if (!choice<YGFlexDirection>(*value,
                                         {{"column", YGFlexDirectionColumn},
                                          {"column_reverse", YGFlexDirectionColumnReverse},
                                          {"row", YGFlexDirectionRow},
                                          {"row_reverse", YGFlexDirectionRowReverse}},
                                         direction)) return false;
            YGNodeStyleSetFlexDirection(node, direction);
            return true;
        }
        case Key::JustifyContent: {
            YGJustify justify;
            if (!choice<YGJustify>(*value,
                                   {{"flex_start", YGJustifyFlexStart},
                                    {"center", YGJustifyCenter},
                                    {"flex_end", YGJustifyFlexEnd},
                                    {"space_between", YGJustifySpaceBetween},
                                    {"space_around", YGJustifySpaceAround},
                                    {"space_evenly", YGJustifySpaceEvenly}},
                                   justify)) return false;
            YGNodeStyleSetJustifyContent(node, justify);
            return true;
        }
        case Key::AlignItems: {
            YGAlign alignment;
            if (!align(*value, alignment)) return false;
            YGNodeStyleSetAlignItems(node, alignment);
            return true;
        }
        case Key::AlignSelf: {
            YGAlign alignment;
            if (!align(*value, alignment)) return false;
            YGNodeStyleSetAlignSelf(node, alignment);
            return true;
        }
        case Key::AlignContent: {
            YGAlign alignment;
            if (!align(*value, alignment)) return false;
            YGNodeStyleSetAlignContent(node, alignment);
            return true;
        }
        case Key::Position: {
            YGPositionType type;
            if (!choice<YGPositionType>(*value,
                                        {{"static", YGPositionTypeStatic},
                                         {"relative", YGPositionTypeRelative},
                                         {"absolute", YGPositionTypeAbsolute}},
                                        type)) return false;
            YGNodeStyleSetPositionType(node, type);
            return true;
        }
        case Key::FlexWrap: {
            YGWrap wrap;
            if (!choice<YGWrap>(*value, {{"nowrap", YGWrapNoWrap}, {"wrap", YGWrapWrap}, {"wrap_reverse", YGWrapWrapReverse}},
                                wrap)) return false;
            YGNodeStyleSetFlexWrap(node, wrap);
            return true;
        }
        case Key::Display: {
            YGDisplay display;
            if (!choice<YGDisplay>(*value, {{"flex", YGDisplayFlex}, {"none", YGDisplayNone}, {"contents", YGDisplayContents}},
                                   display)) return false;
            YGNodeStyleSetDisplay(node, display);
            return true;
        }
        case Key::Overflow: {
            YGOverflow overflow;
            if (!choice<YGOverflow>(*value,
                                    {{"visible", YGOverflowVisible}, {"hidden", YGOverflowHidden}, {"scroll", YGOverflowScroll}},
                                    overflow)) return false;
            YGNodeStyleSetOverflow(node, overflow);
            return true;
        }
        case Key::Width:
            if (!length(*value, size, true)) return false;
            if (size.unit == Length::Unit::Auto) YGNodeStyleSetWidthAuto(node);
            else if (size.unit == Length::Unit::Percent) YGNodeStyleSetWidthPercent(node, size.amount);
            else YGNodeStyleSetWidth(node, size.amount);
            return true;
        case Key::Height:
            if (!length(*value, size, true)) return false;
            if (size.unit == Length::Unit::Auto) YGNodeStyleSetHeightAuto(node);
            else if (size.unit == Length::Unit::Percent) YGNodeStyleSetHeightPercent(node, size.amount);
            else YGNodeStyleSetHeight(node, size.amount);
            return true;
        case Key::FlexBasis:
            if (!length(*value, size, true)) return false;
            if (size.unit == Length::Unit::Auto) YGNodeStyleSetFlexBasisAuto(node);
            else if (size.unit == Length::Unit::Percent) YGNodeStyleSetFlexBasisPercent(node, size.amount);
            else YGNodeStyleSetFlexBasis(node, size.amount);
            return true;
        case Key::MinWidth:
            if (!length(*value, size, false)) return false;
            if (size.unit == Length::Unit::Percent) YGNodeStyleSetMinWidthPercent(node, size.amount);
            else YGNodeStyleSetMinWidth(node, size.amount);
            return true;
        case Key::MinHeight:
            if (!length(*value, size, false)) return false;
            if (size.unit == Length::Unit::Percent) YGNodeStyleSetMinHeightPercent(node, size.amount);
            else YGNodeStyleSetMinHeight(node, size.amount);
            return true;
        case Key::MaxWidth:
            if (!length(*value, size, false)) return false;
            if (size.unit == Length::Unit::Percent) YGNodeStyleSetMaxWidthPercent(node, size.amount);
            else YGNodeStyleSetMaxWidth(node, size.amount);
            return true;
        case Key::MaxHeight:
            if (!length(*value, size, false)) return false;
            if (size.unit == Length::Unit::Percent) YGNodeStyleSetMaxHeightPercent(node, size.amount);
            else YGNodeStyleSetMaxHeight(node, size.amount);
            return true;
        case Key::Flex:
            if (!number(*value, amount)) return false;
            YGNodeStyleSetFlex(node, amount);
            return true;
        case Key::FlexGrow:
            if (!number(*value, amount)) return false;
            YGNodeStyleSetFlexGrow(node, amount);
            return true;
        case Key::FlexShrink:
            if (!number(*value, amount)) return false;
            YGNodeStyleSetFlexShrink(node, amount);
            return true;
        case Key::AspectRatio:
            if (!number(*value, amount)) return false;
            YGNodeStyleSetAspectRatio(node, amount);
            return true;
        case Key::Margin:
            if (!length(*value, size, true)) return false;
            if (size.unit == Length::Unit::Auto) YGNodeStyleSetMarginAuto(node, edge);
            else if (size.unit == Length::Unit::Percent) YGNodeStyleSetMarginPercent(node, edge, size.amount);
            else YGNodeStyleSetMargin(node, edge, size.amount);
            return true;
        case Key::Padding:
            if (!length(*value, size, false)) return false;
            if (size.unit == Length::Unit::Percent) YGNodeStyleSetPaddingPercent(node, edge, size.amount);
            else YGNodeStyleSetPadding(node, edge, size.amount);
            return true;
        case Key::Border:
            if (!number(*value, amount)) return false;
            YGNodeStyleSetBorder(node, edge, amount);
            return true;
        case Key::Inset:
            if (!length(*value, size, true)) return false;
            if (size.unit == Length::Unit::Auto) YGNodeStyleSetPositionAuto(node, edge);
            else if (size.unit == Length::Unit::Percent) YGNodeStyleSetPositionPercent(node, edge, size.amount);
            else YGNodeStyleSetPosition(node, edge, size.amount);
            return true;
        case Key::Gap: {
            if (!length(*value, size, false)) return false;
            YGGutter gutter = static_cast<YGGutter>(spec.edge);
            if (size.unit == Length::Unit::Percent) YGNodeStyleSetGapPercent(node, gutter, size.amount);
            else YGNodeStyleSetGap(node, gutter, size.amount);
            return true;
        }
    }
    return false;
}

}  // namespace pn
