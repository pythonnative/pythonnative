/*
 * The PythonNative renderer core: one C ABI for Python and every platform.
 *
 * Python commits JSON envelopes from its commit worker; the core validates
 * them against the loaded contracts, updates its shadow tree, lays it out
 * with Yoga, flattens layout-only views, and queues binary mount
 * transactions for the platform's UI thread. The UI thread never waits on
 * another thread and never takes the core's commit lock.
 *
 * Strings returned by `pn_core_*` functions are heap copies the caller
 * releases with `pn_core_free`. Every function is safe to call before the
 * platform is configured; calls made with an unknown surface fail softly.
 *
 * Mount transaction format (little-endian):
 *
 *   u32 magic 'PNMT', u16 format (1), u16 reserved, i64 surface,
 *   i64 revision, i64 transaction id, u32 op count, then the ops:
 *
 *   0 reset    (destroy every view of the surface)
 *   1 create   i64 tag, str component, value props
 *   2 update   i64 tag, u8 flags (1 = recreate the widget), value changed,
 *              u32 count, str removed...
 *   3 insert   i64 parent, i64 child, u32 index (move-aware)
 *   5 delete   i64 tag (also detaches the view from its parent)
 *   6 frame    i64 tag, f64 x, f64 y, f64 width, f64 height
 *   7 command  i64 tag, str name, value arguments, i64 call id
 *
 *   str:   u32 length, UTF-8 bytes
 *   value: u8 kind, then 0 null, 1 false, 2 true, 3 i64, 4 f64, 5 str,
 *          6 array (u32 count, values), 7 object (u32 count, str key, value)
 *
 * Animated writes (`pn_core_take_writes`): u32 count, then per write
 * i64 tag, str prop, value.
 */
#ifndef PN_CORE_H
#define PN_CORE_H

#include <stddef.h>
#include <stdint.h>

#if defined(_WIN32)
#define PN_CORE_API __declspec(dllexport)
#else
#define PN_CORE_API __attribute__((visibility("default")))
#endif

