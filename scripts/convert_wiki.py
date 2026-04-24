#!/usr/bin/env python3
"""
史记世界书转换器 v4 — 从 shiji-kb wiki pages 生成 SillyTavern V2 lorebook
数据源: /tmp/shiji-kb/wiki/public/pages.json + wiki/public/pages/*.md
"""

import json, re, os, sys
from pathlib import Path
from collections import Counter

PAGES_JSON = Path("/tmp/shiji-kb/wiki/public/pages.json")
PAGES_DIR = Path("/tmp/shiji-kb/wiki/public/pages")
OUTPUT_DIR = Path("/tmp/mytavern-shiji/assets/lorebooks")

# 时代标签 → 关键词映射（用于拆分时代子集）
ERA_KEYWORDS = {
    "wudai": ["五帝", "夏", "殷", "周本纪", "三代", "尧", "舜", "禹", "汤", "文王", "武王",
              "纣", "桀", "盘庚", "周公", "成王", "康王", "昭王", "穆王", "共王", "懿王",
              "厉王", "宣王", "幽王", "平王"],
    "chunqiu": ["齐桓", "晋文", "楚庄", "秦穆", "宋襄", "郑庄", "管仲", "鲍叔", "晏婴",
                "孔子", "老子", "孙武", "伍子胥", "申包胥", "范蠡", "西施", "勾践",
                "晋国", "齐国", "鲁国", "楚国", "郑国", "吴国", "越国", "春秋"],
    "zhanguo": ["商鞅", "苏秦", "张仪", "白起", "王翦", "廉颇", "蔺相如", "李牧",
                "信陵君", "平原君", "孟尝君", "春申君", "吕不韦", "荆轲", "乐毅",
                "赵括", "庞涓", "孙膑", "韩非", "战国"],
    "qin": ["秦始皇", "嬴政", "李斯", "赵高", "蒙恬", "扶苏", "胡亥", "子婴",
            "秦王", "秦朝", "秦二世", "焚书坑儒", "统一六国"],
    "chuhan": ["项羽", "刘邦", "韩信", "张良", "萧何", "范增", "项庄", "项伯",
               "樊哙", "彭越", "英布", "陈平", "鸿门宴", "楚汉", "垓下", "乌江"],
    "xihan": ["汉文帝", "汉景帝", "汉武帝", "卫青", "霍去病", "李广", "司马迁",
              "董仲舒", "张骞", "苏武", "晁错", "周亚夫", "窦太后", "司马相如",
              "朱买臣", "主父偃", "东方朔", "西汉", "匈奴"],
}

# 页面类型优先级和是否包含
INCLUDE_TYPES = {"person", "event", "place", "story", "overview", "concept", "state", "侯国"}
SKIP_TYPES = {"redirect", "disambiguation", "special", "list", "skill", "year"}

# 时代名映射
ERA_NAMES = {
    "wudai": "史记世界书·五帝三代",
    "chunqiu": "史记世界书·春秋",
    "zhanguo": "史记世界书·战国",
    "qin": "史记世界书·秦",
    "chuhan": "史记世界书·楚汉",
    "xihan": "史记世界书·西汉",
}

# 插入顺序（越低越先插入）
ORDER_MAP = {
    "overview": 0, "concept": 5, "state": 10, "侯国": 15,
    "person": 20, "event": 40, "place": 60, "story": 80,
}

CATEGORY_CN = {
    "person": "人物", "event": "事件", "place": "地点", "story": "故事",
    "overview": "综述", "concept": "概念", "state": "邦国", "侯国": "侯国",
}

def read_page(page_key, path_rel):
    """读取 wiki 页面 markdown 内容"""
    md_path = PAGES_DIR / path_rel
    if md_path.exists():
        return md_path.read_text(encoding="utf-8")
    # fallback: 尝试直接用 key 作为文件名
    alt = PAGES_DIR / f"{page_key}.md"
    if alt.exists():
        return alt.read_text(encoding="utf-8")
    return None

def strip_frontmatter(text):
    """移除 YAML frontmatter"""
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            return text[end+3:].strip()
    return text

def clean_wikilinks(text):
    """清理 wiki 双向链接 [[name|display]] → display, [[name]] → name"""
    text = re.sub(r'\[\[([^\]|]+)\|([^\]]+)\]\]', r'\2', text)
    text = re.sub(r'\[\[([^\]]+)\]\]', r'\1', text)
    return text

