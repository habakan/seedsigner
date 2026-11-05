# SeedSigner's own QR encoders drawn on the Pico's display: a SeedQR, then an animated UR PSBT at the
# QRDisplayScreen's size and border, timing each frame from encoding to the LCD
import binascii, gc, time
from seedsigner.gui.renderer import Renderer
from seedsigner.models.encode_qr import SeedQrEncoder, UrPsbtQrEncoder
from seedsigner.models.settings import SettingsConstants as SC

PSBT = binascii.a2b_base64("cHNidP8BAMUCAAAAAi3cJLA5qNmU6PAXQFY7QkDphmQ2iS3DXR4GlOZQu2gMAAAAAAD9////RXe+3a5meMIh5QyFFTp/Cs3laOFUFY+TuBbIwtGcj28BAAAAAP3///8DoIYBAAAAAAAWABSlpznvac+MBo6URWMiZxE52rh26iBOAAAAAAAAFgAUmEQgSFlZ0Noj5/6QK/MVgUzHtktovwAAAAAAACJRIIgtdOXQVy1agWzvAEGpa2wd6DL2+WdtlgXETV6al9PcAAAAAAABAFICAAAAATAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwAAAAAAD/////AaCGAQAAAAAAFgAUwM681sPTyox13F7GLr5VMw75EOIAAAAAAQEfoIYBAAAAAAAWABTAzrzWw9PKjHXcXsYuvlUzDvkQ4iIGAzDVT9DdQgpuX402JPXzSCyuNQ951fB1O/W+75wtka88GHPF2gpUAACAAAAAgAAAAIAAAAAAAAAAAAABAH0CAAAAATExMTExMTExMTExMTExMTExMTExMTExMTExMTExMTExAAAAAAD/////AugDAAAAAAAAFgAUMTExMTExMTExMTExMTExMTExMTFwEQEAAAAAACJRIKYIafDbzx3GWcnOy6+AUBNeqejNxIcFPx3GiAlJ3GhMAAAAAAEBK3ARAQAAAAAAIlEgpghp8NvPHcZZyc7Lr4BQE16p6M3EhwU/HcaICUncaEwhFsyKS8ZNiXvdxfvC9nD3qLoLOGd5EGzxIjxvxdfNb8EVGQBzxdoKVgAAgAAAAIAAAACAAAAAAAAAAAAAACICAoSuDvvlyzWyQDbUjUnTxVqE+nVVK9Fi/DoqVeKZfdRZGHPF2gpUAACAAAAAgAAAAIAAAAAABQAAAAAhBzmfGy9Dk/KaGMk3hZxd2KdzUBAxV+uIDwLowIIUJ3zvGQBzxdoKVgAAgAAAAIAAAACAAQAAAAAAAAAA")
MNEMONIC = "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about".split()

Renderer.configure_instance()
r = Renderer.get_instance()
seedqr = SeedQrEncoder(mnemonic=MNEMONIC, wordlist_language_code="en")
t = time.ticks_ms()
r.show_image(seedqr.next_part_image(240, 240, border=2, background_color="ffffff"))
print("SeedQR", seedqr.cur_part(), "ms", time.ticks_diff(time.ticks_ms(), t))
time.sleep(3)

ur = UrPsbtQrEncoder(psbt=PSBT, qr_density=SC.DENSITY__MEDIUM)
times = []
for i in range(30):
    t = time.ticks_ms()
    r.show_image(ur.next_part_image(240, 240, border=2, background_color="ffffff"))
    times.append(time.ticks_diff(time.ticks_ms(), t))
gc.collect()
print("UR frames", ur.seq_len(), "ms per frame min/max", min(times), max(times), "free KB", gc.mem_free() // 1024)
