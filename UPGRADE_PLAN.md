# 世界书系统 v2 升级方案

## 目标

补齐 SillyTavern 世界书核心功能，利用 OpenClaw 现有能力，不新增依赖。

## 现有能力盘点

| 能力 | 来源 | 用途 |
|------|------|------|
| numpy 2.4 | 已安装 | 向量计算（余弦相似度） |
| sqlite3 | Python stdlib | 向量索引存储 |
| web_search/tavily | OpenClaw 内置 | 实时知识补充 |
| LCM | OpenClaw 内置 | 历史对话检索 |
| session管理 | OpenClaw 内置 | 存档/读档 |
| exec | OpenClaw 内置 | 运行脚本 |
| message | OpenClaw 内置 | 发送消息 |

## 差距分析（vs SillyTavern）

| 功能 | ST | 我们v1 | 方案 |
|------|-----|--------|------|
| 关键词匹配 | ✅ | ✅ | 已有 |
| scanDepth | ✅ | ✅ | 已有 |
| scoring (primary+secondary) | ✅ | ✅ | 已有 |
| budget | ✅ | ✅ | 已有 |
| recursive | ✅ | ✅（1轮） | **改为多轮** |
| group_scoring | ✅ | ✅ | 已有 |
| constant | ✅ | ✅ | 已有 |
| insertion_order | ✅ | ✅ | 已有 |
| **position策略** | ✅ 6种 | ❌ | **新增** |
| **向量检索** | ✅ | ❌ | **新增** |
| **min_activations** | ✅ | ❌ | **新增** |
| **exclude_keys** | ✅ | ❌ | **新增** |
| **match_whole_words** | ✅ | ❌ | **新增** |
| **character lore** | ✅ | ❌ | **新增** |
| **角色卡** | ✅ V2规范 | ❌ | **新增** |
| **动态世界书** | ❌ | ❌ | **新增（独有）** |

## 升级计划

### Phase 1: 世界书引擎增强（load_era.py → lorebook_engine.py）

**1.1 向量检索（numpy实现，无需embedding模型）**

用字符n-gram向量代替词向量：
- 对每个entry的content+keys，计算字符3-gram频率向量
- 对用户消息计算同样的n-gram向量
- 余弦相似度匹配（numpy.dot）
- 预计算所有entry向量存入sqlite3，运行时O(1)查询

优点：纯stdlib+numpy，中文友好，无需分词，无需模型

**1.2 Position策略**

ST有6种插入位置，我们简化为3种：
- `before_char` — 世界书在角色设定之前（默认）
- `after_char` — 世界书在角色设定之后
- `top_author` — 世界书在最顶部（最高权重）

**1.3 exclude_keys**

某些关键词出现时应**排除**该entry（而非激活）
例：entry"汉朝"的exclude_keys=["汉武帝"]，讨论汉武帝时不激活汉朝概述

**1.4 min_activations + min_activations_depth_max**

如果激活entry数 < min_activations，自动扩大扫描深度
直到满足最低激活数或超过depth_max

**1.5 match_whole_words**

中文按字符匹配，英文按\b word boundary匹配

**1.6 多轮recursive**

当前只做1轮recursive，改为最多3轮（可配置）

### Phase 2: 角色卡系统

**2.1 角色卡格式（JSON，兼容ST V2简化版）**

```json
{
  "name": "项羽",
  "description": "西楚霸王，力拔山兮气盖世",
  "personality": "刚愎自用、重情重义、勇猛无双",
  "scenario": "楚汉相争，垓下之围",
  "first_mes": "你是何人？竟敢擅入本王营帐！",
  "mes_example": "（冷笑）刘邦小儿，也配与我为敌？",
  "system_prompt": "你是项羽，字羽，下相人。楚国贵族后裔...",
  "post_history_instructions": "",
  "lorebook": ["chuhan"],  // 绑定的世界书
  "tags": ["历史", "军事", "楚汉"],
  "creator_notes": ""
}
```

**2.2 角色卡存储**

```
assets/characters/
├── 项羽.json
├── 刘邦.json
├── 韩信.json
└── ...
```

**2.3 角色卡绑定世界书**

角色卡的 `lorebook` 字段指定绑定的世界书ID列表
加载角色时自动加载对应世界书

### Phase 3: 动态世界书（独有功能）

**ST做不到的：利用OpenClaw能力**

**3.1 实时搜索补充**

当世界书中找不到相关信息时，自动调用 web_search/tavily 搜索
例：用户问"长平之战的细节" → 世界书没有 → 自动搜索 → 整合进回复

**3.2 世界书自学习**

每次对话结束后，将新提到的知识自动提取并建议添加到世界书
用户确认后写入

**3.3 LCM历史关联**

利用OpenClaw的LCM系统，检索之前的对话中与当前话题相关的历史片段
实现"跨会话记忆"

## 文件结构（v2）

```
mytavern1/
├── SKILL.md
├── scripts/
│   ├── lorebook_engine.py      # v2核心引擎（向量+关键词混合检索）
│   ├── convert_era.py          # 数据转换
│   ├── build_vector_index.py   # 预计算向量索引
│   └── char_manager.py         # 角色卡管理
├── assets/
│   ├── lorebooks/              # 世界书JSON
│   ├── characters/             # 角色卡JSON
│   └── indices/                # 预计算向量索引（sqlite3）
└── references/
    ├── eras.md
    └── chatglm-guide.md
```

## 实现优先级

| 优先级 | 功能 | 工作量 | 价值 |
|--------|------|--------|------|
| P0 | 角色卡系统 | 低 | 核心缺失 |
| P0 | character lore绑定 | 低 | 核心缺失 |
| P1 | 向量检索（n-gram） | 中 | 显著提升匹配质量 |
| P1 | exclude_keys | 低 | 精确控制 |
| P1 | position策略 | 低 | 灵活性 |
| P2 | min_activations | 低 | 边界优化 |
| P2 | 多轮recursive | 低 | 完善 |
| P3 | 动态世界书（搜索补充） | 中 | 独有功能 |
| P3 | 世界书自学习 | 中 | 独有功能 |
