[CmdletBinding()]
param(
    [int]$Port = 9222,
    [string]$ProfileDir = (Join-Path $env:TEMP "smart-context-cdp-profile"),
    [string]$Url = "https://www.google.com"
)

$chromeCandidates = @(
    (Join-Path $env:ProgramFiles "Google\Chrome\Application\chrome.exe"),
    (Join-Path ${env:ProgramFiles(x86)} "Google\Chrome\Application\chrome.exe"),
    (Join-Path $env:LOCALAPPDATA "Google\Chrome\Application\chrome.exe")
) | Where-Object { $_ -and (Test-Path -LiteralPath $_) }

if ($chromeCandidates.Count -eq 0) {
    throw "Google Chrome was not found in the standard Windows install locations."
}

$endpoint = "http://127.0.0.1:$Port"
$versionUrl = "$endpoint/json/version"
try {
    $existing = Invoke-RestMethod -Uri $versionUrl -TimeoutSec 2
    if ($existing.Browser) {
        Write-Output "Chrome CDP is already available at $endpoint"
        Write-Output "Use: --cdp-url $endpoint"
        exit 0
    }
} catch {
    # Start an isolated instance below.
}

New-Item -ItemType Directory -Force -Path $ProfileDir | Out-Null
$arguments = @(
    "--remote-debugging-port=$Port",
    "--user-data-dir=$ProfileDir",
    "--no-first-run",
    "--no-default-browser-check",
    $Url
)
Start-Process -FilePath $chromeCandidates[0] -ArgumentList $arguments | Out-Null

$deadline = (Get-Date).AddSeconds(15)
do {
    Start-Sleep -Milliseconds 250
    try {
        $ready = Invoke-RestMethod -Uri $versionUrl -TimeoutSec 2
        if ($ready.Browser) {
            Write-Output "Chrome CDP is ready at $endpoint"
            Write-Output "This is an isolated profile: $ProfileDir"
            Write-Output "Pass --cdp-url $endpoint to Smart Context Capture."
            exit 0
        }
    } catch {
        # Keep polling until the deadline.
    }
} while ((Get-Date) -lt $deadline)

throw "Chrome started but CDP did not become ready at $endpoint within 15 seconds."
