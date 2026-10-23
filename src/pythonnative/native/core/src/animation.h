// Animation graphs and drivers, evaluated on the UI thread.
//
// Python installs expression graphs (`animation_graph.py`) and starts
// timing, spring, and decay drivers on graph nodes or directly on view
// props. Each display frame advances the drivers, re-evaluates affected
// graphs, and queues `(tag, prop, value)` writes for the platform.
#pragma once

#include <cstdint>
#include <functional>
#include <map>
#include <set>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

#include "value.h"

namespace pn {

class Core;

class Animator {
public:
    /// Looks up a mounted view's current prop value (for direct prop animations).
    using PropLookup = std::function<const Value*(int64_t surface, int64_t tag, const std::string& prop)>;

    explicit Animator(Core& core) : core_(core) {}

    void set_lookup(PropLookup lookup) { lookup_ = std::move(lookup); }
    /// Whether `request` is acceptable; checked when Python queues it.
    static bool valid_request(const Value& request, std::string& error);
    /// Apply one queued request (`graph`, `set`, `start`, or `cancel`).
    void handle(int64_t surface, int64_t tag, const Value& request);
    /// Feed an event's numeric fields into bound graph nodes.
    void event(const Value& bindings, const Value& payload);
    /// Drop graphs, bindings, and drivers for a destroyed view.
    void forget(int64_t surface, int64_t tag);
    void forget_surface(int64_t surface);
    /// Advance active drivers; returns whether any are still running.
    bool frame(double timestamp_ms);
    bool running() const;
    void set_reduce_motion(bool enabled) { reduce_motion_ = enabled; }
    /// Forget every graph, driver, and pending write.
    void reset();

    /// Pending writes, encoded as documented in `pn_core.h`.
    bool take_writes(std::vector<uint8_t>& out);

private:
    struct Input {
        bool constant = true;
        double value = 0;
        int64_t node = 0;
    };
    struct Node {
        int64_t id = 0;
        std::string kind;
        std::vector<Input> inputs;
        double minimum = 0, maximum = 0;
        std::vector<double> ranges;
        std::vector<Value> outputs;
        bool color = false;
        std::string left = "extend", right = "extend";
    };
    struct Binding {
        int64_t surface = 0;
        int64_t tag = 0;
        std::string prop;
        int64_t node = 0;
    };
    struct Graph {
        std::vector<Node> nodes;
        std::vector<Binding> bindings;
    };
    struct Driver {
        int64_t id = 0;
        int64_t surface = 0;
        int64_t node = 0;
        Value spec;
        bool active = false;
        bool report = false;
        bool standalone = false;   // drives a value no view is bound to
        int64_t direct_graph = 0;  // a synthetic graph for a direct prop animation
        double elapsed = 0;
        double current = 0;
        double velocity = 0;
    };

    void install(int64_t surface, const Value& graph);
    void collect();
    void evaluate(const std::unordered_set<int64_t>* changed);
    double interpolate(const Node& node, double incoming);
    bool start(int64_t surface, int64_t tag, const Value& request);
    void cancel(int64_t surface, int64_t id);
    bool advance(Driver& driver, double dt);
    void write(const Binding& binding, const Value& value);
    void complete(int64_t surface, int64_t id, bool finished, const Value* value);

    Core& core_;
    PropLookup lookup_;
    std::map<int64_t, Graph> graphs_;
    std::unordered_map<int64_t, double> values_;
    std::unordered_map<int64_t, double> previous_;
    std::unordered_map<int64_t, Value> outputs_;
    std::unordered_map<int64_t, std::set<int64_t>> membership_;  // node -> graphs
    std::map<int64_t, Driver> drivers_;
    std::unordered_map<std::string, Value> applied_;            // "surface:tag:prop" -> last write
    std::unordered_map<std::string, std::set<int64_t>> view_graphs_;  // "surface:tag" -> graphs bound to it
    std::vector<uint8_t> writes_;
    uint32_t write_count_ = 0;
    double previous_time_ = -1;
    bool reduce_motion_ = false;
    int64_t synthetic_ids_ = 0;
};

/// The easing curve for a timing spec, or nullptr when it isn't valid.
std::function<double(double)> easing_function(const Value* easing);

}  // namespace pn
