# Tự động chuyển Encoding hỗ trợ gõ Tiếng Việt
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

function Show-Menu {
    Clear-Host
    Write-Host "===================================================" -ForegroundColor Cyan
    Write-Host "            N8N START        " -ForegroundColor Yellow
    Write-Host "===================================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  ---> ENTER to START n8n" -ForegroundColor Green
    Write-Host "  ---> DELETE to STOP n8n "-ForegroundColor Red
    Write-Host ""
    Write-Host "===================================================" -ForegroundColor Cyan
}

while ($true) {
    Show-Menu
    
    # Bắt phím bấm trực tiếp từ bàn phím
    $key = $host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

    # Mã 13 = Phím ENTER
    if ($key.VirtualKeyCode -eq 13) {
        Clear-Host
        Write-Host "===================================================" -ForegroundColor Green
        Write-Host "[+] NODE_FUNCTION_ALLOW_BUILTIN=child_process SETTING'S SUCCESSFUL!" -ForegroundColor Green
        Write-Host "[+] N8N'S STARTING..." -ForegroundColor Green
        Write-Host "===================================================" -ForegroundColor Green
        Write-Host ""

        # Gán biến môi trường trong PowerShell
        $env:NODE_FUNCTION_ALLOW_BUILTIN = "child_process"

        # Khởi chạy n8n
        n8n start

        Write-Host ""
        Write-Host "[!] N8N STOPPED." -ForegroundColor Yellow
        Write-Host "ANYTHING TO BACK..." -ForegroundColor Gray
        $null = $host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    }
    # Mã 46 = Phím DELETE (hoặc phím Q để thoát)
    elseif ($key.VirtualKeyCode -eq 46 -or $key.Character -eq 'q') {
        Clear-Host
        Write-Host "===================================================" -ForegroundColor Red
        Write-Host "[-] DELETE. STOP PROCESSING..." -ForegroundColor Red
        Write-Host "===================================================" -ForegroundColor Red
        Start-Sleep -Seconds 1
        break
    }
}