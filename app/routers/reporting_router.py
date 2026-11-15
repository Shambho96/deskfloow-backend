import csv
import io
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, Response, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.core.dependencies import get_current_user_context
from app.core.context import UserContext
from app.services.reporting_service import execute_custom_report, resolve_date_range

router = APIRouter(prefix="/api/v1/reports", tags=["Reporting Exports"])


@router.get("/export")
async def export_report(
    report_type: str = Query("ROOM_REVENUE", description="Report domain/type code"),
    date_preset: str = Query("last_30_days"),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    group_by: str = Query("daily"),
    metrics: Optional[str] = Query(None, description="Comma-separated metric keys"),
    outlet_ids: Optional[str] = Query(None, description="Comma-separated outlet IDs"),
    export_format: str = Query("csv", description="csv or json"),
    ctx: UserContext = Depends(get_current_user_context),
    db: AsyncSession = Depends(get_db),
):
    """
    Exports a custom report directly as a downloadable CSV or JSON file.
    """
    # 1. Parse outlets
    if outlet_ids:
        try:
            parsed_outlets = [int(x.strip()) for x in outlet_ids.split(",") if x.strip()]
        except ValueError:
            parsed_outlets = [int(ctx.outlet_id)] if ctx.outlet_id else [1]
    else:
        parsed_outlets = [int(ctx.outlet_id)] if ctx.outlet_id else [1]

    # Security check: User must be allowed in requested outlets
    if not ctx.is_owner:
        allowed = set([int(x) for x in ctx.allowed_outlets] + [int(ctx.outlet_id)])
        for oid in parsed_outlets:
            if oid not in allowed:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Unauthorized access to outlet #{oid}",
                )

    # 2. Parse metrics
    if metrics:
        selected_metrics = [m.strip() for m in metrics.split(",") if m.strip()]
    else:
        selected_metrics = ["room_revenue"]

    # 3. Parse dates
    d_from = datetime.strptime(date_from, "%Y-%m-%d").date() if date_from else None
    d_to = datetime.strptime(date_to, "%Y-%m-%d").date() if date_to else None
    start_d, end_d = resolve_date_range(date_preset, d_from, d_to)

    # 4. Execute report query
    raw = await execute_custom_report(
        session=db,
        client_id=int(ctx.client_id),
        outlet_ids=parsed_outlets,
        report_type=report_type,
        date_from=start_d,
        date_to=end_d,
        group_by=group_by,
        selected_metrics=selected_metrics,
    )

    rows = raw["rows"]
    summary = raw["meta"]["summary"]

    # 5. Render output
    if export_format.lower() == "json":
        return raw

    # Generate CSV in-memory
    output = io.StringIO()
    writer = csv.writer(output)

    # Header Row
    headers = ["Period", "Date"] + [m.replace("_", " ").title() for m in selected_metrics]
    writer.writerow(headers)

    # Data Rows
    for r in rows:
        row_data = [r.get("period", ""), r.get("date", "")]
        for m in selected_metrics:
            row_data.append(r.get(m, 0.0))
        writer.writerow(row_data)

    # Summary Row
    summary_row = ["TOTAL / AVG", "—"]
    for m in selected_metrics:
        summary_row.append(summary.get(m, 0.0))
    writer.writerow(summary_row)

    csv_content = output.getvalue()
    filename = f"report_{report_type.lower()}_{start_d}_{end_d}.csv"

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
