"""
Dataset Collection Blueprint

Provides the public-facing page for keystroke dynamics dataset collection.
No login required — designed for research respondents.

Routes:
    GET /dataset          → dataset collection UI
"""

from flask import Blueprint, render_template

from app.models.dataset import DATASET_TOTAL_SAMPLES

dataset_bp = Blueprint("dataset", __name__)


@dataset_bp.route("/dataset")
def collection_page():
    """Public dataset collection page."""
    return render_template(
        "dataset_collection.html",
        total_samples=DATASET_TOTAL_SAMPLES,
    )
