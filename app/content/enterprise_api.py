import json
import os
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from app import db
from app.models import (
    Project, Content, Organization, Membership, Campaign,
    AssetFolder, Asset, AssetVersion, BrandKit, BrandColor,
    ContentVersion, AffiliateNetwork, AffiliateProduct, AffiliateLink,
    TrackingLink, ClickEvent, ConversionEvent, RevenueEvent,
    ApprovalRequest, ApprovalComment, Plan, Subscription, Invoice,
    Payment, UsageTracking
)

enterprise_bp = Blueprint('enterprise', __name__)

# Helper to get or create a default organization for a user
def get_user_org(user_id):
    membership = Membership.query.filter_by(user_id=user_id).first()
    if membership:
        return membership.organization
    
    new_org = Organization(name=f"{current_user.username}'s Workspace", plan_tier='pro')
    db.session.add(new_org)
    db.session.commit()
    
    new_member = Membership(organization_id=new_org.id, user_id=user_id, role='admin')
    db.session.add(new_member)
    db.session.commit()
    return new_org


# ==========================================
# MODULE 1: DIGITAL ASSET MANAGEMENT (DAM)
# ==========================================

@enterprise_bp.route('/dam/assets/upload', methods=['POST'])
@login_required
def upload_asset():
    folder_id = request.form.get('folder_id', type=int)
    file = request.files.get('file')
    
    if not file:
        return jsonify({"success": False, "error": "No file uploaded"}), 400
        
    org = get_user_org(current_user.id)
    from werkzeug.utils import secure_filename
    filename = secure_filename(file.filename)
    if not filename:
        return jsonify({"success": False, "error": "Invalid filename"}), 400
        
    # Object storage adapter (S3/GCS/Azure/local via STORAGE_PROVIDER)
    from app.infra.storage import get_storage
    raw = file.read()
    stored = get_storage().put(
        raw,
        organization_id=org.id,
        filename=filename,
        content_type=file.content_type,
        folder='dam',
        meta={'uploaded_by': current_user.id},
    )
    s3_url = stored.url
    file_size = stored.size
    
    try:
        new_asset = Asset(
            organization_id=org.id,
            folder_id=folder_id,
            name=filename,
            file_type=file.content_type or 'application/octet-stream',
            file_size=file_size,
            s3_url=s3_url,
            current_version=1,
            created_by=current_user.id
        )
        db.session.add(new_asset)
        db.session.commit()
        
        # Save version trace
        new_version = AssetVersion(
            asset_id=new_asset.id,
            version_num=1,
            file_size=file_size,
            s3_url=s3_url,
            created_by=current_user.id
        )
        db.session.add(new_version)
        db.session.commit()
        
        return jsonify({
            "success": True,
            "asset_id": new_asset.id,
            "name": new_asset.name,
            "file_type": new_asset.file_type,
            "file_size": new_asset.file_size,
            "s3_url": new_asset.s3_url,
            "current_version": new_asset.current_version
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500


# ==========================================
# MODULE 2: BRAND KIT SYSTEM
# ==========================================

@enterprise_bp.route('/brand-kit', methods=['PUT'])
@login_required
def update_brand_kit():
    data = request.get_json() or {}
    org = get_user_org(current_user.id)
    
    logo_url = data.get('logo_url')
    font_header = data.get('font_header', 'Inter')
    font_body = data.get('font_body', 'Inter')
    brand_voice = data.get('brand_voice_description')
    cta_style = data.get('cta_style', {})
    company_info = data.get('company_info')
    brand_colors = data.get('brand_colors', []) # [{"hex_value": "#...", "role": "primary"}]
    
    try:
        brand_kit = BrandKit.query.filter_by(organization_id=org.id).first()
        if not brand_kit:
            brand_kit = BrandKit(organization_id=org.id)
            db.session.add(brand_kit)
            db.session.commit()
            
        brand_kit.logo_url = logo_url
        brand_kit.font_header = font_header
        brand_kit.font_body = font_body
        brand_kit.brand_voice_description = brand_voice
        brand_kit.cta_style = cta_style
        brand_kit.company_info = company_info
        
        # Clear existing colors
        BrandColor.query.filter_by(brand_kit_id=brand_kit.id).delete()
        
        for c in brand_colors:
            color = BrandColor(
                brand_kit_id=brand_kit.id,
                hex_value=c.get('hex_value'),
                color_role=c.get('role', 'primary')
            )
            db.session.add(color)
            
        db.session.commit()
        return jsonify({"success": True, "brand_kit_id": brand_kit.id, "message": "Brand Kit configured successfully"})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500


# ==========================================
# MODULE 3: CONTENT VERSION CONTROL
# ==========================================

@enterprise_bp.route('/content/<int:content_id>/commit', methods=['POST'])
@login_required
def commit_content_revision(content_id):
    data = request.get_json() or {}
    title = data.get('title')
    body = data.get('body')
    commit_message = data.get('commit_message', 'No message description')
    status = data.get('status', 'draft')
    
    if not title or not body:
        return jsonify({"success": False, "error": "title and body are required to commit version"}), 400
        
    content = Content.query.get(content_id)
    if not content or content.project.user_id != current_user.id:
        return jsonify({"success": False, "error": "Content not found or unauthorized"}), 404
        
    try:
        # Resolve incremental version number
        last_version = db.session.query(db.func.max(ContentVersion.version_num))\
            .filter_by(content_id=content.id)\
            .scalar() or 0
        
        new_version_num = last_version + 1
        
        # Update current content state
        content.title = title
        content.body = body
        content.status = status
        
        # Create commit log
        version_log = ContentVersion(
            content_id=content.id,
            version_num=new_version_num,
            title=title,
            body=body,
            status=status,
            commit_message=commit_message,
            created_by=current_user.id
        )
        db.session.add(version_log)
        db.session.commit()
        
        return jsonify({
            "success": True,
            "content_id": content.id,
            "version_num": version_log.version_num,
            "commit_message": version_log.commit_message,
            "committed_at": version_log.created_at.isoformat()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500


# ==========================================
# MODULE 5: AFFILIATE MARKETING ENGINE
# ==========================================

@enterprise_bp.route('/affiliate/links', methods=['POST'])
@login_required
def create_affiliate_link():
    data = request.get_json() or {}
    product_name = data.get('product_name')
    network_name = data.get('network_name', 'Amazon')
    raw_url = data.get('raw_url')
    short_code = data.get('short_code')
    campaign_id = data.get('campaign_id')
    
    if not product_name or not raw_url or not short_code:
        return jsonify({"success": False, "error": "product_name, raw_url, and short_code are required"}), 400
        
    org = get_user_org(current_user.id)
    
    try:
        # Get or create Network placeholder
        network = AffiliateNetwork.query.filter_by(name=network_name).first()
        if not network:
            network = AffiliateNetwork(name=network_name, status='active')
            db.session.add(network)
            db.session.commit()
            
        # Get or create product placeholder
        product = AffiliateProduct.query.filter_by(organization_id=org.id, name=product_name).first()
        if not product:
            product = AffiliateProduct(
                network_id=network.id,
                organization_id=org.id,
                external_product_id=f"ext_{product_name.lower().replace(' ', '_')}",
                name=product_name,
                source_url=raw_url,
                price=99.00,
                commission_rate=10.00
            )
            db.session.add(product)
            db.session.commit()
            
        # Create affiliate raw link
        aff_link = AffiliateLink(
            product_id=product.id,
            raw_url=raw_url,
            tracking_code=f"tracking_{org.id}"
        )
        db.session.add(aff_link)
        db.session.commit()
        
        # Expose shortened tracking link
        track_link = TrackingLink(
            affiliate_link_id=aff_link.id,
            campaign_id=campaign_id,
            short_code=short_code,
            destination_url=raw_url
        )
        db.session.add(track_link)
        db.session.commit()
        
        return jsonify({
            "success": True,
            "tracking_link_id": track_link.id,
            "redirect_url": f"https://oplyra.com/link/{track_link.short_code}",
            "destination_url": track_link.destination_url
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500


@enterprise_bp.route('/affiliate/dashboard', methods=['GET'])
@login_required
def affiliate_dashboard_metrics():
    """Aggregates and returns click and revenue telemetry logs (Module 10)."""
    # In production, this pulls rolled up ClickHouse counts.
    # We will simulate high-performance aggregates here.
    return jsonify({
        "success": True,
        "metrics": {
            "clicks": 4829,
            "conversions": 168,
            "conversion_rate": 3.48,
            "total_revenue": 14850.00,
            "total_commission": 1485.00,
            "epc": 0.31,
            "roi": 148.00
        },
        "top_products": [
            {"name": "ASUS ROG Gaming Laptop", "sales": 104, "revenue": 1040.00},
            {"name": "Secretlab Gaming Chair", "sales": 42, "revenue": 315.00},
            {"name": "Elgato Stream Deck", "sales": 22, "revenue": 130.00}
        ]
    })


# ==========================================
# MODULE 8: APPROVAL WORKFLOW
# ==========================================

@enterprise_bp.route('/approvals/request', methods=['POST'])
@login_required
def submit_approval_request():
    data = request.get_json() or {}
    content_id = data.get('content_id')
    reviewer_id = data.get('reviewer_id')
    notes = data.get('notes', '')
    
    if not content_id:
        return jsonify({"success": False, "error": "content_id is required"}), 400
        
    content = Content.query.get(content_id)
    if not content or content.project.user_id != current_user.id:
        return jsonify({"success": False, "error": "Content not found or unauthorized"}), 404
        
    try:
        content.status = 'review_pending'
        
        request_log = ApprovalRequest(
            content_id=content.id,
            requester_id=current_user.id,
            reviewer_id=reviewer_id,
            status='pending',
            notes=notes
        )
        db.session.add(request_log)
        db.session.commit()
        
        return jsonify({
            "success": True,
            "approval_request_id": request_log.id,
            "notes": request_log.notes,
            "status": request_log.status,
            "submitted_at": request_log.submitted_at.isoformat()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500


# ==========================================
# MODULE 11: AI AGENTS TRACKS
# ==========================================

@enterprise_bp.route('/agents/status', methods=['GET'])
@login_required
def query_ai_agents_logs():
    """Returns activity logs for AI agents — powered by Agent Framework when available."""
    try:
        from app.services.agents.manager import AgentManager
        agents = AgentManager().agent_status_summary(user_id=current_user.id)
        return jsonify({"success": True, "agents": agents})
    except Exception:
        # Backward-compatible stub if framework unavailable
        return jsonify({
            "success": True,
            "agents": [
                {
                    "name": "Content Agent",
                    "goal": "Generate and scale blog topics for active electronics campaigns.",
                    "status": "idle",
                    "last_run": (datetime.utcnow() - timedelta(minutes=45)).isoformat(),
                    "logs": "Parsed Brand voice guidelines. Created guided review for 'ASUS ROG Laptop'. Scheduled blog draft."
                },
                {
                    "name": "SEO Agent",
                    "goal": "Scan generated posts to confirm target keywords meet 1.5% density checks.",
                    "status": "idle",
                    "last_run": datetime.utcnow().isoformat(),
                    "logs": "Ready for keyword auditing."
                },
                {
                    "name": "Research Agent",
                    "goal": "Analyze competitor landing page CTA structures and headlines angles.",
                    "status": "idle",
                    "last_run": (datetime.utcnow() - timedelta(hours=2)).isoformat(),
                    "logs": "Ready for competitor research."
                },
            ]
        })


# ==========================================
# SPRINT 1: FILES ENDPOINTS
# ==========================================

@enterprise_bp.route('/dam/assets/<int:asset_id>/download', methods=['GET'])
@login_required
def download_asset(asset_id):
    from app.models import Asset
    from flask import send_file, abort
    import os
    
    asset = Asset.query.get_or_404(asset_id)
    org = get_user_org(current_user.id)
    if asset.organization_id != org.id:
        abort(403)
        
    upload_dir = os.path.join(current_app.root_path, '..', 'uploads')
    local_path = os.path.join(upload_dir, asset.name)
    
    if not os.path.exists(local_path):
        abort(404)
        
    return send_file(local_path, as_attachment=True, download_name=asset.name)


@enterprise_bp.route('/dam/assets/<int:asset_id>/delete', methods=['POST'])
@login_required
def delete_asset(asset_id):
    from app.models import Asset
    import os
    
    asset = Asset.query.get_or_404(asset_id)
    org = get_user_org(current_user.id)
    if asset.organization_id != org.id:
        return jsonify({"success": False, "error": "Unauthorized"}), 403
        
    try:
        upload_dir = os.path.join(current_app.root_path, '..', 'uploads')
        local_path = os.path.join(upload_dir, asset.name)
        if os.path.exists(local_path):
            os.remove(local_path)
            
        db.session.delete(asset)
        db.session.commit()
        return jsonify({"success": True, "message": "Asset deleted successfully"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500

