param([switch]$StartUpdate,[ValidatePattern('^v[0-9]+$')][string]$Generation='v16')
& (Join-Path $PSScriptRoot 'oem_qmk_ota.ps1') -StartUpdate:$StartUpdate -Generation $Generation -BuildRelative 'build/native_app_ota' -ImageFile 'bat68_native_app.bin' -UpdaterFile 'BAT68_QMK_NATIVE_v118.exe'
