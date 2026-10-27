#include "shadow.h"

#include <algorithm>
#include <chrono>
#include <cmath>

#include "core.h"
#include "style.h"

namespace pn {

namespace {

constexpr uint32_t kMountMagic = 0x544D4E50;  // "PNMT"
constexpr uint16_t kMountFormat = 1;
constexpr const char* kEdges[] = {"left", "top", "right", "bottom", "start", "end", "horizontal", "vertical"};

ShadowNode& node_of(YGNodeConstRef yoga) {
    return *static_cast<ShadowNode*>(YGNodeGetContext(yoga));
}

thread_local Surface* measuring_surface = nullptr;

YGSize measure_trampoline(YGNodeConstRef yoga, float width, YGMeasureMode width_mode, float height,
                          YGMeasureMode height_mode) {
    if (measuring_surface == nullptr) return {0, 0};
    return measuring_surface->measure_leaf(node_of(yoga), width, width_mode, height, height_mode);
}

float baseline_trampoline(YGNodeConstRef yoga, float width, float height) {
    if (measuring_surface == nullptr) return height;
    return measuring_surface->baseline_leaf(node_of(yoga), width, height);
}

bool same_constraint(float a, float b) {
    return a == b || (std::isnan(a) && std::isnan(b));
}

bool same_frame(const Frame& a, const Frame& b) {
    return a[0] == b[0] && a[1] == b[1] && a[2] == b[2] && a[3] == b[3];
}

double finite_or_zero(float value) {
    return std::isfinite(value) ? static_cast<double>(value) : 0.0;
}

/// The insert sequence turning `before` into `after` (see `reconciler/children.py`).
std::vector<std::pair<int64_t, uint32_t>> plan_moves(const std::vector<int64_t>& before,
                                                     const std::vector<int64_t>& after) {
    std::vector<std::pair<int64_t, uint32_t>> ops;
    if (before == after) return ops;
    std::unordered_map<int64_t, size_t> position_after;
    for (size_t i = 0; i < after.size(); ++i) position_after[after[i]] = i;
    std::vector<size_t> targets;
    for (int64_t tag : before) {
        auto found = position_after.find(tag);
        if (found != position_after.end()) targets.push_back(found->second);
    }
    // Longest increasing subsequence of the surviving targets: those children stay put.
    std::vector<size_t> tails, tail_index, previous(targets.size(), SIZE_MAX);
    for (size_t i = 0; i < targets.size(); ++i) {
        auto it = std::lower_bound(tails.begin(), tails.end(), targets[i]);
        size_t length = static_cast<size_t>(it - tails.begin());
        if (it == tails.end()) {
            tails.push_back(targets[i]);
            tail_index.push_back(i);
        } else {
            *it = targets[i];
            tail_index[length] = i;
        }
        previous[i] = length > 0 ? tail_index[length - 1] : SIZE_MAX;
    }
    std::unordered_set<size_t> keep;
    if (!tail_index.empty()) {
        for (size_t i = tail_index.back(); i != SIZE_MAX; i = previous[i]) keep.insert(targets[i]);
    }
    std::vector<int64_t> sim = before;
    bool has_anchor = false;
    int64_t anchor = 0;
    for (size_t i = after.size(); i-- > 0;) {
        int64_t tag = after[i];
        if (keep.count(i) != 0) {
            anchor = tag;
            has_anchor = true;
            continue;
        }
        auto existing = std::find(sim.begin(), sim.end(), tag);
        if (existing != sim.end()) sim.erase(existing);
        size_t index = sim.size();
        if (has_anchor) index = static_cast<size_t>(std::find(sim.begin(), sim.end(), anchor) - sim.begin());
        sim.insert(sim.begin() + static_cast<std::ptrdiff_t>(index), tag);
        ops.emplace_back(tag, static_cast<uint32_t>(index));
        anchor = tag;
        has_anchor = true;
    }
    return ops;
}

}  // namespace

// ----------------------------------------------------------------------
// Lifecycle
// ----------------------------------------------------------------------

Surface::Surface(Core& core, int64_t id) : core_(core), id_(id) {}

Surface::~Surface() {
    reset_tree();
}

void Surface::reset_tree() {
    for (auto& [tag, node] : nodes_) {
        if (node->yoga != nullptr) {
            YGNodeRemoveAllChildren(node->yoga);
        }
    }
    for (auto& [tag, node] : nodes_) {
        if (node->yoga != nullptr) YGNodeFree(node->yoga);
        node->yoga = nullptr;
    }
    nodes_.clear();
    lists_.clear();
    portals_.clear();
    detached_roots_.clear();
    requested_.clear();
}

const ShadowNode* Surface::node(int64_t tag) const {
    auto found = nodes_.find(tag);
    return found == nodes_.end() ? nullptr : found->second.get();
}

bool Surface::is_mounted(int64_t tag) const {
    const ShadowNode* found = node(tag);
    return found != nullptr && found->mounted;
}

// ----------------------------------------------------------------------
// Validation
// ----------------------------------------------------------------------

/// Structural state a commit would leave behind, without touching the tree.
struct Surface::Candidate {
    struct Entry {
        bool live = false;
        uint16_t component = 0;
        int64_t parent = 0;
        int64_t child_count = 0;
    };
    const Surface& surface;
    bool replacing;
    std::unordered_map<int64_t, Entry> entries;

