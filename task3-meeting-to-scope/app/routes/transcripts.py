from __future__ import annotations

import json
from pathlib import Path
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/transcripts", tags=["transcripts"])


class TranscriptUpload(BaseModel):
    id: str
    project_id: str
    project_name: str
    label: str
    meeting_date: str
    is_follow_up: bool = False
    parent_transcript_id: str | None = None
    client_name: str
    dialogue: list[dict]


def get_transcripts_dir() -> Path:
    return Path(__file__).parent.parent.parent / "transcripts"


@router.get("")
async def list_transcripts() -> list[dict]:
    tdir = get_transcripts_dir()
    results = []
    if tdir.exists():
        for f in tdir.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                results.append({
                    "id": data.get("id", f.stem),
                    "project_id": data.get("project_id"),
                    "project_name": data.get("project_name"),
                    "label": data.get("label"),
                    "meeting_date": data.get("meeting_date"),
                    "is_follow_up": data.get("is_follow_up", False),
                    "client_name": data.get("client_name"),
                    "turns_count": len(data.get("dialogue", [])),
                })
            except Exception:
                pass
    return sorted(results, key=lambda x: x.get("label", ""))


@router.get("/{transcript_id}")
async def get_transcript(transcript_id: str) -> dict:
    tdir = get_transcripts_dir()
    fpath = tdir / f"{transcript_id}.json"
    if not fpath.exists():
        raise HTTPException(status_code=404, detail="Transcript not found")
    return json.loads(fpath.read_text(encoding="utf-8"))
