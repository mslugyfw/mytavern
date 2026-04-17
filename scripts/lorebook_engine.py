#!/usr/bin/env python3
"""
世界书引擎 v3 — 整合所有功能

v1: 关键词扫描 + budget + recursive
v2: 角色卡系统（char_manager.py）
v3: 向量检索 + exclude_keys + position策略 + min_activations + 多轮recursive + 角色卡集成

算法优先级：
1. constant entry → 无条件注入
2. 关键词匹配（primary + secondary keys）→ 打分
3. exclude_keys → 排除
4. 向量检索 → 补充分数
5. min_activations → 扩大扫描深度
6. budget → 逐条注入
7. recursive → 多轮链式激活（最多3轮）
8. position → 控制插入位置

Position策略：
  before_char (0) — 世界书在角色设定之前（默认，中等影响）
  after_char (1)  — 世界书在角色设定之后（高影响）
  top_author (2)  — 世界书在最顶部（最高权重）
"""

import json, sys, re
import numpy as np
from pathlib import Path
from collections import Counter
from datetime import datetime

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
LOREBOOKS_DIR = SKILL_DIR / "assets" / "lorebooks"
INDEX_DIR = SKILL_DIR / "assets" / "indices"
CHARS_DIR = SKILL_DIR / "assets" / "characters"
OUTPUT_DIR = Path("/tmp/mytavern1")

# === 默认配置 ===
DEFAULT_DEPTH = 4
DEFAULT_SCAN_DEPTH = 10
BUDGET_PERCENT = 25
BUDGET_CAP = 0  # 0=不封顶
MAX_RECURSIVE_ROUNDS = 3
N_GRAM = 3

# Position策略
POS_BEFORE_CHAR = 0
POS_AFTER_CHAR = 1
POS_TOP_AUTHOR = 2


def estimate_tokens(text):
    cn = len(re.findall(r'[\u4e00-\u9fff]', text))
    en = len(text) - cn
    return int(cn * 1.5 + en * 0.25)


def extract_ngrams(text, n=N_GRAM):
    text = re.sub(r'\s+', '', text)
    if len(text) < n:
        return {}
    grams = [text[i:i+n] for i in range(len(text) - n + 1)]
    return dict(Counter(grams))


def cosine_similarity(v1, v2):
    if not v1 or not v2:
        return 0.0
    all_keys = set(v1.keys()) | set(v2.keys())
    if not all_keys:
        return 0.0
    key_list = list(all_keys)
    idx = {k: i for i, k in enumerate(key_list)}
    a = np.zeros(len(key_list))
    b = np.zeros(len(key_list))
    for k, val in v1.items():
        a[idx[k]] = val
    for k, val in v2.items():
        b[idx[k]] = val
    dot = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot / (norm_a * norm_b))


def load_lorebook(era_id):
    fpath = LOREBOOKS_DIR / f"{era_id}.json"
    if not fpath.exists():
        return None
    with open(fpath, encoding="utf-8") as f:
        return json.load(f)


def load_vector_index(lorebook_id):
    db_path = INDEX_DIR / f"{lorebook_id}_vectors.db"
    if not db_path.exists():
        return None
    import sqlite3
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute("SELECT entry_key, name, ngrams_json FROM vectors")
    index = {}
    for row in cur.fetchall():
        index[row[0]] = {
            "name": row[1],
            "ngrams": json.loads(row[2])
        }
    conn.close()
    return index


def format_entry_compact(e):
    name = e.get("name", "")
    content = e.get("content", "")
    group = e.get("group", "")
    ref = e.get("extensions", {}).get("ref_count", 0)
    
    content = re.sub(r'\[\d+\] ', '', content)
    content = re.sub(r'#{1,4} ', '', content)
    content = re.sub(r'\[\d+\.\d+\] ', '', content)
    content = re.sub(r'\n{2,}', '\n', content).strip()
    
    if len(content) > 200:
        content = content[:200] + "…"
    
    lines = [f"[{group}]{name}"]
    if ref > 0:
        lines[0] += f"({ref})"
    lines.append(content)
    return "\n".join(lines)


