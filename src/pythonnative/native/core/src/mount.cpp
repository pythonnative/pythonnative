#include "mount.h"

#include "core.h"

namespace pn {

void MountState::begin(const Transaction& transaction) {
    for (const MirrorChange& change : transaction.mirror) {
        switch (change.kind) {
            case MirrorChange::Kind::Reset:
                for (const auto& [tag, view] : views_) animator_.forget(surface_, tag);
                views_.clear();
                lists_.clear();
                break;
            case MirrorChange::Kind::Create: {
                View& view = views_[change.tag];
                view.component = change.component;
                view.props = change.props;
                view.gestures.reset();
                rebuild_gestures(change.tag, view);
                if (change.list) lists_[change.tag].pending.push_back(change.list);
                break;
            }
            case MirrorChange::Kind::Update: {
                auto found = views_.find(change.tag);
                if (found == views_.end()) break;
                for (const auto& [key, value] : change.props) set_member(found->second.props, key, value);
                for (const std::string& key : change.removed) remove_member(found->second.props, key);
                if (find_member(change.props, "gestures") != nullptr) rebuild_gestures(change.tag, found->second);
                if (change.list) lists_[change.tag].pending.push_back(change.list);
                break;
            }
            case MirrorChange::Kind::Delete:
                views_.erase(change.tag);
                lists_.erase(change.tag);
                animator_.forget(surface_, change.tag);
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
    return found == views_.end() ? nullptr : find_member(found->second.props, name);
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
    // Animated bindings update on this thread before Python sees the event.
    auto found = views_.find(tag);
    if (found != views_.end() && arguments.is_array() && !arguments.as_array().empty()) {
        const Value& payload = arguments.as_array()[0];
        const Value* bindings = nullptr;
        if (name.rfind("gesture:", 0) == 0) {
            const Value* specs = find_member(found->second.props, "gestures");
            size_t index = static_cast<size_t>(std::strtoul(name.c_str() + 8, nullptr, 10));
            if (specs != nullptr && index < specs->as_array().size()) {
                const Value* events = specs->as_array()[index].find("animated_events");
                const Value* state = payload.find("state");
                if (events != nullptr && state != nullptr) bindings = events->find(state->as_string());
            }
        } else if (const Value* events = find_member(found->second.props, "_pn_animated_events")) {
            bindings = events->find(name);
        }
        if (bindings != nullptr && payload.is_object()) animator_.event(*bindings, payload);
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
