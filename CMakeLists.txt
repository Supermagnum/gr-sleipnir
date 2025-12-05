cmake_minimum_required(VERSION 3.8)
project(gr-opus)

# Set the version of this module here
set(GR_OPUS_VERSION_MAJOR 1)
set(GR_OPUS_VERSION_MINOR 0)
set(GR_OPUS_VERSION_PATCH 0)
set(GR_OPUS_VERSION "${GR_OPUS_VERSION_MAJOR}.${GR_OPUS_VERSION_MINOR}.${GR_OPUS_VERSION_PATCH}")

# Find required packages
find_package(PkgConfig REQUIRED)
pkg_check_modules(GR REQUIRED gnuradio-runtime)

# Include directories
include_directories(${GR_INCLUDE_DIRS})

# Set Python installation paths
set(GR_PYTHON_DIR ${GR_PYTHON_DIR} CACHE PATH "Directory for Python modules")
set(GRC_BLOCKS_DIR ${GRC_BLOCKS_DIR} CACHE PATH "Directory for GRC block definitions")

# Add subdirectories
add_subdirectory(python)
add_subdirectory(grc)

