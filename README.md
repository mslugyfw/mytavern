# MyTavern — 通用角色扮演酒馆

基于世界书的交互式角色扮演系统，为 OpenClaw 智能体设计。

当前内置《史记》世界书（6个时代，1156条知识），将来可挂载《资治通鉴》、二十四史或其他小说世界观。

## ✨ 特性

- **世界书引擎 v3**：关键词 + 字符n-gram向量混合检索，参考 SillyTavern world-info.js
- **角色卡系统**：JSON角色卡，兼容ST V2简化版，支持角色绑定专属世界书
- **动态世界书**：实时搜索补充、世界书自学习、LCM跨会话记忆（ST做不到）
- **6个时代**：五帝三代、春秋、战国、秦、楚汉、西汉，覆盖史记130章
- **211个角色卡**：自动从史记世界书生成，可直接扮演
- **6个向量索引**：sqlite3存储，毫秒级检索

## 🤖 智能体安装指南

> 本节写给AI智能体阅读。如果你是智能体，请按以下步骤配置此项目。

### 第1步：确认环境

你需要确认以下能力是否可用：

```bash
# 必须有
python3 --version          # 需要 3.10+
python3 -c "import numpy; print(numpy.__version__)"  # 需要 numpy
python3 -c "import sqlite3; print('ok')"             # 内置，一定有

# 可选（增强功能）
# web_search / tavily_search   # 用于动态搜索补充
# lcm_grep / lcm_expand_query  # 用于跨会话记忆
# browser tool                 # 用于ChatGLM生图
```

### 第2步：放置skill目录

将整个 `mytavern1/` 目录复制到你的 skills 目录：

```
~/.openclaw/skills/mytavern1/
├── SKILL.md                     ← 你会自动读到这个
├── scripts/                     ← Python脚本，你用 exec 调用
│   ├── lorebook_engine.py       ← 核心引擎（v3）
│   ├── build_vector_index.py    ← 向量索引构建
│   ├── char_manager.py          ← 角色卡管理
│   ├── dynamic_worldbook.py     ← 动态世界书
│   ├── convert_era.py           ← 数据转换
│   └── list_eras.py             ← 时代列表
├── references/                  ← 参考文档
│   ├── eras.md                  ← 时代选择菜单
│   └── chatglm-guide.md         ← 生图指南
└── assets/
    ├── lorebooks/*.json         ← 世界书数据
    ├── characters/*.json        ← 角色卡
    ├── indices/*.db             ← 向量索引（预构建）
    └── learned/                 ← 自学习知识
```

### 第3步：理解工作流程

当用户说"进入酒馆"时，按以下流程操作：

```
1. 读取 references/eras.md → 展示时代菜单
2. 用户选择时代（如"西汉"）
3. 展示该时代可用角色（执行 char_manager.py list 或从 characters/ 读取）
4. 用户选角色或自定义身份
5. 生成context（执行 lorebook_engine.py context <角色名> <世界书ID>）
6. 开始角色扮演
```

### 第4步：角色扮演规则

**你的角色**：旁白 + 系统NPC控制器 + 百科全书

**回答优先级**：
1. NPC角色回答（以角色身份说话）
2. 系统补充（史记原文细节）
3. 系统代答（标注【系统】）

**关键原则**：
- 让古人自己说话，不要替他们总结
- 以史记原文为基础，补充内容标注【补】
- 默认收束正史，允许超能力等合理偏移
- 营造氛围感（环境、气味、声音、光线）

### 第5步：脚本调用参考

```bash
# 列出角色
python3 ~/.openclaw/skills/mytavern1/scripts/char_manager.py list

# 从世界书自动生成角色卡
python3 ~/.openclaw/skills/mytavern1/scripts/char_manager.py auto <世界书ID> [最低引用数]

# 加载角色context
python3 ~/.openclaw/skills/mytavern1/scripts/lorebook_engine.py context <角色名> <世界书ID>

# 测试世界书匹配
python3 ~/.openclaw/skills/mytavern1/scripts/lorebook_engine.py check <世界书ID> <查询文本>

# 检查是否需要搜索补充
python3 ~/.openclaw/skills/mytavern1/scripts/dynamic_worldbook.py check <世界书ID> <查询>

# 记录学习建议
python3 ~/.openclaw/skills/mytavern1/scripts/dynamic_worldbook.py learn <世界书ID> <主题> <内容>

# 构建向量索引
python3 ~/.openclaw/skills/mytavern1/scripts/build_vector_index.py build <世界书ID>
```

### 第6步：动态功能（可选增强）

**实时搜索补充**：当世界书中找不到用户提到的话题时，调用 `tavily_search` 或 `web_search` 搜索，将结果整合进回复并标注【补】。

**世界书自学习**：对话中出现有价值的新知识时，用 `dynamic_worldbook.py learn` 记录。退出酒馆前列出建议让用户确认，确认后 `approve` + `apply` 写入。

**跨会话记忆**：用户提到之前对话中的内容时，调用 `lcm_grep` 搜索历史，调用 `lcm_expand_query` 深度检索。

