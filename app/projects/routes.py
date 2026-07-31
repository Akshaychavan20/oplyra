from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Project, AnalyticsLog

projects_bp = Blueprint('projects', __name__)

@projects_bp.route('/', methods=['GET'])
@login_required
def projects_status():
    """Lists all projects (Clients) owned by the current user with folders, search, and pagination."""
    query = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = 12
    sort = (request.args.get('sort') or 'updated').strip().lower()
    
    # organization filters
    folder_id = request.args.get('folder_id', type=int)
    favorites_only = request.args.get('favorites', '').strip().lower() in ['true', '1']
    archived_only = request.args.get('archived', '').strip().lower() in ['true', '1']
    pinned_only = request.args.get('pinned', '').strip().lower() in ['true', '1']
    
    projects_query = Project.query.filter_by(user_id=current_user.id)
    
    if favorites_only:
        projects_query = projects_query.filter(Project.is_favorite == True)
        
    if archived_only:
        projects_query = projects_query.filter(Project.is_archived == True)
    else:
        # Default: hide archived clients unless explicitly requested
        projects_query = projects_query.filter(Project.is_archived == False)
        
    if pinned_only:
        projects_query = projects_query.filter(Project.is_pinned == True)
        
    if folder_id:
        projects_query = projects_query.filter(Project.folder_id == folder_id)
        
    if query:
        projects_query = projects_query.filter(
            Project.name.contains(query) | Project.description.contains(query)
        )
        
    # Sort pinned items to the very top, then by requested sort
    if sort == 'name':
        projects_query = projects_query.order_by(Project.is_pinned.desc(), Project.name.asc())
    elif sort == 'name_desc':
        projects_query = projects_query.order_by(Project.is_pinned.desc(), Project.name.desc())
    elif sort == 'created':
        projects_query = projects_query.order_by(Project.is_pinned.desc(), Project.created_at.desc())
    else:
        sort = 'updated'
        projects_query = projects_query.order_by(Project.is_pinned.desc(), Project.updated_at.desc())
        
    pagination = projects_query.paginate(page=page, per_page=per_page, error_out=False)
    projects = pagination.items
    
    from app.models import ProjectFolder
    folders = ProjectFolder.query.filter_by(user_id=current_user.id).order_by(ProjectFolder.name.asc()).all()
    
    return render_template(
        'projects/list.html', 
        projects=projects, 
        pagination=pagination, 
        search_query=query,
        folders=folders,
        selected_folder=folder_id,
        favorites_only=favorites_only,
        archived_only=archived_only,
        pinned_only=pinned_only,
        sort=sort,
    )


@projects_bp.route('/', methods=['POST'])
@projects_bp.route('/new', methods=['POST'])
@login_required
def create_project():
    """Creates a new project workspace."""
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()
    
    if not name:
        flash('Client name is required.', 'danger')
        return redirect(url_for('projects.projects_status'))
        
    new_project = Project(user_id=current_user.id, name=name, description=description)
    
    try:
        db.session.add(new_project)
        db.session.commit()
        
        # Log the project creation activity
        log = AnalyticsLog(user_id=current_user.id, activity_type='create_project')
        db.session.add(log)
        db.session.commit()
        
        flash(f'Client "{name}" created successfully!', 'success')
        return redirect(url_for('projects.view_project', project_id=new_project.id))
    except Exception as e:
        db.session.rollback()
        flash('An error occurred while creating the client. Please try again.', 'danger')
        return redirect(url_for('projects.projects_status'))


