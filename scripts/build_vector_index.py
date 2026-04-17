#!/usr/bin/env python3
"""
向量索引构建器 v1 — 字符n-gram + numpy

用字符级n-gram代替词向量，天然支持中文，无需分词。

原理：
1. 对每个entry的content+keys，提取字符3-gram
2. 计算n-gram频率向量（稀疏向量，用dict表示）
3. 查询时同样提取n-gram，计算余弦相似度
4. 预计算所有向量存入sqlite3，运行时O(k)查询
"""

import json, sqlite3, sys, re
import numpy as np
from pathlib import Path
from collections import Counter

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
LOREBOOKS_DIR = SKILL_DIR / "assets" / "lorebooks"
INDEX_DIR = SKILL_DIR / "assets" / "indices"

N_GRAM = 3  # 字符n-gram大小


def extract_ngrams(text, n=N_GRAM):
    """提取字符n-gram频率"""
    text = re.sub(r'\s+', '', text)  # 去空白
    if len(text) < n:
        return {}
    grams = [text[i:i+n] for i in range(len(text) - n + 1)]
    return dict(Counter(grams))


def cosine_similarity(v1, v2):
    """计算两个频率向量的余弦相似度"""
    if not v1 or not v2:
        return 0.0
    # 合并所有key
    all_keys = set(v1.keys()) | set(v2.keys())
    if not all_keys:
        return 0.0
    
    # 构建numpy向量
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


def build_index(lorebook_id):
    """为指定世界书构建向量索引"""
    lb_path = LOREBOOKS_DIR / f"{lorebook_id}.json"
    if not lb_path.exists():
        print(f"❌ 世界书不存在: {lorebook_id}")
        return
    
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    db_path = INDEX_DIR / f"{lorebook_id}_vectors.db"
    
    # 删除旧索引
    if db_path.exists():
        db_path.unlink()
    
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    
    cur.execute("""
        CREATE TABLE vectors (
            entry_key TEXT PRIMARY KEY,
            name TEXT,
            group_type TEXT,
            ref_count INTEGER,
            ngrams_json TEXT,
            content_preview TEXT
        )
    """)
    
    with open(lb_path, encoding="utf-8") as f:
        lb = json.load(f)
    
    entries = lb.get("entries", {})
    count = 0
    
    for key, e in entries.items():
        name = e.get("name", "")
        content = e.get("content", "")
        keys_str = " ".join(e.get("keys", []))
        group = e.get("group", "")
        rc = e.get("extensions", {}).get("ref_count", 0)
        
        # 合并keys+content的前500字作为索引文本
        index_text = keys_str + " " + content[:500]
        ngrams = extract_ngrams(index_text)
        
        if not ngrams:
            continue
        
        ngrams_json = json.dumps(ngrams, ensure_ascii=False)
        preview = content[:100].replace("\n", " ")
        
        cur.execute(
            "INSERT INTO vectors VALUES (?, ?, ?, ?, ?, ?)",
            (key, name, group, rc, ngrams_json, preview)
        )
        count += 1
    
    conn.commit()
    conn.close()
    
    size = db_path.stat().st_size
    print(f"✅ 向量索引已构建: {lorebook_id}")
    print(f"   {count} 个entry已索引")
    print(f"   文件: {db_path} ({size/1024:.0f}KB)")


def search(lorebook_id, query, top_k=10, min_similarity=0.1):
    """
    向量检索
    
    Args:
        lorebook_id: 世界书ID
        query: 查询文本
        top_k: 返回top-k结果
        min_similarity: 最低相似度阈值
    
    Returns:
        list: [(name, group, similarity, preview), ...]
    """
    db_path = INDEX_DIR / f"{lorebook_id}_vectors.db"
    if not db_path.exists():
        print(f"❌ 索引不存在: {lorebook_id}。先运行 build {lorebook_id}")
        return []
    
    query_ngrams = extract_ngrams(query)
    if not query_ngrams:
        return []
    
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    
    results = []
    cur.execute("SELECT entry_key, name, group_type, ref_count, ngrams_json, content_preview FROM vectors")
    
    for row in cur.fetchall():
        key, name, group, rc, ngrams_json, preview = row
        entry_ngrams = json.loads(ngrams_json)
        
        sim = cosine_similarity(query_ngrams, entry_ngrams)
        if sim >= min_similarity:
            results.append((name, group, sim, preview, rc, key))
    
    conn.close()
    
    # 按相似度降序
    results.sort(key=lambda x: -x[2])
    return results[:top_k]