    Entry* get(int64_t tag) {
        auto found = entries.find(tag);
        if (found != entries.end()) return found->second.live ? &found->second : nullptr;
        if (replacing) return nullptr;
        const ShadowNode* node = surface.node(tag);
        if (node == nullptr) return nullptr;
        Entry& entry = entries[tag];
        entry = {true, node->component->id, node->parent, static_cast<int64_t>(node->children.size())};
        return &entry;
    }
};

bool Surface::validate(const Value& envelope, std::string& error, std::string& detail) {
    const Contracts& contracts = core_.contracts();
    const Value* version = envelope.find("version");
    const Value* application = envelope.find("application");
    const Value* revision = envelope.find("revision");
    const Value* ops = envelope.find("ops");
    if (version == nullptr || !version->is_integer() || version->as_int() != PN_CORE_PROTOCOL_VERSION) {
        error = "expected a protocol v" + std::to_string(PN_CORE_PROTOCOL_VERSION) + " envelope; rebuild the app";
        return false;
    }
    if (application == nullptr || !application->is_string() || application->as_string().empty()) {
        error = "invalid application identity";
        return false;
    }
    bool replacing = application->as_string() != application_;
    int64_t expected = replacing ? 1 : revision_ + 1;
    if (revision == nullptr || !revision->is_integer() || revision->as_int() != expected) {
        error = "expected revision " + std::to_string(expected);
        return false;
    }
    if (!replacing && failed_) {
        error = "the surface failed; remount the application";
        return false;
    }
    if (ops == nullptr || !ops->is_array()) {
        error = "commit ops must be an array";
        return false;
    }
    Candidate candidate{*this, replacing, {}};
    std::unordered_set<int64_t> patched_lists;
    list_patches_.clear();
    const Array& list = ops->as_array();
    for (size_t index = 0; index < list.size(); ++index) {
        auto reject = [&](const std::string& message) {
            error = "invalid op " + std::to_string(index) + ": " + message;
            detail = std::to_string(index);
            return false;
        };
        const Value& op = list[index];
        const Array& parts = op.as_array();
        if (!op.is_array() || parts.size() < 2 || !parts[0].is_string()) return reject("expected an operation array");
        const std::string& code = parts[0].as_string();
        size_t arity = code == "c" || code == "u" || code == "i" ? 4 : code == "d" ? 2 : 0;
        if (arity == 0 || parts.size() != arity) return reject("invalid opcode or arity");
        if (!parts[1].is_integer() || parts[1].as_int() <= 0) return reject("invalid tag");
        int64_t tag = parts[1].as_int();
        if (code == "c") {
            if (candidate.get(tag) != nullptr) return reject("duplicate create of " + std::to_string(tag));
            if (!parts[2].is_string()) return reject("invalid component name");
            const Component* component = contracts.component(parts[2].as_string());
            if (component == nullptr) return reject("unknown component " + parts[2].as_string());
            if (!parts[3].is_object()) return reject("create props must be an object");
            std::string why;
            if (!contracts.validate_props(*component, parts[3].as_object(), false, why)) return reject(why);
            if (const Value* dataset = parts[3].find("dataset"); dataset != nullptr && component->name == "VirtualList") {
                auto patch = std::make_shared<ListPatch>();
                if (!ListStore().prepare(*dataset, *patch, why)) return reject(why);
                if (!patched_lists.insert(tag).second) return reject("a list may receive one dataset patch per commit");
                list_patches_[tag] = patch;
            }
            candidate.entries[tag] = {true, component->id, 0, 0};
            continue;
        }
        Candidate::Entry* entry = candidate.get(tag);
        if (entry == nullptr) return reject("unknown tag " + std::to_string(tag));
        const Component* component = contracts.component(entry->component);
        if (code == "u") {
            if (!parts[2].is_object() || !parts[3].is_array()) return reject("update requires props and removals");
            std::string why;
            if (!contracts.validate_props(*component, parts[2].as_object(), true, why)) return reject(why);
            if (!contracts.validate_removal(*component, parts[2].as_object(), parts[3].as_array(), why)) {
                return reject(why);
            }
            if (const Value* dataset = parts[2].find("dataset"); dataset != nullptr && component->name == "VirtualList") {
                if (!patched_lists.insert(tag).second) return reject("a list may receive one dataset patch per commit");
                auto patch = std::make_shared<ListPatch>();
                auto existing = lists_.find(tag);
                const ListStore empty;
                const ListStore& store = replacing || existing == lists_.end() ? empty : existing->second;
                if (!store.prepare(*dataset, *patch, why)) return reject(why);
                list_patches_[tag] = patch;
            }
        } else if (code == "i") {
            if (!parts[2].is_integer() || !parts[3].is_integer() || parts[3].as_int() < 0) {
                return reject("invalid child or insertion index");
            }
            int64_t child_tag = parts[2].as_int();
            Candidate::Entry* child = candidate.get(child_tag);
            if (child == nullptr) return reject("unknown child " + std::to_string(child_tag));
            for (int64_t ancestor = tag; ancestor != 0;) {
                if (ancestor == child_tag) return reject("insertion creates a cycle");
                Candidate::Entry* above = candidate.get(ancestor);
                ancestor = above == nullptr ? 0 : above->parent;
            }
            entry = candidate.get(tag);
            int64_t siblings = entry->child_count - (child->parent == tag ? 1 : 0);
            if (parts[3].as_int() > siblings) return reject("insertion index exceeds child count");
            if (child->parent != 0) {
                if (Candidate::Entry* old = candidate.get(child->parent)) old->child_count -= 1;
            }
            entry = candidate.get(tag);
            entry->child_count += 1;
            child = candidate.get(child_tag);
            child->parent = tag;
        } else {
            if (entry->child_count != 0) return reject("destroy children before their parent");
            if (entry->parent != 0) {
                if (Candidate::Entry* old = candidate.get(entry->parent)) old->child_count -= 1;
            }
            entry = candidate.get(tag);
            entry->live = false;
        }
    }
    if (const Value* layout = envelope.find("layout")) {
        const Value* roots = layout->find("roots");
        const Value* width = layout->find("width");
        const Value* height = layout->find("height");
        if (!layout->is_object() || roots == nullptr || !roots->is_array() || width == nullptr ||
            !width->is_number() || width->as_double() <= 0 || height == nullptr || !height->is_number() ||
            height->as_double() <= 0) {
            error = "invalid layout request";
            return false;
        }
        for (const Value& root : roots->as_array()) {
            if (!root.is_integer() || candidate.get(root.as_int()) == nullptr) {
                error = "invalid layout root";
                return false;
            }
        }
    }
    return true;
}

// ----------------------------------------------------------------------
// The shadow tree
// ----------------------------------------------------------------------

bool Surface::is_leaf_measured(const ShadowNode& node) const {
    return node.component->measurement != Measurement::Container && YGNodeGetChildCount(node.yoga) == 0;
}

void Surface::refresh_measure(ShadowNode& node) {
    if (is_leaf_measured(node)) {
        if (!YGNodeHasMeasureFunc(node.yoga)) YGNodeSetMeasureFunc(node.yoga, measure_trampoline);
        bool text = node.component->measurement == Measurement::Text;
        YGNodeSetBaselineFunc(node.yoga, text ? baseline_trampoline : nullptr);
        YGNodeMarkDirty(node.yoga);
    } else if (YGNodeHasMeasureFunc(node.yoga)) {
        YGNodeSetMeasureFunc(node.yoga, nullptr);
        YGNodeSetBaselineFunc(node.yoga, nullptr);
    }
}

void Surface::restyle(ShadowNode& node, const std::vector<std::string>& touched) {
    std::vector<std::string_view> keys(touched.begin(), touched.end());
    bool layout = false, recreate = false;
    core_.contracts().changes(*node.component, keys, layout, recreate);
    if (!layout && node.has_frame) return;
    std::unordered_set<std::string> direct(touched.begin(), touched.end());
    for (const char* family : {"margin", "padding"}) {
        std::string prefix = std::string(family) + "_";
        bool affected = std::any_of(touched.begin(), touched.end(), [&](const std::string& key) {
            return key == family || key.rfind(prefix, 0) == 0;
        });
        if (!affected) continue;
        Object resolved;
        if (const Value* value = find_member(node.props, family)) {
            if (value->is_object()) {
                for (const auto& [edge, amount] : value->as_object()) {
                    set_member(resolved, edge == "all" ? std::string(family) : prefix + edge, amount);
                }
            } else {
                set_member(resolved, family, *value);
            }
        }
        for (const char* edge : kEdges) {
            std::string key = prefix + edge;
            if (const Value* value = find_member(node.props, key)) set_member(resolved, key, *value);
        }
        apply_style(node.yoga, family, find_member(resolved, family));
        direct.erase(family);
        for (const char* edge : kEdges) {
            std::string key = prefix + edge;
            apply_style(node.yoga, key, find_member(resolved, key));
            direct.erase(key);
        }
    }
    for (const std::string& key : direct) {
        if (is_layout_style(key)) apply_style(node.yoga, key, find_member(node.props, key));
    }
    if (node.component->clip) {
        YGNodeStyleSetOverflow(node.yoga, YGOverflowHidden);
        if (find_member(node.props, "flex_shrink") == nullptr) YGNodeStyleSetFlexShrink(node.yoga, 1);
    }
    refresh_measure(node);
}

ShadowNode& Surface::create_node(int64_t tag, const Component& component, const Object& props) {
    auto owned = std::make_unique<ShadowNode>();
    ShadowNode& node = *owned;
    node.tag = tag;
    node.component = &component;
    node.props = props;
    node.yoga = YGNodeNew();
    YGNodeSetContext(node.yoga, &node);
    nodes_.emplace(tag, std::move(owned));
    if (component.portal) portals_.insert(tag);
    if (const Value* observed = find_member(props, "_pn_layout"); observed != nullptr && observed->as_bool()) {
        node.observed = true;
        requested_.insert(tag);
    }
    node.header_slot = find_member(props, "_pn_header_slot") != nullptr &&
                       !find_member(props, "_pn_header_slot")->is_null();
    std::vector<std::string> touched;
    touched.reserve(props.size());
    for (const auto& member : props) touched.push_back(member.first);
    restyle(node, touched);
    if (component.name == "VirtualList") {
        ListStore& store = lists_[tag];
        auto patch = list_patches_.find(tag);
        if (patch != list_patches_.end()) store.publish(*patch->second);
    }
    return node;
}

void Surface::update_node(ShadowNode& node, const Object& changed, const Array& removed) {
    std::vector<std::string>& touched = touched_[node.tag];
    std::vector<std::string> keys;
    for (const auto& [key, value] : changed) {
        set_member(node.props, key, value);
        keys.push_back(key);
    }
    for (const Value& name : removed) {
        remove_member(node.props, name.as_string());
        keys.push_back(name.as_string());
    }
    for (const std::string& key : keys) {
        if (std::find(touched.begin(), touched.end(), key) == touched.end()) touched.push_back(key);
    }
    if (const Value* observed = find_member(changed, "_pn_layout")) {
        node.observed = observed->as_bool();
        if (node.observed) requested_.insert(node.tag);
    } else if (std::any_of(removed.begin(), removed.end(),
                           [](const Value& name) { return name.as_string() == "_pn_layout"; })) {
        node.observed = false;
    }
    restyle(node, keys);
    if (node.component->name == "VirtualList") {
        auto patch = list_patches_.find(node.tag);
        if (patch != list_patches_.end()) lists_[node.tag].publish(*patch->second);
    }
}

void Surface::detach_from_parent(ShadowNode& node) {
    if (node.parent == 0) return;
    auto found = nodes_.find(node.parent);
    if (found != nodes_.end()) {
        ShadowNode& parent = *found->second;
        parent.children.erase(std::remove(parent.children.begin(), parent.children.end(), node.tag),
                              parent.children.end());
        if (node.attached) {
            YGNodeRemoveChild(parent.yoga, node.yoga);
            refresh_measure(parent);
        }
    }
    node.parent = 0;
    node.attached = false;
    if (node.detached_root) detached_roots_.erase(node.tag);
    node.detached_root = false;
}

void Surface::insert_node(ShadowNode& parent, ShadowNode& child, int64_t index) {
    detach_from_parent(child);
    index = std::min<int64_t>(index, static_cast<int64_t>(parent.children.size()));
    parent.children.insert(parent.children.begin() + index, child.tag);
    child.parent = parent.tag;
    if (parent.component->detach_children || child.header_slot) {
        child.detached_root = true;
        detached_roots_.insert(child.tag);
        return;
    }
    // Yoga's children are the attached logical children, in order.
    uint32_t position = 0;
    for (int64_t sibling : parent.children) {
        if (sibling == child.tag) break;
        auto found = nodes_.find(sibling);
        if (found != nodes_.end() && found->second->attached) ++position;
    }
    YGNodeSetMeasureFunc(parent.yoga, nullptr);
    YGNodeSetBaselineFunc(parent.yoga, nullptr);
    YGNodeInsertChild(parent.yoga, child.yoga, std::min(position, static_cast<uint32_t>(YGNodeGetChildCount(parent.yoga))));
    child.attached = true;
}

void Surface::destroy_node(ShadowNode& node) {
    detach_from_parent(node);
    portals_.erase(node.tag);
    requested_.erase(node.tag);
    containers_.erase(node.tag);
    lists_.erase(node.tag);
    touched_.erase(node.tag);
    YGNodeFree(node.yoga);
    node.yoga = nullptr;
    nodes_.erase(node.tag);
}

// ----------------------------------------------------------------------
// Measurement
// ----------------------------------------------------------------------

YGSize Surface::measure_leaf(ShadowNode& node, float width, YGMeasureMode width_mode, float height,
                             YGMeasureMode height_mode) {
    float max_width = width_mode == YGMeasureModeUndefined || !std::isfinite(width) ? INFINITY : width;
    float max_height = height_mode == YGMeasureModeUndefined || !std::isfinite(height) ? INFINITY : height;
    auto fit = [&](float w, float h) -> YGSize {
        if (w <= 0 || h <= 0) return {0, 0};
        if (std::isfinite(max_width) && max_width > 0 && w > max_width) {
            h *= max_width / w;
            w = max_width;
        }
        if (std::isfinite(max_height) && max_height > 0 && h > max_height) {
            w *= max_height / h;
            h = max_height;
        }
        return {w, h};
    };
    switch (node.component->measurement) {
        case Measurement::Container: return {0, 0};
        case Measurement::Fill:
            return {std::isfinite(max_width) ? max_width : 0, std::isfinite(max_height) ? max_height : 0};
        case Measurement::Image:
            return node.has_intrinsic ? fit(node.intrinsic_width, node.intrinsic_height) : YGSize{0, 0};
        case Measurement::Svg: {
            float w = 24, h = 24;
            if (const Value* box = find_member(node.props, "view_box"); box != nullptr && box->is_string()) {
                std::vector<float> parts;
                std::string token;
                for (char c : box->as_string() + " ") {
                    if (c == ' ' || c == ',' || c == '\n' || c == '\t') {
                        if (!token.empty()) {
                            char* end = nullptr;
                            float parsed = std::strtof(token.c_str(), &end);
                            if (end != token.c_str()) parts.push_back(parsed);
                            token.clear();
                        }
                    } else {
                        token.push_back(c);
                    }
                }
                if (parts.size() == 4 && parts[2] > 0 && parts[3] > 0) {
                    w = parts[2];
                    h = parts[3];
                }
            }
            return fit(w, h);
        }
        default: break;
    }
    ByteWriter props;
    props.value(Value::object(node.props));
    pn_measure_request request{};
    request.surface = id_;
    request.tag = node.tag;
    request.component = node.component->name.c_str();
    request.mode = node.component->measurement == Measurement::Text      ? PN_MEASURE_TEXT
                   : node.component->measurement == Measurement::Native ? PN_MEASURE_NATIVE
                                                                         : PN_MEASURE_INTRINSIC;
    request.props = {props.bytes().data(), props.size()};
    request.width = width;
    request.width_mode = static_cast<int32_t>(width_mode);
    request.height = height;
    request.height_mode = static_cast<int32_t>(height_mode);
    pn_size size = core_.platform_measure(request);
    float w = std::isfinite(size.width) ? std::max(0.0f, size.width) : 0;
    float h = std::isfinite(size.height) ? std::max(0.0f, size.height) : 0;
    if (std::isfinite(max_width)) w = std::min(w, max_width);
    return {w, h};
}

float Surface::baseline_leaf(ShadowNode& node, float width, float height) {
    return core_.platform_baseline(id_, node.tag, width, height);
}

void Surface::report_container(int64_t tag, ContainerSize size) {
    containers_[tag] = size;
}

void Surface::report_intrinsic(int64_t tag, float width, float height) {
    auto found = nodes_.find(tag);
    if (found == nodes_.end()) return;
    ShadowNode& node = *found->second;
    node.has_intrinsic = true;
    node.intrinsic_width = width;
    node.intrinsic_height = height;
    if (YGNodeHasMeasureFunc(node.yoga)) YGNodeMarkDirty(node.yoga);
}

void Surface::invalidate(int64_t tag) {
    auto found = nodes_.find(tag);
    if (found != nodes_.end() && YGNodeHasMeasureFunc(found->second->yoga)) YGNodeMarkDirty(found->second->yoga);
}

void Surface::invalidate_measurements() {
    for (auto& [tag, node] : nodes_) {
        if (YGNodeHasMeasureFunc(node->yoga)) YGNodeMarkDirty(node->yoga);
    }
}

// ----------------------------------------------------------------------
// Layout
// ----------------------------------------------------------------------

void Surface::calculate(ShadowNode& node, float width, float height) {
    if (same_constraint(node.constraint_width, width) && same_constraint(node.constraint_height, height) &&
        !YGNodeIsDirty(node.yoga)) {
        return;
    }
    YGNodeCalculateLayout(node.yoga, width, height, YGDirectionLTR);
    node.constraint_width = width;
    node.constraint_height = height;
}

Frame Surface::container_for(const ShadowNode& root) const {
    auto own = containers_.find(root.tag);
    if (own != containers_.end() && own->second.width > 0 && own->second.height > 0) {
        return {own->second.x, own->second.y, own->second.width, own->second.height};
    }
    if (root.parent != 0) {
        auto parent = containers_.find(root.parent);
        if (parent != containers_.end() && parent->second.width > 0 && parent->second.height > 0) {
            return {parent->second.x, parent->second.y, parent->second.width, parent->second.height};
        }
    }
    return {0, 0, viewport_.width, viewport_.height};
}

void Surface::collect(ShadowNode& node, const std::unordered_set<int64_t>& roots,
                      std::vector<std::array<double, 5>>& frames, int& visited) {
    if (!YGNodeGetHasNewLayout(node.yoga)) return;
    ++visited;
    YGNodeSetHasNewLayout(node.yoga, false);
    Frame frame = {finite_or_zero(YGNodeLayoutGetLeft(node.yoga)), finite_or_zero(YGNodeLayoutGetTop(node.yoga)),
                   finite_or_zero(YGNodeLayoutGetWidth(node.yoga)), finite_or_zero(YGNodeLayoutGetHeight(node.yoga))};
    if (!node.has_frame || !same_frame(frame, node.frame)) {
        node.frame = frame;
        node.has_frame = true;
        layout_dirty_tags_.insert(node.tag);
        if (!viewport_.selective || node.observed) {
            frames.push_back({static_cast<double>(node.tag), frame[0], frame[1], frame[2], frame[3]});
        }
        requested_.erase(node.tag);
    }
    for (int64_t tag : node.children) {
        auto found = nodes_.find(tag);
        if (found != nodes_.end() && found->second->attached) collect(*found->second, roots, frames, visited);
    }
}

void Surface::compute_layout(std::vector<std::array<double, 5>>& frames, double& duration_ns, int& visited) {
    auto started = std::chrono::steady_clock::now();
    visited = 0;
    if (!viewport_.valid()) {
        duration_ns = 0;
        return;
    }
    measuring_surface = this;
    std::unordered_set<int64_t> roots;
    for (int64_t tag : viewport_.roots) {
        auto found = nodes_.find(tag);
        if (found == nodes_.end()) continue;
        roots.insert(tag);
        calculate(*found->second, viewport_.width, viewport_.height);
    }
    for (int64_t tag : portals_) {
        auto found = nodes_.find(tag);
        if (found == nodes_.end()) continue;
        Frame box = container_for(*found->second);
        YGNodeStyleSetWidth(found->second->yoga, static_cast<float>(box[2]));
        YGNodeStyleSetHeight(found->second->yoga, static_cast<float>(box[3]));
        calculate(*found->second, static_cast<float>(box[2]), static_cast<float>(box[3]));
    }
    // A detached root inside another detached root needs its container's frame
    // first, so lay them out from the outermost in.
    std::vector<std::pair<int, ShadowNode*>> detached;
    for (int64_t tag : detached_roots_) {
        auto found = nodes_.find(tag);
        if (found == nodes_.end()) continue;
        int depth = 0;
        for (int64_t up = found->second->parent; up != 0;) {
            ++depth;
            auto above = nodes_.find(up);
            up = above == nodes_.end() ? 0 : above->second->parent;
        }
        detached.emplace_back(depth, found->second.get());
    }
    std::sort(detached.begin(), detached.end(), [](const auto& a, const auto& b) { return a.first < b.first; });
    auto collect_tree = [&](ShadowNode& root) { collect(root, roots, frames, visited); };
    for (int64_t tag : viewport_.roots) {
        auto found = nodes_.find(tag);
        if (found != nodes_.end()) collect_tree(*found->second);
    }
    for (int64_t tag : portals_) {
        auto found = nodes_.find(tag);
        if (found != nodes_.end()) collect_tree(*found->second);
    }
    for (auto& [depth, root] : detached) {
        if (root->header_slot) {
            calculate(*root, NAN, 44);
        } else {
            auto parent = nodes_.find(root->parent);
            const ShadowNode* list = parent != nodes_.end() && parent->second->component->name == "VirtualList"
                                         ? parent->second.get()
                                         : nullptr;
            if (list != nullptr) {
                const Value* horizontal = find_member(list->props, "horizontal");
                bool across = horizontal != nullptr && horizontal->as_bool();
                float width = list->has_frame && list->frame[2] > 0 ? static_cast<float>(list->frame[2]) : viewport_.width;
                float height = list->has_frame && list->frame[3] > 0 ? static_cast<float>(list->frame[3]) : viewport_.height;
                calculate(*root, across ? NAN : width, across ? height : NAN);
            } else {
                Frame box = container_for(*root);
                calculate(*root, static_cast<float>(box[2]), static_cast<float>(box[3]));
            }
        }
        collect_tree(*root);
    }
    for (int64_t tag : requested_) {
        auto found = nodes_.find(tag);
        if (found != nodes_.end() && found->second->observed && found->second->has_frame) {
            const Frame& frame = found->second->frame;
            frames.push_back({static_cast<double>(tag), frame[0], frame[1], frame[2], frame[3]});
        }
    }
    requested_.clear();
    measuring_surface = nullptr;
    duration_ns = static_cast<double>(
        std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now() - started).count());
}

