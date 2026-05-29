#!/usr/bin/env python3
"""Fetch a file from OSS and write it to disk, with private-key-safe permissions."""
import argparse
import os
import sys

import oss2


def main():
    p = argparse.ArgumentParser(description="Fetch a file from OSS")
    p.add_argument("--ak", required=True, help="AccessKeyId")
    p.add_argument("--sk", required=True, help="AccessKeySecret")
    p.add_argument("--endpoint", required=True, help="OSS endpoint")
    p.add_argument("--bucket", required=True, help="Bucket name")
    p.add_argument("--key", required=True, help="Object key, e.g. ci/private-key.pem")
    p.add_argument("--output", required=True, help="Output file path")
    p.add_argument("--chmod", default="600", help="Permissions for output file (default: 600)")
    args = p.parse_args()

    auth = oss2.Auth(args.ak, args.sk)
    bucket = oss2.Bucket(auth, args.endpoint, args.bucket)
    result = bucket.get_object(args.key)
    data = result.read()
    if isinstance(data, bytes):
        data = data.decode("utf-8")

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w") as f:
        f.write(data)

    os.chmod(args.output, int(args.chmod, 8))
    print(f"Wrote {len(data)} bytes to {args.output}")


if __name__ == "__main__":
    main()
