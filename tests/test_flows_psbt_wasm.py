import hashlib

import pytest

from base import FlowTest, FlowStep

from seedsigner.models import decode_qr
from seedsigner.models.psbt_wasm import WasmPSBTParser
from seedsigner.views.view import MainMenuView
from seedsigner.views import scan_views, seed_views, psbt_views


SEEDQR = "0000" * 11 + "0003"  # BIP39's test seed: abandon x 11, about
EXTERNAL = "bc1q5knnnmmfe7xqdr55g43jyec388dtsah27rxamf"

# bitwasm-signer's vectors for that seed, mainnet: (psbt, spend, change, change outputs, SHA-256 of
# what parser.wasm and the signer write, which the Pico 2 writes too)
VECTORS = {
    "own_p2wpkh_2in_nwu": ("cHNidP8BAJoCAAAAAjSabtmNVX6AiTiZH2ir76Y/xQzI7i2YImjVm8f/P9b+AQAAAAD9////4G2+91hHGx7+cNtKmMJQjGzmZkPzqQtsGKn/J0LC/20AAAAAAP3///8CYOoAAAAAAAAWABSlpznvac+MBo6URWMiZxE52rh26qhbAQAAAAAAFgAUPjSYXcpv3cn7NplA5MfY4oc/UpwAAAAAAAEAcQIAAAABMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAAAAAAAP////8C6AMAAAAAAAAWABQwMDAwMDAwMDAwMDAwMDAwMDAwMKCGAQAAAAAAFgAUwM681sPTyox13F7GLr5VMw75EOIAAAAAAQEfoIYBAAAAAAAWABTAzrzWw9PKjHXcXsYuvlUzDvkQ4iIGAzDVT9DdQgpuX402JPXzSCyuNQ951fB1O/W+75wtka88GHPF2gpUAACAAAAAgAAAAIAAAAAAAAAAAAABAFICAAAAATExMTExMTExMTExMTExMTExMTExMTExMTExMTExMTExAAAAAAD/////AVDDAAAAAAAAFgAUnJD5NOpR+g9lBBdwQ+CQjaaSmYMAAAAAAQEfUMMAAAAAAAAWABSckPk06lH6D2UEF3BD4JCNppKZgyIGA+d1/VHw37jNhl2f8cyioVjPZR/pl/3J/unB07Xplep3GHPF2gpUAACAAAAAgAAAAIAAAAAAAQAAAAAAIgIDAlMkiI5Cmrjj268feAJki5zQHptBhIXF+kwbm1cA4aYYc8XaClQAAIAAAACAAAAAgAEAAAAAAAAAAA==", 60000, 89000, 1,
                           "696baca673452cc6d3f8d94be5a84c724decaa43d9bd4e1524a3e90c7bf8c241"),
    "own_p2tr_2in": ("cHNidP8BAKYCAAAAAvmIkbkqqEcnEUWykj/c9a2rZXF3qQABM2PB/gYR29siAAAAAAD9////caGu+bpB5rrQV8q+TPqo5lLv5LQCw5E+krbrutk5P0UCAAAAAP3///8CoIYBAAAAAAAWABSlpznvac+MBo6URWMiZxE52rh26liYAAAAAAAAIlEgiC105dBXLVqBbO8AQalrbB3oMvb5Z22WBcRNXpqX09wAAAAAAAEBK3ARAQAAAAAAIlEgpghp8NvPHcZZyc7Lr4BQE16p6M3EhwU/HcaICUncaEwhFsyKS8ZNiXvdxfvC9nD3qLoLOGd5EGzxIjxvxdfNb8EVGQBzxdoKVgAAgAAAAIAAAACAAAAAAAAAAAAAAQErcBEBAAAAAAAiUSCoLymUTWW4aua15cx14pTq1sWTkaHtxeAW40mMZ/x7uyEWg9/oWjFR0lFykNpGH+KBVZHvafKxiizmPwFpeosxMUUZAHPF2gpWAACAAAAAgAAAAIAAAAAAAQAAAAAAIQc5nxsvQ5PymhjJN4WcXdinc1AQMVfriA8C6MCCFCd87xkAc8XaClYAAIAAAACAAAAAgAEAAAAAAAAAAA==", 100000, 39000, 1,
                     "98e2e5006ee7d007e619b4dfcd466c829d42da3a3dea646ada8062a550d8fb44"),
    # P2WPKH and P2TR inputs, which embit's PSBTParser refuses as mixed; the signer checks each output
    "own_mixed_nwu": ("cHNidP8BAMUCAAAAAi3cJLA5qNmU6PAXQFY7QkDphmQ2iS3DXR4GlOZQu2gMAAAAAAD9////RXe+3a5meMIh5QyFFTp/Cs3laOFUFY+TuBbIwtGcj28BAAAAAP3///8DoIYBAAAAAAAWABSlpznvac+MBo6URWMiZxE52rh26iBOAAAAAAAAFgAUmEQgSFlZ0Noj5/6QK/MVgUzHtktovwAAAAAAACJRIIgtdOXQVy1agWzvAEGpa2wd6DL2+WdtlgXETV6al9PcAAAAAAABAFICAAAAATAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwAAAAAAD/////AaCGAQAAAAAAFgAUwM681sPTyox13F7GLr5VMw75EOIAAAAAAQEfoIYBAAAAAAAWABTAzrzWw9PKjHXcXsYuvlUzDvkQ4iIGAzDVT9DdQgpuX402JPXzSCyuNQ951fB1O/W+75wtka88GHPF2gpUAACAAAAAgAAAAIAAAAAAAAAAAAABAH0CAAAAATExMTExMTExMTExMTExMTExMTExMTExMTExMTExMTExAAAAAAD/////AugDAAAAAAAAFgAUMTExMTExMTExMTExMTExMTExMTFwEQEAAAAAACJRIKYIafDbzx3GWcnOy6+AUBNeqejNxIcFPx3GiAlJ3GhMAAAAAAEBK3ARAQAAAAAAIlEgpghp8NvPHcZZyc7Lr4BQE16p6M3EhwU/HcaICUncaEwhFsyKS8ZNiXvdxfvC9nD3qLoLOGd5EGzxIjxvxdfNb8EVGQBzxdoKVgAAgAAAAIAAAACAAAAAAAAAAAAAACICAoSuDvvlyzWyQDbUjUnTxVqE+nVVK9Fi/DoqVeKZfdRZGHPF2gpUAACAAAAAgAAAAIAAAAAABQAAAAAhBzmfGy9Dk/KaGMk3hZxd2KdzUBAxV+uIDwLowIIUJ3zvGQBzxdoKVgAAgAAAAIAAAACAAQAAAAAAAAAA", 100000, 69000, 2,
                      "5476c3bb9447d5689cc360fcb9603fac4471b12c6bb14551238924b5dce3eb2c"),
}



