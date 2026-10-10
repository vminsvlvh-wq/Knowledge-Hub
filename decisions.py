"""Decision Impact Tracker: measured outcomes, never invented impact."""
import uuid
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from app.auth import get_current_user
from app.db import get_db
from app.rbac import Role, require_workspace_role

router = APIRouter(prefix="/workspaces/{workspace_id}/decisions", tags=["Decision Impact Tracker"])

class DecisionIn(BaseModel):
    title: str = Field(min_length=3, max_length=180)
    problem: str = Field(min_length=3)
    rationale: str = Field(min_length=3)
    alternatives: str = ""

class MetricIn(BaseModel):
    metric_name: str = Field(min_length=2, max_length=100)
    unit: str = Field(min_length=1, max_length=40)
    direction: Literal["increase", "decrease"]
    baseline: float
    target: float

class MeasurementIn(BaseModel):
    value: float
    note: str = Field(default="", max_length=1000)

class StatusIn(BaseModel):
    status: Literal["planned", "active", "completed", "cancelled"]

def ensure_decision(workspace_id, decision_id):
    with get_db() as conn:
        row=conn.execute("SELECT * FROM decisions WHERE id=? AND workspace_id=?", (decision_id,workspace_id)).fetchone()
        if not row:
            raise HTTPException(404, "القرار غير موجود في مساحة العمل")
        return dict(row)

def ensure_metric(workspace_id, decision_id, metric_id):
    ensure_decision(workspace_id,decision_id)
    with get_db() as conn:
        row=conn.execute("SELECT * FROM decision_metrics WHERE id=? AND decision_id=?",(metric_id,decision_id)).fetchone()
        if not row:
            raise HTTPException(404, "المؤشر غير موجود في هذا القرار")
        return dict(row)

@router.post("", status_code=201)
def create_decision(workspace_id: str, body: DecisionIn, user=Depends(get_current_user)):
    require_workspace_role(workspace_id,user["id"],Role.EDITOR)
    decision_id=str(uuid.uuid4())
    with get_db() as conn:
        conn.execute("INSERT INTO decisions(id,workspace_id,title,problem,rationale,alternatives,owner_id) VALUES (?,?,?,?,?,?,?)",(decision_id,workspace_id,body.title,body.problem,body.rationale,body.alternatives,user["id"]))
    return ensure_decision(workspace_id,decision_id)

@router.get("")
def list_decisions(workspace_id: str,user=Depends(get_current_user)):
    require_workspace_role(workspace_id,user["id"],Role.VIEWER)
    with get_db() as conn:
        return [dict(x) for x in conn.execute("SELECT * FROM decisions WHERE workspace_id=? ORDER BY created_at DESC",(workspace_id,)).fetchall()]

@router.patch("/{decision_id}/status")
def update_status(workspace_id: str,decision_id: str,body: StatusIn,user=Depends(get_current_user)):
    require_workspace_role(workspace_id,user["id"],Role.EDITOR)
    ensure_decision(workspace_id,decision_id)
    with get_db() as conn:
        conn.execute("UPDATE decisions SET status=? WHERE id=? AND workspace_id=?",(body.status,decision_id,workspace_id))
    return ensure_decision(workspace_id,decision_id)

@router.post("/{decision_id}/metrics",status_code=201)
def create_metric(workspace_id: str,decision_id: str,body: MetricIn,user=Depends(get_current_user)):
    require_workspace_role(workspace_id,user["id"],Role.EDITOR)
    ensure_decision(workspace_id,decision_id)
    metric_id=str(uuid.uuid4())
    with get_db() as conn:
        conn.execute("INSERT INTO decision_metrics(id,decision_id,metric_name,unit,direction,baseline,target) VALUES(?,?,?,?,?,?,?)",(metric_id,decision_id,body.metric_name,body.unit,body.direction,body.baseline,body.target))
    return ensure_metric(workspace_id,decision_id,metric_id)

@router.post("/{decision_id}/metrics/{metric_id}/measurements",status_code=201)
def add_measurement(workspace_id: str,decision_id: str,metric_id: str,body: MeasurementIn,user=Depends(get_current_user)):
    require_workspace_role(workspace_id,user["id"],Role.EDITOR)
    ensure_metric(workspace_id,decision_id,metric_id)
    measurement_id=str(uuid.uuid4())
    with get_db() as conn:
        conn.execute("INSERT INTO decision_measurements(id,metric_id,value,note,recorded_by) VALUES(?,?,?,?,?)",(measurement_id,metric_id,body.value,body.note,user["id"]))
    return {"id":measurement_id,"metric_id":metric_id,"value":body.value,"note":body.note}

@router.get("/{decision_id}/impact")
def impact_report(workspace_id: str,decision_id: str,user=Depends(get_current_user)):
    require_workspace_role(workspace_id,user["id"],Role.VIEWER)
    decision=ensure_decision(workspace_id,decision_id)
    metrics=[]
    with get_db() as conn:
        rows=conn.execute("SELECT * FROM decision_metrics WHERE decision_id=? ORDER BY created_at,id",(decision_id,)).fetchall()
        for row in rows:
            m=dict(row)
            measurements=[dict(x) for x in conn.execute("SELECT id,value,note,recorded_by,measured_at FROM decision_measurements WHERE metric_id=? ORDER BY measured_at,id",(m["id"],)).fetchall()]
            latest=measurements[-1]["value"] if measurements else None
            baseline=m["baseline"]
            m["latest_value"]=latest
            m["absolute_change"]=round(latest-baseline,4) if latest is not None else None
            m["percent_change"]=round((latest-baseline)/abs(baseline)*100,2) if latest is not None and baseline != 0 else None
            m["target_met"]=(latest>=m["target"] if m["direction"]=="increase" else latest<=m["target"]) if latest is not None else None
            m["measurements"]=measurements
            metrics.append(m)
    return {"decision":decision,"metrics":metrics,"measurement_count":sum(len(m["measurements"]) for m in metrics),"disclaimer":"التغير المرصود لا يثبت أن القرار وحده تسبب فيه؛ يلزم تقييم العوامل الخارجية."}
