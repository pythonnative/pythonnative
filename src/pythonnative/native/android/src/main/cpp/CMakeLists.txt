# libpncore.so: the renderer core plus its JNI bridge. The builder stages
# the core beside this module (native/core in the repository). Python opens
# the same library with ctypes, so every pn_core_* function stays exported.
cmake_minimum_required(VERSION 3.22)
project(pncore LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(PN_CORE_ROOT ${CMAKE_CURRENT_LIST_DIR}/../../../../core)
add_subdirectory(${PN_CORE_ROOT} ${CMAKE_CURRENT_BINARY_DIR}/core)
set_target_properties(pn_core PROPERTIES CXX_VISIBILITY_PRESET hidden VISIBILITY_INLINES_HIDDEN ON)
add_library(pncore SHARED pncore_jni.cpp)
target_link_libraries(pncore PRIVATE -Wl,--whole-archive pn_core -Wl,--no-whole-archive log)
target_link_options(pncore PRIVATE "-Wl,-z,max-page-size=16384")
