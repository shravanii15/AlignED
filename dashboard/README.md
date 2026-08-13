# AlignED Dashboard

The browsable front-end for the AlignED project: compares real graduate
program curricula against real job-market demand and shows statistically
significant skill gaps, demand trends, and ranked recommendations per
program.

## Run it locally

```
cd dashboard
pip install -r requirements.txt
streamlit run app.py
```

Then open the local URL it prints (usually http://localhost:8501).

It reads directly from `../database/aligned.db`, so make sure the
scripts in `scripts/` (scraping, extraction, gap scoring, trends,
recommendations) have been run first to populate that database.

## Publish it for free (optional)

1. Push this repo to GitHub (already done).
2. Go to [share.streamlit.io](https://share.streamlit.io), sign in with
   GitHub, and point it at this repo with `dashboard/app.py` as the main
   file.
3. You'll get a public URL you can link directly from a resume or
   LinkedIn -- no server to manage or pay for.
