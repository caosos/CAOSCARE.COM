// rtl433_jni.cpp — JNI shim for the rtl_433 native decoder.
//
// This file is the bridge between Kotlin (Rtl433Bridge.kt) and the native
// rtl_433 C library. The nativeStart() function will:
//   1. Open the RTL-SDR via the supplied USB file descriptor
//   2. Configure tuner (sample rate, gain) and band-hop the requested
//      frequencies (315 / 319 / 433.92 / 868 / 915 MHz)
//   3. Pump rtl_433 demodulators
//   4. Marshal each decoded packet into a Kotlin Fingerprint object
//      via JNI and invoke the callback lambda
//
// Status: skeleton — wire up rtl_433 inputs/outputs once vendored.

#include <jni.h>
#include <android/log.h>

#define LOG_TAG "rtl433_jni"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, LOG_TAG, __VA_ARGS__)

extern "C" JNIEXPORT void JNICALL
Java_care_caos_companion_rtl433_Rtl433Bridge_nativeStart(JNIEnv* env, jobject thiz, jint fd, jobject callback) {
    LOGI("nativeStart fd=%d (rtl_433 not yet vendored — see CMakeLists)", fd);
    // TODO: open rtl-sdr from fd, hop bands, decode, callback per packet
}

extern "C" JNIEXPORT void JNICALL
Java_care_caos_companion_rtl433_Rtl433Bridge_nativeStop(JNIEnv* env, jobject thiz) {
    LOGI("nativeStop");
    // TODO: stop decode loop, close USB
}
