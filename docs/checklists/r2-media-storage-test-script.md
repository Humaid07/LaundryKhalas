# R2 Media Storage — Test Script / Checklist

Manual + automated verification for the Cloudflare R2 media storage work.
See [[media-storage-r2]] for architecture.

## A. Security pre-flight (no secrets printed)

- [x] `apps/whatsapp-agent/.env` is **gitignored** and **not tracked**
      (`git check-ignore apps/whatsapp-agent/.env` → prints the path;
      `git ls-files …/.env` → empty).
- [x] `apps/whatsapp-agent/.env.example` contains the R2 vars as **empty
      placeholders** (credentials blank; `MEDIA_STORAGE_PROVIDER=local`).
- [x] No `CLOUDFLARE_R2_*` key in `apps/admin` or `apps/facility-dashboard`
      (only deploy-adapter comments + a "Cloudflare R2 — Standby" status card).
- [x] No `NEXT_PUBLIC_*` variable holds an R2/Cloudflare secret.

## B. Automated backend tests

```
cd apps/whatsapp-agent
./.venv/Scripts/python.exe -m pytest -q                       # full suite
./.venv/Scripts/python.exe -m pytest -q tests/test_facility_order_photos.py
```

Covers (all in `tests/test_facility_order_photos.py`):

- [x] R2 config loads (`test_r2_config_loads`).
- [x] Missing R2 config flagged (`test_missing_r2_config_flag_is_false`) and
      **fails safe** on upload with 503 (`test_missing_r2_config_fails_safe_on_upload`).
- [x] Valid image upload accepted (`test_validate_file_type_accepts_jpeg`,
      `test_upload_intake_creates_row_and_event`).
- [x] Invalid type rejected 415; **SVG rejected**; content-type spoof rejected
      (`test_validate_file_type_rejects_non_image_and_svg`,
      `test_invalid_file_type_rejected`, `test_svg_is_rejected`,
      `test_content_type_spoof_rejected`).
- [x] Oversized rejected 413 (`test_validate_file_size_rejects_oversized`,
      `test_oversized_file_rejected`).
- [x] R2 upload → read → signed URL round-trip via a mocked S3 client, **no
      network** (`test_r2_upload_read_and_sign`); local signed URL is null.
- [x] Facility can upload its **own** order media; **cannot** another facility's
      (404) (`test_cannot_upload_for_another_facility`, `test_list_is_scoped_to_caller_facility`).
- [x] Signed view URL returned **only after** the access check
      (`test_view_url_denied_for_other_facility`, `test_view_url_returns_signed_for_owner`,
      `test_signed_view_url_service_is_scoped`).
- [x] Metadata row created; **object key has no PII**; checksum stored
      (`test_upload_stores_pii_safe_key_and_checksum`, `test_object_key_is_pii_safe`,
      `test_checksum_is_sha256`).
- [x] Order event (audit) created on upload + delete (existing tests).

## C. Frontend gates

```
cd apps/facility-dashboard
npm run typecheck        # clean
npm run lint             # clean (one PRE-EXISTING unrelated warning in orders/page.tsx)
npm run build            # success
```

- [x] Facility order detail renders the **Order Photos** section (existing).
- [x] Intake + pre-dispatch upload buttons work (existing multipart flow).
- [x] Thumbnails render (Bearer content proxy — works for local and R2).
- [x] Error + empty states present; mobile layout does not overflow (2-col grid).
- [x] Order cards show intake/dispatch **photo indicators** (`OrderPhotoBadge`).

## D. Live R2 smoke test (only when enabling R2)

> Requires a real private R2 bucket + creds in the backend `.env` and
> `DATABASE_MODE=supabase`. Migration `000034` applied.

1. [ ] Set `MEDIA_STORAGE_PROVIDER=r2` + `CLOUDFLARE_R2_*`; restart backend.
2. [ ] Facility dashboard → an order → Order Photos → upload an intake JPG.
3. [ ] Row in `order_photos` has `storage_provider='r2'`, `bucket` set,
       `storage_key` = `orders/{market}/{ref}/intake/…`, `checksum_sha256` set.
4. [ ] Object exists in the R2 bucket at that key.
5. [ ] Thumbnail renders; `GET …/photos/{id}/view-url` returns a signed
       `https://…r2.cloudflarestorage.com/…?X-Amz-…` URL that loads the image.
6. [ ] Upload a PDF/SVG → rejected (415). Upload > `MEDIA_MAX_IMAGE_MB` → 413.
7. [ ] From facility A, request facility B's order media → 404.
8. [ ] Delete a photo → row soft-deleted (`deleted_at` set), bytes retained in R2,
       `order_photo_deleted` event written.

## E. Rollback

- Set `MEDIA_STORAGE_PROVIDER=local` to revert to disk storage (existing rows keyed
  `storage_provider` still resolve per-row).
- Migration `000034` rollback SQL is in the migration header (drops the added
  columns; revert the stage CHECK to the 000032 list).
