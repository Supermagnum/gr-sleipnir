########################################################################
# Install grc block definitions
########################################################################

install(FILES
    gr_opus_opus_encoder.block.yml
    gr_opus_opus_decoder.block.yml
    DESTINATION ${GRC_BLOCKS_DIR}
    COMPONENT grc
)