@projects_bp.route('/<int:project_id>', methods=['GET'])
@login_required
def view_project(project_id):
    """Views a specific project workspace and lists its contents."""
    project = Project.query.get_or_404(project_id)
    
    # Ownership authorization check
    if project.user_id != current_user.id:
        abort(403)
        
    from app.models import Campaign, Task, Note, Report, Asset, KnowledgeDocument, AgentRun
    campaigns = Campaign.query.filter_by(project_id=project_id).order_by(Campaign.created_at.desc()).all()
    tasks = Task.query.filter_by(project_id=project_id, is_archived=False).order_by(Task.due_date.asc()).all()
    notes = Note.query.filter_by(project_id=project_id).order_by(Note.updated_at.desc()).all()
    reports = Report.query.filter_by(project_id=project_id).order_by(Report.updated_at.desc()).all()
    
    # Get user org to fetch uploaded files/assets (DAM is org-scoped — no project_id on Asset)
    membership = current_user.memberships[0] if current_user.memberships else None
    org_id = membership.organization_id if membership else None
    assets = (
        Asset.query.filter_by(organization_id=org_id).order_by(Asset.created_at.desc()).limit(24).all()
        if org_id else []
    )

    # Client-scoped knowledge + AI activity (existing models only)
    knowledge_docs = (
        KnowledgeDocument.query.filter_by(project_id=project_id)
        .order_by(KnowledgeDocument.id.desc())
        .limit(12)
        .all()
    )
    agent_runs = (
        AgentRun.query.filter_by(project_id=project_id, user_id=current_user.id)
        .order_by(AgentRun.created_at.desc())
        .limit(12)
        .all()
    )

    # Lightweight activity timeline from existing related records (no new tables)
    timeline = []
    for camp in campaigns[:8]:
        timeline.append({
            'kind': 'campaign',
            'title': camp.name,
            'meta': (camp.status or 'campaign').replace('_', ' '),
            'at': camp.created_at,
            'href': url_for('content.campaign_workspace', campaign_id=camp.id),
        })
    for content in (project.contents or [])[:8]:
        timeline.append({
            'kind': 'content',
            'title': content.title,
            'meta': (content.type or 'content').replace('_', ' '),
            'at': getattr(content, 'generated_at', None) or getattr(content, 'created_at', None),
            'href': url_for('content.view_content', content_id=content.id) if hasattr(content, 'id') else '#',
        })
    for rep in reports[:6]:
        timeline.append({
            'kind': 'report',
            'title': getattr(rep, 'title', None) or f'Report #{rep.id}',
            'meta': 'report',
            'at': rep.updated_at or rep.created_at,
            'href': '#tab-reports',
        })
    for run in agent_runs[:6]:
        goal = ''
        try:
            import json as _json
            payload = _json.loads(run.input_json or '{}')
            goal = (payload.get('goal') or '')[:80]
        except Exception:
            goal = run.mode or 'AI workflow'
        timeline.append({
            'kind': 'ai',
            'title': goal or f'AI run #{run.id}',
            'meta': run.status or 'ai',
            'at': run.created_at,
            'href': url_for('main.index', project_id=project_id) + '#agents',
        })
    timeline = [t for t in timeline if t.get('at')]
    timeline.sort(key=lambda t: t['at'], reverse=True)
    timeline = timeline[:16]
    
    from app.models import ProjectFolder
    folders = ProjectFolder.query.filter_by(user_id=current_user.id).order_by(ProjectFolder.name.asc()).all()
    
    return render_template(
        'projects/detail.html', 
        project=project, 
        contents=project.contents,
        campaigns=campaigns,
        tasks=tasks,
        notes=notes,
        reports=reports,
        assets=assets,
        folders=folders,
        knowledge_docs=knowledge_docs,
        agent_runs=agent_runs,
        timeline=timeline,
    )


