// Immutable JSON-shaped values, the JSON codec, and the binary value encoding.
//
// Commits arrive as JSON text from Python; mount transactions leave as the
// binary encoding documented in `include/pn_core.h`. Objects keep their
// insertion order so encoded props are deterministic.
#pragma once

#include <cstdint>
#include <memory>
#include <string>
#include <string_view>
#include <utility>
#include <variant>
#include <vector>

namespace pn {

class Value;
using Array = std::vector<Value>;
using Member = std::pair<std::string, Value>;
using Object = std::vector<Member>;

/// One JSON value. Arrays and objects are shared and never mutated in place.
class Value {
public:
    enum class Kind : uint8_t { Null, Bool, Int, Double, String, Array, Object };

    Value() = default;
    static Value boolean(bool value);
    static Value integer(int64_t value);
    static Value number(double value);
    static Value string(std::string value);
    static Value array(Array items);
    static Value object(Object members);

    Kind kind() const { return static_cast<Kind>(data_.index()); }
    bool is_null() const { return kind() == Kind::Null; }
    bool is_bool() const { return kind() == Kind::Bool; }
    bool is_string() const { return kind() == Kind::String; }
    bool is_array() const { return kind() == Kind::Array; }
    bool is_object() const { return kind() == Kind::Object; }
    /// An integer or a finite double.
    bool is_number() const;
    /// An integer, or a finite double with no fractional part within 2^53.
    bool is_integer() const;

    bool as_bool() const { return is_bool() && std::get<bool>(data_); }
    double as_double(double fallback = 0) const;
    int64_t as_int(int64_t fallback = 0) const;
    const std::string& as_string() const;
    const Array& as_array() const;
    const Object& as_object() const;

    /// The member named `key`, or nullptr (also for non-objects).
    const Value* find(std::string_view key) const;
    /// Whether this value leaves a view's appearance unchanged when set:
    /// null, false, an empty string, an empty array, or an empty object.
    bool is_neutral() const;

    /// Deep equality; integers and doubles compare by numeric value.
    bool operator==(const Value& other) const;
    bool operator!=(const Value& other) const { return !(*this == other); }

private:
    std::variant<std::monostate, bool, int64_t, double, std::string, std::shared_ptr<const Array>,
                 std::shared_ptr<const Object>>
        data_;
};

/// Returns the member named `key` in `object`, or nullptr.
const Value* find_member(const Object& object, std::string_view key);
/// Sets `key` in `object`, replacing an existing member in place.
void set_member(Object& object, std::string_view key, Value value);
/// Removes `key` from `object`; returns whether it was present.
bool remove_member(Object& object, std::string_view key);

/// Parse strict JSON. On failure returns false and describes the error.
bool parse_json(std::string_view text, Value& out, std::string& error);
/// Compact JSON with unescaped UTF-8 and finite numbers only (non-finite become null).
std::string to_json(const Value& value);
void write_json(const Value& value, std::string& out);
/// Append `text` as a quoted JSON string.
void write_json_string(std::string_view text, std::string& out);

/// Little-endian byte writer for the binary formats in `pn_core.h`.
class ByteWriter {
public:
    void u8(uint8_t value) { bytes_.push_back(value); }
    void u16(uint16_t value);
    void u32(uint32_t value);
    void i64(int64_t value);
    void f64(double value);
    void str(std::string_view value);
    void value(const Value& value);
    /// Overwrite a previously written u32 at `offset`.
    void patch_u32(size_t offset, uint32_t value);
    size_t size() const { return bytes_.size(); }
    const std::vector<uint8_t>& bytes() const { return bytes_; }
    std::vector<uint8_t> take() { return std::move(bytes_); }
    void clear() { bytes_.clear(); }

private:
    std::vector<uint8_t> bytes_;
};

}  // namespace pn
