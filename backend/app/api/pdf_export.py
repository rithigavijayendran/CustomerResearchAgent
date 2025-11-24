"""
PDF Export functionality for Account Plans
"""

from fastapi import APIRouter, Request, HTTPException
from app.models.schemas import AccountPlanSection
import logging
from typing import Dict, Any
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from io import BytesIO
import base64

logger = logging.getLogger(__name__)

router = APIRouter()

def create_pdf_from_account_plan(account_plan: Dict[str, Any], company_name: str = "Company") -> BytesIO:
    """Create a PDF document from account plan data"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.5*inch, bottomMargin=0.5*inch)
    
    # Container for the 'Flowable' objects
    elements = []
    
    # Define styles
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1e40af'),
        spaceAfter=30,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#1e40af'),
        spaceAfter=12,
        spaceBefore=20,
        fontName='Helvetica-Bold'
    )
    
    subheading_style = ParagraphStyle(
        'CustomSubHeading',
        parent=styles['Heading3'],
        fontSize=14,
        textColor=colors.HexColor('#3b82f6'),
        spaceAfter=10,
        spaceBefore=15,
        fontName='Helvetica-Bold'
    )
    
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=11,
        textColor=colors.HexColor('#1f2937'),
        spaceAfter=12,
        alignment=TA_JUSTIFY,
        leading=14
    )
    
    bullet_style = ParagraphStyle(
        'CustomBullet',
        parent=styles['Normal'],
        fontSize=11,
        textColor=colors.HexColor('#1f2937'),
        spaceAfter=8,
        leftIndent=20,
        bulletIndent=10,
        leading=14
    )
    
    # Title
    elements.append(Paragraph(f"Account Plan: {company_name}", title_style))
    elements.append(Spacer(1, 0.3*inch))
    
    # Company Overview
    if account_plan.get('company_overview'):
        elements.append(Paragraph("Company Overview", heading_style))
        elements.append(Paragraph(account_plan['company_overview'], normal_style))
        elements.append(Spacer(1, 0.2*inch))
    
    # Market Summary
    if account_plan.get('market_summary'):
        elements.append(Paragraph("Market Summary", heading_style))
        elements.append(Paragraph(account_plan['market_summary'], normal_style))
        elements.append(Spacer(1, 0.2*inch))
    
    # Key Insights
    if account_plan.get('key_insights'):
        elements.append(Paragraph("Key Insights", heading_style))
        # Split by bullet points or newlines
        insights_text = account_plan['key_insights']
        if '\n' in insights_text or '•' in insights_text:
            for line in insights_text.split('\n'):
                line = line.strip()
                if line and not line.startswith('•'):
                    line = '• ' + line
                if line:
                    elements.append(Paragraph(line, bullet_style))
        else:
            elements.append(Paragraph(insights_text, normal_style))
        elements.append(Spacer(1, 0.2*inch))
    
    # Pain Points
    if account_plan.get('pain_points'):
        elements.append(Paragraph("Pain Points", heading_style))
        pain_text = account_plan['pain_points']
        if '\n' in pain_text or '•' in pain_text:
            for line in pain_text.split('\n'):
                line = line.strip()
                if line and not line.startswith('•'):
                    line = '• ' + line
                if line:
                    elements.append(Paragraph(line, bullet_style))
        else:
            elements.append(Paragraph(pain_text, normal_style))
        elements.append(Spacer(1, 0.2*inch))
    
    # Opportunities
    if account_plan.get('opportunities'):
        elements.append(Paragraph("Opportunities", heading_style))
        opp_text = account_plan['opportunities']
        if '\n' in opp_text or '•' in opp_text:
            for line in opp_text.split('\n'):
                line = line.strip()
                if line and not line.startswith('•'):
                    line = '• ' + line
                if line:
                    elements.append(Paragraph(line, bullet_style))
        else:
            elements.append(Paragraph(opp_text, normal_style))
        elements.append(Spacer(1, 0.2*inch))
    
    # Competitor Analysis
    if account_plan.get('competitor_analysis'):
        elements.append(Paragraph("Competitor Analysis", heading_style))
        elements.append(Paragraph(account_plan['competitor_analysis'], normal_style))
        elements.append(Spacer(1, 0.2*inch))
    
    # SWOT Analysis
    if account_plan.get('swot'):
        elements.append(Paragraph("SWOT Analysis", heading_style))
        swot = account_plan['swot']
        
        # Create SWOT table
        swot_data = []
        if swot.get('strengths'):
            swot_data.append(['Strengths', swot['strengths']])
        if swot.get('weaknesses'):
            swot_data.append(['Weaknesses', swot['weaknesses']])
        if swot.get('opportunities'):
            swot_data.append(['Opportunities', swot['opportunities']])
        if swot.get('threats'):
            swot_data.append(['Threats', swot['threats']])
        
        if swot_data:
            swot_table = Table(swot_data, colWidths=[1.5*inch, 5*inch])
            swot_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e5e7eb')),
                ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#1f2937')),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (0, -1), 11),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#d1d5db')),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            elements.append(swot_table)
        elements.append(Spacer(1, 0.2*inch))
    
    # Strategic Recommendations
    if account_plan.get('strategic_recommendations'):
        elements.append(Paragraph("Strategic Recommendations", heading_style))
        rec_text = account_plan['strategic_recommendations']
        if '\n' in rec_text or '•' in rec_text:
            for line in rec_text.split('\n'):
                line = line.strip()
                if line and not line.startswith('•'):
                    line = '• ' + line
                if line:
                    elements.append(Paragraph(line, bullet_style))
        else:
            elements.append(Paragraph(rec_text, normal_style))
        elements.append(Spacer(1, 0.2*inch))
    
    # Final Account Plan
    if account_plan.get('final_account_plan'):
        elements.append(PageBreak())
        elements.append(Paragraph("Executive Summary", heading_style))
        elements.append(Paragraph(account_plan['final_account_plan'], normal_style))
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer

@router.get("/{session_id}/pdf")
async def download_account_plan_pdf(session_id: str, request: Request):
    """Download account plan as PDF"""
    try:
        session_memory = request.state.session_memory
        session = session_memory.get_session(session_id)
        
        if not session or not session.get('account_plan'):
            raise HTTPException(status_code=404, detail="Account plan not found")
        
        account_plan = session['account_plan']
        company_name = session.get('company_name', 'Company')
        
        # Create PDF
        pdf_buffer = create_pdf_from_account_plan(account_plan, company_name)
        
        from fastapi.responses import Response
        return Response(
            content=pdf_buffer.read(),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="account-plan-{company_name.replace(" ", "-")}.pdf"'
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PDF generation error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error generating PDF: {str(e)}")

