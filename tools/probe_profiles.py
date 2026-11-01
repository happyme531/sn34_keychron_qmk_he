"""Pinned build inputs. Addresses are from each exact stock ARM image."""
PROFILES={
    "110":dict(base="analysis/binary_2_rcdata_4000_0.bin",
               base_sha="21a26ff6a70a2df7ba76d926aadf251e0265426471b1370285d19a9b17e0abe2",
               wrapper="analysis/oem_updater_v110.exe",
               wrapper_sha="aab010bbceee6d0a972f4e433f991720d67d479e439272cb313649f8d647543f",
               hook=0xd7e8, prefix="f8b5fa48", resume=0xd7ec,
               rx=0x20003578,tx=0x20003538,ready=0x20000360,pending=0x20000361,raw=0x20003908),
    "118":dict(base="analysis/v118_rcdata_4000.bin",
               base_sha="38123b9677fd5aed94b7998b8cbed09a5ad139c7283d298752f0ae6ca5112a36",
               wrapper="analysis/oem_updater_v118.exe",
               wrapper_sha="e49a1f88b497790638dadf1a82034ee646b3c34e9a0a97d63d492698c600f523",
               hook=0xeb60, prefix="2de9f84f", resume=0xeb64,
               rx=0x20003668,tx=0x20003628,ready=0x20000364,pending=0x20000365,raw=0x200039f8),
}
