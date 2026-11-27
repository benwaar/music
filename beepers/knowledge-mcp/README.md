# knowledge-mcp

Rust MCP server for the knowledge corpus. Exposes keyword search, semantic search, and read tools so Claude can query Z80/Spectrum/WASM chunks mid-session.

One of three access layers to the same knowledge base: this MCP server is for Claude, the `/asm` skill is for the user, and the FAISS embeddings are for the local LLM (incant RAG).

All three read from the same `knowledge/chunks/*.md` files — same source of truth, three access patterns for three consumers:

| Layer | Consumer | Access pattern |
|-------|----------|----------------|
| **knowledge-mcp** | Claude | Keyword index + ONNX semantic search, MCP stdio |
| **/asm skill** | User | Shell script, browsable from the CLI |
| **FAISS embeddings** | Local LLM (incant) | Semantic vector search, RAG retrieval |

## Build

```bash
cargo build --release
```

Binary: `target/release/knowledge-mcp`

## How it works

On startup:
1. Walks `../knowledge/chunks/` and builds an in-memory keyword index (topic, filename, body text)
2. Loads the ONNX sentence-transformer model + pre-computed vectors from `../knowledge/index/` for semantic search

**Keyword search** — scoring: +10 topic match, +5 filename match, +1 body match. Returns top 5. Best for exact names like `LD A` or `BEEPER`.

**Semantic search** — embeds the query with the ONNX model, dot-product against pre-computed chunk vectors, returns top 5 by cosine similarity. Best for natural language queries like "how to play audio on the Spectrum".

## Tools

| Tool | Description |
|------|-------------|
| `search(query, category?)` | Keyword search across all chunks. Optional category filter (e.g. `z80-instruction`, `wasm-spec`). |
| `search_semantic(query, category?)` | Semantic search using sentence embeddings. Optional category filter. Requires ONNX model + vectors in `knowledge/index/`. |
| `read(chunk_id)` | Read full content of a chunk. ID format: `category/stem` (e.g. `z80-instruction/LD`). |

## Resources

| URI | Description |
|-----|-------------|
| `corpus://categories` | List of chunk categories with file counts |
| `corpus://stats` | Total chunk count and last rebuild timestamp |

## Configuration

Registered in `.mcp.json` at the project root:

```json
{
  "mcpServers": {
    "knowledge-corpus": {
      "type": "stdio",
      "command": "./knowledge-mcp/target/release/knowledge-mcp",
      "args": []
    }
  }
}
```

The server expects to be launched from the repo root (it looks for `knowledge/chunks/` relative to the working directory).

## Dependencies

- `rust-mcp-sdk` v2 (MCP protocol, stdio transport)
- `tract-onnx` (ONNX inference for sentence-transformer embeddings)
- `tokenizers` (HuggingFace tokenizer for query encoding)
- `serde` / `serde_json` (frontmatter parsing)
- `tokio` (async runtime)

## Learn

- [Embeddings and RAG](../explainers/embeddings-and-rag.md) — how text becomes vectors, FAISS indexing, and why this project uses sentence-transformers here but ollama in incant
