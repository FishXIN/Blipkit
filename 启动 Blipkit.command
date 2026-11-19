#!/bin/bash
set -e
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  echo '请按 README.md 创建 .venv 并安装依赖。'
  read -r -p '按回车关闭…'
  exit 1
fi
exec .venv/bin/python main.py
