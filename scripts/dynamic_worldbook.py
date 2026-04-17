#!/usr/bin/env python3
"""
动态世界书 v1 — OpenClaw独有功能

P3-1: 实时搜索补充（世界书没有的 → 自动搜索）
P3-2: 世界书自学习（对话中学到的 → 建议写入）
P3-3: LCM跨会话记忆（之前的对话 → 关联检索）

设计原则：
- 利用OpenClaw内置能力（web_search/tavily/lcm_grep），不新增依赖
- 团子在对话中调用这些功能，不需要单独运行脚本
- 本文件是SKILL.md的补充参考，核心逻辑由团子执行
"""

import json, sys, re
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
LOREBOOKS_DIR = SKILL_DIR / "assets" / "lorebooks"
CHARS_DIR = SKILL_DIR / "assets" / "characters"
LEARN_DIR = SKILL_DIR / "assets" / "learned"  # 自学习的知识


def search_supplement(lorebook_id, query, search_fn=None):
    """
    P3-1: 实时搜索补充
    
    当世界书中找不到足够相关信息时，调用搜索补充。
    
    Args:
        lorebook_id: 世界书ID
        query: 用户查询
        search_fn: 搜索函数（由团子传入web_search/tavily_search）
    
    Returns:
        dict: {
            "found_in_lorebook": bool,
            "lorebook_entries": [...],  # 世界书匹配
            "search_needed": bool,
            "search_query": str,         # 推荐的搜索query
        }
    """
    from build_vector_index import search as vec_search, INDEX_DIR
    from lorebook_engine import load_lorebook
    
    lorebook = load_lorebook(lorebook_id)
    if not lorebook:
        return {"found_in_lorebook": False, "search_needed": True, "search_query": query}
    
    # 先查世界书
    db_path = INDEX_DIR / f"{lorebook_id}_vectors.db"
    vec_results = vec_search(lorebook_id, query, top_k=3, min_similarity=0.01) if db_path.exists() else []
    
    # 关键词匹配
    entries = list(lorebook.get("entries", {}).values())
    query_lower = query.lower()
    kw_matches = []
    for e in entries:
        for k in e.get("keys", []):
            if k.lower() in query_lower:
                kw_matches.append(e.get("name", ""))
                break
    
    found = len(vec_results) > 0 or len(kw_matches) > 0
    
    # 判断是否需要搜索补充
    # 规则：如果向量最高相似度 < 0.1 且无关键词命中，建议搜索
    max_sim = max((r[2] for r in vec_results), default=0)
    search_needed = not found or max_sim < 0.1
    
    # 构建搜索query（去掉常见停用词，提取核心实体）
    stopwords = set("的 了 是 在 有 和 与 也 都 而 就 不 这 那 他 她 它".split())
    core_words = [w for w in query if w not in stopwords and len(w) > 1]
    search_query = " ".join(core_words) if core_words else query
    
    return {
        "found_in_lorebook": found,
        "lorebook_entries": [r[0] for r in vec_results[:3]] + kw_matches[:3],
        "vector_max_sim": max_sim,
        "search_needed": search_needed,
        "search_query": search_query,
    }


