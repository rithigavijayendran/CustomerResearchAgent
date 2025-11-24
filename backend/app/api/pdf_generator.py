"""
PDF Generation using Playwright/Puppeteer
Creates professional PDFs from HTML templates with citations and page numbers
"""

import os
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from io import BytesIO
from pathlib import Path

logger = logging.getLogger(__name__)

# Try to import Playwright
try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("Playwright not available. PDF generation will use fallback method.")


async def generate_pdf_from_plan(
    plan_json: Dict[str, Any],
    company_name: str,
    user_name: str = "User",
    sources: Optional[list] = None
) -> BytesIO:
    """
    Generate PDF from account plan using Playwright
    
    Args:
        plan_json: Account plan JSON data
        company_name: Company name
        user_name: User name
        sources: List of sources for citations
        
    Returns:
        BytesIO buffer containing PDF
    """
    if not PLAYWRIGHT_AVAILABLE:
        # Fallback to ReportLab
        from app.api.pdf_export import create_pdf_from_account_plan
        return create_pdf_from_account_plan(plan_json, company_name)
    
    try:
        # Read HTML template
        template_path = Path(__file__).parent.parent.parent / "templates" / "plan_print.html"
        if not template_path.exists():
            logger.error(f"Template not found: {template_path}")
            # Fallback
            from app.api.pdf_export import create_pdf_from_account_plan
            return create_pdf_from_account_plan(plan_json, company_name)
        
        with open(template_path, 'r', encoding='utf-8') as f:
            html_template = f.read()
        
        # Prepare sections
        sections = []
        section_mapping = {
            "company_overview": "Company Overview",
            "market_summary": "Market Summary",
            "key_insights": "Key Insights",
            "pain_points": "Pain Points",
            "opportunities": "Opportunities",
            "competitor_analysis": "Competitor Analysis",
            "swot": "SWOT Analysis",
            "strategic_recommendations": "Strategic Recommendations",
            "final_account_plan": "Executive Summary"
        }
        
        for key, title in section_mapping.items():
            content = plan_json.get(key, "")
            if content:
                # Add citations if sources available
                if sources and key in ["opportunities", "pain_points", "key_insights"]:
                    # Add citation badges (simplified - in production, map to actual sources)
                    content_with_citations = add_citations(content, sources)
                else:
                    content_with_citations = content
                
                sections.append({
                    "title": title,
                    "content": format_content(content_with_citations)
                })
        
        # Render template
        html_content = render_template(
            html_template,
            company_name=company_name,
            date=datetime.utcnow().strftime("%B %d, %Y"),
            user_name=user_name,
            sections=sections
        )
        
        # Generate PDF with Playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            await page.set_content(html_content, wait_until="networkidle")
            
            # Generate PDF
            pdf_bytes = await page.pdf(
                format="A4",
                margin={
                    "top": "1in",
                    "right": "1in",
                    "bottom": "1in",
                    "left": "1in"
                },
                print_background=True,
                display_header_footer=True,
                header_template='<div></div>',
                footer_template='<div style="font-size: 10px; text-align: center; width: 100%;"><span class="pageNumber"></span> / <span class="totalPages"></span></div>'
            )
            
            await browser.close()
            
            return BytesIO(pdf_bytes)
            
    except Exception as e:
        logger.error(f"Error generating PDF with Playwright: {e}", exc_info=True)
        # Fallback to ReportLab
        from app.api.pdf_export import create_pdf_from_account_plan
        return create_pdf_from_account_plan(plan_json, company_name)


def render_template(template: str, **kwargs) -> str:
    """Simple template rendering (replace {{var}} with values)"""
    result = template
    
    # Handle sections list first
    if 'sections' in kwargs:
        sections = kwargs['sections']
        sections_html = ""
        for section in sections:
            section_html = f"""
            <div class="section">
                <div class="section-title">{section.get('title', '')}</div>
                <div class="section-content">{section.get('content', '')}</div>
            </div>
            """
            sections_html += section_html
        # Replace mustache-style sections block
        import re
        result = re.sub(r'\{\{#sections\}\}.*?\{\{/sections\}\}', sections_html, result, flags=re.DOTALL)
    
    # Replace other variables
    for key, value in kwargs.items():
        if key != 'sections':
            result = result.replace(f"{{{{{key}}}}}", str(value))
    
    return result


def format_content(content: str) -> str:
    """Format content for HTML (markdown-like to HTML)"""
    import re
    
    # Convert markdown-style formatting
    # Bold
    content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', content)
    # Italic
    content = re.sub(r'\*(.+?)\*', r'<em>\1</em>', content)
    # Bullet points
    lines = content.split('\n')
    formatted_lines = []
    in_list = False
    
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('- ') or stripped.startswith('• '):
            if not in_list:
                formatted_lines.append('<ul>')
                in_list = True
            item_text = stripped[2:].strip()
            formatted_lines.append(f'<li>{item_text}</li>')
        else:
            if in_list:
                formatted_lines.append('</ul>')
                in_list = False
            if stripped:
                formatted_lines.append(f'<p>{stripped}</p>')
    
    if in_list:
        formatted_lines.append('</ul>')
    
    return '\n'.join(formatted_lines)


def add_citations(content: str, sources: list) -> str:
    """Add citation badges to content"""
    import re
    
    # Simple citation: add [1], [2] etc. for each source mentioned
    # In production, this would be more sophisticated
    citation_count = 1
    for source in sources[:5]:  # Limit to 5 citations
        url = source.get('url', '')
        if url:
            # Add citation badge
            citation_html = f'<span class="citation">[{citation_count}]</span>'
            # Add at end of first paragraph mentioning the topic
            content = content + citation_html
            citation_count += 1
    
    return content

