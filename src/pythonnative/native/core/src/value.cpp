#include "value.h"

#include <cerrno>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <limits>

namespace pn {

namespace {

constexpr double kMaxSafeInteger = 9007199254740991.0;

const std::string& empty_string() {
    static const std::string value;
    return value;
}

const Array& empty_array() {
    static const Array value;
    return value;
}

const Object& empty_object() {
    static const Object value;
    return value;
}

}  // namespace

Value Value::boolean(bool value) {
    Value result;
    result.data_ = value;
    return result;
}

Value Value::integer(int64_t value) {
    Value result;
    result.data_ = value;
    return result;
}

Value Value::number(double value) {
    Value result;
    result.data_ = value;
    return result;
}

Value Value::string(std::string value) {
    Value result;
    result.data_ = std::move(value);
    return result;
}

Value Value::array(Array items) {
    Value result;
    result.data_ = std::make_shared<const Array>(std::move(items));
    return result;
}

Value Value::object(Object members) {
    Value result;
    result.data_ = std::make_shared<const Object>(std::move(members));
    return result;
}

bool Value::is_number() const {
    if (kind() == Kind::Int) return true;
    return kind() == Kind::Double && std::isfinite(std::get<double>(data_));
}

bool Value::is_integer() const {
    if (kind() == Kind::Int) {
        int64_t value = std::get<int64_t>(data_);
        return value <= static_cast<int64_t>(kMaxSafeInteger) && value >= -static_cast<int64_t>(kMaxSafeInteger);
    }
    if (kind() != Kind::Double) return false;
    double value = std::get<double>(data_);
    return std::isfinite(value) && std::fabs(value) <= kMaxSafeInteger && std::floor(value) == value;
}

double Value::as_double(double fallback) const {
    if (kind() == Kind::Int) return static_cast<double>(std::get<int64_t>(data_));
    if (kind() == Kind::Double) return std::get<double>(data_);
    return fallback;
}

int64_t Value::as_int(int64_t fallback) const {
    if (kind() == Kind::Int) return std::get<int64_t>(data_);
    if (kind() == Kind::Double) {
        double value = std::get<double>(data_);
        if (std::isfinite(value) && std::fabs(value) <= kMaxSafeInteger) return static_cast<int64_t>(value);
    }
    return fallback;
}

const std::string& Value::as_string() const {
    return is_string() ? std::get<std::string>(data_) : empty_string();
}

const Array& Value::as_array() const {
    return is_array() ? *std::get<std::shared_ptr<const Array>>(data_) : empty_array();
}

const Object& Value::as_object() const {
    return is_object() ? *std::get<std::shared_ptr<const Object>>(data_) : empty_object();
}

const Value* Value::find(std::string_view key) const {
    return is_object() ? find_member(as_object(), key) : nullptr;
}

bool Value::is_neutral() const {
    switch (kind()) {
        case Kind::Null: return true;
        case Kind::Bool: return !as_bool();
        case Kind::String: return as_string().empty();
        case Kind::Array: return as_array().empty();
        case Kind::Object: return as_object().empty();
        default: return false;
    }
}

bool Value::operator==(const Value& other) const {
    bool numeric = (kind() == Kind::Int || kind() == Kind::Double);
    bool other_numeric = (other.kind() == Kind::Int || other.kind() == Kind::Double);
    if (numeric && other_numeric) {
        if (kind() == Kind::Int && other.kind() == Kind::Int) {
            return std::get<int64_t>(data_) == std::get<int64_t>(other.data_);
        }
        return as_double() == other.as_double();
    }
    if (kind() != other.kind()) return false;
    switch (kind()) {
        case Kind::Null: return true;
        case Kind::Bool: return as_bool() == other.as_bool();
        case Kind::String: return as_string() == other.as_string();
        case Kind::Array: {
            const Array& a = as_array();
            const Array& b = other.as_array();
            if (&a == &b) return true;
            if (a.size() != b.size()) return false;
            for (size_t i = 0; i < a.size(); ++i) {
                if (a[i] != b[i]) return false;
            }
            return true;
        }
        case Kind::Object: {
            const Object& a = as_object();
            const Object& b = other.as_object();
            if (&a == &b) return true;
            if (a.size() != b.size()) return false;
            for (const auto& [key, value] : a) {
                const Value* match = find_member(b, key);
                if (match == nullptr || *match != value) return false;
            }
            return true;
        }
        default: return false;
    }
}

const Value* find_member(const Object& object, std::string_view key) {
    for (const auto& member : object) {
        if (member.first == key) return &member.second;
    }
    return nullptr;
}

void set_member(Object& object, std::string_view key, Value value) {
    for (auto& member : object) {
        if (member.first == key) {
            member.second = std::move(value);
            return;
        }
    }
    object.emplace_back(std::string(key), std::move(value));
}

bool remove_member(Object& object, std::string_view key) {
    for (auto it = object.begin(); it != object.end(); ++it) {
        if (it->first == key) {
            object.erase(it);
            return true;
        }
    }
    return false;
}

// ----------------------------------------------------------------------
// JSON parsing
// ----------------------------------------------------------------------

namespace {

class Parser {
public:
    explicit Parser(std::string_view text) : text_(text) {}