// ----------------------------------------------------------------------
// Flattening and the mount diff
// ----------------------------------------------------------------------

bool Surface::should_flatten(const ShadowNode& node) const {
    if (!core_.flattening() || !node.component->flatten || node.parent == 0 || node.detached_root) return false;
    auto parent = nodes_.find(node.parent);
    if (parent == nodes_.end() || !parent->second->component->adopt_flattened) return false;
    if (std::find(viewport_.roots.begin(), viewport_.roots.end(), node.tag) != viewport_.roots.end()) return false;
    const Contracts& contracts = core_.contracts();
    for (const auto& [key, value] : node.props) {
        const Field* field = contracts.field(*node.component, key);
        if (field != nullptr && field->flatten) continue;
        if (!value.is_neutral()) return false;
    }
    return true;
}

int64_t Surface::mounted_parent_of(const ShadowNode& node) const {
    for (int64_t up = node.parent; up != 0;) {
        auto found = nodes_.find(up);
        if (found == nodes_.end()) return 0;
        if (!found->second->flattened) return up;
        up = found->second->parent;
    }
    return 0;
}

void Surface::desired_children(const ShadowNode& node, std::vector<int64_t>& out) const {
    for (int64_t tag : node.children) {
        auto found = nodes_.find(tag);
        if (found == nodes_.end()) continue;
        if (found->second->flattened) desired_children(*found->second, out);
        else out.push_back(tag);
    }
}

