# kaisetu

[English](README.md) | 日本語

**AIが生成した差分のためのレビューUI — 整理と解説はAI、判断は人間。**

kaisetu（解説）は [Claude Code](https://code.claude.com) / Codex 用のエージェントスキルです。
`/kaisetu` を実行すると、コーディングエージェントが大きな差分をローカルのレビュー画面に変換します:
変更を**意図ごとにグループ化**し、**リスク順に並べ**、**解説をインラインで付けた**うえで、
画面上のコメントをそのままエージェントのセッションへ送り返せます。

AIエージェントは人間がレビューできる速度を超えて差分を生み出します。kaisetu はレビューを代行しません —
変更の良し悪しを判断するのはあなたの仕事のままです。その代わり、それ以外のすべてを引き受けます:
どの hunk がひとまとまりなのか、どこから注意して読むべきか、作者（AI）が何をしようとしていたのか。

```
/kaisetu
  → エージェントが差分を収集し、hunk を意図単位にグループ化して解説を書く
  → ローカルサーバが起動し、ブラウザが開く
  → 人間が読み、diff行 / グループの意図 / 概要 / AIの解説 にコメントする
  → 「Finish review」→ コメントがエージェントのセッションに届く
  → エージェントが修正または回答し、回答は画面のスレッドに表示される
  → 返信して再送信 … 納得いくまで往復する
```

## 特徴

- **二段構えの概要** — 概要の各行を
  「エンジニアに分かる説明 ＝ 非エンジニアにも伝わる結果」の形で書くので、
  どちらの読者も一目で掴める
- **ファイル単位ではなく意図単位のグループ** — rename とそれに伴う import 修正は1グループ。
  表示はリスク順（high → medium → low）なので、危険な部分から読める
- **インラインのAI解説** — 機能ごとのセクション解説に加え、行レベルの補足と
  「疑問」（AIにも意図が読み取れなかった箇所）を diff 行に直接表示
- **どこにでもコメント** — diff行・概要・グループの意図・AIの解説、どれもホバーで出る `+` から
  コメントできる。自動保存（localStorage + サーバ側 state）
- **スレッドで往復** — エージェントの回答は画面内に表示される。「Reply」でスレッドを続け、
  「Finish review」で送り返す。未回答スレッドはヘッダーにカウント表示
- **解説はその場で書き直る** — 解説に「分かりにくい」とコメントするとエージェントが書き直し、
  数秒で画面が新しい解説に入れ替わる（コメントは保持される）
- **ダークモード** — OS 追従 + 手動トグル
- **依存ゼロ** — HTML テンプレート1枚 + Python 3 標準ライブラリのサーバ。npm もビルドも不要

## クイックスタート（デモ）

エージェントなしで、同梱のサンプルデータで UI を試せます:

```bash
git clone https://github.com/Rasukarusan/kaisetu.git
cd kaisetu
python3 kaisetu/scripts/serve.py kaisetu/example/sample-data.json
```

ブラウザにレビュー画面が開きます。`?` でキーボードショートカット一覧。

## スキルとしてインストール

### Claude Code

```bash
git clone https://github.com/Rasukarusan/kaisetu.git
ln -s "$(pwd)/kaisetu/kaisetu" ~/.claude/skills/kaisetu
ln -s "$(pwd)/kaisetu/kaisetu-list" ~/.claude/skills/kaisetu-list
```

Claude Code を再起動して:

```
/kaisetu                    # 未コミットの変更をレビュー (git diff HEAD)
/kaisetu ブランチ全体        # ベースブランチとの差分
/kaisetu abc1234            # コミット単体
/kaisetu main..HEAD         # git が理解する任意のリビジョン範囲
/kaisetu HEAD~3..HEAD       # 例: 直近3コミット
/kaisetu-list               # 過去のレビューを一覧・再開
```

範囲指定は自由記述です。コミットハッシュ・範囲・ブランチ名・普通の言葉、
どれで指定してもエージェントがそのまま `git diff` に渡します。

### Codex

同じディレクトリを Codex のスキル置き場（例: `~/.agents/skills/`）にリンクし、`$kaisetu` で
呼び出します。スキルの指示はどちらのエージェントでも動くように書かれています。

## 仕組み

| ファイル | 役割 |
|---|---|
| `kaisetu/SKILL.md` | スキル本体 — エージェントが差分を収集・グループ化・解説する手順 |
| `kaisetu/schema.md` | LLM が生成する唯一の成果物 `review-data.json` の仕様 |
| `kaisetu/template.html` | レビュー画面（自己完結・外部リソースなし） |
| `kaisetu/scripts/serve.py` | ローカルサーバ（Python 3 標準ライブラリのみ）。`--build` で静的 HTML 出力 |
| `kaisetu/example/sample-data.json` | デモ用データ |
| `kaisetu-list/SKILL.md` | 過去レビューの一覧・再開を行う補助スキル |

エージェントは `review-data.json`（groups → sections → hunks + 解説）を書いて `serve.py` を起動します。
画面とエージェントは `~/.kaisetu/<repo>/<timestamp>/` 配下のファイルを介して通信します:

- `review-data.result.json` — 「Finish review」で書き出される。エージェントが監視する
- `review-data.replies.json` — エージェントの回答。画面がポーリングしてスレッドに差し込む
- `review-data.state.json` — コメントの自動保存。リロードや別ブラウザでも復元される

サーバは `review-data.json` をリクエストごとに読み直すため、指摘を受けた解説をエージェントが
書き直すと画面が自動で作り直されます。コメントは文章ではなく hunk ID に紐づいているので消えません。

レビューの解説文は、エージェントと会話している言語で生成されます（日本語で使えば日本語で出ます）。

## 設計原則

- **判断は人間、提示はAI。** スキルはエージェントに批評や修正提案を明示的に禁じています。
  提示するのは事実だけ: 何が変わったか、なぜか、影響範囲はどこか。
- **リスクは評決ではなく読み順。** high / medium / low は注意の配分を示すガイドです。
- **対象リポジトリを汚さない。** 作業ファイルはすべて `~/.kaisetu/` 配下に置きます。
- **静的出力にも対応。** `serve.py --build` で単体の静的 HTML を出力でき、PR への添付や
  チームメイトへの共有に使えます。

## ライセンス

MIT
