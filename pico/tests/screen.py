# SeedSigner's own MainMenuScreen, drawn by its own code through the PIL shim onto the Pico's display
import gc, time
t = time.ticks_ms()
from seedsigner.gui.renderer import Renderer
from seedsigner.gui.screens.screen import MainMenuScreen
from seedsigner.views.view import MainMenuView
print("import ms", time.ticks_diff(time.ticks_ms(), t))
Renderer.configure_instance()
r = Renderer.get_instance()
buttons = [MainMenuView.SCAN, MainMenuView.SEEDS, MainMenuView.TOOLS, MainMenuView.SETTINGS]
t = time.ticks_ms()
screen = MainMenuScreen(title="Home", button_data=buttons, show_back_button=False, show_power_button=True)
screen._render()
r.show_image()
print("render and show ms", time.ticks_diff(time.ticks_ms(), t))
gc.collect()
print("free KB", gc.mem_free() // 1024)
