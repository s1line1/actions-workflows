#!/usr/bin/env python3
"""Fetch secrets JSON from OSS, output as KEY=VALUE for GitHub Actions env."""
import argparse
import json
import sys

import oss2


def flatten(data, prefix=""):
    """Recursively flatten nested dict to KEY=VALUE lines."""
    for k, v in data.items():
        key = f"{prefix}{k}".upper()
        if isinstance(v, dict):
            yield from flatten(v, f"{key}_")
        else:
            yield f"{key}={v}"


def main():
    p = argparse.ArgumentParser(description="Fetch secrets JSON from OSS")
    p.add_argument("--ak", required=True, help="AccessKeyId")
    p.add_argument("--sk", required=True, help="AccessKeySecret")
    p.add_argument("--endpoint", required=True, help="OSS endpoint")
    p.add_argument("--bucket", required=True, help="Bucket name")
    p.add_argument("--key", required=True, help="Object key, e.g. ci/secrets.json")
    args = p.parse_args()

    auth = oss2.Auth(args.ak, args.sk)
    bucket = oss2.Bucket(auth, args.endpoint, args.bucket)
    result = bucket.get_object(args.key)
    data = json.loads(result.read())

    for line in flatten(data):
        print(f"{line}")


if __name__ == "__main__":
    main()