    bool parse(Value& out, std::string& error) {
        skip_space();
        if (!value(out, 0)) {
            error = error_.empty() ? "invalid JSON" : error_;
            error += " at offset " + std::to_string(position_);
            return false;
        }
        skip_space();
        if (position_ != text_.size()) {
            error = "unexpected trailing characters at offset " + std::to_string(position_);
            return false;
        }
        return true;
    }

private:
    bool fail(const char* message) {
        if (error_.empty()) error_ = message;
        return false;
    }

    void skip_space() {
        while (position_ < text_.size()) {
            char c = text_[position_];
            if (c != ' ' && c != '\n' && c != '\r' && c != '\t') break;
            ++position_;
        }
    }

    bool literal(std::string_view word) {
        if (text_.substr(position_, word.size()) != word) return fail("invalid literal");
        position_ += word.size();
        return true;
    }

    bool value(Value& out, int depth) {
        if (depth > 256) return fail("nesting too deep");
        if (position_ >= text_.size()) return fail("unexpected end of input");
        char c = text_[position_];
        switch (c) {
            case 'n':
                out = Value();
                return literal("null");
            case 't':
                out = Value::boolean(true);
                return literal("true");
            case 'f':
                out = Value::boolean(false);
                return literal("false");
            case '"': {
                std::string text;
                if (!string(text)) return false;
                out = Value::string(std::move(text));
                return true;
            }
            case '[': return array(out, depth);
            case '{': return object(out, depth);
            default:
                if (c == '-' || (c >= '0' && c <= '9')) return number(out);
                return fail("unexpected character");
        }
    }

    bool array(Value& out, int depth) {
        ++position_;
        Array items;
        skip_space();
        if (position_ < text_.size() && text_[position_] == ']') {
            ++position_;
            out = Value::array(std::move(items));
            return true;
        }
        while (true) {
            skip_space();
            Value item;
            if (!value(item, depth + 1)) return false;
            items.push_back(std::move(item));
            skip_space();
            if (position_ >= text_.size()) return fail("unterminated array");
            char c = text_[position_++];
            if (c == ']') break;
            if (c != ',') return fail("expected ',' or ']'");
        }
        out = Value::array(std::move(items));
        return true;
    }

    bool object(Value& out, int depth) {
        ++position_;
        Object members;
        skip_space();
        if (position_ < text_.size() && text_[position_] == '}') {
            ++position_;
            out = Value::object(std::move(members));
            return true;
        }
        while (true) {
            skip_space();
            if (position_ >= text_.size() || text_[position_] != '"') return fail("expected a string key");
            std::string key;
            if (!string(key)) return false;
            skip_space();
            if (position_ >= text_.size() || text_[position_] != ':') return fail("expected ':'");
            ++position_;
            skip_space();
            Value item;
            if (!value(item, depth + 1)) return false;
            // Later duplicates win, as in Python's json module.
            set_member(members, key, std::move(item));
            skip_space();
            if (position_ >= text_.size()) return fail("unterminated object");
            char c = text_[position_++];
            if (c == '}') break;
            if (c != ',') return fail("expected ',' or '}'");
        }
        out = Value::object(std::move(members));
        return true;
    }

    static void append_utf8(uint32_t code, std::string& out) {
        if (code < 0x80) {
            out.push_back(static_cast<char>(code));
        } else if (code < 0x800) {
            out.push_back(static_cast<char>(0xC0 | (code >> 6)));
            out.push_back(static_cast<char>(0x80 | (code & 0x3F)));
        } else if (code < 0x10000) {
            out.push_back(static_cast<char>(0xE0 | (code >> 12)));
            out.push_back(static_cast<char>(0x80 | ((code >> 6) & 0x3F)));
            out.push_back(static_cast<char>(0x80 | (code & 0x3F)));
        } else {
            out.push_back(static_cast<char>(0xF0 | (code >> 18)));
            out.push_back(static_cast<char>(0x80 | ((code >> 12) & 0x3F)));
            out.push_back(static_cast<char>(0x80 | ((code >> 6) & 0x3F)));
            out.push_back(static_cast<char>(0x80 | (code & 0x3F)));
        }
    }

