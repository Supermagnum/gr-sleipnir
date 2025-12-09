########################################################################
# Install GRC files (if they exist)
########################################################################
if(GRC_BLOCKS_DIR)
    # Install GRC block YAML files if they exist
    file(GLOB GRC_BLOCK_FILES "${CMAKE_CURRENT_SOURCE_DIR}/*.block.yml")
    if(GRC_BLOCK_FILES)
        # Install to specified directory (system or user)
        install(FILES ${GRC_BLOCK_FILES}
            DESTINATION ${GRC_BLOCKS_DIR}
            COMPONENT grc
        )
        
        # Also install to user directory as fallback if installing to system
        if("${GRC_BLOCKS_DIR}" MATCHES "^/usr")
            execute_process(
                COMMAND ${Python3_EXECUTABLE} -c "import os; print(os.path.join(os.path.expanduser('~'), '.gnuradio', 'grc', 'blocks'))"
                OUTPUT_VARIABLE USER_GRC_BLOCKS_DIR
                OUTPUT_STRIP_TRAILING_WHITESPACE
                ERROR_QUIET
            )
            if(USER_GRC_BLOCKS_DIR)
                # Create user directory if it doesn't exist
                install(CODE "file(MAKE_DIRECTORY \"${USER_GRC_BLOCKS_DIR}\")")
                # Install to user directory as well
                install(FILES ${GRC_BLOCK_FILES}
                    DESTINATION "${USER_GRC_BLOCKS_DIR}"
                    COMPONENT grc
                )
            endif()
        endif()
    endif()
endif()

