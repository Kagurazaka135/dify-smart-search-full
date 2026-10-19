# Smart Search (Full)

**Multi-round web search and research for Dify agents and workflows.**

Most search plugins in the marketplace do one thing: take a query, call a search API,
hand back ten links, and stop. This one treats search as a process. It plans several
angles, runs them, judges what came back, searches again when the results are thin, and
reports a structured answer with supporting and opposing points kept apart.

Use it when a single search engine query is not enough: market research, competitive
analysis, fact checking, literature scanning, or any question whose answer is spread
across several sources.

## What you get

You give it a question. You get back a research pass you can audit:

```json
{
  "search_process": [
    {"round": 1, "queries": ["Dify self-hosted vs cloud", "Dify Cloud pricing"],
     "relevant": 7, "verdict": "borderline"},
    {"round": 2, "queries": ["Dify cloud data residency", "Dify self-hosted cost at scale"],
     "relevant": 12, "verdict": "sufficient"}
  ],
  "supporting": [{"point": "Self-hosting removes per-message billing.", "sources": ["https://..."]}],
  "opposing":   [{"point": "Self-hosting shifts vector DB and model costs onto you.", "sources": ["https://..."]}],
  "neutral_facts": [{"fact": "Dify Cloud offers three paid tiers.", "source": "https://..."}],
  "summary": "A balanced synthesis of the findings.",
  "confidence": "high"
}
```

Note the `search_process` array. Every round records the queries it used and why it
decided to continue or stop, so the answer is traceable rather than a black box. Round
two exists because round one was judged thin, not because of a fixed schedule.

## Why not a plain search plugin?

| | Plain search plugins | Smart Search (Full) |
|---|---|---|
| Search rounds | One | Up to three, re-searching when results are thin |
| Query handling | Sends your query as-is | Expands it into 2-3 search angles first |
| Judging results | None | Scores relevance and decides whether to continue |
| Output | A list of links | Supporting / opposing / neutral points, each with sources |
| Search backends | Usually one | Six, tried in order with automatic fallback |

## Search backends

Configure **at least one** API key. The plugin tries backends in the order below and
falls through to the next one when a backend is unset, unavailable, or rate-limited.

| Order | Backend | Credentials | Notes |
|---|---|---|---|
| 1 | **DeepSeek Search** | DeepSeek API key | Cheapest per request and the strongest Chinese coverage. Results below its relevance threshold are discarded before they reach the model. |
| 2 | Serper | serper.dev API key | Google SERP |
| 3 | SerpApi | serpapi.com API key | Google SERP |
| 4 | Google Programmable Search | API key and search engine ID (`cx`) | |
| 5 | Bing Web Search | Azure subscription key | |
| 6 | SearXNG | Base URL | Self-hosted instance with JSON output enabled |

Backends that are not configured are skipped instantly at no cost. If you configure only
one, you get one — the plugin does not require the full chain.

## How it works

```
[1] Query expansion    -> the workspace LLM proposes 2-3 search angles
[2] Search             -> the configured backends, tried in order
[3] Quality scoring    -> the LLM counts relevant hits and rates sufficiency
                          -> "not enough" and rounds remain? go back to [1] with new angles
[4] Content fetch      -> optional: pull page text from high-quality URLs
[5] Structured summary -> supporting / opposing / neutral points, each with sources
```

Every LLM call runs through Dify's **reverse invocation**. The plugin uses the
workspace's own models and credentials and never holds an LLM API key of its own.

## Setup and usage

1. Install the plugin from the marketplace, or add it as a local plugin on a
   self-hosted Dify instance.
2. Configure at least one search backend (see the table above). DeepSeek is the
   cheapest option and the best choice for Chinese-language content.
3. Add the **Smart Search** tool to an agent or workflow, select a model, and run it.

Basic usage in an agent: ask a research-shaped question. The tool decides how many
rounds it needs; `max_rounds` caps it. In a workflow, wire the tool node's `json` output
into a downstream LLM or code node when you want the structured fields rather than the
prose `text` output.

The plugin degrades gracefully: if the primary backend is unavailable or rate-limited,
it automatically tries the next configured backend.

## Parameters

| Name | Type | Required | Default | Description |
|---|---|---|---|---|
| `query` | string | yes | - | The question or topic to research. |
| `model` | model-selector | yes | - | Workspace LLM used for expansion, scoring and summarization. |
| `max_rounds` | number | no | 3 | Maximum number of search rounds (1-10). |
| `fetch_content` | boolean | no | false | Fetch and read page text from top results. Respects `robots.txt`. |

## Outbound network access

The plugin makes outbound connection requests **only** to the destinations below:

- The search backends the administrator has configured:
  - `https://api.deepseek.com` (DeepSeek Search)
  - `https://google.serper.dev`
  - `https://serpapi.com`
  - `https://www.googleapis.com`
  - `https://api.bing.microsoft.com`
  - the configured **SearXNG base URL** (self-hosted, operator-defined)
- Result-page URLs, **only when `fetch_content` is enabled**, and only after the
  target site's `robots.txt` explicitly allows fetching.

No other host is contacted. There is **no web scraping** of any kind in this plugin.

## Source and license

Source code: <https://github.com/Kagurazaka135/dify-smart-search-full>

MIT licensed.

A sibling plugin that reads public result pages directly instead of calling search APIs
is available at <https://github.com/Kagurazaka135/smart-search-scraper>. It is intended
for personal and self-hosted use; this plugin is the one intended for the marketplace.
