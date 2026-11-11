#include "motion_anim.h"

#include <algorithm>
#include <cmath>
#include <numbers>

namespace pn::motion {

namespace {

constexpr double kDefaultDeceleration = 0.998;
constexpr double kDecayRestVelocity = 1.0;  // units per second
constexpr double kDecayRestDistance = 0.1;

double bezier_coordinate(double u, double a, double b) {
    return 3 * (1 - u) * (1 - u) * u * a + 3 * (1 - u) * u * u * b + u * u * u;
}

double bezier(double t, double x1, double y1, double x2, double y2) {
    if (t <= 0) return 0;
    if (t >= 1) return 1;
    double low = 0, high = 1;
    for (int i = 0; i < 24; ++i) {
        double mid = (low + high) / 2;
        if (bezier_coordinate(mid, x1, x2) < t) low = mid;
        else high = mid;
    }
    return bezier_coordinate((low + high) / 2, y1, y2);
}

double bounce(double t) {
    if (t < 1 / 2.75) return 7.5625 * t * t;
    if (t < 2 / 2.75) {
        double u = t - 1.5 / 2.75;
        return 7.5625 * u * u + 0.75;
    }
    if (t < 2.5 / 2.75) {
        double u = t - 2.25 / 2.75;
        return 7.5625 * u * u + 0.9375;
    }
    double u = t - 2.625 / 2.75;
    return 7.5625 * u * u + 0.984375;
}

double number_or(const MValue* value, double fallback) {
    return value != nullptr && value->is_number() ? value->as_double() : fallback;
}

std::shared_ptr<const Closure> callback_of(const MValue& descriptor) {
    const MValue* callback = descriptor.find("on_finish");
    return callback != nullptr && callback->kind() == MValue::Kind::Closure ? callback->closure_ptr() : nullptr;
}

bool reduced(const MValue& descriptor, bool system) {
    const MValue* mode = descriptor.find("reduce_motion");
    if (mode == nullptr || !mode->is_str()) return system;
    if (mode->as_str() == "always") return true;
    if (mode->as_str() == "never") return false;
    return system;
}

/// A number, or a color's four channels.
struct Channels {
    std::vector<double> values;
    bool color = false;
};

bool channels_of(const MValue& value, Channels& out) {
    if (value.is_number()) {
        out.values = {value.as_double()};
        out.color = false;
        return true;
    }
    if (value.is_str()) {
        double rgba[4];
        if (!parse_color(value.as_str(), rgba)) return false;
        out.values.assign(rgba, rgba + 4);
        out.color = true;
        return true;
    }
    return false;
}

MValue value_of(const Channels& channels, bool integer_target) {
    if (channels.color) return MValue::string(format_color(channels.values.data()));
    double v = channels.values.empty() ? 0 : channels.values[0];
    if (!std::isfinite(v)) v = 0;
    (void)integer_target;
    return MValue::number(v);
}

/// Shared handling for animations with a target (`to`).
class Targeted : public Animation {
public:
    explicit Targeted(MValue descriptor) : descriptor_(std::move(descriptor)), callback_(callback_of(descriptor_)) {}

    void start(const MValue& current, double velocity, bool reduce_motion) override {
        const MValue* to = descriptor_.find("to");
        target_value_ = to != nullptr ? *to : MValue();
        reduce_ = reduced(descriptor_, reduce_motion);
        valid_ = channels_of(current, from_) && channels_of(target_value_, to_) && from_.color == to_.color &&
                 from_.values.size() == to_.values.size();
        current_ = valid_ ? from_ : to_;
        velocities_.assign(current_.values.size(), 0.0);
        if (!velocities_.empty() && !current_.color) velocities_[0] = velocity;
        begin();
    }

    MValue value() const override {
        if (!valid_ || done_) return target_value_;
        return value_of(current_, false);
    }

    double velocity() const override { return velocities_.empty() || current_.color ? 0 : velocities_[0]; }

