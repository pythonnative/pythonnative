#include "contracts.h"

#include <algorithm>

namespace pn {

namespace {

bool contains_string(const Value& list, std::string_view text) {
    for (const Value& item : list.as_array()) {
        if (item.is_string() && item.as_string() == text) return true;
    }
    return false;
}

bool flag(const Value* object, std::string_view key, bool fallback) {
    if (object == nullptr) return fallback;
    const Value* value = object->find(key);
    return value != nullptr && value->is_bool() ? value->as_bool() : fallback;
}

/// The value-shaping keys of a schema; documentation and metadata don't matter.
Value shape_of(const Value& schema) {
    static const char* const kKeys[] = {"type",       "anyOf",    "enum", "items", "prefixItems",
                                        "properties", "required", "additionalProperties"};
    Object shape;
    for (const char* key : kKeys) {
        if (const Value* value = schema.find(key)) shape.emplace_back(key, *value);
    }
    return Value::object(std::move(shape));
}

Value command_schema(const Value& contract) {
    Object schema;
    schema.emplace_back("type", Value::string("object"));
    const Value* arguments = contract.find("arguments");
    schema.emplace_back("properties", arguments != nullptr ? *arguments : Value::object({}));
    if (const Value* required = contract.find("required")) {
        schema.emplace_back("required", *required);
    } else {
        Array names;
        if (arguments != nullptr) {
            for (const auto& member : arguments->as_object()) names.push_back(Value::string(member.first));
        }
        schema.emplace_back("required", Value::array(std::move(names)));
    }
    schema.emplace_back("additionalProperties", Value::boolean(false));
    return Value::object(std::move(schema));
}

}  // namespace

Measurement parse_measurement(std::string_view name) {
    if (name == "container") return Measurement::Container;
    if (name == "text") return Measurement::Text;
    if (name == "native") return Measurement::Native;
    if (name == "image") return Measurement::Image;
    if (name == "svg") return Measurement::Svg;
    if (name == "fill") return Measurement::Fill;
    return Measurement::Intrinsic;
}

void Contracts::clear() {
    schemas_.clear();
    schema_index_.clear();
    fields_.clear();
    field_index_.clear();
    components_.clear();
    component_index_.clear();
    modules_.clear();
    fingerprint_.clear();
}

int Contracts::compile(const Value& schema) {
    Value shape = shape_of(schema);
    std::string identity = to_json(shape);
    auto known = schema_index_.find(identity);
    if (known != schema_index_.end()) return known->second;
    int index = static_cast<int>(schemas_.size());
    schema_index_.emplace(identity, index);
    schemas_.emplace_back();
    SchemaNode node;
    if (const Value* any_of = schema.find("anyOf")) {
        node.kind = SchemaNode::Kind::AnyOf;
        for (const Value& item : any_of->as_array()) node.alternatives.push_back(compile(item));
    } else if (const Value* choices = schema.find("enum")) {
        node.kind = SchemaNode::Kind::Enum;
        node.choices = choices->as_array();
    } else {
        const std::string& type = schema.find("type") ? schema.find("type")->as_string() : std::string();
        if (type == "null") node.kind = SchemaNode::Kind::Null;
        else if (type == "string") node.kind = SchemaNode::Kind::String;
        else if (type == "boolean" || type == "event") node.kind = SchemaNode::Kind::Boolean;
        else if (type == "number") node.kind = SchemaNode::Kind::Number;
        else if (type == "integer") node.kind = SchemaNode::Kind::Integer;
        else if (type == "array") {
            node.kind = SchemaNode::Kind::Array;
            if (const Value* prefix = schema.find("prefixItems")) {
                node.tuple = true;
                for (const Value& item : prefix->as_array()) node.prefix.push_back(compile(item));
            } else if (const Value* items = schema.find("items")) {
                node.items = compile(*items);
            }
        } else if (type == "object") {
            node.kind = SchemaNode::Kind::Object;
            if (const Value* properties = schema.find("properties")) {
                for (const auto& [key, item] : properties->as_object()) node.properties.emplace_back(key, compile(item));
                std::sort(node.properties.begin(), node.properties.end(),
                          [](const auto& a, const auto& b) { return a.first < b.first; });
            }
            if (const Value* required = schema.find("required")) {
                for (const Value& name : required->as_array()) node.required.push_back(name.as_string());
            }
            if (const Value* additional = schema.find("additionalProperties")) {
                if (additional->is_bool()) node.closed = !additional->as_bool();
                else if (additional->is_object()) node.additional = compile(*additional);
            }
        }
    }
    schemas_[static_cast<size_t>(index)] = std::move(node);
    return index;
}

bool Contracts::matches(int index, const Value& value) const {
    if (index < 0) return true;
    const SchemaNode& node = schemas_[static_cast<size_t>(index)];
    switch (node.kind) {
        case SchemaNode::Kind::Any: return true;
        case SchemaNode::Kind::Null: return value.is_null();
        case SchemaNode::Kind::String: return value.is_string();
        case SchemaNode::Kind::Boolean: return value.is_bool();
        case SchemaNode::Kind::Number: return value.is_number();
        case SchemaNode::Kind::Integer: return value.is_integer();
        case SchemaNode::Kind::AnyOf:
            for (int alternative : node.alternatives) {
                if (matches(alternative, value)) return true;
            }
            return false;
        case SchemaNode::Kind::Enum:
            for (const Value& choice : node.choices) {
                if (choice.is_null() ? value.is_null()
                    : choice.is_string() ? value.is_string() && value.as_string() == choice.as_string()
                    : choice.is_bool()   ? value.is_bool() && value.as_bool() == choice.as_bool()
                                         : value.is_number() && value.as_double() == choice.as_double()) {
                    return true;
                }
            }
            return false;
        case SchemaNode::Kind::Array: {
            if (!value.is_array()) return false;
            const Array& items = value.as_array();
            if (node.tuple) {
                if (items.size() != node.prefix.size()) return false;
                for (size_t i = 0; i < items.size(); ++i) {
                    if (!matches(node.prefix[i], items[i])) return false;
                }
                return true;
            }
            for (const Value& item : items) {
                if (!matches(node.items, item)) return false;
            }
            return true;
        }
        case SchemaNode::Kind::Object: {
            if (!value.is_object()) return false;
            const Object& members = value.as_object();
            for (const std::string& name : node.required) {
                if (find_member(members, name) == nullptr) return false;
            }
            for (const auto& [key, item] : members) {
                auto it = std::lower_bound(node.properties.begin(), node.properties.end(), key,
                                           [](const auto& property, const std::string& name) {
                                               return property.first < name;
                                           });
                if (it != node.properties.end() && it->first == key) {
                    if (!matches(it->second, item)) return false;
                } else if (node.closed) {
                    return false;
                } else if (!matches(node.additional, item)) {
                    return false;
                }
            }
            return true;
        }
    }
    return false;
}

bool Contracts::load(const Value& document, std::string_view platform, std::string& error) {
    if (!document.is_object()) {
        error = "contract document must be an object";
        return false;
    }
    platform_ = std::string(platform);
    if (const Value* fingerprint = document.find("fingerprint"); fingerprint != nullptr && fingerprint->is_string()) {
        fingerprint_ = fingerprint->as_string();
    }
    const Value* interned = document.find("fields");
    const Value* components = document.find("components");
    if (components != nullptr) {
        for (const auto& [name, spec] : components->as_object()) {
            if (!spec.is_object()) {
                error = "invalid contract for " + name;
                return false;
            }
            if (component_index_.count(name) != 0) continue;  // built-ins and plugins merge once
            Component component;
            component.name = name;
            component.id = static_cast<uint16_t>(components_.size());
            const Value* measurement = spec.find("measurement");
            component.measurement = parse_measurement(measurement != nullptr ? measurement->as_string() : "");
            component.flatten = flag(&spec, "flatten", false);
            component.adopt_flattened = flag(&spec, "adopt_flattened", false);
            component.detach_children = flag(&spec, "detach_children", false);
            component.clip = flag(&spec, "clip", false);
            component.portal = flag(&spec, "portal", false);
            bool supported = true;
            if (const Value* platforms = spec.find("platforms"); platforms != nullptr && platforms->is_array()) {
                supported = contains_string(*platforms, platform_) || platform_ == "host";
            }
            const Value* required = spec.find("required");
            const Value* defaults = spec.find("defaults");
            if (const Value* props = spec.find("props")) {
                for (const auto& [key, raw] : props->as_object()) {
                    const Value* schema = &raw;
                    if (raw.is_integer()) {
                        if (interned == nullptr || raw.as_int() < 0 ||
                            static_cast<size_t>(raw.as_int()) >= interned->as_array().size()) {
                            error = "invalid interned field for " + name + "." + key;
                            return false;
                        }
                        schema = &interned->as_array()[static_cast<size_t>(raw.as_int())];
                    }
                    const Value* native = schema->find("native");
                    Field field;
                    field.name = key;
                    field.schema = compile(*schema);
                    field.allowed = supported;
                    if (native != nullptr) {
                        if (const Value* platforms = native->find("platforms");
                            platforms != nullptr && platforms->is_array() && platform_ != "host") {
                            field.allowed = supported && contains_string(*platforms, platform_);
                        }
                    }
                    field.layout = flag(native, "invalidates_layout", true);
                    field.recreate = flag(native, "recreate", false);
                    field.flatten = flag(native, "flatten", false);
                    field.required = required != nullptr && contains_string(*required, key);
                    if (defaults != nullptr) {
                        if (const Value* fallback = defaults->find(key)) {
                            field.has_default = true;
                            field.default_value = *fallback;
                        }
                    }
                    component.fields.emplace(key, static_cast<int>(fields_.size()));
                    fields_.push_back(std::move(field));
                }
            }
            if (const Value* commands = spec.find("commands")) {
                for (const auto& [method, contract] : commands->as_object()) {
                    component.commands.emplace(method, compile(command_schema(contract)));
                }
            }
            component_index_.emplace(name, component.id);
            components_.push_back(std::move(component));
        }
    }
    if (const Value* modules = document.find("modules")) {
        for (const auto& [name, spec] : modules->as_object()) {
            if (const Value* methods = spec.find("methods")) {
                for (const auto& [method, contract] : methods->as_object()) {
                    modules_.emplace(name + "." + method, compile(command_schema(contract)));
                }
            }
        }
    }
    return true;
}

const Component* Contracts::component(std::string_view name) const {
    auto it = component_index_.find(std::string(name));
    return it == component_index_.end() ? nullptr : &components_[it->second];
}

const Component* Contracts::component(uint16_t id) const {
    return id < components_.size() ? &components_[id] : nullptr;
}

const Field* Contracts::field(const Component& component, std::string_view name) const {
    auto it = component.fields.find(std::string(name));
    return it == component.fields.end() ? nullptr : &fields_[static_cast<size_t>(it->second)];
}

bool Contracts::validate_props(const Component& component, const Object& props, bool partial,
                               std::string& error) const {
    if (!partial) {
        for (const auto& [name, index] : component.fields) {
            if (fields_[static_cast<size_t>(index)].required && find_member(props, name) == nullptr) {
                error = component.name + " requires " + name;
                return false;
            }
        }
    }
    for (const auto& [key, value] : props) {
        const Field* field = this->field(component, key);
        if (field == nullptr) {
            error = "unknown " + component.name + " prop " + key;
            return false;
        }
        if (!field->allowed) {
            error = component.name + "." + key + " isn't supported on " + platform_;
            return false;
        }
        if (!matches(field->schema, value)) {
            error = "invalid " + component.name + "." + key + ": " + to_json(value);
            return false;
        }
    }
    return true;
}

bool Contracts::validate_removal(const Component& component, const Object& changed, const Array& removed,
                                 std::string& error) const {
    for (size_t i = 0; i < removed.size(); ++i) {
        const Value& name = removed[i];
        if (!name.is_string()) {
            error = "removed property names must be strings";
            return false;
        }
        for (size_t j = 0; j < i; ++j) {
            if (removed[j] == name) {
                error = "property " + name.as_string() + " removed twice";
                return false;
            }
        }
        const Field* field = this->field(component, name.as_string());
        if (field == nullptr || !field->allowed) {
            error = "unknown " + component.name + " prop " + name.as_string();
            return false;
        }
        if (field->required) {
            error = "can't remove required " + component.name + "." + name.as_string();
            return false;
        }
        if (find_member(changed, name.as_string()) != nullptr) {
            error = "property " + name.as_string() + " is both set and removed";
            return false;
        }
    }
    return true;
}

void Contracts::changes(const Component& component, const std::vector<std::string_view>& keys, bool& layout,
                        bool& recreate) const {
    layout = false;
    recreate = false;
    for (std::string_view key : keys) {
        const Field* field = this->field(component, key);
        if (field == nullptr || field->layout) layout = true;
        if (field != nullptr && field->recreate) recreate = true;
    }
}

Object Contracts::normalize(const Component& component, const Object& changed, const Array& removed) const {
    Object result = changed;
    for (const Value& name : removed) {
        const Field* field = this->field(component, name.as_string());
        result.emplace_back(name.as_string(), field != nullptr && field->has_default ? field->default_value : Value());
    }
    return result;
}

bool Contracts::validate_command(const Component& component, std::string_view method, const Value& arguments,
                                 std::string& error) const {
    auto it = component.commands.find(std::string(method));
    if (it == component.commands.end()) {
        error = "unknown command " + component.name + "." + std::string(method);
        return false;
    }
    if (!matches(it->second, arguments)) {
        error = "invalid arguments for " + component.name + "." + std::string(method);
        return false;
    }
    return true;
}

bool Contracts::validate_module(std::string_view module, std::string_view method, const Value& arguments) const {
    if (module == "DevSupport" || module == "Host" || module == "Runtime") return true;
    auto it = modules_.find(std::string(module) + "." + std::string(method));
    return it != modules_.end() && matches(it->second, arguments);
}

}  // namespace pn