def check_world_info(lorebook, chat_messages, max_context_tokens=8000,
                     vector_index=None, min_activations=0, min_depth_max=100,
                     keyword_weight=0.6, vector_weight=0.4):
    """
    世界书检查 v3 — 完整版
    
    Args:
        lorebook: 世界书JSON
        chat_messages: 最近N条消息
        max_context_tokens: 总context token数
        vector_index: 预加载的向量索引（可选）
        min_activations: 最低激活数（不够则扩大扫描深度）
        min_depth_max: 扩大扫描的最大深度
        keyword_weight: 关键词匹配权重
        vector_weight: 向量相似度权重
    
    Returns:
        tuple: (activated_entries, before_char_context, after_char_context, top_author_context, stats)
    """
    budget_cap = lorebook.get("extensions", {}).get("budget_cap", BUDGET_CAP)
    budget_tokens = int(max_context_tokens * BUDGET_PERCENT / 100)
    if budget_cap > 0:
        budget_tokens = min(budget_tokens, budget_cap)
    
    entries = list(lorebook.get("entries", {}).values())
    global_recursive = lorebook.get("recursive_scanning", False)
    
    # 构建搜索buffer
    scan_depth = DEFAULT_SCAN_DEPTH
    buffer_text = "\x01".join(m.strip() for m in chat_messages[-scan_depth:])
    buffer_text_lower = buffer_text.lower()
    
    # 查询向量
    query_ngrams = extract_ngrams(buffer_text) if vector_index else None
    
    # === 第1步：评分 ===
    scored = []
    
    for e in entries:
        if e.get("constant", False):
            scored.append((e, float('inf'), "constant"))
            continue
        
        # exclude_keys检查
        exclude_keys = e.get("exclude_keys", [])
        case_sensitive = e.get("case_sensitive", False)
        search_buf = buffer_text if case_sensitive else buffer_text_lower
        
        excluded = False
        for ek in exclude_keys:
            k = ek if case_sensitive else ek.lower()
            if k in search_buf:
                excluded = True
                break
        if excluded:
            continue
        
        # 关键词匹配
        keys = e.get("keys", [])
        secondary_keys = e.get("secondary_keys", [])
        
        primary_score = 0
        for key in keys:
            k = key if case_sensitive else key.lower()
            if k in search_buf:
                primary_score += 1
        
        secondary_score = 0
        for key in secondary_keys:
            k = key if case_sensitive else key.lower()
            if k in search_buf:
                secondary_score += 1
        
        selective = e.get("selective", False)
        if selective and secondary_keys:
            total_kw = (primary_score + secondary_score) if secondary_score == len(secondary_keys) else primary_score
        else:
            total_kw = primary_score + secondary_score
        
        # 向量分数
        vec_score = 0.0
        if query_ngrams and vector_index:
            entry_key = None
            for k, v in lorebook.get("entries", {}).items():
                if v is e:
                    entry_key = k
                    break
            if entry_key and entry_key in vector_index:
                entry_ngrams = vector_index[entry_key]["ngrams"]
                vec_score = cosine_similarity(query_ngrams, entry_ngrams)
        
        # 混合分数
        if primary_score > 0:
            total = keyword_weight * total_kw + vector_weight * vec_score
            scored.append((e, total, "keyword+vector"))
        elif vec_score > 0.05:
            total = vector_weight * vec_score
            scored.append((e, total, "vector_only"))
    
    # === 第2步：min_activations检查 ===
    if min_activations > 0 and len(scored) < min_activations:
        # 扩大扫描深度
        while scan_depth < min_depth_max and len(scored) < min_activations:
            scan_depth += DEFAULT_DEPTH
            buffer_text = "\x01".join(m.strip() for m in chat_messages[-scan_depth:])
            buffer_text_lower = buffer_text.lower()
            search_buf = buffer_text_lower
            
            for e in entries:
                already_scored = any(s[0] is e for s in scored)
                if already_scored or e.get("constant"):
                    continue
                
                exclude_keys = e.get("exclude_keys", [])
                excluded = False
                for ek in exclude_keys:
                    if ek.lower() in search_buf:
                        excluded = True
                        break
                if excluded:
                    continue
                
                keys = e.get("keys", [])
                primary_score = sum(1 for k in keys if k.lower() in search_buf)
                if primary_score > 0:
                    scored.append((e, float(primary_score), "min_activation"))
    
    # === 第3步：排序 ===
    scored.sort(key=lambda x: (-x[1], x[0].get("insertion_order", 100)))
    
    # === 第4步：budget注入 ===
    activated = []
    used_tokens = 0
    
    # constant先注入
    for e, score, source in scored:
        if score == float('inf'):
            content = format_entry_compact(e)
            activated.append((e, content))
            used_tokens += estimate_tokens(content)
    
    # 非constant
    for e, score, source in scored:
        if score == float('inf'):
            continue
        content = format_entry_compact(e)
        tokens = estimate_tokens(content)
        if used_tokens + tokens > budget_tokens:
            continue
        activated.append((e, content))
        used_tokens += tokens
    
    # === 第5步：多轮recursive ===
    if global_recursive:
        activated_keys = set()
        for e, _ in activated:
            activated_keys.add(e.get("name", ""))
        
        for round_num in range(MAX_RECURSIVE_ROUNDS):
            recurse_buffer = buffer_text
            for _, content in activated:
                recurse_buffer += "\x01" + content
            
            new_activations = 0
            for e, score, source in scored:
                if e.get("name", "") in activated_keys:
                    continue
                
                keys = e.get("keys", [])
                hit = False
                for k in keys:
                    if k.lower() in recurse_buffer.lower():
                        hit = True
                        break
                
                if hit:
                    content = format_entry_compact(e)
                    tokens = estimate_tokens(content)
                    if used_tokens + tokens <= budget_tokens:
                        activated.append((e, content))
                        used_tokens += tokens
                        activated_keys.add(e.get("name", ""))
                        new_activations += 1
            
            if new_activations == 0:
                break
    
    # === 第6步：按position分组 ===
    before_char = []
    after_char = []
    top_author = []
    
    for e, content in activated:
        pos = e.get("position", POS_BEFORE_CHAR)
        order = e.get("insertion_order", 100)
        item = (order, content)
        
        if pos == POS_TOP_AUTHOR:
            top_author.append(item)
        elif pos == POS_AFTER_CHAR:
            after_char.append(item)
        else:
            before_char.append(item)
    
    before_char.sort()
    after_char.sort()
    top_author.sort()
    
    before_ctx = "\n".join(c for _, c in before_char)
    after_ctx = "\n".join(c for _, c in after_char)
    top_ctx = "\n".join(c for _, c in top_author)
    
    stats = {
        "activated": len(activated),
        "tokens_used": used_tokens,
        "budget": budget_tokens,
        "recursive_rounds": MAX_RECURSIVE_ROUNDS if global_recursive else 0,
        "vector_enabled": vector_index is not None,
    }
    
    return activated, before_ctx, after_ctx, top_ctx, stats


