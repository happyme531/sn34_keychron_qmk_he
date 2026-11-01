# Temporary recovery access for the one BAT68 device with failed enumeration.
# Run elevated because usbipd registers a device-specific USB sharing filter.
$ErrorActionPreference = 'Stop'
$recoveryRoot = Split-Path -Parent $PSScriptRoot
$recoveryLog = Join-Path $recoveryRoot 'analysis/bat68_recovery_bind.log'
try {
    $state = & 'C:/Program Files/usbipd-win/usbipd.exe' state | ConvertFrom-Json
    $device = @($state.Devices | Where-Object { $_.BusId -eq '4-4' -and $_.InstanceId -eq 'USB\VID_0C45&PID_8037\B68QMK002' })
    if ($device.Count -ne 1) { throw 'Expected BAT68 at 4-4; device identity changed, refusing to bind' }
    & 'C:/Program Files/usbipd-win/usbipd.exe' bind --busid 4-4 *> $recoveryLog
    if ($LASTEXITCODE -ne 0) { throw "usbipd bind failed: $LASTEXITCODE" }
    Add-Content -LiteralPath $recoveryLog -Value 'BAT68_BIND_COMPLETE'
} catch {
    Add-Content -LiteralPath $recoveryLog -Value $_.ToString()
    exit 1
}
