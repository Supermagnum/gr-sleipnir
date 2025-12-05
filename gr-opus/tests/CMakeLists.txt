########################################################################
# Install test files
########################################################################

file(GLOB python_test_files "*.py")

install(PROGRAMS ${python_test_files}
    DESTINATION ${GR_PYTHON_DIR}/gr_opus/tests
    COMPONENT python
)

########################################################################
# Enable testing
########################################################################

enable_testing()

# Add Python tests
find_program(PYTHON3 NAMES python3 python)
if(PYTHON3)
    add_test(NAME qa_opus_encoder COMMAND ${PYTHON3} -B ${CMAKE_CURRENT_SOURCE_DIR}/qa_opus_encoder.py)
    add_test(NAME qa_opus_decoder COMMAND ${PYTHON3} -B ${CMAKE_CURRENT_SOURCE_DIR}/qa_opus_decoder.py)
    add_test(NAME qa_opus_roundtrip COMMAND ${PYTHON3} -B ${CMAKE_CURRENT_SOURCE_DIR}/qa_opus_roundtrip.py)
endif()

