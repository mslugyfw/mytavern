# ChatGLM 生图操作指南

## 浏览器操作

打开页面: `https://chatglm.cn/main/gdetail/65a232c082ff90a2ad2f15e2`

### 注入prompt（Vue.js textarea不能用直接type）
```javascript
element.value = '<prompt>';
element.dispatchEvent(new Event('input'))
```

### 切换16:9
```javascript
document.querySelectorAll('[class*=ratio]')[1].click()
```

### 关闭水印
```javascript
document.querySelector('[class*=watermark]')?.click()
```

### 图片下载
图片URL格式: `https://sfile.chatglm.cn/testpath/<uuid>.png`

## 各时代风格关键词

| 时代 | 英文prompt关键词 |
|------|-----------------|
| 五帝 | ancient China mythology, oracle bone, bronze, epic |
| 春秋 | Spring and Autumn, bamboo slips, silk, scholarly |
| 战国 | Warring States, iron weapons, cavalry, ink wash |
| 秦 | Qin dynasty, terracotta, Great Wall, grand, dark |
| 楚汉 | Chu-Han, epic battle, dramatic, ink wash |
| 西汉 | Western Han, Silk Road, Hanfu, Chang'an, elegant |

## Prompt模板
```
<时代风格>, <场景描述>, traditional Chinese ink wash, 
fine brush, muted colors, cinematic, no text, 16:9
```