#ifdef __cplusplus
extern "C" {
#endif

#define PN_CORE_PROTOCOL_VERSION 7

typedef struct pn_core pn_core;

typedef struct {
    const uint8_t *data;
    size_t size;
} pn_bytes;

typedef struct {
    float width;
    float height;
} pn_size;

/* Measurement modes passed to `pn_platform.measure`. */
enum {
    PN_MEASURE_TEXT = 1,      /* thread-safe text layout */
    PN_MEASURE_INTRINSIC = 2, /* a widget measured on the UI thread */
    PN_MEASURE_NATIVE = 3,    /* a plugin's thread-safe measurement */
};

/* Yoga measure modes, as in YGMeasureMode. */
enum {
    PN_MEASURE_UNDEFINED = 0,
    PN_MEASURE_EXACTLY = 1,
    PN_MEASURE_AT_MOST = 2,
};

typedef struct {
    int64_t surface;
    int64_t tag;
    const char *component;
    int32_t mode;
    pn_bytes props; /* the node's props as an encoded value object */
    float width;
    int32_t width_mode;
    float height;
    int32_t height_mode;
} pn_measure_request;

/* Pointer phases for `pn_core_pointer`. */
enum {
    PN_POINTER_DOWN = 0,
    PN_POINTER_MOVE = 1,
    PN_POINTER_UP = 2,
    PN_POINTER_CANCEL = 3,
};

typedef struct {
    int32_t phase;
    int32_t pointer;
    double x, y;          /* view coordinates, points */
    double window_x, window_y;
    double time;          /* seconds on a monotonic clock */
} pn_pointer_event;

typedef struct {
    void *context;
    /* Drain `pn_core_mount_next` on the UI thread soon. Never blocks. */
    void (*schedule_mount)(void *context);
    /* Call `pn_core_work` soon, on any thread but the UI thread. */
    void (*schedule_work)(void *context);
    /* Start calling `pn_core_animation_frame` every display frame. */
    void (*request_frames)(void *context);
    /* Measure a leaf into `size`; called from the commit or layout worker. */
    void (*measure)(void *context, const pn_measure_request *request, pn_size *size);
    /* A text leaf's first baseline; return `height` when unknown. */
    float (*baseline)(void *context, int64_t surface, int64_t tag, float width, float height);
    /* Queue one message for Python: kind, surface, tag, name, JSON payload. */
    void (*emit)(void *context, const char *kind, int64_t surface, int64_t tag, const char *name,
                 const char *payload);
} pn_platform;

/* -- Setup ---------------------------------------------------------------- */

PN_CORE_API pn_core *pn_core_shared(void);
PN_CORE_API int32_t pn_core_protocol_version(void);
PN_CORE_API void pn_core_set_platform(pn_core *core, const pn_platform *platform);
/* Compile a contract document for "ios", "android", "web", or "host".
 * Returns NULL, or an error message to free. */
PN_CORE_API char *pn_core_load_contracts(pn_core *core, const char *document, const char *platform);
/* The fingerprint of the loaded contracts ("" before loading). */
PN_CORE_API char *pn_core_contract_fingerprint(pn_core *core);
/* Enable or disable view flattening (debugging); on by default. */
PN_CORE_API void pn_core_set_flattening(pn_core *core, int32_t enabled);
/* Forget every surface, queued transaction, and contract (tests and reloads). */
PN_CORE_API void pn_core_reset(pn_core *core);
PN_CORE_API void pn_core_free(void *pointer);

/* -- Python --------------------------------------------------------------- */

/* Validate and apply one commit envelope; returns the acknowledgement. */
PN_CORE_API char *pn_core_commit(pn_core *core, const char *envelope);
/* Lay out without a commit: `{"surface", "roots", "width", "height", "selective"}`. */
PN_CORE_API char *pn_core_layout(pn_core *core, const char *request);
/* Queue a view command behind pending mounts; the platform answers
 * asynchronously with a "command" message carrying `call_id`. */
PN_CORE_API char *pn_core_command(pn_core *core, int64_t surface, int64_t tag, const char *name,
                                  const char *arguments, int64_t call_id);
/* Queue an animation request (`graph`, `start`, `cancel`, `set`). */
PN_CORE_API char *pn_core_animate(pn_core *core, int64_t surface, int64_t tag, const char *request);
/* `{"frame": [x, y, w, h], "window": [x, y, w, h]}`, or "null". */
PN_CORE_API char *pn_core_measure(pn_core *core, int64_t surface, int64_t tag);
/* The deepest view at a point in surface coordinates (DevTools). */
PN_CORE_API char *pn_core_inspect(pn_core *core, int64_t surface, double x, double y);
/* Validate a native module call's arguments against its contract. */
PN_CORE_API int32_t pn_core_validate_module(pn_core *core, const char *module, const char *method,
                                            const char *arguments);
/* Whether a value satisfies a JSON-schema contract (tooling and tests). */
PN_CORE_API int32_t pn_core_check_value(const char *schema, const char *value);
/* Run native-initiated relayout and other deferred work. */
PN_CORE_API void pn_core_work(pn_core *core);

/* -- UI thread ------------------------------------------------------------ */

/* Take the next mount transaction; returns 0 when none is queued. The bytes
 * stay valid until `pn_core_mount_finished` for the same transaction. */
PN_CORE_API int32_t pn_core_mount_next(pn_core *core, pn_bytes *transaction, uint64_t *id);
/* Report a transaction applied (`error` NULL) or failed. */
PN_CORE_API void pn_core_mount_finished(pn_core *core, uint64_t id, const char *error);
/* Whether a view exists for `tag` on the UI thread's side. */
PN_CORE_API int32_t pn_core_is_mounted(pn_core *core, int64_t surface, int64_t tag);
/* The size (and window origin) of a container a detached root lays out in. */
PN_CORE_API void pn_core_report_container(pn_core *core, int64_t surface, int64_t tag, float x, float y,
                                          float width, float height);
/* A leaf's content size changed (an image loaded). */
PN_CORE_API void pn_core_report_intrinsic(pn_core *core, int64_t surface, int64_t tag, float width,
                                          float height);
/* Re-measure one leaf (a text input's content changed). */
PN_CORE_API void pn_core_invalidate(pn_core *core, int64_t surface, int64_t tag);
/* Re-measure every leaf (font scale or content size category changed). */
PN_CORE_API void pn_core_invalidate_measurements(pn_core *core);
/* Stamp and deliver a view event to Python; feeds animated event bindings. */
PN_CORE_API void pn_core_event(pn_core *core, int64_t surface, int64_t tag, const char *name,
                               const char *arguments, int64_t edit_revision);
/* Advance animations to `timestamp_ms`; returns whether frames should continue. */
PN_CORE_API int32_t pn_core_animation_frame(pn_core *core, double timestamp_ms);
/* Take animated prop writes produced since the last call. */
PN_CORE_API int32_t pn_core_take_writes(pn_core *core, pn_bytes *writes);
PN_CORE_API void pn_core_set_reduce_motion(pn_core *core, int32_t enabled);
/* Feed pointer events to a view's gestures. Returns 1 while a pan is active. */
PN_CORE_API int32_t pn_core_pointer(pn_core *core, int64_t surface, int64_t tag,
                                    const pn_pointer_event *events, size_t count);
/* The next time a view's gestures need `pn_core_gesture_poll`, or -1. */
PN_CORE_API double pn_core_gesture_deadline(pn_core *core, int64_t surface, int64_t tag);
PN_CORE_API void pn_core_gesture_poll(pn_core *core, int64_t surface, int64_t tag, double time);
/* Whether a view has gestures the core recognizes. */
PN_CORE_API int32_t pn_core_has_gestures(pn_core *core, int64_t surface, int64_t tag);

/* List datasets, read by a VirtualList's data source on the UI thread. */
/* Publish the next queued dataset patch; returns its edits as JSON, or NULL. */
PN_CORE_API char *pn_core_list_apply(pn_core *core, int64_t surface, int64_t tag);
PN_CORE_API int64_t pn_core_list_count(pn_core *core, int64_t surface, int64_t tag);
/* The published dataset revision (a recreated list view starts from it), or 0. */
PN_CORE_API int64_t pn_core_list_revision(pn_core *core, int64_t surface, int64_t tag);
/* The key at `index`, or NULL. */
PN_CORE_API char *pn_core_list_key(pn_core *core, int64_t surface, int64_t tag, int64_t index);
PN_CORE_API int64_t pn_core_list_index(pn_core *core, int64_t surface, int64_t tag, const char *key);
/* The row's extent (0 when out of range), sticky flag, and revision. */
PN_CORE_API double pn_core_list_extent(pn_core *core, int64_t surface, int64_t tag, int64_t index);
PN_CORE_API int32_t pn_core_list_sticky(pn_core *core, int64_t surface, int64_t tag, int64_t index);
PN_CORE_API int64_t pn_core_list_row_revision(pn_core *core, int64_t surface, int64_t tag, int64_t index);
/* The sticky row at or before `index`, or -1. */
PN_CORE_API int64_t pn_core_list_sticky_at(pn_core *core, int64_t surface, int64_t tag, int64_t index);

#ifdef __cplusplus
}
#endif

#endif /* PN_CORE_H */