Frame Surface::mounted_frame_of(const ShadowNode& node) const {
    Frame frame = node.frame;
    for (int64_t up = node.parent; up != 0;) {
        auto found = nodes_.find(up);
        if (found == nodes_.end() || !found->second->flattened) break;
        frame[0] += found->second->frame[0];
        frame[1] += found->second->frame[1];
        up = found->second->parent;
    }
    return frame;
}

void Surface::begin_transaction(Transaction& transaction, ByteWriter& out) const {
    out.clear();
    out.u32(kMountMagic);
    out.u16(kMountFormat);
    out.u16(0);
    out.i64(id_);
    out.i64(revision_);
    out.i64(static_cast<int64_t>(transaction.id));
    out.u32(0);
}

void Surface::end_transaction(Transaction& transaction, ByteWriter& out, uint32_t count) const {
    out.patch_u32(32, count);
    transaction.op_count = count;
    transaction.bytes = out.take();
}

void Surface::write_frames(Transaction& transaction, ByteWriter& out, uint32_t& count,
                           const std::vector<int64_t>& changed) {
    (void)transaction;
    std::unordered_set<int64_t> roots(viewport_.roots.begin(), viewport_.roots.end());
    std::unordered_set<int64_t> seen;
    std::vector<int64_t> pending(changed.begin(), changed.end());
    while (!pending.empty()) {
        int64_t tag = pending.back();
        pending.pop_back();
        if (!seen.insert(tag).second) continue;
        auto found = nodes_.find(tag);
        if (found == nodes_.end()) continue;
        ShadowNode& node = *found->second;
        if (node.flattened) {
            // Moving a flattened view moves every mounted view under it.
            for (int64_t child : node.children) pending.push_back(child);
            continue;
        }
        if (!node.mounted || !node.has_frame || roots.count(tag) != 0) continue;
        Frame frame = mounted_frame_of(node);
        if (node.has_mounted_frame && same_frame(frame, node.mounted_frame)) continue;
        node.mounted_frame = frame;
        node.has_mounted_frame = true;
        out.u8(kMountFrame);
        out.i64(tag);
        out.f64(frame[0]);
        out.f64(frame[1]);
        out.f64(frame[2]);
        out.f64(frame[3]);
        ++count;
    }
}

