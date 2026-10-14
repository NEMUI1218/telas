# Blackboard 工具箱

帝京大学 Blackboard（`lms2017.teikyo-u.ac.jp`）的课程文件批量下载工具。Windows 和 macOS 都能用。

> **非官方工具**，和帝京大学、Anthology（Blackboard）都没有关系。它用的是 Blackboard 网页自己调用的内部接口，学校那边改版后可能会失效。请在遵守学校 IT 使用规定的前提下使用。

[日本語](#日本語) ・ [English](#english)

## 能做什么

- 用学籍番号和密码登录，列出你的全部课程
- 扫描一门课里的全部内容（文件夹、文件、附件），以树形列出
- 勾选后批量下载到本地，每门课一个文件夹
- 界面支持日文、英文、中文，深色和浅色两种主题
- 可以在程序里切换账号

程序**只读取**数据，不会修改 Blackboard 上的任何东西。

## 下载和安装

到右侧的 [Releases](../../releases) 页面下载：

| 系统 | 文件 | 怎么用 |
|---|---|---|
| Windows | `BlackboardTool-windows.zip` | 解压后双击 `BlackboardTool.exe` |
| macOS（M1 及以后的 Apple 芯片） | `BlackboardTool-macos.zip` | 解压，把 `BlackboardTool.app` 拖进「应用程序」 |

**Mac 第一次打开时**，因为这个程序没有苹果开发者签名，系统会拦下来：

1. 在「应用程序」里**右键**点 `BlackboardTool` → 「打开」→ 再点「打开」。
2. 如果提示「已损坏，无法打开」，打开「终端」运行下面这行，然后再打开：
   ```
   xattr -dr com.apple.quarantine /Applications/BlackboardTool.app
   ```

**Windows** 如果弹出 SmartScreen 提示，点「更多信息」→「仍要运行」。

## 你的账号存在哪里

登录成功后，学籍番号和密码会**以明文**存在你自己电脑上的这个文件夹里，方便下次自动登录：

| 系统 | 位置 |
|---|---|
| Windows | `%APPDATA%\BlackboardTool\` |
| macOS | `~/Library/Application Support/BlackboardTool/` |
| Linux | `~/.config/BlackboardTool/` |

里面是 `bb_config.json`（设置、账号、密码）和 `bb_session.json`（登录会话）。账号密码只会发给 Blackboard 服务器，不会发到任何别的地方。不想留下密码的话，用完点顶栏的「切换账号」，或者直接删掉这个文件夹。**不要把这个文件夹发给别人。**

下载的文件默认保存在「下载」文件夹下的 `Blackboard_download`，可以在下载页修改。

## 从源码运行

需要 Python 3.10 或更新的版本。

```bash
pip install -r requirements.txt
python main.py
```

## 自己打包

```bash
pip install pyinstaller
python -m PyInstaller BlackboardTool.spec --noconfirm --clean
```

Windows 上得到 `dist/BlackboardTool.exe`，macOS 上得到 `dist/BlackboardTool.app`。只能在哪个系统上打哪个系统的包。

不想自己打的话，仓库里的 GitHub Actions（`.github/workflows/build.yml`）会在 GitHub 的服务器上同时打 Windows 和 Mac 两个版本：

- 在仓库的 **Actions** 页面选 **Build** → **Run workflow**，跑完后在那次运行的 Artifacts 里下载。
- 或者推送一个 `v` 开头的标签，会自动发布到 Releases：
  ```bash
  git tag v1.0.0
  git push origin v1.0.0
  ```

## 代码结构

```
main.py                 入口
ui/                     界面（PySide6）
  main_window.py        主窗口：侧栏、顶栏、页面、底部日志
  header.py             登录框 / 已登录状态、课程选择
  download_page.py      文件树和下载
  settings_page.py      语言和主题
  sidebar.py, icons.py  侧栏和图标
services/               不依赖 Qt 的逻辑
  api_client.py         登录、会话、读取接口、下载
  downloader.py         遍历课程内容树、下载文件
utils/
  i18n.py               三种语言的文案
  theme.py              深色 / 浅色配色和样式表
  paths.py              各系统的数据目录
  config.py, signals.py, app_context.py
```

几条约定：后台线程不直接碰界面控件，一律通过 `utils/signals.py` 的信号回到主线程；界面文字都放在 `utils/i18n.py`，加文字时三种语言都要加；颜色和样式只写在 `utils/theme.py`。

## License

[MIT](LICENSE)

---

## 日本語

帝京大学 Blackboard の授業ファイルをまとめてダウンロードするツールです。Windows と macOS に対応しています。**非公式**のツールで、大学や Blackboard とは関係ありません。

- [Releases](../../releases) から自分の OS 用の zip をダウンロードして展開してください。
- Mac で初めて開くときは、アプリを**右クリック →「開く」**。「壊れている」と表示された場合は、ターミナルで `xattr -dr com.apple.quarantine /Applications/BlackboardTool.app` を実行してから開いてください。
- ログインに成功すると、学籍番号とパスワードが自分のパソコン内（上の表の場所）に**平文で**保存されます。サーバー以外には送信しません。使い終わったら「アカウント切替」で消すことができます。
- データは読み取るだけで、Blackboard 上の内容は変更しません。

## English

A tool for bulk-downloading course files from Teikyo University's Blackboard. Runs on Windows and macOS. **Unofficial**, not affiliated with the university or Blackboard.

- Download the zip for your OS from [Releases](../../releases) and unzip it.
- On a Mac, the first time: **right-click the app → Open**. If macOS says it is "damaged", run `xattr -dr com.apple.quarantine /Applications/BlackboardTool.app` in Terminal, then open it again.
- After a successful login your student ID and password are stored **in plain text** on your own computer (see the table above) and are only ever sent to the Blackboard server. Use "Switch account" to remove them.
- The tool only reads data; it never changes anything on Blackboard.
