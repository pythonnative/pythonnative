// The UI thread's side of a surface: a mirror of mounted props, list data
// sources, gesture arbiters, and event identity stamping.
#pragma once

#include <cstdint>
#include <deque>
#include <memory>
#include <string>
#include <unordered_map>

#include "../include/pn_core.h"
#include "motion_runtime.h"
#include "gestures.h"
#include "lists.h"
#include "shadow.h"
#include "value.h"

namespace pn {

class Core;

class MountState {
public:
    MountState(Core& core, motion::Runtime& motion, int64_t surface) : core_(core), motion_(motion), surface_(surface) {}

    /// Apply a transaction's mirror changes as the UI thread takes it.
    void begin(const Transaction& transaction);
    void finish(const Transaction& transaction);

    bool is_mounted(int64_t tag) const { return views_.count(tag) != 0; }
    const Value* prop(int64_t tag, const std::string& name) const;
    /// Forget views a finished exit removed.
    void forget(const std::vector<int64_t>& tags);
    /// Views with the same `shared_tag` on two screens, as JSON pairs (RFC 0009).
    std::string shared_elements(int64_t from_screen, int64_t to_screen) const;

    /// Stamp a view event and send it to Python, feeding animated bindings.
    void event(int64_t tag, const std::string& name, const char* arguments, int64_t edit_revision);
    /// Feed pointers to a view's gestures; returns whether a pan is active.
    bool pointer(int64_t tag, const pn_pointer_event* events, size_t count);
    double gesture_deadline(int64_t tag) const;
    void gesture_poll(int64_t tag, double time);
    bool has_gestures(int64_t tag) const;

    // List data sources.
    std::string list_apply(int64_t tag);
    const ListStore* list(int64_t tag) const;

private:
    struct View {
        uint16_t component = 0;
        Object props;
        std::unique_ptr<GestureArbiter> gestures;
    };
    struct List {
        ListStore store;
        std::deque<std::shared_ptr<ListPatch>> pending;
    };
    void rebuild_gestures(int64_t tag, View& view);
    std::string identity_json(int64_t sequence) const;
    void emit_event(int64_t tag, const std::string& name, const std::string& arguments_json, int64_t edit_revision);

    Core& core_;
    motion::Runtime& motion_;
    int64_t surface_;
    std::string application_;
    int64_t revision_ = 0;
    bool applying_ = false;
    std::string applying_application_;
    int64_t applying_revision_ = 0;
    int64_t sequence_ = 0;
    std::unordered_map<int64_t, View> views_;
    std::unordered_map<int64_t, List> lists_;
    std::unordered_map<int64_t, Object> exiting_;  // props of views animating out
    std::unordered_map<int64_t, int64_t> screens_;  // shared_tag view -> its Screen
};

}  // namespace pn
