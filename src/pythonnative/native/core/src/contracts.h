// Component and module contracts, compiled once from the contract document.
//
// The document is the JSON that `pythonnative.sdk.schema` writes: built-in
// contracts in the interned `fields` form, or a plain manifest of plugin
// contracts. Validation runs over integer-indexed schema nodes; nothing on
// the commit path looks at schema JSON.
#pragma once

#include <cstdint>
#include <deque>
#include <string>
#include <string_view>
#include <unordered_map>
#include <vector>

#include "value.h"

namespace pn {

/// How a leaf component's intrinsic size is found.
enum class Measurement : uint8_t {
    Container,  ///< Never measured; style and children decide its size.
    Text,       ///< Thread-safe platform text layout.
    Intrinsic,  ///< A widget measured on the platform UI thread.
    Native,     ///< A plugin's thread-safe platform measurement.
    Image,      ///< The intrinsic size the platform reports after loading.
    Svg,        ///< The `view_box` aspect, 24 by 24 by default.
    Fill,       ///< The available space (lists without an explicit size).
};

/// A compiled JSON-schema subset: the shapes `sdk.types.type_schema` emits.
struct SchemaNode {
    enum class Kind : uint8_t { Any, Null, String, Boolean, Number, Integer, Array, Object, AnyOf, Enum };
    Kind kind = Kind::Any;
    std::vector<int> alternatives;     // AnyOf
    std::vector<Value> choices;        // Enum
    int items = -1;                    // Array; -1 accepts anything
    std::vector<int> prefix;           // Array tuple items
    bool tuple = false;
    std::vector<std::pair<std::string, int>> properties;  // Object, sorted by name
    std::vector<std::string> required; // Object
    int additional = -1;               // Object; -1 accepts anything
    bool closed = false;               // Object with additionalProperties: false
};

/// One prop of one component.
struct Field {
    std::string name;
    int schema = -1;
    bool allowed = true;    // supported on this platform
    bool layout = true;     // changing it invalidates layout
    bool recreate = false;  // changing it rebuilds the widget
    bool required = false;
    bool flatten = false;   // a layout-only prop that keeps a view flattenable
    bool has_default = false;
    Value default_value;
};

struct Component {
    std::string name;
    uint16_t id = 0;
    Measurement measurement = Measurement::Intrinsic;
    bool flatten = false;          // may be omitted from the mounted tree
    bool adopt_flattened = false;  // may receive a flattened child's children
    bool detach_children = false;  // children lay out as independent roots
    bool clip = false;             // overflow hidden and flex shrink by default
    bool portal = false;           // lays out against its own container
    std::unordered_map<std::string, int> fields;  // name -> index into Contracts::fields
    std::unordered_map<std::string, int> commands;  // method -> object schema
};

/// The compiled contract document.
class Contracts {
public:
    /// Compile `document` for `platform` ("ios", "android", "web", or "host").
    /// Merges with already loaded contracts; returns false with an error on a
    /// malformed or conflicting document.
    bool load(const Value& document, std::string_view platform, std::string& error);
    void clear();

    const Component* component(std::string_view name) const;
    const Component* component(uint16_t id) const;
    const Field& field(int index) const { return fields_[static_cast<size_t>(index)]; }
    const Field* field(const Component& component, std::string_view name) const;
    const std::string& fingerprint() const { return fingerprint_; }
    size_t component_count() const { return components_.size(); }

    /// Check a create (`partial` false) or update's set values. `error` names the prop.
    bool validate_props(const Component& component, const Object& props, bool partial, std::string& error) const;
    /// Check an update's removed names against its set values.
    bool validate_removal(const Component& component, const Object& changed, const Array& removed,
                          std::string& error) const;
    /// Whether changing `keys` invalidates layout or requires recreation.
    void changes(const Component& component, const std::vector<std::string_view>& keys, bool& layout,
                 bool& recreate) const;
    /// Set each removed name to its declared default (or null).
    Object normalize(const Component& component, const Object& changed, const Array& removed) const;
    bool validate_command(const Component& component, std::string_view method, const Value& arguments,
                          std::string& error) const;
    bool validate_module(std::string_view module, std::string_view method, const Value& arguments) const;
    /// Whether `value` satisfies schema node `schema`.
    bool matches(int schema, const Value& value) const;
    /// Compile one standalone schema and return its node index.
    int compile_schema(const Value& schema) { return compile(schema); }

private:
    int compile(const Value& schema);

    std::vector<SchemaNode> schemas_;
    std::unordered_map<std::string, int> schema_index_;
    // Shadow nodes keep pointers to components (and code holds field
    // references across loads), so later loads must never move them: a
    // deque keeps existing elements in place as it grows.
    std::deque<Field> fields_;
    std::unordered_map<std::string, int> field_index_;
    std::deque<Component> components_;
    std::unordered_map<std::string, uint16_t> component_index_;
    std::unordered_map<std::string, int> modules_;  // "Module.method" -> object schema
    std::string platform_;
    std::string fingerprint_;
};

/// Parse a measurement name; unknown names are `Intrinsic`.
Measurement parse_measurement(std::string_view name);

}  // namespace pn
