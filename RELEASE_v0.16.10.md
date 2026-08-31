# v0.16.10 — Mobile Blog API Route Fix

Root cause: mobile Blog called `/api/content/article-from-source`, but the router is mounted at `/api/control/content`, making the live endpoint `/api/control/content/article-from-source`.

Fix: correct the mobile Blog endpoint only. No source-reader, Shield, desktop, Shopify, mail, or other mobile behavior changed.
