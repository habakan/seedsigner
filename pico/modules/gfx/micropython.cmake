# The canvas and the ST7789, on the camera directory's board_pins.h
add_library(usermod_gfx INTERFACE)
target_sources(usermod_gfx INTERFACE ${CMAKE_CURRENT_LIST_DIR}/modgfx.c ${CMAKE_CURRENT_LIST_DIR}/qrcodegen.c)
target_include_directories(usermod_gfx INTERFACE ${CMAKE_CURRENT_LIST_DIR}/../camera)
target_link_libraries(usermod_gfx INTERFACE hardware_spi hardware_gpio)
target_link_libraries(usermod INTERFACE usermod_gfx)
