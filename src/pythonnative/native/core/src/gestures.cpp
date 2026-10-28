#include "gestures.h"

#include <algorithm>
#include <cmath>

namespace pn {

namespace {

constexpr double kPi = 3.14159265358979323846;
constexpr double kMaxTapDuration = 0.4;
constexpr double kMultiTapGap = 0.3;
constexpr double kVelocityWindow = 0.1;

const char* const kBegan = "began";
const char* const kChanged = "changed";
const char* const kEnded = "ended";
const char* const kCancelled = "cancelled";
const char* const kFailed = "__failed";

using Pointers = std::vector<std::pair<int, Point>>;

Point centroid(const Pointers& pointers) {
    if (pointers.empty()) return {};
    double x = 0, y = 0;
    for (const auto& [id, point] : pointers) {
        x += point.x;
        y += point.y;
    }
    return {x / static_cast<double>(pointers.size()), y / static_cast<double>(pointers.size())};
}

std::optional<Offset> offset(const Value* value) {
    if (value == nullptr || value->is_null()) return std::nullopt;
    if (value->is_number()) {
        double amount = value->as_double();
        return amount >= 0 ? Offset{std::nullopt, amount} : Offset{amount, std::nullopt};
    }
    if (value->is_array() && value->as_array().size() >= 2) {
        const Array& bounds = value->as_array();
        Offset result;
        if (bounds[0].is_number()) result.negative = bounds[0].as_double();
        if (bounds[1].is_number()) result.positive = bounds[1].as_double();
        return result;
    }
    return std::nullopt;
}

std::optional<double> nullable(const Value& spec, const char* key, std::optional<double> fallback) {
    const Value* value = spec.find(key);
    if (value == nullptr) return fallback;
    if (value->is_null()) return std::nullopt;
    return value->is_number() ? std::optional<double>(value->as_double()) : fallback;
}

double number(const Value& spec, const char* key, double fallback) {
    const Value* value = spec.find(key);
    return value != nullptr && value->is_number() ? value->as_double() : fallback;
}

std::set<int> int_set(const Value& list) {
    std::set<int> out;
    for (const Value& item : list.as_array()) out.insert(static_cast<int>(item.as_int()));
    return out;
}

class VelocityTracker {
public:
    void add(double x, double y, double t) {
        samples_.push_back({x, y, t});
        double cutoff = t - kVelocityWindow;
        while (samples_.size() > 2 && samples_.front().t < cutoff) samples_.erase(samples_.begin());
    }
    Point velocity() const {
        if (samples_.size() < 2) return {};
        const Sample& first = samples_.front();
        const Sample& last = samples_.back();
        double dt = last.t - first.t;
        if (dt <= 1e-6) return {};
        return {(last.x - first.x) / dt, (last.y - first.y) / dt};
    }
    void reset() { samples_.clear(); }

private:
    struct Sample {
        double x, y, t;
    };
    std::vector<Sample> samples_;
};

}  // namespace

GestureConfig decode_gesture(const Value& spec) {
    GestureConfig config;
    if (!spec.is_object()) return config;
    const Value* kind = spec.find("kind");
    config.kind = kind != nullptr ? kind->as_string() : std::string();
    const Value* enabled = spec.find("enabled");
    config.enabled = enabled == nullptr || !enabled->is_bool() || enabled->as_bool();
    config.taps = static_cast<int>(number(spec, "n_taps", 1));
    config.max_distance = number(spec, "max_distance", 12);
    config.min_duration_ms = number(spec, "min_duration_ms", 500);
    config.min_distance = nullable(spec, "min_distance", 10.0);
    config.min_pointers = static_cast<int>(number(spec, "min_pointers", 1));
    if (const Value* limit = spec.find("max_pointers"); limit != nullptr && limit->is_number()) {
        config.max_pointers = static_cast<int>(limit->as_double());
    }
    config.active_offset_x = offset(spec.find("active_offset_x"));
    config.active_offset_y = offset(spec.find("active_offset_y"));
    config.fail_offset_x = offset(spec.find("fail_offset_x"));
    config.fail_offset_y = offset(spec.find("fail_offset_y"));
    // Swipes default to 300 points per second; a pan without a velocity criterion sends null.
    config.min_velocity = nullable(spec, "min_velocity", config.kind == "pan" ? std::nullopt : std::optional<double>(300.0));
    // A hand-built pan spec without ``min_distance`` uses the default
    // distance only when it names no other activation criterion, as
    // ``Pan()`` does.
    if (config.kind == "pan" && spec.find("min_distance") == nullptr &&
        (config.active_offset_x || config.active_offset_y || config.fail_offset_x || config.fail_offset_y ||
         config.min_velocity)) {
        config.min_distance = std::nullopt;
    }
    if (const Value* direction = spec.find("direction");
        direction != nullptr && direction->is_string() && !direction->as_string().empty() &&
        direction->as_string() != "any") {
        config.direction = direction->as_string();
    }
    config.pointers = static_cast<int>(number(spec, "n_pointers", 1));
    if (const Value* together = spec.find("simultaneous"); together != nullptr && together->is_array()) {
        config.simultaneous = int_set(*together);
    }
    if (const Value* wait = spec.find("wait_for"); wait != nullptr && wait->is_array()) config.wait_for = int_set(*wait);
    if (const Value* events = spec.find("animated_events")) config.animated_events = *events;
    return config;
}

// ----------------------------------------------------------------------
// Recognizers
// ----------------------------------------------------------------------

class Recognizer {
public:
    Recognizer(int index, const GestureConfig& config, EmitFn emit)
        : index(index), config(config), emit_(std::move(emit)) {}
    virtual ~Recognizer() = default;