    void interrupt(std::vector<Completion>& completions) override {
        if (!done_ && callback_) completions.push_back({callback_, false});
        done_ = true;
        interrupted_ = true;
    }

protected:
    virtual void begin() {}
    bool finish(std::vector<Completion>& completions) {
        if (!done_ && callback_) completions.push_back({callback_, true});
        done_ = true;
        current_ = to_;
        std::fill(velocities_.begin(), velocities_.end(), 0.0);
        return true;
    }

    MValue descriptor_;
    std::shared_ptr<const Closure> callback_;
    MValue target_value_;
    Channels from_, to_, current_;
    std::vector<double> velocities_;
    bool valid_ = false;
    bool reduce_ = false;
    bool done_ = false;
    bool interrupted_ = false;
};

class Timing final : public Targeted {
public:
    using Targeted::Targeted;

    bool step(double dt, std::vector<Completion>& completions) override {
        if (done_) return true;
        if (!valid_ || reduce_) return finish(completions);
        elapsed_ += dt;
        double duration = std::max(0.0, number_or(descriptor_.find("duration"), 300)) / 1000.0;
        double t = duration <= 0 ? 1 : std::min(1.0, elapsed_ / duration);
        double eased = easing_ ? easing_(t) : t;
        for (size_t i = 0; i < current_.values.size(); ++i) {
            double previous = current_.values[i];
            current_.values[i] = from_.values[i] + (to_.values[i] - from_.values[i]) * eased;
            velocities_[i] = dt > 0 ? (current_.values[i] - previous) / dt : 0;
        }
        if (t >= 1) return finish(completions);
        return false;
    }

private:
    void begin() override {
        const MValue* easing = descriptor_.find("easing");
        easing_ = easing_function(easing != nullptr ? *easing : MValue());
    }

    double elapsed_ = 0;
    std::function<double(double)> easing_;
};

class Spring final : public Targeted {
public:
    using Targeted::Targeted;

    bool step(double dt, std::vector<Completion>& completions) override {
        if (done_) return true;
        if (!valid_ || reduce_) return finish(completions);
        int steps = std::max(1, static_cast<int>(std::ceil(dt / 0.001)));
        double h = dt / steps;
        for (int s = 0; s < steps; ++s) {
            for (size_t i = 0; i < current_.values.size(); ++i) {
                double displacement = current_.values[i] - to_.values[i];
                double acceleration = (-stiffness_ * displacement - damping_ * velocities_[i]) / mass_;
                velocities_[i] += acceleration * h;
                current_.values[i] += velocities_[i] * h;
            }
        }
        bool overshot = false;
        bool resting = true;
        for (size_t i = 0; i < current_.values.size(); ++i) {
            double span = to_.values[i] - from_.values[i];
            double displacement = current_.values[i] - to_.values[i];
            if (overshoot_clamping_ && span != 0 && ((span > 0 && current_.values[i] > to_.values[i]) ||
                                                     (span < 0 && current_.values[i] < to_.values[i]))) {
                overshot = true;
            }
            if (std::fabs(velocities_[i]) > rest_speed_ || std::fabs(displacement) > rest_displacement_) resting = false;
        }
        if (overshot || resting) return finish(completions);
        return false;
    }

private:
    void begin() override {
        mass_ = std::max(0.001, number_or(descriptor_.find("mass"), 1));
        const MValue* duration = descriptor_.find("duration");
        if (duration != nullptr && duration->is_number() && duration->as_double() > 0) {
            // A spring tuned to settle in about `duration`: SwiftUI's
            // response and damping-fraction model.
            double response = duration->as_double() / 1000.0;
            double ratio = number_or(descriptor_.find("damping_ratio"), 1.0);
            stiffness_ = std::pow(2 * std::numbers::pi / response, 2) * mass_;
            damping_ = 4 * std::numbers::pi * ratio * mass_ / response;
        } else {
            stiffness_ = number_or(descriptor_.find("stiffness"), 100);
            double ratio = number_or(descriptor_.find("damping_ratio"), -1);
            damping_ = ratio >= 0 ? 2 * ratio * std::sqrt(stiffness_ * mass_) : number_or(descriptor_.find("damping"), 10);
        }
        const MValue* clamp = descriptor_.find("overshoot_clamping");
        overshoot_clamping_ = clamp != nullptr && clamp->truthy();
        rest_displacement_ = number_or(descriptor_.find("rest_displacement"), 0.01);
        rest_speed_ = number_or(descriptor_.find("rest_speed"), 2);
        if (!current_.color && !velocities_.empty()) {
            const MValue* velocity = descriptor_.find("velocity");
            if (velocity != nullptr && velocity->is_number() && velocity->as_double() != 0) velocities_[0] = velocity->as_double();
        }
    }

