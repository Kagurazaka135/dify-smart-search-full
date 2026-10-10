# Privacy Policy

## Data handled by this plugin

Smart Search (Full) is a tool plugin for Dify. It performs web search on behalf of the
user and produces a structured summary. To do this it processes:

- **The search query** the user submits, together with any derived search keywords.
- **Public search results** returned by the configured search backend (title, snippet, URL).
- **Public page text** retrieved from result URLs, and only when the user explicitly
  enables the `fetch_content` option.

## Where data is sent

- **Search backends** (only the ones the workspace administrator has configured):
  Serper.dev, Google Programmable Search, Bing Web Search, or a self-hosted SearXNG
  instance. The query is sent to the backend(s) that are configured and reachable.
- **The workspace language model** selected in the `model` parameter. Query expansion,
  quality scoring and summarization are performed by that model through Dify's
  reverse-invocation mechanism. The plugin never stores or sees any model API key.
- **Target pages**, only when `fetch_content` is enabled: the plugin requests the
  result URL's `robots.txt` first and skips any URL that disallows crawling.

## What is stored

The plugin is **stateless**. It does not persist queries, results, or page content,
and it does not run any analytics or telemetry. All processing happens in-memory for
the duration of a single tool call.

## Credentials

Search API keys are supplied by the workspace administrator through the provider
credentials form in Dify. They are held by the Dify platform, not by this plugin, and
are never logged or transmitted anywhere other than the corresponding vendor API.

## Contact

Open an issue in the plugin's repository for any privacy question.
