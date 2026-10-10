# 智能搜索（满血版）

一个 Dify 工具插件：把一个问题变成**多轮、LLM 驱动的网页调研**，并返回结构化的平衡汇总。

市面上的搜索插件大多只做一件事——拿一个查询，调一次搜索 API，回十条链接。
本插件往上补一层：它会**规划**搜索、**评估**结果、结果不够就**换词重搜**，最后把答案
拆成"支持 / 反对 / 中性事实"三部分回报。

## 它做什么

```
[1] 拆词       -> 让工作区 LLM 生成 2-3 个搜索角度
[2] 并发搜索   -> Serper / SerpApi（主力），Google / Bing / SearXNG 自动降级
[3] 评质       -> LLM 统计相关条数并给出"够/勉强/不够"
                  -> 不够且还有轮数？带着新角度回到 [1]
[4] 抓正文     -> 可选、需显式开启：从高质量结果 URL 取正文
[5] 结构化汇总 -> 正/反/中性观点，每条带来源
```

所有 LLM 调用都走 Dify 的**反向调用**：插件用工作区自己的模型和凭据，
自身不持有任何 LLM 密钥。

## 参数

| 名称 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `query` | string | 是 | — | 要调研的问题或主题。 |
| `model` | model-selector | 是 | — | 用于拆词、评质、汇总的工作区 LLM。 |
| `max_rounds` | number | 否 | `3` | 停止细化前的最大搜索轮数。 |
| `fetch_content` | boolean | 否 | `false` | 是否抓取并阅读高质量结果的正文（遵守 robots.txt）。 |

## 输出

```json
{
  "search_process": [
    {"round": 1, "queries": ["..."], "relevant": 5, "verdict": "not enough"}
  ],
  "supporting": [{"point": "...", "sources": ["https://..."]}],
  "opposing": [{"point": "...", "sources": ["https://..."]}],
  "neutral_facts": [{"fact": "...", "source": "https://..."}],
  "summary": "200-300 字的综合判断。",
  "confidence": "high | medium | low"
}
```

## 配置

1. 从 marketplace 安装（或作为本地插件加入自建 Dify）。
2. 在 provider 凭据里配置**至少一个**搜索后端：
   - **Serper** —— 从 [serper.dev](https://serper.dev) 拿的 API key（推荐）。
   - **SerpApi** —— 从 [serpapi.com](https://serpapi.com) 拿的 API key。
   - **Google Programmable Search** —— API key **加**搜索引擎 ID（`cx`）。
   - **Bing Web Search** —— Azure 订阅密钥。
   - **SearXNG** —— 自建实例的 base URL（需开启 JSON 输出）。
3. 把 `Smart Search` 工具加进 agent 或 workflow，选好模型即可运行。

插件会优雅降级：主力后端不可用或被限流时，自动尝试下一个已配置的后端。

## 出站访问域名

插件**只会**向以下目标发起出站请求：

- 管理员已配置的搜索后端：
  - `https://google.serper.dev`
  - `https://serpapi.com`
  - `https://www.googleapis.com`
  - `https://api.bing.microsoft.com`
  - 配置的 **SearXNG base URL**（自建，由运营者指定）
- 结果页 URL，**仅在开启 `fetch_content` 时**，且必须先确认目标站的 `robots.txt` 允许抓取。

不会访问任何其他主机。**没有任何形式的网页裸爬。**

## 两个版本

本插件是一对姊妹插件中的"满血版"。另一位是**智能搜索（裸爬版）**
（[仓库](https://github.com/Kagurazaka135/dify-smart-search-scraper)），
跑**完全相同**的「拆词 → 搜索 → 评质 → 重搜 → 汇总」流水线，只把搜索层换掉。
按自己的场景挑取舍：

| | **满血版**（本插件） | **裸爬版** |
|---|---|---|
| 搜索层 | 官方搜索 API | 直接读公开结果页（HTML） |
| 后端 | Serper / SerpApi / Google CSE / Bing / SearXNG | Bing / DuckDuckGo |
| 凭据 | 需至少一个 API key | **零凭据** |
| `fetch_content` | 遵守 `robots.txt` | 直接抓取，不查 `robots.txt` |
| 定位 | 上架 marketplace / 通用 | 个人自用 / 自建环境 |

想要零配置、零 API key → 用裸爬版；想要只走官方 API、且能上架的版本 → 用本插件。

## 许可

MIT