void Surface::write_mount(Transaction& transaction, bool reset, const std::vector<int64_t>& created,
                          const std::vector<int64_t>& updated, const std::vector<int64_t>& destroyed,
                          const std::unordered_set<int64_t>& structural, const std::vector<int64_t>& frames) {
    const Contracts& contracts = core_.contracts();
    ByteWriter out;
    begin_transaction(transaction, out);
    uint32_t count = 0;
    if (reset) {
        out.u8(kMountReset);
        ++count;
        MirrorChange change;
        change.kind = MirrorChange::Kind::Reset;
        transaction.mirror.push_back(std::move(change));
    }
    for (int64_t tag : destroyed) {
        out.u8(kMountDelete);
        out.i64(tag);
        ++count;
        MirrorChange change;
        change.kind = MirrorChange::Kind::Delete;
        change.tag = tag;
        transaction.mirror.push_back(std::move(change));
    }
    // Decide which surviving views are mounted, oldest first.
    std::vector<int64_t> appeared, vanished;
    std::unordered_set<int64_t> dirty_parents(structural.begin(), structural.end());
    std::vector<int64_t> candidates = created;
    for (const auto& [tag, keys] : touched_) candidates.push_back(tag);
    for (int64_t tag : structural) {
        auto found = nodes_.find(tag);
        if (found != nodes_.end()) candidates.insert(candidates.end(), found->second->children.begin(), found->second->children.end());
    }
    std::unordered_set<int64_t> decided;
    for (int64_t tag : candidates) {
        if (!decided.insert(tag).second) continue;
        auto found = nodes_.find(tag);
        if (found == nodes_.end()) continue;
        ShadowNode& node = *found->second;
        bool flatten = should_flatten(node);
        bool was_mounted = node.mounted;
        node.flattened = flatten;
        if (flatten && was_mounted) vanished.push_back(tag);
        if (!flatten && !was_mounted) appeared.push_back(tag);
        if (flatten != !was_mounted || std::find(created.begin(), created.end(), tag) != created.end()) {
            if (node.parent != 0) dirty_parents.insert(node.parent);
            if (!flatten) dirty_parents.insert(tag);
        }
    }
    std::sort(appeared.begin(), appeared.end());
    for (int64_t tag : appeared) {
        ShadowNode& node = *nodes_.at(tag);
        node.mounted = true;
        node.has_mounted_frame = false;
        node.mounted_children.clear();
        out.u8(kMountCreate);
        out.i64(tag);
        out.str(node.component->name);
        out.value(Value::object(node.props));
        ++count;
        MirrorChange change;
        change.kind = MirrorChange::Kind::Create;
        change.tag = tag;
        change.component = node.component->id;
        change.props = node.props;
        auto patch = list_patches_.find(tag);
        if (patch != list_patches_.end()) change.list = patch->second;
        transaction.mirror.push_back(std::move(change));
    }
    std::unordered_set<int64_t> fresh(appeared.begin(), appeared.end());
    for (int64_t tag : updated) {
        auto found = nodes_.find(tag);
        if (found == nodes_.end() || !found->second->mounted || fresh.count(tag) != 0) continue;
        ShadowNode& node = *found->second;
        const std::vector<std::string>& keys = touched_[tag];
        Object changed;
        Array removed;
        for (const std::string& key : keys) {
            if (const Value* value = find_member(node.props, key)) changed.emplace_back(key, *value);
            else removed.push_back(Value::string(key));
        }
        std::vector<std::string_view> names(keys.begin(), keys.end());
        bool layout = false, recreate = false;
        contracts.changes(*node.component, names, layout, recreate);
        Object normalized = contracts.normalize(*node.component, changed, removed);
        out.u8(kMountUpdate);
        out.i64(tag);
        out.u8(recreate ? 1 : 0);
        out.value(Value::object(normalized));
        out.u32(static_cast<uint32_t>(removed.size()));
        for (const Value& name : removed) out.str(name.as_string());
        ++count;
        MirrorChange change;
        change.kind = MirrorChange::Kind::Update;
        change.tag = tag;
        change.props = std::move(normalized);
        for (const Value& name : removed) change.removed.push_back(name.as_string());
        auto patch = list_patches_.find(tag);
        if (patch != list_patches_.end()) change.list = patch->second;
        transaction.mirror.push_back(std::move(change));
    }
    // Rebuild every affected mounted child list, top-down.
    std::unordered_set<int64_t> mounted_dirty;
    for (int64_t tag : dirty_parents) {
        auto found = nodes_.find(tag);
        if (found == nodes_.end()) continue;
        int64_t target = found->second->flattened ? mounted_parent_of(*found->second) : tag;
        if (target != 0) mounted_dirty.insert(target);
    }
    for (int64_t tag : vanished) {
        auto found = nodes_.find(tag);
        if (found == nodes_.end()) continue;
        int64_t target = mounted_parent_of(*found->second);
        if (target != 0) mounted_dirty.insert(target);
    }
    std::vector<std::pair<int, int64_t>> order;
    for (int64_t tag : mounted_dirty) {
        int depth = 0;
        for (int64_t up = nodes_.at(tag)->parent; up != 0;) {
            ++depth;
            auto above = nodes_.find(up);
            up = above == nodes_.end() ? 0 : above->second->parent;
        }
        order.emplace_back(depth, tag);
    }
    std::sort(order.begin(), order.end());
    std::vector<int64_t> moved;
    for (const auto& [depth, tag] : order) {
        ShadowNode& parent = *nodes_.at(tag);
        if (!parent.mounted) continue;
        std::vector<int64_t> desired;
        desired_children(parent, desired);
        // Plan against what the platform holds right now, not the final list:
        // views that flatten away are deleted only after every insert, and a
        // child leaving for a parent processed later is still here. Indices
        // that ignored them would land moved views beside the wrong sibling.
        std::vector<int64_t> before;
        for (int64_t child : parent.mounted_children) {
            const ShadowNode* held = node(child);
            if (held != nullptr && held->mounted && held->mounted_in == tag) before.push_back(child);
        }
        for (const auto& [child, index] : plan_moves(before, desired)) {
            out.u8(kMountInsert);
            out.i64(tag);
            out.i64(child);
            out.u32(index);
            ++count;
            moved.push_back(child);
        }
        for (int64_t child : desired) nodes_.at(child)->mounted_in = tag;
        parent.mounted_children = std::move(desired);
    }
    for (int64_t tag : vanished) {
        ShadowNode& node = *nodes_.at(tag);
        node.mounted = false;
        node.has_mounted_frame = false;
        node.mounted_children.clear();
        out.u8(kMountDelete);
        out.i64(tag);
        ++count;
        MirrorChange change;
        change.kind = MirrorChange::Kind::Delete;
        change.tag = tag;
        transaction.mirror.push_back(std::move(change));
    }
    std::vector<int64_t> framed = frames;
    framed.insert(framed.end(), appeared.begin(), appeared.end());
    framed.insert(framed.end(), moved.begin(), moved.end());
    write_frames(transaction, out, count, framed);
    end_transaction(transaction, out, count);
}

