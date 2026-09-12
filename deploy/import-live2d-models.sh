#!/bin/bash
# 把本地 Live2D 模型库(~/web-projects/live2d-models)里的 Cubism3/4 模型
# 导入 Open-LLM-VTuber/live2d-models/,供前端"模型切换"菜单使用。
# 约定:目录名必须与其中 <目录名>.model3.json 一致(后端 /live2d-models/info 按此扫描)。
# Cubism2(model.json/moc)不被 OLLVT WebSDK 支持,跳过。
# 用法: ./import-live2d-models.sh [模型目录名...]  不带参数=导入库里全部 model3 模型
set -euo pipefail

LIB="$HOME/web-projects/live2d-models"
DEST="$HOME/web-projects/Open-LLM-VTuber/live2d-models"
mkdir -p "$DEST"

declare -A FOUND=()

# 官方 CubismWebSamples: Samples/Resources/<Name>/<Name>.model3.json
OFFICIAL="$LIB/official/CubismWebSamples/Samples/Resources"
if [ -d "$OFFICIAL" ]; then
  for d in "$OFFICIAL"/*/; do
    name=$(basename "$d")
    [ -f "$d$name.model3.json" ] && FOUND[$name]="$d"
  done
fi

# imuncle 碧蓝航线 C3: live2d_3/model/*/<pname>/<pname>.model3.json
IMUNCLE="$LIB/imuncle/repo/live2d_3/model"
if [ -d "$IMUNCLE" ]; then
  while IFS= read -r f; do
    name=$(basename "$f" .model3.json)
    FOUND[$name]="$(dirname "$f")/"
  done < <(find "$IMUNCLE" -name "*.model3.json")
fi

imported=0; skipped=0
for name in "${!FOUND[@]}"; do
  src="${FOUND[$name]}"
  if [ $# -gt 0 ]; then
    keep=false
    for want in "$@"; do [ "$want" = "$name" ] && keep=true; done
    $keep || continue
  fi
  if [ -e "$DEST/$name" ]; then
    skipped=$((skipped+1)); continue
  fi
  cp -r "$src" "$DEST/$name"
  # 去掉 macOS 垃圾文件
  find "$DEST/$name" -name ".DS_Store" -delete 2>/dev/null || true
  echo "导入: $name"
  imported=$((imported+1))
done

echo "完成: 新导入 $imported 个,已存在跳过 $skipped 个,当前共 $(ls "$DEST" | wc -l) 个模型"
