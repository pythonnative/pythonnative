#include "core.h"

#include <cstdlib>
#include <cstring>
#include <exception>

namespace {

char* copy(const std::string& text) {
    char* out = static_cast<char*>(std::malloc(text.size() + 1));
    if (out == nullptr) return nullptr;
    std::memcpy(out, text.c_str(), text.size() + 1);
    return out;
}

std::string error_json(const std::string& message) {
    std::string out = "{\"ok\":false,\"failed\":false,\"error\":";
    pn::write_json_string(message, out);
    out += "}";
    return out;
}

}  // namespace

namespace pn {

Core& shared_core() {
    static Core* core = new Core();  // never destroyed: platforms may call during teardown
    return *core;
}

Core::Core() : animator_(*this) {
    animator_.set_lookup([this](int64_t surface, int64_t tag, const std::string& prop) -> const Value* {
        auto found = mounts_.find(surface);
        return found == mounts_.end() ? nullptr : found->second->prop(tag, prop);
    });
}

void Core::set_platform(const pn_platform& platform) {
    std::lock_guard<std::mutex> lock(platform_mutex_);
    platform_ = platform;
    has_platform_ = true;
}

std::string Core::load_contracts(const char* document, const char* platform) {
    Value parsed;
    std::string error;
    if (document == nullptr || !parse_json(document, parsed, error)) return "invalid contract JSON: " + error;
    std::lock_guard<std::mutex> lock(commit_mutex_);
    if (!contracts_.load(parsed, platform != nullptr ? platform : "host", error)) return error;
    publish_contracts(std::make_shared<const Contracts>(contracts_));
    return std::string();
}

void Core::publish_contracts(std::shared_ptr<const Contracts> contracts) {
    std::lock_guard<std::mutex> lock(published_mutex_);
    published_contracts_ = std::move(contracts);
}

std::shared_ptr<const Contracts> Core::published_contracts() const {
    std::lock_guard<std::mutex> lock(published_mutex_);
    return published_contracts_;
}

std::string Core::fingerprint() {
    std::lock_guard<std::mutex> lock(commit_mutex_);
    return contracts_.fingerprint();
}

void Core::reset() {
    {
        std::lock_guard<std::mutex> lock(commit_mutex_);
        surfaces_.clear();
        contracts_.clear();
        publish_contracts(std::make_shared<const Contracts>());
    }
    {
        std::lock_guard<std::mutex> lock(queue_mutex_);
        queue_.clear();
        mounting_.reset();
    }
    {
        std::lock_guard<std::mutex> lock(requests_mutex_);
        requests_.clear();
    }
    mounts_.clear();
    animator_.reset();
    flattening_ = true;
}

Surface& Core::surface(int64_t id) {
    auto found = surfaces_.find(id);
    if (found == surfaces_.end()) found = surfaces_.emplace(id, std::make_unique<Surface>(*this, id)).first;
    return *found->second;
}

void Core::enqueue(Transaction transaction) {
    {
        std::lock_guard<std::mutex> lock(queue_mutex_);
        queue_.push_back(std::move(transaction));
    }
    pn_platform platform;
    {
        std::lock_guard<std::mutex> lock(platform_mutex_);
        if (!has_platform_ || platform_.schedule_mount == nullptr) return;
        platform = platform_;
    }
    platform.schedule_mount(platform.context);
}

void Core::post(std::function<void(Core&)> request) {
    {
        std::lock_guard<std::mutex> lock(requests_mutex_);
        requests_.push_back(std::move(request));
    }
    pn_platform platform;
    {
        std::lock_guard<std::mutex> lock(platform_mutex_);
        if (!has_platform_ || platform_.schedule_work == nullptr) return;
        platform = platform_;
    }
    platform.schedule_work(platform.context);
}

// ----------------------------------------------------------------------
// Python side
// ----------------------------------------------------------------------

std::string Core::commit(const char* text) {
    Value envelope;
    std::string error;
    if (text == nullptr || !parse_json(text, envelope, error)) return error_json("invalid commit JSON: " + error);
    const Value* id = envelope.find("surface");
    if (id == nullptr || !id->is_integer() || id->as_int() <= 0) return error_json("invalid surface identity");
    Transaction transaction;
    std::string ack;
    {
        std::lock_guard<std::mutex> lock(commit_mutex_);
        if (contracts_.component_count() == 0) return error_json("load the component contracts before committing");
        Surface& target = surface(id->as_int());
        transaction.id = next_transaction_id();
        ack = target.commit(envelope, transaction);
        if (!transaction.bytes.empty()) enqueue(std::move(transaction));
    }
    return ack;
}

std::string Core::layout(const char* text) {
    Value request;
    std::string error;
    if (text == nullptr || !parse_json(text, request, error)) return error_json("invalid layout JSON: " + error);
    LayoutRequest layout;
    const Value* id = request.find("surface");
    for (const Value& root : request.find("roots") ? request.find("roots")->as_array() : Array()) {
        layout.roots.push_back(root.as_int());
    }
    layout.width = request.find("width") ? static_cast<float>(request.find("width")->as_double()) : 0;
    layout.height = request.find("height") ? static_cast<float>(request.find("height")->as_double()) : 0;
    layout.selective = request.find("selective") == nullptr || request.find("selective")->as_bool();
    std::lock_guard<std::mutex> lock(commit_mutex_);
    Surface& target = surface(id != nullptr ? id->as_int() : 1);
    Transaction transaction;
    transaction.id = next_transaction_id();
    std::string frames = target.layout(layout, transaction);
    if (!transaction.bytes.empty()) enqueue(std::move(transaction));
    return "{\"ok\":true,\"value\":" + frames + "}";
}

std::string Core::command(int64_t surface_id, int64_t tag, const char* name, const char* arguments, int64_t call_id) {
    Value parsed = Value::object({});
    std::string error;
    if (arguments != nullptr && *arguments && !parse_json(arguments, parsed, error)) {
        return error_json("invalid command arguments: " + error);
    }
    std::lock_guard<std::mutex> lock(commit_mutex_);
    Surface& target = surface(surface_id);
    const ShadowNode* node = target.node(tag);
    if (node == nullptr) return error_json("command " + std::string(name ? name : "") + " addressed stale view " + std::to_string(tag));
    if (!node->mounted) {
        return error_json("view #" + std::to_string(tag) + " isn't mounted (it only affects layout)");
    }
    if (!contracts_.validate_command(*node->component, name != nullptr ? name : "", parsed, error)) return error_json(error);
    Transaction transaction;
    transaction.id = next_transaction_id();
    transaction.surface = surface_id;
    transaction.application = target.application();
    transaction.revision = target.revision();
    ByteWriter out;
    out.u32(0x544D4E50);
    out.u16(1);
    out.u16(0);
    out.i64(surface_id);
    out.i64(target.revision());
    out.i64(static_cast<int64_t>(transaction.id));
    out.u32(1);
    out.u8(kMountCommand);
    out.i64(tag);
    out.str(name != nullptr ? name : "");
    out.value(parsed);
    out.i64(call_id);
    transaction.op_count = 1;
    transaction.bytes = out.take();
    enqueue(std::move(transaction));
    return "{\"ok\":true,\"queued\":true}";
}

std::string Core::animate(int64_t surface_id, int64_t tag, const char* text) {
    Value request;
    std::string error;
    if (text == nullptr || !parse_json(text, request, error)) return error_json("invalid animation JSON: " + error);
    if (!Animator::valid_request(request, error)) return error_json(error);
    std::lock_guard<std::mutex> lock(commit_mutex_);
    Surface& target = surface(surface_id);
    Transaction transaction;
    transaction.id = next_transaction_id();
    transaction.surface = surface_id;
    transaction.application = target.application();
    transaction.revision = target.revision();
    ByteWriter out;
    out.u32(0x544D4E50);
    out.u16(1);
    out.u16(0);
    out.i64(surface_id);
    out.i64(target.revision());
    out.i64(static_cast<int64_t>(transaction.id));
    out.u32(0);
    transaction.bytes = out.take();
    transaction.animations.push_back(Value::object({{"tag", Value::integer(tag)}, {"request", request}}));
    enqueue(std::move(transaction));
    return "{\"ok\":true}";
}

std::string Core::measure(int64_t surface_id, int64_t tag) {
    std::lock_guard<std::mutex> lock(commit_mutex_);
    return surface(surface_id).measure(tag);
}

std::string Core::inspect(int64_t surface_id, double x, double y) {
    std::lock_guard<std::mutex> lock(commit_mutex_);
    return surface(surface_id).inspect(x, y);
}

bool Core::validate_module(const char* module, const char* method, const char* arguments) {
    Value parsed = Value::object({});
    std::string error;
    if (arguments != nullptr && *arguments && !parse_json(arguments, parsed, error)) return false;
    std::shared_ptr<const Contracts> contracts = published_contracts();
    return contracts->validate_module(module != nullptr ? module : "", method != nullptr ? method : "", parsed);
}

void Core::work() {
    std::vector<std::function<void(Core&)>> requests;
    {
        std::lock_guard<std::mutex> lock(requests_mutex_);
        requests.swap(requests_);
    }
    // Messages go out after the lock is released: Python may answer one
    // by committing or reading the tree.
    std::vector<std::pair<int64_t, std::string>> messages;
    {
        std::lock_guard<std::mutex> lock(commit_mutex_);
        for (auto& request : requests) request(*this);
        for (auto& [id, target] : surfaces_) {
            if (target->failed()) continue;
            Transaction transaction;
            transaction.id = next_transaction_id();
            std::string message;
            if (target->relayout(transaction, message)) {
                if (!transaction.bytes.empty() && transaction.op_count > 0) enqueue(std::move(transaction));
                if (!message.empty()) messages.emplace_back(id, std::move(message));
            }
        }
    }
    for (const auto& [id, message] : messages) emit("layout", id, 0, "", message);
}

// ----------------------------------------------------------------------
// UI thread
// ----------------------------------------------------------------------

MountState* Core::mount_state(int64_t surface_id) {
    auto found = mounts_.find(surface_id);
    if (found == mounts_.end()) {
        found = mounts_.emplace(surface_id, std::make_unique<MountState>(*this, animator_, surface_id)).first;
    }
    return found->second.get();
}

bool Core::mount_next(pn_bytes& bytes, uint64_t& id) {
    Transaction* next = nullptr;
    {
        std::lock_guard<std::mutex> lock(queue_mutex_);
        if (mounting_ || queue_.empty()) return false;
        mounting_ = std::make_unique<Transaction>(std::move(queue_.front()));
        queue_.pop_front();
        next = mounting_.get();
    }
    mount_state(next->surface)->begin(*next);
    bytes = {next->bytes.data(), next->bytes.size()};
    id = next->id;
    return true;
}

void Core::mount_finished(uint64_t id, const char* error) {
    std::unique_ptr<Transaction> done;
    {
        std::lock_guard<std::mutex> lock(queue_mutex_);
        if (!mounting_ || mounting_->id != id) return;
        done = std::move(mounting_);
    }
    MountState* state = mount_state(done->surface);
    state->finish(*done);
    for (const Value& entry : done->animations) {
        animator_.handle(done->surface, entry.find("tag")->as_int(), *entry.find("request"));
    }
    if (error != nullptr) {
        int64_t surface_id = done->surface;
        post([surface_id](Core& core) { core.surface(surface_id).mark_failed(); });
        std::string payload = "{\"surface\":" + std::to_string(surface_id) + ",\"error\":";
        write_json_string(error, payload);
        payload += "}";
        emit("host", surface_id, 0, "surface_failed", payload);
    }
}

bool Core::is_mounted(int64_t surface_id, int64_t tag) {
    return mount_state(surface_id)->is_mounted(tag);
}

void Core::report_container(int64_t surface_id, int64_t tag, ContainerSize size) {
    post([=](Core& core) { core.surface(surface_id).report_container(tag, size); });
}

void Core::report_intrinsic(int64_t surface_id, int64_t tag, float width, float height) {
    post([=](Core& core) { core.surface(surface_id).report_intrinsic(tag, width, height); });
}

void Core::invalidate(int64_t surface_id, int64_t tag) {
    post([=](Core& core) { core.surface(surface_id).invalidate(tag); });
}

void Core::invalidate_measurements() {
    post([](Core& core) {
        for (auto& [id, target] : core.surfaces_) target->invalidate_measurements();
    });
}

bool Core::animation_frame(double timestamp_ms) {
    return animator_.frame(timestamp_ms);
}

bool Core::take_writes(pn_bytes& writes) {
    static thread_local std::vector<uint8_t> buffer;
    if (!animator_.take_writes(buffer)) {
        writes = {nullptr, 0};
        return false;
    }
    writes = {buffer.data(), buffer.size()};
    return true;
}

void Core::set_reduce_motion(bool enabled) {
    animator_.set_reduce_motion(enabled);
}

// ----------------------------------------------------------------------
// Platform callbacks
// ----------------------------------------------------------------------

pn_size Core::platform_measure(const pn_measure_request& request) {
    pn_platform platform;
    {
        std::lock_guard<std::mutex> lock(platform_mutex_);
        if (!has_platform_ || platform_.measure == nullptr) return {0, 0};
        platform = platform_;
    }
    pn_size size{0, 0};
    platform.measure(platform.context, &request, &size);
    return size;
}

float Core::platform_baseline(int64_t surface_id, int64_t tag, float width, float height) {
    pn_platform platform;
    {
        std::lock_guard<std::mutex> lock(platform_mutex_);
        if (!has_platform_ || platform_.baseline == nullptr) return height;
        platform = platform_;
    }
    return platform.baseline(platform.context, surface_id, tag, width, height);
}

void Core::emit(const char* kind, int64_t surface, int64_t tag, const std::string& name, const std::string& payload) {
    pn_platform platform;
    {
        std::lock_guard<std::mutex> lock(platform_mutex_);
        if (!has_platform_ || platform_.emit == nullptr) return;
        platform = platform_;
    }
    platform.emit(platform.context, kind, surface, tag, name.c_str(), payload.c_str());
}

void Core::request_frames() {
    pn_platform platform;
    {
        std::lock_guard<std::mutex> lock(platform_mutex_);
        if (!has_platform_ || platform_.request_frames == nullptr) return;
        platform = platform_;
    }
    platform.request_frames(platform.context);
}

}  // namespace pn