def truncate_content(text, max_chars=600):
    """截断过长内容，保持段落完整"""
    if len(text) <= max_chars:
        return text
    # 按段落截断
    paras = text.split('\n\n')
    result = []
    length = 0
    for p in paras:
        if length + len(p) > max_chars:
            break
        result.append(p)
        length += len(p)
    if result:
        return '\n\n'.join(result) + "……"
    return text[:max_chars] + "……"

def extract_secondary_keys(page_info):
    """从 aliases 和 tags 提取次要关键词"""
    keys = []
    aliases = page_info.get("aliases", [])
    if isinstance(aliases, list):
        for a in aliases:
            if isinstance(a, str) and a != page_info.get("label", ""):
                keys.append(a)
    tags = page_info.get("tags", [])
    if isinstance(tags, list):
        keys.extend(tags)
    return keys[:10]

def determine_era(name, content, tags):
    """根据名称、内容、标签判断所属时代"""
    text = f"{name} {' '.join(tags) if isinstance(tags, list) else ''} {content[:500]}"
    scores = {}
    for era, keywords in ERA_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            scores[era] = score
    if not scores:
        return None
    return max(scores, key=scores.get)

def build_entry(page_key, page_info, eid):
    """构建单个 lorebook entry"""
    page_type = page_info.get("type", "?")
    name = page_info.get("label", page_key)
    featured = page_info.get("featured", False)
    quality_score = page_info.get("quality_score", 0)

    # 读取页面内容
    raw = read_page(page_key, page_info.get("path", f"pages/{page_key}.md"))
    if raw:
        content = strip_frontmatter(raw)
        content = clean_wikilinks(content)
    else:
        content = f"{name}，见于《史记》。"

    content = truncate_content(content, 600 if not featured else 800)

    secondary = extract_secondary_keys(page_info)
    era = determine_era(name, content, page_info.get("tags", []))
    group = CATEGORY_CN.get(page_type, page_type)
    order = ORDER_MAP.get(page_type, 50)

    entry = {
        "keys": [name],
        "secondary_keys": secondary,
        "comment": f"{group}{'★' if featured else ''} qs={quality_score}",
        "content": content,
        "constant": False,
        "selective": True,
        "insertion_order": order,
        "enabled": True,
        "position": "before_char_defs",
        "case_sensitive": True,
        "name": name,
        "priority": 10,
        "id": eid,
        "group": group,
        "scan_depth": 5,
        "use_group_scoring": False,
        "extensions": {
            "type": page_type,
            "featured": featured,
            "quality_score": quality_score,
            "era": era,
            "page_key": page_key,
        }
    }
    return entry, era

