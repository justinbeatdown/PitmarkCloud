# Pitmark Clean Replacement Engineering Policy

This policy applies across Pitmark Cloud, Shield, PRT, Control Center, Discord automation, web systems, release tooling, and future Pitmark software.

## Core rule

**Replace, verify, remove.**

When a patch, redesign, migration, or new implementation supersedes existing behavior, the repository and live runtime should end with one current implementation of that behavior.

Git history is the rollback archive. Production source is not an archive.

## Required behavior

For every replacement or patch:

1. Identify the current authoritative implementation and every consumer.
2. Add or update regression coverage before changing behavior when practical.
3. Implement the replacement without creating a second permanent source of truth.
4. Verify the replacement on the exact commit intended for release.
5. Remove superseded runtime code, routes, assets, listeners, jobs, environment toggles, duplicate APIs, stale build artifacts, stale generated files, and obsolete in-product patch/release notes that are no longer part of the current product.
6. Search the repository for references to the removed implementation and resolve every live consumer.
7. Re-run compile/tests after deletion, not only before deletion.
8. Verify the production deployment is serving the intended current implementation.

## Do not do this

- Do not keep `v1`, `v2`, `v3`, `new`, `new2`, `final`, `legacy`, or dated copies wired into production after a replacement is accepted.
- Do not stack new CSS/JavaScript over old CSS/JavaScript to override behavior.
- Do not leave an old API route or worker live "just in case" when no supported consumer requires it.
- Do not keep competing schedulers, state stores, caches, event listeners, or background jobs for the same responsibility.
- Do not leave stale patch notes or old-build notices in the live product after they are superseded.
- Do not preserve obsolete code solely because deleting it feels risky. Verify dependencies, then remove it.

## Historical information

Historical implementation details belong in Git history, pull requests, release history, or an intentional archive that is not part of the live runtime. Historical records may be retained when they are genuinely user-facing history or legally/operationally required, but they must not masquerade as current product state or remain executable by accident.

## Exceptions

A temporary compatibility layer is allowed only when a known active consumer requires it. The same change must document:

- the consumer;
- why immediate removal is unsafe;
- the migration path;
- the deletion condition.

Compatibility code without a known consumer is obsolete code and should be removed.

## Definition of clean

A patch is not complete merely because the new path works. It is complete when the new path works, the old path is no longer live, stale artifacts are gone, tests cover the current behavior, and the repository is simpler than it was before the change whenever reasonably possible.