// ----------------------------------------------------------------------
// The C ABI
// ----------------------------------------------------------------------

using pn::shared_core;

namespace {

pn::Core& unwrap(pn_core* core) {
    return core != nullptr ? *reinterpret_cast<pn::Core*>(core) : shared_core();
}

template <typename Fn>
char* guarded(Fn&& body) {
    try {
        return copy(body());
    } catch (const std::exception& error) {
        return copy(error_json(std::string("renderer core error: ") + error.what()));
    } catch (...) {
        return copy(error_json("renderer core error"));
    }
}

template <typename Fn>
void guarded_void(Fn&& body) {
    try {
        body();
    } catch (...) {
    }
}

}  // namespace

extern "C" {

pn_core* pn_core_shared(void) {
    return reinterpret_cast<pn_core*>(&shared_core());
}

int32_t pn_core_protocol_version(void) {
    return PN_CORE_PROTOCOL_VERSION;
}

void pn_core_set_platform(pn_core* core, const pn_platform* platform) {
    if (platform != nullptr) unwrap(core).set_platform(*platform);
}

char* pn_core_load_contracts(pn_core* core, const char* document, const char* platform) {
    try {
        std::string error = unwrap(core).load_contracts(document, platform);
        return error.empty() ? nullptr : copy(error);
    } catch (const std::exception& error) {
        return copy(error.what());
    }
}

char* pn_core_contract_fingerprint(pn_core* core) {
    return guarded([&] { return unwrap(core).fingerprint(); });
}

void pn_core_set_flattening(pn_core* core, int32_t enabled) {
    unwrap(core).set_flattening(enabled != 0);
}

void pn_core_reset(pn_core* core) {
    guarded_void([&] { unwrap(core).reset(); });
}

void pn_core_free(void* pointer) {
    std::free(pointer);
}

char* pn_core_commit(pn_core* core, const char* envelope) {
    return guarded([&] { return unwrap(core).commit(envelope); });
}

char* pn_core_layout(pn_core* core, const char* request) {
    return guarded([&] { return unwrap(core).layout(request); });
}

char* pn_core_command(pn_core* core, int64_t surface, int64_t tag, const char* name, const char* arguments,
                      int64_t call_id) {
    return guarded([&] { return unwrap(core).command(surface, tag, name, arguments, call_id); });
}

char* pn_core_animate(pn_core* core, int64_t surface, int64_t tag, const char* request) {
    return guarded([&] { return unwrap(core).animate(surface, tag, request); });
}

char* pn_core_measure(pn_core* core, int64_t surface, int64_t tag) {
    return guarded([&] { return unwrap(core).measure(surface, tag); });
}

char* pn_core_inspect(pn_core* core, int64_t surface, double x, double y) {
    return guarded([&] { return unwrap(core).inspect(surface, x, y); });
}

int32_t pn_core_validate_module(pn_core* core, const char* module, const char* method, const char* arguments) {
    try {
        return unwrap(core).validate_module(module, method, arguments) ? 1 : 0;
    } catch (...) {
        return 0;
    }
}

int32_t pn_core_check_value(const char* schema, const char* value) {
    try {
        pn::Value parsed_schema, parsed_value;
        std::string error;
        if (schema == nullptr || value == nullptr || !pn::parse_json(schema, parsed_schema, error) ||
            !pn::parse_json(value, parsed_value, error)) {
            return 0;
        }
        pn::Contracts contracts;
        int index = contracts.compile_schema(parsed_schema);
        return contracts.matches(index, parsed_value) ? 1 : 0;
    } catch (...) {
        return 0;
    }
}

void pn_core_work(pn_core* core) {
    guarded_void([&] { unwrap(core).work(); });
}

int32_t pn_core_mount_next(pn_core* core, pn_bytes* transaction, uint64_t* id) {
    if (transaction == nullptr || id == nullptr) return 0;
    try {
        return unwrap(core).mount_next(*transaction, *id) ? 1 : 0;
    } catch (...) {
        return 0;
    }
}

void pn_core_mount_finished(pn_core* core, uint64_t id, const char* error) {
    guarded_void([&] { unwrap(core).mount_finished(id, error); });
}

int32_t pn_core_is_mounted(pn_core* core, int64_t surface, int64_t tag) {
    try {
        return unwrap(core).is_mounted(surface, tag) ? 1 : 0;
    } catch (...) {
        return 0;
    }
}

void pn_core_report_container(pn_core* core, int64_t surface, int64_t tag, float x, float y, float width,
                              float height) {
    guarded_void([&] { unwrap(core).report_container(surface, tag, {x, y, width, height}); });
}

void pn_core_report_intrinsic(pn_core* core, int64_t surface, int64_t tag, float width, float height) {
    guarded_void([&] { unwrap(core).report_intrinsic(surface, tag, width, height); });
}

void pn_core_invalidate(pn_core* core, int64_t surface, int64_t tag) {
    guarded_void([&] { unwrap(core).invalidate(surface, tag); });
}

void pn_core_invalidate_measurements(pn_core* core) {
    guarded_void([&] { unwrap(core).invalidate_measurements(); });
}

void pn_core_event(pn_core* core, int64_t surface, int64_t tag, const char* name, const char* arguments,
                   int64_t edit_revision) {
    guarded_void([&] {
        unwrap(core).mount_state(surface)->event(tag, name != nullptr ? name : "", arguments, edit_revision);
    });
}

int32_t pn_core_animation_frame(pn_core* core, double timestamp_ms) {
    try {
        return unwrap(core).animation_frame(timestamp_ms) ? 1 : 0;
    } catch (...) {
        return 0;
    }
}

int32_t pn_core_take_writes(pn_core* core, pn_bytes* writes) {
    if (writes == nullptr) return 0;
    try {
        return unwrap(core).take_writes(*writes) ? 1 : 0;
    } catch (...) {
        return 0;
    }
}

void pn_core_set_reduce_motion(pn_core* core, int32_t enabled) {
    unwrap(core).set_reduce_motion(enabled != 0);
}

int32_t pn_core_pointer(pn_core* core, int64_t surface, int64_t tag, const pn_pointer_event* events, size_t count) {
    try {
        return unwrap(core).mount_state(surface)->pointer(tag, events, count) ? 1 : 0;
    } catch (...) {
        return 0;
    }
}

double pn_core_gesture_deadline(pn_core* core, int64_t surface, int64_t tag) {
    try {
        return unwrap(core).mount_state(surface)->gesture_deadline(tag);
    } catch (...) {
        return -1;
    }
}

void pn_core_gesture_poll(pn_core* core, int64_t surface, int64_t tag, double time) {
    guarded_void([&] { unwrap(core).mount_state(surface)->gesture_poll(tag, time); });
}

int32_t pn_core_has_gestures(pn_core* core, int64_t surface, int64_t tag) {
    try {
        return unwrap(core).mount_state(surface)->has_gestures(tag) ? 1 : 0;
    } catch (...) {
        return 0;
    }
}

char* pn_core_list_apply(pn_core* core, int64_t surface, int64_t tag) {
    try {
        std::string edits = unwrap(core).mount_state(surface)->list_apply(tag);
        return edits.empty() ? nullptr : copy(edits);
    } catch (...) {
        return nullptr;
    }
}

namespace {

const pn::ListStore* list_of(pn_core* core, int64_t surface, int64_t tag) {
    return unwrap(core).mount_state(surface)->list(tag);
}

}  // namespace

int64_t pn_core_list_count(pn_core* core, int64_t surface, int64_t tag) {
    const pn::ListStore* list = list_of(core, surface, tag);
    return list != nullptr ? static_cast<int64_t>(list->keys().size()) : 0;
}

int64_t pn_core_list_revision(pn_core* core, int64_t surface, int64_t tag) {
    const pn::ListStore* list = list_of(core, surface, tag);
    return list != nullptr ? list->revision() : 0;
}

char* pn_core_list_key(pn_core* core, int64_t surface, int64_t tag, int64_t index) {
    const pn::ListStore* list = list_of(core, surface, tag);
    const pn::ListRow* row = list != nullptr ? list->row(index) : nullptr;
    return row != nullptr ? copy(row->key) : nullptr;
}

int64_t pn_core_list_index(pn_core* core, int64_t surface, int64_t tag, const char* key) {
    const pn::ListStore* list = list_of(core, surface, tag);
    return list != nullptr && key != nullptr ? list->index_of(key) : -1;
}

double pn_core_list_extent(pn_core* core, int64_t surface, int64_t tag, int64_t index) {
    const pn::ListStore* list = list_of(core, surface, tag);
    const pn::ListRow* row = list != nullptr ? list->row(index) : nullptr;
    return row != nullptr ? row->extent : 0;
}

int32_t pn_core_list_sticky(pn_core* core, int64_t surface, int64_t tag, int64_t index) {
    const pn::ListStore* list = list_of(core, surface, tag);
    const pn::ListRow* row = list != nullptr ? list->row(index) : nullptr;
    return row != nullptr && row->sticky ? 1 : 0;
}

int64_t pn_core_list_row_revision(pn_core* core, int64_t surface, int64_t tag, int64_t index) {
    const pn::ListStore* list = list_of(core, surface, tag);
    const pn::ListRow* row = list != nullptr ? list->row(index) : nullptr;
    return row != nullptr ? row->revision : 0;
}

int64_t pn_core_list_sticky_at(pn_core* core, int64_t surface, int64_t tag, int64_t index) {
    const pn::ListStore* list = list_of(core, surface, tag);
    return list != nullptr ? list->sticky_at(index) : -1;
}

}  // extern "C"
