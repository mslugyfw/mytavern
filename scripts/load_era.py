#!/usr/bin/env python3
"""
世界书加载器 v2 — 参考SillyTavern world-info.js

ST核心算法:
1. scanDepth: 只扫描最近N条消息中是否出现关键词
2. scoring: primary key命中数 + secondary key命中数 → 排序
3. budget: 按百分比计算token预算（context的25%），逐条加入直到超预算
4. group_scoring: 同group的entry共享score（任一命中=全部激活）
5. insertion_order: 越小越优先插入
6. recursive: 已注入的entry内容也参与下一轮扫描（链式激活）
7. constant: 无条件注入，不受budget限制
"""

import json, sys, re
from pathlib import Path

ASSETS_DIR = Path(__file__).parent.parent / "assets" / "lorebooks"
OUTPUT_DIR = Path("/tmp/mytavern1")

# ST默认值
DEFAULT_DEPTH = 4        # 扫描最近4条消息
DEFAULT_WEIGHT = 100
DEFAULT_SCAN_DEPTH = 10   # 全局默认scan depth
BUDGET_PERCENT = 25       # context的25%用于世界书
MAX_SCAN_DEPTH = 1000

def estimate_tokens(text):
    """粗估token数（中文≈1.5，英文≈0.25）"""
    cn = len(re.findall(r'[\u4e00-\u9fff]', text))
    en = len(text) - cn
    return int(cn * 1.5 + en * 0.25)

def load_lorebook(era_id):
    fpath = ASSETS_DIR / f"{era_id}.json"
    if not fpath.exists():
        return None
    with open(fpath, encoding="utf-8") as f:
        return json.load(f)

def check_world_info(lorebook, chat_messages, max_context_tokens=8000):
    """
    参考SillyTavern checkWorldInfo()
    
    1. 扫描chat_messages中的关键词
    2. 给每个entry打分（primary+secondary keys命中数）
    3. 按score排序
    4. 按budget逐条注入
    5. 支持recursive扫描（已注入entry的content也参与匹配）
    
    Args:
        lorebook: 世界书JSON
        chat_messages: 最近N条聊天消息（列表）
        max_context_tokens: 可用总context token数
    
    Returns:
        list: 激活的entry列表，按insertion_order排序
    """
    budget_tokens = int(max_context_tokens * BUDGET_PERCENT / 100)
    
    entries = list(lorebook.get("entries", {}).values())
    buffer_text = "\x01".join(m.strip() for m in chat_messages[-DEFAULT_DEPTH:])
    buffer_text_lower = buffer_text.lower()
    
    # 1. 评分
    scored = []
    for e in entries:
        # constant entry无条件激活
        if e.get("constant", False):
            scored.append((e, float('inf'), True))
            continue
        
        case_sensitive = e.get("case_sensitive", False)
        use_group_scoring = e.get("use_group_scoring", False)
        scan_depth = e.get("scan_depth", DEFAULT_SCAN_DEPTH)
        keys = e.get("keys", [])
        secondary_keys = e.get("secondary_keys", [])
        
        # 扫描buffer
        search_buf = buffer_text if case_sensitive else buffer_text_lower
        
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
        
        # selective logic (参考ST)
        selective = e.get("selective", False)
        if selective and secondary_keys:
            # AND_ALL: 只有全部secondary命中才算
            if secondary_score == len(secondary_keys):
                total = primary_score + secondary_score
            else:
                total = primary_score  # 只计primary
        else:
            total = primary_score + secondary_score
        
        # 至少一个primary key命中才激活
        if primary_score > 0 or e.get("constant"):
            scored.append((e, total, False))
    
    # 2. 按score降序排序，score相同按insertion_order升序
    scored.sort(key=lambda x: (-x[1], x[0].get("insertion_order", 100)))
    
    # 3. 按budget注入
    activated = []
    used_tokens = 0
    
    # constant entries先注入（不受budget限制）
    for e, score, is_const in scored:
        if is_const:
            content = format_entry_compact(e)
            activated.append((e, content))
            used_tokens += estimate_tokens(content)
    
    # 非constant按score排序注入
    for e, score, is_const in scored:
        if is_const:
            continue
        content = format_entry_compact(e)
        tokens = estimate_tokens(content)
        if used_tokens + tokens > budget_tokens:
            continue
        activated.append((e, content))
        used_tokens += tokens
    
    # 4. recursive扫描（简化版：1轮）
    if lorebook.get("recursive_scanning", False):
        recurse_buffer = buffer_text
        for e, content in activated:
            recurse_buffer += "\x01" + content
        
        # 重新扫描未激活的entry
        activated_names = set(item[0]["name"] for item in activated)
        for e, score, is_const in scored:
            if e["name"] in activated_names or is_const:
                continue
            for key in e.get("keys", []):
                if key.lower() in recurse_buffer.lower():
                    content = format_entry_compact(e)
                    tokens = estimate_tokens(content)
                    if used_tokens + tokens <= budget_tokens:
                        activated.append((e, content))
                        used_tokens += tokens
                    break
    
    # 5. 按insertion_order排序输出
    activated.sort(key=lambda x: x[0].get("insertion_order", 100))
    
    return activated, used_tokens, budget_tokens

