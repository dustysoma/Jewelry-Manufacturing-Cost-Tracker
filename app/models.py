from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field


class Order(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    client_name: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = "intake"


class Piece(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    order_id: int = Field(foreign_key="order.id")

    name: str = "Piece"

    # Metal
    metal: Optional[str] = None          # GOLD / SILVER / PLATINUM
    alloy: Optional[str] = None          # 10K / 14K / 18K / 925 / PT950
    finished_weight_g: Optional[float] = None
    loss_pct: float = 0.0                # 0.07 = 7% loss/overpour

    # Image
    image_data: Optional[str] = None     # base64 encoded image

    # Printing SLA
    files_sent_at: Optional[datetime] = None
    expected_print_delivery_at: Optional[datetime] = None
    actual_print_delivery_at: Optional[datetime] = None


class RateCard(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    category: str                        # CAD, PRINT, STONE, SETTING, POLISH, PLATING, ENAMEL, ENGRAVING, INLAY, MISC
    name: str                            # "Prong setting 1.3mm", "Rhodium plating", "CAD New Ring Standard"
    unit_type: str                       # job, piece, stone, carat, gram, hour, character, color, section, etc.
    unit_cost: float
    active: bool = True


class LineItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    piece_id: int = Field(foreign_key="piece.id")

    category: str
    name: str
    unit_type: str
    qty: float = 1.0
    unit_cost: float = 0.0
    notes: Optional[str] = None

    # Optional: link back to a rate card template
    rate_card_id: Optional[int] = Field(default=None, foreign_key="ratecard.id")


class MetalPriceSnapshot(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    captured_at: datetime = Field(default_factory=datetime.utcnow)
    currency: str = "USD"

    # per gram
    gold_per_g: float
    silver_per_g: float
    platinum_per_g: float


class Job(SQLModel, table=True):
    """Saved job record for invoices/expense tracking"""
    id: Optional[int] = Field(default=None, primary_key=True)
    order_id: Optional[int] = Field(default=None, foreign_key="order.id")
    piece_id: Optional[int] = Field(default=None, foreign_key="piece.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    finalized_at: Optional[datetime] = None

    # totals captured at time of save
    line_items_total: float = 0.0
    metal_cost: float = 0.0
    total_cost: float = 0.0

    # optional notes or external invoice id
    notes: Optional[str] = None
    external_invoice_id: Optional[str] = None

    # snapshot of piece image at time of job save
    image_data: Optional[str] = None
