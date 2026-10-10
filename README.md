# Smart Search (Full)

A Dify tool plugin that turns a single question into a **multi-round, LLM-driven web
research pass** and returns a structured, balanced summary.

Most search plugins in the marketplace do one thing: take a query, call a search
API, hand back a list of ten links. This plugin fills the gap one step further up the
stack — it *plans* the search, *judges* what came back, *re-searches* when the results
are thin, and *reports* the answer with supporting and opposing points separated out.

## What it does

```
[1] Query expansion   -> the workspace LLM proposes 2-3 search angles
[2] Concurrent search -> Serper / SerpApi (primary), Google CSE / Bing / SearXNG as fallbacks
[3] Quality scoring   -> the LLM counts relevant hits and rates sufficiency
                         -> "not enough" and rounds remain? go back to [1] with new angles
[4] Content fetch     -> optional, opt-in: pull page text from high-quality URLs
[5] Structured summary -> positive / negative / neutral points, each with sources
```

Every LLM call runs through Dify's **reverse invocation**: the plugin uses the
workspace's own models and credentials, and never holds an LLM API key of its own.

## Parameters

| Name | Type | Required | Default | Description |
|---|---|---|---|---|
| `query` | string | yes | — | The question or topic to research. |
| `model` | model-selector | yes | — | Workspace LLM used for expansion, scoring and summarization. |
| `max_rounds` | number | no | `3` | Maximum search rounds before the plugin stops refining. |
| `fetch_content` | boolean | no | `false` | Fetch and read page text from top result URLs (respects `robots.txt`). |

## Output

```json
{
  "search_process": [
    {"round": 1, "queries": ["..."], "relevant": 5, "verdict": "not enough"}
  ],
  "supporting": [{"point": "...", "sources": ["https://..."]}],
  "opposing": [{"point": "...", "sources": ["https://..."]}],
  "neutral_facts": [{"fact": "...", "source": "https://..."}],
  "summary": "200-300 word synthesis with a confidence judgement.",
  "confidence": "high | medium | low"
}
```

## Setup

1. Install the plugin from the marketplace (or add it as a local plugin in a
   self-hosted Dify).
2. Configure the provider credentials with **at least one** search backend:
   - **Serper** — an API key from [serper.dev](https://serper.dev) (recommended).
   - **SerpApi** — an API key from [serpapi.com](https://serpapi.com).
   - **Google Programmable Search** — an API key **and** a search-engine ID (`cx`).
   - **Bing Web Search** — an Azure subscription key.
   - **SearXNG** — the base URL of a self-hosted instance with the JSON format enabled.
3. Add the `Smart Search` tool to an agent or workflow, pick a model, and run it.

The plugin degrades gracefully: if the primary backend is unavailable or rate-limited,
it automatically tries the next configured backend.

## Outbound network access

The plugin makes outbound requests **only** to the following destinations:

- Search backends the administrator has configured:
  - `https://google.serper.dev`
  - `https://serpapi.com`
  - `https://www.googleapis.com`
  - `https://api.bing.microsoft.com`
  - the configured **SearXNG base URL** (self-hosted, operator-defined)
- Result-page URLs, **only when `fetch_content` is enabled**, and only after the
  target's `robots.txt` explicitly allows fetching.

No other host is contacted. There is **no web scraping** of any kind.

## The two versions

This plugin is one half of a pair. Its sibling, **Smart Search (Scraper)**
([repository](https://github.com/Kagurazaka135/dify-smart-search-scraper)), runs the
exact same plan → search → judge → re-search → report pipeline, but swaps the search
layer out. Pick whichever trade-off fits your setup:

| | **Full** (this plugin) | **Scraper** |
|---|---|---|
| Search layer | Official search APIs | Reads public result pages directly (HTML) |
| Backends | Serper / SerpApi / Google CSE / Bing / SearXNG | Bing / DuckDuckGo |
| Credentials | At least one API key | **None** |
| `fetch_content` | Honors `robots.txt` | Fetches directly, no `robots.txt` check |
| Intended for | Marketplace / general use | Personal & self-hosted use |

Want zero setup and no API keys? Use the Scraper. Want a version that only talks to
official APIs — and can be published to the marketplace? Use this one.

## License

MIT
