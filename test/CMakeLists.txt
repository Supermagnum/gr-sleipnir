# SPDX-License-Identifier: GPL-3.0-or-later
function(gr_sleipnir4_add_ut name)
  add_executable(${name} ${name}.cpp)
  target_compile_features(${name} PRIVATE cxx_std_23)
  target_include_directories(${name} PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
  target_link_libraries(
    ${name}
    PRIVATE gnuradio4::gnuradio-options
            gnuradio4::gnuradio-core
            gnuradio4::gnuradio-blocklib-core
            gnuradio4::gr-sleipnir
            ut)
  add_test(NAME ${name} COMMAND ${CMAKE_CROSSCOMPILING_EMULATOR} $<TARGET_FILE:${name}>)
endfunction()

gr_sleipnir4_add_ut(qa_SuperframeAssembler)
gr_sleipnir4_add_ut(qa_SuperframeParser)
gr_sleipnir4_add_ut(qa_TextMessageAssembler)
gr_sleipnir4_add_ut(qa_TextMessageParser)
gr_sleipnir4_add_ut(qa_SleipnirTxHier)
gr_sleipnir4_add_ut(qa_SleipnirRxHier)

find_package(Python3 COMPONENTS Interpreter)
if(Python3_Interpreter_FOUND)
  set(_gr_sleipnir4_py_path "${CMAKE_CURRENT_SOURCE_DIR}/../python")
  add_test(
    NAME qa_KissBridge
    COMMAND "${Python3_EXECUTABLE}" -m pytest "${CMAKE_CURRENT_SOURCE_DIR}/qa_KissBridge.py"
    WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}")
  set_tests_properties(qa_KissBridge PROPERTIES ENVIRONMENT "PYTHONPATH=${_gr_sleipnir4_py_path}")
endif()
