########################################################################
# Install GRC files (if they exist)
########################################################################
if(GRC_BLOCKS_DIR)
    # Install GRC block YAML files if they exist
    file(GLOB GRC_BLOCK_FILES "${CMAKE_CURRENT_SOURCE_DIR}/*.block.yml")
    if(GRC_BLOCK_FILES)
        install(FILES ${GRC_BLOCK_FILES}
            DESTINATION ${GRC_BLOCKS_DIR}
            COMPONENT grc
        )
    endif()
endif()

