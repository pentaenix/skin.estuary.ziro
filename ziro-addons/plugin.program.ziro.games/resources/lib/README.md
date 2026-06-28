# plugin.program.ziro.games library modules

This folder contains the production game-library logic.

Expected module ownership:

```text
db.py
  SQLite schema, migrations, database access, upserts, query helpers.

scanner.py
  Dynamic source scanning. Should not hardcode consoles. Reads sources from DB/settings.

routes.py
  Kodi plugin route rendering and ListItem creation. Routes should remain stable for the skin.

paths.py
  Userdata/profile paths, artwork/cache/db paths. Keep cross-platform where possible.

mock.py
  Temporary/demo data only. Do not rely on mock data for production behavior.
```

If you add metadata providers, prefer a new package:

```text
metadata/
  base.py
  local.py
  screenscraper.py
  igdb.py
  steamgriddb.py
```

If you add artwork handling, prefer:

```text
artwork.py
```

If you add source/platform forms, keep UI entry points in `routes.py` but business logic in dedicated modules.