    double mass_ = 1, stiffness_ = 100, damping_ = 10;
    bool overshoot_clamping_ = false;
    double rest_displacement_ = 0.01, rest_speed_ = 2;
};

class Decay final : public Animation {
public:
    explicit Decay(MValue descriptor) : descriptor_(std::move(descriptor)), callback_(callback_of(descriptor_)) {}

    void start(const MValue& current, double velocity, bool reduce_motion) override {
        from_ = current.is_number() ? current.as_double() : 0;
        position_ = from_;
        velocity_ = number_or(descriptor_.find("velocity"), velocity);
        start_velocity_ = velocity_;
        deceleration_ = std::min(0.999999, std::max(0.000001, number_or(descriptor_.find("deceleration"), kDefaultDeceleration)));
        rubber_ = number_or(descriptor_.find("rubber_band_factor"), 0.6);
        if (const MValue* clamp = descriptor_.find("clamp"); clamp != nullptr && clamp->is_seq() && clamp->as_seq().size() == 2) {
            lower_ = clamp->as_seq()[0].as_double();
            upper_ = clamp->as_seq()[1].as_double();
            clamped_ = true;
        }
        reduce_ = reduced(descriptor_, reduce_motion);
    }

    bool step(double dt, std::vector<Completion>& completions) override {
        if (done_) return true;
        if (reduce_) {
            double final_value = from_ + start_velocity_ / 1000.0 / (1 - deceleration_);
            position_ = clamped_ ? std::min(upper_, std::max(lower_, final_value)) : final_value;
            return finish(completions);
        }
        if (spring_) {
            std::vector<Completion> ignored;
            bool finished = spring_->step(dt, ignored);
            position_ = spring_->value().as_double();
            velocity_ = spring_->velocity();
            if (finished) return finish(completions);
            return false;
        }
        elapsed_ms_ += dt * 1000.0;
        double next = decay_position(from_, start_velocity_, deceleration_, elapsed_ms_);
        velocity_ = start_velocity_ * std::pow(deceleration_, elapsed_ms_);
        double final_value = from_ + start_velocity_ / 1000.0 / (1 - deceleration_);
        position_ = next;
        if (clamped_ && (position_ < lower_ || position_ > upper_)) {
            double bound = position_ < lower_ ? lower_ : upper_;
            if (rubber_ <= 0) {
                position_ = bound;
                return finish(completions);
            }
            // Past a bound: spring back to it, carrying the fling's momentum.
            MValue spring = MValue::map({{"__animation__", MValue::boolean(true)},
                                         {"type", MValue::string("spring")},
                                         {"to", MValue::number(bound)},
                                         {"stiffness", MValue::number(300 * std::max(0.05, rubber_))},
                                         {"damping_ratio", MValue::number(1.0)}});
            std::string error;
            spring_ = make_animation(spring, error);
            if (!spring_) {
                position_ = bound;
                return finish(completions);
            }
            spring_->start(MValue::number(position_), velocity_, false);
            return false;
        }
        if (std::fabs(velocity_) < kDecayRestVelocity || std::fabs(position_ - final_value) < kDecayRestDistance) {
            return finish(completions);
        }
        return false;
    }

    void interrupt(std::vector<Completion>& completions) override {
        if (!done_ && callback_) completions.push_back({callback_, false});
        done_ = true;
    }

    MValue value() const override { return MValue::number(std::isfinite(position_) ? position_ : 0); }
    double velocity() const override { return done_ ? 0 : velocity_; }

private:
    bool finish(std::vector<Completion>& completions) {
        if (!done_ && callback_) completions.push_back({callback_, true});
        done_ = true;
        velocity_ = 0;
        return true;
    }

