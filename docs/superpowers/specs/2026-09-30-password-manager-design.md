# パスワード管理アプリ 設計書

- 作成日: 2026-09-30
- 対象: Android（Flet 1.0.2 / Python、`flet build apk` で配布）
- 状態: レビュー待ち

## 1. 目的と前提

自分の Android 端末で日常的に使うパスワード管理アプリを作る。

| 区分 | 内容 |
|---|---|
| ユーザー指定 | Android で使用 / DB は SQLite / 入力項目はタイトル・ID・パスワード・URL・メモ / ドメイン駆動設計 |
| 合意事項 | マスターパスワード＋暗号化（案1: 項目を暗号化、DB ファイル全体の暗号化はしない）/ 全項目を暗号化（タイトル含む）/ パスワード生成・コピー＆自動消去・自動ロック・バックアップ（＋マスターパスワード変更）を追加 |
| 前提（仮定） | 利用者は1人・端末1台。クラウド同期なし。登録件数は数百件程度 |

### 成功の基準

- 端末から SQLite ファイルを取り出しても、マスターパスワードなしではどの項目も読めない
- 一覧・検索・追加・編集・削除が Android 実機で動く
- バックアップファイルから別端末（または再インストール後）に復元できる

### 対象外

生体認証、クラウド同期、複数ユーザー、ブラウザ自動入力、カテゴリ・タグ。

## 2. アーキテクチャ（DDD 4層）

```
src/
├── main.py                      # エントリポイント。依存の組み立てのみ
├── domain/                      # 業務ルール。Flet・SQLite・暗号に依存しない
│   ├── credential.py            # Credential エンティティ + 値オブジェクト
│   ├── password_generator.py    # PasswordGenerator（ドメインサービス）
│   ├── repository.py            # CredentialRepository（抽象）
│   └── errors.py                # ValidationError など
├── application/                 # ユースケース
│   ├── vault_service.py         # 初期設定・ロック解除・ロック・マスターPW変更
│   ├── credential_service.py    # 一覧・検索・追加・編集・削除
│   └── backup_service.py        # エクスポート・インポート
├── infrastructure/
│   ├── crypto.py                # scrypt 鍵導出・AES-GCM 暗号化
│   ├── database.py              # 接続・スキーマ作成
│   └── sqlite_repository.py     # CredentialRepository 実装（暗号化して保存）
└── presentation/                # Flet UI
    ├── app.py                   # 画面遷移・自動ロック・クリップボード自動消去
    └── views/                   # setup / unlock / list / edit / generator / settings
```

依存方向: `presentation → application → domain`。`infrastructure` は `domain` の抽象を実装する。組み立ては `main.py` で行う。

## 3. ドメインモデル

### Credential（エンティティ）

| 属性 | 型 | ルール |
|---|---|---|
| id | `CredentialId` | UUID4 文字列。生成時に採番 |
| title | `Title` | 必須、前後空白除去、1〜100文字 |
| login_id | `str` | 任意、256文字まで |
| password | `Password` | 必須、1〜256文字。`repr`/`str` は `********` |
| url | `Url \| None` | 任意。入力時は `http://` または `https://` で始まり、ホスト部があること |
| memo | `str` | 任意、2000文字まで |
| created_at / updated_at | `datetime`（UTC） | 更新時に `updated_at` を更新 |

- 生成: `Credential.create(title, login_id, password, url, memo)`
- 更新: `credential.update(...)` が値オブジェクトを検証し `updated_at` を更新
- ルール違反は `ValidationError(field, message)` を送出する（UI はフィールド単位で表示）

### PasswordGenerator（ドメインサービス）

- 長さ 8〜64（初期値 16）
- 文字種: 小文字・大文字・数字・記号（初期値すべて ON）。最低1種必須
- 選んだ文字種を最低1文字ずつ含める
- 乱数は `secrets`（`SystemRandom` でシャッフル）

### CredentialRepository（抽象）

`list_all() / get(id) / add(c) / update(c) / delete(id)`。検索はアプリケーション層で、復号済みの一覧に対して行う（全項目が暗号化されているため）。

## 4. 暗号化と保存

### 鍵

- マスターパスワード: 8文字以上
- 鍵導出: scrypt（n=2^15, r=8, p=1, 32バイト）、ソルト 16バイト（初期設定時にランダム生成）
- 鍵はメモリ上のみ保持。ロック時に参照を破棄する（Python では確実なメモリ消去はできない。これは許容する制約とする）

### 暗号化

- AES-256-GCM（`cryptography` ライブラリ）。1レコードごとにランダムな 12バイト nonce
- 1レコードの全項目（title, login_id, password, url, memo）を JSON にまとめて1つの暗号文にする
- レコード ID を AAD（付加認証データ）に使い、暗号文を別レコードに入れ替えられないようにする
- 保存形式: `nonce(12) || ciphertext+tag`

### スキーマ（SQLite、ファイルは `FLET_APP_STORAGE_DATA/vault.db`）

```sql
CREATE TABLE vault_meta (
  id          INTEGER PRIMARY KEY CHECK (id = 1),
  kdf_salt    BLOB    NOT NULL,
  kdf_n       INTEGER NOT NULL,
  kdf_r       INTEGER NOT NULL,
  kdf_p       INTEGER NOT NULL,
  verifier    BLOB    NOT NULL,   -- 定数 "passwordapp-vault-v1" を暗号化したもの
  schema_version INTEGER NOT NULL
);
CREATE TABLE credentials (
  id         TEXT PRIMARY KEY,
  payload    BLOB NOT NULL,       -- 暗号文
  created_at TEXT NOT NULL,       -- ISO8601 UTC
  updated_at TEXT NOT NULL
);
```

