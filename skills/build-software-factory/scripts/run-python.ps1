param([Parameter(ValueFromRemainingArguments=$true)][string[]]$PythonArguments)
$ErrorActionPreference = 'Stop'
$candidates = @()
foreach ($name in @('python','python3','py')) {
    $command = Get-Command $name -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($command -and $command.Source -notmatch '\\Microsoft\\WindowsApps\\') {
        $prefix = @(); if ($name -eq 'py') { $prefix = @('-3') }
        $candidates += [pscustomobject]@{Executable=$command.Source; Prefix=$prefix}
    }
}
$common = Join-Path $env:LOCALAPPDATA 'Programs\Python'
if (Test-Path -LiteralPath $common) {
    foreach ($directory in Get-ChildItem -LiteralPath $common -Directory) {
        $exe = Join-Path $directory.FullName 'python.exe'
        if (Test-Path -LiteralPath $exe -PathType Leaf) { $candidates += [pscustomobject]@{Executable=$exe; Prefix=@()} }
    }
}
$selected = $null
foreach ($candidate in $candidates) {
    $prefix = $candidate.Prefix
    try {
        $reported = & $candidate.Executable @prefix -c 'import sys; print(sys.executable); raise SystemExit(0 if sys.version_info >= (3, 9) else 1)' 2>$null
    } catch { continue }
    if ($LASTEXITCODE -eq 0) { $selected = $candidate; break }
}
if (-not $selected) { throw 'No working Python 3.9+ interpreter found. Install or select one explicitly; this launcher installs nothing.' }
Write-Host ('Using Python: ' + ($reported -join ''))
$prefix = $selected.Prefix
& $selected.Executable @prefix @PythonArguments
exit $LASTEXITCODE