    virtual void down(const Pointers&, double) {}
    virtual void move(const Pointers&, double) {}
    virtual void up(const Pointers&, double, double, double) {}
    virtual void cancel(double) {}
    virtual void force_fail(double t) { cancel(t); }
    virtual std::optional<double> deadline() const { return std::nullopt; }
    virtual void poll(double) {}
    virtual bool active_pan() const { return false; }

    const int index;
    const GestureConfig config;

protected:
    void emit(const char* state, Payload fields = {}) {
        Payload payload;
        payload.emplace_back("kind", Value::string(config.kind));
        payload.emplace_back("state", Value::string(state));
        for (auto& field : fields) payload.push_back(std::move(field));
        emit_(index, payload);
    }
    void fail() { emit(kFailed); }
    static Member field(const char* name, double value) { return {name, Value::number(value)}; }
    static Member count(const Pointers& pointers) {
        return {"pointer_count", Value::integer(static_cast<int64_t>(pointers.size()))};
    }

private:
    EmitFn emit_;
};

namespace {

class Tap : public Recognizer {
public:
    using Recognizer::Recognizer;

    void down(const Pointers& pointers, double t) override {
        if (pointers.size() != 1) {
            if (!failed_) {
                failed_ = true;
                fail();
            }
            return;
        }
        if (taps_ > 0 && t - last_tap_ > kMultiTapGap) taps_ = 0;
        failed_ = false;
        gap_deadline_.reset();
        origin_ = centroid(pointers);
        down_time_ = t;
    }
    void move(const Pointers& pointers, double) override {
        if (!origin_ || failed_) return;
        Point c = centroid(pointers);
        if (std::hypot(c.x - origin_->x, c.y - origin_->y) > config.max_distance) {
            failed_ = true;
            fail();
        }
    }
    void up(const Pointers&, double t, double x, double y) override {
        if (failed_ || !origin_) {
            reset();
            return;
        }
        if (t - down_time_ > kMaxTapDuration) {
            reset();
            fail();
            return;
        }
        ++taps_;
        last_tap_ = t;
        if (taps_ >= std::max(1, config.taps)) {
            emit(kEnded, {field("x", x), field("y", y)});
            reset();
        } else {
            gap_deadline_ = t + kMultiTapGap;
        }
        origin_.reset();
    }
    void cancel(double) override { reset(); }
    std::optional<double> deadline() const override { return gap_deadline_; }
    void poll(double t) override {
        if (gap_deadline_ && t >= *gap_deadline_) {
            gap_deadline_.reset();
            taps_ = 0;
            fail();
        }
    }

private:
    void reset() {
        origin_.reset();
        if (taps_ >= std::max(1, config.taps)) taps_ = 0;
        failed_ = false;
        gap_deadline_.reset();
    }
    std::optional<Point> origin_;
    double down_time_ = 0;
    int taps_ = 0;
    double last_tap_ = 0;
    bool failed_ = false;
    std::optional<double> gap_deadline_;
};

class LongPress : public Recognizer {
public:
    using Recognizer::Recognizer;

