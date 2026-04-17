#!/usr/bin/env python3
"""
角色卡管理器 v1

功能：
- 创建/列出/查看/删除角色卡
- 角色卡绑定世界书（character lore）
- 从世界书自动提取角色信息生成角色卡

角色卡格式（兼容SillyTavern V2简化版）：
{
  "name": "角色名",
  "description": "一句话描述",
  "personality": "性格特征",
  "scenario": "当前场景设定",
  "first_mes": "开场白",
  "mes_example": "对话示例",
  "system_prompt": "系统提示词（告诉AI如何扮演）",
  "lorebook": ["世界书ID列表"],
  "tags": ["标签"],
  "creator_notes": "创作者备注",
  "metadata": {
    "version": 1,
    "created": "2026-04-18",
    "modified": "2026-04-18",
    "source": "manual|auto|shiji-kb"
  }
}
"""

import json, sys, os, re
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
CHARS_DIR = SKILL_DIR / "assets" / "characters"
LOREBOOKS_DIR = SKILL_DIR / "assets" / "lorebooks"


def list_characters():
    """列出所有角色卡"""
    CHARS_DIR.mkdir(parents=True, exist_ok=True)
    chars = sorted(CHARS_DIR.glob("*.json"))
    if not chars:
        print("📭 暂无角色卡。用 create <名字> 创建，或 auto <世界书ID> 从世界书自动生成。")
        return []
    
    print(f"🎭 角色卡列表（{len(chars)}个）\n")
    result = []
    for f in chars:
        with open(f, encoding="utf-8") as fp:
            c = json.load(fp)
        lorebooks = c.get("lorebook", [])
        lore_str = ", ".join(lorebooks) if lorebooks else "无"
        tags = c.get("tags", [])
        tag_str = " ".join(f"[{t}]" for t in tags) if tags else ""
        desc = c.get("description", "")[:40]
        print(f"  {c['name']}")
        print(f"    {desc}")
        print(f"    世界书: {lore_str} {tag_str}")
        print()
        result.append(c)
    return result


