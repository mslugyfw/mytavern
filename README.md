# MyTavern — 史记角色扮演酒馆

基于《史记》世界书的交互式历史角色扮演系统，为 OpenClaw 智能体设计。

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

### 数据源

本项目的世界书数据源自 [shiji-kb](https://github.com/baojie/shiji-kb)（史记知识库）：

> 鲍捷，史记知识库，2026，在线发布于 https://github.com/baojie/shiji-kb
>
> shiji-kb 基于 AI Agent 从《史记》原文中提取实体、事件、地点等结构化知识，覆盖130章。

### 许可证兼容性

| 项目 | 许可证 | 兼容性 |
|------|--------|--------|
| **shiji-kb**（数据源） | CC BY-NC-SA 4.0 | 源数据 |
| **本项目**（代码+衍生数据） | CC BY-NC-SA 4.0 | ✅ 兼容 |

本项目为 shiji-kb 的衍生作品，遵守 CC BY-NC-SA 4.0：
- **BY**：引用 shiji-kb 并链接原项目
- **NC**：非商业用途
- **SA**：衍生作品使用相同许可证

### 技术参考

- [SillyTavern](https://github.com/SillyTavern/SillyTavern) — 世界书引擎算法参考
- [OpenClaw](https://github.com/openclaw/openclaw) — 智能体运行时
- [ChatGLM](https://chatglm.cn) — 场景插图生成

## 📜 许可证

[CC BY-NC-SA 4.0](LICENSE)

代码和世界书数据均以 CC BY-NC-SA 4.0 发布，与上游 shiji-kb 许可证保持一致。
