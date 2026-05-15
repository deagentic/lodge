import os
import sys


def main():
    event_name = os.environ.get("GITHUB_EVENT_NAME")
    if event_name != "pull_request":
        print("Not a PR, skipping Gitflow enforcement.")
        return 0

    base_ref = os.environ.get("GITHUB_BASE_REF", "")
    head_ref = os.environ.get("GITHUB_HEAD_REF", "")

    if not head_ref:
        print("Could not detect GITHUB_HEAD_REF, skipping.")
        return 0

    print(f"Checking Gitflow: {head_ref} -> {base_ref}")

    if base_ref == "main":
        valid_prefixes = ("staging", "release/", "hotfix/")
        if not any(head_ref.startswith(p) for p in valid_prefixes):
            if head_ref != "staging":
                print(
                    f"Error: PR to main must be from staging, release/*, or hotfix/* (got {head_ref})"
                )
                return 1

    if base_ref == "staging":
        valid_prefixes = ("feature/", "hotfix/", "release/", "chore/", "docs/", "fix/")
        if not any(head_ref.startswith(p) for p in valid_prefixes):
            print(
                f"Error: PR to staging must be from feature/*, hotfix/*, release/* or other standard prefixes (got {head_ref})"
            )
            return 1

    print("Gitflow check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
