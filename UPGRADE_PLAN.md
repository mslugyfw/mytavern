# 世界书系统升级方案

## 目标

补齐 SillyTavern 世界书核心功能，利用 OpenClaw 现有能力，不新增依赖。

## 状态：✅ 全部完成（2026-04-18）

UPGRADE_PLAN 中所有 P0-P3 功能均已实现。

---

## 差距分析（vs SillyTavern）

| 功能 | ST | 我们 | 状态 |
|------|-----|------|------|
| 关键词匹配 | ✅ | ✅ | ✅ 原有 |
| scanDepth | ✅ | ✅ | ✅ 原有 |
| scoring (primary+secondary) | ✅ | ✅ | ✅ 原有 |
| budget | ✅ | ✅ | ✅ 原有 |
| recursive | ✅ | ✅ | ✅ 改为多轮（最多3轮） |
| group_scoring | ✅ | ✅ | ✅ 原有 |
| constant | ✅ | ✅ | ✅ 原有 |
| insertion_order | ✅ | ✅ | ✅ 原有 |
| position策略 | ✅ 6种 | ✅ 3种 | ✅ P1 完成 |
| 向量检索 | ✅ | ✅ | ✅ P1 完成 |
| min_activations | ✅ | ✅ | ✅ P1 完成 |
| exclude_keys | ✅ | ✅ | ✅ P1 完成 |
| match_whole_words | ✅ | ✅ | ✅ P2 完成 |
| character lore | ✅ | ✅ | ✅ P0 完成 |
| 角色卡 | ✅ V2规范 | ✅ | ✅ P0 完成 |
| **动态世界书** | ❌ | ✅ | ✅ P3 完成（独有） |

## 实现记录

### Phase 1: 世界书引擎增强 ✅

- **向量检索**：字符3-gram + numpy余弦相似度 + sqlite3预计算索引（6个时代已构建）
- **混合检索**：关键词60% + 向量40% 加权
- **Position策略**：before_char / after_char / top_author
- **exclude_keys**：排除匹配，避免误激活
- **min_activations**：最低激活数，不够自动扩大扫描深度
- **多轮recursive**：最多3轮链式激活
- **match_whole_words**：中文按字符，英文按\b匹配

实现文件：`scripts/lorebook_engine.py`、`scripts/build_vector_index.py`

### Phase 2: 角色卡系统 ✅

- **JSON格式**：兼容 SillyTavern V2 简化版
- **30个核心角色卡**：description/personality/first_mes/mes_example/system_prompt 全手写
- **世界书绑定**：角色卡 lorebook 字段自动加载对应世界书
- **角色卡管理**：char_manager.py 支持 list/show/create/auto 命令
- **自动生成**：从世界书自动提取高频实体生成角色卡

覆盖6个时代：
- 五帝三代：黄帝、大禹、周武王
- 春秋：孔子、管仲、勾践
- 战国：商鞅、苏秦、张仪、白起、荆轲、屈原
- 秦：秦始皇、李斯、赵高、蒙恬
- 楚汉：项羽、刘邦、韩信、张良、萧何、范增、樊哙、吕后
- 西汉：卫青、霍去病、张骞、李广、司马迁、董仲舒

实现文件：`scripts/char_manager.py`、`assets/characters/*.json`

### Phase 3: 动态世界书（OpenClaw独有） ✅

- **实时搜索补充**：世界书没有 → tavily_search/web_search → 标注【补】
- **世界书自学习**：对话中学到 → learn → approve → apply → 写入世界书 + 重建索引
- **LCM跨会话记忆**：lcm_grep/lcm_expand_query 检索历史对话

实现文件：`scripts/dynamic_worldbook.py`

### 额外完成

- **README 智能体安装指南**：7步教程，任何智能体读完即可配置
- **ChatGLM生图集成**：浏览器自动化生成场景插图
- **文字校对规则**：发送前自检错别字
- **6个时代世界书**：1156个entry（人物300+事件736+地点100+朝代20）
- **6个向量索引**：sqlite3预构建，毫秒级检索

---

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
| browser | OpenClaw 内置 | ChatGLM生图 |

## 文件结构

```
mytavern1/
├── SKILL.md                        # OpenClaw skill 定义
├── scripts/
│   ├── lorebook_engine.py          # v3世界书引擎（关键词+向量混合检索）
│   ├── build_vector_index.py       # 预计算向量索引（字符n-gram + numpy + sqlite3）
│   ├── char_manager.py             # 角色卡管理（创建/列表/自动生成/绑定世界书）
│   ├── dynamic_worldbook.py        # 动态世界书（搜索补充+自学习+LCM记忆）
│   ├── convert_era.py              # shiji-kb → 世界书JSON转换器
│   └── list_eras.py                # 列出可用时代
├── references/
│   ├── eras.md                     # 时代选择菜单
│   └── chatglm-guide.md            # ChatGLM生图指南
└── assets/
    ├── lorebooks/                  # 世界书JSON（6个时代）
    ├── characters/                 # 角色卡JSON（30个核心角色）
    ├── indices/                    # 向量索引（sqlite3，预构建）
    └── learned/                    # 自学习知识（待确认写入）
```

数据源: shiji-kb (CC BY-NC-SA 4.0)
