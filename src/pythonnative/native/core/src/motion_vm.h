// Worklets: the verified bytecode Python compiles worklet functions into
// (RFC 0009), the values it computes with, and the interpreter that runs it
// on the UI thread.
//
// `pythonnative.motion.compiler` emits a program as JSON: constants, a
// capture count, flat `[op, arg, op, arg, ...]` code, and a source line per
// instruction. The core verifies every program before it can run (operand
// indices, jump targets, stack depth) and gives each run an instruction
// budget, so a bad or runaway program fails one binding instead of the UI
// thread. Values follow Python's semantics for the subset worklets use:
// integers stay integers, `//` and `%` floor, `round` rounds half to even,
// and type errors raise.
#pragma once

#include <cstdint>
#include <functional>
#include <memory>
#include <string>
#include <string_view>
#include <unordered_map>
#include <utility>
#include <variant>
#include <vector>

#include "value.h"

namespace pn::motion {

struct Program;
struct Closure;
class MValue;

using Seq = std::vector<MValue>;
using Map = std::vector<std::pair<std::string, MValue>>;

struct SharedRef {
    int64_t id = 0;
};
struct IntrinsicRef {
    int32_t id = 0;
};
struct PythonRef {
    int64_t id = 0;
};

/// One worklet value.
class MValue {
public:
    enum class Kind : uint8_t { None, Bool, Int, Float, Str, Seq, Map, Shared, Closure, Intrinsic, Python };

    MValue() = default;
    static MValue boolean(bool value);
    static MValue integer(int64_t value);
    static MValue number(double value);
    static MValue string(std::string value);
    static MValue seq(Seq items);
    static MValue map(Map members);
    static MValue shared(int64_t id);
    static MValue closure(std::shared_ptr<const Closure> closure);
    static MValue intrinsic(int32_t id);
    static MValue python(int64_t id);

    Kind kind() const { return static_cast<Kind>(data_.index()); }
    bool is_none() const { return kind() == Kind::None; }
    bool is_number() const { return kind() == Kind::Int || kind() == Kind::Float || kind() == Kind::Bool; }
    bool is_str() const { return kind() == Kind::Str; }
    bool is_seq() const { return kind() == Kind::Seq; }
    bool is_map() const { return kind() == Kind::Map; }

    bool as_bool() const { return std::get<bool>(data_); }
    int64_t as_int() const;  // Bool, Int (Float truncates)
    double as_double() const;  // any number
    const std::string& as_str() const { return *std::get<std::shared_ptr<const std::string>>(data_); }
    const Seq& as_seq() const { return *std::get<std::shared_ptr<const Seq>>(data_); }
    const Map& as_map() const { return *std::get<std::shared_ptr<const Map>>(data_); }
    int64_t shared_id() const { return std::get<SharedRef>(data_).id; }
    const Closure& as_closure() const { return *std::get<std::shared_ptr<const Closure>>(data_); }
    std::shared_ptr<const Closure> closure_ptr() const { return std::get<std::shared_ptr<const Closure>>(data_); }
    int32_t intrinsic_id() const { return std::get<IntrinsicRef>(data_).id; }
    int64_t python_id() const { return std::get<PythonRef>(data_).id; }

