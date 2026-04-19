# Papers Workspace Layout

Folder ini menampung semua artefak paper agar root project tetap bersih.

## Struktur

- `drafts/`
  - File sumber paper (`.tex`) yang siap diedit.
- `outputs/`
  - Hasil generate (`.docx`) dari draft.
- `references/`
  - Template, file bimbingan, dan referensi eksternal (DOCX/PDF).
- `guides/`
  - Panduan proses penulisan/konversi.

## Workflow singkat

1. Edit draft pada `drafts/`.
2. Jalankan converter:
   - `venv/Scripts/python.exe scripts/tex_to_docx_with_template.py`
3. Ambil hasil terbaru di `outputs/`.
