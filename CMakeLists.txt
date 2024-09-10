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

message(DEBUG "Looking for dxtbx build dir via importing in python")
execute_process(COMMAND python -c "import dxtbx, pathlib; print(pathlib.Path(dxtbx.__file__).parent.resolve())"
                RESULT_VARIABLE NO_DXTBX
                OUTPUT_VARIABLE DXTBX_DIR
                OUTPUT_STRIP_TRAILING_WHITESPACE
                ERROR_QUIET)
message(">> DXTBX result=${NO_DXTBX} and dir=${DXTBX_DIR}")

message(DEBUG "Looking for dxtbx build dir via importing in python")
execute_process(COMMAND python -c "import dials, pathlib; print(pathlib.Path(dials.__file__).parent.resolve())"
                RESULT_VARIABLE NO_DIALS
                OUTPUT_VARIABLE DIALS_DIR
                OUTPUT_STRIP_TRAILING_WHITESPACE
                ERROR_QUIET)
message(">> DIALS result=${NO_DIALS} and dir=${DIALS_DIR}")

set(INCS
  ${XFEL}
  ${XFEL}/..
  ${CONDA}/lib/${PY}/site-packages
  ${CONDA}/lib/${PY}/site-packages/annlib_adaptbx/include
  ${CONDA}/lib/${PY}/site-packages/annlib/include
  ${CONDA}/share/cctbx/annlib_adaptbx/include
  ${CONDA}/include
  ${CONDA}/include/${PY}

)

if (NOT NO_DXTBX)
    cmake_path(GET DXTBX_DIR PARENT_PATH dxtbx_include_root)
    set(DXTBX_INCLUDE ${dxtbx_include_root})
    message(">> DXTBX INCLUDE: ${DXTBX_INCLUDE}")
    set(INCS
        ${INCS}
        ${DXTBX_INCLUDE}
    )
endif()

if (NOT NO_DXTBX)
    cmake_path(GET DIALS_DIR PARENT_PATH dials_include_root)
    set(DIALS_INCLUDE ${dials_include_root})
    message(">> DIALS INCLUDE: ${DIALS_INCLUDE}")
    set(INCS
        ${INCS}
        ${DIALS_INCLUDE}
    )
endif()


set(LIBS
  ${BOOST_LIBS}
  ${CCTBX_LIB}
)

add_compile_options(
    "$<$<COMPILE_LANGUAGE:CXX>:-O3;-fPIC>"
)

add_library(vonH_xes OBJECT "${XFEL}/vonHamos/xes_ext.cpp")
add_library(xfel_met OBJECT "${XFEL}/metrology_ext.cpp")
add_library(_ext OBJECT "${XFEL}/ext.cpp")
add_library(met_leg_scale OBJECT "${XFEL}/metrology/legacy_scale/ext.cpp")
add_library(sdfac OBJECT "${XFEL}/merging/algorithms/error_model/sdfac_refine_ext.cpp")
add_library(mono_sim OBJECT "${XFEL}/mono_simulation/ext.cpp")
add_library(cluster OBJECT "${XFEL}/clustering/ext.cpp")
#add_library(scale_core OBJECT ${XFEL}/metrology/legacy_scale/scale_core.cpp)
#add_library(bandpass_gaussian OBJECT ${XFEL}/metrology/legacy_scale/bandpass_gaussian.cpp)
target_include_directories(vonH_xes PRIVATE ${INCS})
target_include_directories(xfel_met PRIVATE ${INCS})
target_include_directories(mono_sim PRIVATE ${INCS})
target_include_directories(_ext PRIVATE ${INCS})
target_include_directories(met_leg_scale PRIVATE ${INCS})
target_include_directories(sdfac PRIVATE ${INCS})
target_include_directories(cluster PRIVATE ${INCS})

set(CMAKE_SHARED_LIBRARY_PREFIX "")
set(CMAKE_SHARED_LIBRARY_SUFFIX_CXX ".so")
add_library(xes_ext SHARED)
add_library(xfel_metrology_ext SHARED)
add_library(xfel_ext SHARED)
add_library(xfel_legacy_scale_ext SHARED)
add_library(xfel_sdfac_refine_ext SHARED)
add_library(xfel_mono_sim_ext SHARED)
add_library(sx_clustering_ext SHARED)


if (${CMAKE_SYSTEM_NAME} MATCHES "Darwin")
  set(LIBS
    ${LIBS}
    "-undefined dynamic_lookup"
  )
endif()

target_link_libraries(xes_ext vonH_xes ${LIBS})
target_link_libraries(xfel_metrology_ext xfel_met ${LIBS})
target_link_libraries(xfel_ext _ext ${LIBS})
target_link_libraries(xfel_legacy_scale_ext met_leg_scale ${LIBS})
target_link_libraries(xfel_sdfac_refine_ext sdfac ${LIBS})
target_link_libraries(xfel_mono_sim_ext mono_sim ${LIBS})
target_link_libraries(sx_clustering_ext cluster ${LIBS})

set(CMAKE_INSTALL_PREFIX "${XFEL_PROJ}")
message(">> INSTALL PREFIX: ${CMAKE_INSTALL_PREFIX}")
set(targets
    xes_ext
    xfel_ext
    xfel_metrology_ext
    xfel_legacy_scale_ext
    xfel_sdfac_refine_ext
    xfel_mono_sim_ext
    sx_clustering_ext
    )

# copy extension module to site-packages
set(PYSITE "${CONDA}/lib/${PY}/site-packages")
if (IS_DIRECTORY "${PYSITE}")
  message(">> PYTHON SITE PACKAGES: ${PYSITE}")
  install (TARGETS ${targets} DESTINATION ${PYSITE})
else()
  install(TARGETS ${targets} DESTINATION ext)
endif()