    /// The member named `key` of a map, or nullptr.
    const MValue* find(std::string_view key) const;
    /// Python truthiness.
    bool truthy() const;
    /// Python's type name, for error messages.
    const char* type_name() const;

private:
    std::variant<std::monostate, bool, int64_t, double, std::shared_ptr<const std::string>, std::shared_ptr<const Seq>,
                 std::shared_ptr<const Map>, SharedRef, std::shared_ptr<const Closure>, IntrinsicRef, PythonRef>
        data_;
};

/// Python `==` (numbers compare by value; sequences and maps deeply).
bool equal(const MValue& a, const MValue& b);

/// A worklet raised: `TypeError`, `ZeroDivisionError`, and so on.
struct WorkletError {
    std::string type;
    std::string message;
};

/// Opcodes. Each instruction is `[op, arg]`; see `pythonnative/motion/program.py`.
enum Op : int32_t {
    kNop = 0,
    kConst = 1,       // push consts[arg]
    kLoad = 2,        // push locals[arg]
    kStore = 3,       // locals[arg] = pop
    kCapture = 4,     // push captures[arg]
    kPop = 5,
    kDup = 6,
    kSwap = 7,
    kValueGet = 8,    // shared -> its value
    kValueSet = 9,    // value, shared -> write (an animation starts it)
    kField = 10,      // obj -> obj[consts[arg]] (event fields and map keys)
    kIndex = 11,      // seq, index -> item
    kBinary = 12,     // a, b -> a op b
    kCompare = 13,    // a, b -> a cmp b
    kUnary = 14,      // a -> op a
    kJump = 15,
    kJumpIfFalse = 16,       // pop; jump when falsy
    kJumpIfTrue = 17,        // pop; jump when truthy
    kJumpIfFalseOrPop = 18,  // `and`: keep and jump when falsy, else pop
    kJumpIfTrueOrPop = 19,   // `or`: keep and jump when truthy, else pop
    kBuildSeq = 20,          // n items -> seq
    kBuildMap = 21,          // n key/value pairs -> map
    kCall = 22,              // callee, args..., kwvalues..., [kwnames] -> result; arg = npos | nkw << 8
    kReturn = 23,
    kLen = 24,
    kUnpack = 25,            // seq -> arg items, first on top
    kCancel = 26,            // shared -> None (cancel its animation)
};

enum BinaryOp : int32_t { kAdd = 0, kSub, kMul, kTrueDiv, kFloorDiv, kMod, kPow };
enum CompareOp : int32_t { kLt = 0, kLe, kEq, kNe, kGt, kGe, kIn, kNotIn, kIs, kIsNot };
enum UnaryOp : int32_t { kNeg = 0, kPos, kNot };

/// A compiled worklet.
struct Program {
    int64_t id = 0;
    std::string name;
    std::string file;
    int line = 0;
    int params = 0;
    int locals = 0;
    int captures = 0;
    int max_stack = 0;
    std::vector<MValue> consts;
    std::vector<int32_t> code;   // op, arg pairs
    std::vector<int32_t> lines;  // one per instruction
};

/// A program with its captured values.
struct Closure {
    std::shared_ptr<const Program> program;
    std::vector<MValue> captures;
};

/// Decode and verify a program document. Returns nullptr with `error` set.
std::shared_ptr<const Program> decode_program(int64_t id, const Value& document, std::string& error);

/// The intrinsic id for a name (`abs`, `math.sin`, `with_spring`, ...), or -1.
int32_t intrinsic_id(std::string_view name);
const char* intrinsic_name(int32_t id);

/// Convert between wire values and worklet values. Closures, shared values,
/// intrinsics, and Python callbacks travel as single-key marker objects
/// (`{"__shared__": 3}`); `programs` resolves a closure's program id.
using ProgramLookup = std::function<std::shared_ptr<const Program>(int64_t)>;
bool from_wire(const Value& value, const ProgramLookup& programs, MValue& out, std::string& error);
Value to_wire(const MValue& value);

/// What a running worklet needs from the runtime.
class Host {
public:
    virtual ~Host() = default;
    /// Read a shared value (recording the dependency).
    virtual MValue read_shared(int64_t id) = 0;
    /// Write a shared value; a map marked `__animation__` starts an animation.
    virtual void write_shared(int64_t id, const MValue& value) = 0;
    virtual void cancel_shared(int64_t id) = 0;
    /// Queue a Python callback.
    virtual void call_python(int64_t id, const Seq& args) = 0;
};

/// Where a failed run stopped.
struct Failure {
    WorkletError error;
    std::string name;  // the worklet's name
    std::string file;
    int line = 0;
};

class VM {
public:
    static constexpr int64_t kBudget = 50000;

    explicit VM(Host& host) : host_(host) {}
    /// Run `closure` with `args`. Returns false and fills `failure` on error.
    bool run(const Closure& closure, const Seq& args, MValue& result, Failure& failure);

private:
    bool call(const MValue& callee, Seq& positional, Map& keywords, MValue& result, Failure& failure, int depth);
    bool execute(const Closure& closure, const Seq& args, MValue& result, Failure& failure, int depth);
    bool intrinsic(int32_t id, Seq& positional, Map& keywords, MValue& result, WorkletError& error);

    Host& host_;
    int64_t steps_ = 0;
};

/// Arithmetic and comparison with Python's semantics (exposed for tests).
bool binary(BinaryOp op, const MValue& a, const MValue& b, MValue& out, WorkletError& error);
bool compare(CompareOp op, const MValue& a, const MValue& b, MValue& out, WorkletError& error);

/// Colors: parse `#RGB`, `#RRGGBB`, `#RRGGBBAA`, `rgb(...)`, `rgba(...)`,
/// and `transparent` into RGBA channels (0-255, alpha 0-1); format as `#RRGGBBAA`.
bool parse_color(std::string_view text, double rgba[4]);
std::string format_color(const double rgba[4]);
std::string mix_colors(std::string_view from, std::string_view to, double t);

/// `interpolate(x, inputs, outputs, extrapolate)` with `extend`, `clamp`, or `identity` per side.
double interpolate(double x, const std::vector<double>& inputs, const std::vector<double>& outputs,
                   const std::string& left, const std::string& right);

}  // namespace pn::motion
