// Animation drivers for shared values and layout animations (RFC 0009).
//
// A driver animates one value: a number, or a color as four channels. It's
// built from the descriptor `with_timing`, `with_spring`, `with_decay`,
// `with_delay`, `with_sequence`, or `with_repeat` returns (a map marked
// `__animation__`), started from the value it replaces, and stepped once per
// display frame. Completion callbacks (`on_finish` worklets) are collected
// rather than run, so the runtime runs them after the frame's writes.
#pragma once

#include <functional>
#include <memory>
#include <string>
#include <vector>

#include "motion_vm.h"

namespace pn::motion {

/// The easing curve a descriptor names: a name, `[x1, y1, x2, y2]`, or
/// `{"samples": [...]}`. Null means ease-in-out. Returns nullptr when invalid.
std::function<double(double)> easing_function(const MValue& easing);

/// A finished (or interrupted) animation's `on_finish` worklet.
struct Completion {
    std::shared_ptr<const Closure> callback;
    bool finished = false;
};

class Animation {
public:
    virtual ~Animation() = default;
    /// Begin from `current`, moving at `velocity` units per second.
    virtual void start(const MValue& current, double velocity, bool reduce_motion) = 0;
    /// Advance by `dt` seconds; returns true once finished.
    virtual bool step(double dt, std::vector<Completion>& completions) = 0;
    /// Report interruption to every `on_finish` still waiting.
    virtual void interrupt(std::vector<Completion>& completions) = 0;
    virtual MValue value() const = 0;
    virtual double velocity() const { return 0; }
};

/// Build a driver from a descriptor. Returns nullptr with `error` set.
std::unique_ptr<Animation> make_animation(const MValue& descriptor, std::string& error);

/// Whether a value is an animation descriptor.
bool is_animation(const MValue& value);

/// React Native's decay model, with velocity in units per second.
double decay_position(double from, double velocity, double deceleration, double elapsed_ms);

}  // namespace pn::motion
