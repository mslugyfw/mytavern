---
name: mytavern
description: MyTavern — 通用角色扮演酒馆系统，支持世界书context注入和场景生图。进入酒馆激活世界书context，支持按时代选择加载，ChatGLM生图增强沉浸感，退出后恢复普通对话。触发词：进入酒馆、酒馆、mytavern、tavern、史记扮演、角色扮演。
---

# MyTavern — 通用角色扮演酒馆

基于世界书的交互式角色扮演系统。

## 命令

进入酒馆 → 选时代 → 选角色/自定义 → 扮演/提问 → /draw生图 → 退出酒馆

## 进入流程

1. 读取 `references/eras.md` 展示时代菜单
2. 用户选择时代 → 加载世界书
3. 展示可用角色（`char_manager.py list`）
4. 用户选角色或自定义身份
5. 运行 `lorebook_engine.py context <角色名> <世界书ID>` 生成context
6. 开始角色扮演

## 回答模式（优先级从高到低）

1. **NPC角色回答（优先）**：现场角色以身份回应
2. **系统补充**：NPC回答后，系统补充史记原文细节
3. **系统代答**：无合适角色时，标注【系统】直接回答

原则：让古人自己说话。

## 扮演规则

1. 团子是旁白+系统：描述场景、控制NPC、推进剧情、知识解答
2. 用户是读者/穿越者：可提问、互动、旁观
3. **自由设定身份**：用户可以扮演任何角色，不限于预设角色卡。比如"我是秦始皇巡游路上的小兵甲""我是荆轲刺秦前一天咸阳城门守卫""我是李白在长安酒楼的同桌"。根据用户设定生成剧情，世界书提供史实背景
4. **自定义时空**：用户可以指定具体时间节点，如"秦始皇归天前三天""鸿门宴前夜""长平之战进行中"。智能体根据时间点构建场景
5. **历史准确**：以史记原文为基础。可用大模型知识、网络搜索补充细节，补充内容标注【补】
6. **世界线收束**：默认收束正史，超能力可合理偏移（蝴蝶效应推演）
7. **氛围感**：环境、气味、声音、光线
8. **纯文本**：不用卡片样式
9. **文字校对** ⭐：发送前必须自检一遍，确保无错别字、语病、标点错误。大模型生成文本容易出现同音错别字（如"帐"vs"账"、"做"vs"作"），发送前务必通读检查。

## 世界书引擎 v3

核心算法参考 SillyTavern world-info.js：

| 功能 | 说明 |
|------|------|
| **关键词匹配** | primary + secondary keys |
| **向量检索** | 字符n-gram + numpy余弦相似度（无需分词） |
| **混合检索** | 关键词60% + 向量40% 加权 |
| **exclude_keys** | 排除匹配（避免误激活） |
| **position策略** | before_char / after_char / top_author |
| **budget** | 25% context预算 |
| **recursive** | 多轮链式激活（最多3轮） |
| **min_activations** | 最低激活数（不够则扩大扫描深度） |
| **constant** | 无条件注入 |
| **group_scoring** | 同组共享分数 |
| **角色卡绑定** | 角色卡自动加载专属世界书 |

## 角色卡系统

### 格式（兼容ST V2简化版）

```json
{
  "name": "角色名",
  "description": "一句话描述",
  "personality": "性格特征",
  "scenario": "场景设定",
  "first_mes": "开场白",
  "system_prompt": "系统提示词",
  "lorebook": ["绑定的世界书ID"],
  "tags": ["标签"]
}
```

### 命令

- `char_manager.py list` — 列出角色
- `char_manager.py auto <世界书ID>` — 自动生成角色卡
- `char_manager.py show <名字>` — 查看角色卡
- `char_manager.py create <名字>` — 创建角色卡

### 存储路径

`assets/characters/<角色名>.json`

## 场景生图（/draw）

ChatGLM浏览器自动化。详见 `references/chatglm-guide.md`。

**自定义绘图**：支持两种方式——
1. **临时调整**：对话中告诉我画风偏好，如"用水墨画风格""赛博朋克风"，我按你的偏好调整提示词
2. **替换绘图skill**：如果你有其他生图skill（如DALL-E、Midjourney MCP等），告诉我skill名称，我切换绘图后端

## 退出酒馆

**退出前必须执行：**
1. 自动保存游戏进度（时代、角色、剧情摘要、关键决定）
2. 如有未确认的学习建议，提醒用户
3. 清理 `/tmp/mytavern1/` 临时文件
4. 恢复普通对话模式

### 存档系统

存档保存在 `/tmp/mytavern1/saves/`，JSON格式。

**保存内容：**
- 当前时代和角色
- 剧情摘要（最近发生了什么）
- 关键决定（用户做过的选择）
- 世界状态（重要NPC的状态变化）

**命令：**
- `/save` — 手动保存
- `/load` — 读取最新存档
- `/saves` — 列出所有存档
- 退出酒馆时自动保存

**读档后恢复：**
1. 重新加载对应时代的世界书
2. 注入存档中的剧情摘要作为context
3. 从上次中断的剧情继续

## 动态世界书（OpenClaw独有）

SillyTavern做不到的功能，利用OpenClaw内置能力实现：

### 实时搜索补充（P3-1）
当世界书中找不到相关信息时，自动调用 `web_search`/`tavily_search` 补充。

```
1. 用户提到世界书中没有的内容
2. 调用 dynamic_worldbook.py check 判断是否需要搜索
3. 如果 search_needed=true → 用 tavily_search 搜索
4. 将搜索结果整合进回复，标注【补】
```

### 世界书自学习（P3-2）
对话中学到的新知识，建议写入世界书。

```
1. 对话中出现有价值的新知识（史实、人物关系等）
2. 调用 dynamic_worldbook.py learn 记录建议
3. 退出酒馆前，列出建议让用户确认
4. 用户确认后 apply 写入世界书 + 重建向量索引
```

### LCM跨会话记忆（P3-3）
利用OpenClaw的LCM系统检索历史对话。

```
1. 用户提到之前对话中的内容
2. 调用 lcm_grep 搜索历史
3. 调用 lcm_expand_query 深度检索
4. 整合历史信息，保持连续性
```

**备用方案（无LCM时）**：
- 读取 `~/.openclaw/workspace/memory/` 下的日期日志作为记忆补充
- 读取 `~/.openclaw/workspace/MEMORY.md` 获取长期记忆
- 如果用户提到上次扮演的剧情细节但无法检索，坦诚告知"上次对话的记忆已过期，请提醒我关键情节"
- 世界书自学习（P3-2）不受影响，学到的知识仍会写入世界书

## 文件结构

```
mytavern1/
├── SKILL.md
├── scripts/
│   ├── lorebook_engine.py      # v3世界书引擎（关键词+向量混合检索）
│   ├── build_vector_index.py   # 预计算向量索引（sqlite3）
│   ├── char_manager.py         # 角色卡管理
│   ├── dynamic_worldbook.py    # 动态世界书（搜索补充+自学习）
│   ├── convert_era.py          # shiji-kb → 世界书JSON转换器
│   └── list_eras.py            # 列出可用时代
├── references/
│   ├── eras.md                 # 时代选择菜单
│   └── chatglm-guide.md        # ChatGLM生图指南
└── assets/
    ├── lorebooks/              # 世界书JSON
    ├── characters/             # 角色卡JSON
    ├── indices/                # 向量索引（sqlite3）
    └── learned/                # 自学习知识（待确认）
```

数据源: shiji-kb (CC BY-NC-SA 4.0)
