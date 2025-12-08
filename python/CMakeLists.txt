########################################################################
# Install python sources
########################################################################
install(FILES
    crypto_helpers.py
    example_superframe_tx.py
    frame_aware_ldpc.py
    ptt_control_integration.py
    ptt_gpio.py
    ptt_network.py
    ptt_serial.py
    ptt_vox.py
    sleipnir_rx_block.py
    sleipnir_rx_hier.py
    sleipnir_superframe_assembler.py
    sleipnir_superframe_parser.py
    sleipnir_tx_block.py
    sleipnir_tx_hier.py
    superframe_controller.py
    voice_frame_builder.py
    zmq_control_helper.py
    zmq_status_output.py
    DESTINATION ${GR_PYTHON_DIR}/sleipnir
    COMPONENT python
)

########################################################################
# Install __init__.py
########################################################################
install(FILES
    __init__.py
    DESTINATION ${GR_PYTHON_DIR}/sleipnir
    COMPONENT python
)

########################################################################
# Custom target to validate Python files
########################################################################
file(GLOB PYTHON_FILES "${CMAKE_CURRENT_SOURCE_DIR}/*.py")
list(REMOVE_ITEM PYTHON_FILES "${CMAKE_CURRENT_SOURCE_DIR}/__init__.py")

add_custom_target(check_python
    COMMAND ${Python3_EXECUTABLE} -m py_compile ${PYTHON_FILES}
    WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
    COMMENT "Validating Python syntax..."
)

