# SPDX-License-Identifier: GPL-3.0-or-later
cmake_minimum_required(VERSION 3.22)

if(NOT DEFINED CMAKE_CXX_COMPILER)
  find_program(_GR_SLEIPNIR4_CXX NAMES g++-14 g++-15 DOC "C++23 compiler")
  if(_GR_SLEIPNIR4_CXX)
    set(CMAKE_CXX_COMPILER "${_GR_SLEIPNIR4_CXX}" CACHE FILEPATH "C++ compiler" FORCE)
  endif()
endif()

project(
  gr-sleipnir4
  VERSION 1.0.0
  LANGUAGES CXX
  DESCRIPTION "GNU Radio 4.0 port of gr-sleipnir — 8-carrier QPSK digital voice superframe blocks")

set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

include(GNUInstallDirs)

option(GR_SLEIPNIR4_BUILD_TESTS "Build Boost.UT unit tests" ON)

# --- Required: gnuradio4 core ---
find_package(gnuradio4 REQUIRED CONFIG)

# --- Required: gr-opus (for Opus PDU message types in tests) ---
find_package(gnuradio4-gr-opus QUIET CONFIG)
if(NOT gnuradio4-gr-opus_FOUND)
  message(STATUS "gr-sleipnir4: gnuradio4::gr-opus not found via find_package; tests will not link against it")
  set(GR_SLEIPNIR4_HAVE_OPUS OFF)
else()
  message(STATUS "gr-sleipnir4: gnuradio4::gr-opus found")
  set(GR_SLEIPNIR4_HAVE_OPUS ON)
endif()

# --- Optional: OpenSSL for ECDSA frame signing ---
find_package(OpenSSL QUIET)
if(OpenSSL_FOUND)
  message(STATUS "gr-sleipnir4: OpenSSL ${OPENSSL_VERSION} found — ECDSA signing enabled (GR_SLEIPNIR4_HAVE_OPENSSL)")
  set(GR_SLEIPNIR4_HAVE_OPENSSL ON)
else()
  message(STATUS "gr-sleipnir4: OpenSSL not found — signing stubs will be used")
  set(GR_SLEIPNIR4_HAVE_OPENSSL OFF)
endif()

# --- Optional: gr-linux-crypto ---
find_package(gnuradio4-gr-linux-crypto QUIET CONFIG)
if(gnuradio4-gr-linux-crypto_FOUND)
  message(STATUS "gr-sleipnir4: gnuradio4::gr-linux-crypto found")
  set(GR_SLEIPNIR4_HAVE_LINUX_CRYPTO ON)
else()
  set(GR_SLEIPNIR4_HAVE_LINUX_CRYPTO OFF)
endif()

# --- Optional: gr-nacl (ChaCha20 MAC) ---
find_package(gnuradio4-gr-nacl QUIET CONFIG)
if(gnuradio4-gr-nacl_FOUND)
  message(STATUS "gr-sleipnir4: gnuradio4::gr-nacl found")
  set(GR_SLEIPNIR4_HAVE_NACL ON)
else()
  set(GR_SLEIPNIR4_HAVE_NACL OFF)
endif()

# --- Interface library ---
add_library(gnuradio4-gr-sleipnir INTERFACE)
add_library(gnuradio4::gr-sleipnir ALIAS gnuradio4-gr-sleipnir)

target_include_directories(
  gnuradio4-gr-sleipnir
  INTERFACE $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
            $<INSTALL_INTERFACE:include>)

target_link_libraries(gnuradio4-gr-sleipnir
  INTERFACE
    gnuradio4::gnuradio-core
    gnuradio4::gnuradio-blocklib-core)

if(GR_SLEIPNIR4_HAVE_OPENSSL)
  target_compile_definitions(gnuradio4-gr-sleipnir INTERFACE GR_SLEIPNIR4_HAVE_OPENSSL)
  target_link_libraries(gnuradio4-gr-sleipnir INTERFACE OpenSSL::Crypto)
endif()

if(GR_SLEIPNIR4_HAVE_NACL)
  target_compile_definitions(gnuradio4-gr-sleipnir INTERFACE GR_SLEIPNIR4_HAVE_NACL)
  target_link_libraries(gnuradio4-gr-sleipnir INTERFACE gnuradio4::gr-nacl)
endif()

if(GR_SLEIPNIR4_HAVE_LINUX_CRYPTO)
  target_compile_definitions(gnuradio4-gr-sleipnir INTERFACE GR_SLEIPNIR4_HAVE_LINUX_CRYPTO HAVE_GR_LINUX_CRYPTO)
  target_link_libraries(gnuradio4-gr-sleipnir INTERFACE gnuradio4::gr-linux-crypto)
endif()

# --- Install headers ---
install(DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}/include/"
        DESTINATION "${CMAKE_INSTALL_INCLUDEDIR}")

install(
  DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}/python/sleipnir/"
  DESTINATION "${CMAKE_INSTALL_DATAROOTDIR}/gr-sleipnir4/python/sleipnir"
  FILES_MATCHING
  PATTERN "*.py")

install(
  TARGETS gnuradio4-gr-sleipnir
  EXPORT gr-sleipnir4-targets
  INCLUDES DESTINATION "${CMAKE_INSTALL_INCLUDEDIR}")

install(
  EXPORT gr-sleipnir4-targets
  FILE gr-sleipnir4-targets.cmake
  NAMESPACE gnuradio4::
  DESTINATION "${CMAKE_INSTALL_LIBDIR}/cmake/gr-sleipnir4")

# --- CMake package config ---
include(CMakePackageConfigHelpers)

configure_package_config_file(
  "${CMAKE_CURRENT_SOURCE_DIR}/cmake/gr-sleipnir4-config.cmake.in"
  "${CMAKE_CURRENT_BINARY_DIR}/gr-sleipnir4-config.cmake"
  INSTALL_DESTINATION "${CMAKE_INSTALL_LIBDIR}/cmake/gr-sleipnir4")

write_basic_package_version_file(
  "${CMAKE_CURRENT_BINARY_DIR}/gr-sleipnir4-config-version.cmake"
  VERSION "${PROJECT_VERSION}"
  COMPATIBILITY SameMajorVersion)

install(
  FILES "${CMAKE_CURRENT_BINARY_DIR}/gr-sleipnir4-config.cmake"
        "${CMAKE_CURRENT_BINARY_DIR}/gr-sleipnir4-config-version.cmake"
  DESTINATION "${CMAKE_INSTALL_LIBDIR}/cmake/gr-sleipnir4")

# --- pkg-config ---
configure_file(
  "${CMAKE_CURRENT_SOURCE_DIR}/cmake/gnuradio4-gr-sleipnir.pc.in"
  "${CMAKE_CURRENT_BINARY_DIR}/gnuradio4-gr-sleipnir.pc"
  @ONLY)

install(FILES "${CMAKE_CURRENT_BINARY_DIR}/gnuradio4-gr-sleipnir.pc"
        DESTINATION "${CMAKE_INSTALL_LIBDIR}/pkgconfig")

# --- Tests ---
if(GR_SLEIPNIR4_BUILD_TESTS)
  include(FetchContent)
  set(BOOST_UT_DISABLE_MODULE ON CACHE BOOL "Disable UT Module Support" FORCE)
  FetchContent_Declare(
    ut
    GIT_REPOSITORY https://github.com/boost-ext/ut.git
    GIT_TAG 53e17f25119598c6458d30351b260193096ba67e
    EXCLUDE_FROM_ALL)
  FetchContent_MakeAvailable(ut)
  enable_testing()
  add_subdirectory(test)
endif()
