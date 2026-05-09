Write-Host "====================================================" -ForegroundColor Cyan
Write-Host "☢️ VIPER RISC MANIFOLD: AUTONOMOUS SYSTEM IGNITION" -ForegroundColor Cyan
Write-Host "====================================================" -ForegroundColor Cyan

Write-Host "`n[1/5] Purging zombie processes and clearing ports..." -ForegroundColor Yellow
Stop-Process -Name "python" -Force -ErrorAction SilentlyContinue
Stop-Process -Name "cloudflared" -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

Write-Host "[2/5] Igniting Python-RISC Logic Bridge (Port 8080) and House Engine..." -ForegroundColor Yellow
Start-Process -FilePath "C:\Users\viper\AppData\Local\Programs\Python\Python311\python.exe" -ArgumentList "C:\Users\viper\house_inference_engine.py" -WorkingDirectory "C:\Users\viper" -WindowStyle Hidden
Start-Sleep -Seconds 15
Start-Process -FilePath "C:\Users\viper\AppData\Local\Programs\Python\Python311\python.exe" -ArgumentList "C:\Users\viper\risc_bridge_server.py" -WorkingDirectory "C:\Users\viper" -WindowStyle Hidden

Write-Host "[3/5] Igniting Karoo Infinite Triplet Loop Daemon..." -ForegroundColor Yellow
Start-Process -FilePath "C:\Users\viper\AppData\Local\Programs\Python\Python311\python.exe" -ArgumentList "C:\Users\viper\infinite_triplet_loop.py" -WorkingDirectory "C:\Users\viper" -WindowStyle Hidden

Write-Host "[4/5] Establishing Cloudflare Quantum Tunnel..." -ForegroundColor Yellow
Remove-Item "C:\Users\viper\tunnel_house.log" -ErrorAction SilentlyContinue
Start-Process -FilePath "C:\Users\viper\cloudflared.exe" -ArgumentList "tunnel --url http://127.0.0.1:8080 --logfile C:\Users\viper\tunnel_house.log --no-autoupdate" -WorkingDirectory "C:\Users\viper" -WindowStyle Hidden

Write-Host "      Waiting for Cloudflare to assign public routing..." -ForegroundColor DarkGray
Start-Sleep -Seconds 10

Write-Host "[5/5] Extracting Public URL & Syncing to LOIBI Nodes..." -ForegroundColor Yellow
$logContent = Get-Content "tunnel_house.log" -ErrorAction SilentlyContinue
if ($logContent) {
    $match = $logContent | Select-String -Pattern "https://[a-zA-Z0-9-]+\.trycloudflare\.com" | Select-Object -Last 1
    if ($match) {
        $tunnelUrl = $match.Matches[0].Value
        Write-Host "`n====================================================" -ForegroundColor Green
        Write-Host "✅ SYSTEM 100% SECURED AND ACTIVE." -ForegroundColor Green
        Write-Host "🌐 PUBLIC URL: $tunnelUrl" -ForegroundColor White
        Write-Host "====================================================" -ForegroundColor Green
        
        # Sync to Local Desktop
        $tunnelUrl | Out-File -FilePath "$env:USERPROFILE\Desktop\CLOUDFLARE_URL.txt" -Force
        
        # Sync to OneDrive Desktop
        $oneDrivePath = "$env:USERPROFILE\OneDrive - Personal\Desktop"
        if (Test-Path $oneDrivePath) {
            $tunnelUrl | Out-File -FilePath "$oneDrivePath\CLOUDFLARE_URL.txt" -Force
            Write-Host "✔️ Synced to OneDrive." -ForegroundColor Green
        }
        
        # Open in default browser automatically
        Start-Process $tunnelUrl
        
    } else {
        Write-Host "⚠️ Tunnel URL not found. Cloudflare may be delayed. Check tunnel_house.log" -ForegroundColor Red
    }
} else {
    Write-Host "⚠️ Failed to read tunnel log." -ForegroundColor Red
}

Write-Host "`nThe Triplet is now sustaining itself in the background." -ForegroundColor Cyan
Write-Host "You may close this window. The manifold will remain active." -ForegroundColor Cyan
Start-Sleep -Seconds 10
