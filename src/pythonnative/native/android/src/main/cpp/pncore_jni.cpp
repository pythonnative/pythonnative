// JNI bridge between the renderer core (include/pn_core.h) and Kotlin's
// `com.pythonnative.runtime.core.PNCore`.
//
// The core calls its platform callbacks from Python's commit worker, the
// core's work executor, and the UI thread. Each callback attaches the
// calling thread when needed (and detaches it when the thread exits),
// uses method ids cached at load, runs inside its own local reference
// frame, and clears any Kotlin exception so the core never continues with
// one pending. Text that may hold any Unicode crosses as UTF-8 byte arrays,
// never as modified UTF-8 strings.
#include <android/log.h>
#include <jni.h>
#include <pthread.h>

#include <cstring>
#include <string>
#include <vector>

#include "pn_core.h"

namespace {

JavaVM* vm = nullptr;
jclass core_class = nullptr;
jmethodID schedule_mount_method = nullptr;
jmethodID schedule_work_method = nullptr;
jmethodID request_frames_method = nullptr;
jmethodID measure_method = nullptr;
jmethodID baseline_method = nullptr;
jmethodID emit_method = nullptr;
pthread_key_t detach_key;

constexpr const char* kTag = "PythonNative";

void detach_thread(void*) {
    if (vm != nullptr) vm->DetachCurrentThread();
}

/// The calling thread's environment, attaching it on first use.
JNIEnv* environment() {
    JNIEnv* env = nullptr;
    jint status = vm->GetEnv(reinterpret_cast<void**>(&env), JNI_VERSION_1_6);
    if (status == JNI_OK) return env;
    if (status != JNI_EDETACHED) return nullptr;
    JavaVMAttachArgs args{JNI_VERSION_1_6, "PythonNative-core", nullptr};
    if (vm->AttachCurrentThread(&env, &args) != JNI_OK) return nullptr;
    // A non-null value makes the key's destructor detach on thread exit.
    pthread_setspecific(detach_key, env);
    return env;
}

/// Report and clear a pending Kotlin exception; returns whether one was pending.
bool failed(JNIEnv* env, const char* where) {
    if (!env->ExceptionCheck()) return false;
    __android_log_print(ANDROID_LOG_ERROR, kTag, "PNCore.%s threw", where);
    env->ExceptionDescribe();
    env->ExceptionClear();
    return true;
}

/// A local reference frame for one callback.
class Frame {
public:
    explicit Frame(JNIEnv* env) : env_(env), pushed_(env != nullptr && env->PushLocalFrame(16) == 0) {}
    ~Frame() {
        if (pushed_) env_->PopLocalFrame(nullptr);
    }
    bool ok() const { return pushed_; }

private:
    JNIEnv* env_;
    bool pushed_;
};

jbyteArray bytes(JNIEnv* env, const char* text) {
    size_t size = text != nullptr ? std::strlen(text) : 0;
    jbyteArray array = env->NewByteArray(static_cast<jsize>(size));
    if (array != nullptr && size > 0) {
        env->SetByteArrayRegion(array, 0, static_cast<jsize>(size), reinterpret_cast<const jbyte*>(text));
    }
    return array;
}

std::string utf8(JNIEnv* env, jbyteArray array) {
    if (array == nullptr) return std::string();
    jsize size = env->GetArrayLength(array);
    std::string out(static_cast<size_t>(size), '\0');
    if (size > 0) env->GetByteArrayRegion(array, 0, size, reinterpret_cast<jbyte*>(out.data()));
    return out;
}

std::string ascii(JNIEnv* env, jstring text) {
    if (text == nullptr) return std::string();
    const char* chars = env->GetStringUTFChars(text, nullptr);
    std::string out = chars != nullptr ? chars : "";
    if (chars != nullptr) env->ReleaseStringUTFChars(text, chars);
    return out;
}

void call_void(jmethodID method, const char* where) {
    JNIEnv* env = environment();
    if (env == nullptr) return;
    Frame frame(env);
    if (!frame.ok()) return;
    env->CallStaticVoidMethod(core_class, method);
    failed(env, where);
}

void schedule_mount(void*) { call_void(schedule_mount_method, "scheduleMount"); }
void schedule_work(void*) { call_void(schedule_work_method, "scheduleWork"); }
void request_frames(void*) { call_void(request_frames_method, "requestFrames"); }

void measure(void*, const pn_measure_request* request, pn_size* size) {
    size->width = 0;
    size->height = 0;
    JNIEnv* env = environment();
    if (env == nullptr) return;
    Frame frame(env);
    if (!frame.ok()) return;
    jstring component = env->NewStringUTF(request->component != nullptr ? request->component : "");
    jobject props = env->NewDirectByteBuffer(const_cast<uint8_t*>(request->props.data),
                                             static_cast<jlong>(request->props.size));
    if (failed(env, "measure") || component == nullptr || props == nullptr) return;
    auto result = static_cast<jfloatArray>(env->CallStaticObjectMethod(
        core_class, measure_method, static_cast<jlong>(request->surface), static_cast<jlong>(request->tag), component,
        static_cast<jint>(request->mode), props, request->width, static_cast<jint>(request->width_mode),
        request->height, static_cast<jint>(request->height_mode)));
    if (failed(env, "measure") || result == nullptr || env->GetArrayLength(result) < 2) return;
    jfloat values[2] = {0, 0};
    env->GetFloatArrayRegion(result, 0, 2, values);
    if (failed(env, "measure")) return;
    size->width = values[0];
    size->height = values[1];
}

float baseline(void*, int64_t surface, int64_t tag, float width, float height) {
    JNIEnv* env = environment();
    if (env == nullptr) return height;
    Frame frame(env);
    if (!frame.ok()) return height;
    jfloat value = env->CallStaticFloatMethod(core_class, baseline_method, static_cast<jlong>(surface),
                                              static_cast<jlong>(tag), width, height);
    return failed(env, "baseline") ? height : value;
}

void emit(void*, const char* kind, int64_t surface, int64_t tag, const char* name, const char* payload) {
    JNIEnv* env = environment();
    if (env == nullptr) return;
    Frame frame(env);
    if (!frame.ok()) return;
    jstring kind_string = env->NewStringUTF(kind != nullptr ? kind : "");
    jstring name_string = env->NewStringUTF(name != nullptr ? name : "");
    jbyteArray payload_bytes = bytes(env, payload);
    if (failed(env, "emit") || kind_string == nullptr || name_string == nullptr || payload_bytes == nullptr) return;
    env->CallStaticVoidMethod(core_class, emit_method, kind_string, static_cast<jlong>(surface),
                              static_cast<jlong>(tag), name_string, payload_bytes);
    failed(env, "emit");
}

jstring take_string(JNIEnv* env, char* text) {
    if (text == nullptr) return nullptr;
    jstring out = env->NewStringUTF(text);
    pn_core_free(text);
    return out;
}

pn_core* core() { return pn_core_shared(); }

}  // namespace

