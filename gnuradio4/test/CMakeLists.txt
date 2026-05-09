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
gr_sleipnir4_add_ut(qa_SleipnirTxHier)
gr_sleipnir4_add_ut(qa_SleipnirRxHier)
