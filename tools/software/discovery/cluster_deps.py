import os
import json
import re
import argparse
from collections import defaultdict


def extract_deps_package_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            deps = list(data.get("dependencies", {}).keys()) + list(
                data.get("devDependencies", {}).keys()
            )
            return sorted(deps)
    except Exception:
        return []


def extract_deps_requirements(path):
    try:
        deps = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.split("#")[0].strip()
                if line:
                    pkg = re.split(r"[=><~]", line)[0]
                    deps.append(pkg)
        return sorted(deps)
    except Exception:
        return []


def extract_deps_pom_xml(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
            # Simple regex for artifactIds to avoid heavy XML parsing
            deps = re.findall(r"<artifactId>(.*?)</artifactId>", content)
            return sorted(list(set(deps)))
    except Exception:
        return []


def extract_deps_csproj(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
            # Look for PackageReference Include="..."
            deps = re.findall(r'PackageReference\s+Include="(.*?)"', content)
            return sorted(list(set(deps)))
    except Exception:
        return []


def _process_deps_file(root, filename, extractor, prefix, clusters):
    deps = extractor(os.path.join(root, filename))
    if deps:
        clusters[f"{prefix}:" + ",".join(deps)].append(root)


def _process_dir_files(root: str, files: list[str], clusters: dict):
    if "package.json" in files:
        _process_deps_file(
            root, "package.json", extract_deps_package_json, "npm", clusters
        )

    if "requirements.txt" in files:
        _process_deps_file(
            root, "requirements.txt", extract_deps_requirements, "pip", clusters
        )

    if "pom.xml" in files:
        _process_deps_file(root, "pom.xml", extract_deps_pom_xml, "maven", clusters)

    for f in files:
        if f.endswith(".csproj"):
            _process_deps_file(root, f, extract_deps_csproj, "nuget", clusters)


def cluster_projects(target_dir):
    clusters = defaultdict(list)

    for root, dirs, files in os.walk(target_dir):
        dirs[:] = [
            d
            for d in dirs
            if d not in {".git", "node_modules", "venv", "__pycache__", "dist", "build"}
        ]
        _process_dir_files(root, files, clusters)

    return {sig: paths for sig, paths in clusters.items() if len(paths) > 1}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Cluster projects by identical dependencies."
    )
    parser.add_argument("path", help="Path to scan")
    parser.add_argument("--out", default="deps_clusters.json", help="Output JSON file")
    args = parser.parse_args()

    print(f"Scanning {args.path} for duplicate project signatures...")
    clusters = cluster_projects(args.path)

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"clusters": clusters}, f, indent=2)

    print(f"Found {len(clusters)} clusters of projects with identical dependencies.")
    print(f"Report saved to {args.out}")
