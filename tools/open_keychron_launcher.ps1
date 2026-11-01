param([switch]$AttachOnly)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$browser=Join-Path $root 'build/chrome_arm64/Chrome-bin/chrome.exe'
$profile=Join-Path $root 'build/launcher_arm64_profile'
$port=19368
$running=$false
try {
    $version=Invoke-RestMethod "http://127.0.0.1:$port/json/version" -TimeoutSec 2
    $running=$version.Browser -like 'Chrome/*'
} catch {}
if(!$running){
    if($AttachOnly){throw 'The BAT68 configuration browser is not running.'}
    if(!(Test-Path -LiteralPath $browser)){throw 'Workspace ARM64 Chrome is absent.'}
    $bytes=[System.IO.File]::ReadAllBytes($browser)
    $pe=[BitConverter]::ToInt32($bytes,60)
    if([BitConverter]::ToUInt16($bytes,$pe+4) -ne 0xAA64){throw 'Expected a native Windows ARM64 browser.'}
    $signature=Get-AuthenticodeSignature $browser
    if($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notlike '*O=Google LLC*'){throw 'Chrome signature verification failed.'}
    # External ownership lets the browser survive automation daemon exits.
    $arguments=@('--user-data-dir="'+$profile+'"','--remote-debugging-address=127.0.0.1',"--remote-debugging-port=$port",'--no-first-run','--no-default-browser-check','--disable-features=Translate','--new-window','https://launcher.keychron.com/#/json')
    Start-Process -FilePath $browser -ArgumentList $arguments -WindowStyle Normal | Out-Null
}
$compatScript=Join-Path $PSScriptRoot 'apply_launcher_compat.py'
$workerState=Join-Path $root 'build/launcher_compat_worker.json'
$workerRunning=$false
if(Test-Path -LiteralPath $workerState){
    try {
        $worker=Get-Content -LiteralPath $workerState -Raw | ConvertFrom-Json
        $workerProcess=Get-CimInstance Win32_Process -Filter "ProcessId=$($worker.pid)"
        $workerRunning=$workerProcess.CommandLine -like '*apply_launcher_compat.py*--watch*'
    } catch {}
}
if(!$workerRunning){
    $uvCommand=(Get-Command uv).Source
    Start-Process -FilePath $uvCommand -ArgumentList @('run',('"'+$compatScript+'"'),'--watch','--port',"$port") -WindowStyle Hidden -RedirectStandardOutput (Join-Path $root 'build/launcher_compat_worker.log') -RedirectStandardError (Join-Path $root 'build/launcher_compat_worker_error.log') | Out-Null
}
& uv run $compatScript --port $port
if($LASTEXITCODE -ne 0){throw 'Launcher compatibility patch could not be attached.'}
[PSCustomObject]@{URL='https://launcher.keychron.com/#/json';Browser=$browser;CDP="http://127.0.0.1:$port";Definition=(Join-Path $root 'build/bat68/bat68_launcher.json')}