def format_entry_compact(e):
    """紧凑格式，节省token。只保留正文，去掉章节编号"""
    name = e.get("name", "")
    content = e.get("content", "")
    group = e.get("group", "")
    ref = e.get("extensions", {}).get("ref_count", 0)
    
    # 去掉章节编号标记: # [0] ... ## ... ### ...
    content = re.sub(r'\[\d+\] ', '', content)
    content = re.sub(r'#{1,4} ', '', content)
    # 去掉 [1.1] 子编号
    content = re.sub(r'\[\d+\.\d+\] ', '', content)
    # 去掉多余空行
    content = re.sub(r'\n{2,}', '\n', content)
    content = content.strip()
    
    # 截断
    if len(content) > 200:
        content = content[:200] + "…"
    
    lines = [f"[{group}]{name}"]
    if ref > 0:
        lines[0] += f"({ref})"
    lines.append(content)
    return "\n".join(lines)

def generate_static_context(lorebook):
    """生成静态context（时代背景，不含需要扫描匹配的entry）"""
    name = lorebook.get("name", "")
    desc = lorebook.get("description", "")
    era = lorebook.get("extensions", {}).get("era", "")
    
    era_intro = {
        "wudai": "你身处上古时代。黄帝、尧、舜、禹的传说在口耳间流传。青铜器刚刚出现，文字刻在龟甲上。天地之间，神与人尚未分离。",
        "chunqiu": "你身处春秋时代。周天子权威衰落，诸侯争霸。齐桓公、晋文公相继称霸。孔子带着弟子周游列国，传播仁义礼智信。",
        "zhanguo": "你身处战国时代。七雄并立，合纵连横。商鞅在秦国变法，苏秦张仪纵横捭阖。铁器普及，战争愈发残酷。",
        "qin": "你身处秦朝。秦始皇一统六国，书同文车同轨。长城绵延万里，阿房宫巍峨壮丽。然而严刑峻法之下，民怨沸腾。",
        "chuhan": "你身处楚汉相争之际。项羽力拔山兮气盖世，刘邦从沛县亭长到汉王。天下苍生在战火中挣扎求生。",
        "xihan": "你身处西汉王朝。文景之治后，汉武帝北击匈奴、通西域。丝绸之路连通东西，长安城万国来朝。",
    }
    
    intro = era_intro.get(era, "你身处中国古代。")
    return f"# {name}\n\n{intro}\n\n{desc}\n"

def main():
    if len(sys.argv) < 2:
        print("用法: python3 load_era.py <era_id> [--static]")
        print("  --static: 生成静态context（不依赖聊天内容）")
        sys.exit(1)
    
    era_id = sys.argv[1]
    static_mode = "--static" in sys.argv
    
    lorebook = load_lorebook(era_id)
    if not lorebook:
        print(f"❌ 时代 {era_id} 不存在")
        sys.exit(1)
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    if static_mode:
        # 静态模式：加载高频entry作为背景知识
        context = generate_static_context(lorebook)
        
        # 按引用次数排序加载高频entry
        entries = list(lorebook.get("entries", {}).values())
        entries.sort(key=lambda e: -e.get("extensions", {}).get("ref_count", 0))
        
        # constant去重加载
        seen_content = set()
        for e in entries:
            if not e.get("constant"):
                continue
            content_hash = e.get("content", "")[:100]
            if content_hash in seen_content:
                continue
            seen_content.add(content_hash)
            context += format_entry_compact(e) + "\n\n"
        
        used = estimate_tokens(context)
        budget = 4000
        seen_content = set()
        for e in entries:
            if e.get("constant"):
                continue
            block = format_entry_compact(e) + "\n\n"
            # 去重：跳过内容相同的entry
            content_hash = e.get("content", "")[:100]
            if content_hash in seen_content:
                continue
            seen_content.add(content_hash)
            tokens = estimate_tokens(block)
            if used + tokens > budget:
                break
            context += block
            used += tokens
        
        out_path = OUTPUT_DIR / "current_context.md"
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(context)
        
        print(f"✅ 静态context已生成: {lorebook.get('name', era_id)}")
        print(f"   预估token: {used}")
        print(f"   输出: {out_path}")
    else:
        # 动态模式（参考ST checkWorldInfo）
        print(f"✅ 世界书已加载: {lorebook.get('name', era_id)}")
        print(f"   总entry: {len(lorebook.get('entries', {}))}")
        print(f"   budget: {BUDGET_PERCENT}% context")
        print(f"   scan_depth: {DEFAULT_DEPTH} messages")
        print(f"   recursive: {lorebook.get('recursive_scanning', False)}")
        print(f"\n   ⚠️ 动态模式需要在每轮对话中调用check_world_info()")
        print(f"   请使用 --static 生成初始context")

if __name__ == "__main__":
    main()
