name: Build USGS station index

on:
  workflow_dispatch:      # manual “Run workflow” button
  schedule:
    - cron: "0 6 * * 1"   # optional: Mondays 06:00 UTC (change or remove if you want)

permissions:
  contents: write         # allow the workflow to commit the JSON

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Build stations.json
        run: |
          python build_usgs_station_index.py
          mkdir -p data
          mv stations.json stations.min.json data/

      - name: Commit updated JSON
        uses: stefanzweifel/git-auto-commit-action@v5
        with:
          commit_message: "Update stations index"
          file_pattern: data/*.json
