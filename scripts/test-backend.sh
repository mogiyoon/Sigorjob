#!/bin/bash

set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

cd "$ROOT"
python3 -m unittest backend.tests.test_api
