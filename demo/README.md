# Demo inputs

## Self-contained demo (recommended)

`scripts/demo_seed.py` generates all documents in memory and exercises the
full 10-stage pipeline. No external PDF files needed:

```bash
uvicorn app.main:app                # in one terminal

python scripts/demo_seed.py         # in another terminal
```

It creates a syllabus, past paper, and mark scheme as minimal PDFs,
then runs upload → extract → embed → parse questions → map → corrections →
mastery → emphasis → teaching units → calendar → plan → disrupt → replan →
generation. Every step prints what actually landed.

## Manual demo with your own papers

`scripts/demo_pipeline.py` uses your own past papers. Point it at the
syllabus and one or more papers:

```bash
uvicorn app.main:app

python scripts/demo_pipeline.py \
  --syllabus demo/CS201_DSA_Syllabus.pdf \
  --paper "2024:final:/path/to/final-2024.pdf" \
  --paper "2022:mid1:/path/to/mid1-2022.pdf"
```

## Sample files

- `CS201_DSA_Syllabus.pdf` — a sample Data Structures & Algorithms course
  syllabus, written for this demo so the repo has a working syllabus input
  without redistributing a real institution's material. It is **sample data,
  not a real course document.** `make_syllabus.py` regenerates it
  (`pip install fpdf2` first); fpdf2 is not an app dependency.
