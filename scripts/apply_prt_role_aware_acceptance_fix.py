from pathlib import Path

path = Path("api/early_access_admin.py")
source = path.read_text(encoding="utf-8")

bad = '''becomes before public release.

"
            "Broadcast Studio is in development.'''
good = r'''becomes before public release.\n\n"
            "Broadcast Studio is in development.'''

if bad in source:
    source = source.replace(bad, good, 1)
elif good not in source:
    raise SystemExit("Expected broadcaster acceptance string not found")

path.write_text(source, encoding="utf-8")
print("Corrected broadcaster acceptance string escaping")
