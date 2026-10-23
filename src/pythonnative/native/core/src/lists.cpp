#include "lists.h"

#include <algorithm>
#include <cmath>

namespace pn {

namespace {

bool row_from(const Value& raw, ListRow& row) {
    const Array& values = raw.as_array();
    if (!raw.is_array() || values.size() != 4) return false;
    if (!values[0].is_string() || values[0].as_string().empty()) return false;
    if (!values[1].is_integer() || values[1].as_int() < 1) return false;
    if (!values[2].is_number() || !(values[2].as_double() > 0) || !std::isfinite(values[2].as_double())) return false;
    if (!values[3].is_bool()) return false;
    row = {values[0].as_string(), values[1].as_int(), values[2].as_double(), values[3].as_bool()};
    return true;
}

}  // namespace

bool ListStore::prepare(const Value& packet, ListPatch& patch, std::string& error) const {
    auto invalid = [&](const char* message) {
        error = message;
        return false;
    };
    const Object& members = packet.as_object();
    if (!packet.is_object() || members.size() != 3) return invalid("invalid list packet");
    const Value* base = packet.find("base");
    const Value* revision = packet.find("revision");
    const Value* changes = packet.find("changes");
    if (base == nullptr || revision == nullptr || changes == nullptr || !changes->is_array()) {
        return invalid("invalid list packet");
    }
    if (!base->is_integer() || base->as_int() != revision_ || !revision->is_integer() ||
        revision->as_int() != revision_ + 1) {
        return invalid("stale list revision");
    }
    patch = ListPatch();
    patch.base = revision_;
    patch.revision = revision->as_int();
    auto exists = [&](const std::string& key) {
        if (patch.deleted.count(key) != 0) return false;
        return patch.changed.count(key) != 0 || (!patch.reset && rows_.count(key) != 0);
    };
    auto order = [&]() -> std::vector<std::string>& {
        if (!patch.reorders) {
            patch.reorders = true;
            patch.order = keys_;
        }
        return patch.order;
    };
    for (const Value& change : changes->as_array()) {
        const Array& parts = change.as_array();
        if (!change.is_array() || parts.empty() || !parts[0].is_string()) return invalid("invalid list change");
        const std::string& code = parts[0].as_string();
        if (code == "reset") {
            if (parts.size() != 2 || !parts[1].is_array() || patch.reset || !patch.changed.empty() ||
                !patch.edits.empty() || !patch.deleted.empty()) {
                return invalid("list reset must be the first change");
            }
            patch.reset = true;
            patch.reorders = true;
            patch.order.clear();
            for (const Value& raw : parts[1].as_array()) {
                ListRow row;
                if (!row_from(raw, row)) return invalid("invalid list row");
                if (patch.changed.count(row.key) != 0) return invalid("list keys must be unique");
                patch.order.push_back(row.key);
                patch.changed.emplace(row.key, row);
            }
            patch.edits.push_back({'r', 0, 0});
        } else if (code == "i") {
            ListRow row;
            if (parts.size() != 3 || !parts[1].is_integer() || !row_from(parts[2], row)) {
                return invalid("invalid list insertion");
            }
            int64_t index = parts[1].as_int();
            std::vector<std::string>& keys = order();
            if (index < 0 || index > static_cast<int64_t>(keys.size()) || exists(row.key)) {
                return invalid("invalid list insertion");
            }
            keys.insert(keys.begin() + index, row.key);
            patch.deleted.erase(row.key);
            patch.changed[row.key] = row;
            patch.edits.push_back({'i', index, index});
        } else if (code == "u") {
            ListRow row;
            if (parts.size() != 2 || !row_from(parts[1], row) || !exists(row.key)) {
                return invalid("unknown list update key");
            }
            patch.changed[row.key] = row;
        } else if (code == "d" || code == "m") {
            if (parts.size() != (code == "d" ? 2u : 3u) || !parts[1].is_string() || !exists(parts[1].as_string())) {
                return invalid("invalid list change");
            }
            const std::string& key = parts[1].as_string();
            std::vector<std::string>& keys = order();
            auto found = std::find(keys.begin(), keys.end(), key);
            if (found == keys.end()) return invalid("invalid list change");
            int64_t old = found - keys.begin();
            if (code == "d") {
                keys.erase(found);
                patch.changed.erase(key);
                patch.deleted.insert(key);
                patch.edits.push_back({'d', old, old});
            } else {
                if (!parts[2].is_integer() || parts[2].as_int() < 0 ||
                    parts[2].as_int() >= static_cast<int64_t>(keys.size())) {
                    return invalid("invalid list move index");
                }
                int64_t index = parts[2].as_int();
                keys.erase(found);
                keys.insert(keys.begin() + index, key);
                patch.edits.push_back({'m', old, index});
            }
        } else {
            return invalid("invalid list change");
        }
    }
    return true;
}

void ListStore::publish(const ListPatch& patch) {
    bool sticky_changed = false;
    for (const auto& [key, row] : patch.changed) {
        auto old = rows_.find(key);
        if (old == rows_.end() || old->second.sticky != row.sticky) sticky_changed = true;
    }
    if (patch.reset) {
        rows_.clear();
    } else {
        for (const std::string& key : patch.deleted) rows_.erase(key);
    }
    for (const auto& [key, row] : patch.changed) rows_[key] = row;
    if (patch.reorders) {
        keys_ = patch.order;
        indices_.clear();
        for (size_t i = 0; i < keys_.size(); ++i) indices_[keys_[i]] = static_cast<int64_t>(i);
    }
    if (patch.reorders || sticky_changed) {
        sticky_.clear();
        for (size_t i = 0; i < keys_.size(); ++i) {
            if (rows_[keys_[i]].sticky) sticky_.push_back(static_cast<int64_t>(i));
        }
    }
    revision_ = patch.revision;
}

const ListRow* ListStore::row(int64_t index) const {
    if (index < 0 || index >= static_cast<int64_t>(keys_.size())) return nullptr;
    auto found = rows_.find(keys_[static_cast<size_t>(index)]);
    return found == rows_.end() ? nullptr : &found->second;
}

int64_t ListStore::index_of(const std::string& key) const {
    auto found = indices_.find(key);
    return found == indices_.end() ? -1 : found->second;
}

int64_t ListStore::sticky_at(int64_t index) const {
    auto it = std::upper_bound(sticky_.begin(), sticky_.end(), index);
    return it == sticky_.begin() ? -1 : *(it - 1);
}

std::string edits_json(const ListPatch& patch) {
    std::string out = "{\"revision\":" + std::to_string(patch.revision) + ",\"reset\":";
    out += patch.reset ? "true" : "false";
    out += ",\"edits\":[";
    bool first = true;
    for (const ListEdit& edit : patch.edits) {
        if (!first) out += ",";
        first = false;
        out += "[\"";
        out += edit.code == 'r' ? std::string("reset") : std::string(1, edit.code);
        out += "\"," + std::to_string(edit.from) + "," + std::to_string(edit.to) + "]";
    }
    out += "]}";
    return out;
}

}  // namespace pn