extern "C" JNIEXPORT jint JNI_OnLoad(JavaVM* machine, void*) {
    vm = machine;
    pthread_key_create(&detach_key, detach_thread);
    JNIEnv* env = nullptr;
    if (vm->GetEnv(reinterpret_cast<void**>(&env), JNI_VERSION_1_6) != JNI_OK) return JNI_ERR;
    // Loaded from PNCore's initializer, so the app class loader resolves it here;
    // threads the core attaches later couldn't find app classes themselves.
    jclass local = env->FindClass("com/pythonnative/runtime/core/PNCore");
    if (local == nullptr) return JNI_ERR;
    core_class = static_cast<jclass>(env->NewGlobalRef(local));
    env->DeleteLocalRef(local);
    schedule_mount_method = env->GetStaticMethodID(core_class, "scheduleMount", "()V");
    schedule_work_method = env->GetStaticMethodID(core_class, "scheduleWork", "()V");
    request_frames_method = env->GetStaticMethodID(core_class, "requestFrames", "()V");
    measure_method = env->GetStaticMethodID(core_class, "measure", "(JJLjava/lang/String;ILjava/nio/ByteBuffer;FIFI)[F");
    baseline_method = env->GetStaticMethodID(core_class, "baseline", "(JJFF)F");
    emit_method = env->GetStaticMethodID(core_class, "emit", "(Ljava/lang/String;JJLjava/lang/String;[B)V");
    if (env->ExceptionCheck() || schedule_mount_method == nullptr || schedule_work_method == nullptr ||
        request_frames_method == nullptr || measure_method == nullptr || baseline_method == nullptr ||
        emit_method == nullptr) {
        env->ExceptionClear();
        return JNI_ERR;
    }
    return JNI_VERSION_1_6;
}

