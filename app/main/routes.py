from flask import Blueprint, render_template, redirect, url_for, jsonify, request
from flask_login import current_user, login_required
from app import db
from app.models import Project, Content, AnalyticsLog
from datetime import datetime, timedelta

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    """Root route: Redirects to login if not authenticated; renders dashboard if authenticated."""
    if not current_user.is_authenticated:
        return render_template('main/index.html')
        
    # Auto-seed onboarding tasks if none exist
    from app.models import Task, Report, Campaign
    if Task.query.filter_by(user_id=current_user.id).count() == 0:
        db.session.add_all([
            Task(user_id=current_user.id, title="Create your first Client profile", description="Go to the Clients tab and register a client portfolio.", priority="high"),
            Task(user_id=current_user.id, title="Launch your first Marketing Campaign", description="Add a campaign nested under a client to organize your marketing work.", priority="medium"),
            Task(user_id=current_user.id, title="Write an AI SEO Article", description="Use the AI Assistant to draft high-converting copy.", priority="medium")
        ])
        db.session.commit()

    # Query dashboard details
    total_projects = Project.query.filter_by(user_id=current_user.id).count()
    
    total_contents = db.session.query(Content)\
        .join(Project)\
        .filter(Project.user_id == current_user.id)\
        .count()
        
    # Retrieve the 5 most recently updated projects (Clients)
    from sqlalchemy.orm import joinedload
    recent_projects = Project.query.filter_by(user_id=current_user.id)\
        .options(joinedload(Project.contents))\
        .order_by(Project.updated_at.desc())\
        .limit(5)\
        .all()

    # Retrieve Today's Work data grouped by urgency
    from datetime import date
    all_active_tasks = Task.query.filter_by(user_id=current_user.id, is_archived=False)\
        .order_by(Task.due_date.asc(), Task.created_at.desc())\
        .all()
        
    urgent_tasks = []
    today_tasks = []
    upcoming_tasks = []
    waiting_tasks = []
    completed_tasks = []
    
    today_date = date.today()
    
    for task in all_active_tasks:
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

    upcoming_deadlines = Task.query.filter_by(user_id=current_user.id, status='pending', is_archived=False)\
        .filter(Task.due_date != None)\
        .order_by(Task.due_date.asc())\
        .limit(5)\
        .all()

    pending_reports = Report.query.filter_by(user_id=current_user.id)\
        .order_by(Report.updated_at.desc())\
        .limit(5)\
        .all()

    recent_campaigns = Campaign.query.join(Project)\
        .filter(Project.user_id == current_user.id)\
        .order_by(Campaign.created_at.desc())\
        .limit(5)\
        .all()
        
    all_projects = Project.query.filter_by(user_id=current_user.id).all()
    all_campaigns = Campaign.query.join(Project).filter(Project.user_id == current_user.id).all()

    from app.services.marketing_intelligence import MarketingIntelligenceEngine
    from app.services.automation_engine import AutomationEngine
    
    today_focus = MarketingIntelligenceEngine.get_today_focus(current_user.id)
    weekly_intelligence = MarketingIntelligenceEngine.get_weekly_intelligence(current_user.id)
    reminders = AutomationEngine.get_reminders(current_user.id)

    # Recent DAM assets for Files panel (org-scoped when membership exists)
    recent_assets = []
    try:
        from app.models import Asset, Membership
        membership = Membership.query.filter_by(user_id=current_user.id).first()
        if membership:
            recent_assets = (
                Asset.query.filter_by(organization_id=membership.organization_id)
                .order_by(Asset.id.desc())
                .limit(24)
                .all()
            )
        else:
            recent_assets = (
                Asset.query.filter_by(created_by=current_user.id)
                .order_by(Asset.id.desc())
                .limit(24)
                .all()
            )
    except Exception:
        recent_assets = []

    return render_template(
        'main/dashboard.html', 
        total_projects=total_projects, 
        total_contents=total_contents, 
        recent_projects=recent_projects,
        urgent_tasks=urgent_tasks,
        today_tasks=today_tasks,
        upcoming_tasks=upcoming_tasks,
        waiting_tasks=waiting_tasks,
        completed_tasks=completed_tasks,
        upcoming_deadlines=upcoming_deadlines,
        pending_reports=pending_reports,
        recent_campaigns=recent_campaigns,
        all_projects=all_projects,
        all_campaigns=all_campaigns,
        today_focus=today_focus,
        weekly_intelligence=weekly_intelligence,
        reminders=reminders,
        recent_assets=recent_assets,
    )

