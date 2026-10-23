# The renderer core and the Yoga release it embeds, as one static library.
# Android's module build adds its JNI bridge on top; the host extension and
# the iOS package compile the same sources.
cmake_minimum_required(VERSION 3.22)
project(pn_core LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)
file(GLOB_RECURSE PN_YOGA_SOURCES ${CMAKE_CURRENT_LIST_DIR}/yoga/*.cpp)
file(GLOB PN_CORE_SOURCES ${CMAKE_CURRENT_LIST_DIR}/src/*.cpp)
add_library(pn_core STATIC ${PN_CORE_SOURCES} ${PN_YOGA_SOURCES})
target_include_directories(pn_core PUBLIC ${CMAKE_CURRENT_LIST_DIR}/include PRIVATE ${CMAKE_CURRENT_LIST_DIR})