#define PN_JNI(type, name) extern "C" JNIEXPORT type JNICALL Java_com_pythonnative_runtime_core_PNCore_##name

PN_JNI(void, nativeInstall)(JNIEnv*, jclass) {
    pn_platform platform{};
    platform.schedule_mount = schedule_mount;
    platform.schedule_work = schedule_work;
    platform.request_frames = request_frames;
    platform.measure = measure;
    platform.baseline = baseline;
    platform.emit = emit;
    pn_core_set_platform(core(), &platform);
}

PN_JNI(jint, nativeProtocolVersion)(JNIEnv*, jclass) {
    return pn_core_protocol_version();
}

PN_JNI(jboolean, nativeValidateModule)(JNIEnv* env, jclass, jstring module, jstring method, jbyteArray arguments) {
    std::string args = utf8(env, arguments);
    return pn_core_validate_module(core(), ascii(env, module).c_str(), ascii(env, method).c_str(), args.c_str()) != 0;
}

PN_JNI(void, nativeWork)(JNIEnv*, jclass) {
    pn_core_work(core());
}

PN_JNI(jobject, nativeMountNext)(JNIEnv* env, jclass) {
    pn_bytes transaction{};
    uint64_t id = 0;
    if (!pn_core_mount_next(core(), &transaction, &id)) return nullptr;
    // The bytes stay valid until `mountFinished` for this transaction.
    return env->NewDirectByteBuffer(const_cast<uint8_t*>(transaction.data), static_cast<jlong>(transaction.size));
}

PN_JNI(void, nativeMountFinished)(JNIEnv* env, jclass, jlong id, jbyteArray error) {
    if (error == nullptr) {
        pn_core_mount_finished(core(), static_cast<uint64_t>(id), nullptr);
        return;
    }
    std::string message = utf8(env, error);
    pn_core_mount_finished(core(), static_cast<uint64_t>(id), message.c_str());
}

PN_JNI(void, nativeReportContainer)(JNIEnv*, jclass, jlong surface, jlong tag, jfloat x, jfloat y, jfloat width,
                                    jfloat height) {
    pn_core_report_container(core(), surface, tag, x, y, width, height);
}

PN_JNI(void, nativeReportIntrinsic)(JNIEnv*, jclass, jlong surface, jlong tag, jfloat width, jfloat height) {
    pn_core_report_intrinsic(core(), surface, tag, width, height);
}

PN_JNI(void, nativeInvalidate)(JNIEnv*, jclass, jlong surface, jlong tag) {
    pn_core_invalidate(core(), surface, tag);
}

PN_JNI(void, nativeInvalidateMeasurements)(JNIEnv*, jclass) {
    pn_core_invalidate_measurements(core());
}

PN_JNI(void, nativeEvent)(JNIEnv* env, jclass, jlong surface, jlong tag, jstring name, jbyteArray arguments,
                          jlong edit_revision) {
    std::string event = ascii(env, name);
    std::string args = utf8(env, arguments);
    pn_core_event(core(), surface, tag, event.c_str(), args.c_str(), edit_revision);
}

