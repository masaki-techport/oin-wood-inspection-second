# =============================================
# setup_python.ps1
# ---------------------------------------------
# Releaseフォルダ用 Windows 組み込み版 Python 環境セットアップ自動化スクリプト
#
# 【主な機能・ワークフロー】
#   - Release内の既存Python環境フォルダ(例: python310等)を検出し、ユーザー確認後に安全に削除
#   - Python公式サイトから3.9以降のバージョン一覧を取得し、対話的にバージョン選択
#   - 選択バージョンのembeddable zipが存在するか自動判定し、最新版を推奨
#   - 組み込み版zipをダウンロード・展開し、site有効化や追加パス設定を自動化
#       ※ 追加パスを変更したい場合は $extraPaths を編集してください
#   - pipインストールとrequirements.txtによる依存モジュール自動インストール
#   - Releaseフォルダにrun.batを自動生成（src-api/main.pyを組み込みPythonで起動）
#
# 【実行例】
#   - PowerShellで本スクリプトを右クリック「PowerShellで実行」またはターミナルから実行
# =============================================

# 追加するパスのリストを作成 (必要に応じて修正)
#  - パスを追加する際にはカンマ区切りで追加 ("pathA", "pathB" など)
#  - パスは Python.exe のあるディレクトリからの相対パスを指定する
$extraPaths = @(
    "../src-api/source"
)

$ftpBase = "https://www.python.org/ftp/python/"
$response = Invoke-WebRequest -Uri $ftpBase

# 元のディレクトリを保存
$originalDir = Get-Location