class TestPSBTSigningFlow(FlowTest):
    """Scan, review and sign with embit's PSBTParser and with the Pico's WasmPSBTParser."""

    @pytest.fixture(params=["embit", "wasm"])
    def parser(self, request, monkeypatch):
        if request.param == "wasm":
            # As on the Pico: no embit PSBT objects; parser.wasm and the signer answer the views
            monkeypatch.setattr(decode_qr, "psbt", None)
            monkeypatch.setattr(psbt_views, "PSBTParser", WasmPSBTParser)
            monkeypatch.setattr("seedsigner.models.psbt.PSBTParser", WasmPSBTParser)
        return request.param


    @pytest.mark.parametrize("vector", VECTORS)
    def test_scan_review_and_sign(self, parser, vector):
        psbt, spend, change, n_change, signed_sha256 = VECTORS[vector]
        if parser == "embit" and vector == "own_mixed_nwu":
            pytest.skip("embit's PSBTParser refuses mixed input types")

        def check(view):
            p = self.controller.psbt_parser
            assert (p.spend_amount, p.change_amount, p.fee_amount, p.num_inputs) == (spend, change, 1000, 2)
            assert p.destination_addresses == [EXTERNAL]
            if parser == "wasm":
                assert hashlib.sha256(self.controller.psbt).hexdigest() == signed_sha256

        self.run_sequence([
            FlowStep(MainMenuView, button_data_selection=MainMenuView.SCAN),
            FlowStep(scan_views.ScanView, before_run=lambda view: view.decoder.add_data(psbt)),
            FlowStep(psbt_views.PSBTSelectSeedView, button_data_selection=psbt_views.PSBTSelectSeedView.SCAN_SEED),
            FlowStep(scan_views.ScanSeedQRView, before_run=lambda view: view.decoder.add_data(SEEDQR)),
            FlowStep(seed_views.SeedFinalizeView, button_data_selection=seed_views.SeedFinalizeView.FINALIZE),
            FlowStep(seed_views.SeedOptionsView, is_redirect=True),
            FlowStep(psbt_views.PSBTOverviewView),
            FlowStep(psbt_views.PSBTMathView),
            FlowStep(psbt_views.PSBTAddressDetailsView, button_data_selection=0),
        ] + [
            FlowStep(psbt_views.PSBTChangeDetailsView, button_data_selection=psbt_views.PSBTChangeDetailsView.NEXT),
        ] * n_change + [
            FlowStep(psbt_views.PSBTFinalizeView, button_data_selection=psbt_views.PSBTFinalizeView.APPROVE_PSBT),
            FlowStep(psbt_views.PSBTSignedQRDisplayView, before_run=check),
            FlowStep(MainMenuView),
        ])
