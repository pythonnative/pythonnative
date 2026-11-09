#include "motion_runtime.h"

#include <algorithm>
#include <cmath>

#include "core.h"
#include "style.h"

namespace pn::motion {

namespace {

const std::set<std::string, std::less<>>& paint_keys() {
    static const std::set<std::string, std::less<>> keys = {
        "opacity",
        "transform",
        "background_color",
        "color",
        "border_color",
        "border_top_color",
        "border_right_color",
        "border_bottom_color",
        "border_left_color",
        "border_radius",
        "border_top_left_radius",
        "border_top_right_radius",
        "border_bottom_left_radius",
        "border_bottom_right_radius",
        "shadow_color",
        "shadow_offset",
        "shadow_opacity",
        "shadow_radius",
        "elevation",
        "tint_color",
        "placeholder_color",
        "text_shadow_color",
        "text_shadow_offset",
        "text_shadow_radius",
        "z_index",
    };
    return keys;
}

/// Transform entries layout animations compose after the view's own transform.
const char* const kTransformChannels[] = {"translate_x", "translate_y", "scale",  "scale_x", "scale_y",
                                          "rotate",      "rotate_x",    "rotate_y", "skew_x",  "skew_y"};

bool is_transform_channel(std::string_view key) {
    for (const char* name : kTransformChannels) {
        if (key == name) return true;
    }
    return false;
}

double number(const Value* value, double fallback) {
    return value != nullptr && value->is_number() ? value->as_double() : fallback;
}

std::array<double, 4> frame_of(const Value* value) {
    std::array<double, 4> out{};
    if (value != nullptr && value->is_array() && value->as_array().size() == 4) {
        for (size_t i = 0; i < 4; ++i) out[i] = value->as_array()[i].as_double();
    }
    return out;
}

const char* const kFrameKeys[] = {"frame_x", "frame_y", "frame_width", "frame_height"};

Array as_transform_list(const Value& value) {
    if (value.is_array()) return value.as_array();
    if (value.is_object() && !value.as_object().empty()) return {value};
    return {};
}

MValue lerp_value(const MValue& a, const MValue& b, double t) {
    if (a.is_number() && b.is_number()) return MValue::number(a.as_double() + (b.as_double() - a.as_double()) * t);
    if (a.is_str() && b.is_str()) {
        double x[4], y[4];
        if (parse_color(a.as_str(), x) && parse_color(b.as_str(), y)) return MValue::string(mix_colors(a.as_str(), b.as_str(), t));
    }
    if (a.is_seq() && b.is_seq() && a.as_seq().size() == b.as_seq().size()) {
        Seq items;
        for (size_t i = 0; i < a.as_seq().size(); ++i) items.push_back(lerp_value(a.as_seq()[i], b.as_seq()[i], t));
        return MValue::seq(std::move(items));
    }
    if (a.is_map() && b.is_map()) {
        Map members;
        for (const auto& [key, value] : a.as_map()) {
            const MValue* other = b.find(key);
            members.emplace_back(key, other != nullptr ? lerp_value(value, *other, t) : value);
        }
        return MValue::map(std::move(members));
    }
    return t < 1 ? a : b;
}

}  // namespace

bool animatable_style(std::string_view key, bool& layout) {
    if (paint_keys().count(key) != 0) {
        layout = false;
        return true;
    }
    if (key == "display" || key == "position" || key == "direction" || key == "overflow") return false;
    if (is_layout_style(key)) {
        layout = true;
        return true;
    }
    return false;
}

// ======================================================================
// Requests
// ======================================================================

bool Runtime::valid_request(const Value& request, std::string& error) {
    const Value* op = request.find("op");
    if (op == nullptr || !op->is_string()) {
        error = "motion requests need an op";
        return false;
    }
    const std::string& name = op->as_string();
    auto need_id = [&]() {
        const Value* id = request.find("id");
        if (id == nullptr || !id->is_integer()) {
            error = name + " requests need an id";
            return false;
        }
        return true;
    };
    if (name == "batch") {
        const Value* requests = request.find("requests");
        if (requests == nullptr || !requests->is_array()) {
            error = "batch requests need requests";
            return false;
        }
        for (const Value& inner : requests->as_array()) {
            if (!valid_request(inner, error)) return false;
        }
        return true;
    }
    if (name == "program") {
        if (!need_id()) return false;
        const Value* program = request.find("program");
        if (program == nullptr) {
            error = "program requests need a program";
            return false;
        }
        return decode_program(request.find("id")->as_int(), *program, error) != nullptr;
    }
    if (name == "shared" || name == "set" || name == "cancel") return need_id();
    if (name == "animate") {
        if (!need_id()) return false;
        const Value* animation = request.find("animation");
        if (animation == nullptr || !animation->is_object()) {
            error = "animate requests need an animation";
            return false;
        }
        return true;
    }
    if (name == "bind") {
        if (!need_id()) return false;
        const Value* kind = request.find("kind");
        static const std::set<std::string, std::less<>> kinds = {"derived", "reaction", "frame", "style", "handler"};
        if (kind == nullptr || !kind->is_string() || kinds.count(kind->as_string()) == 0) {
            error = "bind requests need a kind";
            return false;
        }
        if (request.find("closure") == nullptr) {
            error = "bind requests need a closure";
            return false;
        }
        return true;
    }
    if (name == "release") return true;
    error = "unknown motion op " + name;
    return false;
}

void Runtime::emit(int64_t surface, const std::string& payload) {
    core_.emit("motion", surface != 0 ? surface : last_surface_, 0, "", payload);
}

void Runtime::handle(const Value& request, int64_t surface) {
    surface_ = surface;
    last_surface_ = surface;
    const std::string& op = request.find("op")->as_string();
    if (op == "batch") {
        for (const Value& inner : request.find("requests")->as_array()) handle(inner, surface);
        return;
    }
    if (op == "program") define_program(request);
    else if (op == "shared") define_shared(request);
    else if (op == "set" || op == "animate") {
        int64_t id = request.find("id")->as_int();
        if (op == "set") {
            MValue value;
            std::string error;
            const Value* wire = request.find("value");
            if (wire != nullptr && from_wire(*wire, [this](int64_t p) { return programs_.count(p) ? programs_[p] : nullptr; },
                                             value, error)) {
                set_value(id, value);
            }
        } else {
            MValue descriptor;
            std::string error;
            int64_t token = request.find("token") != nullptr ? request.find("token")->as_int() : 0;
            if (!from_wire(*request.find("animation"),
                           [this](int64_t p) { return programs_.count(p) ? programs_[p] : nullptr; }, descriptor, error)) {
                Failure failure;
                failure.error = {"ValueError", error};
                report(failure, 0);
                if (token != 0) finished_tokens_.emplace_back(token, false, surface);
            } else {
                start_animation(id, descriptor, token);
            }
        }
    } else if (op == "cancel") {
        cancel_shared(request.find("id")->as_int());
    } else if (op == "bind") {
        bind(request);
    } else if (op == "release") {
        release(request);
    }
    flush();
    run_completions();
    publish();
}

void Runtime::define_program(const Value& request) {
    std::string error;
    int64_t id = request.find("id")->as_int();
    auto program = decode_program(id, *request.find("program"), error);
    if (program) programs_[id] = std::move(program);
}

void Runtime::define_shared(const Value& request) {
    int64_t id = request.find("id")->as_int();
    MValue value;
    std::string error;
    if (const Value* wire = request.find("value")) from_wire(*wire, nullptr, value, error);
    auto [entry, created] = shared_.try_emplace(id);
    entry->second.surface = surface_;
    if (created) {
        entry->second.value = value;
        unpublished_.insert(id);
    }
}

bool Runtime::closure_from(const Value* wire, std::shared_ptr<const Closure>& out, std::string& error) {
    if (wire == nullptr) {
        error = "missing closure";
        return false;
    }
    MValue value;
    if (!from_wire(*wire, [this](int64_t p) { return programs_.count(p) ? programs_[p] : nullptr; }, value, error)) return false;
    if (value.kind() != MValue::Kind::Closure) {
        error = "expected a worklet";
        return false;
    }
    out = value.closure_ptr();
    return true;
}

void Runtime::bind(const Value& request) {
    int64_t id = request.find("id")->as_int();
    const std::string& kind = request.find("kind")->as_string();
    Binding& binding = bindings_[id];
    binding.id = id;
    binding.surface = surface_;
    binding.kind = kind == "derived"    ? Kind::Derived
                   : kind == "reaction" ? Kind::Reaction
                   : kind == "frame"    ? Kind::Frame
                   : kind == "style"    ? Kind::Style
                                        : Kind::Handler;
    std::string error;
    if (!closure_from(request.find("closure"), binding.closure, error) ||
        (binding.kind == Kind::Reaction && !closure_from(request.find("react"), binding.react, error))) {
        binding.failed = true;
        Failure failure;
        failure.error = {"ValueError", error};
        report(failure, id);
        return;
    }
    binding.failed = false;
    binding.dirty = true;
    if (const Value* output = request.find("output"); output != nullptr && output->is_integer()) {
        binding.output = output->as_int();
        shared_.try_emplace(binding.output);
    }
    if (const Value* active = request.find("active"); active != nullptr) binding.active = active->as_bool();
    if (binding.kind == Kind::Frame && binding.active) core_.request_frames();
}

void Runtime::release(const Value& request) {
    if (const Value* shared = request.find("shared")) {
        for (const Value& id : shared->as_array()) {
            auto found = shared_.find(id.as_int());
            if (found == shared_.end()) continue;
            if (found->second.animation) {
                std::vector<Completion> ignored;
                found->second.animation->interrupt(ignored);
            }
            if (found->second.token != 0) finished_tokens_.emplace_back(found->second.token, false, found->second.surface);
            shared_.erase(found);
            std::lock_guard<std::mutex> lock(published_mutex_);
            published_.erase(id.as_int());
        }
    }
    if (const Value* bindings = request.find("bindings")) {
        for (const Value& id : bindings->as_array()) {
            auto found = bindings_.find(id.as_int());
            if (found == bindings_.end()) continue;
            for (int64_t dep : found->second.deps) {
                auto shared = shared_.find(dep);
                if (shared != shared_.end()) shared->second.dependents.erase(found->first);
            }
            if (found->second.kind == Kind::Style) {
                auto targets = style_targets_.find(found->first);
                if (targets != style_targets_.end()) {
                    for (int64_t tag : targets->second) {
                        auto keys = style_keys_.find(tag);
                        if (keys == style_keys_.end()) continue;
                        std::vector<std::string> orphaned;
                        for (auto& [key, writers] : keys->second) {
                            writers.erase(found->first);
                            if (writers.empty()) orphaned.push_back(key);
                        }
                        for (const std::string& key : orphaned) {
                            keys->second.erase(key);
                            restore(tag, key);
                        }
                    }
                }
                // Views may keep naming the binding until their next commit.
                style_targets_.erase(found->first);
            }
            bindings_.erase(found);
        }
    }
}

// ======================================================================
// Shared values and bindings
// ======================================================================

MValue Runtime::read_shared(int64_t id) {
    if (recording_ != nullptr) recording_->insert(id);
    auto found = shared_.find(id);
    return found == shared_.end() ? MValue() : found->second.value;
}

void Runtime::write_shared(int64_t id, const MValue& value) {
    if (is_animation(value)) start_animation(id, value, 0);
    else set_value(id, value);
}

void Runtime::cancel_shared(int64_t id) {
    auto found = shared_.find(id);
    if (found == shared_.end()) return;
    MValue before = found->second.value;
    interrupt(found->second);
    if (!equal(before, found->second.value)) mark_dependents(id);
    unpublished_.insert(id);
}

void Runtime::call_python(int64_t id, const Seq& args) {
    Array items;
    for (const MValue& item : args) items.push_back(to_wire(item));
    std::string payload = "{\"type\":\"call\",\"callback\":" + std::to_string(id) + ",\"args\":" +
                          to_json(Value::array(std::move(items))) + "}";
    emit(surface_, payload);
}

void Runtime::set_value(int64_t id, const MValue& value) {
    Shared& shared = shared_[id];
    if (shared.animation) interrupt(shared);
    if (!equal(shared.value, value) || shared.value.kind() != value.kind()) {
        shared.value = value;
        mark_dependents(id);
        unpublished_.insert(id);
    }
}

void Runtime::interrupt(Shared& shared) {
    if (!shared.animation) return;
    shared.value = shared.animation->value();
    shared.animation->interrupt(completions_);
    shared.animation.reset();
    if (shared.token != 0) finished_tokens_.emplace_back(shared.token, false, shared.surface);
    shared.token = 0;
}

void Runtime::start_animation(int64_t id, const MValue& descriptor, int64_t token) {
    Shared& shared = shared_[id];
    double velocity = shared.animation ? shared.animation->velocity() : 0;
    interrupt(shared);
    std::string error;
    std::unique_ptr<Animation> animation = make_animation(descriptor, error);
    if (!animation) {
        Failure failure;
        failure.error = {"ValueError", error};
        report(failure, 0);
        if (token != 0) finished_tokens_.emplace_back(token, false, surface_);
        return;
    }
    if (surface_ != 0) shared.surface = surface_;
    animation->start(shared.value, velocity, reduce_motion_);
    shared.animation = std::move(animation);
    shared.token = token;
    core_.request_frames();
}

void Runtime::mark_dependents(int64_t id) {
    auto found = shared_.find(id);
    if (found == shared_.end()) return;
    for (int64_t binding : found->second.dependents) {
        auto entry = bindings_.find(binding);
        if (entry != bindings_.end()) entry->second.dirty = true;
    }
}

bool Runtime::run(Binding& binding, const std::shared_ptr<const Closure>& closure, const Seq& args, MValue& result,
                  bool record) {
    if (!closure) return false;
    std::set<int64_t> deps;
    std::set<int64_t>* saved = recording_;
    int64_t saved_surface = surface_;
    if (binding.surface != 0) surface_ = binding.surface;
    recording_ = record ? &deps : nullptr;
    VM vm(*this);
    Failure failure;
    Seq arguments = args;
    arguments.resize(static_cast<size_t>(closure->program->params));
    bool ok = vm.run(*closure, arguments, result, failure);
    recording_ = saved;
    if (!ok) {
        binding.failed = true;
        report(failure, binding.id);
        surface_ = saved_surface;
        return false;
    }
    surface_ = saved_surface;
    if (record) track(binding, std::move(deps));
    return true;
}

void Runtime::track(Binding& binding, std::set<int64_t> deps) {
    for (int64_t old : binding.deps) {
        if (deps.count(old) != 0) continue;
        auto found = shared_.find(old);
        if (found != shared_.end()) found->second.dependents.erase(binding.id);
    }
    for (int64_t id : deps) shared_[id].dependents.insert(binding.id);
    binding.deps = std::move(deps);
}

void Runtime::run_binding(Binding& binding) {
    MValue result;
    switch (binding.kind) {
        case Kind::Derived:
            if (run(binding, binding.closure, {}, result, true)) write_shared(binding.output, result);
            break;
        case Kind::Reaction:
            if (run(binding, binding.closure, {}, result, true)) {
                if (!binding.has_previous || !equal(result, binding.previous)) {
                    MValue previous = binding.has_previous ? binding.previous : MValue();
                    binding.previous = result;
                    binding.has_previous = true;
                    MValue ignored;
                    run(binding, binding.react, {result, previous}, ignored, false);
                }
            }
            break;
        case Kind::Style:
            if (run(binding, binding.closure, {}, result, true)) apply_style(binding, result);
            break;
        default: break;
    }
}

void Runtime::flush() {
    if (flushing_) return;
    flushing_ = true;
    for (int round = 0; round < 32; ++round) {
        bool ran = false;
        for (Kind kind : {Kind::Derived, Kind::Reaction, Kind::Style}) {
            for (auto& [id, binding] : bindings_) {
                if (binding.kind != kind || !binding.dirty || binding.failed) continue;
                binding.dirty = false;
                run_binding(binding);
                ran = true;
            }
        }
        if (!ran) break;
    }
    flushing_ = false;
}

void Runtime::run_completions() {
    for (int round = 0; round < 8 && (!completions_.empty() || !finished_tokens_.empty()); ++round) {
        std::vector<Completion> pending;
        pending.swap(completions_);
        for (const Completion& completion : pending) {
            Binding scratch;
            MValue ignored;
            run(scratch, completion.callback, {MValue::boolean(completion.finished)}, ignored, false);
        }
        std::vector<std::tuple<int64_t, bool, int64_t>> tokens;
        tokens.swap(finished_tokens_);
        for (const auto& [token, finished, surface] : tokens) {
            emit(surface, "{\"type\":\"finished\",\"token\":" + std::to_string(token) +
                              ",\"finished\":" + (finished ? "true" : "false") + "}");
        }
        flush();
    }
}

void Runtime::report(const Failure& failure, int64_t binding) {
    std::string payload = "{\"type\":\"error\",\"binding\":" + std::to_string(binding) + ",\"error_type\":";
    write_json_string(failure.error.type, payload);
    payload += ",\"message\":";
    write_json_string(failure.error.message, payload);
    payload += ",\"name\":";
    write_json_string(failure.name, payload);
    payload += ",\"file\":";
    write_json_string(failure.file, payload);
    payload += ",\"line\":" + std::to_string(failure.line) + "}";
    emit(surface_, payload);
}

void Runtime::publish() {
    if (unpublished_.empty()) return;
    std::unique_lock<std::mutex> lock(published_mutex_, std::try_to_lock);
    if (!lock.owns_lock()) return;  // a reader holds it; publish after the next frame or event
    for (int64_t id : unpublished_) {
        auto found = shared_.find(id);
        if (found != shared_.end()) published_[id] = to_json(to_wire(found->second.value));
    }
    unpublished_.clear();
}

std::string Runtime::published(int64_t id) {
    std::lock_guard<std::mutex> lock(published_mutex_);
    auto found = published_.find(id);
    return found == published_.end() ? std::string("null") : found->second;
}

// ======================================================================
// Animated styles
// ======================================================================

void Runtime::write_prop(int64_t tag, const std::string& key, const Value& value) {
    auto& applied = applied_[tag];
    auto found = applied.find(key);
    if (found != applied.end() && found->second == value && found->second.kind() == value.kind()) return;
    applied[key] = value;
    ByteWriter out;
    out.u8(0);
    out.i64(tag);
    out.str(key);
    out.value(value);
    writes_.insert(writes_.end(), out.bytes().begin(), out.bytes().end());
    ++write_count_;
}

void Runtime::write_frame(int64_t tag, const std::array<double, 4>& frame) {
    frames_[tag] = frame;
    ByteWriter out;
    out.u8(1);
    out.i64(tag);
    for (double part : frame) out.f64(std::isfinite(part) ? part : 0);
    writes_.insert(writes_.end(), out.bytes().begin(), out.bytes().end());
    ++write_count_;
}

Value Runtime::static_value(int64_t surface, int64_t tag, const std::string& key) {
    const Value* value = lookup_ ? lookup_(surface, tag, key) : nullptr;
    return value != nullptr ? *value : Value();
}

void Runtime::restore(int64_t tag, const std::string& key) {
    int64_t surface = view_surface_.count(tag) ? view_surface_[tag] : 0;
    bool layout = false;
    animatable_style(key, layout);
    if (layout) {
        auto found = layout_values_.find(tag);
        if (found != layout_values_.end() && found->second.erase(key) != 0 && layout_post_) {
            layout_post_(surface, tag, key, Value());
        }
        return;
    }
    auto values = motion_values_.find(tag);
    if (values != motion_values_.end()) values->second.erase(key);
    write_prop(tag, key, static_value(surface, tag, key));
}

void Runtime::apply_style(Binding& binding, const MValue& style) {
    auto targets = style_targets_.find(binding.id);
    if (targets == style_targets_.end()) return;
    if (!style.is_map()) {
        binding.failed = true;
        Failure failure;
        failure.error = {"TypeError", std::string("an animated style must return a dict, not '") + style.type_name() + "'"};
        failure.name = binding.closure ? binding.closure->program->name : "";
        failure.file = binding.closure ? binding.closure->program->file : "";
        failure.line = binding.closure ? binding.closure->program->line : 0;
        report(failure, binding.id);
        return;
    }
    for (const auto& [key, value] : style.as_map()) {
        bool layout = false;
        if (!animatable_style(key, layout)) {
            binding.failed = true;
            Failure failure;
            failure.error = {"ValueError", "an animated style can't write " + key};
            failure.name = binding.closure->program->name;
            failure.file = binding.closure->program->file;
            failure.line = binding.closure->program->line;
            report(failure, binding.id);
            return;
        }
    }
    std::vector<int64_t> tags(targets->second.begin(), targets->second.end());
    for (int64_t tag : tags) apply_style_to(binding.id, tag, style);
}

void Runtime::apply_style_to(int64_t binding, int64_t tag, const MValue& style) {
    int64_t surface = view_surface_.count(tag) ? view_surface_[tag] : 0;
    auto& keys = style_keys_[tag];
    std::set<std::string> written;
    for (const auto& [key, value] : style.as_map()) {
        bool layout = false;
        animatable_style(key, layout);
        Value wire = to_wire(value);
        written.insert(key);
        keys[key].insert(binding);
        if (layout) {
            auto& posted = layout_values_[tag];
            auto found = posted.find(key);
            if (found == posted.end() || found->second != wire) {
                posted[key] = wire;
                if (layout_post_) layout_post_(surface, tag, key, wire);
            }
        } else {
            motion_values_[tag][key] = wire;
            write_prop(tag, key, wire);
        }
    }
    std::vector<std::string> orphaned;
    for (auto& [key, writers] : keys) {
        if (written.count(key) != 0 || writers.count(binding) == 0) continue;
        writers.erase(binding);
        if (writers.empty()) orphaned.push_back(key);
    }
    for (const std::string& key : orphaned) {
        keys.erase(key);
        restore(tag, key);
    }
}

void Runtime::update_targets(int64_t surface, int64_t tag, const Value* motion) {
    view_surface_[tag] = surface;
    std::vector<int64_t> wanted;
    if (motion != nullptr) {
        if (const Value* styles = motion->find("style"); styles != nullptr && styles->is_array()) {
            for (const Value& id : styles->as_array()) {
                if (id.is_integer()) wanted.push_back(id.as_int());
            }
        }
    }
    std::vector<int64_t>& current = view_styles_[tag];
    for (int64_t binding : current) {
        if (std::find(wanted.begin(), wanted.end(), binding) != wanted.end()) continue;
        style_targets_[binding].erase(tag);
        auto keys = style_keys_.find(tag);
        if (keys == style_keys_.end()) continue;
        std::vector<std::string> orphaned;
        for (auto& [key, writers] : keys->second) {
            writers.erase(binding);
            if (writers.empty()) orphaned.push_back(key);
        }
        for (const std::string& key : orphaned) {
            keys->second.erase(key);
            restore(tag, key);
        }
    }
    for (int64_t binding : wanted) {
        if (std::find(current.begin(), current.end(), binding) != current.end()) continue;
        style_targets_[binding].insert(tag);
        auto found = bindings_.find(binding);
        if (found != bindings_.end() && !found->second.failed) found->second.dirty = true;
    }
    current = wanted;
    if (current.empty()) view_styles_.erase(tag);
}

void Runtime::view_mounted(int64_t surface, int64_t tag, const Object& props) {
    view_surface_[tag] = surface;
    if (const Value* motion = find_member(props, "_pn_motion")) {
        update_targets(surface, tag, motion);
        flush();
        publish();
    }
}

void Runtime::view_updated(int64_t surface, int64_t tag, const Object& props, const Object& changed,
                           const std::vector<std::string>& removed) {
    bool motion_changed = find_member(changed, "_pn_motion") != nullptr ||
                          std::find(removed.begin(), removed.end(), "_pn_motion") != removed.end();
    if (motion_changed) update_targets(surface, tag, find_member(props, "_pn_motion"));
    // A commit that sets a key motion controls applied the static value;
    // put the animated one back in the same UI-thread turn.
    auto values = motion_values_.find(tag);
    if (values != motion_values_.end()) {
        for (const auto& [key, value] : changed) {
            auto found = values->second.find(key);
            if (found == values->second.end()) continue;
            applied_[tag].erase(key);
            write_prop(tag, key, found->second);
        }
    }
    if (motion_changed) {
        flush();
        publish();
    }
}

void Runtime::view_deleted(int64_t tag) {
    auto styles = view_styles_.find(tag);
    if (styles != view_styles_.end()) {
        for (int64_t binding : styles->second) style_targets_[binding].erase(tag);
        view_styles_.erase(styles);
    }
    style_keys_.erase(tag);
    motion_values_.erase(tag);
    applied_.erase(tag);
    layout_values_.erase(tag);
    entering_.erase(tag);
    layout_.erase(tag);
    frames_.erase(tag);
    view_surface_.erase(tag);
}

void Runtime::surface_reset(int64_t surface) {
    std::vector<int64_t> tags;
    for (const auto& [tag, owner] : view_surface_) {
        if (owner == surface) tags.push_back(tag);
    }
    for (int64_t tag : tags) view_deleted(tag);
    for (auto it = exiting_.begin(); it != exiting_.end();) {
        it = it->second.surface == surface ? exiting_.erase(it) : std::next(it);
    }
}

bool Runtime::event(int64_t surface, int64_t tag, int64_t binding_id, const Value& arguments) {
    surface_ = surface;
    last_surface_ = surface;
    auto found = bindings_.find(binding_id);
    if (found == bindings_.end() || found->second.failed) return false;
    view_surface_.try_emplace(tag, surface);
    Seq args;
    if (arguments.is_array()) {
        for (const Value& item : arguments.as_array()) {
            MValue converted;
            std::string error;
            if (from_wire(item, nullptr, converted, error)) args.push_back(std::move(converted));
        }
    }
    MValue ignored;
    run(found->second, found->second.closure, args, ignored, false);
    flush();
    run_completions();
    publish();
    return true;
}

// ======================================================================
// Layout animations and exits
// ======================================================================

std::unique_ptr<Animation> Runtime::channel_animation(const Value& spec, const MValue& to, std::string& error) {
    Map members = {{"__animation__", MValue::boolean(true)}, {"to", to}};
    const Value* reduce = spec.find("reduce_motion");
    members.emplace_back("reduce_motion", MValue::string(reduce != nullptr && reduce->is_string() ? reduce->as_string() : "system"));
    const Value* spring = spec.find("spring");
    if (spring != nullptr && spring->is_object()) {
        members.emplace_back("type", MValue::string("spring"));
        for (const auto& [key, value] : spring->as_object()) {
            MValue converted;
            if (from_wire(value, nullptr, converted, error)) members.emplace_back(key, converted);
        }
    } else {
        members.emplace_back("type", MValue::string("timing"));
        members.emplace_back("duration", MValue::number(number(spec.find("duration"), 300)));
        MValue easing;
        if (const Value* wire = spec.find("easing")) from_wire(*wire, nullptr, easing, error);
        members.emplace_back("easing", easing);
    }
    MValue descriptor = MValue::map(std::move(members));
    double delay = number(spec.find("delay"), 0);
    if (delay > 0) {
        descriptor = MValue::map({{"__animation__", MValue::boolean(true)},
                                  {"type", MValue::string("delay")},
                                  {"delay", MValue::number(delay)},
                                  {"animation", descriptor}});
    }
    return make_animation(descriptor, error);
}

bool Runtime::build(ViewAnimation& view, const Value& spec, const std::array<double, 4>& frame, double window_width,
                    double window_height, bool entering_side, std::string& error) {
    const Value* type_value = spec.find("type");
    std::string type = type_value != nullptr && type_value->is_string() ? type_value->as_string() : std::string();
    auto add = [&](const std::string& key, double from, double to) {
        Channel channel;
        channel.key = key;
        channel.animation = channel_animation(spec, MValue::number(to), error);
        if (!channel.animation) return false;
        channel.animation->start(MValue::number(from), 0, reduce_motion_);
        channel.value = channel.animation->value();
        view.channels.push_back(std::move(channel));
        return true;
    };
    double opacity = 1;
    {
        auto values = motion_values_.find(view.tag);
        const Value* motion = values != motion_values_.end() && values->second.count("opacity") ? &values->second["opacity"] : nullptr;
        Value fallback = static_value(view.surface, view.tag, "opacity");
        opacity = number(motion != nullptr ? motion : &fallback, 1);
    }
    const Value* edge_value = spec.find("edge");
    std::string edge = edge_value != nullptr && edge_value->is_string() ? edge_value->as_string() : std::string("right");
    double offset_x = edge == "left" ? -window_width : edge == "right" ? window_width : 0;
    double offset_y = edge == "top" ? -window_height : edge == "bottom" ? window_height : 0;
    const char* axis = offset_x != 0 ? "translate_x" : "translate_y";
    double distance = offset_x != 0 ? offset_x : offset_y;
    if (type == "fade_in") return add("opacity", 0, opacity);
    if (type == "fade_out") return add("opacity", opacity, 0);
    if (type == "slide_in") return add(axis, distance, 0);
    if (type == "slide_out") return add(axis, 0, distance);
    if (type == "zoom_in") return add("scale", 0, 1);
    if (type == "zoom_out") return add("scale", 1, 0);
    if (type == "linear") {
        view.frame = true;
        for (size_t i = 0; i < 4; ++i) {
            if (!add(kFrameKeys[i], view.from[i], view.to[i])) return false;
        }
        return true;
    }
    if (type == "fading") {
        view.frame = true;
        view.fading = true;
        return add("progress", 0, 1);
    }
    if (type == "keyframes") {
        const Value* frames = spec.find("frames");
        if (frames == nullptr || !frames->is_array() || frames->as_array().size() < 2) {
            error = "Keyframes needs at least two keyframes";
            return false;
        }
        for (const Value& raw : frames->as_array()) {
            if (!raw.is_array() || raw.as_array().size() < 2) continue;
            MValue style;
            if (!from_wire(raw.as_array()[1], nullptr, style, error) || !style.is_map()) return false;
            view.keyframes.emplace_back(raw.as_array()[0].as_double(), style.as_map());
            MValue easing;
            if (raw.as_array().size() > 2) from_wire(raw.as_array()[2], nullptr, easing, error);
            auto curve = easing_function(easing.is_none() ? MValue::string("linear") : easing);
            view.keyframe_easings.push_back(curve ? curve : [](double t) { return t; });
        }
        std::sort(view.keyframes.begin(), view.keyframes.end(),
                  [](const auto& a, const auto& b) { return a.first < b.first; });
        view.keyframed = true;
        Value linear = Value::object({{"duration", Value::number(number(spec.find("duration"), 300))},
                                      {"delay", Value::number(number(spec.find("delay"), 0))},
                                      {"easing", Value::string("linear")},
                                      {"reduce_motion", spec.find("reduce_motion") ? *spec.find("reduce_motion") : Value()}});
        Channel channel;
        channel.key = "progress";
        channel.animation = channel_animation(linear, MValue::number(1), error);
        if (!channel.animation) return false;
        channel.animation->start(MValue::number(0), 0, reduce_motion_);
        channel.value = channel.animation->value();
        view.channels.push_back(std::move(channel));
        return true;
    }
    if (type == "custom") {
        Map values = {{"window_width", MValue::number(window_width)}, {"window_height", MValue::number(window_height)}};
        const char* prefix = entering_side ? "target_" : "current_";
        const char* names[] = {"x", "y", "width", "height"};
        for (size_t i = 0; i < 4; ++i) values.emplace_back(std::string(prefix) + names[i], MValue::number(frame[i]));
        if (view.type == ViewAnimation::Type::Layout) {
            for (size_t i = 0; i < 4; ++i) values.emplace_back(std::string("current_") + names[i], MValue::number(view.from[i]));
            for (size_t i = 0; i < 4; ++i) values.emplace_back(std::string("target_") + names[i], MValue::number(view.to[i]));
        }
        return build_custom(view, spec, values, error);
    }
    error = "unknown layout animation " + type;
    return false;
}

bool Runtime::build_custom(ViewAnimation& view, const Value& spec, const Map& values, std::string& error) {
    std::shared_ptr<const Closure> closure;
    if (!closure_from(spec.find("worklet"), closure, error)) return false;
    Binding scratch;
    scratch.id = 0;
    MValue result;
    if (!run(scratch, closure, {MValue::map(values)}, result, false)) {
        error = "the custom layout animation failed";
        return false;
    }
    const MValue* initial = result.find("initial");
    const MValue* animate = result.find("animate");
    if (animate == nullptr || !animate->is_map()) {
        error = "a custom layout animation returns {'initial': {...}, 'animate': {...}}";
        return false;
    }
    auto start_value = [&](const std::string& key) -> MValue {
        if (initial != nullptr) {
            if (const MValue* value = initial->find(key)) return *value;
        }
        static const char* frame_names[] = {"x", "y", "width", "height"};
        for (size_t i = 0; i < 4; ++i) {
            if (key == frame_names[i]) return MValue::number(view.type == ViewAnimation::Type::Layout ? view.from[i] : view.to[i]);
        }
        MValue converted;
        std::string ignored;
        from_wire(static_value(view.surface, view.tag, key), nullptr, converted, ignored);
        if (converted.is_none() && (key == "opacity" || key.rfind("scale", 0) == 0)) return MValue::number(1);
        if (converted.is_none()) return MValue::number(0);
        return converted;
    };
    for (const auto& [raw_key, target] : animate->as_map()) {
        std::string key = raw_key;
        static const char* frame_names[] = {"x", "y", "width", "height"};
        for (size_t i = 0; i < 4; ++i) {
            if (raw_key == frame_names[i]) {
                key = kFrameKeys[i];
                view.frame = true;
            }
        }
        Channel channel;
        channel.key = key;
        MValue descriptor = is_animation(target)
                                ? target
                                : MValue::map({{"__animation__", MValue::boolean(true)},
                                               {"type", MValue::string("timing")},
                                               {"to", target},
                                               {"duration", MValue::integer(0)}});
        channel.animation = make_animation(descriptor, error);
        if (!channel.animation) return false;
        channel.animation->start(start_value(raw_key), 0, reduce_motion_);
        channel.value = channel.animation->value();
        view.channels.push_back(std::move(channel));
    }
    return true;
}

void Runtime::write_view(ViewAnimation& view) {
    std::map<std::string, Value> style;
    std::vector<std::pair<std::string, double>> transform;
    std::array<double, 4> frame = view.type == ViewAnimation::Type::Layout ? view.to : std::array<double, 4>{};
    bool frame_written = false;
    double progress = 0;
    for (Channel& channel : view.channels) {
        const std::string& key = channel.key;
        bool is_frame = false;
        for (size_t i = 0; i < 4; ++i) {
            if (key == kFrameKeys[i]) {
                frame[i] = channel.value.as_double();
                frame_written = true;
                is_frame = true;
            }
        }
        if (is_frame) continue;
        if (key == "progress") {
            progress = channel.value.as_double();
            continue;
        }
        if (is_transform_channel(key)) {
            transform.emplace_back(key, channel.value.as_double());
            continue;
        }
        style[key] = to_wire(channel.value);
    }
    if (view.fading) {
        frame = progress < 0.5 ? view.from : view.to;
        frame_written = true;
        Value base = static_value(view.surface, view.tag, "opacity");
        style["opacity"] = Value::number(number(&base, 1) * std::fabs(1 - 2 * progress));
    }
    if (view.keyframed && !view.keyframes.empty()) {
        // Each key interpolates between the keyframes that set it.
        std::set<std::string> keys;
        for (const auto& [at, values] : view.keyframes) {
            for (const auto& [key, value] : values) keys.insert(key);
        }
        for (const std::string& key : keys) {
            std::vector<std::pair<double, MValue>> stops;
            std::vector<std::function<double(double)>> easings;
            for (size_t i = 0; i < view.keyframes.size(); ++i) {
                for (const auto& [name, value] : view.keyframes[i].second) {
                    if (name == key) {
                        stops.emplace_back(view.keyframes[i].first, value);
                        easings.push_back(view.keyframe_easings[i]);
                    }
                }
            }
            if (stops.empty()) continue;
            MValue value = stops.front().second;
            if (progress >= stops.back().first) {
                value = stops.back().second;
            } else {
                for (size_t i = 0; i + 1 < stops.size(); ++i) {
                    if (progress >= stops[i].first && progress <= stops[i + 1].first) {
                        double span = stops[i + 1].first - stops[i].first;
                        double t = span <= 0 ? 1 : (progress - stops[i].first) / span;
                        value = lerp_value(stops[i].second, stops[i + 1].second, easings[i + 1](t));
                        break;
                    }
                }
            }
            style[key] = to_wire(value);
        }
    }
    if (!transform.empty()) {
        auto values = motion_values_.find(view.tag);
        Value base = values != motion_values_.end() && values->second.count("transform")
                         ? values->second["transform"]
                         : static_value(view.surface, view.tag, "transform");
        Array entries = as_transform_list(base);
        for (const char* name : kTransformChannels) {
            for (const auto& [key, value] : transform) {
                if (key == name) entries.push_back(Value::object({{key, Value::number(value)}}));
            }
        }
        style["transform"] = Value::array(std::move(entries));
    }
    for (const auto& [key, value] : style) {
        bool layout = false;
        if (!animatable_style(key, layout)) continue;
        if (layout) {
            int64_t surface = view.surface;
            if (layout_post_) layout_post_(surface, view.tag, key, value);
        } else {
            write_prop(view.tag, key, value);
        }
        view.written.insert(key);
    }
    if (frame_written) write_frame(view.tag, frame);
}

void Runtime::finish_view(ViewAnimation& view, bool completed) {
    (void)completed;
    if (view.type == ViewAnimation::Type::Exiting) {
        remove(view.surface, view.subtree);
        return;
    }
    for (const std::string& key : view.written) {
        bool layout = false;
        animatable_style(key, layout);
        if (layout) {
            if (layout_post_) layout_post_(view.surface, view.tag, key, Value());
            continue;
        }
        auto values = motion_values_.find(view.tag);
        if (values != motion_values_.end() && values->second.count(key)) write_prop(view.tag, key, values->second[key]);
        else write_prop(view.tag, key, static_value(view.surface, view.tag, key));
    }
    if (view.frame) write_frame(view.tag, view.to);
}

void Runtime::remove(int64_t surface, const std::vector<int64_t>& subtree) {
    if (subtree.empty()) return;
    ByteWriter out;
    out.u8(2);
    out.u32(static_cast<uint32_t>(subtree.size()));
    for (int64_t tag : subtree) out.i64(tag);
    writes_.insert(writes_.end(), out.bytes().begin(), out.bytes().end());
    ++write_count_;
    for (int64_t tag : subtree) {
        view_deleted(tag);
        exiting_.erase(tag);
    }
    if (removed_) removed_(surface, subtree);
}

void Runtime::start_entering(int64_t surface, const Value& record) {
    int64_t tag = record.find("tag")->as_int();
    ViewAnimation view;
    view.type = ViewAnimation::Type::Entering;
    view.surface = surface;
    view.tag = tag;
    std::array<double, 4> frame = frame_of(record.find("frame"));
    view.to = frame;
    const Value* window = record.find("window");
    double width = window != nullptr && window->is_array() && window->as_array().size() == 2 ? window->as_array()[0].as_double() : 0;
    double height = window != nullptr && window->is_array() && window->as_array().size() == 2 ? window->as_array()[1].as_double() : 0;
    std::string error;
    if (!build(view, *record.find("spec"), frame, width, height, true, error)) {
        Failure failure;
        failure.error = {"ValueError", error};
        report(failure, 0);
        return;
    }
    write_view(view);
    entering_[tag] = std::move(view);
    core_.request_frames();
}

void Runtime::start_layout(int64_t surface, const Value& record) {
    int64_t tag = record.find("tag")->as_int();
    ViewAnimation view;
    view.type = ViewAnimation::Type::Layout;
    view.surface = surface;
    view.tag = tag;
    view.from = frame_of(record.find("from"));
    view.to = frame_of(record.find("to"));
    // Retarget a running transition from where the view is now.
    auto running_frame = frames_.find(tag);
    if (layout_.count(tag) != 0 && running_frame != frames_.end()) view.from = running_frame->second;
    const Value* window = record.find("window");
    double width = window != nullptr && window->is_array() && window->as_array().size() == 2 ? window->as_array()[0].as_double() : 0;
    double height = window != nullptr && window->is_array() && window->as_array().size() == 2 ? window->as_array()[1].as_double() : 0;
    std::string error;
    if (!build(view, *record.find("spec"), view.to, width, height, true, error)) {
        Failure failure;
        failure.error = {"ValueError", error};
        report(failure, 0);
        return;
    }
    write_view(view);
    layout_[tag] = std::move(view);
    core_.request_frames();
}

void Runtime::start_exit(int64_t surface, const Value& record) {
    int64_t tag = record.find("tag")->as_int();
    ViewAnimation view;
    view.type = ViewAnimation::Type::Exiting;
    view.surface = surface;
    view.tag = tag;
    for (const Value& item : record.find("subtree") ? record.find("subtree")->as_array() : Array()) view.subtree.push_back(item.as_int());
    if (view.subtree.empty()) view.subtree.push_back(tag);
    // Nothing else animates or styles a leaving subtree.
    for (int64_t member : view.subtree) {
        entering_.erase(member);
        layout_.erase(member);
        auto styles = view_styles_.find(member);
        if (styles != view_styles_.end()) {
            for (int64_t binding : styles->second) style_targets_[binding].erase(member);
            view_styles_.erase(styles);
        }
        style_keys_.erase(member);
    }
    view.host_owned = record.find("owner") != nullptr && record.find("owner")->as_int() == 1;
    if (view.host_owned) {
        // The platform may finish (or skip) its transition while applying the
        // transaction, before this record arrives at `mount_finished`.
        if (finished_early_.erase(tag) != 0) {
            remove(surface, view.subtree);
            return;
        }
        exiting_[tag] = std::move(view);
        return;
    }
    std::array<double, 4> frame = frame_of(record.find("frame"));
    view.to = frame;
    const Value* window = record.find("window");
    double width = window != nullptr && window->is_array() && window->as_array().size() == 2 ? window->as_array()[0].as_double() : 0;
    double height = window != nullptr && window->is_array() && window->as_array().size() == 2 ? window->as_array()[1].as_double() : 0;
    std::string error;
    const Value* spec = record.find("spec");
    if (spec == nullptr || !build(view, *spec, frame, width, height, false, error)) {
        if (!error.empty()) {
            Failure failure;
            failure.error = {"ValueError", error};
            report(failure, 0);
        }
        remove(surface, view.subtree);
        return;
    }
    write_view(view);
    exiting_[tag] = std::move(view);
    core_.request_frames();
}

void Runtime::records(int64_t surface, const std::vector<Value>& records) {
    surface_ = surface;
    last_surface_ = surface;
    for (const Value& record : records) {
        const Value* kind = record.find("kind");
        if (kind == nullptr || !kind->is_string() || record.find("tag") == nullptr) continue;
        if (kind->as_string() == "entering") start_entering(surface, record);
        else if (kind->as_string() == "layout") start_layout(surface, record);
        else if (kind->as_string() == "exit") start_exit(surface, record);
    }
    run_completions();
    publish();
}

void Runtime::exit_finished(int64_t surface, int64_t tag) {
    auto found = exiting_.find(tag);
    if (found == exiting_.end()) {
        finished_early_.insert(tag);
        return;
    }
    if (!found->second.host_owned) return;
    std::vector<int64_t> subtree = found->second.subtree;
    remove(surface, subtree);
}

// ======================================================================
// Frames
// ======================================================================

bool Runtime::frame(double timestamp_ms) {
    // The first frame after the runtime was idle is where animations start, so
    // it draws their initial values instead of skipping a frame's worth.
    double dt = previous_time_ < 0 ? 0.0 : std::min(0.064, std::max(0.0, (timestamp_ms - previous_time_) / 1000.0));
    previous_time_ = timestamp_ms;
    for (auto& [id, shared] : shared_) {
        if (!shared.animation) continue;
        bool done = shared.animation->step(dt, completions_);
        MValue value = shared.animation->value();
        if (!equal(value, shared.value) || value.kind() != shared.value.kind()) {
            shared.value = value;
            mark_dependents(id);
            unpublished_.insert(id);
        }
        if (done) {
            shared.animation.reset();
            if (shared.token != 0) finished_tokens_.emplace_back(shared.token, true, shared.surface);
            shared.token = 0;
        }
    }
    MValue info = MValue::map({{"timestamp_ms", MValue::number(timestamp_ms)}, {"delta_ms", MValue::number(dt * 1000.0)}});
    for (auto& [id, binding] : bindings_) {
        if (binding.kind != Kind::Frame || !binding.active || binding.failed) continue;
        MValue ignored;
        run(binding, binding.closure, {info}, ignored, false);
    }
    flush();
    for (auto* group : {&entering_, &layout_, &exiting_}) {
        std::vector<int64_t> finished;
        for (auto& [tag, view] : *group) {
            if (view.host_owned) continue;
            bool done = true;
            for (Channel& channel : view.channels) {
                bool channel_done = channel.animation->step(dt, completions_);
                channel.value = channel.animation->value();
                done = done && channel_done;
            }
            write_view(view);
            if (done) finished.push_back(tag);
        }
        for (int64_t tag : finished) {
            auto found = group->find(tag);
            if (found == group->end()) continue;
            ViewAnimation view = std::move(found->second);
            group->erase(found);
            finish_view(view, true);
        }
    }
    run_completions();
    publish();
    bool active = running();
    if (!active) previous_time_ = -1;
    return active;
}

bool Runtime::running() const {
    for (const auto& [id, shared] : shared_) {
        if (shared.animation) return true;
    }
    for (const auto& [id, binding] : bindings_) {
        if (binding.kind == Kind::Frame && binding.active && !binding.failed) return true;
    }
    if (!entering_.empty() || !layout_.empty()) return true;
    for (const auto& [tag, view] : exiting_) {
        if (!view.host_owned) return true;
    }
    return false;
}

bool Runtime::take_writes(std::vector<uint8_t>& out) {
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

void Runtime::reset() {
    programs_.clear();
    shared_.clear();
    bindings_.clear();
    completions_.clear();
    finished_tokens_.clear();
    view_surface_.clear();
    view_styles_.clear();
    style_targets_.clear();
    motion_values_.clear();
    applied_.clear();
    layout_values_.clear();
    style_keys_.clear();
    entering_.clear();
    layout_.clear();
    exiting_.clear();
    frames_.clear();
    finished_early_.clear();
    writes_.clear();
    write_count_ = 0;
    previous_time_ = -1;
    unpublished_.clear();
    std::lock_guard<std::mutex> lock(published_mutex_);
    published_.clear();
}

// ======================================================================
// Standalone evaluation
// ======================================================================

namespace {

class Scratch final : public Host {
public:
    std::unordered_map<int64_t, MValue> shared;
    std::vector<std::pair<int64_t, MValue>> writes;
    std::vector<std::pair<int64_t, Seq>> calls;

    MValue read_shared(int64_t id) override {
        auto found = shared.find(id);
        return found == shared.end() ? MValue() : found->second;
    }
    void write_shared(int64_t id, const MValue& value) override {
        shared[id] = value;
        writes.emplace_back(id, value);
    }
    void cancel_shared(int64_t id) override { writes.emplace_back(id, MValue::string("__cancel__")); }
    void call_python(int64_t id, const Seq& args) override { calls.emplace_back(id, args); }
};

}  // namespace

std::string evaluate(const char* text) {
    Value request;
    std::string error;
    auto fail = [](const std::string& type, const std::string& message, int line) {
        std::string out = "{\"ok\":false,\"error_type\":";
        write_json_string(type, out);
        out += ",\"message\":";
        write_json_string(message, out);
        out += ",\"line\":" + std::to_string(line) + "}";
        return out;
    };
    if (text == nullptr || !parse_json(text, request, error)) return fail("ValueError", "invalid JSON: " + error, 0);
    std::unordered_map<int64_t, std::shared_ptr<const Program>> programs;
    if (const Value* table = request.find("programs"); table != nullptr && table->is_object()) {
        for (const auto& [key, document] : table->as_object()) {
            int64_t id = std::strtoll(key.c_str(), nullptr, 10);
            auto program = decode_program(id, document, error);
            if (!program) return fail("ValueError", error, 0);
            programs[id] = program;
        }
    }
    ProgramLookup lookup = [&](int64_t id) { return programs.count(id) ? programs[id] : nullptr; };
    MValue closure;
    const Value* wire = request.find("closure");
    if (wire == nullptr || !from_wire(*wire, lookup, closure, error) || closure.kind() != MValue::Kind::Closure) {
        return fail("ValueError", error.empty() ? "expected a closure" : error, 0);
    }
    Scratch host;
    if (const Value* shared = request.find("shared"); shared != nullptr && shared->is_object()) {
        for (const auto& [key, value] : shared->as_object()) {
            MValue converted;
            if (!from_wire(value, lookup, converted, error)) return fail("ValueError", error, 0);
            host.shared[std::strtoll(key.c_str(), nullptr, 10)] = converted;
        }
    }
    Seq args;
    if (const Value* raw = request.find("args"); raw != nullptr && raw->is_array()) {
        for (const Value& item : raw->as_array()) {
            MValue converted;
            if (!from_wire(item, lookup, converted, error)) return fail("ValueError", error, 0);
            args.push_back(std::move(converted));
        }
    }
    VM vm(host);
    MValue result;
    Failure failure;
    if (!vm.run(closure.as_closure(), args, result, failure)) return fail(failure.error.type, failure.error.message, failure.line);
    Object writes;
    for (const auto& [id, value] : host.writes) writes.emplace_back(std::to_string(id), to_wire(value));
    Array calls;
    for (const auto& [id, items] : host.calls) {
        Array converted;
        for (const MValue& item : items) converted.push_back(to_wire(item));
        calls.push_back(Value::array({Value::integer(id), Value::array(std::move(converted))}));
    }
    return "{\"ok\":true,\"value\":" + to_json(to_wire(result)) + ",\"writes\":" + to_json(Value::object(std::move(writes))) +
           ",\"calls\":" + to_json(Value::array(std::move(calls))) + "}";
}

}  // namespace pn::motion