try {
    # Releaseフォルダの作成と移動
    $releaseDir = Join-Path $PSScriptRoot "Release"
    if (-not (Test-Path $releaseDir)) {
        New-Item -ItemType Directory -Path $releaseDir | Out-Null
    }
    Set-Location $releaseDir

    # Release内のPython***フォルダを確認し、存在する場合は削除するかユーザに確認
    $pythonDirs = Get-ChildItem -Path $releaseDir -Directory | Where-Object { $_.Name -match '^python(\d+|\d+\.\d+)$' }
    foreach ($pyDir in $pythonDirs) {
        $dirName = $pyDir.Name
        Write-Host "検出: $dirName" -ForegroundColor Yellow
        $ans = Read-Host "Release内に [$dirName] フォルダが既に存在します。削除してよろしいですか？ (y/N)"
        if ($ans -eq "y" -or $ans -eq "Y") {
            Remove-Item $pyDir.FullName -Recurse -Force
            Write-Host "$dirName フォルダを削除しました。" -ForegroundColor Green
        }
        else {
            Write-Host "処理を中断します。" -ForegroundColor Yellow
            exit 1
        }
    }

    # 全バージョン取得
    $allVersions = ($response.Content -split "`n") |
        Where-Object { $_ -match 'href="(\d+\.\d+\.\d+)/"' } |
        ForEach-Object { ($_ -replace '.*href="([^"]+)/".*', '$1') } |
        Where-Object { $_ -like "3.*" }

    # 3.9以上のメジャーバージョン抽出（昇順）
    $majorVersions = $allVersions |
        ForEach-Object { ($_ -split '\.')[0..1] -join '.' } |
        Where-Object { [version]$_ -ge [version]"3.9" } |
        Sort-Object { [version]$_ } -Unique

    # まずメジャーバージョン選択
    Write-Host "`n== メジャーバージョンを選択してください (3.9以降) =="
    for ($i = 0; $i -lt $majorVersions.Count; $i++) {
        Write-Host "[$i] $($majorVersions[$i])"
    }
    $majorIndex = Read-Host "番号を入力してください"
    if ($majorIndex -notmatch '^\d+$' -or [int]$majorIndex -ge $majorVersions.Count) {
        Write-Error "無効な入力です"
        exit 1
    }
    $selectedMajor = $majorVersions[$majorIndex]

    # 選択したメジャーバージョンに該当する全パッチバージョンを抽出
    $patchVersions = $allVersions | Where-Object { $_ -like "$selectedMajor.*" } | Sort-Object { [version]$_ }

    # ↓ ここで組み込み版存在チェックをしてフィルターする
    Write-Host "組み込み版の存在チェックをしています。少々お待ちください..." -ForegroundColor Cyan

    $validPatchVersions = @()
    foreach ($ver in $patchVersions) {
        $zipUrl = "$ftpBase$ver/python-$ver-embed-amd64.zip"
        try {
            # HEAD リクエストで存在確認
            Invoke-WebRequest -Uri $zipUrl -Method Head -ErrorAction Stop | Out-Null
            $validPatchVersions += $ver
        }
        catch {
            # 存在しない場合は無視
        }
    }

    if ($validPatchVersions.Count -eq 0) {
        Write-Error "選択したメジャーバージョンに組み込み版が存在しません。"
        exit 1
    }

    # 有効なパッチバージョンを昇順で表示
    $validPatchVersions = $validPatchVersions | Sort-Object { [version]$_ }

    Write-Host "`n== 組み込み版が存在するパッチバージョンを選択してください =="
    for ($i = 0; $i -lt $validPatchVersions.Count; $i++) {
        Write-Host "[$i] $($validPatchVersions[$i])"
    }
    # デフォルトで最新版（昇順なので最後が最新版）
    $defaultPatchIndex = $validPatchVersions.Count - 1
    $patchIndex = Read-Host "番号を入力してください（Enterで最新版: $defaultPatchIndex）"
    if ($patchIndex -eq "") {
        $patchIndex = $defaultPatchIndex
    }
    if ($patchIndex -notmatch '^\d+$' -or [int]$patchIndex -ge $validPatchVersions.Count) {
        Write-Error "無効な入力です"
        exit 1
    }

    $version = $validPatchVersions[$patchIndex]
    Write-Host "`n選択されたバージョン: $version" -ForegroundColor Green

    Write-Host "`n組み込み版Pythonをダウンロードします。" -ForegroundColor Cyan
    Read-Host -Prompt "任意のキーを押してください..."

    # バージョン入力
    # $version = Read-Host "Pythonバージョンを入力してください (例: 3.10.11)"

    # バージョン文字列処理
    # $shortVersion = $version -replace '\.', ''        # 例: 31011
    $majorMinor = ($version -split '\.')[0..1] -join '.' # 3.10
    $embedName = "python-$version-embed-amd64.zip"
    $downloadUrl = "https://www.python.org/ftp/python/$version/$embedName"
    $targetFolder = "python$($majorMinor -replace '\.', '')"

    # 作業ディレクトリの作成
    New-Item -ItemType Directory -Path $targetFolder -Force | Out-Null

    # ダウンロード
    $zipPath = "$targetFolder\$embedName"
    Invoke-WebRequest -Uri $downloadUrl -OutFile $zipPath

    # 展開
    Expand-Archive -Path $zipPath -DestinationPath $targetFolder -Force
    Remove-Item $zipPath

    # site 有効化: python3xx._pth を編集
    $pthFile = Get-ChildItem -Path $targetFolder -Filter "python*._pth" | Select-Object -First 1
    if ($pthFile) {
        $pthPath = $pthFile.FullName

        # site のインポートを有効化
        Write-Host "`n== $($pthFile.Name) の 'import site' を有効化します =="
        (Get-Content $pthPath) |
            ForEach-Object { $_ -replace '^#import site', 'import site' } |
            Set-Content $pthPath
        Write-Host "$($pthFile.Name) の 'import site' を有効化しました" -ForegroundColor Green

        # . のみの行の直後にパスを1行ずつ追加
        Write-Host "`n== $($pthFile.Name) に追加パスを追記します =="
        $pthLines = Get-Content $pthPath
        $newPthLines = @()
        for ($i = 0; $i -lt $pthLines.Count; $i++) {
            $newPthLines += $pthLines[$i]
            if ($pthLines[$i] -eq ".") {
                $newPthLines += $extraPaths
            }
        }
        Set-Content $pthPath $newPthLines
        Write-Host "追加パスを $($pthFile.Name) に追記しました" -ForegroundColor Green
    }
    else {
        Write-Error "_pth ファイルが見つからなかったため、セットアップを中断します。"
        exit 1
    }

    # pipインストール
    Write-Host "`n== pip をインストールします =="
    $pythonExe = Join-Path $targetFolder "python.exe"
    $pipUrl = "https://bootstrap.pypa.io/get-pip.py"
    $getPip = "$targetFolder\get-pip.py"
    Invoke-WebRequest -Uri $pipUrl -OutFile $getPip
    & $pythonExe $getPip --disable-pip-version-check --no-warn-script-location # --no-warn-conflicts
    Remove-Item $getPip

    # requirements.txt からモジュールインストール
    Write-Host "`n== requirements.txt のモジュールをインストールします =="
    $requirementsPath = "../src-api/requirements.txt"
    if (Test-Path $requirementsPath) {
        # & $pythonExe -m pip install --upgrade pip setuptools > $null 2>&1
        & $pythonExe -m pip install -r $requirementsPath --disable-pip-version-check --no-warn-script-location # --no-warn-conflicts
        Write-Host "requirements.txt のモジュールをインストールしました。" -ForegroundColor Green
    }
    else {
        $absPath = [System.IO.Path]::GetFullPath($requirementsPath)
        Write-Warning "$absPath が見つかりませんでした。"
        Write-Host "処理を中断します。" -ForegroundColor Yellow
        exit 1
    }

    Write-Host "Python $version の組み込み版セットアップが完了しました。" -ForegroundColor Green

    # Releaseフォルダに run.bat を作成（Shift JISで保存）
    Write-Host "`n== Releaseフォルダに run.bat を作成します =="

    function Write-ShiftJISFile {
        param (
            [string]$Path,
            [string[]]$Lines
        )
        $sjis = [System.Text.Encoding]::GetEncoding("shift_jis")
        [System.IO.File]::WriteAllLines($Path, $Lines, $sjis)
    }

    $runBatPath = Join-Path $releaseDir "run.bat"
    $runBatContent = @'
@echo off
REM run.bat - Releaseフォルダ用起動バッチ

REM このバッチのある場所をカレントディレクトリに
cd /d "%~dp0src-api"

REM Python実行ファイルのパス（Release/python310 などを自動検出）
for /d %%D in ("%~dp0python*") do (
    set PYDIR=%%~fD
)
set PYEXE=%PYDIR%\python.exe

REM main.py を実行
"%PYEXE%" source\main.py
'@ -split "`n"

    Write-ShiftJISFile -Path $runBatPath -Lines $runBatContent
    Write-Host "Releaseフォルダに run.bat をShift JISで作成しました。" -ForegroundColor Green
}
finally {
    # 元のディレクトリに戻る
    Set-Location $originalDir
}