    MValue descriptor_;
    std::shared_ptr<const Closure> callback_;
    double from_ = 0, position_ = 0, velocity_ = 0, start_velocity_ = 0;
    double deceleration_ = kDefaultDeceleration, rubber_ = 0.6;
    double lower_ = 0, upper_ = 0, elapsed_ms_ = 0;
    bool clamped_ = false, reduce_ = false, done_ = false;
    std::unique_ptr<Animation> spring_;
};

class Delay final : public Animation {
public:
    Delay(MValue descriptor, std::unique_ptr<Animation> child)
        : descriptor_(std::move(descriptor)), child_(std::move(child)) {}

    void start(const MValue& current, double velocity, bool reduce_motion) override {
        current_ = current;
        velocity_ = velocity;
        reduce_ = reduce_motion;
        remaining_ = std::max(0.0, number_or(descriptor_.find("delay"), 0)) / 1000.0;
        bool skip = reduced(descriptor_, reduce_motion);
        if (remaining_ <= 0 || skip) begin_child();
    }

    bool step(double dt, std::vector<Completion>& completions) override {
        if (!started_) {
            remaining_ -= dt;
            if (remaining_ > 0) return false;
            double leftover = -remaining_;
            begin_child();
            return child_->step(leftover, completions);
        }
        return child_->step(dt, completions);
    }

    void interrupt(std::vector<Completion>& completions) override { child_->interrupt(completions); }
    MValue value() const override { return started_ ? child_->value() : current_; }
    double velocity() const override { return started_ ? child_->velocity() : 0; }

private:
    void begin_child() {
        started_ = true;
        child_->start(current_, velocity_, reduce_);
    }

    MValue descriptor_;
    std::unique_ptr<Animation> child_;
    MValue current_;
    double velocity_ = 0, remaining_ = 0;
    bool reduce_ = false, started_ = false;
};

class Sequence final : public Animation {
public:
    explicit Sequence(std::vector<MValue> descriptors) : descriptors_(std::move(descriptors)) {}

    void start(const MValue& current, double velocity, bool reduce_motion) override {
        current_ = current;
        velocity_ = velocity;
        reduce_ = reduce_motion;
        index_ = 0;
        begin(0);
    }

    bool step(double dt, std::vector<Completion>& completions) override {
        while (active_) {
            bool finished = active_->step(dt, completions);
            current_ = active_->value();
            velocity_ = active_->velocity();
            if (!finished) return false;
            dt = 0;
            if (!begin(index_ + 1)) return true;
        }
        return true;
    }

    void interrupt(std::vector<Completion>& completions) override {
        if (active_) active_->interrupt(completions);
        // Animations that never started report interruption too.
        for (size_t i = index_ + 1; i < descriptors_.size(); ++i) {
            if (auto callback = callback_of(descriptors_[i])) completions.push_back({callback, false});
        }
        active_.reset();
    }

    MValue value() const override { return active_ ? active_->value() : current_; }
    double velocity() const override { return active_ ? active_->velocity() : velocity_; }

private:
    bool begin(size_t index) {
        index_ = index;
        active_.reset();
        if (index >= descriptors_.size()) return false;
        std::string error;
        active_ = make_animation(descriptors_[index], error);
        if (!active_) return begin(index + 1);
        active_->start(current_, velocity_, reduce_);
        return true;
    }

    std::vector<MValue> descriptors_;
    std::unique_ptr<Animation> active_;
    size_t index_ = 0;
    MValue current_;
    double velocity_ = 0;
    bool reduce_ = false;
};

class Repeat final : public Animation {
public:
    explicit Repeat(MValue descriptor) : descriptor_(std::move(descriptor)), callback_(callback_of(descriptor_)) {}

