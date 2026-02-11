#!/bin/bash
# Clear the cache directory

CACHE_DIR="./cache"

if [ -d "$CACHE_DIR" ]; then
    echo "Clearing cache directory: $CACHE_DIR"
    rm -rf "$CACHE_DIR"/*
    echo "Cache cleared."
else
    echo "Cache directory not found: $CACHE_DIR"
fi
