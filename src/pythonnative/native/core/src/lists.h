// Revisioned keyed list datasets (`VirtualList`'s `dataset` prop).
//
// The commit side validates a patch against its copy; the mount side keeps
// its own copy for the platform's data source and publishes each patch when
// the list's update reaches the UI thread.
#pragma once

#include <cstdint>
#include <memory>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

#include "value.h"

namespace pn {

struct ListRow {
    std::string key;
    int64_t revision = 0;
    double extent = 0;
    bool sticky = false;
    bool operator==(const ListRow& other) const {
        return key == other.key && revision == other.revision && extent == other.extent && sticky == other.sticky;
    }
};

/// One structural change, in the order applied: `code` is "reset", "i", "d", or "m".
struct ListEdit {
    char code = 'r';
    int64_t from = 0;
    int64_t to = 0;
};

/// A validated patch, ready to publish onto the store it was prepared against.
struct ListPatch {
    int64_t base = 0;
    int64_t revision = 0;
    bool reset = false;
    bool reorders = false;  // `order` replaces the key order
    std::vector<std::string> order;
    std::unordered_map<std::string, ListRow> changed;
    std::unordered_set<std::string> deleted;
    std::vector<ListEdit> edits;
};

class ListStore {
public:
    /// Validate `packet` (`{"base", "revision", "changes"}`) against this store.
    bool prepare(const Value& packet, ListPatch& patch, std::string& error) const;
    /// Apply a patch prepared against the current revision.
    void publish(const ListPatch& patch);

    int64_t revision() const { return revision_; }
    const std::vector<std::string>& keys() const { return keys_; }
    const ListRow* row(int64_t index) const;
    int64_t index_of(const std::string& key) const;
    /// The sticky row index at or before `index`, or -1.
    int64_t sticky_at(int64_t index) const;

private:
    int64_t revision_ = 0;
    std::vector<std::string> keys_;
    std::unordered_map<std::string, ListRow> rows_;
    std::unordered_map<std::string, int64_t> indices_;
    std::vector<int64_t> sticky_;
};

/// Describe a patch's edits as JSON for the platform's list update.
std::string edits_json(const ListPatch& patch);

}  // namespace pn
