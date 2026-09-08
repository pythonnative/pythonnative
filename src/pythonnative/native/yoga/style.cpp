#include "include/PNStyle.h"
#include <string>
#include <cstdlib>
#include <cmath>
extern "C" bool PNYogaSetStyle(YGNodeRef node, const char* rawKey, const char* rawValue) {
    std::string key(rawKey), value(rawValue);
    bool percent = !value.empty() && value.back() == '%';
    char* end = nullptr;
    float number = std::strtof(rawValue, &end);
    if (key == "direction") {
        if (value == "inherit") { YGNodeStyleSetDirection(node, static_cast<YGDirection>(0)); return true; }
        if (value == "ltr") { YGNodeStyleSetDirection(node, static_cast<YGDirection>(1)); return true; }
        if (value == "rtl") { YGNodeStyleSetDirection(node, static_cast<YGDirection>(2)); return true; }
        return false;
    }
    if (key == "flex_direction") {
        if (value == "column") { YGNodeStyleSetFlexDirection(node, static_cast<YGFlexDirection>(0)); return true; }
        if (value == "column_reverse") { YGNodeStyleSetFlexDirection(node, static_cast<YGFlexDirection>(1)); return true; }
        if (value == "row") { YGNodeStyleSetFlexDirection(node, static_cast<YGFlexDirection>(2)); return true; }
        if (value == "row_reverse") { YGNodeStyleSetFlexDirection(node, static_cast<YGFlexDirection>(3)); return true; }
        return false;
    }
    if (key == "justify_content") {
        if (value == "flex_start") { YGNodeStyleSetJustifyContent(node, static_cast<YGJustify>(0)); return true; }
        if (value == "center") { YGNodeStyleSetJustifyContent(node, static_cast<YGJustify>(1)); return true; }
        if (value == "flex_end") { YGNodeStyleSetJustifyContent(node, static_cast<YGJustify>(2)); return true; }
        if (value == "space_between") { YGNodeStyleSetJustifyContent(node, static_cast<YGJustify>(3)); return true; }
        if (value == "space_around") { YGNodeStyleSetJustifyContent(node, static_cast<YGJustify>(4)); return true; }
        if (value == "space_evenly") { YGNodeStyleSetJustifyContent(node, static_cast<YGJustify>(5)); return true; }
        return false;
    }
    if (key == "align_items") {
        if (value == "auto") { YGNodeStyleSetAlignItems(node, static_cast<YGAlign>(0)); return true; }
        if (value == "flex_start") { YGNodeStyleSetAlignItems(node, static_cast<YGAlign>(1)); return true; }
        if (value == "center") { YGNodeStyleSetAlignItems(node, static_cast<YGAlign>(2)); return true; }
        if (value == "flex_end") { YGNodeStyleSetAlignItems(node, static_cast<YGAlign>(3)); return true; }
        if (value == "stretch") { YGNodeStyleSetAlignItems(node, static_cast<YGAlign>(4)); return true; }
        if (value == "baseline") { YGNodeStyleSetAlignItems(node, static_cast<YGAlign>(5)); return true; }
        if (value == "space_between") { YGNodeStyleSetAlignItems(node, static_cast<YGAlign>(6)); return true; }
        if (value == "space_around") { YGNodeStyleSetAlignItems(node, static_cast<YGAlign>(7)); return true; }
        if (value == "space_evenly") { YGNodeStyleSetAlignItems(node, static_cast<YGAlign>(8)); return true; }
        return false;
    }
    if (key == "align_self") {
        if (value == "auto") { YGNodeStyleSetAlignSelf(node, static_cast<YGAlign>(0)); return true; }
        if (value == "flex_start") { YGNodeStyleSetAlignSelf(node, static_cast<YGAlign>(1)); return true; }
        if (value == "center") { YGNodeStyleSetAlignSelf(node, static_cast<YGAlign>(2)); return true; }
        if (value == "flex_end") { YGNodeStyleSetAlignSelf(node, static_cast<YGAlign>(3)); return true; }
        if (value == "stretch") { YGNodeStyleSetAlignSelf(node, static_cast<YGAlign>(4)); return true; }
        if (value == "baseline") { YGNodeStyleSetAlignSelf(node, static_cast<YGAlign>(5)); return true; }
        if (value == "space_between") { YGNodeStyleSetAlignSelf(node, static_cast<YGAlign>(6)); return true; }
        if (value == "space_around") { YGNodeStyleSetAlignSelf(node, static_cast<YGAlign>(7)); return true; }
        if (value == "space_evenly") { YGNodeStyleSetAlignSelf(node, static_cast<YGAlign>(8)); return true; }
        return false;
    }
    if (key == "align_content") {
        if (value == "auto") { YGNodeStyleSetAlignContent(node, static_cast<YGAlign>(0)); return true; }
        if (value == "flex_start") { YGNodeStyleSetAlignContent(node, static_cast<YGAlign>(1)); return true; }
        if (value == "center") { YGNodeStyleSetAlignContent(node, static_cast<YGAlign>(2)); return true; }
        if (value == "flex_end") { YGNodeStyleSetAlignContent(node, static_cast<YGAlign>(3)); return true; }
        if (value == "stretch") { YGNodeStyleSetAlignContent(node, static_cast<YGAlign>(4)); return true; }
        if (value == "baseline") { YGNodeStyleSetAlignContent(node, static_cast<YGAlign>(5)); return true; }
        if (value == "space_between") { YGNodeStyleSetAlignContent(node, static_cast<YGAlign>(6)); return true; }
        if (value == "space_around") { YGNodeStyleSetAlignContent(node, static_cast<YGAlign>(7)); return true; }
        if (value == "space_evenly") { YGNodeStyleSetAlignContent(node, static_cast<YGAlign>(8)); return true; }
        return false;
    }
    if (key == "position") {
        if (value == "static") { YGNodeStyleSetPositionType(node, static_cast<YGPositionType>(0)); return true; }
        if (value == "relative") { YGNodeStyleSetPositionType(node, static_cast<YGPositionType>(1)); return true; }
        if (value == "absolute") { YGNodeStyleSetPositionType(node, static_cast<YGPositionType>(2)); return true; }
        return false;
    }
    if (key == "flex_wrap") {
        if (value == "nowrap") { YGNodeStyleSetFlexWrap(node, static_cast<YGWrap>(0)); return true; }
        if (value == "wrap") { YGNodeStyleSetFlexWrap(node, static_cast<YGWrap>(1)); return true; }
        if (value == "wrap_reverse") { YGNodeStyleSetFlexWrap(node, static_cast<YGWrap>(2)); return true; }
        return false;
    }
    if (key == "display") {
        if (value == "flex") { YGNodeStyleSetDisplay(node, static_cast<YGDisplay>(0)); return true; }
        if (value == "none") { YGNodeStyleSetDisplay(node, static_cast<YGDisplay>(1)); return true; }
        if (value == "contents") { YGNodeStyleSetDisplay(node, static_cast<YGDisplay>(2)); return true; }
        return false;
    }
    if (key == "width") {
        if (value == "auto") { YGNodeStyleSetWidthAuto(node); return true; }
        if (percent) { YGNodeStyleSetWidthPercent(node, number); return true; }
        YGNodeStyleSetWidth(node, number); return end != rawValue;
    }
    if (key == "height") {
        if (value == "auto") { YGNodeStyleSetHeightAuto(node); return true; }
        if (percent) { YGNodeStyleSetHeightPercent(node, number); return true; }
        YGNodeStyleSetHeight(node, number); return end != rawValue;
    }
    if (key == "min_width") {
        if (percent) { YGNodeStyleSetMinWidthPercent(node, number); return true; }
        YGNodeStyleSetMinWidth(node, number); return end != rawValue;
    }
    if (key == "min_height") {
        if (percent) { YGNodeStyleSetMinHeightPercent(node, number); return true; }
        YGNodeStyleSetMinHeight(node, number); return end != rawValue;
    }
    if (key == "max_width") {
        if (percent) { YGNodeStyleSetMaxWidthPercent(node, number); return true; }
        YGNodeStyleSetMaxWidth(node, number); return end != rawValue;
    }
    if (key == "max_height") {
        if (percent) { YGNodeStyleSetMaxHeightPercent(node, number); return true; }
        YGNodeStyleSetMaxHeight(node, number); return end != rawValue;
    }
    if (key == "flex_basis") {
        if (value == "auto") { YGNodeStyleSetFlexBasisAuto(node); return true; }
        if (percent) { YGNodeStyleSetFlexBasisPercent(node, number); return true; }
        YGNodeStyleSetFlexBasis(node, number); return end != rawValue;
    }
    if (key == "flex") {
        YGNodeStyleSetFlex(node, number); return end != rawValue;
    }
    if (key == "flex_grow") {
        YGNodeStyleSetFlexGrow(node, number); return end != rawValue;
    }
    if (key == "flex_shrink") {
        YGNodeStyleSetFlexShrink(node, number); return end != rawValue;
    }
    if (key == "aspect_ratio") {
        YGNodeStyleSetAspectRatio(node, number); return end != rawValue;
    }
    if (key == "margin_left") {
        if (value == "auto") { YGNodeStyleSetMarginAuto(node, static_cast<YGEdge>(0)); return true; }
        if (percent) { YGNodeStyleSetMarginPercent(node, static_cast<YGEdge>(0), number); return true; }
        YGNodeStyleSetMargin(node, static_cast<YGEdge>(0), number); return end != rawValue;
    }
    if (key == "margin_top") {
        if (value == "auto") { YGNodeStyleSetMarginAuto(node, static_cast<YGEdge>(1)); return true; }
        if (percent) { YGNodeStyleSetMarginPercent(node, static_cast<YGEdge>(1), number); return true; }
        YGNodeStyleSetMargin(node, static_cast<YGEdge>(1), number); return end != rawValue;
    }
    if (key == "margin_right") {
        if (value == "auto") { YGNodeStyleSetMarginAuto(node, static_cast<YGEdge>(2)); return true; }
        if (percent) { YGNodeStyleSetMarginPercent(node, static_cast<YGEdge>(2), number); return true; }
        YGNodeStyleSetMargin(node, static_cast<YGEdge>(2), number); return end != rawValue;
    }
    if (key == "margin_bottom") {
        if (value == "auto") { YGNodeStyleSetMarginAuto(node, static_cast<YGEdge>(3)); return true; }
        if (percent) { YGNodeStyleSetMarginPercent(node, static_cast<YGEdge>(3), number); return true; }
        YGNodeStyleSetMargin(node, static_cast<YGEdge>(3), number); return end != rawValue;
    }
    if (key == "margin_start") {
        if (value == "auto") { YGNodeStyleSetMarginAuto(node, static_cast<YGEdge>(4)); return true; }
        if (percent) { YGNodeStyleSetMarginPercent(node, static_cast<YGEdge>(4), number); return true; }
        YGNodeStyleSetMargin(node, static_cast<YGEdge>(4), number); return end != rawValue;
    }
    if (key == "margin_end") {
        if (value == "auto") { YGNodeStyleSetMarginAuto(node, static_cast<YGEdge>(5)); return true; }
        if (percent) { YGNodeStyleSetMarginPercent(node, static_cast<YGEdge>(5), number); return true; }
        YGNodeStyleSetMargin(node, static_cast<YGEdge>(5), number); return end != rawValue;
    }
    if (key == "margin_horizontal") {
        if (value == "auto") { YGNodeStyleSetMarginAuto(node, static_cast<YGEdge>(6)); return true; }
        if (percent) { YGNodeStyleSetMarginPercent(node, static_cast<YGEdge>(6), number); return true; }
        YGNodeStyleSetMargin(node, static_cast<YGEdge>(6), number); return end != rawValue;
    }
    if (key == "margin_vertical") {
        if (value == "auto") { YGNodeStyleSetMarginAuto(node, static_cast<YGEdge>(7)); return true; }
        if (percent) { YGNodeStyleSetMarginPercent(node, static_cast<YGEdge>(7), number); return true; }
        YGNodeStyleSetMargin(node, static_cast<YGEdge>(7), number); return end != rawValue;
    }
    if (key == "margin") {
        if (value == "auto") { YGNodeStyleSetMarginAuto(node, static_cast<YGEdge>(8)); return true; }
        if (percent) { YGNodeStyleSetMarginPercent(node, static_cast<YGEdge>(8), number); return true; }
        YGNodeStyleSetMargin(node, static_cast<YGEdge>(8), number); return end != rawValue;
    }
    if (key == "padding_left") {
        if (percent) { YGNodeStyleSetPaddingPercent(node, static_cast<YGEdge>(0), number); return true; }
        YGNodeStyleSetPadding(node, static_cast<YGEdge>(0), number); return end != rawValue;
    }
    if (key == "padding_top") {
        if (percent) { YGNodeStyleSetPaddingPercent(node, static_cast<YGEdge>(1), number); return true; }
        YGNodeStyleSetPadding(node, static_cast<YGEdge>(1), number); return end != rawValue;
    }
    if (key == "padding_right") {
        if (percent) { YGNodeStyleSetPaddingPercent(node, static_cast<YGEdge>(2), number); return true; }
        YGNodeStyleSetPadding(node, static_cast<YGEdge>(2), number); return end != rawValue;
    }
    if (key == "padding_bottom") {
        if (percent) { YGNodeStyleSetPaddingPercent(node, static_cast<YGEdge>(3), number); return true; }
        YGNodeStyleSetPadding(node, static_cast<YGEdge>(3), number); return end != rawValue;
    }
    if (key == "padding_start") {
        if (percent) { YGNodeStyleSetPaddingPercent(node, static_cast<YGEdge>(4), number); return true; }
        YGNodeStyleSetPadding(node, static_cast<YGEdge>(4), number); return end != rawValue;
    }
    if (key == "padding_end") {
        if (percent) { YGNodeStyleSetPaddingPercent(node, static_cast<YGEdge>(5), number); return true; }
        YGNodeStyleSetPadding(node, static_cast<YGEdge>(5), number); return end != rawValue;
    }
    if (key == "padding_horizontal") {
        if (percent) { YGNodeStyleSetPaddingPercent(node, static_cast<YGEdge>(6), number); return true; }
        YGNodeStyleSetPadding(node, static_cast<YGEdge>(6), number); return end != rawValue;
    }
    if (key == "padding_vertical") {
        if (percent) { YGNodeStyleSetPaddingPercent(node, static_cast<YGEdge>(7), number); return true; }
        YGNodeStyleSetPadding(node, static_cast<YGEdge>(7), number); return end != rawValue;
    }
    if (key == "padding") {
        if (percent) { YGNodeStyleSetPaddingPercent(node, static_cast<YGEdge>(8), number); return true; }
        YGNodeStyleSetPadding(node, static_cast<YGEdge>(8), number); return end != rawValue;
    }
    if (key == "left") {
        if (value == "auto") { YGNodeStyleSetPositionAuto(node, static_cast<YGEdge>(0)); return true; }
        if (percent) { YGNodeStyleSetPositionPercent(node, static_cast<YGEdge>(0), number); return true; }
        YGNodeStyleSetPosition(node, static_cast<YGEdge>(0), number); return end != rawValue;
    }
    if (key == "top") {
        if (value == "auto") { YGNodeStyleSetPositionAuto(node, static_cast<YGEdge>(1)); return true; }
        if (percent) { YGNodeStyleSetPositionPercent(node, static_cast<YGEdge>(1), number); return true; }
        YGNodeStyleSetPosition(node, static_cast<YGEdge>(1), number); return end != rawValue;
    }
    if (key == "right") {
        if (value == "auto") { YGNodeStyleSetPositionAuto(node, static_cast<YGEdge>(2)); return true; }
        if (percent) { YGNodeStyleSetPositionPercent(node, static_cast<YGEdge>(2), number); return true; }
        YGNodeStyleSetPosition(node, static_cast<YGEdge>(2), number); return end != rawValue;
    }
    if (key == "bottom") {
        if (value == "auto") { YGNodeStyleSetPositionAuto(node, static_cast<YGEdge>(3)); return true; }
        if (percent) { YGNodeStyleSetPositionPercent(node, static_cast<YGEdge>(3), number); return true; }
        YGNodeStyleSetPosition(node, static_cast<YGEdge>(3), number); return end != rawValue;
    }
    if (key == "start") {
        if (value == "auto") { YGNodeStyleSetPositionAuto(node, static_cast<YGEdge>(4)); return true; }
        if (percent) { YGNodeStyleSetPositionPercent(node, static_cast<YGEdge>(4), number); return true; }
        YGNodeStyleSetPosition(node, static_cast<YGEdge>(4), number); return end != rawValue;
    }
    if (key == "end") {
        if (value == "auto") { YGNodeStyleSetPositionAuto(node, static_cast<YGEdge>(5)); return true; }
        if (percent) { YGNodeStyleSetPositionPercent(node, static_cast<YGEdge>(5), number); return true; }
        YGNodeStyleSetPosition(node, static_cast<YGEdge>(5), number); return end != rawValue;
    }
    if (key == "border_left_width") {
        YGNodeStyleSetBorder(node, static_cast<YGEdge>(0), number); return end != rawValue;
    }
    if (key == "border_top_width") {
        YGNodeStyleSetBorder(node, static_cast<YGEdge>(1), number); return end != rawValue;
    }
    if (key == "border_right_width") {
        YGNodeStyleSetBorder(node, static_cast<YGEdge>(2), number); return end != rawValue;
    }
    if (key == "border_bottom_width") {
        YGNodeStyleSetBorder(node, static_cast<YGEdge>(3), number); return end != rawValue;
    }
    if (key == "border_start_width") {
        YGNodeStyleSetBorder(node, static_cast<YGEdge>(4), number); return end != rawValue;
    }
    if (key == "border_end_width") {
        YGNodeStyleSetBorder(node, static_cast<YGEdge>(5), number); return end != rawValue;
    }
    if (key == "border_horizontal_width") {
        YGNodeStyleSetBorder(node, static_cast<YGEdge>(6), number); return end != rawValue;
    }
    if (key == "border_vertical_width") {
        YGNodeStyleSetBorder(node, static_cast<YGEdge>(7), number); return end != rawValue;
    }
    if (key == "border_width") {
        YGNodeStyleSetBorder(node, static_cast<YGEdge>(8), number); return end != rawValue;
    }
    if (key == "gap") { if (percent) YGNodeStyleSetGapPercent(node, static_cast<YGGutter>(2), number); else YGNodeStyleSetGap(node, static_cast<YGGutter>(2), number); return true; }
    if (key == "spacing") { if (percent) YGNodeStyleSetGapPercent(node, static_cast<YGGutter>(2), number); else YGNodeStyleSetGap(node, static_cast<YGGutter>(2), number); return true; }
    if (key == "row_gap") { if (percent) YGNodeStyleSetGapPercent(node, static_cast<YGGutter>(1), number); else YGNodeStyleSetGap(node, static_cast<YGGutter>(1), number); return true; }
    if (key == "column_gap") { if (percent) YGNodeStyleSetGapPercent(node, static_cast<YGGutter>(0), number); else YGNodeStyleSetGap(node, static_cast<YGGutter>(0), number); return true; }
    return false;
}