@main_bp.route('/api/analytics/dashboard')
@login_required
def analytics_dashboard():
    """API endpoint to get aggregated analytics data for the authenticated user."""
    timeframe = request.args.get('timeframe', '30d').strip().lower()
    today = datetime.utcnow().date()
    
    # 1. Backwards Compatible buckets (7-day and 30-day lists)
    date_list_7 = [today - timedelta(days=i) for i in range(6, -1, -1)]
    weekly_labels = [dt.strftime('%a') for dt in date_list_7]
    weekly_counts = [0] * 7
    weekly_tokens = [0] * 7
    date_to_idx_7 = {dt: i for i, dt in enumerate(date_list_7)}
    
    date_list_30 = [today - timedelta(days=i) for i in range(29, -1, -1)]
    monthly_labels = [dt.strftime('%b %d') for dt in date_list_30]
    monthly_counts = [0] * 30
    monthly_tokens = [0] * 30
    date_to_idx_30 = {dt: i for i, dt in enumerate(date_list_30)}
    
    # 2. Dynamic Timeframe setup
    if timeframe == '7d':
        days_limit = 7
    elif timeframe == '90d':
        days_limit = 90
    elif timeframe == 'all':
        days_limit = 365
    else: # 30d default
        days_limit = 30
        
    date_list_tf = [today - timedelta(days=i) for i in range(days_limit - 1, -1, -1)]
    tf_labels = [dt.strftime('%b %d') for dt in date_list_tf]
    tf_counts = [0] * days_limit
    tf_tokens = [0] * days_limit
    date_to_idx_tf = {dt: i for i, dt in enumerate(date_list_tf)}

    # Query projects and contents count
    total_projects = Project.query.filter_by(user_id=current_user.id).count()
    
    total_contents = db.session.query(Content)\
        .join(Project)\
        .filter(Project.user_id == current_user.id)\
        .count()
    
    # Group content counts by format types directly in database
    type_counts = db.session.query(Content.type, db.func.count(Content.id))\
        .join(Project)\
        .filter(Project.user_id == current_user.id)\
        .group_by(Content.type)\
        .all()
    
    content_type_distribution = {
        "blog": 0,
        "email": 0,
        "facebook_post": 0,
        "product_review": 0,
        "carousel": 0,
        "video_script": 0,
        "image_prompt": 0,
        "ad_copy": 0
    }
    for ctype, count in type_counts:
        if ctype in content_type_distribution:
            content_type_distribution[ctype] = count
            
    # Retrieve content dates within the limit
    start_date_tf = datetime.combine(today - timedelta(days=days_limit - 1), datetime.min.time())
    start_date_30 = datetime.combine(today - timedelta(days=29), datetime.min.time())
    
    all_timeframe_contents = db.session.query(Content.generated_at)\
        .join(Project)\
        .filter(Project.user_id == current_user.id, Content.generated_at >= start_date_tf)\
        .all()
    
    for (gen_at,) in all_timeframe_contents:
        if gen_at:
            c_date = gen_at.date()
            if c_date in date_to_idx_tf:
                tf_counts[date_to_idx_tf[c_date]] += 1
            if c_date in date_to_idx_30:
                monthly_counts[date_to_idx_30[c_date]] += 1
            if c_date in date_to_idx_7:
                weekly_counts[date_to_idx_7[c_date]] += 1
            
    # Calculate sum of tokens directly in database
    total_tokens = db.session.query(db.func.sum(AnalyticsLog.token_usage))\
        .filter_by(user_id=current_user.id)\
        .scalar() or 0
    
    # Retrieve logs within timeframe
    all_timeframe_logs = db.session.query(AnalyticsLog.created_at, AnalyticsLog.token_usage)\
        .filter(AnalyticsLog.user_id == current_user.id, AnalyticsLog.created_at >= start_date_tf)\
        .all()
    
    for created_at, token_usage in all_timeframe_logs:
        if created_at:
            log_date = created_at.date()
            if log_date in date_to_idx_tf:
                tf_tokens[date_to_idx_tf[log_date]] += token_usage
            if log_date in date_to_idx_30:
                monthly_tokens[date_to_idx_30[log_date]] += token_usage
            if log_date in date_to_idx_7:
                weekly_tokens[date_to_idx_7[log_date]] += token_usage
            
    return jsonify({
        "total_projects": total_projects,
        "total_contents": total_contents,
        "total_tokens": total_tokens,
        "content_type_distribution": content_type_distribution,
        "timeframe": timeframe,
        "timeframe_activity": {
            "labels": tf_labels,
            "counts": tf_counts
        },
        "timeframe_token_usage": {
            "labels": tf_labels,
            "tokens": tf_tokens
        },
        "weekly_activity": {
            "labels": weekly_labels,
            "counts": weekly_counts
        },
        "monthly_activity": {
            "labels": monthly_labels,
            "counts": monthly_counts
        },
        "weekly_token_usage": {
            "labels": weekly_labels,
            "tokens": weekly_tokens
        },
        "monthly_token_usage": {
            "labels": monthly_labels,
            "tokens": monthly_tokens
        }
    })


