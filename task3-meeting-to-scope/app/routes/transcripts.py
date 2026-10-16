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


def get_user_transcripts_dir() -> Path:
    return Path(__file__).parent.parent.parent / "transcripts_user"


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
                    "is_user_transcript": False,
                })
            except Exception:
                pass

    udir = get_user_transcripts_dir()
    if udir.exists():
        from agents.transcript_analyst import parse_transcript_text
        for f in sorted(udir.glob("*.txt")):
            try:
                content = f.read_text(encoding="utf-8")
                dialogue = parse_transcript_text(content)
                clean_name = f.stem.replace("_", " ").title()
                results.append({
                    "id": f.stem,
                    "project_id": f"proj_{f.stem}",
                    "project_name": clean_name,
                    "label": f"User: {clean_name}",
                    "meeting_date": "2026-10-16",
                    "is_follow_up": False,
                    "client_name": "User Upload",
                    "turns_count": len(dialogue),
                    "is_user_transcript": True,
                })
            except Exception:
                pass

    return sorted(results, key=lambda x: str(x.get("label", "")))


@router.get("/{transcript_id}")
async def get_transcript(transcript_id: str) -> dict:
    tdir = get_transcripts_dir()
    fpath = tdir / f"{transcript_id}.json"
    if fpath.exists():
        return json.loads(fpath.read_text(encoding="utf-8"))

    udir = get_user_transcripts_dir()
    ufpath = udir / f"{transcript_id}.txt"
    if ufpath.exists():
        from agents.transcript_analyst import parse_transcript_text
        dialogue = parse_transcript_text(ufpath.read_text(encoding="utf-8"))
        clean_name = transcript_id.replace("_", " ").title()
        return {
            "id": transcript_id,
            "project_id": f"proj_{transcript_id}",
            "project_name": clean_name,
            "label": f"User: {clean_name}",
            "meeting_date": "2026-10-16",
            "is_follow_up": False,
            "client_name": "User Upload",
            "dialogue": dialogue,
        }

    raise HTTPException(status_code=404, detail="Transcript not found")