PN_JNI(jboolean, nativeAnimationFrame)(JNIEnv*, jclass, jdouble timestamp_ms) {
    return pn_core_animation_frame(core(), timestamp_ms) != 0;
}

PN_JNI(jobject, nativeTakeWrites)(JNIEnv* env, jclass) {
    pn_bytes writes{};
    if (!pn_core_take_writes(core(), &writes) || writes.size == 0) return nullptr;
    // Valid until the next take on this thread; Kotlin decodes it right away.
    return env->NewDirectByteBuffer(const_cast<uint8_t*>(writes.data), static_cast<jlong>(writes.size));
}

PN_JNI(void, nativeSetReduceMotion)(JNIEnv*, jclass, jboolean enabled) {
    pn_core_set_reduce_motion(core(), enabled ? 1 : 0);
}

PN_JNI(jint, nativePointer)(JNIEnv* env, jclass, jlong surface, jlong tag, jdoubleArray values, jint count) {
    if (values == nullptr || count <= 0 || env->GetArrayLength(values) < count * 7) return 0;
    std::vector<jdouble> raw(static_cast<size_t>(count) * 7);
    env->GetDoubleArrayRegion(values, 0, count * 7, raw.data());
    std::vector<pn_pointer_event> events(static_cast<size_t>(count));
    for (jint i = 0; i < count; ++i) {
        const jdouble* item = raw.data() + static_cast<size_t>(i) * 7;
        events[static_cast<size_t>(i)] = {static_cast<int32_t>(item[0]), static_cast<int32_t>(item[1]),
                                          item[2], item[3], item[4], item[5], item[6]};
    }
    return pn_core_pointer(core(), surface, tag, events.data(), events.size());
}

PN_JNI(jdouble, nativeGestureDeadline)(JNIEnv*, jclass, jlong surface, jlong tag) {
    return pn_core_gesture_deadline(core(), surface, tag);
}

PN_JNI(void, nativeGesturePoll)(JNIEnv*, jclass, jlong surface, jlong tag, jdouble time) {
    pn_core_gesture_poll(core(), surface, tag, time);
}

PN_JNI(jboolean, nativeHasGestures)(JNIEnv*, jclass, jlong surface, jlong tag) {
    return pn_core_has_gestures(core(), surface, tag) != 0;
}

PN_JNI(jstring, nativeListApply)(JNIEnv* env, jclass, jlong surface, jlong tag) {
    return take_string(env, pn_core_list_apply(core(), surface, tag));
}

PN_JNI(jlong, nativeListCount)(JNIEnv*, jclass, jlong surface, jlong tag) {
    return pn_core_list_count(core(), surface, tag);
}

PN_JNI(jlong, nativeListRevision)(JNIEnv*, jclass, jlong surface, jlong tag) {
    return pn_core_list_revision(core(), surface, tag);
}

PN_JNI(jbyteArray, nativeListKey)(JNIEnv* env, jclass, jlong surface, jlong tag, jlong index) {
    char* key = pn_core_list_key(core(), surface, tag, index);
    if (key == nullptr) return nullptr;
    jbyteArray out = bytes(env, key);
    pn_core_free(key);
    return out;
}

PN_JNI(jlong, nativeListIndex)(JNIEnv* env, jclass, jlong surface, jlong tag, jbyteArray key) {
    std::string text = utf8(env, key);
    return pn_core_list_index(core(), surface, tag, text.c_str());
}

PN_JNI(jdouble, nativeListExtent)(JNIEnv*, jclass, jlong surface, jlong tag, jlong index) {
    return pn_core_list_extent(core(), surface, tag, index);
}

PN_JNI(jboolean, nativeListSticky)(JNIEnv*, jclass, jlong surface, jlong tag, jlong index) {
    return pn_core_list_sticky(core(), surface, tag, index) != 0;
}

PN_JNI(jlong, nativeListStickyAt)(JNIEnv*, jclass, jlong surface, jlong tag, jlong index) {
    return pn_core_list_sticky_at(core(), surface, tag, index);
}
