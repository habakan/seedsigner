# The DVP camera driver and the Rust QR reader from bitwasm-signer-pico (see ORIGIN), for the rp2 port
set(CAMERA_DIR ${CMAKE_CURRENT_LIST_DIR})
add_library(pico_camera STATIC ${CAMERA_DIR}/camera.c ${CAMERA_DIR}/camera_ov7670.c)
pico_generate_pio_header(pico_camera ${CAMERA_DIR}/camera.pio)
target_include_directories(pico_camera PUBLIC ${CAMERA_DIR})
target_link_libraries(pico_camera PUBLIC pico_stdlib hardware_pio hardware_dma hardware_i2c hardware_clocks)

# Cargo decides for itself whether anything changed, so it always runs; flags as bitwasm-signer-pico's
set(QR_READER_LIB ${CMAKE_BINARY_DIR}/qr_reader/riscv32imac-unknown-none-elf/release/libqr_reader.a)
add_custom_target(qr_reader_lib
  COMMAND ${CMAKE_COMMAND} -E env "RUSTFLAGS=-C target-feature=+zba,+zbb,+zbs -C relocation-model=static"
    cargo build --release --locked --target-dir ${CMAKE_BINARY_DIR}/qr_reader
  WORKING_DIRECTORY ${CAMERA_DIR}/qr_reader
  BYPRODUCTS ${QR_READER_LIB})

add_library(usermod_camera INTERFACE)
target_sources(usermod_camera INTERFACE ${CAMERA_DIR}/modcamera.c)
target_include_directories(usermod_camera INTERFACE ${CAMERA_DIR})
target_link_libraries(usermod_camera INTERFACE pico_camera ${QR_READER_LIB} hardware_watchdog)
add_dependencies(usermod_camera qr_reader_lib)
target_link_libraries(usermod INTERFACE usermod_camera)
