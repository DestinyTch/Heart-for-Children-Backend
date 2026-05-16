"""
routes/stats.py
================
GET /api/stats — returns total verified amount and donor count for the
                 live counter displayed on the frontend.
"""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify
from pymongo.errors import PyMongoError

from app import mongo

logger = logging.getLogger(__name__)
stats_bp = Blueprint("stats", __name__)


@stats_bp.get("/stats")
def get_stats():
    """
    Calculate and return live fundraising statistics.

    Only counts donations with status == 'verified' to prevent pending /
    unconfirmed gift cards from inflating the public counter.

    Returns:
        200  { "total_raised": float, "donor_count": int }
        500  { "error": "Could not retrieve stats." }
    """
    logger.info("📊 Stats request received")

    try:
        pipeline = [
            {"$match": {"status": "verified"}},
            {
                "$group": {
                    "_id": None,
                    "total_raised": {
                        # amount is stored as a string (from form input); cast to double safely.
                        "$sum": {
                            "$convert": {
                                "input":   "$amount",
                                "to":      "double",
                                "onError": 0,
                                "onNull":  0,
                            }
                        }
                    },
                    "donor_count": {"$sum": 1},
                }
            },
        ]

        results = list(mongo.db.donations.aggregate(pipeline))

        if results:
            total_raised = round(results[0]["total_raised"], 2)
            donor_count  = results[0]["donor_count"]
            logger.info(f"✅ Stats: ${total_raised} from {donor_count} donors")
        else:
            # No verified donations yet — return zeros so the frontend animates from 0.
            total_raised = 0.0
            donor_count  = 0
            logger.info("ℹ️  No verified donations yet")

        return jsonify({
            "total_raised": total_raised,
            "donor_count":  donor_count,
        }), 200

    except PyMongoError as exc:
        logger.exception(f"❌ Stats aggregation failed: {exc}")
        return jsonify({"error": "Could not retrieve stats."}), 500
