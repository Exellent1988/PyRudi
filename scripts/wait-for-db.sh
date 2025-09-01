#!/bin/bash
# Wait for database to be ready

set -e

host="$1"
port="$2"
shift 2
cmd="$@"

echo "⏳ Waiting for $host:$port..."

until nc -z "$host" "$port"; do
  echo "🔄 Database $host:$port is unavailable - sleeping"
  sleep 1
done

echo "✅ Database $host:$port is ready!"
exec $cmd