def generate_context_with_character(char_name, lorebook_id, chat_messages=None,
                                     max_context_tokens=8000):
    """
    一站式：加载角色卡 + 世界书 → 生成完整context
    
    Returns:
        dict: {
            "character": {...},
            "top_author": str,
            "before_char": str, 
            "after_char": str,
            "first_mes": str,
            "stats": {...}
        }
    """
    # 加载角色卡
    char_path = CHARS_DIR / f"{char_name}.json"
    if not char_path.exists():
        return None
    
    with open(char_path, encoding="utf-8") as f:
        char = json.load(f)
    
    # 确定世界书列表
    lorebook_ids = char.get("lorebook", [lorebook_id] if lorebook_id else [])
    
    # 加载世界书
    lorebook = None
    vector_index = None
    
    for lb_id in lorebook_ids:
        lorebook = load_lorebook(lb_id)
        if lorebook:
            vector_index = load_vector_index(lb_id)
            break
    
    # 生成时代背景
    top_ctx = ""
    if lorebook:
        era = lorebook.get("extensions", {}).get("era", "")
        era_intros = {
            "wudai": "你身处上古时代。黄帝、尧、舜、禹的传说在口耳间流传。",
            "chunqiu": "你身处春秋时代。诸侯争霸，百家争鸣。",
            "zhanguo": "你身处战国时代。七雄并立，合纵连横。",
            "qin": "你身处秦朝。始皇一统六国，书同文车同轨。",
            "chuhan": "你身处楚汉相争之际。项羽与刘邦争夺天下。",
            "xihan": "你身处西汉王朝。文景之治后武帝开疆拓土。",
        }
        name = lorebook.get("name", "")
        desc = lorebook.get("description", "")
        intro = era_intros.get(era, "你身处中国古代。")
        top_ctx = f"# {name}\n\n{intro}\n\n{desc}\n"
    
    # 角色设定
    char_ctx = ""
    if char.get("system_prompt"):
        char_ctx += f"## 角色设定\n{char['system_prompt']}\n"
    if char.get("personality"):
        char_ctx += f"## 性格\n{char['personality']}\n"
    if char.get("scenario"):
        char_ctx += f"## 场景\n{char['scenario']}\n"
    if char.get("mes_example"):
        char_ctx += f"## 对话风格\n{char['mes_example']}\n"
    
    # 世界书动态匹配
    before_ctx = ""
    after_ctx = ""
    stats = {"activated": 0, "tokens_used": 0, "budget": 0}
    
    if lorebook and chat_messages:
        _, before_ctx, after_ctx, _, stats = check_world_info(
            lorebook, chat_messages, max_context_tokens, vector_index,
            min_activations=3
        )
    elif lorebook:
        # 无聊天记录时，加载高频entry
        entries = list(lorebook.get("entries", {}).values())
        entries.sort(key=lambda e: -e.get("extensions", {}).get("ref_count", 0))
        used = estimate_tokens(top_ctx + char_ctx)
        budget = 4000
        seen = set()
        parts = []
        for e in entries[:30]:
            h = e.get("content", "")[:80]
            if h in seen:
                continue
            seen.add(h)
            block = format_entry_compact(e)
            t = estimate_tokens(block)
            if used + t > budget:
                break
            parts.append(block)
            used += t
        before_ctx = "\n".join(parts)
        stats = {"activated": len(parts), "tokens_used": used, "budget": budget}
    
    return {
        "character": char,
        "top_author": top_ctx,
        "before_char": before_ctx,
        "after_char": after_ctx,
        "first_mes": char.get("first_mes", ""),
        "stats": stats,
    }


