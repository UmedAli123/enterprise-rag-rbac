"""CLI tool to query the RAG system directly with specific access levels."""

import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.generation import answer


def main():
    parser = argparse.ArgumentParser(description="Ask questions to the RAG system with specific allowed access levels.")
    parser.add_argument(
        "--levels",
        nargs="+",
        required=True,
        help="One or more allowed access levels (e.g. public, hr, finance, engineering, executive)"
    )
    parser.add_argument("question", nargs="+", help="Question to ask")
    args = parser.parse_args()

    question_text = " ".join(args.question) if isinstance(args.question, list) else str(args.question)

    print(f"\nQuery: {question_text}")
    print(f"Allowed Levels: {args.levels}\n" + "-" * 50)

    result = answer(question=question_text, allowed_levels=args.levels)

    print("\nAnswer:\n", result["answer"])
    print("\nSources:")
    if result["sources"]:
        for s in result["sources"]:
            print(f"- [{s['doc_id']}] {s['title']} -> {s['section']}")
    else:
        print("(No sources cited)")
    print("-" * 50 + "\n")


if __name__ == "__main__":
    main()
