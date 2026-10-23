// Gesture recognition from raw pointer streams, with Gesture Handler's
// activation rules and `Simultaneous`, `Race`, and `Exclusive` composition.
//
// Android, the browser preview, and headless tests feed pointers here; iOS
// uses UIKit recognizers configured with the same specs.
#pragma once

#include <functional>
#include <map>
#include <memory>
#include <optional>
#include <set>
#include <string>
#include <vector>

#include "value.h"

namespace pn {

struct Point {
    double x = 0;
    double y = 0;
};

/// `[negative, positive]` bounds; crossing either side is strict.
struct Offset {
    std::optional<double> negative;
    std::optional<double> positive;
    bool crosses(double delta) const {
        return (negative && delta < *negative) || (positive && delta > *positive);
    }
};

/// One leaf gesture, decoded from an entry of the `gestures` prop.
struct GestureConfig {
    std::string kind;
    bool enabled = true;
    int taps = 1;
    double max_distance = 12;
    double min_duration_ms = 500;
    std::optional<double> min_distance = 10.0;
    int min_pointers = 1;
    std::optional<int> max_pointers;
    std::optional<Offset> active_offset_x, active_offset_y, fail_offset_x, fail_offset_y;
    std::optional<double> min_velocity;
    std::optional<std::string> direction;
    int pointers = 1;
    std::optional<std::set<int>> simultaneous;  // nullopt: alongside everything
    std::set<int> wait_for;
    Value animated_events;                       // state -> {field: node id}
};

GestureConfig decode_gesture(const Value& spec);

/// A payload's ordered fields; "kind" and "state" come first.
using Payload = Object;
using EmitFn = std::function<void(int, const Payload&)>;

class Recognizer;

/// Arbitrates one view's recognizers.
class GestureArbiter {
public:
    GestureArbiter(std::vector<GestureConfig> specs, EmitFn emit);
    ~GestureArbiter();

    void down(int pointer, double x, double y, double t, double window_x, double window_y);
    void move(int pointer, double x, double y, double t, double window_x, double window_y);
    void up(int pointer, double x, double y, double t, double window_x, double window_y);
    void cancel(double t);
    void poll(double t);
    std::optional<double> deadline() const;
    bool has_active_pan() const;
    const std::vector<GestureConfig>& specs() const { return specs_; }

private:
    enum class State { Possible, Waiting, Active, Done, Failed };
    Recognizer* recognizer_for(int index) const;
    void deliver(int index, const Payload& payload);
    bool simultaneous(int a, int b) const;
    void mediate(int index, const Payload& payload);
    void request_activation(int index, const Payload& payload);
    void activate(int index, const std::vector<Payload>& payloads);
    void set_failed(int index);
    void resolved(int index, bool succeeded);

    std::vector<GestureConfig> specs_;
    EmitFn emit_;
    Point window_offset_;
    std::vector<std::pair<int, Point>> pointers_;  // in press order
    std::vector<std::unique_ptr<Recognizer>> recognizers_;
    std::vector<int> indices_;
    std::map<int, State> states_;
    std::map<int, std::vector<Payload>> buffers_;
    double last_time_ = 0;
};

}  // namespace pn
