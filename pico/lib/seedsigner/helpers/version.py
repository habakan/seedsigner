"""SeedSigner's Version on the Pico: what pico/Makefile read from git at build time (pico_version.py), as
SeedSigner OS reads its version.json. No git, no CI variables and no source files to date on the device."""
import pico_version


class Version:
    @classmethod
    def get_version_name(cls):
        return pico_version.NAME

    @classmethod
    def get_version_fork(cls):
        return pico_version.FORK

    @classmethod
    def get_short_commit_hash(cls):
        return pico_version.SHORT_COMMIT_HASH

    @classmethod
    def get_version_timestamp(cls):
        return None

    @classmethod
    def is_release_image(cls):
        return pico_version.NAME.startswith("v")