@projects_bp.route('/<int:project_id>/edit', methods=['POST'])
@login_required
def edit_project(project_id):
    """Edits project workspace details (name and description)."""
    project = Project.query.get_or_404(project_id)
    
    # Ownership authorization check
    if project.user_id != current_user.id:
        abort(403)
        
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()
    folder_id = request.form.get('folder_id')
    
    if not name:
        flash('Client name cannot be empty.', 'danger')
        return redirect(url_for('projects.view_project', project_id=project.id))
        
    try:
        project.name = name
        project.description = description
        if folder_id and folder_id.strip() != "":
            project.folder_id = int(folder_id)
        else:
            project.folder_id = None
        db.session.commit()
        
        # Log project update
        log = AnalyticsLog(user_id=current_user.id, activity_type='edit_project')
        db.session.add(log)
        db.session.commit()
        
        flash('Client details updated successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash('An error occurred while saving client modifications.', 'danger')
        
    return redirect(url_for('projects.view_project', project_id=project.id))


@projects_bp.route('/<int:project_id>/delete', methods=['POST'])
@login_required
def delete_project(project_id):
    """Deletes a specific project workspace, cascading to delete all stored contents."""
    project = Project.query.get_or_404(project_id)
    
    # Ownership authorization check
    if project.user_id != current_user.id:
        abort(403)
        
    name = project.name
    try:
        db.session.delete(project)
        db.session.commit()
        
        # Log project deletion
        log = AnalyticsLog(user_id=current_user.id, activity_type='delete_project')
        db.session.add(log)
        db.session.commit()
        
        flash(f'Client "{name}" has been deleted.', 'info')
    except Exception as e:
        db.session.rollback()
        flash('An error occurred while deleting the client.', 'danger')
        
    return redirect(url_for('projects.projects_status'))


# ==========================================
# SPRINT 3: PROJECT ORGANIZATION ENDPOINTS
# ==========================================

@projects_bp.route('/folders/new', methods=['POST'])
@login_required
def create_folder():
    """Creates a new ProjectFolder category."""
    from app.models import ProjectFolder
    name = request.form.get('name', '').strip()
    if not name:
        flash('Folder name is required.', 'danger')
        return redirect(url_for('projects.projects_status'))
        
    try:
        folder = ProjectFolder(user_id=current_user.id, name=name)
        db.session.add(folder)
        db.session.commit()
        flash(f'Folder "{name}" created successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Failed to create folder.', 'danger')
        
    return redirect(url_for('projects.projects_status'))


@projects_bp.route('/folders/<int:folder_id>/delete', methods=['POST'])
@login_required
def delete_folder(folder_id):
    """Deletes a folder, releasing all contained projects (setting their folder_id = null)."""
    from app.models import ProjectFolder
    folder = ProjectFolder.query.get_or_404(folder_id)
    if folder.user_id != current_user.id:
        abort(403)
        
    try:
        # Clear folder references on children projects
        for project in folder.projects:
            project.folder_id = None
        db.session.delete(folder)
        db.session.commit()
        flash('Folder removed successfully.', 'info')
    except Exception as e:
        db.session.rollback()
        flash('Failed to delete folder.', 'danger')
        
    return redirect(url_for('projects.projects_status'))


@projects_bp.route('/<int:project_id>/move-to-folder', methods=['POST'])
@login_required
def move_project_to_folder(project_id):
    """Assigns a project workspace to a folder category."""
    from app.models import ProjectFolder
    project = Project.query.get_or_404(project_id)
    if project.user_id != current_user.id:
        abort(403)
        
    folder_id = request.form.get('folder_id')
    
    try:
        if folder_id:
            folder = ProjectFolder.query.get(int(folder_id))
            if not folder or folder.user_id != current_user.id:
                abort(403)
            project.folder_id = folder.id
        else:
            project.folder_id = None
            
        db.session.commit()
        flash('Workspace location updated.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Failed to update workspace folder.', 'danger')
        
    return redirect(url_for('projects.view_project', project_id=project.id))


@projects_bp.route('/<int:project_id>/toggle-pin', methods=['POST'])
@login_required
def toggle_pin(project_id):
    """Toggles pinning status for rapid home access."""
    project = Project.query.get_or_404(project_id)
    if project.user_id != current_user.id:
        return jsonify({"success": False, "error": "Unauthorized"}), 403
        
    try:
        project.is_pinned = not project.is_pinned
        db.session.commit()
        return jsonify({"success": True, "is_pinned": project.is_pinned})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500


@projects_bp.route('/<int:project_id>/toggle-favorite', methods=['POST'])
@login_required
def toggle_favorite(project_id):
    """Toggles favorite status."""
    project = Project.query.get_or_404(project_id)
    if project.user_id != current_user.id:
        return jsonify({"success": False, "error": "Unauthorized"}), 403
        
    try:
        project.is_favorite = not project.is_favorite
        db.session.commit()
        return jsonify({"success": True, "is_favorite": project.is_favorite})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500


@projects_bp.route('/<int:project_id>/toggle-archive', methods=['POST'])
@login_required
def toggle_archive(project_id):
    """Toggles archived status."""
    project = Project.query.get_or_404(project_id)
    if project.user_id != current_user.id:
        return jsonify({"success": False, "error": "Unauthorized"}), 403
        
    try:
        project.is_archived = not project.is_archived
        db.session.commit()
        return jsonify({"success": True, "is_archived": project.is_archived})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500


@projects_bp.route('/<int:project_id>/duplicate', methods=['POST'])
@login_required
def duplicate_project(project_id):
    """Duplicates a project workspace, copying campaigns, content, tasks, and notes recursively."""
    project = Project.query.get_or_404(project_id)
    if project.user_id != current_user.id:
        abort(403)
        
    try:
        from app.models import Campaign, Task, Note, Content, SEOAnalysis
        
        # 1. Duplicate Project root
        new_project = Project(
            user_id=current_user.id,
            name=f"Copy of {project.name}",
            description=project.description,
            folder_id=project.folder_id,
            is_favorite=project.is_favorite,
            category=project.category,
            tags=project.tags
        )
        db.session.add(new_project)
        db.session.flush()  # Populates new_project.id
        
        campaign_map = {}
        
        # 2. Duplicate Campaigns
        for camp in project.campaigns:
            new_camp = Campaign(
                project_id=new_project.id,
                organization_id=camp.organization_id,
                name=camp.name,
                type=camp.type,
                description=camp.description,
                status=camp.status,
                start_date=camp.start_date,
                end_date=camp.end_date
            )
            db.session.add(new_camp)
            db.session.flush()
            campaign_map[camp.id] = new_camp.id
            
        # 3. Duplicate Contents & SEO Reviews
        for cnt in project.contents:
            new_cnt = Content(
                project_id=new_project.id,
                campaign_id=campaign_map.get(cnt.campaign_id) if cnt.campaign_id else None,
                organization_id=cnt.organization_id,
                title=cnt.title,
                body=cnt.body,
                type=cnt.type,
                prompt_used=cnt.prompt_used,
                status=cnt.status,
                is_favorite=cnt.is_favorite
            )
            db.session.add(new_cnt)
            db.session.flush()
            
            if cnt.seo_analysis:
                new_seo = SEOAnalysis(
                    content_id=new_cnt.id,
                    seo_score=cnt.seo_analysis.seo_score,
                    readability_score=cnt.seo_analysis.readability_score,
                    keywords_found=cnt.seo_analysis.keywords_found,
                    suggestions=cnt.seo_analysis.suggestions,
                    _details=cnt.seo_analysis._details
                )
                db.session.add(new_seo)
                
        # 4. Duplicate Tasks
        for tsk in project.tasks:
            new_tsk = Task(
                user_id=current_user.id,
                project_id=new_project.id,
                campaign_id=campaign_map.get(tsk.campaign_id) if tsk.campaign_id else None,
                title=tsk.title,
                description=tsk.description,
                status=tsk.status,
                priority=tsk.priority,
                due_date=tsk.due_date,
                is_archived=tsk.is_archived
            )
            db.session.add(new_tsk)
            
        # 5. Duplicate Notes
        for nt in project.notes:
            new_nt = Note(
                user_id=current_user.id,
                project_id=new_project.id,
                campaign_id=campaign_map.get(nt.campaign_id) if nt.campaign_id else None,
                title=nt.title,
                body=nt.body
            )
            db.session.add(new_nt)
            
        db.session.commit()
        flash(f'Successfully duplicated workspace into "{new_project.name}"!', 'success')
        return redirect(url_for('projects.view_project', project_id=new_project.id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'An error occurred during duplication: {str(e)}', 'danger')
        return redirect(url_for('projects.view_project', project_id=project.id))

