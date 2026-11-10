#!/bin/sh
# 挂载的数据目录可能由 root 创建：先修正权限，再以普通用户运行
set -e
if [ "$(id -u)" = "0" ]; then
  mkdir -p "$DATA_DIR"
  chown -R app:app "$DATA_DIR"
  exec setpriv --reuid=app --regid=app --init-groups "$@"
fi
exec "$@"
