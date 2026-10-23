// Map PythonNative style props onto Yoga nodes.
#pragma once

#include <string_view>

#include <yoga/Yoga.h>

#include "value.h"

namespace pn {

/// Whether `key` is a style prop Yoga consumes.
bool is_layout_style(std::string_view key);

/// Apply one style prop to `node`. A null `value` (or JSON null) resets the
/// field to Yoga's default. Returns false for an unknown key or a value of
/// the wrong shape, which leaves the node unchanged.
bool apply_style(YGNodeRef node, std::string_view key, const Value* value);

}  // namespace pn
