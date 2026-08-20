# Shadows Invoke-WebRequest so the relay's outbound call is CAPTURED, never delivered.
# A function outranks a cmdlet in PowerShell's command resolution order, so the relay
# body below calls this instead of the real cmdlet. Nothing leaves the machine.
#
# Usage:  ./decode-relay.sh
#         cat shadow-prelude.ps1 search-relay.ps1 > run-relay.ps1
#         CAPTURE_PATH=./capture/proxy-outbound.jsonl pwsh -NoProfile -File run-relay.ps1
$script:CapturePath = $env:CAPTURE_PATH
if (-not $script:CapturePath) { $script:CapturePath = './proxy-outbound.jsonl' }
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $script:CapturePath) | Out-Null

function Invoke-WebRequest {
    param(
        [string]$Uri, [string]$Method, $Body, $Headers,
        [switch]$UseBasicParsing, [int]$TimeoutSec
    )
    $rec = [ordered]@{
        captured_at_utc = (Get-Date).ToUniversalTime().ToString('o')
        outbound_uri    = $Uri
        method          = $Method
        headers         = @{}
        body            = $Body
        timeout_sec     = $TimeoutSec
    }
    if ($Headers) { foreach ($k in $Headers.Keys) { $rec.headers[$k] = [string]$Headers[$k] } }
    ($rec | ConvertTo-Json -Compress -Depth 6) | Out-File -FilePath $script:CapturePath -Append -Encoding utf8
    Write-Host "[CAPTURED OUTBOUND] $Method $Uri"
    return [pscustomobject]@{ Content = '{"results":[{"title":"intercepted","url":"https://local.invalid","content":"not sent"}]}' }
}
