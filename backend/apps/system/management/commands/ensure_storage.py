"""Prepares file storage at start-up (ADR-0009, PQR-012): creates the S3 bucket if missing.

``--probe`` also writes, reads back and deletes a small file (container smoke test).
"""

import uuid
from typing import Any

from django.core.files.base import ContentFile
from django.core.files.storage import storages
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Crée le bucket S3 s'il manque ; --probe vérifie une écriture puis une lecture."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--probe", action="store_true")

    def handle(self, *args: Any, **options: Any) -> None:
        storage: Any = storages["default"]  # the real backend, not the lazy default_storage
        backend = type(storage).__name__
        if backend == "S3Storage":
            self._ensure_bucket(storage)
        else:
            self.stdout.write(f"Stockage local ({backend}) : aucun bucket à créer.")
        if options["probe"]:
            self._probe(storage)

    def _ensure_bucket(self, storage: Any) -> None:
        from botocore.exceptions import ClientError

        client = storage.connection.meta.client
        bucket = storage.bucket_name
        try:
            client.head_bucket(Bucket=bucket)
            self.stdout.write(f"Bucket S3 « {bucket} » présent.")
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") not in {"404", "NoSuchBucket"}:
                raise CommandError(f"Stockage S3 injoignable : {exc}") from exc
            client.create_bucket(Bucket=bucket)
            self.stdout.write(self.style.SUCCESS(f"Bucket S3 « {bucket} » créé."))

    def _probe(self, storage: Any) -> None:
        name = f"probes/{uuid.uuid4().hex}.txt"
        payload = b"PointQR storage probe"
        saved = storage.save(name, ContentFile(payload))
        try:
            with storage.open(saved, "rb") as handle:
                if handle.read() != payload:
                    raise CommandError("Le fichier relu ne correspond pas au fichier écrit.")
        finally:
            storage.delete(saved)
        self.stdout.write(self.style.SUCCESS("Écriture, lecture et suppression : OK."))
