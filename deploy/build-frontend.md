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
rsync -a dist/web/ ~/web-projects/Open-LLM-VTuber/frontend/ --exclude=.git
```
无需重启后端(静态文件即时生效);浏览器强刷(Ctrl+Shift+R)。
