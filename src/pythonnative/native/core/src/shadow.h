// The commit side of a surface: validation, the shadow tree, Yoga layout,
// view flattening, and the mount diff.
//
// Everything here runs under the core's commit lock, on the Python commit
// worker or the core's layout work. It never touches platform views; it
// writes mount transactions for the UI thread instead.
#pragma once

#include <array>
#include <cmath>
#include <cstdint>
#include <functional>
#include <memory>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

#include <yoga/Yoga.h>

#include "contracts.h"
#include "lists.h"
#include "value.h"

namespace pn {

class Core;

using Frame = std::array<double, 4>;  // x, y, width, height

/// Mount transaction op codes (see `include/pn_core.h`).
enum MountOp : uint8_t {
    kMountReset = 0,
    kMountCreate = 1,
    kMountUpdate = 2,
    kMountInsert = 3,
    kMountDelete = 5,
    kMountFrame = 6,
    kMountCommand = 7,
};

/// A change the UI thread applies to its mirror when it takes a transaction.
struct MirrorChange {
    enum class Kind : uint8_t { Create, Update, Delete, Reset } kind = Kind::Create;
    int64_t tag = 0;
    uint16_t component = 0;
    Object props;            // create: all props; update: changed (normalized)
    std::vector<std::string> removed;
    std::shared_ptr<ListPatch> list;  // a published dataset patch for this list
};

/// One queued unit of UI-thread work.
struct Transaction {
    uint64_t id = 0;
    int64_t surface = 0;
    std::string application;
    int64_t revision = 0;
    std::vector<uint8_t> bytes;  // header plus view ops
    uint32_t op_count = 0;
    std::vector<MirrorChange> mirror;
    std::vector<Value> animations;  // `{"tag", "request"}` objects, run after the view ops
};

struct ShadowNode {
    int64_t tag = 0;
    const Component* component = nullptr;
    Object props;
    int64_t parent = 0;
    std::vector<int64_t> children;
    YGNodeRef yoga = nullptr;
    bool attached = false;      // a child of its parent's Yoga node
    bool detached_root = false; // lays out as its own root inside a parent's container
    bool header_slot = false;
    bool observed = false;      // `_pn_layout`: Python wants this frame
    bool has_frame = false;
    Frame frame{};              // relative to its logical parent
    float constraint_width = NAN;
    float constraint_height = NAN;
    bool has_intrinsic = false;
    float intrinsic_width = 0;
    float intrinsic_height = 0;
    // Mounted state, as last written to a transaction.
    bool flattened = false;
    bool mounted = false;
    std::vector<int64_t> mounted_children;
    int64_t mounted_in = 0;  // the mounted view the platform holds this one in
    bool has_mounted_frame = false;
    Frame mounted_frame{};
};

/// Layout inputs Python sends with a commit (or `pn_core_layout`).
struct LayoutRequest {
    std::vector<int64_t> roots;
    float width = 0;
    float height = 0;
    bool selective = true;
    bool valid() const { return width > 0 && height > 0; }
};

struct ContainerSize {
    float x = 0, y = 0, width = 0, height = 0;
};

class Surface {
public:
    Surface(Core& core, int64_t id);
    ~Surface();
    Surface(const Surface&) = delete;
    Surface& operator=(const Surface&) = delete;

    int64_t id() const { return id_; }
    const std::string& application() const { return application_; }
    int64_t revision() const { return revision_; }
    bool failed() const { return failed_; }
    void mark_failed() { failed_ = true; }

    /// Validate and apply one commit envelope. Returns the acknowledgement
    /// (or rejection) JSON and fills `transaction` when it was accepted.
    std::string commit(const Value& envelope, Transaction& transaction);
    /// Lay out without a commit; returns the frames JSON.
    std::string layout(const LayoutRequest& request, Transaction& transaction);
    /// Relayout after native-initiated changes; returns whether anything moved.
    bool relayout(Transaction& transaction, std::string& layout_message);

    void report_container(int64_t tag, ContainerSize size);
    void report_intrinsic(int64_t tag, float width, float height);
    void invalidate(int64_t tag);
    void invalidate_measurements();

    /// `{"frame": [...], "window": [...]}` for a shadow node, or null.
    std::string measure(int64_t tag) const;
    /// The deepest node at a point in surface coordinates, as JSON.
    std::string inspect(double x, double y) const;
    const ShadowNode* node(int64_t tag) const;
    bool is_mounted(int64_t tag) const;

    /// Used by the Yoga measure trampolines.
    YGSize measure_leaf(ShadowNode& node, float width, YGMeasureMode width_mode, float height,
                        YGMeasureMode height_mode);
    float baseline_leaf(ShadowNode& node, float width, float height);

private:
    struct Candidate;
    bool validate(const Value& envelope, std::string& error, std::string& detail);
    void reset_tree();

    ShadowNode& create_node(int64_t tag, const Component& component, const Object& props);
    void update_node(ShadowNode& node, const Object& changed, const Array& removed);
    void insert_node(ShadowNode& parent, ShadowNode& child, int64_t index);
    void destroy_node(ShadowNode& node);
    void detach_from_parent(ShadowNode& node);
    void restyle(ShadowNode& node, const std::vector<std::string>& touched);
    void refresh_measure(ShadowNode& node);
    bool is_leaf_measured(const ShadowNode& node) const;

    /// Lay out every root, collecting changed frames into `frames`.
    void compute_layout(std::vector<std::array<double, 5>>& frames, double& duration_ns, int& visited);
    void calculate(ShadowNode& node, float width, float height);
    void collect(ShadowNode& node, const std::unordered_set<int64_t>& roots,
                 std::vector<std::array<double, 5>>& frames, int& visited);
    Frame container_for(const ShadowNode& root) const;

    bool should_flatten(const ShadowNode& node) const;
    int64_t mounted_parent_of(const ShadowNode& node) const;
    void desired_children(const ShadowNode& node, std::vector<int64_t>& out) const;
    Frame mounted_frame_of(const ShadowNode& node) const;
    void write_mount(Transaction& transaction, bool reset, const std::vector<int64_t>& created,
                     const std::vector<int64_t>& updated, const std::vector<int64_t>& destroyed,
                     const std::unordered_set<int64_t>& structural, const std::vector<int64_t>& frames);
    void write_frames(Transaction& transaction, ByteWriter& out, uint32_t& count,
                      const std::vector<int64_t>& changed);
    void begin_transaction(Transaction& transaction, ByteWriter& out) const;
    void end_transaction(Transaction& transaction, ByteWriter& out, uint32_t count) const;
    std::string layout_json(const std::vector<std::array<double, 5>>& frames, double duration_ns, int visited) const;

    Core& core_;
    int64_t id_;
    std::string application_;
    int64_t revision_ = 0;
    bool failed_ = false;
    std::unordered_map<int64_t, std::unique_ptr<ShadowNode>> nodes_;
    std::unordered_map<int64_t, ListStore> lists_;  // commit-side datasets by VirtualList tag
    std::unordered_set<int64_t> portals_;
    std::unordered_set<int64_t> detached_roots_;
    std::unordered_set<int64_t> requested_;
    std::unordered_map<int64_t, ContainerSize> containers_;
    LayoutRequest viewport_;
    // Per commit bookkeeping for the mount diff.
    std::unordered_map<int64_t, std::vector<std::string>> touched_;
    std::unordered_map<int64_t, std::shared_ptr<ListPatch>> list_patches_;
    std::unordered_set<int64_t> layout_dirty_tags_;
};

}  // namespace pn