def hybrid_search(lorebook_id, query, top_k=10, keyword_weight=0.6, vector_weight=0.4):
    """
    混合检索：关键词 + 向量
    
    Args:
        keyword_weight: 关键词匹配权重
        vector_weight: 向量相似度权重
    """
    db_path = INDEX_DIR / f"{lorebook_id}_vectors.db"
    if not db_path.exists():
        return search(lorebook_id, query, top_k)
    
    query_ngrams = extract_ngrams(query)
    query_lower = query.lower()
    
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    
    scored = []
    cur.execute("SELECT entry_key, name, group_type, ref_count, ngrams_json, content_preview FROM vectors")
    
    for row in cur.fetchall():
        key, name, group, rc, ngrams_json, preview = row
        entry_ngrams = json.loads(ngrams_json)
        
        # 向量分数
        vec_score = cosine_similarity(query_ngrams, entry_ngrams)
        
        # 关键词分数：名字是否在query中出现
        kw_score = 0.0
        if name and name.lower() in query_lower:
            kw_score = 1.0
        # 也检查keys
        lb_path = LOREBOOKS_DIR / f"{lorebook_id}.json"
        if lb_path.exists():
            with open(lb_path, encoding="utf-8") as f:
                lb = json.load(f)
            entry = lb.get("entries", {}).get(key, {})
            for k in entry.get("keys", []):
                if k.lower() in query_lower:
                    kw_score = max(kw_score, 0.8)
                    break
        
        # 加权混合
        total = keyword_weight * kw_score + vector_weight * vec_score
        
        if total > 0.05:
            scored.append((name, group, total, kw_score, vec_score, preview, rc, key))
    
    conn.close()
    
    scored.sort(key=lambda x: -x[2])
    return scored[:top_k]


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("命令:")
        print("  build <世界书ID>                  构建向量索引")
        print("  build_all                         构建所有世界书索引")
        print("  search <世界书ID> <查询> [top_k]   向量检索")
        print("  hybrid <世界书ID> <查询> [top_k]   混合检索（关键词+向量）")
        sys.exit(0)
    
    cmd = sys.argv[1]
    
    if cmd == "build":
        if len(sys.argv) < 3:
            print("用法: build_vector_index.py build <世界书ID>")
            sys.exit(1)
        build_index(sys.argv[2])
    
    elif cmd == "build_all":
        for f in sorted(LOREBOOKS_DIR.glob("*.json")):
            lorebook_id = f.stem
            build_index(lorebook_id)
            print()
    
    elif cmd == "search":
        if len(sys.argv) < 4:
            print("用法: build_vector_index.py search <世界书ID> <查询> [top_k]")
            sys.exit(1)
        top_k = int(sys.argv[4]) if len(sys.argv) > 4 else 10
        results = search(sys.argv[2], " ".join(sys.argv[3:]), top_k)
        for name, group, sim, preview, rc, key in results:
            print(f"  {name} [{group}] sim={sim:.3f} ref={rc}")
            print(f"    {preview[:60]}")
    
    elif cmd == "hybrid":
        if len(sys.argv) < 4:
            print("用法: build_vector_index.py hybrid <世界书ID> <查询> [top_k]")
            sys.exit(1)
        top_k = int(sys.argv[4]) if len(sys.argv) > 4 else 10
        results = hybrid_search(sys.argv[2], " ".join(sys.argv[3:]), top_k)
        for name, group, total, kw, vec, preview, rc, key in results:
            print(f"  {name} [{group}] total={total:.3f} kw={kw:.2f} vec={vec:.3f} ref={rc}")
            print(f"    {preview[:60]}")
    
    else:
        print(f"❌ 未知命令: {cmd}")


if __name__ == "__main__":
    main()
