cmake_minimum_required(VERSION 3.2)
project(xfel_project)

set (CMAKE_CXX_STANDARD 14)

# Get Python version information
execute_process(
  COMMAND python -c "import sys; print(sys.version_info[0])"
  OUTPUT_VARIABLE PYMAJ
  OUTPUT_STRIP_TRAILING_WHITESPACE
)

execute_process(
  COMMAND python -c "import sys; print(sys.version_info[1])"
  OUTPUT_VARIABLE PYMIN
  OUTPUT_STRIP_TRAILING_WHITESPACE
)


# easyBragg github folder:
if (NOT DEFINED XFEL_PROJ)
    get_filename_component(XFEL_PROJ ".." REALPATH BASE_DIR "${CMAKE_BINARY_DIR}")
endif()

set(XFEL "${XFEL_PROJ}/xfel")

message(">> XFEL DIR: ${XFEL}")
set(CONDA $ENV{CONDA_PREFIX})
set(PYNUM "${PYMAJ}${PYMIN}")
set(PY "python${PYMAJ}.${PYMIN}")

find_library(BOOST_PY REQUIRED NAMES boost_python${PYNUM} HINTS "${CONDA}/lib")
find_library(BOOST_SYS REQUIRED NAMES boost_system HINTS "${CONDA}/lib")
find_library(BOOST_NP REQUIRED NAMES boost_numpy${PYNUM} HINTS "${CONDA}/lib")
set(BOOST_LIBS
    ${BOOST_PY}
    ${BOOST_SYS}
    ${BOOST_NP}
)
message(">> Boost libraries found: ${BOOST_LIBS}")
find_library(CCTBX_LIB REQUIRED NAMES cctbx HINTS "${CONDA}/lib")
message(">> CCTBX library found: ${CCTBX_LIB}")

set(INCS
  ${XFEL}
  ${CONDA}/lib/${PY}/site-packages
  ${CONDA}/include
  ${CONDA}/include/${PY}
)

set(LIBS
  ${BOOST_LIBS}
  ${CCTBX_LIB}
)

add_compile_options(
    "$<$<COMPILE_LANGUAGE:CXX>:-O3;-fPIC>"
)

add_library(vonH_xes_ext OBJECT ${XFEL}/vonHamos/xes_ext.cpp)
target_include_directories(vonH_xes_ext PRIVATE ${INCS})

set(CMAKE_SHARED_LIBRARY_PREFIX "")
set(CMAKE_SHARED_LIBRARY_SUFFIX_CXX ".so")
add_library(xes_ext SHARED)

if (${CMAKE_SYSTEM_NAME} MATCHES "Darwin")
  target_link_libraries(xes_ext vonH_xes_ext ${LIBS} "-undefined dynamic_lookup")
else()
  target_link_libraries(xes_ext vonH_xes_ext ${LIBS})
endif()

set(CMAKE_INSTALL_PREFIX "${XFEL_PROJ}")
message(">> INSTALL PREFIX: ${CMAKE_INSTALL_PREFIX}")
install(TARGETS xes_ext DESTINATION ext)
