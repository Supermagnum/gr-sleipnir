########################################################################
# Install python sources
########################################################################

file(GLOB python_files "*.py")

install(PROGRAMS ${python_files}
    DESTINATION ${GR_PYTHON_DIR}/gr_opus
    COMPONENT python
)

