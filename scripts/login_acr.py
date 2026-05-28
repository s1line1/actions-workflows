#!/usr/bin/env python3
"""
Log in to Alibaba Cloud Container Registry (ACR).

Modes:
  1. Fixed password (personal edition):   username + password   [default]
  2. AK/SK temporary token (enterprise):  access_key_id + access_key_secret + instance_id

Priority: config file > env vars > CLI args

Config: .acr_config.json (same dir as this script)
{
  "registry":     "crpi-xxx.cn-shanghai.personal.cr.aliyuncs.com",
  "username":     "cicd@1199373001503098",
  "password":     "your-fixed-password",
  "instance_id":  "crpi-xxx"          (optional, for --reset-password)
}
"""

import argparse
import json
import os
import subprocess
import sys

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".acr_config.json")


def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return {}


def save_config(cfg):
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
        f.write("\n")


def login_with_password(registry, username, password):
    cmd = [
        "docker", "login",
        "--username", username,
        "--password-stdin",
        registry,
    ]
    proc = subprocess.run(cmd, input=password, text=True, capture_output=True)
    if proc.returncode != 0:
        print(f"docker login failed:\n{proc.stderr}", file=sys.stderr)
        sys.exit(1)
    print(proc.stdout.strip())


def login_via_ak(access_key_id, access_key_secret, region, registry, instance_id):
    from alibabacloud_cr20181201.client import Client as CRClient
    from alibabacloud_tea_openapi.models import Config
    from alibabacloud_cr20181201.models import GetAuthorizationTokenRequest

    config = Config(
        access_key_id=access_key_id,
        access_key_secret=access_key_secret,
        endpoint=f"cr.{region}.aliyuncs.com",
    )
    client = CRClient(config)

    req = GetAuthorizationTokenRequest(instance_id=instance_id)
    resp = client.get_authorization_token(req)
    if resp.status_code != 200 or not resp.body.is_success:
        body = resp.body.to_map()
        print(f"GetAuthorizationToken failed: code={body.get('Code')}, message={body.get('Message')}", file=sys.stderr)
        sys.exit(1)

    token = resp.body.authorization_token
    temp_username = resp.body.temp_username
    login_with_password(registry, temp_username, token)
    print(f"Token expires at: {resp.body.expire_time}")


def reset_password(instance_id, new_password, region, access_key_id, access_key_secret):
    """Call ResetLoginPassword API (cr 2016-06-07) via aliyun CLI."""
    cmd = [
        "aliyun", "cr", "--version", "2016-06-07", "ResetLoginPassword",
        "--InstanceId", instance_id,
        "--Password", new_password,
        "--access-key-id", access_key_id,
        "--access-key-secret", access_key_secret,
        "--region", region,
    ]
    proc = subprocess.run(cmd, text=True, capture_output=True)
    if proc.returncode != 0:
        print(f"ResetLoginPassword failed:\n{proc.stderr}", file=sys.stderr)
        sys.exit(1)
    print(proc.stdout.strip())


def main():
    cfg = load_config()

    parser = argparse.ArgumentParser(description="Log in to Alibaba Cloud Container Registry")
    parser.add_argument("--registry", help="Registry domain")
    parser.add_argument("--username", help="ACR username")
    parser.add_argument("--password", help="ACR password")
    parser.add_argument("--ak", action="store_true", help="Force AK/SK temporary token mode")
    parser.add_argument("--config", help="Path to config JSON")
    parser.add_argument("--reset-password", metavar="NEWPWD",
                        help="Reset fixed password via OpenAPI and update config")
    args = parser.parse_args()

    if args.config:
        with open(os.path.expanduser(args.config)) as f:
            cfg = json.load(f)

    registry = args.registry or cfg.get("registry") or os.environ.get("ACR_REGISTRY")
    username = args.username or cfg.get("username") or os.environ.get("ACR_USERNAME")
    password = args.password or cfg.get("password") or os.environ.get("ACR_PASSWORD")

    if args.reset_password:
        instance_id = cfg.get("instance_id")
        region = cfg.get("region") or os.environ.get("ACR_REGION", "cn-shanghai")
        access_key_id = cfg.get("access_key_id") or os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_ID")
        access_key_secret = cfg.get("access_key_secret") or os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_SECRET")

        if not instance_id:
            print("instance_id is required in config for --reset-password", file=sys.stderr)
            sys.exit(1)
        if not access_key_id or not access_key_secret:
            print("access_key_id and access_key_secret required in config for --reset-password", file=sys.stderr)
            sys.exit(1)

        reset_password(instance_id, args.reset_password, region, access_key_id, access_key_secret)

        cfg["password"] = args.reset_password
        save_config(cfg)
        print(f"Password updated in {CONFIG_PATH}")
        return

    if args.ak or (cfg.get("access_key_id") and not username):
        region = cfg.get("region") or os.environ.get("ACR_REGION")
        access_key_id = cfg.get("access_key_id") or os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_ID")
        access_key_secret = cfg.get("access_key_secret") or os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_SECRET")
        instance_id = cfg.get("instance_id")
        if not access_key_id or not access_key_secret or not region or not registry:
            print("AK mode requires access_key_id, access_key_secret, region, and registry in config", file=sys.stderr)
            sys.exit(1)
        login_via_ak(access_key_id, access_key_secret, region, registry, instance_id)
    elif username and password and registry:
        login_with_password(registry, username, password)
    else:
        print(f"Missing credentials. Edit {CONFIG_PATH} or pass --registry/--username/--password.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
