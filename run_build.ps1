# =============================================
# run_build.ps1
# ---------------------------------------------
# Reactフロントエンドのビルド（npm install & build）を実行
# Docker Desktop/WSL2自動判定・node_modules削除確認付き
# make_release.ps1 から呼び出されるビルド専用スクリプト
#
# 【主な処理】
#   - node_modules フォルダの削除確認（ユーザー選択）
#   - Docker Desktop/WSL2自動判定・WSLディストリ選択
#   - docker compose run で npm install & npm run build を一括実行
#   - エラー時は即中断・終了コード伝播
#   - スクリプト終了時に元のディレクトリへ復帰
# =============================================

param(
    [string]$service = "node-app",
    [string]$workdir = "/workspace",
    [string]$originalDir = (Get-Location)
)

Set-Location (Split-Path -Parent $MyInvocation.MyCommand.Definition)
try {
    # node_modules フォルダの有無を確認し、存在する場合は削除確認
    $nodeModulesDir = Join-Path "." "node_modules"
    if (Test-Path $nodeModulesDir) {
        $ans = Read-Host "`nnode_modules フォルダが既に存在します。削除してよろしいですか？ (y/N)"
        if ($ans -eq "y" -or $ans -eq "Y") {
            Remove-Item $nodeModulesDir -Recurse -Force
            Write-Host "node_modules フォルダを削除しました。" -ForegroundColor Yellow
        }
        else {
            Write-Host "node_modules フォルダを残して続行します。" -ForegroundColor Yellow
        }
    }

    # Docker Desktop利用判定
    $dockerInfo = & docker info 2>$null
    $useDockerDesktop = $false
    if ($dockerInfo -match "Docker Desktop") {
        $useDockerDesktop = $true
    }

    if ($useDockerDesktop) {
        Write-Host "`nDocker Desktop環境が検出されました。ローカルのdocker composeを使用します。" -ForegroundColor Cyan
        $wslPrefix = ""
    }
    else {
        # 利用可能なWSLディストリビューション一覧を表示し、ユーザーに名前を手入力させる（wsl -l -q使用）
        $wslListRaw = & wsl -l -q
        $wslList = $wslListRaw | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne "" }
        $defaultDistro = "Ubuntu"
        Write-Host "`ndocker compose を実行するWSLディストリビューションを選択してください:"
        Write-Host "利用可能なWSLディストリビューション一覧:"
        foreach ($distro in $wslList) {
            if ($distro -eq $defaultDistro) {
                Write-Host ("  {0} (デフォルト)" -f $distro) -ForegroundColor Cyan
            }
            else {
                Write-Host ("  {0}" -f $distro)
            }
        }
        $inputDistro = Read-Host "`n使用するWSLディストリビューション名を入力してください（未入力はUbuntu）"
        if ([string]::IsNullOrWhiteSpace($inputDistro)) {
            $wslDistro = $defaultDistro
        }
        else {
            $wslDistro = $inputDistro
        }
        if ($wslList -notcontains $wslDistro) {
            Write-Host "`nエラー: 指定されたWSLディストリビューション '$wslDistro' は存在しません。" -ForegroundColor Red
            exit 1
        }
        Write-Host "`n選択されたWSLディストリビューション: $wslDistro" -ForegroundColor Cyan
        $wslPrefix = "wsl -d $wslDistro "
    }

    try {
        write-host "npm run build を実行しています..." -ForegroundColor Green
        $LASTEXITCODE = 0
        Invoke-Expression ("$wslPrefix docker compose run --rm -u node -w $workdir $service sh -c 'npm install && npm run build'")
        if ($LASTEXITCODE -eq 130) {
            Write-Host "npm run build がユーザーによって中断されました (Ctrl-C)" -ForegroundColor Red
            exit 1
        }
    }
    catch {
        Write-Host "npm run build でエラーが発生しました" -ForegroundColor Red
        exit 1
    }
}
catch {
    Write-Host "Dockerコンテナの起動中にエラーが発生しました" -ForegroundColor Red
    exit 1
}
finally {
    # スクリプト終了時に元のディレクトリに戻る
    Set-Location $originalDir
}

Write-Host "`nbuildフォルダが完成しました。" -ForegroundColor Cyan
