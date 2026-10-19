# 智能搜索（满血版）

**给 Dify Agent 与工作流用的多轮网页调研工具。**

市面上大多数搜索插件只做一件事：拿到查询词，调一次搜索 API，返回十条链接，然后结束。这个插件把搜索当成一个过程：先规划几个角度、跑一遍、判断结果够不够、不够就换个说法再搜，最后给出一份把正反观点分开的结构化结论。

当一次搜索不够用时用它：市场调研、竞品分析、事实核查、文献扫描，以及任何答案散落在多个来源里的问题。

## 你会得到什么

你给一个问题，拿回一份**可追溯**的调研过程：

```json
{
  "search_process": [
    {"round": 1, "queries": ["Dify 自托管 云版 对比", "Dify Cloud 价格"],
     "relevant": 7, "verdict": "borderline"},
    {"round": 2, "queries": ["Dify 云版 数据驻留", "Dify 自托管 规模 成本"],
     "relevant": 12, "verdict": "sufficient"}
  ],
  "supporting": [{"point": "自托管可以摆脱按消息计费。", "sources": ["https://..."]}],
  "opposing":   [{"point": "自托管把向量库和模型成本转移到你自己身上。", "sources": ["https://..."]}],
  "neutral_facts": [{"fact": "Dify Cloud 提供三个付费档位。", "source": "https://..."}],
  "summary": "对调研发现的平衡综述。",
  "confidence": "high"
}
```

注意 `search_process` 这个数组。每一轮都记录了用了哪些查询、以及为什么决定继续或停止，所以结论是可追溯的，不是黑箱。第二轮之所以存在，是因为第一轮被判为「不够」，而不是按固定计划硬跑。

## 为什么不用普通搜索插件？

| | 普通搜索插件 | 智能搜索（满血版） |
|---|---|---|
| 搜索轮数 | 一次 | 最多三轮，结果不够就换角度重搜 |
| 查询处理 | 原样发送查询词 | 先拆成 2-3 个搜索角度 |
| 结果评估 | 无 | 评估相关性并决定是否继续 |
| 输出 | 一列链接 | 支持 / 反对 / 中性三类要点，各带来源 |
| 搜索后端 | 通常一个 | 六个，按顺序尝试并自动降级 |

## 搜索后端

**至少配置一个** API 密钥。插件按下表顺序尝试后端；某个后端未配置、不可用或被限流时，自动落到下一个。

| 顺序 | 后端 | 凭据 | 说明 |
|---|---|---|---|
| 1 | **DeepSeek 搜索** | DeepSeek API 密钥 | 单次成本最低，中文覆盖最好。低于其相关性阈值的结果会在进入模型前被丢弃。 |
| 2 | Serper | serper.dev API 密钥 | Google SERP |
| 3 | SerpApi | serpapi.com API 密钥 | Google SERP |
| 4 | Google Programmable Search | API 密钥 + 搜索引擎 ID（`cx`） | |
| 5 | Bing Web Search | Azure 订阅密钥 | |
| 6 | SearXNG | 基础地址 | 自建实例，需开启 JSON 输出 |

未配置的后端会被瞬时跳过，不产生任何成本。只配一个后端也完全可用，插件不要求配满整条链。

## 工作流程

```
[1] 拆词   -> 工作区 LLM 提出 2-3 个搜索角度
[2] 搜索   -> 按顺序使用已配置的后端
[3] 评质   -> LLM 统计相关条数并判断是否足够
              -> 「不够」且还有轮数？带着新角度回到 [1]
[4] 抓正文 -> 可选：从高质量结果页读取正文
[5] 汇总   -> 支持 / 反对 / 中性要点，各带来源
```

所有 LLM 调用都走 Dify 的**反向调用**：插件使用工作区自己的模型和凭据，自身不持有任何 LLM API 密钥。

## 安装与配置

1. 从市场安装本插件，或在自托管的 Dify 中作为本地插件添加。
2. 至少配置一个搜索后端（见上表）。DeepSeek 是成本最低的选项，也是中文内容的最佳选择。
3. 把 **智能搜索** 工具加到 Agent 或工作流中，选择模型后运行。

插件会优雅降级：主后端不可用或被限流时，自动尝试下一个已配置的后端。

## 参数

| 名称 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `query` | string | 是 | - | 要调研的问题或主题。 |
| `model` | model-selector | 是 | - | 用于拆词、评质和汇总的工作区 LLM。 |
| `max_rounds` | number | 否 | 3 | 最大搜索轮数（1-10）。 |
| `fetch_content` | boolean | 否 | false | 抓取并阅读高质量结果的页面正文，遵守 `robots.txt`。 |

## 出网访问

插件**只会**向以下目标发起出网连接请求：

- 管理员已配置的搜索后端：
  - `https://api.deepseek.com`（DeepSeek 搜索）
  - `https://google.serper.dev`
  - `https://serpapi.com`
  - `https://www.googleapis.com`
  - `https://api.bing.microsoft.com`
  - 已配置的 **SearXNG 基础地址**（自建、由运营者指定）
- 结果页 URL，**仅在开启 `fetch_content` 时**，且只在目标站点的 `robots.txt` 明确允许抓取的情况下。

不访问其他任何主机。本插件**不包含任何网页抓取**。

## 源码与许可

源码：<https://github.com/Kagurazaka135/dify-smart-search-full>

MIT 许可。

另有一个姊妹插件，直接读取公开结果页而不调用搜索 API：<https://github.com/Kagurazaka135/smart-search-scraper>。它面向个人与自托管使用；本插件才是面向市场的那个。