std::string Surface::layout_json(const std::vector<std::array<double, 5>>& frames, double duration_ns,
                                 int visited) const {
    std::string out = "{\"application\":";
    write_json_string(application_, out);
    out += ",\"surface\":" + std::to_string(id_) + ",\"revision\":" + std::to_string(revision_) + ",\"frames\":[";
    bool first = true;
    for (const auto& frame : frames) {
        if (!first) out += ",";
        first = false;
        out += "[" + std::to_string(static_cast<int64_t>(frame[0]));
        for (int i = 1; i < 5; ++i) {
            out += ",";
            write_json(Value::number(frame[i]), out);
        }
        out += "]";
    }
    out += "],\"metrics\":{\"layout_ns\":" + std::to_string(static_cast<int64_t>(duration_ns)) +
           ",\"visited\":" + std::to_string(visited) + ",\"views\":" + std::to_string(nodes_.size()) + "}}";
    return out;
}

// ----------------------------------------------------------------------
// Commits
// ----------------------------------------------------------------------

std::string Surface::commit(const Value& envelope, Transaction& transaction) {
    auto started = std::chrono::steady_clock::now();
    std::string error, detail;
    const Value* application = envelope.find("application");
    const Value* revision = envelope.find("revision");
    auto identity = [&]() {
        std::string out = "\"application\":";
        write_json_string(application != nullptr ? application->as_string() : std::string(), out);
        out += ",\"surface\":" + std::to_string(id_);
        out += ",\"revision\":" + std::to_string(revision != nullptr ? revision->as_int() : 0);
        return out;
    };
    if (!validate(envelope, error, detail)) {
        list_patches_.clear();
        std::string out = "{\"ok\":false,\"failed\":false," + identity() + ",\"error\":";
        write_json_string(error, out);
        if (!detail.empty()) out += ",\"op\":" + detail;
        out += "}";
        return out;
    }
    auto validated = std::chrono::steady_clock::now();
    bool replacing = application->as_string() != application_;
    bool had_views = !application_.empty();
    std::vector<int64_t> created, updated, destroyed;
    std::unordered_set<int64_t> structural;
    if (replacing) {
        reset_tree();
        containers_.clear();
        application_ = application->as_string();
        failed_ = false;
    }
    touched_.clear();
    layout_dirty_tags_.clear();
    const Contracts& contracts = core_.contracts();
    for (const Value& op : envelope.find("ops")->as_array()) {
        const Array& parts = op.as_array();
        const std::string& code = parts[0].as_string();
        int64_t tag = parts[1].as_int();
        if (code == "c") {
            create_node(tag, *contracts.component(parts[2].as_string()), parts[3].as_object());
            created.push_back(tag);
        } else if (code == "u") {
            ShadowNode& node = *nodes_.at(tag);
            if (std::find(updated.begin(), updated.end(), tag) == updated.end() &&
                std::find(created.begin(), created.end(), tag) == created.end()) {
                updated.push_back(tag);
            }
            update_node(node, parts[2].as_object(), parts[3].as_array());
        } else if (code == "i") {
            ShadowNode& parent = *nodes_.at(tag);
            ShadowNode& child = *nodes_.at(parts[2].as_int());
            if (child.parent != 0) structural.insert(child.parent);
            insert_node(parent, child, parts[3].as_int());
            structural.insert(tag);
        } else {
            ShadowNode& node = *nodes_.at(tag);
            if (node.parent != 0) structural.insert(node.parent);
            if (node.mounted) destroyed.push_back(tag);
            if (int64_t parent = mounted_parent_of(node); parent != 0) structural.insert(parent);
            created.erase(std::remove(created.begin(), created.end(), tag), created.end());
            updated.erase(std::remove(updated.begin(), updated.end(), tag), updated.end());
            destroy_node(node);
        }
    }
    for (int64_t tag : destroyed) structural.erase(tag);
    revision_ = revision->as_int();
    if (const Value* request = envelope.find("layout")) {
        viewport_.roots.clear();
        for (const Value& root : request->find("roots")->as_array()) viewport_.roots.push_back(root.as_int());
        viewport_.width = static_cast<float>(request->find("width")->as_double());
        viewport_.height = static_cast<float>(request->find("height")->as_double());
        const Value* selective = request->find("selective");
        viewport_.selective = selective == nullptr || selective->as_bool();
    }
    std::vector<std::array<double, 5>> frames;
    double layout_ns = 0;
    int visited = 0;
    compute_layout(frames, layout_ns, visited);
    std::vector<int64_t> changed(layout_dirty_tags_.begin(), layout_dirty_tags_.end());
    write_mount(transaction, replacing && had_views, created, updated, destroyed, structural, changed);
    transaction.surface = id_;
    transaction.application = application_;
    transaction.revision = revision_;
    list_patches_.clear();
    touched_.clear();
    auto finished = std::chrono::steady_clock::now();
    auto ns = [](auto from, auto to) {
        return std::to_string(std::chrono::duration_cast<std::chrono::nanoseconds>(to - from).count());
    };
    std::string out = "{\"ok\":true," + identity() + ",\"metrics\":{\"validate_ns\":" + ns(started, validated) +
                      ",\"commit_ns\":" + ns(started, finished) + ",\"operations\":" +
                      std::to_string(transaction.op_count) + "}";
    if (envelope.find("layout") != nullptr) out += ",\"layout\":" + layout_json(frames, layout_ns, visited);
    out += "}";
    return out;
}

