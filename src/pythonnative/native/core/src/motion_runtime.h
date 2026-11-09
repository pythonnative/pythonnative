// The motion runtime: shared values, worklet bindings, animation drivers,
// layout animations, and exits, all on the platform UI thread (RFC 0009).
//
// Python installs programs and bindings with `pn_core_motion` requests,
// which ride the mount queue so they apply in order with commits. Views
// reference bindings through their `_pn_motion` prop: `style` lists the
// animated style bindings that write to the view, and `events` maps an
// event name to the handler worklet that runs on this thread instead of
// in Python. Each display frame advances drivers, then runs derived
// values, reactions, frame callbacks, and animated styles, and queues the
// writes the platform applies (format in `pn_core.h`).
#pragma once

#include <array>
#include <cstdint>
#include <functional>
#include <map>
#include <memory>
#include <mutex>
#include <set>
#include <tuple>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

#include "motion_anim.h"
#include "motion_vm.h"
#include "value.h"

namespace pn {

class Core;

namespace motion {

/// Whether an animated style may write `key`, and whether it affects layout.
bool animatable_style(std::string_view key, bool& layout);

class Runtime final : public Host {
public:
    /// The committed value of a view's prop (to restore after animating), or nullptr.
    using PropLookup = std::function<const Value*(int64_t surface, int64_t tag, const std::string& key)>;
    /// Apply an animated layout prop through the core's layout worker (null restores it).
    using LayoutPost = std::function<void(int64_t surface, int64_t tag, const std::string& key, const Value& value)>;
    /// Views a finished exit removed, so mount state can forget them.
    using Removed = std::function<void(int64_t surface, const std::vector<int64_t>& tags)>;

    explicit Runtime(Core& core) : core_(core) {}

    void set_lookup(PropLookup lookup) { lookup_ = std::move(lookup); }
    void set_layout_post(LayoutPost post) { layout_post_ = std::move(post); }
    void set_removed(Removed removed) { removed_ = std::move(removed); }

    /// Check a request on the Python thread before it's queued.
    static bool valid_request(const Value& request, std::string& error);
    /// Apply a request on the UI thread.
    void handle(const Value& request, int64_t surface);

    // Views (UI thread, from mount state).
    void view_mounted(int64_t surface, int64_t tag, const Object& props);
    void view_updated(int64_t surface, int64_t tag, const Object& props, const Object& changed,
                      const std::vector<std::string>& removed);
    void view_deleted(int64_t tag);
    void surface_reset(int64_t surface);
    /// Run an event's handler worklet; returns whether one ran.
    bool event(int64_t surface, int64_t tag, int64_t binding, const Value& arguments);

    /// Layout animation and exit records a transaction carried.
    void records(int64_t surface, const std::vector<Value>& records);
    /// A host-owned exit (a leaving screen or modal) finished.
    void exit_finished(int64_t surface, int64_t tag);

    /// Advance animations; returns whether frames should continue.
    bool frame(double timestamp_ms);
    bool running() const;
    void set_reduce_motion(bool enabled) { reduce_motion_ = enabled; }
    void reset();
    bool take_writes(std::vector<uint8_t>& out);

    /// The latest published value of a shared value as JSON (any thread).
    std::string published(int64_t id);

    // Host, for worklets.
    MValue read_shared(int64_t id) override;
    void write_shared(int64_t id, const MValue& value) override;
    void cancel_shared(int64_t id) override;
    void call_python(int64_t id, const Seq& args) override;

private:
    enum class Kind : uint8_t { Derived, Reaction, Frame, Style, Handler };

    struct Binding {
        int64_t id = 0;
        Kind kind = Kind::Handler;
        std::shared_ptr<const Closure> closure;  // the worklet (a reaction's `prepare`)
        std::shared_ptr<const Closure> react;
        int64_t output = 0;  // a derived value's shared value
        bool active = true;  // frame callbacks
        bool dirty = true;
        bool failed = false;
        bool has_previous = false;
        MValue previous;
        std::set<int64_t> deps;
        int64_t surface = 0;  // where messages about it go
    };

    struct Shared {
        MValue value;
        std::unique_ptr<Animation> animation;
        int64_t token = 0;
        int64_t surface = 0;  // where its finished message goes
        std::set<int64_t> dependents;
    };

    void emit(int64_t surface, const std::string& payload);

    struct Channel {
        std::string key;  // a style key, a transform entry, or frame_x/frame_y/frame_width/frame_height
        std::unique_ptr<Animation> animation;
        MValue value;
    };

