# Anime catalog

`anime.sqlite3` is the canonical catalog used by `build.py`. The old
`anime.json` file is retained only as the migration input for the original 100
fully curated records; it is no longer read by the site generator.

The database separates anime, genres, moods, characters, outbound links and
source records. Affiliate URLs are stored per anime and validated to contain
the Amazon tracking tag `sekailog-22`.

Useful commands:

```sh
python scripts/manage_anime.py validate
python scripts/manage_anime.py stats
python scripts/manage_anime.py export --output /tmp/anime-export.json
```

The original 100 records were selected editorially. Basic metadata and image
cross-references for expanded records come from manami-project's
`anime-offline-database` under ODbL 1.0 / DbCL 1.0. `curation_level` records
whether an entry has full editorial details or source-backed basic metadata.
