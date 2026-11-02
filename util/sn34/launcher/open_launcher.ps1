param(
    [string]$Keyboard='battle68',
    [string]$Keymap='default',
    [string]$BrowserPath=$env:SN34_CHROME,
    [int]$Port=19368,
    [switch]$AttachOnly,
    [switch]$Visible
)
$ErrorActionPreference='Stop'
if($Port -lt 1 -or $Port -gt 65535){throw 'Invalid TCP port.'}
if($Keyboard -notmatch '^[a-z0-9_]+(/[a-z0-9_]+)*$' -or $Keymap -notmatch '^[a-z0-9_]+$'){throw 'Invalid keyboard/keymap name.'}
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../..'))
$stateRoot=Join-Path $root '.build/launcher'
New-Item -ItemType Directory -Path $stateRoot -Force | Out-Null
$running=$false
try {
    $version=Invoke-RestMethod "http://127.0.0.1:$Port/json/version" -TimeoutSec 2
    $running=$version.Browser -like 'Chrome/*'
} catch {}
if(!$running){
    if($AttachOnly){throw 'The configuration browser is not running.'}
    if(!$BrowserPath -or !(Test-Path -LiteralPath $BrowserPath)){throw 'Supply an external Chrome executable with -BrowserPath or SN34_CHROME.'}
    $signature=Get-AuthenticodeSignature -LiteralPath $BrowserPath
    if($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notlike '*O=Google LLC*'){throw 'Chrome signature verification failed.'}
    $profile=Join-Path $stateRoot "profile_$Port"
    $arguments=@('--user-data-dir="'+$profile+'"','--remote-debugging-address=127.0.0.1',"--remote-debugging-port=$Port",'--no-first-run','--no-default-browser-check','--new-window','https://launcher.keychron.com/#/json')
    $style=if($Visible){'Normal'}else{'Hidden'}
    Start-Process -FilePath $BrowserPath -ArgumentList $arguments -WindowStyle $style | Out-Null
}
$script=Join-Path $PSScriptRoot 'apply_compat.py'
$state=Join-Path $stateRoot "worker_$Port.json"
$workerRunning=$false
if(Test-Path -LiteralPath $state){
    try {
        $worker=Get-Content -LiteralPath $state -Raw | ConvertFrom-Json
        $process=Get-CimInstance Win32_Process -Filter "ProcessId=$($worker.pid)"
        $workerRunning=$process.CommandLine -like '*apply_compat.py*--watch*'
    } catch {}
}
if($workerRunning -and $worker.keyboard -ne $Keyboard){throw 'This port is serving another keyboard; select a different -Port.'}
if(!$workerRunning){
    $uv=(Get-Command uv).Source
    Start-Process -FilePath $uv -ArgumentList @('run','--locked',('"'+$script+'"'),'--watch','--keyboard',$Keyboard,'--port',"$Port") -WindowStyle Hidden -RedirectStandardOutput (Join-Path $stateRoot "worker_$Port.log") -RedirectStandardError (Join-Path $stateRoot "worker_$Port.error.log") | Out-Null
}
& uv run --locked $script --keyboard $Keyboard --port $Port
if($LASTEXITCODE -ne 0){throw 'Launcher compatibility patch could not be attached.'}
$target=$Keyboard.Replace('/','_')+'_'+$Keymap
[PSCustomObject]@{URL='https://launcher.keychron.com/#/json';CDP="http://127.0.0.1:$Port";Definition=(Join-Path $root ".build/${target}_config/sn34_launcher.json")}
