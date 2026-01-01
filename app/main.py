from datetime import datetime, time as dtime, timedelta
from fastapi import FastAPI, Depends, HTTPException
from sqlmodel import Session, select
import logging

from .db import init_db, get_session
from .models import Order, Piece, LineItem, MetalPriceSnapshot, RateCard, Job
from .settings import settings
from .metal_prices import get_metals_per_gram, alloy_factor

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = FastAPI(title="Jewelry Manufacturing Tracker")


@app.on_event("startup")
def _startup():
    try:
        logger.debug("Running init_db() on startup")
        init_db()
        logger.debug("Database initialized successfully")
    except Exception:
        logger.exception("Unhandled exception during startup init_db()")
        raise

@app.get("/")
def home():
    return {"status": "ok"}

@app.get("/api/health")
def health():
    return {"ok": True}

# ---------- Metals ----------
@app.get("/api/metals/live")
async def metals_live(currency: str | None = None):
    currency = currency or settings.BASE_CURRENCY
    try:
        data = await get_metals_per_gram(currency=currency)
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))
    m = data.get("metals", {})
    return {
        "currency": data.get("currency", currency),
        "unit": data.get("unit", "g"),
        "gold_per_g": float(m["gold"]),
        "silver_per_g": float(m["silver"]),
        "platinum_per_g": float(m["platinum"]),
    }

@app.post("/api/metals/snapshot")
async def metals_snapshot(session: Session = Depends(get_session), currency: str | None = None):
    currency = currency or settings.BASE_CURRENCY
    try:
        data = await get_metals_per_gram(currency=currency)
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))
    m = data.get("metals", {})
    snap = MetalPriceSnapshot(
        currency=data.get("currency", currency),
        gold_per_g=float(m["gold"]),
        silver_per_g=float(m["silver"]),
        platinum_per_g=float(m["platinum"]),
    )
    session.add(snap)
    session.commit()
    session.refresh(snap)
    # Force-refresh in-memory metals cache so subsequent GETs return fresh data
    try:
        await get_metals_per_gram(settings.BASE_CURRENCY, cache_seconds=0)
    except Exception:
        # don't fail the snapshot if cache refresh has an issue
        pass

    return snap

@app.get("/api/metals/snapshots")
def list_snapshots(session: Session = Depends(get_session)):
    return session.exec(select(MetalPriceSnapshot).order_by(MetalPriceSnapshot.id.desc())).all()

# ---------- Orders ----------
@app.post("/api/orders")
def create_order(client_name: str, session: Session = Depends(get_session)):
    o = Order(client_name=client_name)
    session.add(o)
    session.commit()
    session.refresh(o)
    return o

@app.get("/api/orders")
def list_orders(session: Session = Depends(get_session)):
    return session.exec(select(Order).order_by(Order.id.desc())).all()

@app.get("/api/orders/{order_id}/pieces")
def list_pieces_for_order(order_id: int, session: Session = Depends(get_session)):
    return session.exec(select(Piece).where(Piece.order_id == order_id).order_by(Piece.id.desc())).all()


# ---------- Pieces ----------
@app.post("/api/orders/{order_id}/pieces")
def create_piece(order_id: int, name: str = "Piece", session: Session = Depends(get_session)):
    p = Piece(order_id=order_id, name=name)
    session.add(p)
    session.commit()
    session.refresh(p)
    return p

@app.patch("/api/pieces/{piece_id}")
def update_piece(
    piece_id: int,
    metal: str | None = None,
    alloy: str | None = None,
    finished_weight_g: float | None = None,
    loss_pct: float | None = None,
    files_sent_at: datetime | None = None,
    session: Session = Depends(get_session),
):
    piece = session.get(Piece, piece_id)
    if not piece:
        return {"error": "piece not found"}

    if metal is not None: piece.metal = metal
    if alloy is not None: piece.alloy = alloy
    if finished_weight_g is not None: piece.finished_weight_g = finished_weight_g
    if loss_pct is not None: piece.loss_pct = loss_pct
    if files_sent_at is not None:
        piece.files_sent_at = files_sent_at

        # SLA rule: if sent by 11:00am → expected delivery 3:30pm same day
        sent_local = files_sent_at  # keep naive for now
        cutoff = datetime.combine(sent_local.date(), dtime(11, 0))
        deliver_same_day = datetime.combine(sent_local.date(), dtime(15, 30))
        if sent_local <= cutoff:
            piece.expected_print_delivery_at = deliver_same_day
        else:
            # simple fallback: next day 3:30pm
            piece.expected_print_delivery_at = deliver_same_day + timedelta(days=1)

    session.add(piece)
    session.commit()
    session.refresh(piece)
    return piece


