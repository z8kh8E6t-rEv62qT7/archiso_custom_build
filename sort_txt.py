#!/usr/bin/env python3

import sys
from pathlib import Path


def sort_txt(file_path):
    path = Path(file_path)

    if not path.is_file():
        print(f"文件不存在: {path}")
        sys.exit(1)

    with path.open("r", encoding="utf-8") as f:
        lines = f.readlines()

    # 去掉空行，并按字典序排序
    lines = sorted(line.strip() for line in lines if line.strip())

    with path.open("w", encoding="utf-8") as f:
        for line in lines:
            f.write(line + "\n")

    print(f"排序完成: {path}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"用法: {sys.argv[0]} <txt文件路径>")
        sys.exit(1)

    sort_txt(sys.argv[1])
