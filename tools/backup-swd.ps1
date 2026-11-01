param([switch]$IdentifyOnly,[ValidateRange(100,5000)][int]$SpeedKHz=1000)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path $PSScriptRoot -Parent
$taskExe = Join-Path $PSScriptRoot 'openocd-ch347\libusb-bin\openocd.exe'
$taskCfg = Join-Path $PSScriptRoot 'openocd-ch347\bat68-swd.cfg'
$taskStamp = Get-Date -Format 'yyyyMMdd_HHmmss_fff'
$taskOut = Join-Path $taskRoot "backups\swd_$taskStamp"
New-Item -ItemType Directory -Path $taskOut -Force | Out-Null

# All reads use physical addresses, independent of the shadow-memory REMAP.
# Halting and resuming touches debug registers, but this script contains no
# target reset, flash controller write, option write, erase, unlock, or program.
$taskTcl = @'
init
set task_rc [catch {
    halt
    wait_halt 2000
    echo "BAT68_CPUID"
    mdw 0xe000ed00 1
    echo "BAT68_CHIPID"
    mdw 0x4001f010 2
    echo "BAT68_BOOT_VECTOR"
    mdw 0x00200000 8
    echo "BAT68_USER_VECTOR"
    mdw 0x00202000 8
    if {!$task_identify_only} {
        dump_image "$task_out/boot_a.bin" 0x00200000 0x2000
        dump_image "$task_out/boot_b.bin" 0x00200000 0x2000
        dump_image "$task_out/user_a.bin" 0x00202000 0x7e000
        dump_image "$task_out/user_b.bin" 0x00202000 0x7e000
        dump_image "$task_out/information_a.bin" 0x00400000 0x800
        dump_image "$task_out/information_b.bin" 0x00400000 0x800
    }
} task_error]
catch {resume}
if {$task_rc} { echo "BAT68_READ_FAILED: $task_error"; shutdown error }
shutdown
'@
$taskScript = Join-Path $taskOut 'read-only.tcl'
$taskPrefix = 'set task_out {' + $taskOut.Replace([char]92,[char]47) + "}`nset task_identify_only " + ([int][bool]$IdentifyOnly) + "`n"
[IO.File]::WriteAllText($taskScript, $taskPrefix + $taskTcl, [Text.UTF8Encoding]::new($false))
$taskLog = Join-Path $taskOut 'openocd.log'
if ($IdentifyOnly) { $SpeedKHz=100 }
& $taskExe -f $taskCfg -c "adapter speed $SpeedKHz" -f $taskScript 2>&1 | Tee-Object -FilePath $taskLog
if ($LASTEXITCODE -ne 0) { throw "SWD read failed. See $taskLog. No Flash write was requested." }
if ($IdentifyOnly) { Write-Output "Identity log: $taskLog"; exit 0 }

$taskSizes = @{ boot = 0x2000; user = 0x7e000; information = 0x800 }
$taskManifest = [ordered]@{ method='SWD read-only, halted CPU'; timestamp=$taskStamp; regions=@() }
foreach ($taskRegion in @('boot','user','information')) {
    $taskFirst = Join-Path $taskOut ($taskRegion + '_a.bin')
    $taskSecond = Join-Path $taskOut ($taskRegion + '_b.bin')
    if ((Get-Item -LiteralPath $taskFirst).Length -ne $taskSizes[$taskRegion] -or
        (Get-Item -LiteralPath $taskSecond).Length -ne $taskSizes[$taskRegion]) {
        throw "Wrong length for $taskRegion; retain files as unverified reads."
    }
    $taskHashA = (Get-FileHash -LiteralPath $taskFirst -Algorithm SHA256).Hash
    $taskHashB = (Get-FileHash -LiteralPath $taskSecond -Algorithm SHA256).Hash
    if ($taskHashA -ne $taskHashB) { throw "Unstable $taskRegion reads; hashes differ. Retain these as unverified reads." }
    $taskManifest.regions += [ordered]@{ name=$taskRegion; bytes=$taskSizes[$taskRegion]; sha256=$taskHashA; two_reads_match=$true }
}
$taskUserBytes=[IO.File]::ReadAllBytes((Join-Path $taskOut 'user_a.bin'))
$taskInitialSp=[BitConverter]::ToUInt32($taskUserBytes,0)
$taskResetVector=[BitConverter]::ToUInt32($taskUserBytes,4)
if ($taskInitialSp -lt 0x20000000 -or $taskInitialSp -gt 0x20028000 -or ($taskResetVector -band 1) -eq 0) {
    throw 'User vector table is implausible; do not treat these reads as a recovery backup.'
}
$taskManifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $taskOut 'verified_manifest.json') -Encoding utf8
Write-Output "Two reads matched for every requested region: $taskOut"
