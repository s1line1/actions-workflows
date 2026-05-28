#!/usr/bin/env python3
"""
Store / retrieve sensitive config (Docker creds, registry info, etc.) on Alibaba Cloud OSS.
AK/SK always passed via CLI (from GitHub Actions secrets).
"""
import argparse
import json
import sys

import oss2


def make_bucket(args):
    auth = oss2.Auth(args.access_key_id, args.access_key_secret)
    return oss2.Bucket(auth, args.endpoint, args.bucket)


def cmd_upload(args):
    bucket = make_bucket(args)
    with open(args.file, "rb") as f:
        bucket.put_object(args.key, f)
    print(f"Uploaded {args.file} -> oss://{args.bucket}/{args.key}")


def cmd_get(args):
    bucket = make_bucket(args)
    try:
        result = bucket.get_object(args.key)
        content = result.read()
        if args.out == "-":
            sys.stdout.buffer.write(content)
        else:
            with open(args.out, "wb") as f:
                f.write(content)
            print(f"Downloaded to {args.out}")
    except oss2.exceptions.OssError as e:
        print(f"OSS error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_get_value(args):
    bucket = make_bucket(args)
    try:
        result = bucket.get_object(args.key)
        data = json.loads(result.read())
    except oss2.exceptions.OssError as e:
        print(f"OSS error: {e}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}", file=sys.stderr)
        sys.exit(1)

    keys = args.json_key.split(".")
    for k in keys:
        if isinstance(data, dict) and k in data:
            data = data[k]
        else:
            print(f"Key '{args.json_key}' not found in OSS object", file=sys.stderr)
            sys.exit(1)
    print(data)


def main():
    parser = argparse.ArgumentParser(description="OSS secrets store")
    parser.add_argument("--access-key-id", required=True, help="AccessKeyId")
    parser.add_argument("--access-key-secret", required=True, help="AccessKeySecret")
    parser.add_argument("--endpoint", required=True, help="e.g. https://oss-cn-hangzhou.aliyuncs.com")
    parser.add_argument("--bucket", required=True, help="Bucket name")

    sub = parser.add_subparsers(dest="command", required=True)

    p_upload = sub.add_parser("upload")
    p_upload.add_argument("--file", required=True, help="Local file to upload")
    p_upload.add_argument("--key", required=True, help="OSS object key")

    p_get = sub.add_parser("get")
    p_get.add_argument("--key", required=True, help="OSS object key")
    p_get.add_argument("--out", default="-", help="Output file (default: stdout)")

    p_val = sub.add_parser("get-value")
    p_val.add_argument("--key", required=True, help="OSS object key")
    p_val.add_argument("--json-key", required=True, help="Dot-notation key, e.g. docker.password")

    args = parser.parse_args()
    {
        "upload": cmd_upload,
        "get": cmd_get,
        "get-value": cmd_get_value,
    }[args.command](args)


if __name__ == "__main__":
    main()
