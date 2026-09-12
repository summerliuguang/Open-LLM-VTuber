# OLLVT 前端构建说明

前端源码: `~/web-projects/Open-LLM-VTuber-Web`(Open-LLM-VTuber-Web main 分支 + 本地补丁)
后端 `frontend/` 目录是构建产物,不要直接改(会被下次构建覆盖)。

## 本地修改点(相对上游 main)

1. `src/renderer/src/context/websocket-context.tsx`:默认 WS/Base 地址改为
   `wss://192.168.5.15:29011/client-ws` / `https://192.168.5.15:29011`(局域网部署默认值)
2. `src/renderer/src/hooks/use-is-mobile.ts`(新增):手机端断点判断
3. `src/renderer/src/components/mobile/mobile-header.tsx`(新增):手机端顶栏
   (☰ 设置抽屉 + 模型名点击重命名[localStorage 按配置名保存] + 历史/新建)
4. `src/renderer/src/App.tsx`:window 模式下 isMobile 分支——全屏模型 +
   顶栏 + 底部输入条 + SettingUI 参数抽屉

## 构建与部署

```bash
cd ~/web-projects/Open-LLM-VTuber-Web
npm install --ignore-scripts --registry=https://registry.npmmirror.com   # 首次
npm run build:web                       # 输出到 dist/web
rsync -a --delete dist/web/ ~/web-projects/Open-LLM-VTuber/frontend/    # --delete 清掉旧 hash 产物
```
无需重启后端(静态文件即时生效);浏览器强刷(Ctrl+Shift+R)。

## 更新 fork 的 build 分支(子模块指针指向它)

build 分支的树 = dist/web 内容放在**仓库根**(assets/index.html/libs/favicon.ico)。
用临时 worktree 更新(不要用 GIT_INDEX_FILE+git add -A 的偷懒法:dist 被 gitignore,
-ADD 会把整个源码树加进去,或路径多一层 dist/ 前缀):

```bash
cd ~/web-projects/Open-LLM-VTuber-Web
git worktree add --detach /tmp/ollvt-build-wt origin/build
find /tmp/ollvt-build-wt -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +
cp -r dist/web/. /tmp/ollvt-build-wt/
cd /tmp/ollvt-build-wt && git add -A && git commit -m "构建:<说明>(源码 <main 分支 sha>)"
git push origin HEAD:refs/heads/build --force
cd ~/web-projects/Open-LLM-VTuber-Web && git worktree remove --force /tmp/ollvt-build-wt
```

主仓库(frontend 是 gitlink 指针,frontend/ 目录本身未初始化 .git)更新指针:

```bash
cd ~/web-projects/Open-LLM-VTuber
git update-index --cacheinfo 160000 $(git --git-dir=$HOME/web-projects/Open-LLM-VTuber-Web/.git rev-parse origin/build) frontend
git commit -m "前端子模块指针更新到 <构建说明>"
git push origin main
```
