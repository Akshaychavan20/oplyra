import json
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, abort
from flask_login import login_required, current_user
from app import db
from app.models import (
    Project, Content, AnalyticsLog, Organization, Membership, Campaign,
    CarouselSlide, SocialAccount, SocialPost, WorkflowDefinition,
    WorkflowRun, AuditLog, AnalyticsMetrics
)
from app.services.ai_service import GeminiService

content_bp = Blueprint('content', __name__)

@content_bp.route('/', methods=['GET'])
@content_bp.route('/generate', methods=['GET'])
@login_required
def content_status():
    """Renders the AI Content Generation configuration form."""
    projects = Project.query.filter_by(user_id=current_user.id)\
        .order_by(Project.name.asc())\
        .all()
        
    # Read optional query parameter to pre-select a project
    selected_project_id = request.args.get('project_id', type=int)
    
    org = get_user_org(current_user.id)
    campaigns = Campaign.query.filter_by(organization_id=org.id).order_by(Campaign.name.asc()).all() if org else []
    
    return render_template(
        'content/generate.html', 
        projects=projects, 
        selected_project_id=selected_project_id,
        campaigns=campaigns
    )


@content_bp.route('/generate', methods=['POST'])
@login_required
def generate_content():
    """Handles AJAX requests to trigger the Gemini API and save the marketing asset."""
    project_id = request.form.get('project_id', type=int)
    campaign_id = request.form.get('campaign_id', type=int)
    content_type = request.form.get('type', '').strip()
    topic = request.form.get('topic', '').strip()
    product_name = request.form.get('product_name', '').strip()
    keywords_raw = request.form.get('keywords', '').strip()
    audience = request.form.get('audience', '').strip()
    tone = request.form.get('tone', '').strip()
    length = request.form.get('length', '').strip()
    cta = request.form.get('cta', '').strip()
    model = request.form.get('model', '').strip()
    
    # Form validation
    if not project_id or not content_type or not audience or not tone:
        return jsonify({"success": False, "error": "Please fill in all required configuration fields."}), 400
        
    # Project authorization check
    project = Project.query.get(project_id)
    if not project or project.user_id != current_user.id:
        return jsonify({"success": False, "error": "Unauthorized project access."}), 403
        
    # Tone/audience formatting
    keywords = [k.strip() for k in keywords_raw.split(',') if k.strip()] if keywords_raw else []
    
    try:
        # Instantiate the service layer
        ai_service = GeminiService()
        
        # Select and execute generation based on selected type
        generated_text = ""
        tokens_used = 0
        asset_title = ""
        
        if content_type == 'blog':
            if not topic:
                return jsonify({"success": False, "error": "Blog Topic is required."}), 400
            asset_title = topic
            generated_text, tokens_used = ai_service.generate_blog(
                topic=topic,
                keywords=keywords,
                audience=audience,
                tone=tone,
                product_name=product_name,
                length=length,
                cta=cta,
                model=model
            )
            
        elif content_type == 'email':
            if not product_name:
                return jsonify({"success": False, "error": "Product Name is required."}), 400
            asset_title = f"Email Campaign: {product_name}"
            if topic:
                asset_title += f" - {topic}"
            generated_text, tokens_used = ai_service.generate_email(
                product_name=product_name,
                keywords=keywords,
                audience=audience,
                tone=tone,
                topic=topic,
                length=length,
                cta=cta,
                model=model
            )
            
        elif content_type == 'facebook_post':
            if not product_name:
                return jsonify({"success": False, "error": "Product Name is required."}), 400
            asset_title = f"FB Post: {product_name}"
            generated_text, tokens_used = ai_service.generate_facebook_post(
                product_name=product_name,
                keywords=keywords,
                audience=audience,
                tone=tone,
                topic=topic,
                length=length,
                cta=cta,
                model=model
            )
            
        elif content_type == 'product_review':
            if not product_name:
                return jsonify({"success": False, "error": "Product Name is required."}), 400
            asset_title = f"Review: {product_name}"
            generated_text, tokens_used = ai_service.generate_product_review(
                product_name=product_name,
                keywords=keywords,
                audience=audience,
                tone=tone,
                length=length,
                cta=cta,
                model=model
            )
            
        elif content_type == 'carousel':
            if not product_name:
                return jsonify({"success": False, "error": "Product/Concept Name is required."}), 400
            asset_title = f"Carousel: {product_name}"
            generated_text, tokens_used = ai_service.generate_carousel(
                product_name=product_name,
                keywords=keywords,
                audience=audience,
                tone=tone,
                topic=topic,
                length=length,
                cta=cta,
                model=model
            )
            
        elif content_type == 'video_script':
            if not product_name:
                return jsonify({"success": False, "error": "Product/Topic Name is required."}), 400
            asset_title = f"Video Script: {product_name}"
            generated_text, tokens_used = ai_service.generate_video_script(
                product_name=product_name,
                keywords=keywords,
                audience=audience,
                tone=tone,
                topic=topic,
                length=length,
                cta=cta,
                model=model
            )
            
        elif content_type == 'image_prompt':
            if not product_name:
                return jsonify({"success": False, "error": "Core Subject/Concept is required."}), 400
            asset_title = f"Image Prompt: {product_name}"
            generated_text, tokens_used = ai_service.generate_image_prompt(
                product_name=product_name,
                keywords=keywords,
                topic=topic,
                model=model
            )
            
        elif content_type == 'ad_copy':
            if not product_name:
                return jsonify({"success": False, "error": "Product Name is required."}), 400
            asset_title = f"Ad Copy: {product_name}"
            generated_text, tokens_used = ai_service.generate_ad_copy(
                product_name=product_name,
                keywords=keywords,
                audience=audience,
                tone=tone,
                topic=topic,
                length=length,
                cta=cta,
                model=model
            )
        else:
            return jsonify({"success": False, "error": f"Invalid content type: {content_type}"}), 400
            
        # 1. Create content asset in the database
        prompt_data = {
            "type": content_type,
            "topic": topic,
            "product_name": product_name,
            "keywords": keywords,
            "audience": audience,
            "tone": tone,
            "length": length,
            "cta": cta,
            "model": model,
            "campaign_id": campaign_id,
            "full_prompt": getattr(ai_service, 'last_prompt', None),
            "system_instruction": getattr(ai_service, 'last_system_instruction', None)
        }
        
        org = get_user_org(current_user.id)
        content_asset = Content(
            project_id=project_id,
            organization_id=org.id if org else None,
            campaign_id=campaign_id if campaign_id else None,
            type=content_type,
            title=asset_title,
            body=generated_text,
            prompt_used=json.dumps(prompt_data),
            status='draft'
        )
        db.session.add(content_asset)
        db.session.commit()
        
        # 2. Write analytics log with token counts
        analytics_log = AnalyticsLog(
            user_id=current_user.id,
            activity_type=f"generate_{content_type}",
            token_usage=tokens_used
        )
        db.session.add(analytics_log)
        db.session.commit()
        
        # Return success with the target preview URL
        flash("Content generated successfully using AI!", "success")
        return jsonify({
            "success": True, 
            "redirect_url": url_for('content.view_content', content_id=content_asset.id)
        })
        
    except ValueError as ve:
        return jsonify({"success": False, "error": str(ve)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@content_bp.route('/view/<int:content_id>', methods=['GET'])
@login_required
def view_content(content_id):
    """Renders the AI Content preview page and formats prompt parameters."""
    content = Content.query.get_or_404(content_id)
    
    # Project authorization check
    if content.project.user_id != current_user.id:
        abort(403)
        
    # Parse prompt settings
    try:
        prompt_settings = json.loads(content.prompt_used)
    except Exception:
        prompt_settings = {}
        
    # Automatic Baseline SEO Check: Runs if no analysis has been saved yet
    from app.models import SEOAnalysis
    from app.services.seo_service import SEOAnalyzer
    
    if not content.seo_analysis:
        keywords = prompt_settings.get('keywords', [])
        if keywords:
            try:
                report = SEOAnalyzer.analyze(content.title, content.body, keywords)
                seo_rec = SEOAnalysis(
                    content_id=content.id,
                    seo_score=report['seo_score'],
                    readability_score=report['readability_score']
                )
                seo_rec.keywords_found = report['keywords_report']
                seo_rec.suggestions = report['suggestions']
                db.session.add(seo_rec)
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                # Fail silently for preview readability but log issue
                from flask import current_app
                current_app.logger.error(f"Failed to compile baseline SEO: {str(e)}")
        
    return render_template(
        'content/view.html', 
        content=content, 
        prompt_settings=prompt_settings
    )


@content_bp.route('/view/<int:content_id>/seo', methods=['POST'])
@login_required
def view_content_seo(content_id):
    """Triggers/Updates the SEO analysis scorecard using a user-specified keywords list."""
    content = Content.query.get_or_404(content_id)
    
    # Ownership verification
    if content.project.user_id != current_user.id:
        abort(403)
        
    keywords_raw = request.form.get('keywords', '').strip()
    if not keywords_raw:
        flash('Please enter at least one target keyword for SEO checking.', 'danger')
        return redirect(url_for('content.view_content', content_id=content.id))
        
    keywords = [k.strip() for k in keywords_raw.split(',') if k.strip()]
    
    from app.models import SEOAnalysis
    from app.services.seo_service import SEOAnalyzer
    
    try:
        report = SEOAnalyzer.analyze(content.title, content.body, keywords)
        
        # Check if record exists
        seo_rec = SEOAnalysis.query.filter_by(content_id=content.id).first()
        if not seo_rec:
            seo_rec = SEOAnalysis(content_id=content.id)
            db.session.add(seo_rec)
            
        seo_rec.seo_score = report['seo_score']
        seo_rec.readability_score = report['readability_score']
        seo_rec.keywords_found = report['keywords_report']
        seo_rec.suggestions = report['suggestions']
        
        # Save analysis settings to prompt keywords list as well to preserve state
        try:
            prompt_data = json.loads(content.prompt_used)
        except Exception:
            prompt_data = {}
        prompt_data['keywords'] = keywords
        content.prompt_used = json.dumps(prompt_data)
        
        db.session.commit()
        
        # Log SEO analysis
        log = AnalyticsLog(user_id=current_user.id, activity_type='seo_analysis')
        db.session.add(log)
        db.session.commit()
        
        flash('SEO analysis updated successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash('An error occurred during SEO compilations.', 'danger')
        
    return redirect(url_for('content.view_content', content_id=content.id))

@content_bp.route('/edit/<int:content_id>', methods=['POST'])
@login_required
def edit_content(content_id):
    """Saves manual edits to a generated content asset."""
    content = Content.query.get_or_404(content_id)
    
    # Ownership verification
    if content.project.user_id != current_user.id:
        abort(403)
        
    title = request.form.get('title', '').strip()
    body = request.form.get('body', '').strip()
    status = request.form.get('status', 'draft').strip()
    
    if not title or not body:
        flash('Content Title and Body cannot be empty.', 'danger')
        return redirect(url_for('content.view_content', content_id=content.id))
        
    try:
        content.title = title
        content.body = body
        content.status = status
        db.session.commit()
        
        # Log edit
        log = AnalyticsLog(user_id=current_user.id, activity_type='edit_content')
        db.session.add(log)
        db.session.commit()
        
        flash('Marketing asset updated successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash('An error occurred while saving modifications.', 'danger')
        
    return redirect(url_for('content.view_content', content_id=content.id))


@content_bp.route('/<int:content_id>/delete', methods=['POST'])
@login_required
def delete_content(content_id):
    """Deletes a generated content asset."""
    content = Content.query.get_or_404(content_id)
    
    # Ownership verification
    if content.project.user_id != current_user.id:
        abort(403)
        
    project_id = content.project_id
    title = content.title
    
    try:
        db.session.delete(content)
        db.session.commit()
        
        # Log deletion
        log = AnalyticsLog(user_id=current_user.id, activity_type='delete_content')
        db.session.add(log)
        db.session.commit()
        
        flash(f'Asset "{title}" deleted successfully.', 'info')
    except Exception as e:
        db.session.rollback()
        flash('An error occurred while deleting the asset.', 'danger')
        
    return redirect(url_for('projects.view_project', project_id=project_id))


@content_bp.route('/regenerate/<int:content_id>', methods=['POST'])
@login_required
def regenerate_content(content_id):
    """Regenerates content for an existing asset using the same prompt parameters."""
    content = Content.query.get_or_404(content_id)
    
    # Ownership verification
    if content.project.user_id != current_user.id:
        return jsonify({"success": False, "error": "Unauthorized access."}), 403
        
    # Parse original prompt settings
    try:
        prompt_data = json.loads(content.prompt_used)
    except Exception:
        return jsonify({"success": False, "error": "Original prompt parameters are missing or corrupted."}), 400
        
    content_type = prompt_data.get('type')
    topic = prompt_data.get('topic', '')
    product_name = prompt_data.get('product_name', '')
    keywords = prompt_data.get('keywords', [])
    audience = prompt_data.get('audience', 'tech enthusiasts')
    tone = prompt_data.get('tone', 'informative')
    length = prompt_data.get('length', '')
    cta = prompt_data.get('cta', '')
    model = prompt_data.get('model', '')
    
    try:
        # Instantiate the service layer
        ai_service = GeminiService()
        
        # Execute generation based on original format type
        generated_text = ""
        tokens_used = 0
        
        if content_type == 'blog':
            generated_text, tokens_used = ai_service.generate_blog(
                topic=topic,
                keywords=keywords,
                audience=audience,
                tone=tone,
                product_name=product_name,
                length=length,
                cta=cta,
                model=model
            )
        elif content_type == 'email':
            generated_text, tokens_used = ai_service.generate_email(
                product_name=product_name,
                keywords=keywords,
                audience=audience,
                tone=tone,
                topic=topic,
                length=length,
                cta=cta,
                model=model
            )
        elif content_type == 'facebook_post':
            generated_text, tokens_used = ai_service.generate_facebook_post(
                product_name=product_name,
                keywords=keywords,
                audience=audience,
                tone=tone,
                topic=topic,
                length=length,
                cta=cta,
                model=model
            )
        elif content_type == 'product_review':
            generated_text, tokens_used = ai_service.generate_product_review(
                product_name=product_name,
                keywords=keywords,
                audience=audience,
                tone=tone,
                length=length,
                cta=cta,
                model=model
            )
        elif content_type == 'carousel':
            generated_text, tokens_used = ai_service.generate_carousel(
                product_name=product_name,
                keywords=keywords,
                audience=audience,
                tone=tone,
                topic=topic,
                length=length,
                cta=cta,
                model=model
            )
        elif content_type == 'video_script':
            generated_text, tokens_used = ai_service.generate_video_script(
                product_name=product_name,
                keywords=keywords,
                audience=audience,
                tone=tone,
                topic=topic,
                length=length,
                cta=cta,
                model=model
            )
        elif content_type == 'image_prompt':
            generated_text, tokens_used = ai_service.generate_image_prompt(
                product_name=product_name,
                keywords=keywords,
                topic=topic,
                model=model
            )
        elif content_type == 'ad_copy':
            generated_text, tokens_used = ai_service.generate_ad_copy(
                product_name=product_name,
                keywords=keywords,
                audience=audience,
                tone=tone,
                topic=topic,
                length=length,
                cta=cta,
                model=model
            )
        else:
            return jsonify({"success": False, "error": f"Invalid original content type: {content_type}"}), 400
            
        # Update content asset details
        content.body = generated_text
        prompt_data["full_prompt"] = getattr(ai_service, 'last_prompt', None)
        prompt_data["system_instruction"] = getattr(ai_service, 'last_system_instruction', None)
        content.prompt_used = json.dumps(prompt_data)
        db.session.commit()
        
        # Write analytics log with token counts
        analytics_log = AnalyticsLog(
            user_id=current_user.id,
            activity_type=f"regenerate_{content_type}",
            token_usage=tokens_used
        )
        db.session.add(analytics_log)
        db.session.commit()
        
        flash("Content regenerated successfully using AI!", "success")
        return jsonify({
            "success": True,
            "redirect_url": url_for('content.view_content', content_id=content.id)
        })
        
    except ValueError as ve:
        return jsonify({"success": False, "error": str(ve)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@content_bp.route('/<int:content_id>/export', methods=['GET'])
@login_required
def export_pdf(content_id):
    """Compiles content to various formats and streams it as a file download attachment."""
    content = Content.query.get_or_404(content_id)
    
    # Ownership verification
    if content.project.user_id != current_user.id:
        abort(403)
        
    export_format = request.args.get('format', 'pdf').strip().lower()
    
    try:
        from app.services.pdf_service import PDFService
        from app.services.docx_service import DocxService
        from flask import send_file
        import io
        import re
        
        safe_title = re.sub(r'[^\w\s-]', '', content.title).strip().replace(' ', '_')
        if not safe_title:
            safe_title = 'content'

        # Log export activity
        log = AnalyticsLog(user_id=current_user.id, activity_type=f'export_{export_format}')
        db.session.add(log)
        db.session.commit()

        if export_format == 'pdf':
            pdf_buffer = PDFService.generate_pdf(content)
            return send_file(
                pdf_buffer,
                mimetype='application/pdf',
                as_attachment=True,
                download_name=f"{safe_title}.pdf"
            )
        elif export_format == 'docx':
            docx_buffer = DocxService.generate_docx(content)
            return send_file(
                docx_buffer,
                mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                as_attachment=True,
                download_name=f"{safe_title}.docx"
            )
        elif export_format == 'txt':
            # Strip simple markdown characters or serve plain body
            txt_buffer = io.BytesIO(content.body.encode('utf-8'))
            return send_file(
                txt_buffer,
                mimetype='text/plain',
                as_attachment=True,
                download_name=f"{safe_title}.txt"
            )
        elif export_format == 'markdown':
            md_buffer = io.BytesIO(content.body.encode('utf-8'))
            return send_file(
                md_buffer,
                mimetype='text/markdown',
                as_attachment=True,
                download_name=f"{safe_title}.md"
            )
        else:
            flash(f"Unsupported export format: {export_format}", "danger")
            return redirect(url_for('content.view_content', content_id=content.id))
            
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Export Error ({export_format}): {str(e)}")
        flash('An error occurred during copy compilation.', 'danger')
        return redirect(url_for('content.view_content', content_id=content.id))


# Setup audit configuration bounds
from datetime import datetime, timedelta

# Helper to get or create a default organization for a user
def get_user_org(user_id):
    membership = Membership.query.filter_by(user_id=user_id).first()
    if membership:
        return membership.organization
    
    # Create default org if not exists
    new_org = Organization(name=f"{current_user.username}'s Workspace", plan_tier='pro')
    db.session.add(new_org)
    db.session.commit()
    
    new_member = Membership(organization_id=new_org.id, user_id=user_id, role='admin')
    db.session.add(new_member)
    db.session.commit()
    return new_org

def seed_campaign_lifecycle(campaign_id):
    from app.models import CampaignLifecycleItem
    
    checklist_definitions = {
        'Onboarding': [
            'Business Details', 'Target Audience', 'Goals', 'Budget', 
            'Competitors', 'Platforms', 'Brand Notes', 'Landing Page', 
            'Google Business Profile', 'Facebook Page', 'Instagram'
        ],
        'Planning': [
            'Marketing Strategy', 'Keywords', 'Campaign Objectives', 
            'Content Plan', 'Creative Plan', 'Timeline', 'Approval'
        ],
        'Execution': [
            'Facebook Ads', 'Google Ads', 'SEO', 'Blog', 
            'Landing Page', 'Creative Upload', 'Tracking Setup'
        ],
        'Monitoring': [
            'Performance Review', 'Budget Review', 'CTR Review', 
            'SEO Progress', 'Optimization Notes'
        ],
        'Reporting': [
            'Weekly Report', 'Monthly Report', 'Client Summary', 
            'Recommendations'
        ],
        'Completed': [
            'Campaign Archive', 'Final Metrics', 'Lessons Learned', 
            'Renewal Opportunity'
        ]
    }
    
    for stage, items in checklist_definitions.items():
        for item_name in items:
            db_item = CampaignLifecycleItem(
                campaign_id=campaign_id,
                stage=stage,
                name=item_name,
                is_completed=False
            )
            db.session.add(db_item)
    db.session.commit()

@content_bp.route('/campaigns', methods=['GET', 'POST'])
@login_required
def manage_campaigns():
    org = get_user_org(current_user.id)
    if request.method == 'POST':
        data = request.get_json() or request.form
        name = data.get('name')
        camp_type = data.get('type', 'social_campaign')
        description = data.get('description', '')
        from app.utils.currency import normalize_currency

        budget = float(data.get('budget', 0.00))
        currency = normalize_currency(data.get('currency'))
        project_id = data.get('project_id')
        start_date_str = data.get('start_date')
        end_date_str = data.get('end_date')
        status = data.get('status', 'active')
        
        if not name:
            return jsonify({"success": False, "error": "Campaign name is required"}), 400
            
        from datetime import datetime
        start_date = None
        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            except ValueError:
                pass
        end_date = None
        if end_date_str:
            try:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
            except ValueError:
                pass
                
        campaign = Campaign(
            organization_id=org.id,
            project_id=int(project_id) if project_id else None,
            name=name,
            type=camp_type,
            description=description,
            budget=budget,
            currency=currency,
            start_date=start_date,
            end_date=end_date,
            status=status
        )
        db.session.add(campaign)
        
        # Log action
        audit = AuditLog(
            organization_id=org.id,
            user_id=current_user.id,
            action_type='create',
            entity_type='campaigns',
            entity_id=0
        )
        db.session.add(audit)
        db.session.commit()
        
        audit.entity_id = campaign.id
        db.session.commit()
        
        seed_campaign_lifecycle(campaign.id)
        
        return jsonify({
            "success": True,
            "campaign": {
                "id": campaign.id,
                "name": campaign.name,
                "type": campaign.type,
                "description": campaign.description,
                "budget": float(campaign.budget),
                "currency": campaign.currency,
                "status": campaign.status
            }
        }), 201
        
    campaigns = Campaign.query.join(Project).filter(Project.user_id == current_user.id).all()
    return jsonify({
        "success": True,
        "campaigns": [{
            "id": c.id,
            "name": c.name,
            "type": c.type,
            "description": c.description,
            "budget": float(c.budget),
            "currency": c.currency,
            "status": c.status
        } for c in campaigns]
    })


@content_bp.route('/campaigns/<int:campaign_id>/edit', methods=['POST'])
@login_required
def edit_campaign(campaign_id):
    campaign = Campaign.query.get_or_404(campaign_id)
    if campaign.project.user_id != current_user.id:
        abort(403)
        
    from app.utils.currency import normalize_currency

    data = request.get_json() or request.form
    name = data.get('name')
    camp_type = data.get('type')
    description = data.get('description')
    budget = data.get('budget')
    currency = data.get('currency')
    status = data.get('status')
    start_date_str = data.get('start_date')
    end_date_str = data.get('end_date')
    project_id = data.get('project_id')
    
    if name:
        campaign.name = name
    if camp_type:
        campaign.type = camp_type
    if description is not None:
        campaign.description = description
    if budget is not None:
        campaign.budget = float(budget)
    if currency is not None:
        campaign.currency = normalize_currency(currency)
    if status:
        campaign.status = status
    if project_id:
        campaign.project_id = int(project_id)
        
    from datetime import datetime
    if start_date_str:
        try:
            campaign.start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        except ValueError:
            pass
    if end_date_str:
        try:
            campaign.end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        except ValueError:
            pass
            
    try:
        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500


@content_bp.route('/campaigns/<int:campaign_id>/delete', methods=['POST'])
@login_required
def delete_campaign(campaign_id):
    campaign = Campaign.query.get_or_404(campaign_id)
    if campaign.project.user_id != current_user.id:
        abort(403)
        
    try:
        db.session.delete(campaign)
        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500

@content_bp.route('/calendar', methods=['GET'])
@login_required
def get_calendar_posts():
    org = get_user_org(current_user.id)
    from sqlalchemy.orm import joinedload
    posts = db.session.query(SocialPost)\
        .join(SocialAccount)\
        .options(joinedload(SocialPost.content), joinedload(SocialPost.social_account))\
        .filter(SocialAccount.organization_id == org.id)\
        .all()
        
    return jsonify({
        "success": True,
        "posts": [{
            "id": p.id,
            "content_title": p.content.title,
            "platform": p.social_account.platform,
            "account_name": p.social_account.account_name,
            "scheduled_at": p.scheduled_at.isoformat(),
            "published_at": p.published_at.isoformat() if p.published_at else None,
            "status": p.status,
            "failure_reason": p.failure_reason
        } for p in posts]
    })

@content_bp.route('/calendar/reschedule', methods=['POST'])
@login_required
def reschedule_post():
    data = request.get_json() or {}
    post_id = data.get('post_id')
    new_date_str = data.get('scheduled_at')
    
    if not post_id or not new_date_str:
        return jsonify({"success": False, "error": "post_id and scheduled_at are required"}), 400
        
    post = SocialPost.query.get(post_id)
    if not post or post.content.project.user_id != current_user.id:
        return jsonify({"success": False, "error": "Post not found or unauthorized"}), 404
        
    try:
        new_date = datetime.fromisoformat(new_date_str.replace('Z', '+00:00'))
        old_date = post.scheduled_at
        post.scheduled_at = new_date.replace(tzinfo=None)
        
        org = get_user_org(current_user.id)
        audit = AuditLog(
            organization_id=org.id,
            user_id=current_user.id,
            action_type='schedule',
            entity_type='social_posts',
            entity_id=post.id,
            payload_diff=json.dumps({"old_time": old_date.isoformat(), "new_time": post.scheduled_at.isoformat()})
        )
        db.session.add(audit)
        db.session.commit()
        
        return jsonify({"success": True, "message": "Post rescheduled successfully", "scheduled_at": post.scheduled_at.isoformat()})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500

@content_bp.route('/social/schedule', methods=['POST'])
@login_required
def schedule_social_post():
    data = request.get_json() or {}
    content_id = data.get('content_id')
    platform = data.get('platform')
    scheduled_at_str = data.get('scheduled_at')
    
    if not content_id or not platform or not scheduled_at_str:
        return jsonify({"success": False, "error": "content_id, platform, and scheduled_at are required"}), 400
        
    content = Content.query.get(content_id)
    if not content or content.project.user_id != current_user.id:
        return jsonify({"success": False, "error": "Content not found or unauthorized"}), 404
        
    org = get_user_org(current_user.id)
    
    account = SocialAccount.query.filter_by(organization_id=org.id, platform=platform).first()
    if not account:
        account = SocialAccount(
            organization_id=org.id,
            platform=platform,
            platform_account_id=f"mock_{platform}_123",
            account_name=f"Demo {platform.capitalize()} Account",
            access_token="placeholder_token"
        )
        db.session.add(account)
        db.session.commit()
        
    try:
        scheduled_at = datetime.fromisoformat(scheduled_at_str.replace('Z', '+00:00')).replace(tzinfo=None)
        
        post = SocialPost(
            content_id=content.id,
            social_account_id=account.id,
            scheduled_at=scheduled_at,
            status='scheduled'
        )
        db.session.add(post)
        db.session.commit()
        
        audit = AuditLog(
            organization_id=org.id,
            user_id=current_user.id,
            action_type='schedule',
            entity_type='social_posts',
            entity_id=post.id
        )
        db.session.add(audit)
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": "Post scheduled successfully",
            "post_id": post.id,
            "platform": platform,
            "scheduled_at": post.scheduled_at.isoformat()
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500

@content_bp.route('/workflows', methods=['GET', 'POST'])
@login_required
def manage_workflows():
    org = get_user_org(current_user.id)
    if request.method == 'POST':
        data = request.get_json() or {}
        name = data.get('name')
        trigger_event = data.get('trigger_event')
        trigger_config = data.get('trigger_config', {})
        actions_sequence = data.get('actions_sequence', [])
        
        if not name or not trigger_event:
            return jsonify({"success": False, "error": "name and trigger_event are required"}), 400
            
        workflow = WorkflowDefinition(
            organization_id=org.id,
            name=name,
            trigger_event=trigger_event,
            is_active=True
        )
        workflow.trigger_config = trigger_config
        workflow.actions_sequence = actions_sequence
        db.session.add(workflow)
        db.session.commit()
        
        return jsonify({
            "success": True,
            "workflow": {
                "id": workflow.id,
                "name": workflow.name,
                "trigger_event": workflow.trigger_event,
                "is_active": workflow.is_active,
                "trigger_config": workflow.trigger_config,
                "actions_sequence": workflow.actions_sequence
            }
        }), 201
        
    workflows = WorkflowDefinition.query.filter_by(organization_id=org.id).all()
    return jsonify({
        "success": True,
        "workflows": [{
            "id": w.id,
            "name": w.name,
            "trigger_event": w.trigger_event,
            "is_active": w.is_active,
            "trigger_config": w.trigger_config,
            "actions_sequence": w.actions_sequence
        } for w in workflows]
    })

@content_bp.route('/workflows/run/<int:workflow_id>', methods=['POST'])
@login_required
def run_workflow_simulation(workflow_id):
    workflow = WorkflowDefinition.query.get_or_404(workflow_id)
    org = get_user_org(current_user.id)
    
    if workflow.organization_id != org.id:
        return jsonify({"success": False, "error": "Unauthorized workflow access"}), 403
        
    data = request.get_json() or {}
    entity_id = data.get('entity_id')
    
    if not entity_id:
        return jsonify({"success": False, "error": "entity_id is required to simulate trigger"}), 400
        
    run = WorkflowRun(
        workflow_definition_id=workflow.id,
        trigger_entity_id=entity_id,
        status='running'
    )
    db.session.add(run)
    db.session.commit()
    
    actions_ran = []
    try:
        for action in workflow.actions_sequence:
            action_type = action.get('action_type')
            
            if action_type == 'generate_social_caption':
                content = Content.query.get(entity_id)
                promo_caption = Content(
                    project_id=content.project_id if content else org.id,
                    organization_id=org.id,
                    type='social_caption',
                    title=f"Promo: {content.title if content else 'New Content'}",
                    body=f"✨ Auto-Promote: {content.title if content else 'Check out our latest update!'} Read more to discover all tips.",
                    prompt_used=json.dumps({"action": "workflow_auto_caption", "trigger_entity": entity_id}),
                    status='approved'
                )
                db.session.add(promo_caption)
                db.session.commit()
                actions_ran.append(f"Generated caption ID: {promo_caption.id}")
                
            elif action_type == 'generate_ai_image':
                content = Content.query.get(entity_id)
                image_content = Content(
                    project_id=content.project_id if content else org.id,
                    organization_id=org.id,
                    type='image',
                    title=f"Promo Image for: {content.title if content else 'Asset'}",
                    body="https://s3.amazonaws.com/oplyra-media/assets/workflow_generated_promo.png",
                    prompt_used=json.dumps({"action": "workflow_auto_image", "trigger_entity": entity_id}),
                    status='approved'
                )
                db.session.add(image_content)
                db.session.commit()
                actions_ran.append(f"Generated promo image ID: {image_content.id}")
                
            elif action_type == 'schedule_social_post':
                account = SocialAccount.query.filter_by(organization_id=org.id).first()
                if not account:
                    account = SocialAccount(
                        organization_id=org.id,
                        platform='linkedin',
                        platform_account_id="linkedin_default",
                        account_name="Default LinkedIn",
                        access_token="placeholder"
                    )
                    db.session.add(account)
                    db.session.commit()
                
                caption = Content.query.filter_by(organization_id=org.id, type='social_caption').order_by(Content.id.desc()).first()
                if caption:
                    post = SocialPost(
                        content_id=caption.id,
                        social_account_id=account.id,
                        scheduled_at=datetime.utcnow() + timedelta(minutes=5),
                        status='scheduled'
                    )
                    db.session.add(post)
                    db.session.commit()
                    actions_ran.append(f"Scheduled social post ID: {post.id} for platform: {account.platform}")
                    
        run.status = 'success'
        run.completed_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            "success": True,
            "run_id": run.id,
            "status": run.status,
            "actions_executed": actions_ran
        })
    except Exception as e:
        db.session.rollback()
        run.status = 'failed'
        run.completed_at = datetime.utcnow()
        db.session.commit()
        return jsonify({"success": False, "run_id": run.id, "status": "failed", "error": str(e)}), 500

@content_bp.route('/convert', methods=['POST'])
@login_required
def convert_content_format():
    """Converts content to a new format (e.g. blog post to carousel slides or text-to-image prompt)."""
    data = request.get_json() or {}
    content_id = data.get('content_id')
    target_format = data.get('target_format')
    
    if not content_id or not target_format:
        return jsonify({"success": False, "error": "content_id and target_format are required"}), 400
        
    content = Content.query.get(content_id)
    if not content or content.project.user_id != current_user.id:
        return jsonify({"success": False, "error": "Content not found or unauthorized"}), 404
        
    org = get_user_org(current_user.id)
    
    try:
        if target_format == 'carousel':
            carousel_asset = Content(
                project_id=content.project_id,
                organization_id=org.id,
                type='carousel',
                title=f"Slides: {content.title}",
                body="Multi-slide PDF Document",
                prompt_used=json.dumps({"converted_from": content.id, "format": "carousel"}),
                status='draft'
            )
            db.session.add(carousel_asset)
            db.session.commit()
            
            slides_text = [
                f"Slide 1: Introduction to {content.title}",
                "Slide 2: Key Takeaways & Best Practices",
                "Slide 3: Read the Full Post on our Site!"
            ]
            for i, text in enumerate(slides_text, 1):
                slide = CarouselSlide(
                    content_id=carousel_asset.id,
                    slide_order=i,
                    slide_text=text,
                    media_url="https://s3.amazonaws.com/oplyra-media/assets/slide_bg.png"
                )
                slide.layout_config = {"color": "#6c5ce7", "text_align": "center"}
                db.session.add(slide)
            db.session.commit()
            
            audit = AuditLog(
                organization_id=org.id,
                user_id=current_user.id,
                action_type='generate',
                entity_type='contents',
                entity_id=carousel_asset.id
            )
            db.session.add(audit)
            db.session.commit()
            
            return jsonify({
                "success": True,
                "message": "Blog converted to carousel successfully",
                "carousel_content_id": carousel_asset.id,
                "slides_count": len(slides_text)
            })
            
        elif target_format == 'image_prompt':
            prompt_summary = f"Beautiful flat vector illustration, high resolution, theme: {content.title}"
            image_asset = Content(
                project_id=content.project_id,
                organization_id=org.id,
                type='image',
                title=f"Image prompt: {content.title}",
                body=prompt_summary,
                prompt_used=json.dumps({"converted_from": content.id, "format": "image_prompt"}),
                status='approved'
            )
            db.session.add(image_asset)
            db.session.commit()
            
            audit = AuditLog(
                organization_id=org.id,
                user_id=current_user.id,
                action_type='generate',
                entity_type='contents',
                entity_id=image_asset.id
            )
            db.session.add(audit)
            db.session.commit()
            
            return jsonify({
                "success": True,
                "message": "Text converted to image prompt successfully",
                "image_content_id": image_asset.id,
                "prompt": prompt_summary
            })
            
        elif target_format == 'video_script':
            video_script = (
                "00:00 - Hook: Ever wondered how to automate marketing?\n"
                "00:05 - Visual: Show the calendar grid dashboard.\n"
                "00:15 - Point: Oplyra lets you auto-create carousels, text & videos.\n"
                "00:25 - Outro: Sign up for free today at oplyra.com!"
            )
            video_asset = Content(
                project_id=content.project_id,
                organization_id=org.id,
                type='video',
                title=f"Shorts Script: {content.title}",
                body=video_script,
                prompt_used=json.dumps({"converted_from": content.id, "format": "video_script"}),
                status='draft'
            )
            db.session.add(video_asset)
            db.session.commit()
            
            audit = AuditLog(
                organization_id=org.id,
                user_id=current_user.id,
                action_type='generate',
                entity_type='contents',
                entity_id=video_asset.id
            )
            db.session.add(audit)
            db.session.commit()
            
            return jsonify({
                "success": True,
                "message": "Blog converted to video script successfully",
                "video_content_id": video_asset.id,
                "script": video_script
            })
            
        else:
            return jsonify({"success": False, "error": f"Unsupported conversion target: {target_format}"}), 400
            
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500

@content_bp.route('/campaigns/view', methods=['GET'])
@login_required
def campaigns_view():
    """Renders the Campaigns management page."""
    all_projects = Project.query.filter_by(user_id=current_user.id).order_by(Project.name.asc()).all()
    campaigns = Campaign.query.join(Project).filter(Project.user_id == current_user.id).order_by(Campaign.created_at.desc()).all()
    selected_project_id = request.args.get('project_id', type=int)
    return render_template(
        'content/campaigns.html',
        campaigns=campaigns,
        all_projects=all_projects,
        selected_project_id=selected_project_id,
    )


@content_bp.route('/campaigns/<int:campaign_id>/checklist/toggle', methods=['POST'])
@login_required
def toggle_campaign_checklist_item(campaign_id):
    campaign = Campaign.query.get_or_404(campaign_id)
    if campaign.project.user_id != current_user.id:
        abort(403)
        
    data = request.get_json() or {}
    item_id = data.get('item_id')
    
    from app.models import CampaignLifecycleItem
    item = CampaignLifecycleItem.query.filter_by(id=item_id, campaign_id=campaign_id).first_or_404()
    item.is_completed = not item.is_completed
    
    try:
        db.session.commit()
        return jsonify({
            "success": True,
            "item_id": item.id,
            "is_completed": item.is_completed,
            "stage": item.stage,
            "stage_progress": campaign.get_stage_progress(item.stage),
            "overall_progress": campaign.get_overall_progress()
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500


@content_bp.route('/campaigns/<int:campaign_id>/stage', methods=['POST'])
@login_required
def update_campaign_stage(campaign_id):
    campaign = Campaign.query.get_or_404(campaign_id)
    if campaign.project.user_id != current_user.id:
        abort(403)
        
    data = request.get_json() or {}
    stage = data.get('stage')
    
    valid_stages = ['Onboarding', 'Planning', 'Execution', 'Monitoring', 'Reporting', 'Completed']
    if stage not in valid_stages:
        return jsonify({"success": False, "error": "Invalid lifecycle stage"}), 400

    stage_order = valid_stages
    current_idx = stage_order.index(campaign.current_stage)
    new_idx = stage_order.index(stage)
    if new_idx > current_idx:
        current_progress = campaign.get_stage_progress(campaign.current_stage)
        if current_progress < 100:
            return jsonify({
                "success": False,
                "error": f"Complete all {campaign.current_stage} checklist items ({current_progress}% done) before advancing."
            }), 400
        
    campaign.current_stage = stage
    
    from app.services.automation_engine import AutomationEngine
    from app.models import TimelineMilestone
    from datetime import datetime
    
    # 1. Update Timeline Milestone
    milestones = TimelineMilestone.query.filter_by(campaign_id=campaign.id, stage=stage).all()
    for m in milestones:
        m.status = 'completed'
        m.completed_at = datetime.utcnow()

    try:
        db.session.commit()
        
        # 2. Automatically generate stage-specific tasks
        AutomationEngine.generate_stage_tasks(campaign, stage)
        
        # 3. Evaluate automation rules for the campaign
        if stage == 'Reporting':
            AutomationEngine.evaluate_rules(campaign, "stage_start_reporting")
        elif stage == 'Completed':
            AutomationEngine.evaluate_rules(campaign, "campaign_completed")
            
        # 4. Log stage transition activity
        AutomationEngine.log_activity(
            campaign.id, 
            current_user.id, 
            "campaign_updated", 
            f"Campaign stage updated to '{stage}'."
        )

        return jsonify({
            "success": True,
            "current_stage": campaign.current_stage,
            "stage_progress": campaign.get_stage_progress(stage)
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500

@content_bp.route('/campaigns/<int:campaign_id>/workspace', methods=['GET'])
@login_required
def campaign_workspace(campaign_id):
    """Renders the comprehensive Campaign Workspace single-page view."""
    campaign = Campaign.query.get_or_404(campaign_id)
    if campaign.project.user_id != current_user.id:
        abort(403)
        
    from app.models import CampaignLifecycleItem, Task, Content, Asset, Note, Report, Project
    from app.services.recommendation_engine import RecommendationEngine
    from datetime import date
    
    # 1. Fetch lifecycle checklist items
    lifecycle_items = CampaignLifecycleItem.query.filter_by(campaign_id=campaign_id).all()
    onboarding_items = [it for it in lifecycle_items if it.stage.lower() == 'onboarding']
    planning_items = [it for it in lifecycle_items if it.stage.lower() == 'planning']
    execution_items = [it for it in lifecycle_items if it.stage.lower() == 'execution']
    monitoring_items = [it for it in lifecycle_items if it.stage.lower() == 'monitoring']
    reporting_items = [it for it in lifecycle_items if it.stage.lower() == 'reporting']
    completed_items = [it for it in lifecycle_items if it.stage.lower() == 'completed']
    
    # 2. Group campaign tasks by urgency
    all_campaign_tasks = Task.query.filter_by(campaign_id=campaign_id, is_archived=False)\
        .order_by(Task.due_date.asc(), Task.created_at.desc())\
        .all()
        
    urgent_tasks = []
    today_tasks = []
    upcoming_tasks = []
    waiting_tasks = []
    completed_tasks = []
    
    today_date = date.today()
    
    for task in all_campaign_tasks:
        if task.status == 'completed':
            completed_tasks.append(task)
        elif task.status == 'waiting':
            waiting_tasks.append(task)
        else:
            if task.due_date:
                task_due_date = task.due_date.date()
                if task_due_date < today_date:
                    urgent_tasks.append(task)
                elif task_due_date == today_date:
                    today_tasks.append(task)
                else:
                    upcoming_tasks.append(task)
            else:
                if task.priority == 'high':
                    urgent_tasks.append(task)
                else:
                    upcoming_tasks.append(task)
                    
    # 3. Fetch notes, files, reports, contents
    contents = Content.query.filter_by(campaign_id=campaign_id).order_by(Content.generated_at.desc()).all()
    
    membership = current_user.memberships[0] if current_user.memberships else None
    org_id = membership.organization_id if membership else None
    assets = Asset.query.filter_by(organization_id=org_id).order_by(Asset.created_at.desc()).all() if org_id else []
    
    notes = Note.query.filter_by(campaign_id=campaign_id).order_by(Note.created_at.desc()).all()
    reports = Report.query.filter_by(campaign_id=campaign_id).order_by(Report.created_at.desc()).all()
    
    # 4. Fetch dynamic suggestions and marketing intelligence components
    from app.services.marketing_intelligence import MarketingIntelligenceEngine
    recommendations = MarketingIntelligenceEngine.get_personalized_recommendations(campaign_id)
    health = MarketingIntelligenceEngine.get_campaign_health(campaign)
    best_next_action = MarketingIntelligenceEngine.get_best_next_action(campaign)
    prioritized_tasks = MarketingIntelligenceEngine.get_smart_prioritized_tasks(campaign_id)
    risks = MarketingIntelligenceEngine.get_campaign_risks(campaign)
    opportunities = MarketingIntelligenceEngine.get_campaign_opportunities(campaign)
    insights = MarketingIntelligenceEngine.get_campaign_insights(campaign)
    
    # 5. Fetch Sprint 4 automation structures
    from app.models import TimelineMilestone, ActivityLog, AutomationRule
    timeline_milestones = TimelineMilestone.query.filter_by(campaign_id=campaign_id).order_by(TimelineMilestone.due_date.asc()).all()
    activity_logs = ActivityLog.query.filter_by(campaign_id=campaign_id).order_by(ActivityLog.created_at.desc()).all()
    automation_rules = AutomationRule.query.filter_by(campaign_id=campaign_id).all()

    all_projects = Project.query.filter_by(user_id=current_user.id).order_by(Project.name.asc()).all()
    
    return render_template(
        'content/campaign_workspace.html',
        campaign=campaign,
        onboarding_items=onboarding_items,
        planning_items=planning_items,
        execution_items=execution_items,
        monitoring_items=monitoring_items,
        reporting_items=reporting_items,
        completed_items=completed_items,
        urgent_tasks=urgent_tasks,
        today_tasks=today_tasks,
        upcoming_tasks=upcoming_tasks,
        waiting_tasks=waiting_tasks,
        completed_tasks=completed_tasks,
        contents=contents,
        assets=assets,
        notes=notes,
        reports=reports,
        recommendations=recommendations,
        all_projects=all_projects,
        health=health,
        best_next_action=best_next_action,
        prioritized_tasks=prioritized_tasks,
        risks=risks,
        opportunities=opportunities,
        insights=insights,
        timeline_milestones=timeline_milestones,
        activity_logs=activity_logs,
        automation_rules=automation_rules
    )

@content_bp.route('/calendar/view', methods=['GET'])
@login_required
def calendar_view():
    """Renders the interactive scheduled Content Calendar page."""
    org = get_user_org(current_user.id)
    accounts = SocialAccount.query.filter_by(organization_id=org.id).all()
    contents = db.session.query(Content)\
        .join(Project)\
        .filter(Project.user_id == current_user.id)\
        .all()
    return render_template('content/calendar.html', accounts=accounts, contents=contents)


@content_bp.route('/improve/<int:content_id>', methods=['POST'])
@login_required
def improve_content(content_id):
    """Triggers the Gemini API to improve, shorten, humanize, or rewrite content using AIGateway."""
    content = Content.query.get_or_404(content_id)
    if content.project.user_id != current_user.id:
        return jsonify({"success": False, "error": "Unauthorized access."}), 403
        
    data = request.get_json() or request.form or {}
    action = data.get('action', '').strip().lower()
    
    if not action:
        return jsonify({"success": False, "error": "No action specified."}), 400
        
    action_instructions = {
        'rewrite': "Rewrite the following copy. Maintain the original message, length, and structural headings, but express it differently with refreshed vocabulary.",
        'improve': "Improve the overall grammar, flow, spelling, structure, and vocabulary of the following copy. Do not remove headers.",
        'expand': "Expand the following copy by introducing more detailed paragraphs, context, and logical elaboration, without adding fluff.",
        'shorten': "Condense the following copy. Make it concise, crisp, and direct. Eliminate wordy sentences while retaining all key marketing messages.",
        'humanize': "Humanize the following text. Write naturally, like an expert human copywriter. Remove robotic transitions, overly complex templates, or typical AI sentence structures.",
        'seo_optimize': "Optimize the following text for search engine standards. Build strong keyword density and context structure without stuffing.",
        'tone_professional': "Adjust the tone of the copy to be highly professional, corporate, and authoritative.",
        'tone_friendly': "Adjust the tone of the copy to be friendly, warm, conversational, and approachable.",
        'tone_persuasive': "Adjust the tone of the copy to be highly persuasive, benefit-oriented, and conversion-focused.",
        'tone_formal': "Adjust the tone of the copy to be formal, respectful, and sophisticated.",
        'tone_casual': "Adjust the tone of the copy to be casual, colloquial, and lighthearted."
    }
    
    instruction = action_instructions.get(action)
    if not instruction:
        return jsonify({"success": False, "error": f"Invalid action: {action}"}), 400
        
    system_instruction = (
        "You are an expert content editor and copywriter. Optimize and edit the text strictly according to the user instruction. "
        "Do NOT write any conversational meta-text or preambles. Output raw Markdown text directly. "
        "Do NOT wrap your output in markdown code blocks or code fences."
    )
    
    prompt = f"Instruction: {instruction}\n\nOriginal Text:\n{content.body}"
    
    try:
        from app.services.ai_gateway import AIGateway
        gateway = AIGateway()
        
        improved_text, tokens_used = gateway.generate(
            prompt=prompt,
            system_instruction=system_instruction,
            model='gemini-1.5-flash',
            user_id=current_user.id,
            skip_cache=True
        )
        
        # Write analytics log
        log = AnalyticsLog(
            user_id=current_user.id,
            activity_type=f"improve_{action}",
            token_usage=tokens_used
        )
        db.session.add(log)
        db.session.commit()
        
        return jsonify({
            "success": True,
            "original": content.body,
            "improved": improved_text
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ==========================================
# SPRINT 3: CONTENT LIBRARY ENDPOINTS
# ==========================================

@content_bp.route('/library', methods=['GET'])
@login_required
def content_library():
    """Renders the comprehensive content library page with search, filters, sorting, and pagination."""
    q = request.args.get('q', '').strip()
    content_type = request.args.get('type', '').strip()
    status = request.args.get('status', '').strip()
    favorites_only = request.args.get('favorites', '').strip().lower() in ['true', '1']
    project_id = request.args.get('project_id', type=int)
    sort_by = request.args.get('sort_by', 'newest').strip()
    page = request.args.get('page', 1, type=int)
    
    query = Content.query.join(Project).filter(Project.user_id == current_user.id)
    
    # Text Search
    if q:
        query = query.filter(Content.title.contains(q) | Content.body.contains(q))
        
    # Filters
    if content_type:
        query = query.filter(Content.type == content_type)
    if status:
        query = query.filter(Content.status == status)
    else:
        # Default: hide soft-deleted items unless explicitly looking for them
        query = query.filter(Content.status != 'deleted')
        
    if favorites_only:
        query = query.filter(Content.is_favorite == True)
    if project_id:
        query = query.filter(Content.project_id == project_id)
        
    # Sorting
    if sort_by == 'oldest':
        query = query.order_by(Content.generated_at.asc())
    elif sort_by == 'title_asc':
        query = query.order_by(Content.title.asc())
    elif sort_by == 'title_desc':
        query = query.order_by(Content.title.desc())
    elif sort_by == 'seo_high':
        from app.models import SEOAnalysis
        query = query.outerjoin(SEOAnalysis).order_by(SEOAnalysis.seo_score.desc())
    elif sort_by == 'seo_low':
        from app.models import SEOAnalysis
        query = query.outerjoin(SEOAnalysis).order_by(SEOAnalysis.seo_score.asc())
    else: # newest
        query = query.order_by(Content.generated_at.desc())
        
    pagination = query.paginate(page=page, per_page=12, error_out=False)
    contents = pagination.items
    
    all_projects = Project.query.filter_by(user_id=current_user.id).order_by(Project.name.asc()).all()
    
    return render_template(
        'content/library.html',
        contents=contents,
        pagination=pagination,
        all_projects=all_projects,
        search_query=q,
        selected_type=content_type,
        selected_status=status,
        favorites_only=favorites_only,
        selected_project=project_id,
        selected_sort=sort_by
    )

@content_bp.route('/api/bulk-action', methods=['POST'])
@login_required
def bulk_action():
    """Handles bulk operations for multiple copywriting assets."""
    data = request.get_json() or {}
    action = data.get('action', '').strip().lower()
    content_ids = data.get('ids', [])
    
    if not content_ids:
        return jsonify({"success": False, "error": "No items selected."}), 400
        
    # Ownership verification
    contents = Content.query.join(Project).filter(
        Project.user_id == current_user.id,
        Content.id.in_(content_ids)
    ).all()
    
    if len(contents) != len(content_ids):
        return jsonify({"success": False, "error": "Unauthorized or invalid assets selected."}), 403
        
    try:
        if action == 'delete':
            # Soft delete: move to trash bin
            for content in contents:
                content.status = 'deleted'
            db.session.commit()
            return jsonify({"success": True, "message": f"Successfully moved {len(contents)} items to Trash."})
            
        elif action == 'restore':
            # Restore soft deleted items
            for content in contents:
                content.status = 'draft'
            db.session.commit()
            return jsonify({"success": True, "message": f"Successfully restored {len(contents)} items."})
            
        elif action == 'permanent_delete':
            # Permanently remove from database
            for content in contents:
                db.session.delete(content)
            db.session.commit()
            return jsonify({"success": True, "message": f"Successfully deleted {len(contents)} items permanently."})
            
        elif action == 'favorite':
            for content in contents:
                content.is_favorite = True
            db.session.commit()
            return jsonify({"success": True, "message": f"Successfully added {len(contents)} items to Favorites."})
            
        elif action == 'unfavorite':
            for content in contents:
                content.is_favorite = False
            db.session.commit()
            return jsonify({"success": True, "message": f"Successfully removed {len(contents)} items from Favorites."})
            
        elif action == 'move':
            project_id = data.get('project_id')
            if not project_id:
                return jsonify({"success": False, "error": "Target project is required."}), 400
            # Verify target project ownership
            target_proj = Project.query.filter_by(id=project_id, user_id=current_user.id).first()
            if not target_proj:
                return jsonify({"success": False, "error": "Unauthorized target workspace."}), 403
                
            campaign_id = data.get('campaign_id')
            
            for content in contents:
                content.project_id = project_id
                content.campaign_id = campaign_id if campaign_id else None
            db.session.commit()
            return jsonify({"success": True, "message": f"Successfully moved {len(contents)} items."})
            
        elif action == 'export':
            # Batch export as ZIP archive
            import io
            import zipfile
            import re
            
            export_format = data.get('export_format', 'markdown').strip().lower()
            zip_buffer = io.BytesIO()
            
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for content in contents:
                    # Sanitize filename
                    safe_title = re.sub(r'[^\w\s-]', '', content.title).strip().replace(' ', '_')
                    if not safe_title:
                        safe_title = f"copy_{content.id}"
                        
                    if export_format == 'markdown':
                        filename = f"{safe_title}.md"
                        file_data = content.body.encode('utf-8')
                        zip_file.writestr(filename, file_data)
                        
                    elif export_format == 'txt':
                        filename = f"{safe_title}.txt"
                        file_data = content.body.encode('utf-8')
                        zip_file.writestr(filename, file_data)
                        
                    elif export_format == 'pdf':
                        from app.services.pdf_service import PDFService
                        filename = f"{safe_title}.pdf"
                        pdf_stream = PDFService.generate_pdf(content)
                        zip_file.writestr(filename, pdf_stream.getvalue())
                        
                    elif export_format == 'docx':
                        from app.services.docx_service import DocxService
                        filename = f"{safe_title}.docx"
                        docx_stream = DocxService.generate_docx(content)
                        zip_file.writestr(filename, docx_stream.getvalue())
            
            zip_buffer.seek(0)
            
            # Log export activity
            log = AnalyticsLog(user_id=current_user.id, activity_type=f"bulk_export_{export_format}")
            db.session.add(log)
            db.session.commit()
            
            from flask import send_file
            import uuid
            zip_filename = f"bulk_export_{uuid.uuid4().hex[:8]}.zip"
            return send_file(
                zip_buffer,
                mimetype='application/zip',
                as_attachment=True,
                download_name=zip_filename
            )
            
        else:
            return jsonify({"success": False, "error": f"Invalid action: {action}"}), 400
            
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500


@content_bp.route('/campaigns/wizard', methods=['POST'])
@login_required
def create_campaign_wizard():
    org = get_user_org(current_user.id)
    data = request.get_json() or {}
    
    name = data.get('name')
    playbook_key = data.get('playbook')
    goal = data.get('goal')
    platforms = data.get('platforms', [])
    if not platforms and playbook_key:
        _DEFAULT_PLATFORMS = {
            'facebook_lead_gen': ['facebook'],
            'google_search': ['google'],
            'seo_campaign': ['seo'],
            'local_business': ['facebook', 'google'],
            'ecommerce': ['facebook', 'google'],
            'restaurant': ['facebook'],
            'clinic': ['facebook', 'google'],
            'gym': ['facebook'],
            'furniture_store': ['facebook', 'google'],
        }
        platforms = _DEFAULT_PLATFORMS.get(playbook_key, ['facebook'])
    from app.utils.currency import normalize_currency

    budget = float(data.get('budget', 0.00))
    currency = normalize_currency(data.get('currency'))
    start_date_str = data.get('start_date')
    end_date_str = data.get('end_date')
    duration_type = (data.get('duration_type') or 'fixed').strip().lower()
    recurrence = data.get('recurrence')
    project_id = data.get('project_id')
    import_campaign_id = data.get('import_campaign_id')
    
    if not name:
        return jsonify({"success": False, "error": "Campaign name is required"}), 400
    if not project_id:
        return jsonify({"success": False, "error": "Client Workspace project is required"}), 400

    if duration_type not in ('fixed', 'ongoing', 'recurring'):
        duration_type = 'fixed'
        
    from datetime import datetime
    if not start_date_str:
        return jsonify({"success": False, "error": "Start date is required"}), 400
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
    except ValueError:
        return jsonify({"success": False, "error": "Invalid start date"}), 400

    end_date = None
    if duration_type == 'fixed':
        if not end_date_str:
            return jsonify({"success": False, "error": "End date is required for fixed-duration campaigns"}), 400
        try:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        except ValueError:
            return jsonify({"success": False, "error": "Invalid end date"}), 400
        if end_date < start_date:
            return jsonify({"success": False, "error": "End date must be on or after the start date"}), 400
    elif duration_type == 'ongoing':
        end_date = None
    elif duration_type == 'recurring':
        allowed_recurrence = {'daily', 'weekly', 'monthly', 'quarterly', 'yearly'}
        recurrence = (recurrence or 'weekly').strip().lower()
        if recurrence not in allowed_recurrence:
            return jsonify({"success": False, "error": "Please select a valid recurrence frequency"}), 400
        if end_date_str:
            try:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
            except ValueError:
                return jsonify({"success": False, "error": "Invalid end date"}), 400
            if end_date < start_date:
                return jsonify({"success": False, "error": "End date must be on or after the start date"}), 400

    from app.services.automation_engine import AutomationEngine
    campaign = AutomationEngine.create_campaign_from_wizard(
        user_id=current_user.id,
        org_id=org.id,
        project_id=int(project_id),
        name=name,
        playbook_key=playbook_key,
        goal=goal,
        platforms=platforms,
        budget=budget,
        currency=currency,
        start_date=start_date,
        end_date=end_date,
        duration_type=duration_type,
        recurrence=recurrence if duration_type == 'recurring' else None,
        import_campaign_id=int(import_campaign_id) if import_campaign_id else None
    )

    return jsonify({
        "success": True,
        "campaign_id": campaign.id
    }), 201


@content_bp.route('/campaigns/<int:campaign_id>/automation-rules', methods=['POST'])
@login_required
def toggle_campaign_automation_rule(campaign_id):
    campaign = Campaign.query.get_or_404(campaign_id)
    if campaign.project.user_id != current_user.id:
        abort(403)
        
    data = request.get_json() or {}
    rule_id = data.get('rule_id')
    
    from app.models import AutomationRule
    rule = AutomationRule.query.filter_by(id=rule_id, campaign_id=campaign_id).first_or_404()
    rule.is_enabled = not rule.is_enabled
    db.session.commit()
    
    from app.services.automation_engine import AutomationEngine
    status = "enabled" if rule.is_enabled else "disabled"
    AutomationEngine.log_activity(
        campaign.id,
        current_user.id,
        "campaign_updated",
        f"Automation rule was {status}."
    )
    
    return jsonify({
        "success": True,
        "rule_id": rule.id,
        "is_enabled": rule.is_enabled
    })


