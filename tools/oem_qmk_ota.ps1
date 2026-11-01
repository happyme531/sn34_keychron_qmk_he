param([switch]$StartUpdate,[ValidatePattern('^v[0-9]+$')][string]$Generation='v3',
      [string]$BuildRelative='build/qmk_bridge',
      [string]$ImageFile='bat68_qmk_bridge_v118.bin',
      [string]$UpdaterFile='BAT68_QMK_BRIDGE_v118.exe')
$ErrorActionPreference='Stop'
$otaRoot=Split-Path -Parent $PSScriptRoot
$otaBuild=Join-Path $otaRoot $BuildRelative
$otaManifest=Get-Content -LiteralPath (Join-Path $otaBuild 'manifest.json') -Raw | ConvertFrom-Json
$otaTests=Get-Content -LiteralPath (Join-Path $otaBuild 'test_results.json') -Raw | ConvertFrom-Json
$otaProgram=Get-Item -LiteralPath (Join-Path $otaBuild $UpdaterFile)
$otaImageHash=(Get-FileHash -LiteralPath (Join-Path $otaBuild $ImageFile)).Hash.ToLowerInvariant()
$otaExeHash=(Get-FileHash -LiteralPath $otaProgram.FullName).Hash.ToLowerInvariant()
if($otaTests.status -ne 'PASS_OFFLINE_NOT_FLASHED' -or $otaImageHash -ne $otaTests.image_sha256 -or $otaImageHash -ne $otaManifest.image_sha256 -or $otaExeHash -ne $otaTests.updater_sha256){throw 'Built image/updater do not match passed tests'}
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using System.Text;
public static class Bat68Ota {
 [DllImport("user32.dll")] public static extern IntPtr GetDlgItem(IntPtr hWnd,int id);
 [DllImport("user32.dll",CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr hWnd,StringBuilder text,int maximum);
 [DllImport("user32.dll")] public static extern IntPtr SendMessage(IntPtr hWnd,uint msg,IntPtr w,IntPtr l);
 [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr hWnd,uint msg,IntPtr w,IntPtr l);
 public static string Text(IntPtr window,int id){var b=new StringBuilder(256);GetWindowText(GetDlgItem(window,id),b,b.Capacity);return b.ToString();}
 public static int Progress(IntPtr window){return SendMessage(GetDlgItem(window,1008),0x408,IntPtr.Zero,IntPtr.Zero).ToInt32();}
}
'@
$otaProcess=Start-Process -FilePath $otaProgram.FullName -WorkingDirectory $otaBuild -WindowStyle Normal -PassThru
$otaOpenDeadline=[DateTime]::UtcNow.AddSeconds(10)
do{
    Start-Sleep -Milliseconds 200
    $otaProcess.Refresh()
    $otaWindow=$otaProcess.MainWindowHandle
}while($otaWindow -eq [IntPtr]::Zero -and [DateTime]::UtcNow -lt $otaOpenDeadline)
if($otaWindow -eq [IntPtr]::Zero){throw 'OTA window did not open'}
$otaExpected='CheckSum : '+$otaManifest.checksum
if([Bat68Ota]::Text($otaWindow,1028) -ne $otaExpected){throw 'Native OTA checksum differs from tested image'}
if(-not $StartUpdate){[pscustomobject]@{Id=$otaProcess.Id;Checksum=$otaExpected;Status=[Bat68Ota]::Text($otaWindow,1070)} | ConvertTo-Json;return}
$otaButton=[Bat68Ota]::GetDlgItem($otaWindow,1002)
if($otaButton -eq [IntPtr]::Zero -or -not [Bat68Ota]::PostMessage($otaButton,0xF5,[IntPtr]::Zero,[IntPtr]::Zero)){throw 'OTA Start button could not be activated'}
$otaDeadline=[DateTime]::UtcNow.AddSeconds(40)
$otaRetriedAfterBoot=$false
do{
    Start-Sleep -Seconds 1
    $otaStatus=[Bat68Ota]::Text($otaWindow,1070)
    $otaProgress=[Bat68Ota]::Progress($otaWindow)
    if($otaStatus -eq 'Update fail' -and $otaProgress -eq 0 -and -not $otaRetriedAfterBoot){
        # A full reset can take longer to enumerate than the factory app's
        # direct jump. Retry this same original GUI once after Boot is present.
        $otaBoot=Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue | Where-Object {$_.InstanceId -like 'USB\VID_0C45&PID_7210*' -and $_.Status -eq 'OK'} | Select-Object -First 1
        if($otaBoot){
            [void][Bat68Ota]::PostMessage($otaButton,0xF5,[IntPtr]::Zero,[IntPtr]::Zero)
            $otaRetriedAfterBoot=$true
        }
    }
    if($otaStatus -eq 'Update successfully' -and $otaProgress -eq 100){break}
}while([DateTime]::UtcNow -lt $otaDeadline)
$otaResult=[pscustomobject]@{Time=(Get-Date).ToString('o');ProcessId=$otaProcess.Id;Status=$otaStatus;Progress=$otaProgress;ImageSHA256=$otaImageHash;Checksum=$otaManifest.checksum;RetriedAfterBootEnumeration=$otaRetriedAfterBoot}
$otaResult | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $otaRoot "analysis/qmk_${Generation}_ota_result.json") -Encoding utf8
$otaResult | ConvertTo-Json
if($otaStatus -ne 'Update successfully' -or $otaProgress -ne 100){throw 'OTA did not report success; inspect this existing window before retrying'}