std::string Surface::layout(const LayoutRequest& request, Transaction& transaction) {
    viewport_ = request;
    layout_dirty_tags_.clear();
    std::vector<std::array<double, 5>> frames;
    double layout_ns = 0;
    int visited = 0;
    compute_layout(frames, layout_ns, visited);
    std::vector<int64_t> changed(layout_dirty_tags_.begin(), layout_dirty_tags_.end());
    if (!changed.empty()) {
        ByteWriter out;
        begin_transaction(transaction, out);
        uint32_t count = 0;
        write_frames(transaction, out, count, changed);
        end_transaction(transaction, out, count);
        transaction.surface = id_;
        transaction.application = application_;
        transaction.revision = revision_;
    }
    return layout_json(frames, layout_ns, visited);
}

bool Surface::relayout(Transaction& transaction, std::string& layout_message) {
    if (!viewport_.valid() || application_.empty()) return false;
    layout_dirty_tags_.clear();
    std::vector<std::array<double, 5>> frames;
    double layout_ns = 0;
    int visited = 0;
    compute_layout(frames, layout_ns, visited);
    if (layout_dirty_tags_.empty()) return false;
    std::vector<int64_t> changed(layout_dirty_tags_.begin(), layout_dirty_tags_.end());
    ByteWriter out;
    begin_transaction(transaction, out);
    uint32_t count = 0;
    write_frames(transaction, out, count, changed);
    end_transaction(transaction, out, count);
    transaction.surface = id_;
    transaction.application = application_;
    transaction.revision = revision_;
    if (!frames.empty()) layout_message = layout_json(frames, layout_ns, visited);
    return count > 0 || !frames.empty();
}

