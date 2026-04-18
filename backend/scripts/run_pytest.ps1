param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$PytestArgs
)

$backendRoot = Split-Path -Parent $PSScriptRoot
$preferredPython = "F:\miniconda\envs\chatchat\python.exe"

if (-not $env:SystemRoot) {
    $env:SystemRoot = "C:\Windows"
}
if (-not $env:windir) {
    $env:windir = $env:SystemRoot
}
if (-not $env:PYTHONHASHSEED) {
    $env:PYTHONHASHSEED = "0"
}

if ($env:PYTHONPATH) {
    $env:PYTHONPATH = "$backendRoot;$env:PYTHONPATH"
} else {
    $env:PYTHONPATH = $backendRoot
}

$python = if (Test-Path $preferredPython) { $preferredPython } else { "python" }

& $python -m pytest @PytestArgs
exit $LASTEXITCODE
