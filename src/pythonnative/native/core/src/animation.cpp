#include "animation.h"

#include <algorithm>
#include <cmath>
#include <cstdio>

#include "core.h"

namespace pn {

namespace {

constexpr double kDefaultDeceleration = 0.998;
constexpr double kRestVelocity = 0.001;
constexpr double kRestDistance = 0.1;

const std::set<std::string>& direct_props() {
    static const std::set<std::string> props = {"opacity", "translate_x", "translate_y", "scale", "scale_x",
                                                "scale_y", "rotate",      "rotate_x",    "rotate_y"};
    return props;
}

double number(const Value* value, double fallback = 0) {
    return value != nullptr && value->is_number() ? value->as_double() : fallback;
}

std::string view_key(int64_t surface, int64_t tag) {
    return std::to_string(surface) + ":" + std::to_string(tag);
}

std::string prop_key(int64_t surface, int64_t tag, const std::string& prop) {
    return view_key(surface, tag) + ":" + prop;
}

double bezier_coordinate(double u, double a, double b) {
    return 3 * (1 - u) * (1 - u) * u * a + 3 * (1 - u) * u * u * b + u * u * u;
}

double bezier(double t, double x1, double y1, double x2, double y2) {
    double low = 0, high = 1;
    for (int i = 0; i < 18; ++i) {
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

double clamp_deceleration(double d) {
    if (!std::isfinite(d)) return kDefaultDeceleration;
    return std::min(0.999999, std::max(0.000001, d));
}

double decay_velocity(double v0, double d, double t) {
    return v0 * std::pow(clamp_deceleration(d), std::max(0.0, t));
}

double decay_position(double x0, double v0, double d, double t) {
    d = clamp_deceleration(d);
    return x0 + v0 * (1 - std::pow(d, std::max(0.0, t))) / (1 - d);
}

double decay_final(double x0, double v0, double d) {
    return x0 + v0 / (1 - clamp_deceleration(d));
}

bool decay_at_rest(double x0, double v0, double d, double t) {
    return std::fabs(decay_velocity(v0, d, t)) < kRestVelocity ||
           std::fabs(decay_position(x0, v0, d, t) - decay_final(x0, v0, d)) < kRestDistance;
}

std::string hex_color(const Array& from, const Array& to, double t) {
    std::string out = "#";
    size_t count = std::min(from.size(), to.size());
    for (size_t i = 0; i < count; ++i) {
        double a = from[i].as_double(), b = to[i].as_double();
        double channel = std::round(a + (b - a) * std::min(1.0, std::max(0.0, t)));
        char buffer[16];  // two digits; sized for any int so compilers can't warn about truncation
        std::snprintf(buffer, sizeof(buffer), "%02X", static_cast<int>(std::min(255.0, std::max(0.0, channel))));
        out += buffer;
    }
    return out;
}

}  // namespace

std::function<double(double)> easing_function(const Value* easing) {
    struct Curve {
        const char* name;
        double x1, y1, x2, y2;
    };
    static const Curve kNamed[] = {
        {"linear", 0, 0, 1, 1},
        {"ease", 0.42, 0, 1, 1},
        {"ease_in", 0.42, 0, 1, 1},
        {"ease_out", 0, 0, 0.58, 1},
        {"ease_in_out", 0.42, 0, 0.58, 1},
        {"quad", 1.0 / 3.0, 0, 2.0 / 3.0, 1.0 / 3.0},
        {"cubic", 1.0 / 3.0, 0, 2.0 / 3.0, 0},
    };
    if (easing == nullptr || easing->is_null()) {
        return [](double t) { return bezier(t, 0.42, 0, 0.58, 1); };
    }
    if (easing->is_string()) {
        if (easing->as_string() == "bounce") return bounce;
        for (const Curve& curve : kNamed) {
            if (easing->as_string() == curve.name) {
                Curve c = curve;
                return [c](double t) { return bezier(t, c.x1, c.y1, c.x2, c.y2); };
            }
        }
        return nullptr;
    }
    if (const Value* samples = easing->find("samples"); samples != nullptr && samples->as_array().size() >= 2) {
        // A Python easing callable, sampled at even steps; interpolate between samples.
        std::vector<double> points;
        for (const Value& item : samples->as_array()) {
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
    if (easing->is_array() && easing->as_array().size() == 4) {
        const Array& p = easing->as_array();
        for (const Value& item : p) {
            if (!item.is_number()) return nullptr;
        }
        double x1 = p[0].as_double(), y1 = p[1].as_double(), x2 = p[2].as_double(), y2 = p[3].as_double();
        return [=](double t) { return bezier(t, x1, y1, x2, y2); };
    }
    return nullptr;
}

bool Animator::valid_request(const Value& request, std::string& error) {
    const Value* op = request.find("op");
    if (op == nullptr || !op->is_string()) {
        error = "animation requests need an op";
        return false;
    }
    const std::string& name = op->as_string();
    if (name == "graph") {
        if (request.find("graph") == nullptr || !request.find("graph")->is_object()) {
            error = "graph requests need a graph";
            return false;
        }
        return true;
    }
    if (name == "set") {
        const Value* prop = request.find("prop");
        if (prop == nullptr || !prop->is_string()) {
            error = "set requests need a prop";
            return false;
        }
        return true;
    }
    if (name == "cancel") return request.find("id") != nullptr && request.find("id")->is_integer();
    if (name != "start") {
        error = "unknown animation op " + name;
        return false;
    }
    const Value* prop = request.find("prop");
    const Value* spec = request.find("spec");
    if (prop == nullptr || !prop->is_string() || spec == nullptr || !spec->is_object() ||
        request.find("id") == nullptr || !request.find("id")->is_integer()) {
        error = "start requests need an id, a prop, and a spec";
        return false;
    }
    const Value* kind = spec->find("kind");
    std::string type = kind != nullptr ? kind->as_string() : std::string();
    if (type != "timing" && type != "spring" && type != "decay") {
        error = "unknown animation kind";
        return false;
    }
    if (type == "timing" && !easing_function(spec->find("easing"))) {
        error = "unknown easing";
        return false;
    }
    if (type == "decay" && (spec->find("velocity") == nullptr || !spec->find("velocity")->is_number())) {
        error = "decay needs a velocity";
        return false;
    }
    bool graph = prop->as_string().rfind("_pn_graph:", 0) == 0 || prop->as_string().rfind("_pn_value:", 0) == 0;
    if (!graph && direct_props().count(prop->as_string()) == 0) {
        error = "can't animate " + prop->as_string() + " natively";
        return false;
    }
    if (!graph && type != "decay" && spec->find("to") == nullptr) {
        error = "timing and spring animations need a target";
        return false;
    }
    return true;
}

void Animator::handle(int64_t surface, int64_t tag, const Value& request) {
    const std::string& op = request.find("op")->as_string();
    if (op == "graph") {
        install(surface, *request.find("graph"));
    } else if (op == "set") {
        const std::string& prop = request.find("prop")->as_string();
        const Value* value = request.find("value");
        if (prop.rfind("_pn_graph:", 0) == 0) {
            int64_t node = std::strtoll(prop.c_str() + 10, nullptr, 10);
            double next = number(value, NAN);
            if (!std::isfinite(next) || (values_.count(node) && values_[node] == next)) return;
            values_[node] = next;
            std::unordered_set<int64_t> changed = {node};
            evaluate(&changed);
        } else if (value != nullptr) {
            write({surface, tag, prop, 0}, *value);
        }
    } else if (op == "start") {
        int64_t id = request.find("id")->as_int();
        if (!start(surface, tag, request)) complete(surface, id, false, nullptr);
    } else if (op == "cancel") {
        cancel(surface, request.find("id")->as_int());
    }
}

void Animator::install(int64_t surface, const Value& spec) {
    int64_t id = spec.find("id") ? spec.find("id")->as_int() : 0;
    Graph graph;
    for (const Value& raw : spec.find("nodes") ? spec.find("nodes")->as_array() : Array()) {
        Node node;
        node.id = raw.find("id") ? raw.find("id")->as_int() : 0;
        node.kind = raw.find("kind") ? raw.find("kind")->as_string() : std::string();
        if (const Value* inputs = raw.find("inputs")) {
            for (const Value& input : inputs->as_array()) {
                Input parsed;
                if (const Value* source = input.find("node"); source != nullptr && !source->is_null()) {
                    parsed.constant = false;
                    parsed.node = source->as_int();
                } else {
                    parsed.value = number(input.find("constant"));
                }
                node.inputs.push_back(parsed);
            }
        }
        node.minimum = number(raw.find("minimum"));
        node.maximum = number(raw.find("maximum"));
        if (const Value* ranges = raw.find("ranges")) {
            for (const Value& item : ranges->as_array()) node.ranges.push_back(item.as_double());
        }
        if (const Value* outputs = raw.find("outputs")) node.outputs = outputs->as_array();
        node.color = raw.find("color") != nullptr && raw.find("color")->as_bool();
        if (const Value* left = raw.find("left"); left != nullptr && left->is_string()) node.left = left->as_string();
        if (const Value* right = raw.find("right"); right != nullptr && right->is_string()) node.right = right->as_string();
        if (values_.count(node.id) == 0) values_[node.id] = number(raw.find("value"));
        if (previous_.count(node.id) == 0) previous_[node.id] = number(raw.find("previous"));
        graph.nodes.push_back(std::move(node));
    }
    for (const Value& raw : spec.find("bindings") ? spec.find("bindings")->as_array() : Array()) {
        const Array& parts = raw.as_array();
        if (parts.size() != 3) continue;
        graph.bindings.push_back({surface, parts[0].as_int(), parts[1].as_string(), parts[2].as_int()});
    }
    // A reinstalled graph replaces every graph that shares one of its nodes.
    std::unordered_set<int64_t> ids;
    for (const Node& node : graph.nodes) ids.insert(node.id);
    for (auto it = graphs_.begin(); it != graphs_.end();) {
        bool shares = std::any_of(it->second.nodes.begin(), it->second.nodes.end(),
                                  [&](const Node& node) { return ids.count(node.id) != 0; });
        it = shares ? graphs_.erase(it) : std::next(it);
    }
    if (!graph.bindings.empty()) graphs_[id] = std::move(graph);
    collect();
    evaluate(nullptr);
}

void Animator::collect() {
    membership_.clear();
    view_graphs_.clear();
    std::unordered_set<int64_t> live;
    for (const auto& [id, driver] : drivers_) {
        if (driver.standalone) live.insert(driver.node);
    }
    for (const auto& [graph_id, graph] : graphs_) {
        for (const Node& node : graph.nodes) {
            membership_[node.id].insert(graph_id);
            live.insert(node.id);
        }
        for (const Binding& binding : graph.bindings) view_graphs_[view_key(binding.surface, binding.tag)].insert(graph_id);
    }
    for (auto it = values_.begin(); it != values_.end();) it = live.count(it->first) ? std::next(it) : values_.erase(it);
    for (auto it = previous_.begin(); it != previous_.end();) it = live.count(it->first) ? std::next(it) : previous_.erase(it);
    for (auto it = outputs_.begin(); it != outputs_.end();) it = live.count(it->first) ? std::next(it) : outputs_.erase(it);
    std::vector<std::pair<int64_t, int64_t>> stopped;
    for (const auto& [id, driver] : drivers_) {
        if (live.count(driver.node) == 0) stopped.emplace_back(driver.surface, id);
    }
    for (const auto& [surface, id] : stopped) {
        drivers_.erase(id);
        complete(surface, id, false, nullptr);
    }
}

double Animator::interpolate(const Node& node, double incoming) {
    const std::vector<double>& ranges = node.ranges;
    if (ranges.size() < 2 || node.outputs.size() != ranges.size()) return 0;
    double x = incoming;
    const std::string& mode = x < ranges.front() ? node.left : x > ranges.back() ? node.right : std::string("extend");
    if (mode == "identity") return x;
    if (mode == "clamp") x = std::min(ranges.back(), std::max(ranges.front(), x));
    size_t index = 0;
    while (index < ranges.size() - 2 && x >= ranges[index + 1]) ++index;
    double span = ranges[index + 1] - ranges[index];
    double t = span == 0 ? 0 : (x - ranges[index]) / span;
    if (node.color) {
        outputs_[node.id] = Value::string(hex_color(node.outputs[index].as_array(), node.outputs[index + 1].as_array(), t));
        return 0;
    }
    double from = node.outputs[index].as_double(), to = node.outputs[index + 1].as_double();
    return from + (to - from) * t;
}

void Animator::evaluate(const std::unordered_set<int64_t>* changed) {
    std::set<int64_t> affected;
    if (changed == nullptr) {
        for (const auto& [id, graph] : graphs_) affected.insert(id);
    } else {
        for (int64_t node : *changed) {
            auto found = membership_.find(node);
            if (found != membership_.end()) affected.insert(found->second.begin(), found->second.end());
        }
    }
    for (int64_t graph_id : affected) {
        auto found = graphs_.find(graph_id);
        if (found == graphs_.end()) continue;
        Graph& graph = found->second;
        std::unordered_set<int64_t> dirty;
        if (changed != nullptr) dirty = *changed;
        for (const Node& node : graph.nodes) {
            bool stale = changed == nullptr || dirty.count(node.id) != 0 ||
                         std::any_of(node.inputs.begin(), node.inputs.end(),
                                     [&](const Input& input) { return !input.constant && dirty.count(input.node) != 0; });
            if (!stale) continue;
            dirty.insert(node.id);
            std::vector<double> inputs;
            for (const Input& input : node.inputs) inputs.push_back(input.constant ? input.value : values_[input.node]);
            double a = inputs.empty() ? 0 : inputs[0];
            double b = inputs.size() > 1 ? inputs[1] : 0;
            double value = 0;
            if (node.kind == "value") value = values_[node.id];
            else if (node.kind == "add") value = a + b;
            else if (node.kind == "subtract") value = a - b;
            else if (node.kind == "multiply") value = a * b;
            else if (node.kind == "divide") value = b == 0 ? 0 : a / b;
            else if (node.kind == "modulo") value = b == 0 ? 0 : std::fmod(a, b);
            else if (node.kind == "negate") value = -a;
            else if (node.kind == "diff_clamp") {
                double prior = previous_.count(node.id) ? previous_[node.id] : a;
                value = std::min(node.maximum, std::max(node.minimum, values_[node.id] + a - prior));
                previous_[node.id] = a;
            } else if (node.kind == "interpolate") {
                value = interpolate(node, a);
            }
            values_[node.id] = std::isfinite(value) ? value : 0;
            if (!node.color) outputs_[node.id] = Value::number(values_[node.id]);
        }
        for (const Binding& binding : graph.bindings) {
            auto output = outputs_.find(binding.node);
            if (output != outputs_.end()) write(binding, output->second);
        }
    }
}

void Animator::write(const Binding& binding, const Value& value) {
    std::string key = prop_key(binding.surface, binding.tag, binding.prop);
    auto applied = applied_.find(key);
    if (applied != applied_.end() && applied->second == value) return;
    applied_[key] = value;
    ByteWriter out;
    out.i64(binding.tag);
    out.str(binding.prop);
    out.value(value);
    writes_.insert(writes_.end(), out.bytes().begin(), out.bytes().end());
    ++write_count_;
}

bool Animator::take_writes(std::vector<uint8_t>& out) {
    out.clear();
    if (write_count_ == 0) return false;
    ByteWriter header;
    header.u32(write_count_);
    out = header.take();
    out.insert(out.end(), writes_.begin(), writes_.end());
    writes_.clear();
    write_count_ = 0;
    return true;
}

void Animator::event(const Value& bindings, const Value& payload) {
    std::unordered_set<int64_t> changed;
    for (const auto& [field, node] : bindings.as_object()) {
        const Value* value = payload.find(field);
        if (value == nullptr || !value->is_number()) continue;
        int64_t id = node.as_int();
        double next = value->as_double();
        if (values_.count(id) == 0 || values_[id] != next) {
            values_[id] = next;
            changed.insert(id);
        }
    }
    if (!changed.empty()) evaluate(&changed);
}

bool Animator::start(int64_t surface, int64_t tag, const Value& request) {
    int64_t id = request.find("id")->as_int();
    const std::string& prop = request.find("prop")->as_string();
    const Value& spec = *request.find("spec");
    auto existing = drivers_.find(id);
    if (existing != drivers_.end()) drivers_.erase(existing);
    Driver driver;
    driver.id = id;
    driver.surface = surface;
    driver.spec = spec;
    driver.report = spec.find("report") != nullptr && spec.find("report")->as_bool();
    if (prop.rfind("_pn_graph:", 0) == 0) {
        driver.node = std::strtoll(prop.c_str() + 10, nullptr, 10);
        if (values_.count(driver.node) == 0) return false;
    } else if (prop.rfind("_pn_value:", 0) == 0) {
        // A value no view is bound to: drive it alone and report its frames.
        driver.node = std::strtoll(prop.c_str() + 10, nullptr, 10);
        driver.standalone = true;
        if (values_.count(driver.node) == 0) values_[driver.node] = number(spec.find("from"));
    } else {
        // A direct prop animation drives a one-node graph bound to the view.
        double from = 0;
        if (const Value* start = spec.find("from"); start != nullptr && start->is_number()) {
            from = start->as_double();
        } else if (auto applied = applied_.find(prop_key(surface, tag, prop)); applied != applied_.end() && applied->second.is_number()) {
            from = applied->second.as_double();
        } else {
            const Value* current = lookup_ ? lookup_(surface, tag, prop) : nullptr;
            from = current != nullptr && current->is_number() ? current->as_double()
                   : (prop == "opacity" || prop.rfind("scale", 0) == 0) ? 1.0
                                                                       : 0.0;
        }
        int64_t node = -(++synthetic_ids_);
        Graph graph;
        Node value;
        value.id = node;
        value.kind = "value";
        graph.nodes.push_back(value);
        graph.bindings.push_back({surface, tag, prop, node});
        values_[node] = from;
        graphs_[node] = std::move(graph);
        collect();
        driver.node = node;
        driver.direct_graph = node;
    }
    driver.current = number(spec.find("from"), values_[driver.node]);
    driver.velocity = number(spec.find("velocity"), number(spec.find("initial_velocity")));
    driver.active = true;
    drivers_[id] = std::move(driver);
    core_.request_frames();
    return true;
}

void Animator::cancel(int64_t surface, int64_t id) {
    auto found = drivers_.find(id);
    if (found == drivers_.end()) return;
    Value value = Value::number(values_[found->second.node]);
    int64_t direct = found->second.direct_graph;
    bool standalone = found->second.standalone;
    drivers_.erase(found);
    if (direct != 0) graphs_.erase(direct);
    if (direct != 0 || standalone) collect();
    complete(surface, id, false, &value);
}

void Animator::complete(int64_t surface, int64_t id, bool finished, const Value* value) {
    std::string payload = "{\"id\":" + std::to_string(id) + ",\"finished\":" + (finished ? "true" : "false");
    if (value != nullptr) {
        payload += ",\"value\":";
        write_json(*value, payload);
    }
    payload += "}";
    core_.emit("animation", surface, 0, "", payload);
}

bool Animator::advance(Driver& driver, double dt) {
    driver.elapsed += dt;
    const Value& spec = driver.spec;
    double delay = number(spec.find("delay_ms")) / 1000;
    if (driver.elapsed < delay) return false;
    double target = number(spec.find("to"));
    bool done = false;
    const std::string kind = spec.find("kind") ? spec.find("kind")->as_string() : std::string();
    if (kind == "spring") {
        double mass = std::max(0.001, number(spec.find("mass"), 1));
        double stiffness = number(spec.find("stiffness"), 100);
        double damping = number(spec.find("damping"), 10);
        int steps = std::max(1, static_cast<int>(std::ceil(dt / 0.004)));
        for (int i = 0; i < steps; ++i) {
            double step = dt / steps;
            driver.velocity += (-stiffness * (driver.current - target) - damping * driver.velocity) / mass * step;
            driver.current += driver.velocity * step;
        }
        done = std::fabs(driver.velocity) < number(spec.find("rest_speed_threshold"), 0.01) &&
               std::fabs(driver.current - target) < number(spec.find("rest_displacement_threshold"), 0.01);
        if (done) driver.current = target;
    } else if (kind == "decay") {
        // React Native's model: velocity in points per millisecond, v(t) = v0 * d^t.
        double from = number(spec.find("from"), driver.current);
        double v0 = number(spec.find("velocity"));
        double d = number(spec.find("deceleration"), kDefaultDeceleration);
        double t = (driver.elapsed - delay) * 1000;
        done = decay_at_rest(from, v0, d, t);
        driver.current = done ? decay_final(from, v0, d) : decay_position(from, v0, d, t);
        driver.velocity = decay_velocity(v0, d, t);
        target = decay_final(from, v0, d);
    } else {
        double duration = std::max(0.001, number(spec.find("duration_ms"), 300) / 1000);
        double t = std::min(1.0, std::max(0.0, (driver.elapsed - delay) / duration));
        auto easing = easing_function(spec.find("easing"));
        double eased = easing ? easing(t) : t;
        double from = number(spec.find("from"), values_[driver.node]);
        if (!spec.find("from")) {
            // Without an explicit start, the value at the first frame is the origin.
            if (!driver.spec.find("_origin")) {
                Object augmented = driver.spec.as_object();
                augmented.emplace_back("_origin", Value::number(values_[driver.node]));
                driver.spec = Value::object(std::move(augmented));
            }
            from = number(driver.spec.find("_origin"));
        }
        done = t >= 1;
        driver.current = done ? target : from + (target - from) * eased;
    }
    if (reduce_motion_) {
        driver.current = target;
        done = true;
    }
    values_[driver.node] = std::isfinite(driver.current) ? driver.current : 0;
    return done;
}

bool Animator::frame(double timestamp_ms) {
    double dt = previous_time_ < 0 ? 1.0 / 60.0 : std::min(0.064, std::max(0.0, (timestamp_ms - previous_time_) / 1000));
    previous_time_ = timestamp_ms;
    std::unordered_set<int64_t> changed;
    std::vector<int64_t> completed;
    for (auto& [id, driver] : drivers_) {
        if (!driver.active) continue;
        double before = values_[driver.node];
        if (advance(driver, dt)) completed.push_back(id);
        if (before != values_[driver.node]) changed.insert(driver.node);
    }
    if (!changed.empty()) evaluate(&changed);
    for (auto& [id, driver] : drivers_) {
        if (driver.report && driver.active) {
            core_.emit("animation", driver.surface, 0, "",
                       "{\"id\":" + std::to_string(id) + ",\"value\":" + to_json(Value::number(values_[driver.node])) + "}");
        }
    }
    for (int64_t id : completed) {
        auto found = drivers_.find(id);
        if (found == drivers_.end()) continue;
        Value value = Value::number(values_[found->second.node]);
        int64_t direct = found->second.direct_graph;
        int64_t surface = found->second.surface;
        drivers_.erase(found);
        if (direct != 0) graphs_.erase(direct);
        complete(surface, id, true, &value);
    }
    if (!completed.empty()) collect();
    bool active = running();
    if (!active) previous_time_ = -1;
    return active;
}

void Animator::reset() {
    graphs_.clear();
    values_.clear();
    previous_.clear();
    outputs_.clear();
    membership_.clear();
    drivers_.clear();
    applied_.clear();
    view_graphs_.clear();
    writes_.clear();
    write_count_ = 0;
    previous_time_ = -1;
}

bool Animator::running() const {
    return std::any_of(drivers_.begin(), drivers_.end(), [](const auto& entry) { return entry.second.active; });
}

void Animator::forget(int64_t surface, int64_t tag) {
    std::string key = view_key(surface, tag);
    std::string prefix = key + ":";
    for (auto it = applied_.begin(); it != applied_.end();) {
        it = it->first.rfind(prefix, 0) == 0 ? applied_.erase(it) : std::next(it);
    }
    auto bound = view_graphs_.find(key);
    if (bound == view_graphs_.end()) return;
    for (int64_t graph_id : bound->second) {
        auto found = graphs_.find(graph_id);
        if (found == graphs_.end()) continue;
        auto& bindings = found->second.bindings;
        bindings.erase(std::remove_if(bindings.begin(), bindings.end(),
                                      [&](const Binding& b) { return b.surface == surface && b.tag == tag; }),
                       bindings.end());
        if (bindings.empty()) graphs_.erase(found);
    }
    collect();
}

void Animator::forget_surface(int64_t surface) {
    for (auto it = graphs_.begin(); it != graphs_.end();) {
        auto& bindings = it->second.bindings;
        bindings.erase(std::remove_if(bindings.begin(), bindings.end(), [&](const Binding& b) { return b.surface == surface; }),
                       bindings.end());
        it = bindings.empty() ? graphs_.erase(it) : std::next(it);
    }
    std::string prefix = std::to_string(surface) + ":";
    for (auto it = applied_.begin(); it != applied_.end();) {
        it = it->first.rfind(prefix, 0) == 0 ? applied_.erase(it) : std::next(it);
    }
    collect();
}

}  // namespace pn