// ----------------------------------------------------------------------
// Reads
// ----------------------------------------------------------------------

std::string Surface::measure(int64_t tag) const {
    const ShadowNode* target = node(tag);
    if (target == nullptr || !target->has_frame) return "null";
    Frame window = target->frame;
    const ShadowNode* current = target;
    while (true) {
        if (current->detached_root || current->parent == 0 || current->component->portal) {
            Frame box = container_for(*current);
            window[0] += box[0];
            window[1] += box[1];
            break;
        }
        const ShadowNode* parent = node(current->parent);
        if (parent == nullptr) break;
        window[0] += parent->frame[0];
        window[1] += parent->frame[1];
        current = parent;
    }
    std::string out = "{\"frame\":[";
    for (int i = 0; i < 4; ++i) {
        if (i) out += ",";
        write_json(Value::number(target->frame[static_cast<size_t>(i)]), out);
    }
    out += "],\"window\":[";
    for (int i = 0; i < 4; ++i) {
        if (i) out += ",";
        write_json(Value::number(window[static_cast<size_t>(i)]), out);
    }
    out += "],\"mounted\":";
    out += target->mounted ? "true" : "false";
    out += "}";
    return out;
}

std::string Surface::inspect(double x, double y) const {
    const ShadowNode* best = nullptr;
    std::function<void(const ShadowNode&, double, double)> visit = [&](const ShadowNode& current, double ox,
                                                                       double oy) {
        double left = ox + current.frame[0], top = oy + current.frame[1];
        if (!current.has_frame || x < left || y < top || x > left + current.frame[2] || y > top + current.frame[3]) {
            return;
        }
        best = &current;
        for (int64_t tag : current.children) {
            const ShadowNode* child = node(tag);
            if (child != nullptr && child->attached) visit(*child, left, top);
        }
    };
    for (int64_t tag : viewport_.roots) {
        if (const ShadowNode* root = node(tag)) visit(*root, 0, 0);
    }
    if (best == nullptr) return "null";
    std::string out = "{\"tag\":" + std::to_string(best->tag) + ",\"component\":";
    write_json_string(best->component->name, out);
    out += ",\"flattened\":";
    out += best->flattened ? "true" : "false";
    out += "}";
    return out;
}

}  // namespace pn
