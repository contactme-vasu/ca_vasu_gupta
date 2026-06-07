# Publishing Options

To refresh NSE data and rebuild the static website, run:

```powershell
python main.py
```

This updates the static browser page in:

```text
site/index/
```

## Option 1: Manual Git Push

Use this when the GitHub Pages website repository is the same folder.

```powershell
git add site/index
git add cache/site_data.json
git commit -m "Update index analysis website"
git push
```

## Option 2: One Command Push

Use this only when `cache/site_data.json` already exists and you want to recopy the static templates without refreshing NSE data.

```powershell
python publish_site.py --push
```

Use this when the website repository is a different local folder:

```powershell
python publish_site.py --output-dir "D:\path\to\caabcd-site\index" --push
```

## Option 3: GitHub Actions

The workflow template is in:

```text
.github/workflows/publish-index-site.yml
```

It can run manually or on April 5 and October 5. As written, it refreshes NSE data, computes the analysis JSON, rebuilds the website, and commits `cache/site_data.json` plus `site/index/`.

`main.py` is non-interactive and always refreshes TRI data from NSE.

The intended unattended workflow is:

```text
run main.py -> commit cache/site_data.json and site/index/
```

## RBI T-Bill Data

`Auctions of 364-Day Government of India Treasury Bills.xlsx` is still required for Sharpe Ratio and Sortino Ratio. For GitHub Actions, keep this workbook in the repository unless/until the project adds an automated RBI download step. It is backend calculation data and is not copied into `site/index/`.

## Domain Path

For GitHub Pages, commit the generated files so this path exists in the website repository:

```text
index/index.html
```

Then the public URL will be:

```text
https://www.caabcd.com/index/
```
