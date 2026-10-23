// The process-wide core: contracts, surfaces, the mount queue, and the
// platform callbacks behind `include/pn_core.h`.
#pragma once

#include <atomic>
#include <deque>
#include <functional>
#include <map>
#include <memory>
#include <mutex>
#include <string>
#include <unordered_map>

#include "../include/pn_core.h"
#include "contracts.h"
#include "mount.h"
#include "shadow.h"

namespace pn {

class Core {
public:
    Core();

    // Setup.
    void set_platform(const pn_platform& platform);
    std::string load_contracts(const char* document, const char* platform);
    std::string fingerprint();
    void set_flattening(bool enabled) { flattening_ = enabled; }
    bool flattening() const { return flattening_; }
    void reset();

    // Python side.
    std::string commit(const char* envelope);
    std::string layout(const char* request);
    std::string command(int64_t surface, int64_t tag, const char* name, const char* arguments, int64_t call_id);
    std::string animate(int64_t surface, int64_t tag, const char* request);
    std::string measure(int64_t surface, int64_t tag);
    std::string inspect(int64_t surface, double x, double y);
    bool validate_module(const char* module, const char* method, const char* arguments);
    void work();

    // UI thread.
    bool mount_next(pn_bytes& transaction, uint64_t& id);
    void mount_finished(uint64_t id, const char* error);
    bool is_mounted(int64_t surface, int64_t tag);
    void report_container(int64_t surface, int64_t tag, ContainerSize size);
    void report_intrinsic(int64_t surface, int64_t tag, float width, float height);
    void invalidate(int64_t surface, int64_t tag);
    void invalidate_measurements();
    MountState* mount_state(int64_t surface);
    bool animation_frame(double timestamp_ms);
    bool take_writes(pn_bytes& writes);
    void set_reduce_motion(bool enabled);

    // Used by surfaces and mount state.
    const Contracts& contracts() const { return contracts_; }
    pn_size platform_measure(const pn_measure_request& request);
    float platform_baseline(int64_t surface, int64_t tag, float width, float height);
    void emit(const char* kind, int64_t surface, int64_t tag, const std::string& name, const std::string& payload);
    void request_frames();
    uint64_t next_transaction_id() { return ++transaction_ids_; }

private:
    Surface& surface(int64_t id);  // requires commit_mutex_
    void enqueue(Transaction transaction);
    void post(std::function<void(Core&)> request);

    std::mutex commit_mutex_;
    Contracts contracts_;
    // An immutable copy for module calls, which arrive on the UI thread
    // and may not take the commit lock. Its mutex only guards swapping the
    // pointer, never compilation or validation.
    std::shared_ptr<const Contracts> published_contracts_ = std::make_shared<const Contracts>();
    mutable std::mutex published_mutex_;
    void publish_contracts(std::shared_ptr<const Contracts> contracts);
    std::shared_ptr<const Contracts> published_contracts() const;
    std::map<int64_t, std::unique_ptr<Surface>> surfaces_;
    std::atomic<bool> flattening_{true};

    // Platform callbacks; copied once at setup.
    std::mutex platform_mutex_;
    pn_platform platform_{};
    bool has_platform_ = false;

    // The queue between the commit side and the UI thread.
    std::mutex queue_mutex_;
    std::deque<Transaction> queue_;
    std::unique_ptr<Transaction> mounting_;
    std::atomic<uint64_t> transaction_ids_{0};

    // Requests the UI thread posts for `work`.
    std::mutex requests_mutex_;
    std::vector<std::function<void(Core&)>> requests_;

    // UI-thread state; touched only from the UI thread.
    std::map<int64_t, std::unique_ptr<MountState>> mounts_;
    Animator animator_;
};

Core& shared_core();

}  // namespace pn
