cmake_minimum_required(VERSION 3.22)
project(pn_e2e_checksum LANGUAGES C)
add_library(pn_e2e_checksum SHARED checksum.c)
target_link_options(pn_e2e_checksum PRIVATE "-Wl,-z,max-page-size=16384")
