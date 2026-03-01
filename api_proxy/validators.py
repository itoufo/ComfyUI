import json
import re
from typing import Any

from fastapi import HTTPException, status

from .config import settings

# Nodes that should never be exposed to external users
BLOCKED_NODES: set[str] = {
    "LoadImage",         # filesystem access
    "LoadImageMask",     # filesystem access
    "UploadImage",       # filesystem write
    "LoadImageFromUrl",  # SSRF risk
    "PythonModule",      # arbitrary code
    "ExecuteScript",     # arbitrary code
    "RunCommand",        # arbitrary code
    "Shell",             # arbitrary code
}

# Allowed characters in filenames
_SAFE_FILENAME = re.compile(r"^[a-zA-Z0-9_\-][a-zA-Z0-9_\-. ]{0,254}$")


def validate_workflow(workflow: dict[str, Any]) -> None:
    """Validate a ComfyUI workflow dict."""
    raw = json.dumps(workflow)

    # Size check
    if len(raw.encode("utf-8")) > settings.MAX_WORKFLOW_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Workflow exceeds {settings.MAX_WORKFLOW_SIZE // 1024}KB limit",
        )

    # Node count
    if len(workflow) > settings.MAX_NODE_COUNT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Workflow exceeds {settings.MAX_NODE_COUNT} node limit",
        )

    # Check each node
    for node_id, node in workflow.items():
        if not isinstance(node, dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid node format at '{node_id}'",
            )

        class_type = node.get("class_type", "")

        # Block dangerous nodes
        if class_type in BLOCKED_NODES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Node type '{class_type}' is not allowed",
            )

        # Check for path traversal in string inputs
        inputs = node.get("inputs", {})
        for key, value in inputs.items():
            if isinstance(value, str) and (".." in value or "/" in value or "\\" in value):
                # Allow node references like ["3", 0] (they're lists, not strings)
                # Block strings that look like path traversal
                if ".." in value:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Path traversal detected in node '{node_id}' input '{key}'",
                    )


def validate_filename(filename: str) -> None:
    """Ensure filename is safe (no path traversal)."""
    if not _SAFE_FILENAME.match(filename):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename",
        )
    if ".." in filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Path traversal not allowed",
        )
