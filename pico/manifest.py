# The rp2 port's own modules, then SeedSigner as `make -C pico py` leaves it
freeze("$(PORT_DIR)/modules")
freeze("../build/pico/py")
