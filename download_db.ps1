# Download SQLite DB from Railway production via SSH (no HTTP endpoint needed)
# Usage: .\download_db.ps1
# Requires: railway CLI installed and logged in, project linked

$outFile = "biometric_auth_railway_$(Get-Date -Format 'yyyyMMdd_HHmmss').db"

Write-Host "Connecting to Railway via SSH..." -ForegroundColor Cyan
$b64 = railway ssh -- base64 /app/data/biometric_auth.db
if ($LASTEXITCODE -ne 0 -or -not $b64) {
    Write-Host "ERROR: SSH connection failed or DB not found." -ForegroundColor Red
    exit 1
}

Write-Host "Decoding..." -ForegroundColor Cyan
$bytes = [System.Convert]::FromBase64String($b64.Trim())

# Verify SQLite magic header
$header = [System.Text.Encoding]::ASCII.GetString($bytes[0..14])
if (-not $header.StartsWith("SQLite format 3")) {
    Write-Host "ERROR: File is not a valid SQLite database." -ForegroundColor Red
    exit 1
}

[System.IO.File]::WriteAllBytes("$PWD\$outFile", $bytes)
Write-Host "Done: $outFile ($([math]::Round($bytes.Length/1MB, 2)) MB)" -ForegroundColor Green
