#include <jni.h>
#include <stdint.h>

JNIEXPORT jlong JNICALL Java_com_pythonnative_e2e_checksum_ChecksumModule_adler32Native(
    JNIEnv *env, jobject self, jbyteArray input) {
    (void)self;
    jsize length = (*env)->GetArrayLength(env, input);
    jbyte *data = (*env)->GetByteArrayElements(env, input, NULL);
    uint32_t a = 1, b = 0;
    for (jsize i = 0; i < length; i++) {
        a = (a + (uint8_t)data[i]) % 65521;
        b = (b + a) % 65521;
    }
    (*env)->ReleaseByteArrayElements(env, input, data, JNI_ABORT);
    return (jlong)((b << 16) | a);
}
