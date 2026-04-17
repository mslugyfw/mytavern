# MyTavern — 通用角色扮演酒馆

基于世界书的交互式角色扮演系统，为 OpenClaw 智能体设计。

当前内置《史记》世界书（6个时代，1156条知识），将来可挂载《资治通鉴》、二十四史或其他小说世界观。

## ✨ 特性

- **世界书引擎**：参考 SillyTavern world-info.js 实现，支持 scanDepth、scoring、budget、recursive 激活
- **6个时代**：五帝三代、春秋、战国、秦、楚汉、西汉，覆盖史记130章
- **1156个知识条目**：人物300 + 事件736 + 地点100 + 朝代20
- **沉浸式开场**：每个时代有独立的时代背景描述
- **ChatGLM生图**：浏览器自动化生成场景插图（可选）
- **历史收束**：默认遵循正史，允许合理偏移

## 🚀 使用

### 前置要求

- OpenClaw（[GitHub](https://github.com/openclaw/openclaw)）
- Python 3.10+

### 安装

将 `mytavern1/` 目录放入 `~/.openclaw/skills/` 即可自动加载。

### 命令

```
进入酒馆        → 选时代 → 扮演/提问 → /draw生图 → 退出酒馆
/char list      → 查看当前时代可扮演角色
退出酒馆        → 清理context，恢复普通对话
```

## 📂 文件结构

```
mytavern1/
├── SKILL.md                    # OpenClaw skill 定义
├── scripts/
│   ├── list_eras.py            # 列出可用时代
│   ├── convert_era.py          # shiji-kb → 世界书JSON转换器
│   └── load_era.py             # 世界书加载器（ST算法实现）
├── references/
│   ├── eras.md                 # 时代选择菜单
│   └── chatglm-guide.md        # ChatGLM生图指南
└── assets/
    └── lorebooks/
        ├── wudai.json          # 五帝三代（~850KB）
        ├── chunqiu.json        # 春秋（~3.5MB）
        ├── zhanguo.json        # 战国（~800KB）
        ├── qin.json            # 秦（~1MB）
        ├── chuhan.json         # 楚汉（~1.7MB）
        └── xihan.json          # 西汉（~2.9MB）
```

## 📖 世界书引擎

参考 SillyTavern 的 world-info.js 核心算法：

| 功能 | 说明 |
|------|------|
| **scanDepth** | 只扫描最近N条消息中是否出现关键词 |
| **scoring** | primary key命中数 + secondary key命中数排序 |
| **budget** | 25% context预算，逐条注入直到超预算 |
| **group_scoring** | 同group entry共享score |
| **recursive** | 已注入entry内容参与下一轮扫描（链式激活） |
| **constant** | 无条件注入，不受budget限制 |

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

代码部分自由使用。每个世界书数据遵循其上游数据源的许可证。

### 技术参考

- [SillyTavern](https://github.com/SillyTavern/SillyTavern) — 世界书引擎算法参考
- [OpenClaw](https://github.com/openclaw/openclaw) — 智能体运行时
- [ChatGLM](https://chatglm.cn) — 场景插图生成

## 📜 许可证

[CC BY-NC-SA 4.0](LICENSE)

- **代码**：CC BY-NC-SA 4.0（可自由 fork、修改、二次分发）
- **史记世界书数据**：CC BY-NC-SA 4.0（与 shiji-kb 保持一致）
- **未来世界书数据**：各自遵循上游数据源许可证
