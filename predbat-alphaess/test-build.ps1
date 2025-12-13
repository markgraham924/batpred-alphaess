# Local Docker build test script for Predbat AlphaESS add-on
# This builds the Docker image locally so you can test without pushing to GitHub and rebuilding in HA

Write-Host "Building Predbat AlphaESS add-on Docker image locally..." -ForegroundColor Cyan

# Build the image (uses Dockerfile in current directory)
docker build -t predbat-alphaess-test:local -f Dockerfile .

if ($LASTEXITCODE -eq 0) {
    Write-Host "`nBuild successful!" -ForegroundColor Green
    Write-Host "`nTo run the container for testing:" -ForegroundColor Yellow
    Write-Host "docker run --rm -it predbat-alphaess-test:local" -ForegroundColor White
    Write-Host "`nTo inspect the container:" -ForegroundColor Yellow
    Write-Host "docker run --rm -it predbat-alphaess-test:local sh" -ForegroundColor White
} else {
    Write-Host "`nBuild failed!" -ForegroundColor Red
    exit 1
}
