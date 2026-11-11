#include "mount.h"

#include "core.h"

#include <map>

namespace pn {

void MountState::begin(const Transaction& transaction) {
    for (const MirrorChange& change : transaction.mirror) {
        switch (change.kind) {
            case MirrorChange::Kind::Reset:
                motion_.surface_reset(surface_);
                views_.clear();
                lists_.clear();
                exiting_.clear();
                screens_.clear();
                break;
            case MirrorChange::Kind::Create: {
                View& view = views_[change.tag];
                view.component = change.component;
                view.props = change.props;
                view.gestures.reset();
                rebuild_gestures(change.tag, view);
                if (change.list) lists_[change.tag].pending.push_back(change.list);
                if (change.screen != 0) screens_[change.tag] = change.screen;
                motion_.view_mounted(surface_, change.tag, view.props);
                break;
            }
            case MirrorChange::Kind::Update: {
                auto found = views_.find(change.tag);
                if (found == views_.end()) break;
                for (const auto& [key, value] : change.props) set_member(found->second.props, key, value);
                for (const std::string& key : change.removed) remove_member(found->second.props, key);
                if (find_member(change.props, "gestures") != nullptr) rebuild_gestures(change.tag, found->second);
                if (change.list) lists_[change.tag].pending.push_back(change.list);
                if (change.screen != 0) screens_[change.tag] = change.screen;
                motion_.view_updated(surface_, change.tag, found->second.props, change.props, change.removed);
                break;
            }
            case MirrorChange::Kind::Delete:
                views_.erase(change.tag);
                lists_.erase(change.tag);
                screens_.erase(change.tag);
                motion_.view_deleted(change.tag);
                break;
            case MirrorChange::Kind::Exit:
                // The subtree stays on screen until its exit finishes, but it
                // no longer receives touches or events.
                for (int64_t tag : change.subtree) {
                    auto found = views_.find(tag);
                    if (found == views_.end()) continue;
                    exiting_[tag] = std::move(found->second.props);
                    views_.erase(found);
                    lists_.erase(tag);
                }
                break;
        }
    }
    // Events views emit while this transaction mounts belong to its revision.
    applying_ = true;
    applying_application_ = transaction.application;
    applying_revision_ = transaction.revision;
}

void MountState::finish(const Transaction& transaction) {
    applying_ = false;
    if (!transaction.application.empty()) {
        application_ = transaction.application;
        revision_ = transaction.revision;
    }
}

const Value* MountState::prop(int64_t tag, const std::string& name) const {
    auto found = views_.find(tag);
    if (found != views_.end()) return find_member(found->second.props, name);
    auto leaving = exiting_.find(tag);
    return leaving == exiting_.end() ? nullptr : find_member(leaving->second, name);
}

void MountState::forget(const std::vector<int64_t>& tags) {
    for (int64_t tag : tags) {
        exiting_.erase(tag);
        screens_.erase(tag);
    }
}

std::string MountState::shared_elements(int64_t from_screen, int64_t to_screen) const {
    struct Candidate {
        int64_t tag;
        const Object* props;
    };
    std::map<std::string, Candidate> sources, targets;
    auto props_of = [&](int64_t tag) -> const Object* {
        auto found = views_.find(tag);
        if (found != views_.end()) return &found->second.props;
        auto leaving = exiting_.find(tag);
        return leaving == exiting_.end() ? nullptr : &leaving->second;
    };
    for (const auto& [tag, screen] : screens_) {
        if (screen != from_screen && screen != to_screen) continue;
        const Object* props = props_of(tag);
        if (props == nullptr) continue;
        const Value* name = find_member(*props, "shared_tag");
        if (name == nullptr || !name->is_string() || name->as_string().empty()) continue;
        auto& side = screen == from_screen ? sources : targets;
        auto existing = side.find(name->as_string());
        // The first view mounted with a tag wins when a screen repeats one.
        if (existing == side.end() || tag < existing->second.tag) side[name->as_string()] = {tag, props};
    }
    static const char* const kPaint[] = {"border_radius", "border_top_left_radius", "border_top_right_radius",
                                         "border_bottom_left_radius", "border_bottom_right_radius", "background_color",
                                         "opacity", "shadow_color", "shadow_opacity", "shadow_radius"};
    auto paint = [&](const Object& props) {
        Object out;
        for (const char* key : kPaint) {
            if (const Value* value = find_member(props, key)) out.emplace_back(key, *value);
        }
        return Value::object(std::move(out));
    };
    Array pairs;
    for (const auto& [name, source] : sources) {
        auto target = targets.find(name);
        if (target == targets.end()) continue;
        const Value* transition = find_member(*target->second.props, "shared_transition");
        if (transition == nullptr || !transition->is_object()) transition = find_member(*source.props, "shared_transition");
        pairs.push_back(Value::object({{"name", Value::string(name)},
                                       {"source", Value::integer(source.tag)},
                                       {"target", Value::integer(target->second.tag)},
                                       {"transition", transition != nullptr && transition->is_object() ? *transition : Value()},
                                       {"source_style", paint(*source.props)},
                                       {"target_style", paint(*target->second.props)}}));
    }
    return to_json(Value::array(std::move(pairs)));
}

void MountState::rebuild_gestures(int64_t tag, View& view) {
    const Value* specs = find_member(view.props, "gestures");
    if (specs == nullptr || !specs->is_array() || specs->as_array().empty()) {
        view.gestures.reset();
        return;
    }
    std::vector<GestureConfig> configs;
    for (const Value& spec : specs->as_array()) configs.push_back(decode_gesture(spec));
    view.gestures = std::make_unique<GestureArbiter>(std::move(configs), [this, tag](int index, const Payload& payload) {
        Array arguments;
        arguments.push_back(Value::object(payload));
        emit_event(tag, "gesture:" + std::to_string(index), to_json(Value::array(std::move(arguments))), 0);
    });
}

std::string MountState::identity_json(int64_t sequence) const {
    std::string out = "{\"application\":";
    write_json_string(applying_ ? applying_application_ : application_, out);
    out += ",\"surface\":" + std::to_string(surface_);
    out += ",\"revision\":" + std::to_string(applying_ ? applying_revision_ : revision_);
    out += ",\"sequence\":" + std::to_string(sequence);
    return out;
}

void MountState::emit_event(int64_t tag, const std::string& name, const std::string& arguments_json,
                            int64_t edit_revision) {
    Value arguments;
    std::string error;
    if (!parse_json(arguments_json, arguments, error)) return;
    // Worklet handlers run here, on the UI thread, instead of in Python.
    auto found = views_.find(tag);
    if (found != views_.end()) {
        if (name.rfind("gesture:", 0) == 0) {
            const Value* specs = find_member(found->second.props, "gestures");
            size_t index = static_cast<size_t>(std::strtoul(name.c_str() + 8, nullptr, 10));
            if (specs != nullptr && specs->is_array() && index < specs->as_array().size()) {
                const Value& spec = specs->as_array()[index];
                const Value* worklets = spec.find("worklets");
                const Value* payload = arguments.is_array() && !arguments.as_array().empty() ? &arguments.as_array()[0] : nullptr;
                const Value* state = payload != nullptr ? payload->find("state") : nullptr;
                if (worklets != nullptr && state != nullptr && state->is_string()) {
                    if (const Value* binding = worklets->find(state->as_string()); binding != nullptr && binding->is_integer()) {
                        motion_.event(surface_, tag, binding->as_int(), arguments);
                    }
                }
                const Value* python = spec.find("python");
                if (python != nullptr && python->is_bool() && !python->as_bool()) return;
            }
        } else if (const Value* motion = find_member(found->second.props, "_pn_motion")) {
            const Value* events = motion->find("events");
            const Value* binding = events != nullptr ? events->find(name) : nullptr;
            if (binding != nullptr && binding->is_integer()) {
                motion_.event(surface_, tag, binding->as_int(), arguments);
                return;
            }
        }
    }
    std::string envelope = identity_json(++sequence_);
    envelope += ",\"args\":" + arguments_json + ",\"edit_revision\":" + std::to_string(edit_revision) + "}";
    core_.emit("event", surface_, tag, name, envelope);
}

void MountState::event(int64_t tag, const std::string& name, const char* arguments, int64_t edit_revision) {
    emit_event(tag, name, arguments != nullptr && *arguments ? arguments : "[]", edit_revision);
}

bool MountState::pointer(int64_t tag, const pn_pointer_event* events, size_t count) {
    auto found = views_.find(tag);
    if (found == views_.end() || !found->second.gestures) return false;
    GestureArbiter& arbiter = *found->second.gestures;
    for (size_t i = 0; i < count; ++i) {
        const pn_pointer_event& e = events[i];
        switch (e.phase) {
            case PN_POINTER_DOWN: arbiter.down(e.pointer, e.x, e.y, e.time, e.window_x, e.window_y); break;
            case PN_POINTER_MOVE: arbiter.move(e.pointer, e.x, e.y, e.time, e.window_x, e.window_y); break;
            case PN_POINTER_UP: arbiter.up(e.pointer, e.x, e.y, e.time, e.window_x, e.window_y); break;
            default: arbiter.cancel(e.time); break;
        }
        // An event handler may have replaced this view's gestures.
        found = views_.find(tag);
        if (found == views_.end() || !found->second.gestures || found->second.gestures.get() != &arbiter) return false;
    }
    return arbiter.has_active_pan();
}

double MountState::gesture_deadline(int64_t tag) const {
    auto found = views_.find(tag);
    if (found == views_.end() || !found->second.gestures) return -1;
    std::optional<double> next = found->second.gestures->deadline();
    return next ? *next : -1;
}

void MountState::gesture_poll(int64_t tag, double time) {
    auto found = views_.find(tag);
    if (found != views_.end() && found->second.gestures) found->second.gestures->poll(time);
}

bool MountState::has_gestures(int64_t tag) const {
    auto found = views_.find(tag);
    return found != views_.end() && found->second.gestures != nullptr;
}

std::string MountState::list_apply(int64_t tag) {
    auto found = lists_.find(tag);
    if (found == lists_.end() || found->second.pending.empty()) return std::string();
    std::shared_ptr<ListPatch> patch = found->second.pending.front();
    found->second.pending.pop_front();
    if (patch->base != found->second.store.revision()) return std::string();
    found->second.store.publish(*patch);
    return edits_json(*patch);
}

const ListStore* MountState::list(int64_t tag) const {
    auto found = lists_.find(tag);
    return found == lists_.end() ? nullptr : &found->second.store;
}

}  // namespace pn
