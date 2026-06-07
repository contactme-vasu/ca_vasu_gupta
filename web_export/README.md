# Website Export

This folder contains the code and static templates used by `main.py` and `publish_site.py`.

The files generated for the public website are written to:

```text
site/index/
```

That folder can be copied or committed into the GitHub Pages repository so the page is available at:

```text
/index/
```

`main.py` computes the public analysis data directly from the downloaded TRI cache and writes:

```text
cache/site_data.json
site/index/data.json
```

The public JSON contains only the analysis-table fields shown on the website, not raw TRI values or per-window rolling-return arrays.