@app.get("/api/pieces/{piece_id}")
def get_piece(piece_id: int, session: Session = Depends(get_session)):
    piece = session.get(Piece, piece_id)
    return piece or {"error": "piece not found"}


@app.post("/api/pieces/{piece_id}/image")
def upload_piece_image(piece_id: int, image_data: str, session: Session = Depends(get_session)):
    """Upload base64 image for a piece"""
    piece = session.get(Piece, piece_id)
    if not piece:
        raise HTTPException(status_code=404, detail="piece not found")
    
    piece.image_data = image_data
    session.add(piece)
    session.commit()
    session.refresh(piece)
    return piece



# ---------- Rate Cards ----------
@app.post("/api/rate-cards")
def create_rate_card(
    category: str,
    name: str,
    unit_type: str,
    unit_cost: float,
    active: bool = True,
    session: Session = Depends(get_session),
):
    rc = RateCard(category=category, name=name, unit_type=unit_type, unit_cost=unit_cost, active=active)
    session.add(rc)
    session.commit()
    session.refresh(rc)
    return rc

@app.get("/api/rate-cards")
def list_rate_cards(category: str | None = None, active: bool | None = True, session: Session = Depends(get_session)):
    q = select(RateCard)
    if category:
        q = q.where(RateCard.category == category)
    if active is not None:
        q = q.where(RateCard.active == active)
    return session.exec(q.order_by(RateCard.category, RateCard.name)).all()

# ---------- Line Items ----------
@app.post("/api/pieces/{piece_id}/line-items/from-rate-card")
def add_line_item_from_rate_card(
    piece_id: int,
    rate_card_id: int,
    qty: float = 1.0,
    unit_cost_override: float | None = None,
    notes: str | None = None,
    session: Session = Depends(get_session),
):
    rc = session.get(RateCard, rate_card_id)
    if not rc:
        return {"error": "rate card not found"}

    unit_cost = float(unit_cost_override) if unit_cost_override is not None else rc.unit_cost

    li = LineItem(
        piece_id=piece_id,
        category=rc.category,
        name=rc.name,
        unit_type=rc.unit_type,
        qty=qty,
        unit_cost=unit_cost,
        notes=notes,
        rate_card_id=rc.id,
    )
    session.add(li)
    session.commit()
    session.refresh(li)
    return li

@app.post("/api/pieces/{piece_id}/line-items")
def add_line_item_manual(
    piece_id: int,
    category: str,
    name: str,
    unit_type: str,
    qty: float = 1.0,
    unit_cost: float = 0.0,
    notes: str | None = None,
    session: Session = Depends(get_session),
):
    li = LineItem(piece_id=piece_id, category=category, name=name, unit_type=unit_type, qty=qty, unit_cost=unit_cost, notes=notes)
    session.add(li)
    session.commit()
    session.refresh(li)
    return li

@app.get("/api/pieces/{piece_id}/line-items")
def list_piece_line_items(piece_id: int, session: Session = Depends(get_session)):
    return session.exec(select(LineItem).where(LineItem.piece_id == piece_id)).all()

@app.delete("/api/line-items/{line_item_id}")
def delete_line_item(line_item_id: int, session: Session = Depends(get_session)):
    li = session.get(LineItem, line_item_id)
    if not li:
        raise HTTPException(status_code=404, detail="line item not found")
    session.delete(li)
    session.commit()
    return {"ok": True}

# ---------- Piece Summary / Totals ----------
@app.get("/api/pieces/{piece_id}/summary")
def piece_summary(
    piece_id: int,
    snapshot_id: int | None = None,
    premium_per_g: float = 0.0,
    session: Session = Depends(get_session),
):
    piece = session.get(Piece, piece_id)
    if not piece:
        return {"error": "piece not found"}

    items = session.exec(select(LineItem).where(LineItem.piece_id == piece_id)).all()
    items_total = sum(i.qty * i.unit_cost for i in items)

    metal_cost = 0.0
    metal_breakdown = None

    if snapshot_id and piece.metal and piece.alloy and piece.finished_weight_g:
        snap = session.get(MetalPriceSnapshot, snapshot_id)
        if snap:
            metal = piece.metal.upper()
            spot = snap.gold_per_g if metal == "GOLD" else snap.silver_per_g if metal == "SILVER" else snap.platinum_per_g
            factor = alloy_factor(metal, piece.alloy)
            shop_cost_per_g = (spot * factor) + premium_per_g
            adjusted_weight = piece.finished_weight_g * (1.0 + piece.loss_pct)
            metal_cost = adjusted_weight * shop_cost_per_g

            metal_breakdown = {
                "metal": metal,
                "alloy": piece.alloy,
                "spot_per_g": spot,
                "alloy_factor": factor,
                "premium_per_g": premium_per_g,
                "shop_cost_per_g": shop_cost_per_g,
                "finished_weight_g": piece.finished_weight_g,
                "loss_pct": piece.loss_pct,
                "adjusted_weight_g": adjusted_weight,
                "metal_cost": metal_cost,
                "currency": snap.currency,
            }

    return {
        "piece": piece,
        "line_items_total": items_total,
        "metal_cost": metal_cost,
        "total_cost": items_total + metal_cost,
        "metal_breakdown": metal_breakdown,
        "line_items": items,
    }