# ==========================================
# SPRINT 1: TASKS ENDPOINTS
# ==========================================

@main_bp.route('/api/tasks/new', methods=['POST'])
@login_required
def create_task():
    from app.models import Task
    data = request.get_json() or request.form
    title = data.get('title')
    description = data.get('description', '')
    priority = data.get('priority', 'medium')
    due_date_str = data.get('due_date')
    project_id = data.get('project_id')
    campaign_id = data.get('campaign_id')
    
    if not title:
        return jsonify({"success": False, "error": "Task title is required"}), 400
        
    due_date = None
    if due_date_str:
        try:
            due_date = datetime.strptime(due_date_str, '%Y-%m-%d')
        except ValueError:
            pass
            
    new_task = Task(
        user_id=current_user.id,
        title=title,
        description=description,
        priority=priority,
        due_date=due_date,
        project_id=int(project_id) if project_id else None,
        campaign_id=int(campaign_id) if campaign_id else None,
        status='pending'
    )
    
    try:
        db.session.add(new_task)
        db.session.commit()
        
        # Log timeline activity
        if new_task.campaign_id:
            from app.services.automation_engine import AutomationEngine
            AutomationEngine.log_activity(
                new_task.campaign_id,
                current_user.id,
                "campaign_updated",
                f"Task created: '{new_task.title}'."
            )
            
        return jsonify({
            "success": True, 
            "task": {
                "id": new_task.id,
                "title": new_task.title,
                "description": new_task.description,
                "priority": new_task.priority,
                "due_date": new_task.due_date.strftime('%Y-%m-%d') if new_task.due_date else None,
                "status": new_task.status
            }
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500


@main_bp.route('/api/tasks/toggle/<int:task_id>', methods=['POST'])
@login_required
def toggle_task(task_id):
    from app.models import Task
    task = Task.query.get_or_404(task_id)
    if task.user_id != current_user.id:
        abort(403)
    task.status = 'completed' if task.status == 'pending' else 'pending'
    try:
        db.session.commit()
        
        # Log timeline activity
        if task.campaign_id:
            from app.services.automation_engine import AutomationEngine
            status_label = "completed" if task.status == "completed" else "reopened"
            AutomationEngine.log_activity(
                task.campaign_id,
                current_user.id,
                "task_completed",
                f"Task '{task.title}' marked as {status_label}."
            )
            
        return jsonify({"success": True, "status": task.status})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500


@main_bp.route('/api/tasks/archive/<int:task_id>', methods=['POST'])
@login_required
def archive_task(task_id):
    from app.models import Task
    task = Task.query.get_or_404(task_id)
    if task.user_id != current_user.id:
        abort(403)
    task.is_archived = True
    try:
        db.session.commit()
        
        # Log timeline activity
        if task.campaign_id:
            from app.services.automation_engine import AutomationEngine
            AutomationEngine.log_activity(
                task.campaign_id,
                current_user.id,
                "task_completed",
                f"Task '{task.title}' archived."
            )
            
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500


# ==========================================
# SPRINT 1: NOTES ENDPOINTS
# ==========================================

@main_bp.route('/api/notes/save', methods=['POST'])
@login_required
def save_note():
    from app.models import Note
    data = request.get_json() or request.form
    note_id = data.get('id')
    title = data.get('title', 'Untitled Note')
    body = data.get('body', '')
    project_id = data.get('project_id')
    campaign_id = data.get('campaign_id')
    
    try:
        if note_id:
            note = Note.query.get(int(note_id))
            if not note or note.user_id != current_user.id:
                return jsonify({"success": False, "error": "Unauthorized or not found"}), 403
            note.title = title
            note.body = body
        else:
            note = Note(
                user_id=current_user.id,
                title=title,
                body=body,
                project_id=int(project_id) if project_id else None,
                campaign_id=int(campaign_id) if campaign_id else None
            )
            db.session.add(note)
            
        db.session.commit()
        
        # Log timeline activity
        if note.campaign_id:
            from app.services.automation_engine import AutomationEngine
            AutomationEngine.log_activity(
                note.campaign_id,
                current_user.id,
                "note_added",
                f"Note '{note.title}' updated."
            )
            
        return jsonify({"success": True, "note_id": note.id})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500


@main_bp.route('/api/notes/search', methods=['GET'])
@login_required
def search_notes():
    from app.models import Note
    query = request.args.get('q', '')
    campaign_id = request.args.get('campaign_id')
    
    notes_query = Note.query.filter_by(user_id=current_user.id)
    if campaign_id:
        notes_query = notes_query.filter_by(campaign_id=int(campaign_id))
    if query:
        notes_query = notes_query.filter(Note.title.contains(query) | Note.body.contains(query))
        
    notes = notes_query.all()
    return jsonify({
        "success": True,
        "notes": [{"id": n.id, "title": n.title, "body": n.body, "updated_at": n.updated_at.strftime('%Y-%m-%d %H:%M')} for n in notes]
    })


# ==========================================
# SPRINT 1: REPORTS ENDPOINTS
# ==========================================

@main_bp.route('/api/reports/new', methods=['POST'])
@login_required
def create_report():
    from app.models import Report, Campaign, Task, Content
    data = request.get_json() or request.form
    title = data.get('title')
    project_id = data.get('project_id')
    campaign_id = data.get('campaign_id')
    
    if not title:
        return jsonify({"success": False, "error": "Report title is required"}), 400
        
    # Auto-generate report markdown text
    content_markdown = f"# Performance Report: {title}\n"
    content_markdown += f"Generated on {datetime.utcnow().strftime('%B %d, %Y')}\n\n"
    
    if campaign_id:
        campaign = Campaign.query.get(int(campaign_id))
        if campaign:
            content_markdown += f"## Campaign Overview\n"
            content_markdown += f"- **Name**: {campaign.name}\n"
            content_markdown += f"- **Type**: {campaign.type.replace('_', ' ').capitalize()}\n"
            from app.utils.currency import format_money
            content_markdown += f"- **Budget**: {format_money(campaign.budget, getattr(campaign, 'currency', None))}\n"
            content_markdown += f"- **Timeline**: {campaign.get_timeline_label()}\n"
            content_markdown += f"- **Status**: {campaign.status.upper()}\n\n"
            
            # Tasks checklist progress
            tasks = Task.query.filter_by(campaign_id=campaign.id, is_archived=False).all()
            content_markdown += f"## Tasks Checklist Progress\n"
            if tasks:
                for t in tasks:
                    status_symbol = "[x]" if t.status == 'completed' else "[ ]"
                    content_markdown += f"- {status_symbol} **{t.title}** (Priority: {t.priority.upper()})\n"
            else:
                content_markdown += f"*No tasks defined for this campaign.*\n"
            content_markdown += "\n"
            
            # Copywriting assets summary
            contents = Content.query.filter_by(campaign_id=campaign.id).all()
            content_markdown += f"## AI Copywriting Assets\n"
            if contents:
                for c in contents:
                    content_markdown += f"- **{c.title}** ({c.type.replace('_', ' ').capitalize()}) - *{c.status.capitalize()}*\n"
            else:
                content_markdown += f"*No copywriting assets generated for this campaign.*\n"
    else:
        content_markdown += "## Overview\nThis is a manual performance summary report compiled for client review.\n"
        
    new_report = Report(
        user_id=current_user.id,
        title=title,
        content_markdown=content_markdown,
        project_id=int(project_id) if project_id else None,
        campaign_id=int(campaign_id) if campaign_id else None
    )
    
    try:
        db.session.add(new_report)
        db.session.commit()
        
        # Log timeline activity
        if new_report.campaign_id:
            from app.services.automation_engine import AutomationEngine
            AutomationEngine.log_activity(
                new_report.campaign_id,
                current_user.id,
                "report_generated",
                f"Report compiled: '{new_report.title}'."
            )
            
        return jsonify({
            "success": True,
            "report": {
                "id": new_report.id,
                "title": new_report.title,
                "content_markdown": new_report.content_markdown
            }
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500


@main_bp.route('/api/reports/export/<int:report_id>', methods=['GET'])
@login_required
def export_report_pdf(report_id):
    from app.models import Report
    from app.services.pdf_service import PDFService
    from flask import send_file, current_app
    
    report = Report.query.get_or_404(report_id)
    if report.user_id != current_user.id:
        abort(403)
        
    try:
        pdf_buffer = PDFService.generate_report_pdf(report)
        filename = f"report_{report.id}_{datetime.utcnow().strftime('%Y%m%d')}.pdf"
        return send_file(
            pdf_buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        current_app.logger.error(f"Report PDF Compilation Error: {str(e)}")
        flash('An error occurred during report PDF compilation.', 'danger')
        return redirect(url_for('main.index'))