    void down(const Pointers& pointers, double t) override {
        origin_ = centroid(pointers);
        deadline_ = t + config.min_duration_ms / 1000.0;
        active_ = false;
    }
    void move(const Pointers& pointers, double) override {
        if (!origin_) return;
        Point c = centroid(pointers);
        if (std::hypot(c.x - origin_->x, c.y - origin_->y) > config.max_distance) {
            if (active_) emit(kCancelled, {field("x", c.x), field("y", c.y)});
            reset();
            fail();
        }
    }
    void up(const Pointers&, double, double x, double y) override {
        if (active_) emit(kEnded, {field("x", x), field("y", y)});
        else if (origin_) fail();
        reset();
    }
    void cancel(double) override {
        if (active_) emit(kCancelled);
        reset();
    }
    std::optional<double> deadline() const override { return deadline_; }
    void poll(double t) override {
        if (!deadline_ || !origin_ || active_) return;
        if (t >= *deadline_) {
            active_ = true;
            deadline_.reset();
            emit(kBegan, {field("x", origin_->x), field("y", origin_->y)});
        }
    }

private:
    void reset() {
        origin_.reset();
        deadline_.reset();
        active_ = false;
    }
    std::optional<Point> origin_;
    std::optional<double> deadline_;
    bool active_ = false;
};

class Pan : public Recognizer {
public:
    using Recognizer::Recognizer;

    bool active_pan() const override { return active_; }

