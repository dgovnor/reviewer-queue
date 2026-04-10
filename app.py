from __future__ import annotations

import json
import threading
from pathlib import Path

from flask import Flask, abort, jsonify, request, send_from_directory

from service.queue import (
    VALID_ACTIONS,
    WorkflowError,
    active_queue,
    allowed_actions,
    apply_action,
)

BASE_DIR = Path(__file__).resolve().parent
SEED_PATH = BASE_DIR / "review_items.json"
STATIC_DIR = BASE_DIR / "static"

CURRENT_REVIEWER = "alex"


class ItemStore:

    def __init__(self, items: list[dict]) -> None:
        self._items: dict[str, dict] = {item["id"]: item for item in items}
        self._lock = threading.Lock()

    def all(self) -> list[dict]:
        with self._lock:
            return [dict(item) for item in self._items.values()]

    def get(self, item_id: str) -> dict | None:
        with self._lock:
            item = self._items.get(item_id)
            return dict(item) if item else None

    def replace(self, item: dict) -> None:
        with self._lock:
            self._items[item["id"]] = item


def _load_seed() -> list[dict]:
    with SEED_PATH.open() as fh:
        return json.load(fh)


def create_app() -> Flask:
    app = Flask(__name__, static_folder=None)
    store = ItemStore(_load_seed())

    def _decorate(item: dict) -> dict:
        """Attach computed fields the UI needs."""
        return {**item, "allowed_actions": allowed_actions(item)}

    @app.get("/")
    def index():
        return send_from_directory(STATIC_DIR, "index.html")

    @app.get("/static/<path:filename>")
    def static_files(filename: str):
        return send_from_directory(STATIC_DIR, filename)

    @app.get("/api/reviewer")
    def current_reviewer():
        return jsonify({"reviewer": CURRENT_REVIEWER})

    @app.get("/api/items")
    def list_items():
        queue = active_queue(store.all())
        return jsonify([_decorate(item) for item in queue])

    @app.get("/api/items/<item_id>")
    def get_item(item_id: str):
        item = store.get(item_id)
        if item is None:
            abort(404, description=f"Item '{item_id}' not found.")
        return jsonify(_decorate(item))

    @app.post("/api/items/<item_id>/<action>")
    def perform_action(item_id: str, action: str):
        if action not in VALID_ACTIONS:
            return jsonify({"error": f"Unknown action '{action}'."}), 400

        item = store.get(item_id)
        if item is None:
            return jsonify({"error": f"Item '{item_id}' not found."}), 404

        try:
            updated = apply_action(item, action, reviewer=CURRENT_REVIEWER)
        except WorkflowError as exc:
            return jsonify({"error": str(exc)}), 409

        store.replace(updated)
        return jsonify(_decorate(updated))

    @app.errorhandler(404)
    def _not_found(err):
        return jsonify({"error": getattr(err, "description", "Not found.")}), 404

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5004, debug=False)
