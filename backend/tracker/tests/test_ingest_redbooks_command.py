import os

import django
import pytest
from django.core.management.base import CommandError

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from tracker.management.commands.ingest_redbooks_multi_agent import Command


def test_legacy_command_raises_retired_message():
    command = Command()
    with pytest.raises(CommandError) as excinfo:
        command.handle(
            sources_root="../sources",
            max_workers=10,
            page_chunk_size=120,
            max_page_workers_per_file=5,
            dry_run=False,
            force_reingest=False,
            show_plan=False,
            source_file=None,
            spawn_terminals=True,
            legacy_mode=False,
        )

    message = str(excinfo.value)
    assert "retired" in message.lower()
    assert "ingestion_submit" in message
    assert "ingestion_run" in message