作成日時・更新日時は平文で保存する。並べ替え・バックアップのマージに使うため。一覧はタイトル順（復号後に並べ替え）。

### Vault の状態

- `vault_meta` が無い → 初期設定画面
- ある → ロック解除画面。入力したパスワードから鍵を導出し、`verifier` を復号できれば解除
- 5回続けて失敗したら 30秒間入力を受け付けない（アプリのメモリ上で数える）
- マスターパスワード変更: 現パスワードを確認 → 新しいソルトで鍵を再導出 → 全レコードを1トランザクションで再暗号化し、`vault_meta` を更新

## 5. バックアップ

- エクスポート: JSON ファイル `passwordapp-backup-YYYYMMDD.json`

  ```json
  {"format": "passwordapp-backup", "version": 1,
   "kdf": {"salt": "<b64>", "n": 32768, "r": 8, "p": 1},
   "verifier": "<b64>",
   "credentials": [{"id": "...", "payload": "<b64>", "created_at": "...", "updated_at": "..."}]}
  ```

  中身は DB の暗号文のままなので、平文は含まれない。保存は `FilePicker.save_file(src_bytes=...)` で行う。
- インポート: `FilePicker.pick_files(with_data=True)` でファイルを選ぶ → バックアップ作成時のマスターパスワードを入力 → verifier で確認 → 各レコードを復号し、現在の鍵で再暗号化して保存
  - 同じ ID のレコードは、バックアップ側の `updated_at` が新しい場合のみ上書きし、それ以外はスキップ
  - 結果として「追加 n件 / 更新 n件 / スキップ n件」を表示
  - 形式が不正、または復号に失敗した場合は1件も書き込まない（1トランザクションで処理）

## 6. 画面と操作の流れ

```
起動 ─┬─ 未設定 → [初期設定] ─────────┐
      └─ 設定済 → [ロック解除] ───────┤
                                      ▼
                                   [一覧] ─ 検索ボックス（タイトル・ID・URL・メモを部分一致、大文字小文字を区別しない）
                                     │  各行: タイトル / ID、ID コピー・パスワードコピーボタン
                                     ├─ タップ / ＋ボタン → [編集]（新規・既存）
                                     │     表示/非表示切替、生成ボタン → [生成]、保存、削除（確認ダイアログ）
                                     ├─ メニュー → [パスワード生成]（長さスライダー・文字種チェック・コピー）
                                     ├─ メニュー → [設定]（マスターPW変更・エクスポート・インポート）
                                     └─ メニュー → ロック
```

- **コピー＆自動消去**: `Clipboard.set` でコピーし「30秒後に消去します」と表示する。30秒後、クリップボードの中身がまだ同じ値なら空文字で上書きする（別の内容がコピーされていたら触らない）
- **自動ロック**:
  - `on_app_lifecycle_state_change` で、アプリがバックグラウンドに回った（hide / pause）らすぐにロック
  - 画面操作が5分間なければロック（各操作ハンドラでタイマーをリセット）
  - ロック時は鍵を破棄し、復号済みデータの参照を消して、ロック解除画面へ移る
- 編集画面を開いたまま自動ロックされた場合、未保存の入力は破棄する

## 7. エラー処理

| 状況 | 対応 |
|---|---|
| 入力ルール違反（`ValidationError`） | 該当フィールドの下にエラー文を表示。保存しない |
| マスターパスワード違い | 「パスワードが違います」＋失敗回数カウント |
| 個別レコードの復号失敗（改ざん・破損） | そのレコードを一覧から除外し、「読めないデータが n件あります」と警告 |
| DB エラー | SnackBar で表示。トランザクションはロールバック |
| バックアップ形式不正 / 復号失敗 | ダイアログで理由を表示。何も書き込まない |

## 8. テスト

- `pytest` によるユニットテスト（`tests/` 配下、層ごとにファイルを分ける）
  - domain: 値オブジェクトの検証ルール、`Credential` の作成・更新、生成器（長さ・文字種の保証・範囲外エラー）
  - infrastructure: 暗号化→復号の往復、鍵違い・改ざん・AAD 違いで失敗すること、SQLite に平文が残らないこと（DB ファイルのバイト列に入力文字列が含まれない）
  - application: 初期設定→解除→ロック、検索、マスターPW変更後に旧パスワードで開けず新パスワードで全件読めること、エクスポート→別 DB へインポート（マージ規則・失敗時に何も書き込まれないこと）
  - テストでは scrypt のパラメータを小さくして速度を確保する（本番値は定数で固定）
- UI: Flet の統合テスト（`flet[test]`）で「初期設定 → 登録 → 一覧に出る」を1本。加えて Android 実機で手動確認

## 9. 依存関係と Android ビルド

- `pyproject.toml` の dependencies に `cryptography` を追加する（`sqlite3`・`secrets` は標準ライブラリ）
- リスク: `cryptography` はネイティブ拡張を含む。Flet の Android ビルドは事前ビルド済みパッケージを使う想定だが、実装の早い段階で `flet build apk` を試して確認する。使えなかった場合は代替策（例: `pycryptodome`）を検討する
- 既存のテンプレート（カウンターのサンプル `src/main.py`、`tests/test_main.py`）は置き換える
