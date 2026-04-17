#!/usr/bin/env python3
"""列出可用时代及对应世界书信息"""

import json, os
from pathlib import Path

ASSETS_DIR = Path(__file__).parent.parent / "assets" / "lorebooks"

def main():
    eras = {
        "wudai": {"name": "五帝三代", "time": "前2700-前771"},
        "chunqiu": {"name": "春秋", "time": "前770-前476"},
        "zhanguo": {"name": "战国", "time": "前475-前221"},
        "qin": {"name": "秦", "time": "前221-前207"},
        "chuhan": {"name": "楚汉", "time": "前206-前202"},
        "xihan": {"name": "西汉", "time": "前202-8"},
    }
    
    for eid, info in eras.items():
        fpath = ASSETS_DIR / f"{eid}.json"
        if fpath.exists():
            with open(fpath, encoding="utf-8") as f:
                lb = json.load(f)
            groups = {}
            for e in lb.get("entries", {}).values():
                g = e.get("group", "other")
                groups[g] = groups.get(g, 0) + 1
            gstr = ", ".join(f"{g}:{c}" for g, c in sorted(groups.items(), key=lambda x: -x[1]))
            print(f"{eid} | {info['name']} ({info['time']}) | {len(lb.get('entries',{}))} entries | {gstr}")
        else:
            print(f"{eid} | {info['name']} ({info['time']}) | ❌ 未生成")

if __name__ == "__main__":
    main()
