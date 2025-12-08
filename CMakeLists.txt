cmake_minimum_required(VERSION 3.8)
project(gr-sleipnir)

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

# Find Python
find_package(Python3 COMPONENTS Interpreter REQUIRED)

# Set Python installation paths
if(NOT GR_PYTHON_DIR)
    execute_process(
        COMMAND ${Python3_EXECUTABLE} -c "import gnuradio; import os; print(os.path.dirname(gnuradio.__file__))"
        OUTPUT_VARIABLE GR_PYTHON_DIR
        OUTPUT_STRIP_TRAILING_WHITESPACE
        ERROR_QUIET
    )
    if(NOT GR_PYTHON_DIR)
        # Fallback: use Python site-packages
        execute_process(
            COMMAND ${Python3_EXECUTABLE} -c "import site; print(site.getsitepackages()[0])"
            OUTPUT_VARIABLE GR_PYTHON_DIR
            OUTPUT_STRIP_TRAILING_WHITESPACE
            ERROR_QUIET
        )
    endif()
endif()
set(GR_PYTHON_DIR ${GR_PYTHON_DIR} CACHE PATH "Directory for Python modules")

if(NOT GRC_BLOCKS_DIR)
    execute_process(
        COMMAND ${Python3_EXECUTABLE} -c "import os; print(os.path.join(os.path.expanduser('~'), '.gnuradio', 'grc', 'blocks'))"
        OUTPUT_VARIABLE GRC_BLOCKS_DIR
        OUTPUT_STRIP_TRAILING_WHITESPACE
        ERROR_QUIET
    )
endif()
set(GRC_BLOCKS_DIR ${GRC_BLOCKS_DIR} CACHE PATH "Directory for GRC block definitions")

# Add subdirectories
add_subdirectory(python)

# Add grc subdirectory if it exists and has CMakeLists.txt
if(EXISTS ${CMAKE_CURRENT_SOURCE_DIR}/grc/CMakeLists.txt)
    add_subdirectory(grc)
endif()

########################################################################
# Custom target: build info (runs automatically)
########################################################################
add_custom_target(build_info ALL
    COMMAND ${CMAKE_COMMAND} -E echo ""
    COMMAND ${CMAKE_COMMAND} -E echo "gr-sleipnir: Python-only module - nothing to compile"
    COMMAND ${CMAKE_COMMAND} -E echo "Run 'make install' to install, or 'make check_python' to validate"
    COMMAND ${CMAKE_COMMAND} -E echo ""
)