def main():
    print("📖 加载 shiji-kb wiki pages...")
    with open(PAGES_JSON, encoding="utf-8") as f:
        data = json.load(f)

    pages = data["pages"]
    alias_index = data.get("alias_index", {})

    # 过滤和排序页面
    candidates = []
    for key, info in pages.items():
        ptype = info.get("type", "?")
        if ptype in SKIP_TYPES:
            continue
        # 优先精品页，其次其他
        priority = (0 if info.get("featured") else 1, -info.get("quality_score", 0))
        candidates.append((priority, key, info))

    candidates.sort(key=lambda x: x[0])
    print(f"  候选页面: {len(candidates)}")

    # 生成所有 entries
    all_entries = []
    era_map = {}  # era -> list of entries
    eid = 0

    for _, key, info in candidates:
        entry, era = build_entry(key, info, eid)
        all_entries.append(entry)
        if era:
            era_map.setdefault(era, []).append(entry)
        eid += 1

    print(f"  生成 entries: {len(all_entries)}")

    # 统计
    types = Counter(e["extensions"]["type"] for e in all_entries)
    featured_count = sum(1 for e in all_entries if e["extensions"]["featured"])
    print(f"  精品页: {featured_count}")
    for t, c in types.most_common():
        print(f"    {t}: {c}")

    era_counts = {k: len(v) for k, v in era_map.items()}
    print(f"  时代分布: {era_counts}")
    unmatched = len(all_entries) - sum(era_counts.values())
    print(f"  未匹配时代: {unmatched}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. 生成完整世界书
    print("\n📚 生成完整世界书...")
    full_lorebook = {
        "name": "史记世界书·完整版",
        "description": f"shiji-kb wiki 全量导入，{len(all_entries)}个条目，覆盖130章史记",
        "scan_depth": 10,
        "token_budget": 8192,
        "recursive_scanning": True,
        "extensions": {
            "creator": "团子(Tuanzi)",
            "source": "shiji-kb (CC BY-NC-SA 4.0)",
            "version": "2.0",
            "wiki_commit": "63c115b27",
            "total_pages": len(pages),
            "imported_entries": len(all_entries),
            "featured_entries": featured_count,
        },
        "entries": {str(e["id"]): e for e in all_entries},
    }
    full_path = OUTPUT_DIR / "complete.json"
    with open(full_path, "w", encoding="utf-8") as f:
        json.dump(full_lorebook, f, ensure_ascii=False)
    size = os.path.getsize(full_path)
    print(f"  ✅ complete.json: {len(all_entries)} entries, {size/1024/1024:.1f}MB")

    # 2. 生成时代子集
    print("\n📚 生成时代子集...")
    for era_id, entries in sorted(era_map.items()):
        lorebook = {
            "name": ERA_NAMES.get(era_id, f"史记·{era_id}"),
            "description": f"shiji-kb {ERA_NAMES.get(era_id, era_id)} 子集",
            "scan_depth": 10,
            "token_budget": 4096,
            "recursive_scanning": True,
            "extensions": {
                "source": "shiji-kb (CC BY-NC-SA 4.0)",
                "version": "2.0",
                "era": era_id,
            },
            "entries": {str(e["id"]): e for e in entries},
        }
        out_path = OUTPUT_DIR / f"{era_id}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(lorebook, f, ensure_ascii=False)
        sz = os.path.getsize(out_path)
        groups = Counter(e.get("group", "?") for e in entries)
        gstr = ", ".join(f"{g}:{c}" for g, c in groups.most_common(5))
        print(f"  ✅ {era_id}.json: {len(entries)} entries | {gstr} | {sz/1024:.0f}KB")

    # 3. 同时生成一个只含精品页的精简版
    print("\n📚 生成精简版（仅精品页）...")
    featured_entries = [e for e in all_entries if e["extensions"]["featured"]]
    featured_era = {}
    for e in featured_entries:
        era = e["extensions"].get("era")
        if era:
            featured_era.setdefault(era, []).append(e)

    # 精简完整版
    featured_lorebook = {
        "name": "史记世界书·精简版",
        "description": f"shiji-kb 精品页导入，{len(featured_entries)}个精选条目",
        "scan_depth": 10,
        "token_budget": 4096,
        "recursive_scanning": True,
        "extensions": {
            "source": "shiji-kb (CC BY-NC-SA 4.0)",
            "version": "2.0",
            "featured_only": True,
        },
        "entries": {str(e["id"]): e for e in featured_entries},
    }
    feat_path = OUTPUT_DIR / "featured.json"
    with open(feat_path, "w", encoding="utf-8") as f:
        json.dump(featured_lorebook, f, ensure_ascii=False)
    sz = os.path.getsize(feat_path)
    print(f"  ✅ featured.json: {len(featured_entries)} entries, {sz/1024:.0f}KB")

    # 精简时代子集
    for era_id, entries in sorted(featured_era.items()):
        lorebook = {
            "name": ERA_NAMES.get(era_id, f"史记·{era_id}") + "·精简",
            "description": f"shiji-kb 精品页 {era_id} 子集",
            "scan_depth": 10,
            "token_budget": 2048,
            "recursive_scanning": True,
            "extensions": {
                "source": "shiji-kb (CC BY-NC-SA 4.0)",
                "version": "2.0",
                "era": era_id,
                "featured_only": True,
            },
            "entries": {str(e["id"]): e for e in entries},
        }
        out_path = OUTPUT_DIR / f"{era_id}_featured.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(lorebook, f, ensure_ascii=False)
        sz = os.path.getsize(out_path)
        print(f"  ✅ {era_id}_featured.json: {len(entries)} entries, {sz/1024:.0f}KB")

    print(f"\n🎉 完成！共生成 {2 + len(era_map) + len(featured_era)} 个世界书文件")

if __name__ == "__main__":
    main()