def create_character(name, **kwargs):
    """创建角色卡（交互式/参数式）"""
    CHARS_DIR.mkdir(parents=True, exist_ok=True)
    
    char = {
        "name": name,
        "description": kwargs.get("description", ""),
        "personality": kwargs.get("personality", ""),
        "scenario": kwargs.get("scenario", ""),
        "first_mes": kwargs.get("first_mes", ""),
        "mes_example": kwargs.get("mes_example", ""),
        "system_prompt": kwargs.get("system_prompt", ""),
        "lorebook": kwargs.get("lorebook", []),
        "tags": kwargs.get("tags", []),
        "creator_notes": kwargs.get("creator_notes", ""),
        "metadata": {
            "version": 1,
            "created": datetime.now().strftime("%Y-%m-%d"),
            "modified": datetime.now().strftime("%Y-%m-%d"),
            "source": kwargs.get("source", "manual")
        }
    }
    
    fpath = CHARS_DIR / f"{name}.json"
    with open(fpath, 'w', encoding='utf-8') as f:
        json.dump(char, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 角色卡已创建: {name}")
    print(f"   文件: {fpath}")
    return char


def get_character(name):
    """读取角色卡"""
    fpath = CHARS_DIR / f"{name}.json"
    if not fpath.exists():
        # 尝试模糊匹配
        for f in CHARS_DIR.glob("*.json"):
            if name in f.stem:
                fpath = f
                break
        else:
            return None
    with open(fpath, encoding="utf-8") as f:
        return json.load(f)


def delete_character(name):
    """删除角色卡"""
    fpath = CHARS_DIR / f"{name}.json"
    if fpath.exists():
        fpath.unlink()
        print(f"🗑️ 已删除: {name}")
    else:
        print(f"❌ 角色卡不存在: {name}")


def load_character_context(name):
    """
    加载角色卡的完整context（用于注入system prompt）
    
    Returns:
        str: 包含角色设定+世界书知识的完整context
    """
    char = get_character(name)
    if not char:
        return None
    
    parts = []
    
    # 1. 系统提示词
    if char.get("system_prompt"):
        parts.append(f"# 角色设定\n\n{char['system_prompt']}")
    
    # 2. 性格
    if char.get("personality"):
        parts.append(f"## 性格\n{char['personality']}")
    
    # 3. 场景
    if char.get("scenario"):
        parts.append(f"## 场景\n{char['scenario']}")
    
    # 4. 对话示例
    if char.get("mes_example"):
        parts.append(f"## 对话风格示例\n{char['mes_example']}")
    
    # 5. 绑定的世界书（静态高频entry）
    for lb_id in char.get("lorebook", []):
        lb_path = LOREBOOKS_DIR / f"{lb_id}.json"
        if lb_path.exists():
            with open(lb_path, encoding="utf-8") as f:
                lb = json.load(f)
            
            # 加载与角色相关的entry
            entries = list(lb.get("entries", {}).values())
            name_lower = name.lower()
            
            # 按相关性排序：keys中包含角色名的优先
            relevant = []
            for e in entries:
                keys = e.get("keys", [])
                content = e.get("content", "")
                # 直接匹配角色名
                if any(name_lower in str(k).lower() for k in keys):
                    relevant.append((e, 100))  # 高优先级
                # 内容中提及
                elif name_lower in content[:200]:
                    relevant.append((e, 50))   # 中优先级
            
            relevant.sort(key=lambda x: -x[1])
            
            # 加入高频事件和地点作为背景
            background = [e for e in entries 
                         if e.get("comment", "").startswith("事件") 
                         and e.get("extensions", {}).get("ref_count", 0) >= 2]
            background.sort(key=lambda e: -e.get("extensions", {}).get("ref_count", 0))
            
            # 格式化
            lore_parts = [f"\n## 世界书: {lb.get('name', lb_id)}\n"]
            used_content = set()
            
            # 先加角色相关
            for e, priority in relevant[:10]:
                content = e.get("content", "")
                content_hash = content[:80]
                if content_hash in used_content:
                    continue
                used_content.add(content_hash)
                
                # 清理格式
                content = re.sub(r'\[\d+\] ', '', content)
                content = re.sub(r'#{1,4} ', '', content)
                content = re.sub(r'\[\d+\.\d+\] ', '', content)
                content = re.sub(r'\n{2,}', '\n', content).strip()
                if len(content) > 200:
                    content = content[:200] + "…"
                
                group = e.get("group", "")
                entry_name = e.get("name", "")
                lore_parts.append(f"[{group}]{entry_name}\n{content}")
            
            # 加背景事件（补充token预算）
            budget = 2000
            for e in background[:5]:
                content = e.get("content", "")
                content_hash = content[:80]
                if content_hash in used_content:
                    continue
                used_content.add(content_hash)
                
                content = re.sub(r'\[\d+\] ', '', content)
                content = re.sub(r'#{1,4} ', '', content)
                content = re.sub(r'\[\d+\.\d+\] ', '', content)
                content = re.sub(r'\n{2,}', '\n', content).strip()
                if len(content) > 150:
                    content = content[:150] + "…"
                
                block = f"[{e.get('group','')}] {e.get('name','')}\n{content}"
                if len(lore_parts) < budget:
                    lore_parts.append(block)
            
            parts.append("\n".join(lore_parts))
    
    return "\n\n".join(parts)


def auto_generate_characters(lorebook_id, min_ref_count=3):
    """
    从世界书自动生成角色卡
    
    Args:
        lorebook_id: 世界书ID（如 chuhan, xihan）
        min_ref_count: 最低引用次数（过滤低频人物）
    """
    lb_path = LOREBOOKS_DIR / f"{lorebook_id}.json"
    if not lb_path.exists():
        print(f"❌ 世界书不存在: {lorebook_id}")
        return []
    
    with open(lb_path, encoding="utf-8") as f:
        lb = json.load(f)
    
    entries = list(lb.get("entries", {}).values())
    person_entries = [e for e in entries if e.get("comment", "").startswith("人物")]
    
    # 按引用次数排序
    person_entries.sort(key=lambda e: -e.get("extensions", {}).get("ref_count", 0))
    
    # 确定场景
    era = lb.get("extensions", {}).get("era", lorebook_id)
    era_scenarios = {
        "wudai": "上古时代，黄帝至西周。天地初开，神与人尚未分离。",
        "chunqiu": "春秋时代。周天子权威衰落，诸侯争霸，百家争鸣。",
        "zhanguo": "战国时代。七雄并立，合纵连横，铁血纷争。",
        "qin": "秦朝。始皇一统六国，焚书坑儒，二世而亡。",
        "chuhan": "楚汉相争。项羽与刘邦争夺天下，英雄辈出。",
        "xihan": "西汉王朝。文景之治后武帝开疆拓土，丝路连通东西。",
    }
    scenario = era_scenarios.get(era, "中国古代。")
    
    CHARS_DIR.mkdir(parents=True, exist_ok=True)
    created = []
    
    for e in person_entries:
        rc = e.get("extensions", {}).get("ref_count", 0)
        if rc < min_ref_count:
            continue
        
        name = e.get("name", "")
        if not name or len(name) < 2 or len(name) > 4:
            continue
        
        # 跳过过于通用的单字名
        if len(name) == 1 and rc < 20:
            continue
        
        content = e.get("content", "")
        
        # 清理content用于description
        desc = re.sub(r'\[\d+\] ', '', content)
        desc = re.sub(r'#{1,4} ', '', desc)
        desc = re.sub(r'\[\d+\.\d+\] ', '', desc)
        desc = re.sub(r'\n{2,}', '\n', desc).strip()
        
        # 构建system_prompt
        sys_prompt = f"你是{name}。{desc[:500]}"
        
        # 构建first_mes
        first_mes = f"（看向对方）你是何人？"
        
        char = {
            "name": name,
            "description": desc[:60] + ("…" if len(desc) > 60 else ""),
            "personality": "",
            "scenario": scenario,
            "first_mes": first_mes,
            "mes_example": "",
            "system_prompt": sys_prompt,
            "lorebook": [lorebook_id],
            "tags": ["历史", era],
            "creator_notes": f"自动生成自{lb.get('name', lorebook_id)}，引用{rc}次",
            "metadata": {
                "version": 1,
                "created": datetime.now().strftime("%Y-%m-%d"),
                "modified": datetime.now().strftime("%Y-%m-%d"),
                "source": "shiji-kb",
                "ref_count": rc
            }
        }
        
        fpath = CHARS_DIR / f"{name}.json"
        with open(fpath, 'w', encoding='utf-8') as f:
            json.dump(char, f, ensure_ascii=False, indent=2)
        
        created.append(name)
        print(f"  ✅ {name} (引用{rc}次)")
    
    print(f"\n🎭 共生成 {len(created)} 个角色卡")
    return created


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("命令:")
        print("  list                          列出所有角色卡")
        print("  create <名字>                  创建角色卡（交互式）")
        print("  auto <世界书ID> [最低引用数]    从世界书自动生成角色卡")
        print("  show <名字>                    查看角色卡")
        print("  load <名字>                    加载角色context")
        print("  delete <名字>                  删除角色卡")
        sys.exit(0)
    
    cmd = sys.argv[1]
    
    if cmd == "list":
        list_characters()
    
    elif cmd == "create":
        if len(sys.argv) < 3:
            print("用法: char_manager.py create <名字>")
            sys.exit(1)
        name = sys.argv[2]
        # 简单创建，后续可用交互式
        create_character(name, source="manual")
    
    elif cmd == "auto":
        if len(sys.argv) < 3:
            print("用法: char_manager.py auto <世界书ID> [最低引用数]")
            print("  可用世界书: wudai, chunqiu, zhanguo, qin, chuhan, xihan")
            sys.exit(1)
        lb_id = sys.argv[2]
        min_rc = int(sys.argv[3]) if len(sys.argv) > 3 else 3
        auto_generate_characters(lb_id, min_rc)
    
    elif cmd == "show":
        if len(sys.argv) < 3:
            print("用法: char_manager.py show <名字>")
            sys.exit(1)
        char = get_character(sys.argv[2])
        if char:
            print(json.dumps(char, ensure_ascii=False, indent=2))
        else:
            print(f"❌ 角色卡不存在: {sys.argv[2]}")
    
    elif cmd == "load":
        if len(sys.argv) < 3:
            print("用法: char_manager.py load <名字>")
            sys.exit(1)
        ctx = load_character_context(sys.argv[2])
        if ctx:
            print(ctx)
        else:
            print(f"❌ 角色卡不存在: {sys.argv[2]}")
    
    elif cmd == "delete":
        if len(sys.argv) < 3:
            print("用法: char_manager.py delete <名字>")
            sys.exit(1)
        delete_character(sys.argv[2])
    
    else:
        print(f"❌ 未知命令: {cmd}")


if __name__ == "__main__":
    main()