# ---------- Jobs (persisted) ----------
@app.post("/api/jobs")
def create_job(piece_id: int, snapshot_id: int | None = None, notes: str | None = None, external_invoice_id: str | None = None, session: Session = Depends(get_session)):
    piece = session.get(Piece, piece_id)
    if not piece:
        raise HTTPException(status_code=404, detail="piece not found")

    # compute summary using current DB values
    items = session.exec(select(LineItem).where(LineItem.piece_id == piece_id)).all()
    items_total = sum(i.qty * i.unit_cost for i in items)

    metal_cost = 0.0
    if snapshot_id and piece.metal and piece.alloy and piece.finished_weight_g:
        snap = session.get(MetalPriceSnapshot, snapshot_id)
        if snap:
            metal = piece.metal.upper()
            spot = snap.gold_per_g if metal == "GOLD" else snap.silver_per_g if metal == "SILVER" else snap.platinum_per_g
            factor = alloy_factor(metal, piece.alloy)
            shop_cost_per_g = (spot * factor)
            adjusted_weight = piece.finished_weight_g * (1.0 + piece.loss_pct)
            metal_cost = adjusted_weight * shop_cost_per_g

    total_cost = items_total + metal_cost

    from .models import Job
    job = Job(order_id=piece.order_id, piece_id=piece.id, line_items_total=items_total, metal_cost=metal_cost, total_cost=total_cost, notes=notes, external_invoice_id=external_invoice_id)
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


@app.get("/api/jobs")
def list_jobs(session: Session = Depends(get_session)):
    return session.exec(select(Job).order_by(Job.id.desc())).all()


@app.get("/api/jobs/{job_id}")
def get_job(job_id: int, session: Session = Depends(get_session)):
    j = session.get(Job, job_id)
    if not j:
        raise HTTPException(status_code=404, detail="job not found")
    return j


@app.get("/api/jobs-with-orders")
def jobs_with_orders(session: Session = Depends(get_session)):
    """Returns jobs with client_name and piece info for UI display"""
    jobs = session.exec(select(Job).order_by(Job.created_at.desc())).all()
    result = []
    for job in jobs:
        order = session.get(Order, job.order_id) if job.order_id else None
        piece = session.get(Piece, job.piece_id) if job.piece_id else None
        result.append({
            "id": job.id,
            "client_name": order.client_name if order else "(unknown)",
            "piece_name": piece.name if piece else "(unknown)",
            "created_at": job.created_at,
            "total_cost": job.total_cost,
            "notes": job.notes,
            "line_items_total": job.line_items_total,
            "metal_cost": job.metal_cost,
        })
    return result


@app.patch("/api/jobs/{job_id}")
def update_job(job_id: int, notes: str | None = None, external_invoice_id: str | None = None, session: Session = Depends(get_session)):
    j = session.get(Job, job_id)
    if not j:
        raise HTTPException(status_code=404, detail="job not found")
    
    # Recalculate totals from current piece state
    piece = session.get(Piece, j.piece_id) if j.piece_id else None
    if piece:
        items = session.exec(select(LineItem).where(LineItem.piece_id == j.piece_id)).all()
        items_total = sum(i.qty * i.unit_cost for i in items)
        j.line_items_total = items_total
        
        # Recalculate metal cost if snapshot exists
        # For now, keep existing metal_cost; could recalculate if needed
        j.total_cost = items_total + j.metal_cost
    
    if notes is not None:
        j.notes = notes
    if external_invoice_id is not None:
        j.external_invoice_id = external_invoice_id
    
    session.add(j)
    session.commit()
    session.refresh(j)
    return j


@app.delete("/api/jobs/{job_id}")
def delete_job(job_id: int, session: Session = Depends(get_session)):
    j = session.get(Job, job_id)
    if not j:
        raise HTTPException(status_code=404, detail="job not found")
    session.delete(j)
    session.commit()
    return {"ok": True}


from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request
import os

# Get the correct template directory path
template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "templates")
templates = Jinja2Templates(directory=template_dir)

@app.get("/ui", response_class=HTMLResponse)
def ui(request: Request):
    return templates.TemplateResponse("ui.html", {"request": request})

