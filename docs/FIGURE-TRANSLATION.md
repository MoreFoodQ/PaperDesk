# Optional figure text translation

In Settings → Models, **Translate text inside figures** is enabled by default.
Older configuration files and previously queued jobs retain the enabled behavior.

| Content | Enabled | Disabled |
|---|---|---|
| Body, headings and tables | Translated | Translated |
| Figure captions | Translated | Translated |
| Readable labels, axes and legends inside figures | Translated | Original text retained |
| Source images | Retained | Retained |
| Existing figure translations | Retained | Retained |

This controls the structured figure-label text displayed below the original image.
It does not edit pixels or replace text inside the original image. Page images may
still be sent to the model for body text, formulas, tables and layout. This option
does not prevent image transmission or guarantee a particular token reduction.

## Tasks and later translation

- A new task saves the option when it is queued. Changing settings affects later
  tasks; confirmation, failed-page retries and service restarts retain that task's option.
- Skipped labels do not count as failed body translation. The page may finish normally.
- Re-enable the setting for future tasks. Continuing translation also picks up
  deliberately skipped labels on otherwise completed pages, without replacing their blocks.
- The reader offers **Translate skipped figure text** when eligible labels remain.
  This explicit action translates only those labels even if the global option is off;
  it does not change the global setting and consumes model quota. Page limits still apply.
- Failed image-only fills retain their pending labels and can be retried. Cancelled
  fills keep completed writes and notes; the reader action can start a new fill.
- The option applies to automatic page translation and original-to-translation fills
  for PDF and supported EPUB. Explicit passage retranslation and GPT questions remain
  user-directed operations and are not disabled by this setting.
- Existing documents without an application-owned skip marker are not automatically
  scheduled for extra model calls. Unreadable or absent labels cannot be filled reliably.

## Data compatibility

Figure blocks can contain the additive boolean field `image_translation_skipped`.
The application creates it only for readable original labels deliberately skipped by
this feature and clears it after a successful fill. No library migration is required.
The model cannot set this marker. Notes and highlights remain in reader.json, and
image-only fills retain block IDs, captions, body text, original files and review entries.

The setting does not delete existing translations. Explicit full-page retranslation
still uses the existing block-replacement behavior; matching existing figure IDs/pages
retain their previous label translations when the option is off. Image-only fill is
the operation intended to preserve all existing blocks.

## Verification (2026-10-19)

| Problem | Change | Result |
|---|---|---|
| Model may still return labels when disabled | Filter output before validation, repair and merge | Disabled labels ignored; captions/body/tables retained |
| Missing optional labels could cause retries | Exclude image keys from original-mode fill work | No false missing-translation errors or image-only model calls while disabled |
| Completed pages could prevent later image translation | Track deliberate skips and fill only image keys | Existing body blocks, IDs, notes and review entries preserved |
| Configuration could change during queued work | Persist option in job.json | Queue, confirmation, failure retry, restart and legacy-job behavior verified |
| PDF and EPUB share reader behavior | Exercise actual rendering, cropping, persistence and export | Source/image hashes and reader notes retained in synthetic integration checks |
| Setting could be lost or inaccessible | Native labeled checkbox with an associated explanation | Default-on rendering, boolean saves, browser reload and narrow reader layouts verified |

Final local regressions: **385 Python tests and 118 JavaScript tests passed**.
The source smoke/privacy gate and all nine existing drawer widths also passed.

Run the automated regressions with:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_figure_translation
node --test tests/test_figure_translation.cjs
```

The optional `node scripts/verify_figure_translation.cjs` browser check uses an
isolated temporary library, synthetic PDF/EPUB documents and an in-process model
substitute. Runtime overrides are documented in its header. It does not use account
credentials or make live model requests. Live model adherence and a newly rebuilt
Windows installer are outside this feature branch's validation evidence.

## Release handling

This is an additive feature suitable for the next minor release (proposed 0.3.0).
Validate the branch and review its diff, merge into main, verify remote CI, then
update the version consistently and build/test a new installer from that source.
Previously built 0.2.0 executables do not contain this feature and must not be relabeled.
Branch source can be tried before merging with an isolated library. Merging does not
update a running process or an installed executable; restart the source app or install
the new package. The separate daily-use checkout is not updated by this branch.
