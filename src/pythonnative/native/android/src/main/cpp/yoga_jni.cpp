#include <jni.h>
#include <yoga/Yoga.h>
#include <include/PNStyle.h>
#include <cmath>
static JavaVM* vm;
extern "C" JNIEXPORT jint JNI_OnLoad(JavaVM* value, void*) { vm = value; return JNI_VERSION_1_6; }
static JNIEnv* env() { JNIEnv* result; vm->GetEnv(reinterpret_cast<void**>(&result), JNI_VERSION_1_6); return result; }
static YGNodeRef node(jlong ptr) { return reinterpret_cast<YGNodeRef>(ptr); }
static YGSize measure(YGNodeConstRef n, float w, YGMeasureMode wm, float h, YGMeasureMode hm) {
    auto e = env(); auto object = static_cast<jobject>(YGNodeGetContext(n));
    auto cls = e->GetObjectClass(object);
    auto method = e->GetMethodID(cls, "measure", "(FF)[F");
    auto result = static_cast<jfloatArray>(e->CallObjectMethod(object, method, wm == YGMeasureModeUndefined ? 1e6f : w, hm == YGMeasureModeUndefined ? 1e6f : h));
    float size[2] = {0, 0};
    if (result) { e->GetFloatArrayRegion(result, 0, 2, size); e->DeleteLocalRef(result); }
    e->DeleteLocalRef(cls);
    return {size[0], size[1]};
}
static float baseline(YGNodeConstRef n, float, float h) {
    auto e = env(); auto object = static_cast<jobject>(YGNodeGetContext(n));
    auto cls = e->GetObjectClass(object);
    auto method = e->GetMethodID(cls, "baseline", "(F)F");
    float result = e->CallFloatMethod(object, method, h); e->DeleteLocalRef(cls); return result;
}
#define JNI(name) extern "C" JNIEXPORT name
JNI(jlong) Java_com_pythonnative_runtime_layout_YogaNode_create(JNIEnv* e, jobject self) {
    auto n = YGNodeNew(); YGNodeSetContext(n, e->NewGlobalRef(self)); return reinterpret_cast<jlong>(n);
}
JNI(void) Java_com_pythonnative_runtime_layout_YogaNode_free(JNIEnv* e, jobject, jlong ptr) {
    auto n = node(ptr); e->DeleteGlobalRef(static_cast<jobject>(YGNodeGetContext(n))); YGNodeFree(n);
}
JNI(void) Java_com_pythonnative_runtime_layout_YogaNode_style(JNIEnv* e, jobject, jlong ptr, jstring key, jstring value) {
    auto k = e->GetStringUTFChars(key, nullptr); auto v = e->GetStringUTFChars(value, nullptr);
    PNYogaSetStyle(node(ptr), k, v); e->ReleaseStringUTFChars(key, k); e->ReleaseStringUTFChars(value, v);
}
JNI(void) Java_com_pythonnative_runtime_layout_YogaNode_resetStyle(JNIEnv*, jobject, jlong ptr) {
    auto fresh = YGNodeNew(); YGNodeCopyStyle(node(ptr), fresh); YGNodeFree(fresh);
}
JNI(void) Java_com_pythonnative_runtime_layout_YogaNode_measureLeaf(JNIEnv*, jobject, jlong ptr, jboolean enabled) {
    YGNodeSetMeasureFunc(node(ptr), enabled ? measure : nullptr);
    YGNodeSetBaselineFunc(node(ptr), enabled ? baseline : nullptr);
    if (enabled) YGNodeMarkDirty(node(ptr));
}
JNI(void) Java_com_pythonnative_runtime_layout_YogaNode_insert(JNIEnv*, jobject, jlong ptr, jlong child, jint index) {
    auto n = node(ptr); YGNodeSetMeasureFunc(n, nullptr); YGNodeInsertChild(n, node(child), index);
}
JNI(void) Java_com_pythonnative_runtime_layout_YogaNode_remove(JNIEnv*, jobject, jlong ptr, jlong child) { YGNodeRemoveChild(node(ptr), node(child)); }
JNI(void) Java_com_pythonnative_runtime_layout_YogaNode_calculate(JNIEnv*, jobject, jlong ptr, jfloat w, jfloat h) { YGNodeCalculateLayout(node(ptr), w, h, YGDirectionLTR); }
JNI(jfloatArray) Java_com_pythonnative_runtime_layout_YogaNode_frame(JNIEnv* e, jobject, jlong ptr) {
    auto n = node(ptr); float values[] = {YGNodeLayoutGetLeft(n), YGNodeLayoutGetTop(n), YGNodeLayoutGetWidth(n), YGNodeLayoutGetHeight(n)};
    auto result = e->NewFloatArray(4); e->SetFloatArrayRegion(result, 0, 4, values); return result;
}