    struct ViewAnimation {
        enum class Type : uint8_t { Entering, Layout, Exiting } type = Type::Entering;
        int64_t surface = 0;
        int64_t tag = 0;
        std::vector<Channel> channels;
        // Keyframes: one progress channel and the frames it interpolates.
        bool keyframed = false;
        std::vector<std::pair<double, Map>> keyframes;
        std::vector<std::function<double(double)>> keyframe_easings;
        // Fading layout transitions cross-fade while the frame jumps halfway.
        bool fading = false;
        std::array<double, 4> from{}, to{};
        bool frame = false;
        std::set<std::string> written;  // style keys to restore afterward
        // Exits.
        std::vector<int64_t> subtree;
        bool host_owned = false;
    };

    // Requests.
    void define_program(const Value& request);
    void define_shared(const Value& request);
    void bind(const Value& request);
    void release(const Value& request);
    bool closure_from(const Value* wire, std::shared_ptr<const Closure>& out, std::string& error);

    // Shared values and bindings.
    void set_value(int64_t id, const MValue& value);
    void start_animation(int64_t id, const MValue& descriptor, int64_t token);
    void interrupt(Shared& shared);
    void mark_dependents(int64_t id);
    void flush();
    bool run(Binding& binding, const std::shared_ptr<const Closure>& closure, const Seq& args, MValue& result,
             bool record);
    void run_binding(Binding& binding);
    void track(Binding& binding, std::set<int64_t> deps);
    void report(const Failure& failure, int64_t binding);
    void run_completions();
    void publish();

    // Animated styles.
    void apply_style(Binding& binding, const MValue& style);
    void apply_style_to(int64_t binding, int64_t tag, const MValue& style);
    void restore(int64_t tag, const std::string& key);
    void write_prop(int64_t tag, const std::string& key, const Value& value);
    void write_frame(int64_t tag, const std::array<double, 4>& frame);
    void update_targets(int64_t surface, int64_t tag, const Value* motion);

    // Layout animations.
    void start_entering(int64_t surface, const Value& record);
    void start_layout(int64_t surface, const Value& record);
    void start_exit(int64_t surface, const Value& record);
    bool build(ViewAnimation& animation, const Value& spec, const std::array<double, 4>& frame, double window_width,
               double window_height, bool entering_side, std::string& error);
    bool build_custom(ViewAnimation& animation, const Value& spec, const Map& values, std::string& error);
    void write_view(ViewAnimation& animation);
    void finish_view(ViewAnimation& animation, bool completed);
    void remove(int64_t surface, const std::vector<int64_t>& subtree);
    Value static_value(int64_t surface, int64_t tag, const std::string& key);
    std::unique_ptr<Animation> channel_animation(const Value& spec, const MValue& to, std::string& error);

    Core& core_;
    PropLookup lookup_;
    LayoutPost layout_post_;
    Removed removed_;
    bool reduce_motion_ = false;
    double previous_time_ = -1;

    std::unordered_map<int64_t, std::shared_ptr<const Program>> programs_;
    std::map<int64_t, Shared> shared_;
    std::map<int64_t, Binding> bindings_;
    std::vector<Completion> completions_;
    std::vector<std::tuple<int64_t, bool, int64_t>> finished_tokens_;  // token, finished, surface
    int64_t surface_ = 0;      // the request or view being handled
    int64_t last_surface_ = 0; // where messages go when nothing more specific is known
    std::set<int64_t>* recording_ = nullptr;
    bool flushing_ = false;

    // Views: which bindings style them, and what motion wrote.
    std::unordered_map<int64_t, int64_t> view_surface_;
    std::unordered_map<int64_t, std::vector<int64_t>> view_styles_;     // tag -> style bindings
    std::unordered_map<int64_t, std::set<int64_t>> style_targets_;      // binding -> tags
    std::unordered_map<int64_t, std::map<std::string, Value>> motion_values_;  // tag -> key -> last motion value
    std::unordered_map<int64_t, std::map<std::string, Value>> applied_;        // tag -> key -> last written (dedupe)
    std::unordered_map<int64_t, std::map<std::string, Value>> layout_values_;  // tag -> layout key -> last posted
    std::unordered_map<int64_t, std::unordered_map<std::string, std::set<int64_t>>> style_keys_;  // tag -> key -> bindings

    std::unordered_map<int64_t, ViewAnimation> entering_, layout_, exiting_;
    std::unordered_map<int64_t, std::array<double, 4>> frames_;  // last animated frame per tag
    std::unordered_set<int64_t> finished_early_;  // host-owned exits reported before their record arrived

    std::vector<uint8_t> writes_;
    uint32_t write_count_ = 0;

    std::mutex published_mutex_;
    std::unordered_map<int64_t, std::string> published_;
    std::unordered_set<int64_t> unpublished_;
};

/// Run one worklet outside any runtime (tests and tooling): `{"programs":
/// {id: program}, "closure": closure, "args": [...], "shared": {id: value}}`.
std::string evaluate(const char* request);

}  // namespace motion
}  // namespace pn
