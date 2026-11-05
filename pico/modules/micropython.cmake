include(${CMAKE_CURRENT_LIST_DIR}/bitwasm/micropython.cmake)
include(${CMAKE_CURRENT_LIST_DIR}/wamr/micropython.cmake)
include(${CMAKE_CURRENT_LIST_DIR}/camera/micropython.cmake)

# Double floats: BC-UR's fountain decoder picks mixed fragments with a double-precision alias sampler,
# and single precision picks others, so an animated UR PSBT never completes. Applies to the firmware
target_compile_definitions(usermod INTERFACE MICROPY_FLOAT_IMPL=MICROPY_FLOAT_IMPL_DOUBLE)
