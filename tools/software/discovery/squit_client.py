import json
import requests
import argparse
import sys
import os


class SquitClient:
    def __init__(self, api_key, base_url="https://squit-mcp.example.com/mcp"):
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json"
        }

    def _call_tool(self, tool_name, arguments):
        payload = {
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }
        try:
            response = requests.post(self.base_url, headers=self.headers, json=payload, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"[ERROR] SQUIT Call Failed: {e}", file=sys.stderr)
            return None

    def search(self, query, domains=None, types=None, limit=10):
        args = {"query": query, "limit": limit}
        if domains:
            args["business_domains"] = domains
        if types:
            args["object_types"] = types
        return self._call_tool("squit_search", args)

    def get_code(self, object_id):
        return self._call_tool("squit_get_code", {"parent_object_id": object_id})

    def dependencies(self, object_name, limit=20):
        return self._call_tool("squit_dependencies", {"object_name": object_name, "limit": limit})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SQUIT Semantic SQL Client")
    parser.add_argument("--action", required=True, choices=["search", "get_code", "deps"])
    parser.add_argument("--query", help="Search query or object name")
    parser.add_argument("--id", help="Object ID for get_code")
    parser.add_argument("--key", default=os.environ.get("SQUIT_API_KEY", ""))

    args = parser.parse_args()
    if not args.key:
        print("[ERROR] SQUIT_API_KEY not set. Add it to your .env file or pass --key.", file=sys.stderr)
        sys.exit(1)
    client = SquitClient(args.key)

    if args.action == "search":
        result = client.search(args.query)
        print(json.dumps(result, indent=2))
    elif args.action == "get_code":
        result = client.get_code(args.id)
        print(json.dumps(result, indent=2))
    elif args.action == "deps":
        result = client.dependencies(args.query)
        print(json.dumps(result, indent=2))