def main():
    if len(sys.argv) < 2:
        print("世界书引擎 v3")
        print("\n命令:")
        print("  load <世界书ID> [--static]        加载世界书")
        print("  check <世界书ID> <消息文本>        测试世界书匹配")
        print("  context <角色名> [世界书ID]        生成角色+世界书context")
        print("  search <世界书ID> <查询>           向量检索")
        sys.exit(0)
    
    cmd = sys.argv[1]
    
    if cmd == "load":
        if len(sys.argv) < 3:
            print("用法: load <世界书ID> [--static]")
            sys.exit(1)
        lorebook = load_lorebook(sys.argv[2])
        if not lorebook:
            print(f"❌ 世界书不存在: {sys.argv[2]}")
            sys.exit(1)
        print(f"✅ {lorebook.get('name')}")
        print(f"   entry: {len(lorebook.get('entries', {}))}")
        
        if "--static" in sys.argv:
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            result = generate_context_with_character(None, sys.argv[2])
            # 简化版：只生成世界书context
            entries = list(lorebook.get("entries", {}).values())
            entries.sort(key=lambda e: -e.get("extensions", {}).get("ref_count", 0))
            era = lorebook.get("extensions", {}).get("era", "")
            era_intros = {
                "wudai": "你身处上古时代。", "chunqiu": "你身处春秋时代。",
                "zhanguo": "你身处战国时代。", "qin": "你身处秦朝。",
                "chuhan": "你身处楚汉相争之际。", "xihan": "你身处西汉王朝。",
            }
            ctx = f"# {lorebook.get('name')}\n\n{era_intros.get(era, '')}\n\n"
            used = estimate_tokens(ctx)
            budget = 4000
            seen = set()
            for e in entries:
                h = e.get("content", "")[:80]
                if h in seen:
                    continue
                seen.add(h)
                block = format_entry_compact(e) + "\n"
                t = estimate_tokens(block)
                if used + t > budget:
                    break
                ctx += block
                used += t
            out = OUTPUT_DIR / "current_context.md"
            with open(out, 'w', encoding='utf-8') as f:
                f.write(ctx)
            print(f"   预估token: {used}")
            print(f"   输出: {out}")
    
    elif cmd == "check":
        if len(sys.argv) < 4:
            print("用法: check <世界书ID> <消息文本>")
            sys.exit(1)
        lorebook = load_lorebook(sys.argv[2])
        if not lorebook:
            print(f"❌ 世界书不存在: {sys.argv[2]}")
            sys.exit(1)
        query = " ".join(sys.argv[3:])
        msgs = [query]
        vec_idx = load_vector_index(sys.argv[2])
        activated, before, after, top, stats = check_world_info(
            lorebook, msgs, 8000, vec_idx, min_activations=3
        )
        print(f"📊 匹配结果: {stats['activated']}个entry, {stats['tokens_used']}tokens")
        for e, content in activated[:10]:
            print(f"  [{e.get('group','')}] {e.get('name','')}")
            print(f"    {content[:80]}")
    
    elif cmd == "context":
        if len(sys.argv) < 3:
            print("用法: context <角色名> [世界书ID]")
            sys.exit(1)
        lb_id = sys.argv[3] if len(sys.argv) > 3 else None
        result = generate_context_with_character(sys.argv[2], lb_id)
        if not result:
            print(f"❌ 角色不存在: {sys.argv[2]}")
            sys.exit(1)
        print(f"🎭 {result['character']['name']}")
        print(f"   激活: {result['stats']['activated']}个entry")
        print(f"   Token: {result['stats']['tokens_used']}")
        if result['first_mes']:
            print(f"   开场白: {result['first_mes'][:60]}")
    
    elif cmd == "search":
        if len(sys.argv) < 4:
            print("用法: search <世界书ID> <查询>")
            sys.exit(1)
        from build_vector_index import search
        results = search(sys.argv[2], " ".join(sys.argv[3:]), 5, min_similarity=0.01)
        for name, group, sim, preview, rc, key in results:
            print(f"  {name} [{group}] sim={sim:.4f}")
    
    else:
        print(f"❌ 未知命令: {cmd}")


if __name__ == "__main__":
    main()