    void down(const Pointers& pointers, double t) override {
        if (exceeds_max(pointers)) return;
        if (static_cast<int>(pointers.size()) < std::max(1, config.min_pointers)) return;
        if (!origin_) {
            Point c = centroid(pointers);
            origin_ = c;
            velocity_.reset();
            velocity_.add(c.x, c.y, t);
        } else {
            rebase(pointers);
        }
    }
    void move(const Pointers& pointers, double t) override {
        if (!origin_ || failed_ || static_cast<int>(pointers.size()) < std::max(1, config.min_pointers)) return;
        Point c = centroid(pointers);
        velocity_.add(c.x, c.y, t);
        if (!active_) {
            Point v = velocity_.velocity();
            double dx = c.x - origin_->x, dy = c.y - origin_->y;
            double speed = std::hypot(v.x, v.y);
            if ((config.fail_offset_x && config.fail_offset_x->crosses(dx)) ||
                (config.fail_offset_y && config.fail_offset_y->crosses(dy))) {
                failed_ = true;
                fail();
            } else if ((config.active_offset_x && config.active_offset_x->crosses(dx)) ||
                       (config.active_offset_y && config.active_offset_y->crosses(dy)) ||
                       (config.min_distance && std::hypot(dx, dy) >= *config.min_distance) ||
                       (config.min_velocity && speed >= *config.min_velocity)) {
                active_ = true;
                anchor_ = c;
                emit(kBegan, {field("x", c.x), field("y", c.y), count(pointers)});
            }
            return;
        }
        Point v = velocity_.velocity();
        translation_ = {c.x - anchor_.x, c.y - anchor_.y};
        emit(kChanged, {field("x", c.x), field("y", c.y), field("translation_x", translation_.x),
                        field("translation_y", translation_.y), field("velocity_x", v.x),
                        field("velocity_y", v.y), count(pointers)});
    }
    void up(const Pointers& pointers, double, double x, double y) override {
        if (active_ && static_cast<int>(pointers.size()) < std::max(1, config.min_pointers)) {
            Point v = velocity_.velocity();
            emit(kEnded, {field("x", x), field("y", y), field("translation_x", x - anchor_.x),
                          field("translation_y", y - anchor_.y), field("velocity_x", v.x),
                          field("velocity_y", v.y), count(pointers)});
            reset();
        } else if (pointers.empty()) {
            if (!active_ && origin_ && !failed_) fail();
            reset();
        } else if (active_) {
            rebase(pointers);
        }
    }
    void cancel(double) override {
        if (active_) emit(kCancelled);
        reset();
    }

private:
    bool exceeds_max(const Pointers& pointers) {
        if (!config.max_pointers || static_cast<int>(pointers.size()) <= *config.max_pointers) return false;
        if (active_) {
            emit(kCancelled);
            reset();
            failed_ = true;
        } else if (!failed_) {
            failed_ = true;
            fail();
        }
        return true;
    }
    void rebase(const Pointers& pointers) {
        Point c = centroid(pointers);
        if (!active_) {
            origin_ = c;
            return;
        }
        anchor_ = {c.x - translation_.x, c.y - translation_.y};
    }
    void reset() {
        origin_.reset();
        anchor_ = {};
        active_ = false;
        failed_ = false;
        velocity_.reset();
        translation_ = {};
    }
    std::optional<Point> origin_;
    Point anchor_;
    Point translation_;
    VelocityTracker velocity_;
    bool active_ = false;
    bool failed_ = false;
};

class Swipe : public Recognizer {
public:
    using Recognizer::Recognizer;

    void down(const Pointers& pointers, double t) override {
        if (!tracking_) {
            velocity_.reset();
            tracking_ = true;
            max_pointers_ = 0;
        }
        max_pointers_ = std::max(max_pointers_, static_cast<int>(pointers.size()));
        Point c = centroid(pointers);
        velocity_.add(c.x, c.y, t);
    }
    void move(const Pointers& pointers, double t) override {
        if (!tracking_) return;
        max_pointers_ = std::max(max_pointers_, static_cast<int>(pointers.size()));
        Point c = centroid(pointers);
        velocity_.add(c.x, c.y, t);
    }
    void up(const Pointers& pointers, double t, double x, double y) override {
        if (!tracking_ || !pointers.empty()) return;
        tracking_ = false;
        velocity_.add(x, y, t);
        Point v = velocity_.velocity();
        double speed = std::hypot(v.x, v.y);
        if (speed < config.min_velocity.value_or(300.0) || max_pointers_ < std::max(1, config.pointers)) {
            fail();
            return;
        }
        const char* resolved = std::fabs(v.x) >= std::fabs(v.y) ? (v.x > 0 ? "right" : "left") : (v.y > 0 ? "down" : "up");
        if (config.direction && *config.direction != resolved) {
            fail();
            return;
        }
        emit(kEnded, {field("x", x), field("y", y), field("velocity_x", v.x), field("velocity_y", v.y),
                      {"direction", Value::string(resolved)},
                      {"pointer_count", Value::integer(max_pointers_)}});
    }
    void cancel(double) override {
        tracking_ = false;
        max_pointers_ = 0;
        velocity_.reset();
    }

private:
    VelocityTracker velocity_;
    bool tracking_ = false;
    int max_pointers_ = 0;
};

class TwoFinger : public Recognizer {
public:
    TwoFinger(int index, const GestureConfig& config, EmitFn emit, bool rotation)
        : Recognizer(index, config, std::move(emit)), rotation_(rotation) {}