    void start(const MValue& current, double velocity, bool reduce_motion) override {
        origin_ = current;
        current_ = current;
        velocity_ = velocity;
        reduce_ = reduce_motion;
        const MValue* times = descriptor_.find("times");
        times_ = times != nullptr && times->is_number() ? times->as_int() : -1;
        const MValue* reverse = descriptor_.find("reverse");
        reverse_ = reverse != nullptr && reverse->truthy();
        iteration_ = 0;
        if (reduced(descriptor_, reduce_motion)) {
            // Reduced motion: a finite repeat lands where it would end; an endless one stays put.
            done_ = true;
            if (times_ > 0) {
                std::string error;
                auto once = make_animation(child_descriptor(times_ - 1), error);
                if (once) {
                    std::vector<Completion> ignored;
                    once->start(current_, 0, true);
                    once->step(0, ignored);
                    current_ = once->value();
                }
            }
            return;
        }
        begin();
    }

    bool step(double dt, std::vector<Completion>& completions) override {
        if (done_) {
            if (callback_ && !reported_) {
                completions.push_back({callback_, true});
                reported_ = true;
            }
            return true;
        }
        // Instant iterations (a zero duration) yield after a few, so an endless
        // repeat can't spin the UI thread inside one frame.
        for (int spins = 0; active_; ++spins) {
            if (spins >= 16) return false;
            bool finished = active_->step(dt, completions);
            current_ = active_->value();
            velocity_ = active_->velocity();
            if (!finished) return false;
            dt = 0;
            ++iteration_;
            if (times_ > 0 && iteration_ >= times_) {
                done_ = true;
                active_.reset();
                if (callback_ && !reported_) {
                    completions.push_back({callback_, true});
                    reported_ = true;
                }
                return true;
            }
            begin();
        }
        return done_;
    }

    void interrupt(std::vector<Completion>& completions) override {
        if (active_) active_->interrupt(completions);
        if (callback_ && !reported_) completions.push_back({callback_, false});
        reported_ = true;
        done_ = true;
        active_.reset();
    }

    MValue value() const override { return active_ ? active_->value() : current_; }
    double velocity() const override { return active_ ? active_->velocity() : velocity_; }

private:
    MValue child_descriptor(int64_t iteration) const {
        const MValue* child = descriptor_.find("animation");
        if (child == nullptr) return MValue();
        if (!reverse_ || iteration % 2 == 0 || child->find("to") == nullptr) return *child;
        // Odd iterations of a reversing repeat head back to where the first began.
        Map members = child->as_map();
        for (auto& member : members) {
            if (member.first == "to") member.second = origin_;
        }
        return MValue::map(std::move(members));
    }

    void begin() {
        std::string error;
        active_ = make_animation(child_descriptor(iteration_), error);
        if (!active_) {
            done_ = true;
            return;
        }
        // Without reversing, every iteration starts over from the origin.
        active_->start(reverse_ ? current_ : origin_, velocity_, false);
    }

