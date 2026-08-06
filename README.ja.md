# kaisetu

[English](README.md) | 日本語

https://github.com/user-attachments/assets/b3cb8d23-e147-4e56-a422-4d1b43f8576a

**AIが生成した差分のためのレビューUI — 整理と解説はAI、判断は人間。**

kaisetu（解説）は [Claude Code](https://code.claude.com) / Codex 用のエージェントスキルです。
`/kaisetu` を実行すると、コーディングエージェントが大きな差分をローカルのレビュー画面に変換します:
変更を**意図ごとにグループ化**し、**重要度順に並べ**、**解説をインラインで付けた**うえで、
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

- **一目で「何をやった変更か」が分かる** — 見出しは誰が読んでも分かる一文。その下の各行は
  「エンジニアに分かる説明 ＝ 非エンジニアにも伝わる結果」の形で書き、
  結果は矢印付きで改行して見せる。差分を1行も読む前に、変更の全体像が掴める
- **ファイル単位ではなく意図単位のグループ** — rename とそれに伴う import 修正は1グループ。
  表示は重要度順（high → medium → low）なので、注意して読むべき部分から読める
- **グループごとのファイルツリー** — そのグループがどのディレクトリに何を足したかが形で見える。
  `controller` / `service` / `infrastructure` に対応するファイルが揃っているか、
  想定した層の外に手が入っていないか — **アーキテクチャに沿った変更かどうかが、
  diff を読む前に分かる**
- **インラインのAI解説** — 機能ごとのセクション解説に加え、行レベルの補足と
  「疑問」（AIにも意図が読み取れなかった箇所）を diff 行に直接表示
- **その場で聞けて、その場で直る** — 「ここ何で？」と書けばエージェントが答え、「直して」と書けば
  直る。回答は画面のスレッドに戻ってくるので、セルフレビューを中断せずに往復できる。
  解説に「分かりにくい」と言えば書き直され、数秒で画面が入れ替わる（コメントは保持される）
- **どこにでもコメント** — diff行・概要・グループの意図・AIの解説、どれもホバーで出る `+` から
  コメントできる。自動保存（localStorage + サーバ側 state）
- **左右表示のdiff** — 左が変更前、右が変更後。削除行とそれを置き換えた追加行が同じ行に揃う。
  境界はドラッグで動かせる。ヘッダーの *Split* でユニファイド表示に切り替えられ、選択は記憶される
- **HTML そのもののレビュー** — diff の代わりに `.html` を渡すと、**レンダリング結果**にコメント層が
  重なる。要素をクリックしてコメントすると、エージェントが HTML を直し、画面はその修正を反映して
  再読み込みされる（コメントは要素に貼りついたまま）。グループ化も解説もなし、見てコメントするだけ
- **ダークモード** — OS 追従 + 手動トグル
- **依存ゼロ** — HTML テンプレート1枚 + Python 3 標準ライブラリのサーバ。npm もビルドも不要

## クイックスタート（デモ）

エージェントなしで、同梱のサンプルデータで UI を試せます:

```bash
git clone https://github.com/Rasukarusan/kaisetu.git
cd kaisetu
python3 kaisetu/scripts/serve.py kaisetu/example/sample-kidoku.ja.json   # 実在コミット23ファイルのレビュー
python3 kaisetu/scripts/serve.py kaisetu/example/sample-kidoku.json      # 同じレビューの英語版
python3 kaisetu/scripts/serve.py kaisetu/example/sample-data.json        # diff レビュー（最小例）
python3 kaisetu/scripts/serve.py kaisetu/example/sample-page-data.json   # HTML レビュー
```

ブラウザにレビュー画面が開きます。`?` でキーボードショートカット一覧。

`sample-kidoku.ja.json` は [kidoku](https://github.com/Rasukarusan/kidoku) のコミット `f0a8898`
（23ファイル・30 hunk）を6つの意図にグループ化した実物のレビューです。解説文はエージェントと
会話している言語で生成されるため、同じコミットを英語でレビューしたものが `sample-kidoku.json` です。

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
/kaisetu docs/report.html   # レンダリングされた HTML 自体をレビュー
/kaisetu-list               # 過去のレビューを一覧・再開
```

範囲指定は自由記述です。コミットハッシュ・範囲・ブランチ名・普通の言葉、
どれで指定してもエージェントがそのまま `git diff` に渡します。
`.html` ファイルを渡した場合は HTML レビューに切り替わり、iframe に描画されたページを
要素単位でコメントできます（指摘した要素には番号付きピンが付きます）。

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
| `kaisetu/example/sample-kidoku.ja.json` | デモ用データ: 実在コミットのレビュー（`sample-kidoku.json` は同じものの英語版） |
| `kaisetu/example/sample-data.json` | デモ用データ（diff レビュー・最小例） |
| `kaisetu/example/sample-page-data.json` | デモ用データ（HTML レビュー）+ `sample-page.html` |
| `kaisetu-list/SKILL.md` | 過去レビューの一覧・再開を行う補助スキル |

エージェントは `review-data.json`（groups → sections → hunks + 解説）を書いて `serve.py` を起動します。
画面とエージェントは `~/.kaisetu/<repo>/<timestamp>/` 配下のファイルを介して通信します:

- `review-data.result.json` — 「Finish review」で書き出される。エージェントが監視する
- `review-data.replies.json` — エージェントの回答。画面がポーリングしてスレッドに差し込む
- `review-data.state.json` — コメントの自動保存。リロードや別ブラウザでも復元される

サーバは `review-data.json` をリクエストごとに読み直すため、指摘を受けた解説をエージェントが
書き直すと画面が自動で作り直されます。コメントは文章ではなく hunk ID に紐づいているので消えません。

レビューの解説文は、エージェントと会話している言語で生成されます（日本語で使えば日本語で出ます）。
画面のラベルもその言語に追従するので、日本語のレビューでは「解説 / メモ / 疑問」として表示されます。

## 設計原則

- **判断は人間、提示はAI。** スキルはエージェントに批評や修正提案を明示的に禁じています。
  提示するのは事実だけ: 何が変わったか、なぜか、影響範囲はどこか。
- **重要度は評決ではなく読み順。** high / medium / low は注意の配分を示すガイドです。
- **対象リポジトリを汚さない。** 作業ファイルはすべて `~/.kaisetu/` 配下に置きます。
- **静的出力にも対応。** `serve.py --build` で単体の静的 HTML を出力でき、PR への添付や
  チームメイトへの共有に使えます。

## ライセンス

MIT