    void down(const Pointers& pointers, double) override {
        std::optional<double> measured = measure(pointers);
        if (measured && (rotation_ || *measured > 0) && !initial_) {
            initial_ = measured;
            active_ = true;
            Point c = centroid(pointers);
            emit(kBegan, {field("x", c.x), field("y", c.y), field(name(), rotation_ ? 0.0 : 1.0), count(pointers)});
        }
    }
    void move(const Pointers& pointers, double) override {
        if (!initial_ || !active_) return;
        std::optional<double> measured = measure(pointers);
        if (!measured) return;
        if (rotation_) {
            double delta = *measured - *initial_;
            while (delta > kPi) delta -= 2 * kPi;
            while (delta < -kPi) delta += 2 * kPi;
            amount_ = delta;
        } else {
            if (*measured <= 0) return;
            amount_ = *measured / *initial_;
        }
        Point c = centroid(pointers);
        emit(kChanged, {field("x", c.x), field("y", c.y), field(name(), amount_), count(pointers)});
    }
    void up(const Pointers& pointers, double, double x, double y) override {
        if (active_ && pointers.size() < 2) {
            emit(kEnded, {field("x", x), field("y", y), field(name(), amount_), count(pointers)});
            reset();
        } else if (!active_ && pointers.empty()) {
            fail();
        }
    }
    void cancel(double) override {
        if (active_) emit(kCancelled, {field(name(), amount_)});
        reset();
    }

private:
    const char* name() const { return rotation_ ? "rotation" : "scale"; }
    std::optional<double> measure(const Pointers& pointers) const {
        if (pointers.size() < 2) return std::nullopt;
        const Point& a = pointers[0].second;
        const Point& b = pointers[1].second;
        return rotation_ ? std::atan2(b.y - a.y, b.x - a.x) : std::hypot(b.x - a.x, b.y - a.y);
    }
    void reset() {
        initial_.reset();
        active_ = false;
        amount_ = rotation_ ? 0.0 : 1.0;
    }
    bool rotation_;
    std::optional<double> initial_;
    bool active_ = false;
    double amount_ = rotation_ ? 0.0 : 1.0;
};

std::unique_ptr<Recognizer> make_recognizer(int index, const GestureConfig& config, EmitFn emit) {
    if (config.kind == "tap") return std::make_unique<Tap>(index, config, std::move(emit));
    if (config.kind == "long_press") return std::make_unique<LongPress>(index, config, std::move(emit));
    if (config.kind == "pan") return std::make_unique<Pan>(index, config, std::move(emit));
    if (config.kind == "swipe" || config.kind == "fling") return std::make_unique<Swipe>(index, config, std::move(emit));
    if (config.kind == "pinch") return std::make_unique<TwoFinger>(index, config, std::move(emit), false);
    if (config.kind == "rotation") return std::make_unique<TwoFinger>(index, config, std::move(emit), true);
    return nullptr;
}

std::string state_of(const Payload& payload) {
    const Value* state = find_member(payload, "state");
    return state != nullptr ? state->as_string() : std::string();
}

// Pointers keep their press order, which pinch and rotation rely on.
void put_pointer(Pointers& list, int id, Point point) {
    for (auto& entry : list) {
        if (entry.first == id) {
            entry.second = point;
            return;
        }
    }
    list.emplace_back(id, point);
}

bool has_pointer(const Pointers& list, int id) {
    return std::any_of(list.begin(), list.end(), [&](const auto& entry) { return entry.first == id; });
}

void drop_pointer(Pointers& list, int id) {
    list.erase(std::remove_if(list.begin(), list.end(), [&](const auto& entry) { return entry.first == id; }),
               list.end());
}

}  // namespace

// ----------------------------------------------------------------------
// Arbitration
// ----------------------------------------------------------------------

GestureArbiter::GestureArbiter(std::vector<GestureConfig> specs, EmitFn emit)
    : specs_(std::move(specs)), emit_(std::move(emit)) {
    // Disabled specs keep their index so `gesture:<index>` stays aligned.
    for (size_t i = 0; i < specs_.size(); ++i) {
        if (!specs_[i].enabled) continue;
        int index = static_cast<int>(i);
        auto recognizer = make_recognizer(index, specs_[i], [this](int at, const Payload& payload) { mediate(at, payload); });
        if (!recognizer) continue;
        recognizers_.push_back(std::move(recognizer));
        indices_.push_back(index);
        states_[index] = State::Possible;
    }
}

GestureArbiter::~GestureArbiter() = default;

Recognizer* GestureArbiter::recognizer_for(int index) const {
    for (const auto& recognizer : recognizers_) {
        if (recognizer->index == index) return recognizer.get();
    }
    return nullptr;
}

void GestureArbiter::down(int pointer, double x, double y, double t, double window_x, double window_y) {
    last_time_ = t;
    window_offset_ = {window_x - x, window_y - y};
    bool waiting = std::any_of(states_.begin(), states_.end(), [](const auto& s) { return s.second == State::Waiting; });
    if (pointers_.empty() && !waiting) {
        for (int index : indices_) states_[index] = State::Possible;
        buffers_.clear();
    }
    put_pointer(pointers_, pointer, {x, y});
    for (auto& recognizer : recognizers_) recognizer->down(pointers_, t);
}

void GestureArbiter::move(int pointer, double x, double y, double t, double window_x, double window_y) {
    last_time_ = t;
    window_offset_ = {window_x - x, window_y - y};
    if (!has_pointer(pointers_, pointer)) return;
    put_pointer(pointers_, pointer, {x, y});
    for (auto& recognizer : recognizers_) recognizer->move(pointers_, t);
}

void GestureArbiter::up(int pointer, double x, double y, double t, double window_x, double window_y) {
    last_time_ = t;
    window_offset_ = {window_x - x, window_y - y};
    drop_pointer(pointers_, pointer);
    for (auto& recognizer : recognizers_) recognizer->up(pointers_, t, x, y);
}

void GestureArbiter::cancel(double t) {
    last_time_ = t;
    pointers_.clear();
    buffers_.clear();
    for (int index : indices_) {
        if (states_[index] == State::Waiting) states_[index] = State::Failed;
    }
    for (auto& recognizer : recognizers_) recognizer->cancel(t);
}

void GestureArbiter::poll(double t) {
    last_time_ = t;
    for (auto& recognizer : recognizers_) recognizer->poll(t);
}

std::optional<double> GestureArbiter::deadline() const {
    std::optional<double> earliest;
    for (const auto& recognizer : recognizers_) {
        std::optional<double> next = recognizer->deadline();
        if (next && (!earliest || *next < *earliest)) earliest = next;
    }
    return earliest;
}

bool GestureArbiter::has_active_pan() const {
    return std::any_of(recognizers_.begin(), recognizers_.end(), [](const auto& r) { return r->active_pan(); });
}

void GestureArbiter::deliver(int index, const Payload& payload) {
    const Value* x = find_member(payload, "x");
    const Value* y = find_member(payload, "y");
    if (x == nullptr || y == nullptr) {
        emit_(index, payload);
        return;
    }
    Payload out = payload;
    out.emplace_back("absolute_x", Value::number(x->as_double() + window_offset_.x));
    out.emplace_back("absolute_y", Value::number(y->as_double() + window_offset_.y));
    emit_(index, out);
}

bool GestureArbiter::simultaneous(int a, int b) const {
    const auto& together_a = specs_[static_cast<size_t>(a)].simultaneous;
    const auto& together_b = specs_[static_cast<size_t>(b)].simultaneous;
    if (!together_a || !together_b) return true;
    return together_a->count(b) != 0 && together_b->count(a) != 0;
}

void GestureArbiter::mediate(int index, const Payload& payload) {
    std::string state = state_of(payload);
    State current = states_.count(index) ? states_[index] : State::Possible;
    if (state == kFailed) {
        if (current == State::Possible || current == State::Waiting) set_failed(index);
        return;
    }
    switch (current) {
        case State::Failed:
        case State::Done: return;
        case State::Active:
            deliver(index, payload);
            if (state == kEnded) {
                states_[index] = State::Done;
                resolved(index, true);
            } else if (state == kCancelled) {
                states_[index] = State::Failed;
                resolved(index, false);
            }
            return;
        case State::Waiting: buffers_[index].push_back(payload); return;
        case State::Possible: request_activation(index, payload); return;
    }
}

void GestureArbiter::request_activation(int index, const Payload& payload) {
    for (int other : indices_) {
        if (other == index) continue;
        State s = states_[other];
        if ((s == State::Active || s == State::Done) && !simultaneous(index, other)) {
            set_failed(index);
            return;
        }
    }
    std::vector<int> targets;
    for (int wait : specs_[static_cast<size_t>(index)].wait_for) {
        if (states_.count(wait)) targets.push_back(wait);
    }
    if (std::any_of(targets.begin(), targets.end(), [&](int t) { return states_[t] == State::Active || states_[t] == State::Done; })) {
        set_failed(index);
        return;
    }
    if (std::any_of(targets.begin(), targets.end(), [&](int t) { return states_[t] == State::Possible || states_[t] == State::Waiting; })) {
        states_[index] = State::Waiting;
        buffers_[index].push_back(payload);
        return;
    }
    activate(index, {payload});
}

void GestureArbiter::activate(int index, const std::vector<Payload>& payloads) {
    std::string last = payloads.empty() ? std::string() : state_of(payloads.back());
    bool discrete_done = last == kEnded || last == kCancelled;
    states_[index] = discrete_done ? State::Done : State::Active;
    for (int other : indices_) {
        if (other == index) continue;
        State s = states_[other];
        if ((s == State::Possible || s == State::Waiting) && !simultaneous(index, other)) {
            if (Recognizer* recognizer = recognizer_for(other)) recognizer->force_fail(last_time_);
            set_failed(other);
        }
    }
    for (const Payload& payload : payloads) deliver(index, payload);
    if (states_[index] == State::Done) resolved(index, true);
}

void GestureArbiter::set_failed(int index) {
    if (states_[index] == State::Failed) return;
    states_[index] = State::Failed;
    buffers_.erase(index);
    resolved(index, false);
}

void GestureArbiter::resolved(int index, bool succeeded) {
    for (int waiter : indices_) {
        if (states_[waiter] != State::Waiting) continue;
        const std::set<int>& wait_for = specs_[static_cast<size_t>(waiter)].wait_for;
        if (wait_for.count(index) == 0) continue;
        if (succeeded) {
            if (Recognizer* recognizer = recognizer_for(waiter)) recognizer->force_fail(last_time_);
            set_failed(waiter);
            continue;
        }
        std::vector<int> targets;
        for (int wait : wait_for) {
            if (states_.count(wait)) targets.push_back(wait);
        }
        if (std::any_of(targets.begin(), targets.end(), [&](int t) { return states_[t] == State::Possible || states_[t] == State::Waiting; })) {
            continue;
        }
        if (std::any_of(targets.begin(), targets.end(), [&](int t) { return states_[t] == State::Active || states_[t] == State::Done; })) {
            if (Recognizer* recognizer = recognizer_for(waiter)) recognizer->force_fail(last_time_);
            set_failed(waiter);
            continue;
        }
        std::vector<Payload> payloads = std::move(buffers_[waiter]);
        buffers_.erase(waiter);
        states_[waiter] = State::Possible;
        activate(waiter, payloads);
    }
}

}  // namespace pn