    MValue descriptor_;
    std::shared_ptr<const Closure> callback_;
    std::unique_ptr<Animation> active_;
    MValue origin_, current_;
    double velocity_ = 0;
    int64_t times_ = -1, iteration_ = 0;
    bool reverse_ = false, reduce_ = false, done_ = false, reported_ = false;
};

}  // namespace

double decay_position(double from, double velocity, double deceleration, double elapsed_ms) {
    deceleration = std::min(0.999999, std::max(0.000001, deceleration));
    return from + velocity / 1000.0 * (1 - std::pow(deceleration, std::max(0.0, elapsed_ms))) / (1 - deceleration);
}

bool is_animation(const MValue& value) {
    const MValue* marker = value.find("__animation__");
    return marker != nullptr && marker->truthy();
}

std::function<double(double)> easing_function(const MValue& easing) {
    struct Curve {
        const char* name;
        double x1, y1, x2, y2;
    };
    static const Curve kNamed[] = {
        {"linear", 0, 0, 1, 1},
        // The curves `pythonnative.motion.Easing` defines; quad and cubic are exact as beziers.
        {"ease", 0.42, 0, 1, 1},
        {"ease_in", 0.42, 0, 1, 1},
        {"ease_out", 0, 0, 0.58, 1},
        {"ease_in_out", 0.42, 0, 0.58, 1},
        {"quad", 1.0 / 3.0, 0, 2.0 / 3.0, 1.0 / 3.0},
        {"cubic", 1.0 / 3.0, 0, 2.0 / 3.0, 0},
    };
    if (easing.is_none()) return [](double t) { return bezier(t, 0.42, 0, 0.58, 1); };
    if (easing.is_str()) {
        if (easing.as_str() == "linear") return [](double t) { return t; };
        if (easing.as_str() == "bounce") return bounce;
        for (const Curve& curve : kNamed) {
            if (easing.as_str() == curve.name) {
                Curve c = curve;
                return [c](double t) { return bezier(t, c.x1, c.y1, c.x2, c.y2); };
            }
        }
        return nullptr;
    }
    if (const MValue* samples = easing.find("samples"); samples != nullptr && samples->is_seq() && samples->as_seq().size() >= 2) {
        std::vector<double> points;
        for (const MValue& item : samples->as_seq()) {
            if (!item.is_number()) return nullptr;
            points.push_back(item.as_double());
        }
        return [points](double t) {
            double position = std::min(1.0, std::max(0.0, t)) * static_cast<double>(points.size() - 1);
            size_t index = std::min(points.size() - 2, static_cast<size_t>(position));
            double fraction = position - static_cast<double>(index);
            return points[index] + (points[index + 1] - points[index]) * fraction;
        };
    }
    if (easing.is_seq() && easing.as_seq().size() == 4) {
        const Seq& p = easing.as_seq();
        for (const MValue& item : p) {
            if (!item.is_number()) return nullptr;
        }
        double x1 = p[0].as_double(), y1 = p[1].as_double(), x2 = p[2].as_double(), y2 = p[3].as_double();
        return [=](double t) { return bezier(t, x1, y1, x2, y2); };
    }
    return nullptr;
}

std::unique_ptr<Animation> make_animation(const MValue& descriptor, std::string& error) {
    if (!is_animation(descriptor)) {
        error = "not an animation";
        return nullptr;
    }
    const MValue* type = descriptor.find("type");
    std::string kind = type != nullptr && type->is_str() ? type->as_str() : std::string();
    if (kind == "timing") {
        const MValue* easing = descriptor.find("easing");
        if (!easing_function(easing != nullptr ? *easing : MValue())) {
            error = "unknown easing";
            return nullptr;
        }
        return std::make_unique<Timing>(descriptor);
    }
    if (kind == "spring") return std::make_unique<Spring>(descriptor);
    if (kind == "decay") {
        const MValue* velocity = descriptor.find("velocity");
        if (velocity == nullptr || !velocity->is_number()) {
            error = "with_decay() needs a velocity";
            return nullptr;
        }
        return std::make_unique<Decay>(descriptor);
    }
    if (kind == "delay") {
        const MValue* child = descriptor.find("animation");
        std::unique_ptr<Animation> inner = child != nullptr ? make_animation(*child, error) : nullptr;
        if (!inner) return nullptr;
        return std::make_unique<Delay>(descriptor, std::move(inner));
    }
    if (kind == "sequence") {
        const MValue* children = descriptor.find("animations");
        if (children == nullptr || !children->is_seq()) {
            error = "with_sequence() needs animations";
            return nullptr;
        }
        for (const MValue& child : children->as_seq()) {
            if (!is_animation(child)) {
                error = "with_sequence() takes animations";
                return nullptr;
            }
        }
        return std::make_unique<Sequence>(children->as_seq());
    }
    if (kind == "repeat") {
        const MValue* child = descriptor.find("animation");
        if (child == nullptr || !is_animation(*child)) {
            error = "with_repeat() needs an animation";
            return nullptr;
        }
        const MValue* times = descriptor.find("times");
        if (times != nullptr && times->is_number() && times->as_double() < 1) {
            error = "with_repeat() needs times of at least 1, or None to repeat forever";
            return nullptr;
        }
        return std::make_unique<Repeat>(descriptor);
    }
    error = "unknown animation " + kind;
    return nullptr;
}

}  // namespace pn::motion
