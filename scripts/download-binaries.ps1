param(
    [string]$Manifest = "build\binaries-list.txt"
)

$Root = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ManifestPath = Join-Path $Root "..\$Manifest" | Resolve-Path -ErrorAction SilentlyContinue
if (-not $ManifestPath) {
    Write-Error "Manifest not found: $Manifest"
    exit 1
}

Get-Content $ManifestPath | ForEach-Object {
    $line = $_.Split('#')[0].Trim()
    if ([string]::IsNullOrWhiteSpace($line)) { return }
    $parts = $line -split '\|'
    if ($parts.Count -lt 2) { Write-Warning "Skipping malformed line: $line"; return }
    $url = $parts[0].Trim()
    $out = $parts[1].Trim()
    $sha = if ($parts.Count -ge 3) { $parts[2].Trim() } else { $null }

    $outDir = Split-Path $out -Parent
    if ($outDir -and -not (Test-Path $outDir)) { New-Item -ItemType Directory -Path $outDir -Force | Out-Null }

    if (Test-Path $out) {
        if ($sha) {
            $cur = (Get-FileHash -Algorithm SHA256 -Path $out).Hash.ToLower()
            if ($cur -eq $sha.ToLower()) { Write-Host "OK: $out (matches sha256)"; return }
            else { Write-Host "Mismatch sha256 for $out, re-downloading" }
        } else {
            Write-Host "Exists: $out (no sha provided)"; return
        }
    }

    Write-Host "Downloading $url -> $out"
    try {
        Invoke-WebRequest -Uri $url -OutFile $out -UseBasicParsing -ErrorAction Stop
    } catch {
        Write-Error "Failed to download $url : $_"
        continue
    }

    if ($sha) {
        $cur = (Get-FileHash -Algorithm SHA256 -Path $out).Hash.ToLower()
        if ($cur -ne $sha.ToLower()) { Write-Error "SHA256 mismatch for $out" }
        else { Write-Host "Downloaded and verified: $out" }
    } else { Write-Host "Downloaded: $out" }
}

Write-Host "All done."