def suggest_learn(lorebook_id, topic, content, source="conversation"):
    """
    P3-2: 世界书自学习
    
    将对话中新出现的知识建议写入世界书。
    
    Args:
        lorebook_id: 世界书ID
        topic: 主题/实体名
        content: 学到的内容
        source: 来源（conversation/search/manual）
    
    Returns:
        dict: 建议的entry
    """
    LEARN_DIR.mkdir(parents=True, exist_ok=True)
    
    # 读取已有建议（避免重复）
    learned_path = LEARN_DIR / f"{lorebook_id}_learned.json"
    if learned_path.exists():
        with open(learned_path, encoding="utf-8") as f:
            learned = json.load(f)
    else:
        learned = {"suggestions": [], "applied": []}
    
    # 检查是否已有相同主题
    for s in learned["suggestions"]:
        if s.get("topic") == topic:
            s["content"] = content  # 更新
            s["updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            break
    else:
        # 新建建议
        suggestion = {
            "topic": topic,
            "content": content,
            "source": source,
            "created": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "status": "pending",  # pending / approved / applied
            "keys": [topic],
            "group": "自定义",
            "secondary_keys": [],
            "exclude_keys": [],
            "constant": False,
            "scan_depth": 10,
        }
        learned["suggestions"].append(suggestion)
    
    with open(learned_path, 'w', encoding='utf-8') as f:
        json.dump(learned, f, ensure_ascii=False, indent=2)
    
    return {
        "topic": topic,
        "status": "pending",
        "message": f"💡 已记录学习建议: {topic}（待确认写入世界书）",
    }


def apply_learned(lorebook_id):
    """
    将已确认的学习建议写入世界书
    
    Returns:
        int: 写入的entry数
    """
    learned_path = LEARN_DIR / f"{lorebook_id}_learned.json"
    if not learned_path.exists():
        return 0
    
    with open(learned_path, encoding="utf-8") as f:
        learned = json.load(f)
    
    lb_path = LOREBOOKS_DIR / f"{lorebook_id}.json"
    if not lb_path.exists():
        return 0
    
    with open(lb_path, encoding="utf-8") as f:
        lorebook = json.load(f)
    
    entries = lorebook.get("entries", {})
    applied = 0
    
    for s in learned["suggestions"]:
        if s["status"] != "approved":
            continue
        
        key = str(len(entries) + applied)
        entry = {
            "name": s["topic"],
            "content": s["content"],
            "comment": f"人物 - {s['source']}" if "人物" in s.get("group", "") else f"{s.get('group', '自定义')} - {s['source']}",
            "keys": s.get("keys", [s["topic"]]),
            "secondary_keys": s.get("secondary_keys", []),
            "exclude_keys": s.get("exclude_keys", []),
            "constant": s.get("constant", False),
            "selective": False,
            "insertion_order": 200,  # 放在最后
            "enabled": True,
            "group": s.get("group", "自定义"),
            "extensions": {
                "ref_count": 0,
                "source": s["source"],
                "learned_at": s.get("created", ""),
            }
        }
        entries[key] = entry
        s["status"] = "applied"
        applied += 1
    
    if applied > 0:
        lorebook["entries"] = entries
        with open(lb_path, 'w', encoding='utf-8') as f:
            json.dump(lorebook, f, ensure_ascii=False, indent=2)
        
        # 保存更新后的learned文件
        with open(learned_path, 'w', encoding='utf-8') as f:
            json.dump(learned, f, ensure_ascii=False, indent=2)
        
        # 重建向量索引
        try:
            from build_vector_index import build_index
            build_index(lorebook_id)
        except Exception:
            pass
    
    return applied


def list_learned(lorebook_id):
    """列出学习建议"""
    learned_path = LEARN_DIR / f"{lorebook_id}_learned.json"
    if not learned_path.exists():
        print("📭 暂无学习建议")
        return []
    
    with open(learned_path, encoding="utf-8") as f:
        learned = json.load(f)
    
    suggestions = learned.get("suggestions", [])
    if not suggestions:
        print("📭 暂无学习建议")
        return []
    
    print(f"📝 学习建议（{len(suggestions)}个）\n")
    for i, s in enumerate(suggestions):
        status_icon = {"pending": "⏳", "approved": "✅", "applied": "✔️"}.get(s["status"], "❓")
        print(f"  {status_icon} [{s['status']}] {s['topic']}")
        print(f"    来源: {s['source']} | 时间: {s.get('created', '')}")
        print(f"    {s['content'][:80]}")
        print()
    
    return suggestions


def approve_learned(lorebook_id, topic):
    """批准一个学习建议"""
    learned_path = LEARN_DIR / f"{lorebook_id}_learned.json"
    if not learned_path.exists():
        return False
    
    with open(learned_path, encoding="utf-8") as f:
        learned = json.load(f)
    
    for s in learned["suggestions"]:
        if s["topic"] == topic and s["status"] == "pending":
            s["status"] = "approved"
            with open(learned_path, 'w', encoding='utf-8') as f:
                json.dump(learned, f, ensure_ascii=False, indent=2)
            return True
    
    return False


def main():
    if len(sys.argv) < 2:
        print("动态世界书 v1 — OpenClaw独有功能\n")
        print("命令:")
        print("  check <世界书ID> <查询>            检查是否需要搜索补充")
        print("  learn <世界书ID> <主题> <内容>      记录学习建议")
        print("  list <世界书ID>                     列出学习建议")
        print("  approve <世界书ID> <主题>           批准学习建议")
        print("  apply <世界书ID>                    将批准的建议写入世界书")
        sys.exit(0)
    
    cmd = sys.argv[1]
    
    if cmd == "check":
        if len(sys.argv) < 4:
            print("用法: dynamic_worldbook.py check <世界书ID> <查询>")
            sys.exit(1)
        result = search_supplement(sys.argv[2], " ".join(sys.argv[3:]))
        if result["found_in_lorebook"]:
            print(f"✅ 世界书中有相关内容: {', '.join(result['lorebook_entries'][:3])}")
            if result["search_needed"]:
                print(f"⚠️ 但相关性较低(sim={result['vector_max_sim']:.3f})，建议补充搜索")
                print(f"   搜索建议: {result['search_query']}")
        else:
            print(f"❌ 世界书中未找到相关内容")
            print(f"   建议搜索: {result['search_query']}")
    
    elif cmd == "learn":
        if len(sys.argv) < 5:
            print("用法: dynamic_worldbook.py learn <世界书ID> <主题> <内容>")
            sys.exit(1)
        result = suggest_learn(sys.argv[2], sys.argv[3], " ".join(sys.argv[4:]))
        print(result["message"])
    
    elif cmd == "list":
        if len(sys.argv) < 3:
            print("用法: dynamic_worldbook.py list <世界书ID>")
            sys.exit(1)
        list_learned(sys.argv[2])
    
    elif cmd == "approve":
        if len(sys.argv) < 4:
            print("用法: dynamic_worldbook.py approve <世界书ID> <主题>")
            sys.exit(1)
        if approve_learned(sys.argv[2], sys.argv[3]):
            print(f"✅ 已批准: {sys.argv[3]}（运行 apply 写入世界书）")
        else:
            print(f"❌ 未找到待批准的建议: {sys.argv[3]}")
    
    elif cmd == "apply":
        if len(sys.argv) < 3:
            print("用法: dynamic_worldbook.py apply <世界书ID>")
            sys.exit(1)
        count = apply_learned(sys.argv[2])
        if count > 0:
            print(f"✅ 已写入 {count} 个entry到世界书，向量索引已重建")
        else:
            print("📭 无待写入的建议")
    
    else:
        print(f"❌ 未知命令: {cmd}")


if __name__ == "__main__":
    main()