    bool hex4(uint32_t& code) {
        if (position_ + 4 > text_.size()) return fail("truncated \\u escape");
        code = 0;
        for (int i = 0; i < 4; ++i) {
            char c = text_[position_++];
            code <<= 4;
            if (c >= '0' && c <= '9') code |= static_cast<uint32_t>(c - '0');
            else if (c >= 'a' && c <= 'f') code |= static_cast<uint32_t>(c - 'a' + 10);
            else if (c >= 'A' && c <= 'F') code |= static_cast<uint32_t>(c - 'A' + 10);
            else return fail("invalid \\u escape");
        }
        return true;
    }

    bool string(std::string& out) {
        ++position_;
        while (true) {
            if (position_ >= text_.size()) return fail("unterminated string");
            char c = text_[position_++];
            if (c == '"') return true;
            if (static_cast<unsigned char>(c) < 0x20) return fail("control character in string");
            if (c != '\\') {
                out.push_back(c);
                continue;
            }
            if (position_ >= text_.size()) return fail("unterminated escape");
            char escape = text_[position_++];
            switch (escape) {
                case '"': out.push_back('"'); break;
                case '\\': out.push_back('\\'); break;
                case '/': out.push_back('/'); break;
                case 'b': out.push_back('\b'); break;
                case 'f': out.push_back('\f'); break;
                case 'n': out.push_back('\n'); break;
                case 'r': out.push_back('\r'); break;
                case 't': out.push_back('\t'); break;
                case 'u': {
                    uint32_t code = 0;
                    if (!hex4(code)) return false;
                    if (code >= 0xD800 && code <= 0xDBFF && position_ + 6 <= text_.size() &&
                        text_[position_] == '\\' && text_[position_ + 1] == 'u') {
                        size_t mark = position_;
                        position_ += 2;
                        uint32_t low = 0;
                        if (!hex4(low)) return false;
                        if (low >= 0xDC00 && low <= 0xDFFF) {
                            code = 0x10000 + ((code - 0xD800) << 10) + (low - 0xDC00);
                        } else {
                            position_ = mark;
                        }
                    }
                    append_utf8(code, out);
                    break;
                }
                default: return fail("invalid escape");
            }
        }
    }

    bool number(Value& out) {
        size_t start = position_;
        bool fractional = false;
        if (text_[position_] == '-') ++position_;
        auto digits = [&]() {
            size_t begin = position_;
            while (position_ < text_.size() && text_[position_] >= '0' && text_[position_] <= '9') ++position_;
            return position_ > begin;
        };
        if (!digits()) return fail("invalid number");
        if (position_ < text_.size() && text_[position_] == '.') {
            fractional = true;
            ++position_;
            if (!digits()) return fail("invalid fraction");
        }
        if (position_ < text_.size() && (text_[position_] == 'e' || text_[position_] == 'E')) {
            fractional = true;
            ++position_;
            if (position_ < text_.size() && (text_[position_] == '+' || text_[position_] == '-')) ++position_;
            if (!digits()) return fail("invalid exponent");
        }
        std::string literal(text_.substr(start, position_ - start));
        if (!fractional) {
            errno = 0;
            char* end = nullptr;
            long long parsed = std::strtoll(literal.c_str(), &end, 10);
            if (errno == 0 && end == literal.c_str() + literal.size()) {
                out = Value::integer(static_cast<int64_t>(parsed));
                return true;
            }
        }
        out = Value::number(std::strtod(literal.c_str(), nullptr));
        return true;
    }

