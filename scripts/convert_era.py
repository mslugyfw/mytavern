#!/usr/bin/env python3
"""从完整世界书拆分时代子集"""

import json, os
from pathlib import Path
from collections import Counter

SOURCE = Path("/home/neo/.openclaw/workspace/20260417史记世界书/output/shiji_complete_lorebook.json")
OUTPUT_DIR = Path(__file__).parent.parent / "assets" / "lorebooks"

# 每个时代对应的章节关键词
ERA_CHAPTERS = {
    "wudai": ["五帝", "三代", "夏本纪", "殷本纪", "周本纪", "三代世表", "五帝本纪"],
    "chunqiu": ["齐太公", "鲁周公", "晋世家", "楚世家", "郑世家", "赵世家", "魏世家",
                "韩世家", "田敬仲", "孔子", "管晏", "孙子", "吴起", "伍子胥",
                "仲尼弟子", "外戚", "齐", "鲁", "晋", "楚世家", "郑"],
    "zhanguo": ["商君", "苏秦", "张仪", "穰侯", "白起王翦", "孟子荀卿", "廉颇蔺相如",
                "田单", "吕不韦", "刺客", "李斯", "战国"],
    "qin": ["秦始皇", "始皇", "蒙恬", "李斯", "赵高", "扶苏", "胡亥", "秦本纪"],
    "chuhan": ["项羽", "高祖", "淮阴侯", "陈丞相", "绛侯", "郦生陆贾", "魏豹彭越",
                "黥布", "韩信", "萧相国", "张良"],
    "xihan": ["孝文本纪", "孝景", "孝武", "卫将军", "平津侯", "匈奴", "南越",
                "东越", "朝鲜", "西南夷", "司马相如", "汲郑", "儒林", "酷吏",
                "大宛", "游侠", "佞幸", "滑稽", "日者", "龟策", "货殖",
                "太史公", "外戚世家", "惠景间侯者", "建元以来侯者"],
}

def main():
    with open(SOURCE, encoding="utf-8") as f:
        full = json.load(f)
    
    all_entries = list(full["entries"].values())
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    for era_id, keywords in ERA_CHAPTERS.items():
        era_entries = []
        
        for e in all_entries:
            content = e.get("content", "")
            name = e.get("name", "")
            comment = e.get("comment", "")
            
            # 匹配章节标题或内容中的关键词
            for kw in keywords:
                if kw in content[:100] or kw in name or kw in comment:
                    era_entries.append(e)
                    break
        
        # 去重（按name）
        seen = set()
        unique = []
        for e in era_entries:
            if e["name"] not in seen:
                seen.add(e["name"])
                unique.append(e)
        
        era_names = {"wudai": "史记世界书·五帝三代", "chunqiu": "史记世界书·春秋",
                     "zhanguo": "史记世界书·战国", "qin": "史记世界书·秦",
                     "chuhan": "史记世界书·楚汉", "xihan": "史记世界书·西汉"}
        
        lorebook = {
            "name": era_names.get(era_id, f"史记·{era_id}"),
            "description": f"shiji-kb {era_names.get(era_id, era_id)} 子集",
            "scan_depth": 10,
            "token_budget": 4096,
            "extensions": {
                "source": "shiji-kb (CC BY-NC-SA 4.0)",
                "era": era_id
            },
            "entries": {str(i): e for i, e in enumerate(unique)}
        }
        
        out_path = OUTPUT_DIR / f"{era_id}.json"
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(lorebook, f, ensure_ascii=False, indent=2)
        
        groups = Counter(e.get("group", "?") for e in unique)
        gstr = ", ".join(f"{g}:{c}" for g, c in groups.most_common())
        size = os.path.getsize(out_path)
        print(f"{era_id}: {len(unique)} entries | {gstr} | {size/1024:.0f}KB")

if __name__ == "__main__":
    main()
