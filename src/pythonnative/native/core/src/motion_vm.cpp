#include "motion_vm.h"

#include <algorithm>
#include <cfenv>
#include <cmath>
#include <numbers>
#include <cstdio>
#include <cstring>
#include <limits>

namespace pn::motion {

// ======================================================================
// Values
// ======================================================================

MValue MValue::boolean(bool value) {
    MValue out;
    out.data_ = value;
    return out;
}

MValue MValue::integer(int64_t value) {
    MValue out;
    out.data_ = value;
    return out;
}

MValue MValue::number(double value) {
    MValue out;
    out.data_ = value;
    return out;
}

MValue MValue::string(std::string value) {
    MValue out;
    out.data_ = std::make_shared<const std::string>(std::move(value));
    return out;
}

MValue MValue::seq(Seq items) {
    MValue out;
    out.data_ = std::make_shared<const Seq>(std::move(items));
    return out;
}

MValue MValue::map(Map members) {
    MValue out;
    out.data_ = std::make_shared<const Map>(std::move(members));
    return out;
}

MValue MValue::shared(int64_t id) {
    MValue out;
    out.data_ = SharedRef{id};
    return out;
}

MValue MValue::closure(std::shared_ptr<const Closure> closure) {
    MValue out;
    out.data_ = std::move(closure);
    return out;
}

MValue MValue::intrinsic(int32_t id) {
    MValue out;
    out.data_ = IntrinsicRef{id};
    return out;
}

MValue MValue::python(int64_t id) {
    MValue out;
    out.data_ = PythonRef{id};
    return out;
}

int64_t MValue::as_int() const {
    switch (kind()) {
        case Kind::Bool: return as_bool() ? 1 : 0;
        case Kind::Int: return std::get<int64_t>(data_);
        case Kind::Float: return static_cast<int64_t>(std::get<double>(data_));
        default: return 0;
    }
}

double MValue::as_double() const {
    switch (kind()) {
        case Kind::Bool: return as_bool() ? 1.0 : 0.0;
        case Kind::Int: return static_cast<double>(std::get<int64_t>(data_));
        case Kind::Float: return std::get<double>(data_);
        default: return 0.0;
    }
}

const MValue* MValue::find(std::string_view key) const {
    if (!is_map()) return nullptr;
    for (const auto& [name, value] : as_map()) {
        if (name == key) return &value;
    }
    return nullptr;
}

bool MValue::truthy() const {
    switch (kind()) {
        case Kind::None: return false;
        case Kind::Bool: return as_bool();
        case Kind::Int: return std::get<int64_t>(data_) != 0;
        case Kind::Float: return std::get<double>(data_) != 0.0;
        case Kind::Str: return !as_str().empty();
        case Kind::Seq: return !as_seq().empty();
        case Kind::Map: return !as_map().empty();
        default: return true;
    }
}

const char* MValue::type_name() const {
    switch (kind()) {
        case Kind::None: return "NoneType";
        case Kind::Bool: return "bool";
        case Kind::Int: return "int";
        case Kind::Float: return "float";
        case Kind::Str: return "str";
        case Kind::Seq: return "tuple";
        case Kind::Map: return "dict";
        case Kind::Shared: return "SharedValue";
        case Kind::Closure: return "worklet";
        case Kind::Intrinsic: return "builtin_function_or_method";
        case Kind::Python: return "function";
    }
    return "object";
}

bool equal(const MValue& a, const MValue& b) {
    using Kind = MValue::Kind;
    if (a.is_number() && b.is_number()) {
        if (a.kind() != Kind::Float && b.kind() != Kind::Float) return a.as_int() == b.as_int();
        return a.as_double() == b.as_double();
    }
    if (a.kind() != b.kind()) return false;
    switch (a.kind()) {
        case Kind::None: return true;
        case Kind::Str: return a.as_str() == b.as_str();
        case Kind::Seq: {
            const Seq &x = a.as_seq(), &y = b.as_seq();
            if (x.size() != y.size()) return false;
            for (size_t i = 0; i < x.size(); ++i) {
                if (!equal(x[i], y[i])) return false;
            }
            return true;
        }
        case Kind::Map: {
            const Map &x = a.as_map(), &y = b.as_map();
            if (x.size() != y.size()) return false;
            for (const auto& [key, value] : x) {
                const MValue* other = b.find(key);
                if (other == nullptr || !equal(value, *other)) return false;
            }
            return true;
        }
        case Kind::Shared: return a.shared_id() == b.shared_id();
        case Kind::Closure: return &a.as_closure() == &b.as_closure();
        case Kind::Intrinsic: return a.intrinsic_id() == b.intrinsic_id();
        case Kind::Python: return a.python_id() == b.python_id();
        default: return false;
    }
}

// ======================================================================
// Wire conversion
// ======================================================================

bool from_wire(const Value& value, const ProgramLookup& programs, MValue& out, std::string& error) {
    switch (value.kind()) {
        case Value::Kind::Null: out = MValue(); return true;
        case Value::Kind::Bool: out = MValue::boolean(value.as_bool()); return true;
        case Value::Kind::Int: out = MValue::integer(value.as_int()); return true;
        case Value::Kind::Double: out = MValue::number(value.as_double()); return true;
        case Value::Kind::String: out = MValue::string(value.as_string()); return true;
        case Value::Kind::Array: {
            Seq items;
            items.reserve(value.as_array().size());
            for (const Value& item : value.as_array()) {
                MValue converted;
                if (!from_wire(item, programs, converted, error)) return false;
                items.push_back(std::move(converted));
            }
            out = MValue::seq(std::move(items));
            return true;
        }
        case Value::Kind::Object: {
            const Object& members = value.as_object();
            if (members.size() == 1) {
                const auto& [key, inner] = members.front();
                if (key == "__shared__") {
                    out = MValue::shared(inner.as_int());
                    return true;
                }
                if (key == "__intrinsic__") {
                    int32_t id = inner.is_string() ? intrinsic_id(inner.as_string()) : -1;
                    if (id < 0) {
                        error = "unknown intrinsic " + (inner.is_string() ? inner.as_string() : std::string("?"));
                        return false;
                    }
                    out = MValue::intrinsic(id);
                    return true;
                }
                if (key == "__python__") {
                    out = MValue::python(inner.as_int());
                    return true;
                }
                if (key == "__closure__") {
                    const Value* program = inner.find("program");
                    const Value* captures = inner.find("captures");
                    if (program == nullptr || !program->is_integer()) {
                        error = "a closure needs a program";
                        return false;
                    }
                    auto closure = std::make_shared<Closure>();
                    closure->program = programs ? programs(program->as_int()) : nullptr;
                    if (!closure->program) {
                        error = "unknown worklet program " + std::to_string(program->as_int());
                        return false;
                    }
                    for (const Value& capture : captures != nullptr ? captures->as_array() : Array()) {
                        MValue converted;
                        if (!from_wire(capture, programs, converted, error)) return false;
                        closure->captures.push_back(std::move(converted));
                    }
                    if (static_cast<int>(closure->captures.size()) != closure->program->captures) {
                        error = "worklet " + closure->program->name + " expects " +
                                std::to_string(closure->program->captures) + " captures";
                        return false;
                    }
                    out = MValue::closure(std::move(closure));
                    return true;
                }
            }
            Map converted;
            converted.reserve(members.size());
            for (const auto& [key, item] : members) {
                MValue inner;
                if (!from_wire(item, programs, inner, error)) return false;
                converted.emplace_back(key, std::move(inner));
            }
            out = MValue::map(std::move(converted));
            return true;
        }
    }
    return true;
}

Value to_wire(const MValue& value) {
    using Kind = MValue::Kind;
    switch (value.kind()) {
        case Kind::None: return Value();
        case Kind::Bool: return Value::boolean(value.as_bool());
        case Kind::Int: return Value::integer(value.as_int());
        case Kind::Float: return Value::number(value.as_double());
        case Kind::Str: return Value::string(value.as_str());
        case Kind::Seq: {
            Array items;
            items.reserve(value.as_seq().size());
            for (const MValue& item : value.as_seq()) items.push_back(to_wire(item));
            return Value::array(std::move(items));
        }
        case Kind::Map: {
            Object members;
            members.reserve(value.as_map().size());
            for (const auto& [key, item] : value.as_map()) members.emplace_back(key, to_wire(item));
            return Value::object(std::move(members));
        }
        case Kind::Shared: return Value::object({{"__shared__", Value::integer(value.shared_id())}});
        case Kind::Intrinsic: return Value::object({{"__intrinsic__", Value::string(intrinsic_name(value.intrinsic_id()))}});
        case Kind::Python: return Value::object({{"__python__", Value::integer(value.python_id())}});
        case Kind::Closure: return Value::object({{"__closure__", Value::string(value.as_closure().program->name)}});
    }
    return Value();
}

// ======================================================================
// Programs
// ======================================================================

namespace {

int stack_effect(int32_t op, int32_t arg, bool& ok) {
    ok = true;
    switch (op) {
        case kNop: case kJump: case kUnary: case kValueGet: case kField: case kLen: case kSwap: case kCancel: return 0;
        case kConst: case kLoad: case kCapture: case kDup: return 1;
        case kStore: case kPop: case kIndex: case kBinary: case kCompare: case kJumpIfFalse: case kJumpIfTrue: return -1;
        case kValueSet: return -2;
        case kBuildSeq: return 1 - arg;
        case kBuildMap: return 1 - 2 * arg;
        case kCall: {
            int positional = arg & 0xFF, keywords = (arg >> 8) & 0xFF;
            return -(positional + keywords + (keywords > 0 ? 1 : 0));
        }
        case kReturn: return -1;
        case kUnpack: return arg - 1;
        case kJumpIfFalseOrPop: case kJumpIfTrueOrPop: return -1;  // fallthrough edge
        default: ok = false; return 0;
    }
}

int stack_need(int32_t op, int32_t arg) {
    switch (op) {
        case kStore: case kPop: case kDup: case kValueGet: case kField: case kUnary: case kJumpIfFalse:
        case kJumpIfTrue: case kJumpIfFalseOrPop: case kJumpIfTrueOrPop: case kReturn: case kLen: case kUnpack:
        case kCancel:
            return 1;
        case kSwap: case kIndex: case kBinary: case kCompare: case kValueSet: return 2;
        case kBuildSeq: return arg;
        case kBuildMap: return 2 * arg;
        case kCall: {
            int positional = arg & 0xFF, keywords = (arg >> 8) & 0xFF;
            return 1 + positional + keywords + (keywords > 0 ? 1 : 0);
        }
        default: return 0;
    }
}

}  // namespace

std::shared_ptr<const Program> decode_program(int64_t id, const Value& document, std::string& error) {
    if (!document.is_object()) {
        error = "a worklet program must be an object";
        return nullptr;
    }
    auto program = std::make_shared<Program>();
    program->id = id;
    if (const Value* name = document.find("name"); name != nullptr && name->is_string()) program->name = name->as_string();
    if (const Value* file = document.find("file"); file != nullptr && file->is_string()) program->file = file->as_string();
    if (const Value* line = document.find("line"); line != nullptr && line->is_integer()) program->line = static_cast<int>(line->as_int());
    auto count = [&](const char* key, int& out) {
        const Value* value = document.find(key);
        if (value == nullptr || !value->is_integer() || value->as_int() < 0 || value->as_int() > 4096) {
            error = std::string("worklet program needs a valid ") + key;
            return false;
        }
        out = static_cast<int>(value->as_int());
        return true;
    };
    if (!count("params", program->params) || !count("locals", program->locals) ||
        !count("captures", program->captures)) {
        return nullptr;
    }
    if (program->params > program->locals) {
        error = "a worklet has more parameters than locals";
        return nullptr;
    }
    const Value* consts = document.find("consts");
    const Value* code = document.find("code");
    const Value* lines = document.find("lines");
    if (consts == nullptr || !consts->is_array() || code == nullptr || !code->is_array() || code->as_array().empty() ||
        code->as_array().size() % 2 != 0) {
        error = "worklet program needs consts and code";
        return nullptr;
    }
    for (const Value& item : consts->as_array()) {
        MValue converted;
        if (!from_wire(item, nullptr, converted, error)) return nullptr;
        program->consts.push_back(std::move(converted));
    }
    for (const Value& item : code->as_array()) {
        if (!item.is_integer()) {
            error = "worklet code must be integers";
            return nullptr;
        }
        program->code.push_back(static_cast<int32_t>(item.as_int()));
    }
    size_t count_instructions = program->code.size() / 2;
    if (lines != nullptr && lines->is_array()) {
        for (const Value& item : lines->as_array()) program->lines.push_back(static_cast<int32_t>(item.as_int()));
    }
    program->lines.resize(count_instructions, program->line);

    // Verify: operands, jump targets, and a consistent stack depth on every path.
    std::vector<int> depth(count_instructions, -1);
    std::vector<size_t> pending = {0};
    depth[0] = 0;
    int max_depth = 0;
    auto reject = [&](size_t pc, const std::string& why) {
        error = "invalid worklet " + program->name + " at instruction " + std::to_string(pc) + ": " + why;
        return nullptr;
    };
    auto reach = [&](size_t target, int at, size_t from) -> bool {
        if (target >= count_instructions) {
            error = "invalid worklet " + program->name + " at instruction " + std::to_string(from) + ": jump out of range";
            return false;
        }
        if (depth[target] == -1) {
            depth[target] = at;
            pending.push_back(target);
        } else if (depth[target] != at) {
            error = "invalid worklet " + program->name + " at instruction " + std::to_string(from) + ": inconsistent stack";
            return false;
        }
        return true;
    };
    while (!pending.empty()) {
        size_t pc = pending.back();
        pending.pop_back();
        int32_t op = program->code[pc * 2];
        int32_t arg = program->code[pc * 2 + 1];
        int at = depth[pc];
        if (at < stack_need(op, arg)) return reject(pc, "stack underflow");
        switch (op) {
            case kConst:
                if (arg < 0 || static_cast<size_t>(arg) >= program->consts.size()) return reject(pc, "bad constant");
                break;
            case kField:
                if (arg < 0 || static_cast<size_t>(arg) >= program->consts.size() || !program->consts[arg].is_str()) {
                    return reject(pc, "bad field name");
                }
                break;
            case kLoad: case kStore:
                if (arg < 0 || arg >= program->locals) return reject(pc, "bad local");
                break;
            case kCapture:
                if (arg < 0 || arg >= program->captures) return reject(pc, "bad capture");
                break;
            case kBinary: if (arg < kAdd || arg > kPow) return reject(pc, "bad operator"); break;
            case kCompare: if (arg < kLt || arg > kIsNot) return reject(pc, "bad comparison"); break;
            case kUnary: if (arg < kNeg || arg > kNot) return reject(pc, "bad unary operator"); break;
            case kBuildSeq: case kBuildMap: case kUnpack:
                if (arg < 0 || arg > 1024) return reject(pc, "bad count");
                break;
            case kCall:
                if (arg < 0 || arg > 0xFFFF) return reject(pc, "bad call");
                break;
            default: break;
        }
        bool ok = true;
        int effect = stack_effect(op, arg, ok);
        if (!ok) return reject(pc, "unknown opcode " + std::to_string(op));
        int next = at + effect;
        max_depth = std::max({max_depth, next, at});
        if (max_depth > 512) return reject(pc, "stack too deep");
        if (op == kReturn) continue;
        if (op == kJump) {
            if (!reach(static_cast<size_t>(arg), at, pc)) return nullptr;
            continue;
        }
        if (op == kJumpIfFalse || op == kJumpIfTrue) {
            if (arg < 0 || !reach(static_cast<size_t>(arg), next, pc)) return nullptr;
        } else if (op == kJumpIfFalseOrPop || op == kJumpIfTrueOrPop) {
            if (arg < 0 || !reach(static_cast<size_t>(arg), at, pc)) return nullptr;
        }
        if (pc + 1 >= count_instructions) return reject(pc, "code falls off the end");
        if (!reach(pc + 1, next, pc)) return nullptr;
    }
    program->max_stack = max_depth + 1;
    return program;
}

// ======================================================================
// Python semantics
// ======================================================================

namespace {

using Kind = MValue::Kind;

bool is_int_like(const MValue& v) {
    return v.kind() == Kind::Int || v.kind() == Kind::Bool;
}

WorkletError type_error(std::string message) {
    return {"TypeError", std::move(message)};
}

std::string operand_error(const char* symbol, const MValue& a, const MValue& b) {
    return std::string("unsupported operand type(s) for ") + symbol + ": '" + a.type_name() + "' and '" + b.type_name() + "'";
}

double floor_mod(double a, double b) {
    double r = std::fmod(a, b);
    if (r == 0) return std::copysign(0.0, b);
    if ((r < 0) != (b < 0)) r += b;
    return r;
}

MValue number_result(double value) {
    return MValue::number(value);
}

int compare_strings(const std::string& a, const std::string& b) {
    int r = a.compare(b);
    return r < 0 ? -1 : r > 0 ? 1 : 0;
}

// -1, 0, 1, or 2 when unordered.
bool order(const MValue& a, const MValue& b, int& result, WorkletError& error, const char* symbol) {
    if (a.is_number() && b.is_number()) {
        if (is_int_like(a) && is_int_like(b)) {
            int64_t x = a.as_int(), y = b.as_int();
            result = x < y ? -1 : x > y ? 1 : 0;
        } else {
            double x = a.as_double(), y = b.as_double();
            if (std::isnan(x) || std::isnan(y)) result = 2;
            else result = x < y ? -1 : x > y ? 1 : 0;
        }
        return true;
    }
    if (a.is_str() && b.is_str()) {
        result = compare_strings(a.as_str(), b.as_str());
        return true;
    }
    if (a.is_seq() && b.is_seq()) {
        const Seq &x = a.as_seq(), &y = b.as_seq();
        for (size_t i = 0; i < std::min(x.size(), y.size()); ++i) {
            if (equal(x[i], y[i])) continue;
            return order(x[i], y[i], result, error, symbol);
        }
        result = x.size() < y.size() ? -1 : x.size() > y.size() ? 1 : 0;
        return true;
    }
    error = type_error(std::string("'") + symbol + "' not supported between instances of '" + a.type_name() + "' and '" +
                       b.type_name() + "'");
    return false;
}

// Checked 64-bit arithmetic: true when the result overflows. GCC and Clang
// have builtins; MSVC gets the portable checks.
#if (defined(__GNUC__) || defined(__clang__)) && !defined(PN_PORTABLE_OVERFLOW)
bool add_overflow(int64_t a, int64_t b, int64_t* out) { return __builtin_add_overflow(a, b, out); }
bool sub_overflow(int64_t a, int64_t b, int64_t* out) { return __builtin_sub_overflow(a, b, out); }
bool mul_overflow(int64_t a, int64_t b, int64_t* out) { return __builtin_mul_overflow(a, b, out); }
#else
constexpr int64_t kMin = std::numeric_limits<int64_t>::min();
constexpr int64_t kMax = std::numeric_limits<int64_t>::max();
bool add_overflow(int64_t a, int64_t b, int64_t* out) {
    if ((b > 0 && a > kMax - b) || (b < 0 && a < kMin - b)) return true;
    *out = a + b;
    return false;
}
bool sub_overflow(int64_t a, int64_t b, int64_t* out) {
    if ((b < 0 && a > kMax + b) || (b > 0 && a < kMin + b)) return true;
    *out = a - b;
    return false;
}
bool mul_overflow(int64_t a, int64_t b, int64_t* out) {
    if (a == 0 || b == 0) {
        *out = 0;
        return false;
    }
    if ((a == -1 && b == kMin) || (b == -1 && a == kMin)) return true;
    int64_t product = static_cast<int64_t>(static_cast<uint64_t>(a) * static_cast<uint64_t>(b));
    if (product / b != a) return true;
    *out = product;
    return false;
}
#endif

}  // namespace

bool binary(BinaryOp op, const MValue& a, const MValue& b, MValue& out, WorkletError& error) {
    static const char* symbols[] = {"+", "-", "*", "/", "//", "%", "**"};
    if (a.is_number() && b.is_number()) {
        bool ints = is_int_like(a) && is_int_like(b);
        if (ints) {
            int64_t x = a.as_int(), y = b.as_int(), r = 0;
            switch (op) {
                case kAdd:
                    if (!add_overflow(x, y, &r)) { out = MValue::integer(r); return true; }
                    out = number_result(static_cast<double>(x) + static_cast<double>(y));
                    return true;
                case kSub:
                    if (!sub_overflow(x, y, &r)) { out = MValue::integer(r); return true; }
                    out = number_result(static_cast<double>(x) - static_cast<double>(y));
                    return true;
                case kMul:
                    if (!mul_overflow(x, y, &r)) { out = MValue::integer(r); return true; }
                    out = number_result(static_cast<double>(x) * static_cast<double>(y));
                    return true;
                case kTrueDiv:
                    if (y == 0) { error = {"ZeroDivisionError", "division by zero"}; return false; }
                    out = number_result(static_cast<double>(x) / static_cast<double>(y));
                    return true;
                case kFloorDiv: {
                    if (y == 0) { error = {"ZeroDivisionError", "integer division or modulo by zero"}; return false; }
                    if (x == std::numeric_limits<int64_t>::min() && y == -1) {
                        out = number_result(-static_cast<double>(x));
                        return true;
                    }
                    int64_t q = x / y;
                    if ((x % y != 0) && ((x < 0) != (y < 0))) --q;
                    out = MValue::integer(q);
                    return true;
                }
                case kMod: {
                    if (y == 0) { error = {"ZeroDivisionError", "integer division or modulo by zero"}; return false; }
                    if (y == -1) { out = MValue::integer(0); return true; }
                    int64_t m = x % y;
                    if (m != 0 && ((m < 0) != (y < 0))) m += y;
                    out = MValue::integer(m);
                    return true;
                }
                case kPow: {
                    if (y < 0) {
                        if (x == 0) { error = {"ZeroDivisionError", "0.0 cannot be raised to a negative power"}; return false; }
                        out = number_result(std::pow(static_cast<double>(x), static_cast<double>(y)));
                        return true;
                    }
                    int64_t result = 1, base = x;
                    int64_t exponent = y;
                    bool overflow = false;
                    while (exponent > 0 && !overflow) {
                        if (exponent & 1) overflow = mul_overflow(result, base, &result);
                        exponent >>= 1;
                        if (exponent > 0 && !overflow) overflow = mul_overflow(base, base, &base);
                    }
                    if (overflow) out = number_result(std::pow(static_cast<double>(x), static_cast<double>(y)));
                    else out = MValue::integer(result);
                    return true;
                }
            }
        }
        double x = a.as_double(), y = b.as_double();
        switch (op) {
            case kAdd: out = number_result(x + y); return true;
            case kSub: out = number_result(x - y); return true;
            case kMul: out = number_result(x * y); return true;
            case kTrueDiv:
                if (y == 0) { error = {"ZeroDivisionError", "float division by zero"}; return false; }
                out = number_result(x / y);
                return true;
            case kFloorDiv:
                if (y == 0) { error = {"ZeroDivisionError", "float floor division by zero"}; return false; }
            {
                // CPython's float_floor_div.
                double mod = std::fmod(x, y);
                double div = (x - mod) / y;
                if (mod != 0 && ((y < 0) != (mod < 0))) div -= 1.0;
                double floored = 0;
                if (div != 0) {
                    floored = std::floor(div);
                    if (div - floored > 0.5) floored += 1.0;
                } else {
                    floored = std::copysign(0.0, x / y);
                }
                out = number_result(floored);
                return true;
            }
            case kMod:
                if (y == 0) { error = {"ZeroDivisionError", "float modulo"}; return false; }
                out = number_result(floor_mod(x, y));
                return true;
            case kPow:
                if (x == 0 && y < 0) { error = {"ZeroDivisionError", "0.0 cannot be raised to a negative power"}; return false; }
                if (x < 0 && std::floor(y) != y) { error = {"ValueError", "math domain error"}; return false; }
                out = number_result(std::pow(x, y));
                return true;
        }
    }
    if (op == kAdd && a.is_str() && b.is_str()) {
        out = MValue::string(a.as_str() + b.as_str());
        return true;
    }
    if (op == kAdd && a.is_seq() && b.is_seq()) {
        Seq joined = a.as_seq();
        joined.insert(joined.end(), b.as_seq().begin(), b.as_seq().end());
        out = MValue::seq(std::move(joined));
        return true;
    }
    if (op == kMul && (a.is_seq() || a.is_str() || b.is_seq() || b.is_str())) {
        const MValue& items = a.is_number() ? b : a;
        const MValue& times = a.is_number() ? a : b;
        if (is_int_like(times)) {
            int64_t n = std::max<int64_t>(0, times.as_int());
            if (n > 4096) { error = {"MemoryError", "repetition too large in a worklet"}; return false; }
            if (items.is_str()) {
                std::string text;
                for (int64_t i = 0; i < n; ++i) text += items.as_str();
                out = MValue::string(std::move(text));
            } else {
                Seq repeated;
                for (int64_t i = 0; i < n; ++i) repeated.insert(repeated.end(), items.as_seq().begin(), items.as_seq().end());
                out = MValue::seq(std::move(repeated));
            }
            return true;
        }
    }
    error = type_error(operand_error(symbols[op], a, b));
    return false;
}

bool compare(CompareOp op, const MValue& a, const MValue& b, MValue& out, WorkletError& error) {
    switch (op) {
        case kEq: out = MValue::boolean(equal(a, b)); return true;
        case kNe: out = MValue::boolean(!equal(a, b)); return true;
        case kIs:
        case kIsNot: {
            bool same = a.kind() == b.kind() && (a.is_none() || equal(a, b));
            out = MValue::boolean(op == kIs ? same : !same);
            return true;
        }
        case kIn:
        case kNotIn: {
            bool found = false;
            if (b.is_seq()) {
                for (const MValue& item : b.as_seq()) {
                    if (equal(a, item)) {
                        found = true;
                        break;
                    }
                }
            } else if (b.is_str() && a.is_str()) {
                found = b.as_str().find(a.as_str()) != std::string::npos;
            } else if (b.is_map() && a.is_str()) {
                found = b.find(a.as_str()) != nullptr;
            } else {
                error = type_error(std::string("argument of type '") + b.type_name() + "' is not iterable");
                return false;
            }
            out = MValue::boolean(op == kIn ? found : !found);
            return true;
        }
        default: break;
    }
    static const char* symbols[] = {"<", "<=", "==", "!=", ">", ">="};
    int result = 0;
    if (!order(a, b, result, error, symbols[op])) return false;
    bool value = false;
    if (result != 2) {
        switch (op) {
            case kLt: value = result < 0; break;
            case kLe: value = result <= 0; break;
            case kGt: value = result > 0; break;
            case kGe: value = result >= 0; break;
            default: break;
        }
    }
    out = MValue::boolean(value);
    return true;
}

// ======================================================================
// Colors and interpolation
// ======================================================================

bool parse_color(std::string_view text, double rgba[4]) {
    auto hex = [](char c) -> int {
        if (c >= '0' && c <= '9') return c - '0';
        if (c >= 'a' && c <= 'f') return c - 'a' + 10;
        if (c >= 'A' && c <= 'F') return c - 'A' + 10;
        return -1;
    };
    std::string lowered(text);
    for (char& c : lowered) c = static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
    while (!lowered.empty() && lowered.back() == ' ') lowered.pop_back();
    while (!lowered.empty() && lowered.front() == ' ') lowered.erase(lowered.begin());
    static const std::pair<const char*, uint32_t> named[] = {
        {"black", 0x000000}, {"white", 0xFFFFFF}, {"red", 0xFF0000},   {"green", 0x008000}, {"blue", 0x0000FF},
        {"yellow", 0xFFFF00}, {"orange", 0xFFA500}, {"purple", 0x800080}, {"pink", 0xFFC0CB}, {"gray", 0x808080},
        {"grey", 0x808080},  {"cyan", 0x00FFFF},  {"magenta", 0xFF00FF}, {"lime", 0x00FF00}, {"navy", 0x000080},
        {"teal", 0x008080},  {"silver", 0xC0C0C0}, {"maroon", 0x800000}, {"olive", 0x808000},
    };
    if (lowered == "transparent") {
        rgba[0] = rgba[1] = rgba[2] = 0;
        rgba[3] = 0;
        return true;
    }
    for (const auto& [name, rgb] : named) {
        if (lowered == name) {
            rgba[0] = (rgb >> 16) & 0xFF;
            rgba[1] = (rgb >> 8) & 0xFF;
            rgba[2] = rgb & 0xFF;
            rgba[3] = 1;
            return true;
        }
    }
    if (!lowered.empty() && lowered[0] == '#') {
        std::string digits = lowered.substr(1);
        for (char c : digits) {
            if (hex(c) < 0) return false;
        }
        if (digits.size() == 3) {
            for (int i = 0; i < 3; ++i) rgba[i] = hex(digits[i]) * 17;
            rgba[3] = 1;
            return true;
        }
        auto pair = [&](size_t at) { return hex(digits[at]) * 16 + hex(digits[at + 1]); };
        if (digits.size() == 6) {
            rgba[0] = pair(0);
            rgba[1] = pair(2);
            rgba[2] = pair(4);
            rgba[3] = 1;
            return true;
        }
        if (digits.size() == 8) {  // #AARRGGBB, the Android convention every renderer reads
            rgba[3] = pair(0) / 255.0;
            rgba[0] = pair(2);
            rgba[1] = pair(4);
            rgba[2] = pair(6);
            return true;
        }
        return false;
    }
    bool with_alpha = lowered.rfind("rgba(", 0) == 0;
    if (with_alpha || lowered.rfind("rgb(", 0) == 0) {
        size_t open = lowered.find('('), close = lowered.find(')');
        if (close == std::string::npos) return false;
        std::string inner = lowered.substr(open + 1, close - open - 1);
        double parts[4] = {0, 0, 0, 1};
        int count = 0;
        size_t start = 0;
        while (start <= inner.size() && count < 4) {
            size_t comma = inner.find(',', start);
            std::string token = inner.substr(start, comma == std::string::npos ? std::string::npos : comma - start);
            char* end = nullptr;
            parts[count++] = std::strtod(token.c_str(), &end);
            if (comma == std::string::npos) break;
            start = comma + 1;
        }
        if (count < 3) return false;
        for (int i = 0; i < 4; ++i) rgba[i] = parts[i];
        return true;
    }
    return false;
}

std::string format_color(const double rgba[4]) {
    auto clamp_byte = [](double value) { return static_cast<int>(std::lround(std::min(255.0, std::max(0.0, value)))); };
    char buffer[16];
    std::snprintf(buffer, sizeof(buffer), "#%02X%02X%02X%02X", clamp_byte(rgba[3] * 255.0), clamp_byte(rgba[0]),
                  clamp_byte(rgba[1]), clamp_byte(rgba[2]));
    return buffer;
}

std::string mix_colors(std::string_view from, std::string_view to, double t) {
    double a[4], b[4];
    if (!parse_color(from, a) || !parse_color(to, b)) return std::string(t < 1 ? from : to);
    double mixed[4];
    for (int i = 0; i < 4; ++i) mixed[i] = a[i] + (b[i] - a[i]) * t;
    return format_color(mixed);
}

double interpolate(double x, const std::vector<double>& inputs, const std::vector<double>& outputs,
                   const std::string& left, const std::string& right) {
    if (inputs.size() < 2 || inputs.size() != outputs.size()) return outputs.empty() ? x : outputs.front();
    if (x < inputs.front()) {
        if (left == "identity") return x;
        if (left == "clamp") return outputs.front();
    } else if (x > inputs.back()) {
        if (right == "identity") return x;
        if (right == "clamp") return outputs.back();
    }
    size_t index = 0;
    while (index < inputs.size() - 2 && x >= inputs[index + 1]) ++index;
    double span = inputs[index + 1] - inputs[index];
    double t = span == 0 ? 0 : (x - inputs[index]) / span;
    return outputs[index] + (outputs[index + 1] - outputs[index]) * t;
}

// ======================================================================
// Intrinsics
// ======================================================================

namespace {

const char* const kIntrinsics[] = {
    "abs",          "min",          "max",          "round",       "int",          "float",         "bool",
    "len",          "math.sin",     "math.cos",     "math.tan",    "math.asin",    "math.acos",     "math.atan",
    "math.atan2",   "math.sqrt",    "math.exp",     "math.log",    "math.log10",   "math.log2",     "math.pow",
    "math.floor",   "math.ceil",    "math.fabs",    "math.hypot",  "math.degrees", "math.radians",  "math.copysign",
    "math.fmod",    "math.isfinite", "math.isnan",  "math.isinf",  "math.trunc",   "with_timing",   "with_spring",
    "with_decay",   "with_delay",   "with_sequence", "with_repeat", "interpolate", "interpolate_color", "clamp",
    "snap_point",   "run_on_python",
};
constexpr int32_t kIntrinsicCount = static_cast<int32_t>(sizeof(kIntrinsics) / sizeof(kIntrinsics[0]));

int32_t index_of(std::string_view name) {
    for (int32_t i = 0; i < kIntrinsicCount; ++i) {
        if (name == kIntrinsics[i]) return i;
    }
    return -1;
}

/// Bind `positional` and `keywords` to named parameters; `required` come first.
bool bind(const char* function, const std::vector<std::pair<const char*, const MValue*>>& parameters, size_t required,
          size_t positional_limit, Seq& positional, Map& keywords, std::vector<MValue>& out, WorkletError& error) {
    out.assign(parameters.size(), MValue());
    std::vector<bool> given(parameters.size(), false);
    if (positional.size() > positional_limit) {
        error = type_error(std::string(function) + "() takes at most " + std::to_string(positional_limit) +
                           " positional arguments");
        return false;
    }
    for (size_t i = 0; i < positional.size(); ++i) {
        out[i] = positional[i];
        given[i] = true;
    }
    for (auto& [name, value] : keywords) {
        size_t index = parameters.size();
        for (size_t i = 0; i < parameters.size(); ++i) {
            if (name == parameters[i].first) index = i;
        }
        if (index == parameters.size()) {
            error = type_error(std::string(function) + "() got an unexpected keyword argument '" + name + "'");
            return false;
        }
        if (given[index]) {
            error = type_error(std::string(function) + "() got multiple values for argument '" + name + "'");
            return false;
        }
        out[index] = value;
        given[index] = true;
    }
    for (size_t i = 0; i < parameters.size(); ++i) {
        if (given[i]) continue;
        if (i < required) {
            error = type_error(std::string(function) + "() missing required argument: '" + parameters[i].first + "'");
            return false;
        }
        if (parameters[i].second != nullptr) out[i] = *parameters[i].second;
    }
    return true;
}

bool numeric(const char* function, const MValue& value, WorkletError& error) {
    if (value.is_number()) return true;
    error = type_error(std::string(function) + "() needs a number, not '" + value.type_name() + "'");
    return false;
}

std::vector<double> numbers(const MValue& value, bool& ok) {
    std::vector<double> out;
    ok = value.is_seq();
    if (!ok) return out;
    for (const MValue& item : value.as_seq()) {
        if (!item.is_number()) {
            ok = false;
            return out;
        }
        out.push_back(item.as_double());
    }
    return out;
}

MValue animation(const char* type, std::vector<std::pair<const char*, MValue>> fields) {
    Map members;
    members.emplace_back("__animation__", MValue::boolean(true));
    members.emplace_back("type", MValue::string(type));
    for (auto& [key, value] : fields) members.emplace_back(key, std::move(value));
    return MValue::map(std::move(members));
}

}  // namespace

int32_t intrinsic_id(std::string_view name) {
    return index_of(name);
}

const char* intrinsic_name(int32_t id) {
    return id >= 0 && id < kIntrinsicCount ? kIntrinsics[id] : "?";
}

bool VM::intrinsic(int32_t id, Seq& positional, Map& keywords, MValue& result, WorkletError& error) {
    std::string_view name = intrinsic_name(id);
    auto no_keywords = [&]() {
        if (keywords.empty()) return true;
        error = type_error(std::string(name) + "() takes no keyword arguments");
        return false;
    };
    auto arity = [&](size_t low, size_t high) {
        if (positional.size() >= low && positional.size() <= high) return true;
        error = type_error(std::string(name) + "() takes " + std::to_string(low) +
                           (low == high ? "" : " to " + std::to_string(high)) + " arguments (" +
                           std::to_string(positional.size()) + " given)");
        return false;
    };
    static const MValue none;
    static const MValue system = MValue::string("system");
    if (name == "abs") {
        if (!no_keywords() || !arity(1, 1) || !numeric("abs", positional[0], error)) return false;
        const MValue& x = positional[0];
        result = x.kind() == MValue::Kind::Float ? MValue::number(std::fabs(x.as_double()))
                                                 : MValue::integer(x.as_int() < 0 ? -x.as_int() : x.as_int());
        return true;
    }
    if (name == "min" || name == "max") {
        if (!no_keywords()) return false;
        const Seq* items = &positional;
        if (positional.size() == 1 && positional[0].is_seq()) items = &positional[0].as_seq();
        if (items->empty()) {
            error = {"ValueError", std::string(name) + "() arg is an empty sequence"};
            return false;
        }
        MValue best = items->front();
        for (size_t i = 1; i < items->size(); ++i) {
            MValue less;
            if (!compare(kLt, (*items)[i], best, less, error)) return false;
            MValue greater;
            if (!compare(kGt, (*items)[i], best, greater, error)) return false;
            if ((name == "min" && less.as_bool()) || (name == "max" && greater.as_bool())) best = (*items)[i];
        }
        result = best;
        return true;
    }
    if (name == "round") {
        if (!no_keywords() || !arity(1, 2) || !numeric("round", positional[0], error)) return false;
        const MValue& x = positional[0];
        bool digits = positional.size() == 2 && !positional[1].is_none();
        int saved = std::fegetround();
        std::fesetround(FE_TONEAREST);
        if (!digits) {
            result = x.kind() == MValue::Kind::Float ? MValue::integer(static_cast<int64_t>(std::nearbyint(x.as_double())))
                                                     : MValue::integer(x.as_int());
        } else {
            if (!numeric("round", positional[1], error)) return false;
            double scale = std::pow(10.0, static_cast<double>(positional[1].as_int()));
            double rounded = std::nearbyint(x.as_double() * scale) / scale;
            result = x.kind() == MValue::Kind::Float ? MValue::number(rounded) : MValue::integer(static_cast<int64_t>(rounded));
        }
        std::fesetround(saved);
        return true;
    }
    if (name == "int") {
        if (!no_keywords() || !arity(0, 1)) return false;
        if (positional.empty()) {
            result = MValue::integer(0);
            return true;
        }
        if (!numeric("int", positional[0], error)) return false;
        double x = positional[0].as_double();
        if (!std::isfinite(x)) {
            error = {"ValueError", "cannot convert float infinity or NaN to integer"};
            return false;
        }
        result = positional[0].kind() == MValue::Kind::Float ? MValue::integer(static_cast<int64_t>(std::trunc(x)))
                                                             : MValue::integer(positional[0].as_int());
        return true;
    }
    if (name == "float") {
        if (!no_keywords() || !arity(0, 1)) return false;
        if (positional.empty()) {
            result = MValue::number(0);
            return true;
        }
        if (!numeric("float", positional[0], error)) return false;
        result = MValue::number(positional[0].as_double());
        return true;
    }
    if (name == "bool") {
        if (!no_keywords() || !arity(0, 1)) return false;
        result = MValue::boolean(!positional.empty() && positional[0].truthy());
        return true;
    }
    if (name == "len") {
        if (!no_keywords() || !arity(1, 1)) return false;
        const MValue& x = positional[0];
        if (x.is_seq()) result = MValue::integer(static_cast<int64_t>(x.as_seq().size()));
        else if (x.is_str()) result = MValue::integer(static_cast<int64_t>(x.as_str().size()));
        else if (x.is_map()) result = MValue::integer(static_cast<int64_t>(x.as_map().size()));
        else {
            error = type_error(std::string("object of type '") + x.type_name() + "' has no len()");
            return false;
        }
        return true;
    }
    if (name.rfind("math.", 0) == 0) {
        if (!no_keywords()) return false;
        std::string_view fn = name.substr(5);
        bool two = fn == "atan2" || fn == "pow" || fn == "copysign" || fn == "fmod";
        if (fn == "log") {
            if (!arity(1, 2)) return false;
        } else if (fn == "hypot") {
            if (!arity(1, 16)) return false;
        } else if (!arity(two ? 2 : 1, two ? 2 : 1)) {
            return false;
        }
        for (const MValue& item : positional) {
            if (!numeric(std::string(name).c_str(), item, error)) return false;
        }
        double x = positional[0].as_double();
        double y = positional.size() > 1 ? positional[1].as_double() : 0;
        auto domain = [&]() {
            error = {"ValueError", "math domain error"};
            return false;
        };
        if (fn == "sin") result = MValue::number(std::sin(x));
        else if (fn == "cos") result = MValue::number(std::cos(x));
        else if (fn == "tan") result = MValue::number(std::tan(x));
        else if (fn == "asin") { if (x < -1 || x > 1) return domain(); result = MValue::number(std::asin(x)); }
        else if (fn == "acos") { if (x < -1 || x > 1) return domain(); result = MValue::number(std::acos(x)); }
        else if (fn == "atan") result = MValue::number(std::atan(x));
        else if (fn == "atan2") result = MValue::number(std::atan2(x, y));
        else if (fn == "sqrt") { if (x < 0) return domain(); result = MValue::number(std::sqrt(x)); }
        else if (fn == "exp") result = MValue::number(std::exp(x));
        else if (fn == "log") {
            if (x <= 0 || (positional.size() > 1 && (y <= 0 || y == 1))) return domain();
            result = MValue::number(positional.size() > 1 ? std::log(x) / std::log(y) : std::log(x));
        } else if (fn == "log10") { if (x <= 0) return domain(); result = MValue::number(std::log10(x)); }
        else if (fn == "log2") { if (x <= 0) return domain(); result = MValue::number(std::log2(x)); }
        else if (fn == "pow") {
            if (x < 0 && std::floor(y) != y) return domain();
            result = MValue::number(std::pow(x, y));
        } else if (fn == "floor") result = MValue::integer(static_cast<int64_t>(std::floor(x)));
        else if (fn == "ceil") result = MValue::integer(static_cast<int64_t>(std::ceil(x)));
        else if (fn == "trunc") result = MValue::integer(static_cast<int64_t>(std::trunc(x)));
        else if (fn == "fabs") result = MValue::number(std::fabs(x));
        else if (fn == "hypot") {
            double total = 0;
            for (const MValue& item : positional) total += item.as_double() * item.as_double();
            result = MValue::number(std::sqrt(total));
        } else if (fn == "degrees") result = MValue::number(x * 180.0 / std::numbers::pi);
        else if (fn == "radians") result = MValue::number(x * std::numbers::pi / 180.0);
        else if (fn == "copysign") result = MValue::number(std::copysign(x, y));
        else if (fn == "fmod") { if (y == 0) return domain(); result = MValue::number(std::fmod(x, y)); }
        else if (fn == "isfinite") result = MValue::boolean(std::isfinite(x));
        else if (fn == "isnan") result = MValue::boolean(std::isnan(x));
        else if (fn == "isinf") result = MValue::boolean(std::isinf(x));
        else {
            error = {"NameError", std::string(name) + " isn't available in worklets"};
            return false;
        }
        return true;
    }
    std::vector<MValue> args;
    if (name == "with_timing") {
        static const MValue duration = MValue::integer(300);
        if (!bind("with_timing", {{"to", nullptr}, {"duration", &duration}, {"easing", &none}, {"reduce_motion", &system},
                                  {"on_finish", &none}},
                  1, 1, positional, keywords, args, error)) {
            return false;
        }
        result = animation("timing", {{"to", args[0]}, {"duration", args[1]}, {"easing", args[2]},
                                      {"reduce_motion", args[3]}, {"on_finish", args[4]}});
        return true;
    }
    if (name == "with_spring") {
        static const MValue damping = MValue::integer(10), stiffness = MValue::integer(100), mass = MValue::integer(1),
                            zero = MValue::integer(0), no = MValue::boolean(false), displacement = MValue::number(0.01),
                            speed = MValue::integer(2);
        if (!bind("with_spring",
                  {{"to", nullptr}, {"damping", &damping}, {"stiffness", &stiffness}, {"mass", &mass},
                   {"velocity", &zero}, {"overshoot_clamping", &no}, {"rest_displacement", &displacement},
                   {"rest_speed", &speed}, {"duration", &none}, {"damping_ratio", &none}, {"reduce_motion", &system},
                   {"on_finish", &none}},
                  1, 1, positional, keywords, args, error)) {
            return false;
        }
        result = animation("spring", {{"to", args[0]}, {"damping", args[1]}, {"stiffness", args[2]}, {"mass", args[3]},
                                      {"velocity", args[4]}, {"overshoot_clamping", args[5]},
                                      {"rest_displacement", args[6]}, {"rest_speed", args[7]}, {"duration", args[8]},
                                      {"damping_ratio", args[9]}, {"reduce_motion", args[10]}, {"on_finish", args[11]}});
        return true;
    }
    if (name == "with_decay") {
        static const MValue deceleration = MValue::number(0.998), rubber = MValue::number(0.6);
        if (!bind("with_decay", {{"velocity", nullptr}, {"deceleration", &deceleration}, {"clamp", &none},
                                 {"rubber_band_factor", &rubber}, {"reduce_motion", &system}, {"on_finish", &none}},
                  1, 0, positional, keywords, args, error)) {
            return false;
        }
        result = animation("decay", {{"velocity", args[0]}, {"deceleration", args[1]}, {"clamp", args[2]},
                                     {"rubber_band_factor", args[3]}, {"reduce_motion", args[4]}, {"on_finish", args[5]}});
        return true;
    }
    if (name == "with_delay") {
        if (!bind("with_delay", {{"delay_ms", nullptr}, {"animation", nullptr}, {"reduce_motion", &system}}, 2, 2,
                  positional, keywords, args, error)) {
            return false;
        }
        result = animation("delay", {{"delay", args[0]}, {"animation", args[1]}, {"reduce_motion", args[2]}});
        return true;
    }
    if (name == "with_sequence") {
        if (!no_keywords()) return false;
        result = animation("sequence", {{"animations", MValue::seq(positional)}});
        return true;
    }
    if (name == "with_repeat") {
        static const MValue no = MValue::boolean(false);
        if (!bind("with_repeat",
                  {{"animation", nullptr}, {"times", &none}, {"reverse", &no}, {"on_finish", &none},
                   {"reduce_motion", &system}},
                  1, 1, positional, keywords, args, error)) {
            return false;
        }
        result = animation("repeat", {{"animation", args[0]}, {"times", args[1]}, {"reverse", args[2]},
                                      {"on_finish", args[3]}, {"reduce_motion", args[4]}});
        return true;
    }
    if (name == "interpolate") {
        static const MValue extend = MValue::string("extend");
        if (!bind("interpolate", {{"x", nullptr}, {"input_range", nullptr}, {"output_range", nullptr}, {"extrapolate", &extend}},
                  3, 4, positional, keywords, args, error)) {
            return false;
        }
        if (!numeric("interpolate", args[0], error)) return false;
        bool ok_in = false, ok_out = false;
        std::vector<double> inputs = numbers(args[1], ok_in), outputs = numbers(args[2], ok_out);
        if (!ok_in || !ok_out || inputs.size() < 2 || inputs.size() != outputs.size()) {
            error = {"ValueError", "interpolate() needs input and output ranges of the same length, at least 2"};
            return false;
        }
        std::string left = "extend", right = "extend";
        if (args[3].is_str()) left = right = args[3].as_str();
        else if (args[3].is_seq() && args[3].as_seq().size() == 2 && args[3].as_seq()[0].is_str() &&
                 args[3].as_seq()[1].is_str()) {
            left = args[3].as_seq()[0].as_str();
            right = args[3].as_seq()[1].as_str();
        }
        for (const std::string* mode : {&left, &right}) {
            if (*mode != "extend" && *mode != "clamp" && *mode != "identity") {
                error = {"ValueError", "extrapolate must be 'extend', 'clamp', or 'identity'"};
                return false;
            }
        }
        result = MValue::number(interpolate(args[0].as_double(), inputs, outputs, left, right));
        return true;
    }
    if (name == "interpolate_color") {
        if (!bind("interpolate_color", {{"x", nullptr}, {"input_range", nullptr}, {"colors", nullptr}}, 3, 3, positional,
                  keywords, args, error)) {
            return false;
        }
        if (!numeric("interpolate_color", args[0], error)) return false;
        bool ok = false;
        std::vector<double> inputs = numbers(args[1], ok);
        if (!ok || !args[2].is_seq() || inputs.size() < 2 || inputs.size() != args[2].as_seq().size()) {
            error = {"ValueError", "interpolate_color() needs an input range and as many colors, at least 2"};
            return false;
        }
        double x = std::min(inputs.back(), std::max(inputs.front(), args[0].as_double()));
        size_t index = 0;
        while (index < inputs.size() - 2 && x >= inputs[index + 1]) ++index;
        double span = inputs[index + 1] - inputs[index];
        double t = span == 0 ? 0 : (x - inputs[index]) / span;
        const MValue &from = args[2].as_seq()[index], &to = args[2].as_seq()[index + 1];
        if (!from.is_str() || !to.is_str()) {
            error = type_error("interpolate_color() colors must be strings");
            return false;
        }
        double a[4], b[4];
        if (!parse_color(from.as_str(), a) || !parse_color(to.as_str(), b)) {
            error = {"ValueError", "interpolate_color() can't read color " + from.as_str() + " or " + to.as_str()};
            return false;
        }
        result = MValue::string(mix_colors(from.as_str(), to.as_str(), t));
        return true;
    }
    if (name == "clamp") {
        if (!bind("clamp", {{"x", nullptr}, {"lower", nullptr}, {"upper", nullptr}}, 3, 3, positional, keywords, args, error)) {
            return false;
        }
        for (const MValue& item : args) {
            if (!numeric("clamp", item, error)) return false;
        }
        MValue below, above;
        compare(kLt, args[0], args[1], below, error);
        compare(kGt, args[0], args[2], above, error);
        result = below.as_bool() ? args[1] : above.as_bool() ? args[2] : args[0];
        return true;
    }
    if (name == "snap_point") {
        if (!bind("snap_point", {{"value", nullptr}, {"velocity", nullptr}, {"points", nullptr}}, 3, 3, positional, keywords,
                  args, error)) {
            return false;
        }
        if (!numeric("snap_point", args[0], error) || !numeric("snap_point", args[1], error)) return false;
        bool ok = false;
        std::vector<double> points = numbers(args[2], ok);
        if (!ok || points.empty()) {
            error = {"ValueError", "snap_point() needs at least one point"};
            return false;
        }
        double projected = args[0].as_double() + 0.2 * args[1].as_double();
        size_t best = 0;
        for (size_t i = 1; i < points.size(); ++i) {
            if (std::fabs(points[i] - projected) < std::fabs(points[best] - projected)) best = i;
        }
        result = args[2].as_seq()[best];
        return true;
    }
    if (name == "run_on_python") {
        if (!no_keywords()) return false;
        if (positional.empty() || positional[0].kind() != MValue::Kind::Python) {
            error = type_error("run_on_python() needs a Python callable captured by the worklet");
            return false;
        }
        Seq rest(positional.begin() + 1, positional.end());
        for (const MValue& item : rest) {
            auto kind = item.kind();
            if (kind == MValue::Kind::Closure || kind == MValue::Kind::Intrinsic || kind == MValue::Kind::Python) {
                error = type_error("run_on_python() arguments must be values, not functions");
                return false;
            }
        }
        host_.call_python(positional[0].python_id(), rest);
        result = MValue();
        return true;
    }
    error = {"NameError", std::string(name) + " isn't available in worklets"};
    return false;
}

// ======================================================================
// The interpreter
// ======================================================================

bool VM::run(const Closure& closure, const Seq& args, MValue& result, Failure& failure) {
    steps_ = 0;
    return execute(closure, args, result, failure, 0);
}

bool VM::call(const MValue& callee, Seq& positional, Map& keywords, MValue& result, Failure& failure, int depth) {
    switch (callee.kind()) {
        case MValue::Kind::Closure:
            if (!keywords.empty()) {
                failure.error = type_error("worklets take positional arguments only");
                return false;
            }
            return execute(callee.as_closure(), positional, result, failure, depth + 1);
        case MValue::Kind::Intrinsic:
            return intrinsic(callee.intrinsic_id(), positional, keywords, result, failure.error);
        case MValue::Kind::Python:
            failure.error = type_error("a worklet can't call a Python function directly; use run_on_python()");
            return false;
        default:
            failure.error = type_error(std::string("'") + callee.type_name() + "' object is not callable");
            return false;
    }
}

bool VM::execute(const Closure& closure, const Seq& args, MValue& result, Failure& failure, int depth) {
    const Program& program = *closure.program;
    auto fail_here = [&](size_t pc) {
        if (failure.name.empty()) {
            failure.name = program.name;
            failure.file = program.file;
            failure.line = pc < program.lines.size() ? program.lines[pc] : program.line;
        }
        return false;
    };
    if (depth > 32) {
        failure.error = {"RecursionError", "worklet calls nest too deeply"};
        return fail_here(0);
    }
    if (static_cast<int>(args.size()) != program.params) {
        failure.error = type_error(program.name + "() takes " + std::to_string(program.params) + " arguments (" +
                                   std::to_string(args.size()) + " given)");
        return fail_here(0);
    }
    std::vector<MValue> locals(static_cast<size_t>(program.locals));
    for (size_t i = 0; i < args.size(); ++i) locals[i] = args[i];
    std::vector<MValue> stack;
    stack.reserve(static_cast<size_t>(program.max_stack));
    auto pop = [&]() {
        MValue top = std::move(stack.back());
        stack.pop_back();
        return top;
    };
    size_t pc = 0;
    const size_t count = program.code.size() / 2;
    while (pc < count) {
        if (++steps_ > kBudget) {
            failure.error = {"RuntimeError", "worklet exceeded its instruction budget"};
            return fail_here(pc);
        }
        const int32_t op = program.code[pc * 2];
        const int32_t arg = program.code[pc * 2 + 1];
        size_t next = pc + 1;
        switch (op) {
            case kNop: break;
            case kConst: stack.push_back(program.consts[static_cast<size_t>(arg)]); break;
            case kLoad: stack.push_back(locals[static_cast<size_t>(arg)]); break;
            case kStore: locals[static_cast<size_t>(arg)] = pop(); break;
            case kCapture: stack.push_back(closure.captures[static_cast<size_t>(arg)]); break;
            case kPop: stack.pop_back(); break;
            case kDup: stack.push_back(stack.back()); break;
            case kSwap: std::swap(stack[stack.size() - 1], stack[stack.size() - 2]); break;
            case kValueGet: {
                MValue target = pop();
                if (target.kind() != MValue::Kind::Shared) {
                    failure.error = {"AttributeError", std::string("'") + target.type_name() + "' object has no attribute 'value'"};
                    return fail_here(pc);
                }
                stack.push_back(host_.read_shared(target.shared_id()));
                break;
            }
            case kValueSet: {
                MValue value = pop();
                MValue target = pop();
                if (target.kind() != MValue::Kind::Shared) {
                    failure.error = {"AttributeError", std::string("can't set 'value' on '") + target.type_name() + "'"};
                    return fail_here(pc);
                }
                host_.write_shared(target.shared_id(), value);
                break;
            }
            case kCancel: {
                MValue target = pop();
                if (target.kind() != MValue::Kind::Shared) {
                    failure.error = {"AttributeError", std::string("'") + target.type_name() + "' object has no attribute 'cancel'"};
                    return fail_here(pc);
                }
                host_.cancel_shared(target.shared_id());
                stack.push_back(MValue());
                break;
            }
            case kField: {
                MValue object = pop();
                const std::string& field = program.consts[static_cast<size_t>(arg)].as_str();
                const MValue* found = object.find(field);
                if (found == nullptr) {
                    failure.error = {"AttributeError", std::string("'") + object.type_name() + "' object has no attribute '" + field + "'"};
                    return fail_here(pc);
                }
                stack.push_back(*found);
                break;
            }
            case kIndex: {
                MValue index = pop();
                MValue object = pop();
                if (object.is_seq() || object.is_str()) {
                    if (!is_int_like(index)) {
                        failure.error = type_error("indices must be integers");
                        return fail_here(pc);
                    }
                    int64_t size = object.is_seq() ? static_cast<int64_t>(object.as_seq().size())
                                                   : static_cast<int64_t>(object.as_str().size());
                    int64_t at = index.as_int();
                    if (at < 0) at += size;
                    if (at < 0 || at >= size) {
                        failure.error = {"IndexError", "index out of range"};
                        return fail_here(pc);
                    }
                    if (object.is_seq()) stack.push_back(object.as_seq()[static_cast<size_t>(at)]);
                    else stack.push_back(MValue::string(std::string(1, object.as_str()[static_cast<size_t>(at)])));
                } else if (object.is_map() && index.is_str()) {
                    const MValue* found = object.find(index.as_str());
                    if (found == nullptr) {
                        failure.error = {"KeyError", "'" + index.as_str() + "'"};
                        return fail_here(pc);
                    }
                    stack.push_back(*found);
                } else {
                    failure.error = type_error(std::string("'") + object.type_name() + "' object is not subscriptable");
                    return fail_here(pc);
                }
                break;
            }
            case kBinary: {
                MValue b = pop();
                MValue a = pop();
                MValue out;
                if (!binary(static_cast<BinaryOp>(arg), a, b, out, failure.error)) return fail_here(pc);
                stack.push_back(std::move(out));
                break;
            }
            case kCompare: {
                MValue b = pop();
                MValue a = pop();
                MValue out;
                if (!compare(static_cast<CompareOp>(arg), a, b, out, failure.error)) return fail_here(pc);
                stack.push_back(std::move(out));
                break;
            }
            case kUnary: {
                MValue a = pop();
                if (arg == kNot) {
                    stack.push_back(MValue::boolean(!a.truthy()));
                } else if (!a.is_number()) {
                    failure.error = type_error(std::string("bad operand type for unary ") + (arg == kNeg ? "-" : "+") + ": '" +
                                               a.type_name() + "'");
                    return fail_here(pc);
                } else if (arg == kNeg) {
                    stack.push_back(a.kind() == MValue::Kind::Float ? MValue::number(-a.as_double()) : MValue::integer(-a.as_int()));
                } else {
                    stack.push_back(a.kind() == MValue::Kind::Float ? a : MValue::integer(a.as_int()));
                }
                break;
            }
            case kJump: next = static_cast<size_t>(arg); break;
            case kJumpIfFalse:
                if (!pop().truthy()) next = static_cast<size_t>(arg);
                break;
            case kJumpIfTrue:
                if (pop().truthy()) next = static_cast<size_t>(arg);
                break;
            case kJumpIfFalseOrPop:
                if (!stack.back().truthy()) next = static_cast<size_t>(arg);
                else stack.pop_back();
                break;
            case kJumpIfTrueOrPop:
                if (stack.back().truthy()) next = static_cast<size_t>(arg);
                else stack.pop_back();
                break;
            case kBuildSeq: {
                Seq items(stack.end() - arg, stack.end());
                stack.resize(stack.size() - static_cast<size_t>(arg));
                stack.push_back(MValue::seq(std::move(items)));
                break;
            }
            case kBuildMap: {
                Map members;
                members.reserve(static_cast<size_t>(arg));
                size_t base = stack.size() - static_cast<size_t>(2 * arg);
                for (int i = 0; i < arg; ++i) {
                    const MValue& key = stack[base + static_cast<size_t>(2 * i)];
                    if (!key.is_str()) {
                        failure.error = type_error("worklet dict keys must be strings");
                        return fail_here(pc);
                    }
                    bool replaced = false;
                    for (auto& member : members) {
                        if (member.first == key.as_str()) {
                            member.second = stack[base + static_cast<size_t>(2 * i + 1)];
                            replaced = true;
                        }
                    }
                    if (!replaced) members.emplace_back(key.as_str(), stack[base + static_cast<size_t>(2 * i + 1)]);
                }
                stack.resize(base);
                stack.push_back(MValue::map(std::move(members)));
                break;
            }
            case kCall: {
                int positional = arg & 0xFF, keywords = (arg >> 8) & 0xFF;
                Map named;
                if (keywords > 0) {
                    MValue names = pop();
                    if (!names.is_seq() || static_cast<int>(names.as_seq().size()) != keywords) {
                        failure.error = type_error("malformed keyword call");
                        return fail_here(pc);
                    }
                    size_t base = stack.size() - static_cast<size_t>(keywords);
                    for (int i = 0; i < keywords; ++i) {
                        named.emplace_back(names.as_seq()[static_cast<size_t>(i)].as_str(), stack[base + static_cast<size_t>(i)]);
                    }
                    stack.resize(base);
                }
                Seq values(stack.end() - positional, stack.end());
                stack.resize(stack.size() - static_cast<size_t>(positional));
                MValue callee = pop();
                MValue out;
                if (!call(callee, values, named, out, failure, depth)) return fail_here(pc);
                stack.push_back(std::move(out));
                break;
            }
            case kReturn:
                result = pop();
                return true;
            case kLen: {
                Seq one = {pop()};
                Map none;
                MValue out;
                if (!intrinsic(intrinsic_id("len"), one, none, out, failure.error)) return fail_here(pc);
                stack.push_back(std::move(out));
                break;
            }
            case kUnpack: {
                MValue items = pop();
                if (!items.is_seq()) {
                    failure.error = type_error(std::string("cannot unpack non-iterable ") + items.type_name() + " object");
                    return fail_here(pc);
                }
                if (static_cast<int>(items.as_seq().size()) != arg) {
                    failure.error = {"ValueError", "expected " + std::to_string(arg) + " values to unpack, got " +
                                                       std::to_string(items.as_seq().size())};
                    return fail_here(pc);
                }
                for (size_t i = items.as_seq().size(); i-- > 0;) stack.push_back(items.as_seq()[i]);
                break;
            }
            default:
                failure.error = {"SystemError", "unknown opcode"};
                return fail_here(pc);
        }
        pc = next;
    }
    result = MValue();
    return true;
}

}  // namespace pn::motion
