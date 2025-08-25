# =============================================
# make_release.ps1
# ---------------------------------------------
# Reactフロントエンドのビルド・Pythonバックエンドのセットアップ
# リリース用成果物(Releaseフォルダ)の自動生成スクリプト
#
# 【主な処理・ワークフロー】
#   - Releaseフォルダの安全な削除・作成 (ユーザー確認あり)
#   - setup_python.ps1 の実行 (ユーザー確認あり)
#   - buildフォルダの有無を確認し、再ビルド・削除・スキップを選択可能
#   - Reactビルド処理は run_build.ps1 に外出し（エラー時は即中断）
#   - build, src-api フォルダをReleaseにコピー (不要ファイル除外)
#   - 完了時に「Releaseフォルダが完成しました」と表示
#
# 【実行例】
#   - PowerShellで本スクリプトを右クリック「PowerShellで実行」またはターミナルから実行
# =============================================

# スクリプトのあるディレクトリをカレントディレクトリに
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$originalDir = Get-Location
Set-Location $scriptDir

$buildDir = Join-Path $scriptDir "build"
$releaseDir = Join-Path $scriptDir "Release"

# Releaseフォルダが存在していたらユーザ確認後に削除
if (Test-Path $releaseDir) {
    $ans = Read-Host "`nReleaseフォルダが既に存在します。削除してよろしいですか？ `n最初から作り直す場合は「y」を選択してください。(y/N)"
    if ($ans -eq "y" -or $ans -eq "Y") {
        Remove-Item $releaseDir -Recurse -Force
        Write-Host "Releaseフォルダを削除しました。" -ForegroundColor Yellow
    }
    else {
        $cont = Read-Host "`n既存のReleaseフォルダを残したまま続行しますか？ (y/N)"
        if ($cont -eq "y" -or $cont -eq "Y") {
            Write-Host "既存のReleaseフォルダを残して続行します。" -ForegroundColor Yellow
        }
        else {
            Write-Host "処理を中断します。" -ForegroundColor Yellow
            Set-Location $originalDir
            exit 1
        }
    }
}

# setup_python.ps1 実行前にユーザ確認
$runPythonSetup = Read-Host "`nPythonのセットアップ (setup_python.ps1) を実行しますか？ (y/N)"
if ($runPythonSetup -eq "y" -or $runPythonSetup -eq "Y") {
    try {
        Write-Host "setup_python.ps1 を実行しています..." -ForegroundColor Green

        ########################################
        # setup_python.ps1 を実行
        ########################################
        & "$scriptDir\setup_python.ps1"

        if ($LASTEXITCODE -ne 0) {
            Write-Host "setup_python.ps1 の実行で異常終了しました (exit code: $LASTEXITCODE)" -ForegroundColor Red
            Set-Location $originalDir
            exit 1
        }
    }
    catch {
        Write-Host "setup_python.ps1 の実行でエラーが発生しました" -ForegroundColor Red
        Set-Location $originalDir
        exit 1
    }
}
else {
    Write-Host "Pythonのセットアップを行わずに続行します。" -ForegroundColor Yellow
}

Write-Host "`n##################################################" -ForegroundColor Cyan
Write-Host "`n  引き続きReactのビルドを実施します。" -ForegroundColor Cyan
Write-Host "`n##################################################" -ForegroundColor Cyan
Pause

try {
    $doBuild = $true
    if (Test-Path $buildDir) {
        $ans = Read-Host "`n既存の build フォルダが存在します。再ビルドしますか？ (y/N)"
        if ($ans -eq "y" -or $ans -eq "Y") {
            Remove-Item $buildDir -Recurse -Force
            Write-Host "既存の build フォルダを削除しました。" -ForegroundColor Yellow
        }
        else {
            Write-Host "既存の build フォルダを残してビルドをスキップします。" -ForegroundColor Yellow
            $doBuild = $false
        }
    }
    if ($doBuild) {
        ########################################
        # Reactビルド処理を外部スクリプトに委譲
        ########################################
        & "$scriptDir\run_build.ps1" -originalDir $originalDir

        if ($LASTEXITCODE -ne 0) {
            Write-Host "run_build.ps1 の実行で異常終了しました (exit code: $LASTEXITCODE)" -ForegroundColor Red
            Set-Location $originalDir
            exit 1
        }
    }
    else {
        Write-Host "Reactビルドをスキップしました。" -ForegroundColor Yellow
    }

    # ソースファイルのコピー処理
    # build フォルダを Release フォルダにコピー
    if (Test-Path $buildDir) {
        $releaseBuildDir = Join-Path $releaseDir "build"
        if (Test-Path $releaseBuildDir) {
            Remove-Item $releaseBuildDir -Recurse -Force
        }
        Copy-Item $buildDir $releaseBuildDir -Recurse
        Write-Host "build フォルダを Release フォルダにコピーしました。" -ForegroundColor Green
    }
    # src-api フォルダを Release フォルダにコピー (不要ファイル除外)
    $srcApiDir = Join-Path $scriptDir "src-api"
    $releaseSrcApiDir = Join-Path $releaseDir "src-api"
    if (Test-Path $srcApiDir) {
        if (Test-Path $releaseSrcApiDir) {
            Remove-Item $releaseSrcApiDir -Recurse -Force
        }
        # 除外パターン
        $excludePatterns = @("*__pycache__*", "*.pyc", "*.pyo", "*.pyd")
        # dataフォルダ（大文字小文字区別なし）を1つだけ判定
        $excludeDataDir = (Join-Path $srcApiDir "data").ToUpper()
        Get-ChildItem $srcApiDir -Recurse -Force | Where-Object {
            $fullName = $_.FullName.ToUpper()
            foreach ($pat in $excludePatterns) {
                if ($fullName -like $pat.ToUpper()) { return $false }
            }
            # dataフォルダ自体は許可、中身は除外
            if ($_.PSIsContainer -and $fullName -eq $excludeDataDir) { return $true }
            if ($fullName.StartsWith($excludeDataDir + [System.IO.Path]::DirectorySeparatorChar)) { return $false }
            if ($fullName -eq $excludeDataDir) { return $true }
            return $true
        } | ForEach-Object {
            $target = Join-Path $releaseSrcApiDir ($_.FullName.Substring($srcApiDir.Length).TrimStart('\', '/'))
            if ($_.PSIsContainer) {
                if (-not (Test-Path $target)) { New-Item -ItemType Directory -Path $target | Out-Null }
            }
            else {
                Copy-Item $_.FullName $target
            }
        }
        Write-Host "src-api フォルダを Release フォルダにコピーしました (不要ファイル除外)" -ForegroundColor Green
    }

    Write-Host "`nReleaseフォルダが完成しました。" -ForegroundColor Cyan
}
finally {
    # スクリプト終了時に元のディレクトリに戻る
    Set-Location $originalDir
}
