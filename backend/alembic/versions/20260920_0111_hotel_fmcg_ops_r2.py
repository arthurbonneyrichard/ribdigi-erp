"""Hotel + FMCG ops R2 — folio, HK, maintenance, guest/room fields, scheme scope, delivery.

Revision ID: 20260920_0111
Revises: 20260920_0110
Create Date: 2026-09-20
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260920_0111"
down_revision = "20260920_0110"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Hotel room expansions ---
    op.add_column("hotel_rooms", sa.Column("bed_type", sa.String(length=40), nullable=True))
    op.add_column("hotel_rooms", sa.Column("weekend_rate", sa.Numeric(14, 2), nullable=True))
    op.add_column(
        "hotel_rooms",
        sa.Column("extra_person_charge", sa.Numeric(14, 2), nullable=False, server_default="0"),
    )
    op.add_column("hotel_rooms", sa.Column("amenities", sa.JSON(), nullable=True))
    op.add_column("hotel_rooms", sa.Column("description", sa.Text(), nullable=True))
    op.add_column(
        "hotel_rooms",
        sa.Column(
            "housekeeping_status",
            sa.String(length=20),
            nullable=False,
            server_default="clean",
        ),
    )
    op.create_index("ix_hotel_rooms_housekeeping_status", "hotel_rooms", ["housekeeping_status"])

    # --- Hotel guest expansions ---
    op.add_column("hotel_guests", sa.Column("address", sa.Text(), nullable=True))
    op.add_column("hotel_guests", sa.Column("nationality", sa.String(length=80), nullable=True))
    op.add_column("hotel_guests", sa.Column("id_type", sa.String(length=40), nullable=True))
    op.add_column("hotel_guests", sa.Column("emergency_contact", sa.String(length=200), nullable=True))
    op.add_column("hotel_guests", sa.Column("company_name", sa.String(length=150), nullable=True))
    op.add_column("hotel_guests", sa.Column("preferences", sa.Text(), nullable=True))

    # --- Hotel reservation expansions ---
    op.add_column(
        "hotel_reservations",
        sa.Column("booking_source", sa.String(length=40), nullable=False, server_default="direct"),
    )
    op.add_column("hotel_reservations", sa.Column("special_requests", sa.Text(), nullable=True))
    op.add_column(
        "hotel_reservations",
        sa.Column("deposit_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
    )
    op.add_column("hotel_reservations", sa.Column("deposit_method", sa.String(length=20), nullable=True))
    op.add_column("hotel_reservations", sa.Column("no_show_at", sa.DateTime(), nullable=True))

    # --- Folios ---
    op.create_table(
        "hotel_folios",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column(
            "reservation_id",
            sa.String(length=36),
            sa.ForeignKey("hotel_reservations.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "guest_id",
            sa.String(length=36),
            sa.ForeignKey("hotel_guests.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("folio_number", sa.String(length=40), nullable=False, index=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("opened_at", sa.DateTime(), nullable=False),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "folio_number", name="uq_hotel_folios_tenant_number"),
    )
    op.create_index("ix_hotel_folios_status", "hotel_folios", ["status"])

    op.create_table(
        "hotel_folio_charges",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column(
            "folio_id",
            sa.String(length=36),
            sa.ForeignKey("hotel_folios.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("charge_type", sa.String(length=40), nullable=False, server_default="room"),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 2), nullable=False, server_default="1"),
        sa.Column("unit_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("tax_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("discount_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("line_total", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("is_void", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("void_reason", sa.String(length=255), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_hotel_folio_charges_charge_type", "hotel_folio_charges", ["charge_type"])

    op.create_table(
        "hotel_folio_payments",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column(
            "folio_id",
            sa.String(length=36),
            sa.ForeignKey("hotel_folios.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("method", sa.String(length=20), nullable=False, server_default="cash"),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("reference", sa.String(length=120), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("recorded_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "hotel_housekeeping_tasks",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column(
            "room_id",
            sa.String(length=36),
            sa.ForeignKey("hotel_rooms.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("task_type", sa.String(length=40), nullable=False, server_default="cleaning"),
        sa.Column("priority", sa.String(length=20), nullable=False, server_default="normal"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("assigned_to", sa.String(length=150), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_hotel_housekeeping_tasks_status", "hotel_housekeeping_tasks", ["status"])

    op.create_table(
        "hotel_maintenance_tickets",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column(
            "room_id",
            sa.String(length=36),
            sa.ForeignKey("hotel_rooms.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("title", sa.String(length=150), nullable=False),
        sa.Column("priority", sa.String(length=20), nullable=False, server_default="normal"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
        sa.Column("block_room", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("assigned_to", sa.String(length=150), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_hotel_maintenance_tickets_status", "hotel_maintenance_tickets", ["status"])

    # --- FMCG expansions ---
    op.add_column(
        "fmcg_trade_schemes",
        sa.Column("product_id", sa.String(length=36), sa.ForeignKey("products.id"), nullable=True),
    )
    op.create_index("ix_fmcg_trade_schemes_product_id", "fmcg_trade_schemes", ["product_id"])
    op.add_column("fmcg_trade_schemes", sa.Column("category_id", sa.String(length=36), nullable=True))
    op.create_index("ix_fmcg_trade_schemes_category_id", "fmcg_trade_schemes", ["category_id"])

    op.add_column(
        "fmcg_route_stops",
        sa.Column("delivery_status", sa.String(length=20), nullable=False, server_default="pending"),
    )
    op.create_index("ix_fmcg_route_stops_delivery_status", "fmcg_route_stops", ["delivery_status"])
    op.add_column("fmcg_route_stops", sa.Column("delivered_at", sa.DateTime(), nullable=True))
    op.add_column("fmcg_route_stops", sa.Column("fail_reason", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("fmcg_route_stops", "fail_reason")
    op.drop_column("fmcg_route_stops", "delivered_at")
    op.drop_index("ix_fmcg_route_stops_delivery_status", table_name="fmcg_route_stops")
    op.drop_column("fmcg_route_stops", "delivery_status")

    op.drop_index("ix_fmcg_trade_schemes_category_id", table_name="fmcg_trade_schemes")
    op.drop_column("fmcg_trade_schemes", "category_id")
    op.drop_index("ix_fmcg_trade_schemes_product_id", table_name="fmcg_trade_schemes")
    op.drop_column("fmcg_trade_schemes", "product_id")

    op.drop_index("ix_hotel_maintenance_tickets_status", table_name="hotel_maintenance_tickets")
    op.drop_table("hotel_maintenance_tickets")
    op.drop_index("ix_hotel_housekeeping_tasks_status", table_name="hotel_housekeeping_tasks")
    op.drop_table("hotel_housekeeping_tasks")
    op.drop_table("hotel_folio_payments")
    op.drop_index("ix_hotel_folio_charges_charge_type", table_name="hotel_folio_charges")
    op.drop_table("hotel_folio_charges")
    op.drop_index("ix_hotel_folios_status", table_name="hotel_folios")
    op.drop_table("hotel_folios")

    op.drop_column("hotel_reservations", "no_show_at")
    op.drop_column("hotel_reservations", "deposit_method")
    op.drop_column("hotel_reservations", "deposit_amount")
    op.drop_column("hotel_reservations", "special_requests")
    op.drop_column("hotel_reservations", "booking_source")

    op.drop_column("hotel_guests", "preferences")
    op.drop_column("hotel_guests", "company_name")
    op.drop_column("hotel_guests", "emergency_contact")
    op.drop_column("hotel_guests", "id_type")
    op.drop_column("hotel_guests", "nationality")
    op.drop_column("hotel_guests", "address")

    op.drop_index("ix_hotel_rooms_housekeeping_status", table_name="hotel_rooms")
    op.drop_column("hotel_rooms", "housekeeping_status")
    op.drop_column("hotel_rooms", "description")
    op.drop_column("hotel_rooms", "amenities")
    op.drop_column("hotel_rooms", "extra_person_charge")
    op.drop_column("hotel_rooms", "weekend_rate")
    op.drop_column("hotel_rooms", "bed_type")
