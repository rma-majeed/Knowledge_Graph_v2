"""Automotive Consulting GraphRAG Agent -- CLI entry point.

Usage:
    python src/main.py ingest --path <folder_or_file> [--db <db_path>]

Examples:
    python src/main.py ingest --path documents/
    python src/main.py ingest --path report.pdf --db data/chunks.db
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from pathlib import Path

# Ensure project root is on sys.path when running as `python src/main.py`
_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


def cmd_ingest(args: argparse.Namespace) -> int:
    """Run the ingestion pipeline on a file or directory."""
    from src.ingest.pipeline import ingest_directory, ingest_document

    target = Path(args.path)
    db_path = Path(args.db)

    # Ensure data directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)

    start = time.perf_counter()

    if target.is_dir():
        results = ingest_directory(target, db_path=db_path)
        ingested = [r for r in results if not r["skipped"]]
        skipped = [r for r in results if r["skipped"]]
        total_chunks = sum(r["chunks_inserted"] for r in ingested)
        elapsed = time.perf_counter() - start
        print(
            f"\nIngestion complete in {elapsed:.2f}s\n"
            f"  Documents ingested: {len(ingested)}\n"
            f"  Documents skipped (already indexed): {len(skipped)}\n"
            f"  Total chunks stored: {total_chunks}\n"
            f"  Database: {db_path}"
        )
    elif target.is_file():
        result = ingest_document(target, db_path=db_path)
        elapsed = time.perf_counter() - start
        if result["skipped"]:
            print(f"Skipped (already indexed): {result['filename']} ({elapsed:.2f}s)")
        else:
            print(
                f"Ingested: {result['filename']} -- "
                f"{result['chunks_inserted']} chunks in {elapsed:.2f}s"
            )
    else:
        print(f"Error: {target} is not a file or directory.", file=sys.stderr)
        return 1

    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    """Print ingestion statistics from the database."""
    db_path = Path(args.db)
    if not db_path.exists():
        print(f"Database not found: {db_path}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(str(db_path))
    doc_count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    chunk_count = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    pending = conn.execute(
        "SELECT COUNT(*) FROM chunks WHERE embedding_flag = 0"
    ).fetchone()[0]
    conn.close()

    print(
        f"Database: {db_path}\n"
        f"  Documents: {doc_count}\n"
        f"  Chunks total: {chunk_count}\n"
        f"  Chunks pending embedding: {pending}"
    )
    return 0


def cmd_embed(args: argparse.Namespace) -> int:
    """Run the embedding pipeline on all pending chunks."""
    import sqlite3
    import chromadb
    from src.embed.pipeline import check_lm_studio, embed_all_chunks

    db_path = Path(args.db)
    chroma_path = Path(args.chroma)

    if not db_path.exists():
        print(f"Error: Database not found: {db_path}", file=sys.stderr)
        return 1

    # Ensure chroma directory exists
    chroma_path.mkdir(parents=True, exist_ok=True)

    # Health check before connecting to LM Studio
    if not check_lm_studio():
        print(
            "Error: LM Studio is not running or not reachable at localhost:1234.\n"
            "Start LM Studio, load the embedding model, and retry.",
            file=sys.stderr,
        )
        return 1

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")

    try:
        chroma_client = chromadb.PersistentClient(path=str(chroma_path))
        start = time.perf_counter()
        result = embed_all_chunks(
            conn=conn,
            chroma_client=chroma_client,
            model=args.model,
        )
        elapsed = time.perf_counter() - start
        print(
            f"\nEmbedding complete in {elapsed:.2f}s\n"
            f"  Chunks embedded: {result['chunks_embedded']}\n"
            f"  API batches: {result['batches']}\n"
            f"  ChromaDB: {chroma_path}"
        )
    finally:
        conn.close()

    return 0


def cmd_graph(args: argparse.Namespace) -> int:
    """Run the knowledge graph construction pipeline on embedded chunks."""
    import kuzu
    from src.embed.pipeline import check_lm_studio
    from src.graph.pipeline import build_knowledge_graph

    db_path = Path(args.db)
    graph_path = Path(args.graph)
    state_path = Path(args.state)

    if not db_path.exists():
        print(f"Error: Database not found: {db_path}", file=sys.stderr)
        return 1

    # Health check LM Studio before starting (LLM required for extraction)
    if not check_lm_studio():
        print(
            "Error: LM Studio is not running or not reachable at localhost:1234.\n"
            "Start LM Studio, load the LLM model (Qwen2.5-7B-Instruct), and retry.",
            file=sys.stderr,
        )
        return 1

    # Ensure parent directory exists (kuzu creates the db path itself)
    graph_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    db = kuzu.Database(str(graph_path))

    try:
        start = time.perf_counter()
        result = build_knowledge_graph(
            conn=conn,
            db=db,
            model=args.model,
            state_path=str(state_path),
        )
        elapsed = time.perf_counter() - start
        print(
            f"\nKnowledge graph complete in {elapsed:.2f}s\n"
            f"  Chunks processed: {result['chunks_processed']}\n"
            f"  Entities extracted: {result['entities_extracted']}\n"
            f"  LLM batches: {result['batches']}\n"
            f"  Graph explosion alert: {'YES (see stderr)' if result['alert'] else 'No'}\n"
            f"  KuzuDB: {graph_path}\n"
            f"  State: {state_path}"
        )
    finally:
        conn.close()

    return 0


def cmd_query(args: argparse.Namespace) -> int:
    """Run the query pipeline and print answer + citations."""
    import kuzu
    from src.embed.pipeline import check_lm_studio
    from src.query.pipeline import answer_question

    db_path = Path(args.db)
    graph_path = Path(args.graph)
    chroma_path = Path(args.chroma)

    if not db_path.exists():
        print(f"Error: Database not found: {db_path}", file=sys.stderr)
        return 1

    if not graph_path.exists():
        print(f"Error: KuzuDB not found: {graph_path}", file=sys.stderr)
        return 1

    if not check_lm_studio():
        print(
            "Error: LM Studio is not running at localhost:1234.\n"
            "Ensure LM Studio is running. For query, load the LLM model\n"
            f"({args.llm_model}) — not the embedding model.",
            file=sys.stderr,
        )
        return 1

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    db = kuzu.Database(str(graph_path))

    try:
        result = answer_question(
            question=args.question,
            conn=conn,
            kuzu_db=db,
            chroma_path=str(chroma_path),
            embed_model=args.embed_model,
            llm_model=args.llm_model,
            n_results=args.top_k,
        )
        print(f"\n{result['answer']}\n")
        elapsed = result.get("elapsed_s", 0.0)
        print(f"Query completed in {elapsed:.1f}s")
    finally:
        conn.close()

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="graphrag",
        description="Automotive Consulting GraphRAG Agent",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # ingest subcommand
    p_ingest = subparsers.add_parser("ingest", help="Ingest PDF/PPTX documents")
    p_ingest.add_argument("--path", required=True, help="File or directory to ingest")
    p_ingest.add_argument(
        "--db", default="data/chunks.db", help="SQLite database path (default: data/chunks.db)"
    )
    p_ingest.set_defaults(func=cmd_ingest)

    # stats subcommand
    p_stats = subparsers.add_parser("stats", help="Show database statistics")
    p_stats.add_argument(
        "--db", default="data/chunks.db", help="SQLite database path (default: data/chunks.db)"
    )
    p_stats.set_defaults(func=cmd_stats)

    # embed subcommand
    p_embed = subparsers.add_parser("embed", help="Generate embeddings for pending chunks")
    p_embed.add_argument(
        "--db", default="data/chunks.db", help="SQLite database path (default: data/chunks.db)"
    )
    p_embed.add_argument(
        "--chroma", default="data/chroma_db", help="ChromaDB path (default: data/chroma_db)"
    )
    p_embed.add_argument(
        "--model", default="nomic-embed-text-v1.5",
        help="LM Studio embedding model name (default: nomic-embed-text-v1.5)"
    )
    p_embed.set_defaults(func=cmd_embed)

    # graph subcommand
    p_graph = subparsers.add_parser("graph", help="Build knowledge graph from embedded chunks")
    p_graph.add_argument(
        "--db", default="data/chunks.db", help="SQLite database path (default: data/chunks.db)"
    )
    p_graph.add_argument(
        "--graph", default="data/kuzu_db", help="KuzuDB directory path (default: data/kuzu_db)"
    )
    p_graph.add_argument(
        "--model", default="Qwen2.5-7B-Instruct",
        help="LM Studio LLM model name (default: Qwen2.5-7B-Instruct)"
    )
    p_graph.add_argument(
        "--state", default="data/extraction_state.json",
        help="Extraction checkpoint file (default: data/extraction_state.json)"
    )
    p_graph.set_defaults(func=cmd_graph)

    # query subcommand
    p_query = subparsers.add_parser("query", help="Answer a natural language question")
    p_query.add_argument(
        "--question", required=True,
        help="Natural language question to answer"
    )
    p_query.add_argument(
        "--db", default="data/chunks.db",
        help="SQLite database path (default: data/chunks.db)"
    )
    p_query.add_argument(
        "--chroma", default="data/chroma_db",
        help="ChromaDB path (default: data/chroma_db)"
    )
    p_query.add_argument(
        "--graph", default="data/kuzu_db",
        help="KuzuDB directory path (default: data/kuzu_db)"
    )
    p_query.add_argument(
        "--embed-model", default="nomic-embed-text-v1.5",
        dest="embed_model",
        help="LM Studio embedding model (default: nomic-embed-text-v1.5)"
    )
    p_query.add_argument(
        "--llm-model", default="Qwen2.5-7B-Instruct",
        dest="llm_model",
        help="LM Studio LLM model for answer generation (default: Qwen2.5-7B-Instruct)"
    )
    p_query.add_argument(
        "--top-k", type=int, default=10,
        dest="top_k",
        help="Number of vector results before graph expansion (default: 10)"
    )
    p_query.set_defaults(func=cmd_query)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