    std::string_view text_;
    size_t position_ = 0;
    std::string error_;
};

void write_double(double value, std::string& out) {
    if (!std::isfinite(value)) {
        out += "null";
        return;
    }
    char buffer[32];
    // The shortest of these precisions that round-trips.
    for (int precision = 15; precision <= 17; ++precision) {
        std::snprintf(buffer, sizeof(buffer), "%.*g", precision, value);
        if (std::strtod(buffer, nullptr) == value) break;
    }
    out += buffer;
    // Keep doubles distinguishable from integers, as Python writes them.
    if (std::strpbrk(buffer, ".eEn") == nullptr) out += ".0";
}

}  // namespace

bool parse_json(std::string_view text, Value& out, std::string& error) {
    return Parser(text).parse(out, error);
}

void write_json_string(std::string_view text, std::string& out) {
    out.push_back('"');
    for (char c : text) {
        switch (c) {
            case '"': out += "\\\""; break;
            case '\\': out += "\\\\"; break;
            case '\n': out += "\\n"; break;
            case '\r': out += "\\r"; break;
            case '\t': out += "\\t"; break;
            case '\b': out += "\\b"; break;
            case '\f': out += "\\f"; break;
            default:
                if (static_cast<unsigned char>(c) < 0x20) {
                    char buffer[8];
                    std::snprintf(buffer, sizeof(buffer), "\\u%04x", static_cast<unsigned char>(c));
                    out += buffer;
                } else {
                    out.push_back(c);
                }
        }
    }
    out.push_back('"');
}

void write_json(const Value& value, std::string& out) {
    switch (value.kind()) {
        case Value::Kind::Null: out += "null"; break;
        case Value::Kind::Bool: out += value.as_bool() ? "true" : "false"; break;
        case Value::Kind::Int: out += std::to_string(value.as_int()); break;
        case Value::Kind::Double: write_double(value.as_double(), out); break;
        case Value::Kind::String: write_json_string(value.as_string(), out); break;
        case Value::Kind::Array: {
            out.push_back('[');
            bool first = true;
            for (const Value& item : value.as_array()) {
                if (!first) out.push_back(',');
                first = false;
                write_json(item, out);
            }
            out.push_back(']');
            break;
        }
        case Value::Kind::Object: {
            out.push_back('{');
            bool first = true;
            for (const auto& [key, item] : value.as_object()) {
                if (!first) out.push_back(',');
                first = false;
                write_json_string(key, out);
                out.push_back(':');
                write_json(item, out);
            }
            out.push_back('}');
            break;
        }
    }
}

std::string to_json(const Value& value) {
    std::string out;
    write_json(value, out);
    return out;
}

// ----------------------------------------------------------------------
// Binary encoding
// ----------------------------------------------------------------------

void ByteWriter::u16(uint16_t value) {
    bytes_.push_back(static_cast<uint8_t>(value));
    bytes_.push_back(static_cast<uint8_t>(value >> 8));
}

void ByteWriter::u32(uint32_t value) {
    for (int i = 0; i < 4; ++i) bytes_.push_back(static_cast<uint8_t>(value >> (8 * i)));
}

void ByteWriter::i64(int64_t value) {
    uint64_t bits = static_cast<uint64_t>(value);
    for (int i = 0; i < 8; ++i) bytes_.push_back(static_cast<uint8_t>(bits >> (8 * i)));
}

void ByteWriter::f64(double value) {
    uint64_t bits = 0;
    std::memcpy(&bits, &value, sizeof(bits));
    for (int i = 0; i < 8; ++i) bytes_.push_back(static_cast<uint8_t>(bits >> (8 * i)));
}

void ByteWriter::str(std::string_view value) {
    u32(static_cast<uint32_t>(value.size()));
    bytes_.insert(bytes_.end(), value.begin(), value.end());
}

void ByteWriter::patch_u32(size_t offset, uint32_t value) {
    for (int i = 0; i < 4; ++i) bytes_[offset + i] = static_cast<uint8_t>(value >> (8 * i));
}

void ByteWriter::value(const Value& value) {
    switch (value.kind()) {
        case Value::Kind::Null: u8(0); break;
        case Value::Kind::Bool: u8(value.as_bool() ? 2 : 1); break;
        case Value::Kind::Int:
            u8(3);
            i64(value.as_int());
            break;
        case Value::Kind::Double:
            u8(4);
            f64(value.as_double());
            break;
        case Value::Kind::String:
            u8(5);
            str(value.as_string());
            break;
        case Value::Kind::Array:
            u8(6);
            u32(static_cast<uint32_t>(value.as_array().size()));
            for (const Value& item : value.as_array()) this->value(item);
            break;
        case Value::Kind::Object:
            u8(7);
            u32(static_cast<uint32_t>(value.as_object().size()));
            for (const auto& [key, item] : value.as_object()) {
                str(key);
                this->value(item);
            }
            break;
    }
}

}  // namespace pn
