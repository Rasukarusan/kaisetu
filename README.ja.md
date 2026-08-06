# kaisetu - 緑と赤をスクロールして「見た」ことにしていた私の話

[English](README.md) | 日本語

https://github.com/user-attachments/assets/b3cb8d23-e147-4e56-a422-4d1b43f8576a

**AIが生成した差分を、人間が読める形に組み替えるレビューUI。**

**[ブラウザでデモを試す](https://rasukarusan.github.io/kaisetu/sample-kidoku.ja.html)**（インストール不要・実在コミット23ファイルのレビュー）

先に白状すると、私はAIのdiffを正直ぜんぶ読んでいませんでした。23ファイルのdiffを開いた瞬間、
そっとタブを閉じたくなる。緑と赤をスクロールで眺めて「見た」ことにして、「たぶん大丈夫」で
approve する。しかもレビューが終わらないうちに、AIは次のdiffを出してくる。

どこから読むべきか、どの変更がひとまとまりか、作者は何がしたかったのか。
人間のPRなら作者が口頭でも補ってくれる情報が、AIのdiffには付いてきません。

kaisetu（解説）は、そこを埋める [Claude Code](https://code.claude.com) / Codex 用の
エージェントスキルです。`/kaisetu` を実行すると、コーディングエージェントが大きな差分を
ローカルのレビュー画面に変換します。変更を**意図ごとにグループ化**し、**重要度順に並べ**、
**解説をインラインで付けた**うえで、画面上のコメントをそのままエージェントのセッションへ
送り返せます。

kaisetu を作ったのは、このセルフレビューをやりやすくするためです。AIに書かせた自分のdiffを、
他人のPRを読むときと同じ落ち着きで読みたい。ファイル順に diff を上から読むのは、もうやめました。

<img width="715" alt="Terminal English-selection" src="https://github.com/user-attachments/assets/ee2cf175-e408-45e4-a57d-3f8d051ae851" />

## セルフレビューを楽にする3つの特徴


- 「どこから読めばいいのか」と迷うこと → **グルーピングされます**
- 「この変更、結局なにがしたいの？」と首をかしげること → **一言説明あります**
- 「あとで聞こう」と付箋を溜めること → **その場でAIに聞けます**

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

## ライセンス

MIT
