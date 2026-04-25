cmake_minimum_required(VERSION 3.18.1)
project("rtl433_jni")

# To build the real native decoder:
#   1. git clone --depth 1 https://github.com/merbanan/rtl_433.git rtl_433
#   2. Uncomment the line below (and the externalNativeBuild block in build.gradle.kts).
#
# add_subdirectory(rtl_433)

add_library(rtl433_jni SHARED rtl433_jni.cpp)
find_library(log-lib log)
target_link_libraries(rtl433_jni ${log-lib})