### 第7步：退出酒馆

用户说"退出酒馆"时：
- 清理 `/tmp/mytavern1/`
- 恢复普通对话模式
- 如有未确认的学习建议，提醒用户

### 故障排除

| 问题 | 解决方案 |
|------|----------|
| 世界书找不到 | 检查 assets/lorebooks/ 下是否有对应 .json |
| 向量检索无结果 | 执行 `build_vector_index.py build_all` 重建索引 |
| 角色卡为空 | 执行 `char_manager.py auto <世界书ID>` 生成 |
| 路径错误 | 脚本使用 `__file__` 相对路径，确保目录结构完整 |

---

## 📂 完整文件结构

```
mytavern1/
├── SKILL.md                        # OpenClaw skill 定义（智能体自动加载）
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
    ├── lorebooks/                  # 世界书JSON
    │   ├── wudai.json              # 五帝三代（~850KB）
    │   ├── chunqiu.json            # 春秋（~3.5MB）
    │   ├── zhanguo.json            # 战国（~800KB）
    │   ├── qin.json                # 秦（~1MB）
    │   ├── chuhan.json             # 楚汉（~1.7MB）
    │   └── xihan.json              # 西汉（~2.9MB）
    ├── characters/                 # 角色卡JSON（211个）
    ├── indices/                    # 向量索引（sqlite3，预构建）
    └── learned/                    # 自学习知识（待确认写入）
```

## 📖 世界书引擎 v3

参考 SillyTavern world-info.js，新增向量检索和多项增强：

| 功能 | 说明 |
|------|------|
| **关键词匹配** | primary + secondary keys |
| **向量检索** | 字符3-gram + numpy余弦相似度（无需分词、无需模型） |
| **混合检索** | 关键词60% + 向量40% 加权混合 |
| **exclude_keys** | 排除匹配（避免误激活） |
| **position策略** | before_char / after_char / top_author（3种插入位置） |
| **min_activations** | 最低激活数（不够则自动扩大扫描深度） |
| **budget** | 25% context预算，逐条注入 |
| **recursive** | 多轮链式激活（最多3轮） |
| **constant** | 无条件注入，不受budget限制 |
| **group_scoring** | 同group entry共享score |

## 🎭 角色卡系统

JSON格式，兼容 SillyTavern V2 简化版：

```json
{
  "name": "项羽",
  "description": "西楚霸王",
  "personality": "刚愎自用、重情重义",
  "scenario": "楚汉相争",
  "first_mes": "你是何人？竟敢擅入本王营帐！",
  "system_prompt": "你是项羽...",
  "lorebook": ["chuhan"],
  "tags": ["历史", "军事"]
}
```

## 🌟 动态世界书（OpenClaw独有）

SillyTavern 不具备的能力：

| 功能 | 实现方式 | 说明 |
|------|----------|------|
| **实时搜索补充** | tavily_search / web_search | 世界书没有 → 自动搜索 → 标注【补】 |
| **世界书自学习** | dynamic_worldbook.py | 对话中学到 → 记录建议 → 用户确认 → 写入世界书 |
| **跨会话记忆** | lcm_grep / lcm_expand_query | 检索历史对话 → 保持连续性 |

## 🙏 致谢

### 世界书数据

| 世界书 | 数据源 | 条目数 | 许可证 |
|--------|--------|--------|--------|
| **史记** | [shiji-kb](https://github.com/baojie/shiji-kb) | 1156 | CC BY-NC-SA 4.0 |
| 资治通鉴 | *计划中* | — | — |
| 二十四史 | *计划中* | — | — |
| 自定义小说 | *计划中* | — | — |

史记世界书数据源自 [shiji-kb](https://github.com/baojie/shiji-kb)：

> 鲍捷，史记知识库，2026，在线发布于 https://github.com/baojie/shiji-kb
>
> shiji-kb 基于 AI Agent 从《史记》原文中提取实体、事件、地点等结构化知识，覆盖130章。

### 许可证兼容性

| 组件 | 许可证 | 说明 |
|------|--------|------|
| **代码**（scripts、SKILL.md） | CC BY-NC-SA 4.0 | 本项目原创 |
| **史记世界书**（lorebooks/） | CC BY-NC-SA 4.0 | shiji-kb 衍生作品，SA 兼容 |
| **未来世界书** | 各自独立 | 视数据源许可证而定 |

### 技术参考

- [SillyTavern](https://github.com/SillyTavern/SillyTavern) — 世界书引擎算法参考
- [OpenClaw](https://github.com/openclaw/openclaw) — 智能体运行时
- [ChatGLM](https://chatglm.cn) — 场景插图生成

## 📜 许可证

[CC BY-NC-SA 4.0](LICENSE)

- **代码**：CC BY-NC-SA 4.0（可自由 fork、修改、二次分发）
- **史记世界书数据**：CC BY-NC-SA 4.0（与 shiji-kb 保持一致）
- **未来世界书数据**：各自遵循上游数据源许可证
