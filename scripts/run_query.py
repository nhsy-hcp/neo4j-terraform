import os
import sys
from neo4j import GraphDatabase

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")


def run_queries(file_path):
    if not os.path.exists(file_path):
        print(f"Error: {file_path} not found.")
        sys.exit(1)

    with open(file_path, "r") as f:
        content = f.read()

    # Simple split by semicolon, ignoring comments
    queries = [q.strip() for q in content.split(";") if q.strip()]

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        with driver.session() as session:
            for i, query in enumerate(queries):
                # Skip comments for the title but print them if they exist
                lines = query.split("\n")
                title = f"Query {i + 1}"
                actual_query = []
                for line in lines:
                    if line.strip().startswith("//"):
                        title = line.strip("// ").strip()
                    else:
                        actual_query.append(line)

                print(f"\n--- {title} ---")
                print("\n".join(actual_query).strip())
                print("-" * (len(title) + 8))

                result = session.run(query)
                records = list(result)

                if not records:
                    print("(No results)")
                    continue

                # Print header
                keys = result.keys()
                print(" | ".join(keys))
                print("-" * (sum(len(k) for k in keys) + 3 * (len(keys) - 1)))

                # Print rows
                for record in records:
                    print(" | ".join(str(record[k]) for k in keys))
    except Exception as e:
        print(f"Error executing queries: {e}")
        sys.exit(1)
    finally:
        driver.close()


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "examples/queries.cql"
    run_queries(path)
