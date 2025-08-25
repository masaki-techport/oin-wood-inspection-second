# 環境構築

## 1. Chromeのインストール
Chromeをインストールして、デフォルトブラウザに設定してください。

## 2. PC、DIOデバイス、Baslerカメラを同一ネットワークに接続する

### 手順1: PCのイーサネットのIPとサブネットを固定する

### 手順2: PCと同一のネットワーク帯で、ContecDeviceUtilityでDIOデバイスのIP、サブネットを固定する
ContecDevice下記のURLからインストール  
https://app.box.com/folder/333484023644  

https://help.contec.com/pc-helper/api-tool-wdm/jp/APITOOL.htm?_gl=1*a3yb06*_ga*NjAxMDc1NjYzLjE3MzE1NTE3NTA.*_ga_K598M9BNYF*czE3NTEyNDA3MTQkbzEzOSRnMSR0MTc1MTI0MDg1NiRqNTckbDAkaDA.*_ga_BS4FMZBM5E*czE3NTEyNDA3MTQkbzEwOSRnMSR0MTc1MTI0MDg1NiRqNTckbDAkaDA.#t=start%2Findex.htm

### 手順3: PCと同一のネットワーク帯で、PylonViewerでBaslerカメラのIP、サブネットを固定する
下記からpylonをインストールするとPylonViwerもインストールされる  
https://www.baslerweb.com/ja-jp/downloads/software/

---
**注意:** 設定するIPアドレスが他の機器と重複しないようにしてください。

## 3. サポートされている最新の Visual C++ 再頒布可能パッケージのダウンロード
下記URLからインストール  
https://learn.microsoft.com/ja-jp/cpp/windows/latest-supported-vc-redist?view=msvc-170
  

## 4. リリース成果物自動生成・Python組み込み環境セットアップ

### 1. make_release.ps1 (リリース成果物自動生成)

- **用途**:
  - Reactフロントエンドのビルド・FastAPIバックエンドのRelease用成果物を自動生成します。
- **主な流れ**:
  1. 既存Releaseフォルダの削除確認
  2. setup_python.ps1の実行確認
  3. buildフォルダの再ビルド有無を確認し、run_build.ps1でReactビルド
  4. build, src-apiをReleaseにコピー（不要ファイル除外）
  5. 完了メッセージ
- **実行方法**:
  - PowerShellで右クリック「PowerShellで実行」またはターミナルで

  ```powershell
  ./make_release.ps1
  ```

- **備考**:
  - 内部で `setup_python.ps1` および `run_build.ps1` を実行します。 (詳細は下記参照)

### 2. setup_python.ps1（Release用 組み込みPythonセットアップ）

- **用途**:
  - Releaseフォルダ内にWindows組み込み版Pythonを自動セットアップします。
- **主な流れ**:
  1. 既存のRelease/python*** フォルダ削除確認
  2. Python公式サイトからバージョン選択・ダウンロード
  3. 組み込み版zipを展開・site有効化・パス追加
  4. pipインストール・requirements.txtから依存モジュール自動インストール
  5. Release/run.bat自動生成
- **実行方法**:
  - `make_release.ps1` から自動で呼び出されます
  - 単体実行する場合は、PowerShellで右クリック「PowerShellで実行」またはターミナルで

  ```powershell
  ./setup_python.ps1
  ```

### 3. run_build.ps1（Reactビルド専用スクリプト）

- **用途**:
  - Docker Container内でReactのnpm install & buildを一括実行します。
- **主な流れ**:
  1. node_modules削除確認
  2. Docker Desktop/WSL2自動判定・WSLディストリ選択
  3. docker compose runでnpm install & npm run build
- **実行方法**:
  - `make_release.ps1` から自動で呼び出されます
  - 単体実行する場合は、PowerShellで右クリック「PowerShellで実行」またはターミナルで

  ```powershell
  ./run_build.ps1
  ```

---

#### 注意

- すべてのスクリプトはPowerShell専用です。
- リリース成果物は `Release/` フォルダに生成され、 `run.bat` から実行可能です。
