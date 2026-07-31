from datetime import datetime
import json
from flask_login import UserMixin
from sqlalchemy.dialects.mysql import LONGTEXT
from app import db, bcrypt

class User(db.Model, UserMixin):
    """User Model for representing registered platform users."""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False, index=True)
    email = db.Column(db.String(100), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    projects = db.relationship('Project', backref='owner', lazy=True, cascade='all, delete-orphan')
    analytics_logs = db.relationship('AnalyticsLog', backref='user', lazy=True, cascade='all, delete-orphan')
    memberships = db.relationship('Membership', backref='user', lazy=True, cascade='all, delete-orphan')
    audit_logs = db.relationship('AuditLog', backref='user', lazy=True, cascade='all, delete-orphan')

    def set_password(self, password):
        """Hashes the password using Bcrypt and stores it."""
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        """Checks the hashed password against the candidate password."""
        return bcrypt.check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.username}>"


class PasswordResetToken(db.Model):
    """Stores hashed, single-use password reset tokens with expiry (OWASP).

    The raw token is emailed to the user and never persisted — only SHA-256
    of the token is stored in ``token_hash``.
    """
    __tablename__ = 'password_reset_tokens'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    token_hash = db.Column(db.String(64), unique=True, nullable=False, index=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False, nullable=False)
    used_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(512), nullable=True)

    # Relationship to user
    user = db.relationship('User', backref=db.backref('reset_tokens', lazy=True, cascade='all, delete-orphan'))

    def mark_used(self):
        """Invalidate this token (single-use)."""
        self.used = True
        self.used_at = datetime.utcnow()

    @property
    def is_expired(self):
        return self.expires_at < datetime.utcnow()

    @property
    def is_valid(self):
        return (not self.used) and (not self.is_expired)

    def __repr__(self):
        return f"<PasswordResetToken UserID: {self.user_id} hash={self.token_hash[:10]}...>"


class AuthSecurityLog(db.Model):
    """Security audit trail for authentication events (password reset, etc.)."""
    __tablename__ = 'auth_security_logs'

    id = db.Column(db.Integer, primary_key=True)
    event_type = db.Column(db.String(80), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(512), nullable=True)
    details = db.Column(db.Text, nullable=True)  # JSON string — never store passwords/tokens
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f"<AuthSecurityLog {self.event_type} user={self.user_id}>"


class Organization(db.Model):
    """Organization Model to support SaaS team multi-tenancy."""
    __tablename__ = 'organizations'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    plan_tier = db.Column(db.String(50), default='free') # free, pro, agency, enterprise
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    memberships = db.relationship('Membership', backref='organization', lazy=True, cascade='all, delete-orphan')
    social_accounts = db.relationship('SocialAccount', backref='organization', lazy=True, cascade='all, delete-orphan')
    campaigns = db.relationship('Campaign', backref='organization', lazy=True, cascade='all, delete-orphan')
    contents = db.relationship('Content', backref='organization', lazy=True, cascade='all, delete-orphan')
    workflow_definitions = db.relationship('WorkflowDefinition', backref='organization', lazy=True, cascade='all, delete-orphan')
    audit_logs = db.relationship('AuditLog', backref='organization', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f"<Organization {self.name}>"


class Membership(db.Model):
    """Membership Model mapping user-to-organization roles (RBAC)."""
    __tablename__ = 'memberships'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    role = db.Column(db.String(50), default='content_writer') # admin, manager, editor, content_writer, designer, client
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('organization_id', 'user_id', name='unique_org_user'),)

    def __repr__(self):
        return f"<Membership OrgID: {self.organization_id} UserID: {self.user_id} Role: {self.role}>"


class ProjectFolder(db.Model):
    """ProjectFolder Model to organize projects/clients into folders."""
    __tablename__ = 'project_folders'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    projects = db.relationship('Project', backref='folder', lazy=True)

    def __repr__(self):
        return f"<ProjectFolder {self.name} (User ID: {self.user_id})>"


class Project(db.Model):
    """Project Model for categorizing generated contents into client or campaign folders."""
    __tablename__ = 'projects'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    folder_id = db.Column(db.Integer, db.ForeignKey('project_folders.id', ondelete='SET NULL'), nullable=True)
    is_favorite = db.Column(db.Boolean, default=False, nullable=False)
    is_pinned = db.Column(db.Boolean, default=False, nullable=False)
    is_archived = db.Column(db.Boolean, default=False, nullable=False)
    category = db.Column(db.String(100), nullable=True)
    tags = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    contents = db.relationship('Content', backref='project', lazy=True, cascade='all, delete-orphan')
    campaigns = db.relationship('Campaign', backref='project', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f"<Project {self.name} (User ID: {self.user_id})>"


class Campaign(db.Model):
    """Campaign Model to manage marketing operations and track budgets."""
    __tablename__ = 'campaigns'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id', ondelete='CASCADE'), nullable=True)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(50), nullable=False) # affiliate, product_launch, email, social_campaign
    description = db.Column(db.Text, nullable=True)
    budget = db.Column(db.Numeric(12, 2), default=0.00)
    currency = db.Column(db.String(3), nullable=False, default='INR')
    start_date = db.Column(db.DateTime, nullable=True)
    end_date = db.Column(db.DateTime, nullable=True)
    # Timeline duration: fixed | ongoing | recurring
    duration_type = db.Column(db.String(20), nullable=False, default='fixed')
    # Recurrence cadence when duration_type == recurring: daily|weekly|monthly|quarterly|yearly
    recurrence = db.Column(db.String(20), nullable=True)
    status = db.Column(db.String(50), default='draft') # draft, active, paused, completed
    current_stage = db.Column(db.String(50), default='Onboarding') # Onboarding, Planning, Execution, Monitoring, Reporting, Completed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    contents = db.relationship('Content', backref='campaign', lazy=True, cascade='all, delete-orphan')

    def get_timeline_label(self):
        """Human-readable timeline for cards and summaries."""
        start = self.start_date.strftime('%b %d, %Y') if self.start_date else '—'
        dtype = (self.duration_type or 'fixed').lower()
        if dtype == 'ongoing':
            return f'{start} – Ongoing'
        if dtype == 'recurring':
            cadence = (self.recurrence or 'weekly').replace('_', ' ').title()
            if self.end_date:
                return f'{start} – {self.end_date.strftime("%b %d, %Y")} · {cadence}'
            return f'{start} – Recurring ({cadence})'
        end = self.end_date.strftime('%b %d, %Y') if self.end_date else '—'
        return f'{start} – {end}'

    def get_stage_progress(self, stage_name):
        total = len([item for item in self.lifecycle_items if item.stage.lower() == stage_name.lower()])
        if total == 0:
            return 0
        completed = len([item for item in self.lifecycle_items if item.stage.lower() == stage_name.lower() and item.is_completed])
        return int((completed / total) * 100)
        
    def get_overall_progress(self):
        total = len(self.lifecycle_items)
        if total == 0:
            return 0
        completed = len([item for item in self.lifecycle_items if item.is_completed])
        return int((completed / total) * 100)

    def __repr__(self):
        return f"<Campaign {self.name} (Type: {self.type})>"


class CampaignLifecycleItem(db.Model):
    """CampaignLifecycleItem tracks checklist status per stage."""
    __tablename__ = 'campaign_lifecycle_items'
    
    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id', ondelete='CASCADE'), nullable=False)
    stage = db.Column(db.String(50), nullable=False) # Onboarding, Planning, Execution, Monitoring, Reporting, Completed
    name = db.Column(db.String(100), nullable=False)
    is_completed = db.Column(db.Boolean, default=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    campaign = db.relationship('Campaign', backref=db.backref('lifecycle_items', lazy=True, cascade='all, delete-orphan'))
    
    def __repr__(self):
        return f"<CampaignLifecycleItem {self.name} of Campaign {self.campaign_id}: {self.is_completed}>"


class Content(db.Model):
    """Content Model for tracking blog posts, emails, social media posts, and reviews."""
    __tablename__ = 'contents'

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id', ondelete='SET NULL'), nullable=True)
    type = db.Column(db.String(50), nullable=False)  # blog_post, seo_article, product_review, email_campaign, ad_copy, social_caption, landing_page, image, carousel, video
    title = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text().with_variant(LONGTEXT, "mysql"), nullable=False)  # Multi-dialect database support (SQLite/MySQL)
    prompt_used = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='draft', nullable=False)  # draft, review_pending, approved, rejected, archived
    is_favorite = db.Column(db.Boolean, default=False, nullable=False)
    generated_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    seo_analysis = db.relationship('SEOAnalysis', backref='content', uselist=False, lazy=True, cascade='all, delete-orphan')
    carousel_slides = db.relationship('CarouselSlide', backref='content', lazy=True, cascade='all, delete-orphan')
    social_posts = db.relationship('SocialPost', backref='content', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f"<Content {self.title} (Type: {self.type})>"


class CarouselSlide(db.Model):
    """CarouselSlide Model containing slides settings for multi-frame social shares (LinkedIn/IG)."""
    __tablename__ = 'carousel_slides'

    id = db.Column(db.Integer, primary_key=True)
    content_id = db.Column(db.Integer, db.ForeignKey('contents.id', ondelete='CASCADE'), nullable=False)
    slide_order = db.Column(db.Integer, nullable=False)
    slide_text = db.Column(db.Text, nullable=True)
    media_url = db.Column(db.String(512), nullable=True)
    _layout_config = db.Column('layout_config', db.Text, nullable=True) # Stored JSON config

    @property
    def layout_config(self):
        try:
            return json.loads(self._layout_config) if self._layout_config else {}
        except (ValueError, TypeError):
            return {}

    @layout_config.setter
    def layout_config(self, val):
        self._layout_config = json.dumps(val)

    def __repr__(self):
        return f"<CarouselSlide Content ID: {self.content_id} Order: {self.slide_order}>"


class SocialAccount(db.Model):
    """SocialAccount Model storing credentials and status for external platform APIs."""
    __tablename__ = 'social_accounts'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False)
    platform = db.Column(db.String(50), nullable=False) # facebook, instagram, linkedin, twitter, pinterest, youtube, tiktok
    platform_account_id = db.Column(db.String(255), nullable=False)
    account_name = db.Column(db.String(255), nullable=False)
    encrypted_access_token = db.Column(db.LargeBinary, nullable=False)
    encrypted_refresh_token = db.Column(db.LargeBinary, nullable=True)
    token_expires_at = db.Column(db.DateTime, nullable=True)
    _account_metadata = db.Column('account_metadata', db.Text, nullable=True) # JSON account data

    # Relationships
    social_posts = db.relationship('SocialPost', backref='social_account', lazy=True, cascade='all, delete-orphan')

    @property
    def account_metadata(self):
        try:
            return json.loads(self._account_metadata) if self._account_metadata else {}
        except (ValueError, TypeError):
            return {}

    @account_metadata.setter
    def account_metadata(self, val):
        self._account_metadata = json.dumps(val)

    @property
    def access_token(self):
        """Decrypts the access token from the database (fail-closed)."""
        if not self.encrypted_access_token:
            return ""
        from app.integrations.token_vault import decrypt_token
        return decrypt_token(self.encrypted_access_token)

    @access_token.setter
    def access_token(self, value):
        """Encrypts the access token before storing in database (fail-closed)."""
        if not value:
            self.encrypted_access_token = b""
            return
        from app.integrations.token_vault import encrypt_token
        self.encrypted_access_token = encrypt_token(value)

    def __repr__(self):
        return f"<SocialAccount Platform: {self.platform} Account: {self.account_name}>"


class SocialPost(db.Model):
    """SocialPost Model tracking status of publishing queues and external IDs."""
    __tablename__ = 'social_posts'

    id = db.Column(db.Integer, primary_key=True)
    content_id = db.Column(db.Integer, db.ForeignKey('contents.id', ondelete='CASCADE'), nullable=False)
    social_account_id = db.Column(db.Integer, db.ForeignKey('social_accounts.id', ondelete='CASCADE'), nullable=False)
    scheduled_at = db.Column(db.DateTime, nullable=False)
    published_at = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(50), default='scheduled') # scheduled, publishing, published, failed, cancelled
    external_post_id = db.Column(db.String(255), nullable=True)
    failure_reason = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    analytics_metrics = db.relationship('AnalyticsMetrics', backref='social_post', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f"<SocialPost ID: {self.id} Status: {self.status}>"


class WorkflowDefinition(db.Model):
    """WorkflowDefinition Model containing event triggers and sequential automated marketing plans."""
    __tablename__ = 'workflow_definitions'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    trigger_event = db.Column(db.String(100), nullable=False) # blog_post_created, affiliate_product_added
    _trigger_config = db.Column('trigger_config', db.Text, nullable=True)
    _actions_sequence = db.Column('actions_sequence', db.Text, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    workflow_runs = db.relationship('WorkflowRun', backref='workflow_definition', lazy=True, cascade='all, delete-orphan')

    @property
    def trigger_config(self):
        try:
            return json.loads(self._trigger_config) if self._trigger_config else {}
        except (ValueError, TypeError):
            return {}

    @trigger_config.setter
    def trigger_config(self, val):
        self._trigger_config = json.dumps(val)

    @property
    def actions_sequence(self):
        try:
            return json.loads(self._actions_sequence) if self._actions_sequence else []
        except (ValueError, TypeError):
            return []

    @actions_sequence.setter
    def actions_sequence(self, val):
        self._actions_sequence = json.dumps(val)

    def __repr__(self):
        return f"<WorkflowDefinition {self.name} (Active: {self.is_active})>"


class WorkflowRun(db.Model):
    """WorkflowRun Model logging execution instance status."""
    __tablename__ = 'workflow_runs'

    id = db.Column(db.Integer, primary_key=True)
    workflow_definition_id = db.Column(db.Integer, db.ForeignKey('workflow_definitions.id', ondelete='CASCADE'), nullable=False)
    trigger_entity_id = db.Column(db.Integer, nullable=False) # ID of Content / Campaign / Product that triggered it
    status = db.Column(db.String(50), default='pending') # pending, running, success, failed
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f"<WorkflowRun Run ID: {self.id} Status: {self.status}>"


class AuditLog(db.Model):
    """AuditLog Model maintaining a full security and activity trail of user operations."""
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    action_type = db.Column(db.String(100), nullable=False) # generate, edit, publish, schedule, delete
    entity_type = db.Column(db.String(100), nullable=False) # contents, social_posts, campaigns
    entity_id = db.Column(db.Integer, nullable=False)
    _payload_diff = db.Column('payload_diff', db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def payload_diff(self):
        try:
            return json.loads(self._payload_diff) if self._payload_diff else {}
        except (ValueError, TypeError):
            return {}

    @payload_diff.setter
    def payload_diff(self, val):
        self._payload_diff = json.dumps(val)

    def __repr__(self):
        return f"<AuditLog User ID: {self.user_id} Action: {self.action_type}>"


class AnalyticsMetrics(db.Model):
    """AnalyticsMetrics Model tracking daily metrics snapshots for published posts."""
    __tablename__ = 'analytics_metrics'

    id = db.Column(db.Integer, primary_key=True)
    social_post_id = db.Column(db.Integer, db.ForeignKey('social_posts.id', ondelete='CASCADE'), nullable=False)
    impressions = db.Column(db.Integer, default=0)
    engagements = db.Column(db.Integer, default=0)
    clicks = db.Column(db.Integer, default=0)
    conversions = db.Column(db.Integer, default=0)
    revenue = db.Column(db.Numeric(12, 2), default=0.00)
    record_date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('social_post_id', 'record_date', name='unique_post_date_metrics'),)

    def __repr__(self):
        return f"<AnalyticsMetrics Post: {self.social_post_id} Date: {self.record_date}>"


class SEOAnalysis(db.Model):
    """SEOAnalysis Model for storing computed scores, readability index, and improvements recommendations."""
    __tablename__ = 'seo_analyses'

    id = db.Column(db.Integer, primary_key=True)
    content_id = db.Column(db.Integer, db.ForeignKey('contents.id', ondelete='CASCADE'), unique=True, nullable=False)
    seo_score = db.Column(db.Integer, nullable=False)  # Rating between 0-100
    readability_score = db.Column(db.Integer, nullable=False)  # Rating between 0-100
    _keywords_found = db.Column('keywords_found', db.Text, nullable=False)  # Handled via JSON getter/setter
    _suggestions = db.Column('suggestions', db.Text, nullable=False)        # Handled via JSON getter/setter
    _details = db.Column('details', db.Text, nullable=True)                 # Stored detailed stats JSON
    analyzed_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def keywords_found(self):
        """Gets target keywords dictionary from JSON string stored in db."""
        try:
            return json.loads(self._keywords_found)
        except (ValueError, TypeError):
            return {}

    @keywords_found.setter
    def keywords_found(self, val):
        """Sets target keywords dictionary converted to JSON string."""
        self._keywords_found = json.dumps(val)

    @property
    def suggestions(self):
        """Gets suggestions list from JSON string stored in db."""
        try:
            return json.loads(self._suggestions)
        except (ValueError, TypeError):
            return []

    @suggestions.setter
    def suggestions(self, val):
        """Sets suggestions list converted to JSON string."""
        self._suggestions = json.dumps(val)

    @property
    def details(self):
        """Gets detailed SEO analysis metrics from JSON string stored in db."""
        try:
            return json.loads(self._details) if self._details else {}
        except (ValueError, TypeError):
            return {}

    @details.setter
    def details(self, val):
        """Sets detailed SEO analysis metrics converted to JSON string."""
        self._details = json.dumps(val)

    def __repr__(self):
        return f"<SEOAnalysis Content ID: {self.content_id} (Score: {self.seo_score})>"


class AnalyticsLog(db.Model):
    """AnalyticsLog Model to log individual platform actions and estimate token spending footprint."""
    __tablename__ = 'analytics_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    activity_type = db.Column(db.String(50), nullable=False)  # e.g., login, generate_blog, export_pdf
    token_usage = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<AnalyticsLog User ID: {self.user_id} (Activity: {self.activity_type})>"


# =========================================================================
# ENTERPRISE PLATFORM EXPANSIONS: DATABASE SCHEMAS
# =========================================================================

# 1. DAM: Digital Asset Management
class AssetFolder(db.Model):
    __tablename__ = 'asset_folders'
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('asset_folders.id', ondelete='SET NULL'), nullable=True)
    name = db.Column(db.String(100), nullable=False)
    path = db.Column(db.String(512), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    assets = db.relationship('Asset', backref='folder', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f"<AssetFolder {self.name} Path: {self.path}>"


# Association table for Asset Tagging (Many-to-Many)
assets_tags = db.Table('assets_tags_association',
    db.Column('asset_id', db.Integer, db.ForeignKey('assets.id', ondelete='CASCADE'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('asset_tags.id', ondelete='CASCADE'), primary_key=True)
)


class Asset(db.Model):
    __tablename__ = 'assets'
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False)
    folder_id = db.Column(db.Integer, db.ForeignKey('asset_folders.id', ondelete='SET NULL'), nullable=True)
    name = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.String(100), nullable=False)
    file_size = db.Column(db.BigInteger, nullable=False)
    s3_url = db.Column(db.String(512), nullable=False)
    current_version = db.Column(db.Integer, default=1)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    versions = db.relationship('AssetVersion', backref='asset', lazy=True, cascade='all, delete-orphan')
    tags = db.relationship('AssetTag', secondary=assets_tags, backref=db.backref('assets', lazy='dynamic'))

    def __repr__(self):
        return f"<Asset {self.name} Type: {self.file_type}>"


class AssetVersion(db.Model):
    __tablename__ = 'asset_versions'
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('assets.id', ondelete='CASCADE'), nullable=False)
    version_num = db.Column(db.Integer, nullable=False)
    file_size = db.Column(db.BigInteger, nullable=False)
    s3_url = db.Column(db.String(512), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<AssetVersion Asset: {self.asset_id} Num: {self.version_num}>"


class AssetTag(db.Model):
    __tablename__ = 'asset_tags'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)

    def __repr__(self):
        return f"<AssetTag {self.name}>"


# 2. Brand Kit System
class BrandKit(db.Model):
    __tablename__ = 'brand_kits'
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id', ondelete='CASCADE'), unique=True, nullable=False)
    logo_url = db.Column(db.String(512), nullable=True)
    font_header = db.Column(db.String(100), default='Inter')
    font_body = db.Column(db.String(100), default='Inter')
    brand_voice_description = db.Column(db.Text, nullable=True)
    _cta_style = db.Column('cta_style', db.Text, nullable=True) # JSON
    company_info = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    colors = db.relationship('BrandColor', backref='brand_kit', lazy=True, cascade='all, delete-orphan')

    @property
    def cta_style(self):
        try:
            return json.loads(self._cta_style) if self._cta_style else {}
        except (ValueError, TypeError):
            return {}

    @cta_style.setter
    def cta_style(self, val):
        self._cta_style = json.dumps(val)

    def __repr__(self):
        return f"<BrandKit Org ID: {self.organization_id}>"


class BrandColor(db.Model):
    __tablename__ = 'brand_colors'
    id = db.Column(db.Integer, primary_key=True)
    brand_kit_id = db.Column(db.Integer, db.ForeignKey('brand_kits.id', ondelete='CASCADE'), nullable=False)
    hex_value = db.Column(db.String(7), nullable=False)
    color_role = db.Column(db.String(50), nullable=False) # primary, secondary, accent, background

    def __repr__(self):
        return f"<BrandColor Hex: {self.hex_value} Role: {self.color_role}>"


# 3. Content Version Control
class ContentVersion(db.Model):
    __tablename__ = 'content_versions'
    id = db.Column(db.Integer, primary_key=True)
    content_id = db.Column(db.Integer, db.ForeignKey('contents.id', ondelete='CASCADE'), nullable=False)
    version_num = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text().with_variant(LONGTEXT, "mysql"), nullable=False)
    _prompt_used = db.Column('prompt_used', db.Text, nullable=True) # JSON
    status = db.Column(db.String(50), nullable=False)
    commit_message = db.Column(db.String(255), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def prompt_used(self):
        try:
            return json.loads(self._prompt_used) if self._prompt_used else {}
        except (ValueError, TypeError):
            return {}

    @prompt_used.setter
    def prompt_used(self, val):
        self._prompt_used = json.dumps(val)

    def __repr__(self):
        return f"<ContentVersion Content: {self.content_id} Num: {self.version_num}>"


# 5. Affiliate Marketing Engine
class AffiliateNetwork(db.Model):
    __tablename__ = 'affiliate_networks'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    encrypted_credentials = db.Column(db.LargeBinary, nullable=True)
    status = db.Column(db.String(50), default='active')

    products = db.relationship('AffiliateProduct', backref='network', lazy=True)

    @property
    def credentials(self):
        """Decrypts credentials from database (fail-closed)."""
        if not self.encrypted_credentials:
            return ""
        from app.integrations.token_vault import decrypt_token
        return decrypt_token(self.encrypted_credentials)

    @credentials.setter
    def credentials(self, value):
        """Encrypts credentials before database write (fail-closed)."""
        if not value:
            self.encrypted_credentials = b""
            return
        from app.integrations.token_vault import encrypt_token
        self.encrypted_credentials = encrypt_token(value)

    def __repr__(self):
        return f"<AffiliateNetwork {self.name}>"


class AffiliateProduct(db.Model):
    __tablename__ = 'affiliate_products'
    id = db.Column(db.Integer, primary_key=True)
    network_id = db.Column(db.Integer, db.ForeignKey('affiliate_networks.id', ondelete='SET NULL'), nullable=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False)
    external_product_id = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    price = db.Column(db.Numeric(12, 2), default=0.00)
    commission_rate = db.Column(db.Numeric(5, 2), default=0.00)
    image_url = db.Column(db.String(512), nullable=True)
    source_url = db.Column(db.String(512), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    links = db.relationship('AffiliateLink', backref='product', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f"<AffiliateProduct {self.name} Network ID: {self.network_id}>"


class AffiliateLink(db.Model):
    __tablename__ = 'affiliate_links'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('affiliate_products.id', ondelete='CASCADE'), nullable=False)
    raw_url = db.Column(db.String(512), nullable=False)
    tracking_code = db.Column(db.String(255), nullable=True)
    description = db.Column(db.Text, nullable=True)

    tracking_links = db.relationship('TrackingLink', backref='affiliate_link', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f"<AffiliateLink Product ID: {self.product_id}>"


class TrackingLink(db.Model):
    __tablename__ = 'tracking_links'
    id = db.Column(db.Integer, primary_key=True)
    affiliate_link_id = db.Column(db.Integer, db.ForeignKey('affiliate_links.id', ondelete='CASCADE'), nullable=False)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id', ondelete='SET NULL'), nullable=True)
    short_code = db.Column(db.String(100), unique=True, nullable=False)
    destination_url = db.Column(db.String(512), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    click_events = db.relationship('ClickEvent', backref='tracking_link', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f"<TrackingLink Code: {self.short_code}>"


class ClickEvent(db.Model):
    __tablename__ = 'click_events'
    id = db.Column(db.Integer, primary_key=True)
    tracking_link_id = db.Column(db.Integer, db.ForeignKey('tracking_links.id', ondelete='CASCADE'), nullable=False)
    referrer = db.Column(db.String(512), nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(512), nullable=True)
    click_time = db.Column(db.DateTime, default=datetime.utcnow)

    conversions = db.relationship('ConversionEvent', backref='click_event', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f"<ClickEvent Link ID: {self.tracking_link_id} Time: {self.click_time}>"


class ConversionEvent(db.Model):
    __tablename__ = 'conversion_events'
    id = db.Column(db.Integer, primary_key=True)
    click_event_id = db.Column(db.Integer, db.ForeignKey('click_events.id', ondelete='SET NULL'), nullable=True)
    external_transaction_id = db.Column(db.String(255), unique=True, nullable=True)
    status = db.Column(db.String(50), default='pending') # pending, approved, rejected
    conversion_time = db.Column(db.DateTime, default=datetime.utcnow)

    revenue_event = db.relationship('RevenueEvent', backref='conversion_event', uselist=False, lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f"<ConversionEvent External ID: {self.external_transaction_id} Status: {self.status}>"


class RevenueEvent(db.Model):
    __tablename__ = 'revenue_events'
    id = db.Column(db.Integer, primary_key=True)
    conversion_event_id = db.Column(db.Integer, db.ForeignKey('conversion_events.id', ondelete='CASCADE'), unique=True, nullable=False)
    sale_amount = db.Column(db.Numeric(12, 2), nullable=False)
    commission_amount = db.Column(db.Numeric(12, 2), nullable=False)
    currency = db.Column(db.String(3), default='USD')
    recorded_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<RevenueEvent Commission: {self.commission_amount} recorded: {self.recorded_at}>"


# 8. Approval Workflow
class ApprovalRequest(db.Model):
    __tablename__ = 'approval_requests'
    id = db.Column(db.Integer, primary_key=True)
    content_id = db.Column(db.Integer, db.ForeignKey('contents.id', ondelete='CASCADE'), nullable=False)
    requester_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    reviewer_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    status = db.Column(db.String(50), default='pending') # pending, approved, rejected
    notes = db.Column(db.Text, nullable=True)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    decided_at = db.Column(db.DateTime, nullable=True)

    comments = db.relationship('ApprovalComment', backref='approval_request', lazy=True, cascade='all, delete-orphan')

    # Establish manual backref in Content model or allow backref
    content_ref = db.relationship('Content', backref=db.backref('approval_requests', lazy=True, cascade='all, delete-orphan'))

    def __repr__(self):
        return f"<ApprovalRequest Content ID: {self.content_id} Status: {self.status}>"


class ApprovalComment(db.Model):
    __tablename__ = 'approval_comments'
    id = db.Column(db.Integer, primary_key=True)
    approval_request_id = db.Column(db.Integer, db.ForeignKey('approval_requests.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    comment_text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<ApprovalComment Request: {self.approval_request_id} User: {self.user_id}>"


# 9. SaaS Billing System
class Plan(db.Model):
    __tablename__ = 'plans'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False) # Free, Starter, Pro, Agency, Enterprise
    api_credits_limit = db.Column(db.Integer, nullable=False)
    storage_limit_bytes = db.Column(db.BigInteger, nullable=False)
    team_seats_limit = db.Column(db.Integer, nullable=False)
    price_monthly = db.Column(db.Numeric(12, 2), nullable=False)
    currency = db.Column(db.String(3), default='USD')

    subscriptions = db.relationship('Subscription', backref='plan', lazy=True)

    def __repr__(self):
        return f"<Plan {self.name} Price: {self.price_monthly}>"


class Subscription(db.Model):
    __tablename__ = 'subscriptions'
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id', ondelete='CASCADE'), unique=True, nullable=False)
    plan_id = db.Column(db.Integer, db.ForeignKey('plans.id'), nullable=False)
    stripe_subscription_id = db.Column(db.String(255), unique=True, nullable=True)
    status = db.Column(db.String(50), nullable=False) # active, past_due, canceled, unpaid
    current_period_start = db.Column(db.DateTime, nullable=False)
    current_period_end = db.Column(db.DateTime, nullable=False)

    invoices = db.relationship('Invoice', backref='subscription', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f"<Subscription Org ID: {self.organization_id} Status: {self.status}>"


class Invoice(db.Model):
    __tablename__ = 'invoices'
    id = db.Column(db.Integer, primary_key=True)
    subscription_id = db.Column(db.Integer, db.ForeignKey('subscriptions.id', ondelete='CASCADE'), nullable=False)
    stripe_invoice_id = db.Column(db.String(255), unique=True, nullable=True)
    amount_due = db.Column(db.Numeric(12, 2), nullable=False)
    amount_paid = db.Column(db.Numeric(12, 2), nullable=False)
    pdf_url = db.Column(db.String(512), nullable=True)
    invoice_date = db.Column(db.DateTime, default=datetime.utcnow)

    payments = db.relationship('Payment', backref='invoice', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f"<Invoice ID: {self.id} Stripe ID: {self.stripe_invoice_id}>"


class Payment(db.Model):
    __tablename__ = 'payments'
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id', ondelete='CASCADE'), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    status = db.Column(db.String(50), nullable=False) # succeeded, failed, refunded
    payment_date = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Payment Invoice: {self.invoice_id} status: {self.status}>"


class UsageTracking(db.Model):
    __tablename__ = 'usage_trackings'
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False)
    billing_period_start = db.Column(db.DateTime, nullable=False)
    billing_period_end = db.Column(db.DateTime, nullable=False)
    ai_credits_used = db.Column(db.Integer, default=0)
    storage_used_bytes = db.Column(db.BigInteger, default=0)
    api_calls_count = db.Column(db.Integer, default=0)

    # Establish backref on Organization model
    organization_ref = db.relationship('Organization', backref=db.backref('usage_trackings', lazy=True, cascade='all, delete-orphan'))

    def __repr__(self):
        return f"<UsageTracking Org ID: {self.organization_id} Period: {self.billing_period_start} - {self.billing_period_end}>"


class AIResponseCache(db.Model):
    """AIResponseCache Model to store prompt cache hashes and responses (SQL fallback)."""
    __tablename__ = 'ai_response_cache'

    id = db.Column(db.Integer, primary_key=True)
    prompt_hash = db.Column(db.String(64), unique=True, nullable=False, index=True)
    model_used = db.Column(db.String(50), nullable=False)
    response_text = db.Column(db.Text().with_variant(LONGTEXT, "mysql"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<AIResponseCache Hash: {self.prompt_hash} Model: {self.model_used}>"


class TokenBillingLog(db.Model):
    """TokenBillingLog Model to track granular input/output token counts and costs."""
    __tablename__ = 'token_billing_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    model_used = db.Column(db.String(50), nullable=False)
    input_tokens = db.Column(db.Integer, nullable=False, default=0)
    output_tokens = db.Column(db.Integer, nullable=False, default=0)
    calculated_cost = db.Column(db.Numeric(10, 6), nullable=False, default=0.000000)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<TokenBillingLog User: {self.user_id} Model: {self.model_used} Cost: {self.calculated_cost}>"

class UserRateLimit(db.Model):
    """UserRateLimit Model to track user monthly limits and token consumption."""
    __tablename__ = 'user_rate_limits'

    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    monthly_credits_limit = db.Column(db.Integer, nullable=False, default=50000)
    credits_used = db.Column(db.Integer, nullable=False, default=0)
    reset_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Establish relationship back to User
    user = db.relationship('User', backref=db.backref('rate_limit', uselist=False, cascade='all, delete-orphan'))

    def __repr__(self):
        return f"<UserRateLimit User: {self.user_id} Credits: {self.credits_used}/{self.monthly_credits_limit}>"


class AIProviderConfig(db.Model):
    """Admin-managed AI provider feature flags and metadata."""
    __tablename__ = 'ai_providers'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(40), unique=True, nullable=False, index=True)
    display_name = db.Column(db.String(100), nullable=False)
    is_enabled = db.Column(db.Boolean, default=True, nullable=False)
    is_experimental = db.Column(db.Boolean, default=False, nullable=False)
    priority = db.Column(db.Integer, default=100, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AIModelConfig(db.Model):
    """Catalog of AI models available for routing / UI pickers."""
    __tablename__ = 'ai_models'

    id = db.Column(db.Integer, primary_key=True)
    provider_code = db.Column(db.String(40), nullable=False, index=True)
    model_id = db.Column(db.String(120), unique=True, nullable=False)
    display_name = db.Column(db.String(120), nullable=False)
    is_enabled = db.Column(db.Boolean, default=True, nullable=False)
    supports_stream = db.Column(db.Boolean, default=True, nullable=False)
    supports_vision = db.Column(db.Boolean, default=False, nullable=False)
    input_cost_per_m = db.Column(db.Numeric(12, 6), default=0)
    output_cost_per_m = db.Column(db.Numeric(12, 6), default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class AIRoutingRule(db.Model):
    """Admin-customizable task ? provider preference chain (JSON list)."""
    __tablename__ = 'ai_routing_rules'

    id = db.Column(db.Integer, primary_key=True)
    task_type = db.Column(db.String(50), unique=True, nullable=False)
    provider_chain = db.Column(db.Text, nullable=False)  # JSON array of provider codes
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AIRequestLog(db.Model):
    """Detailed per-request AI usage / cost / latency log."""
    __tablename__ = 'ai_request_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    organization_id = db.Column(db.Integer, nullable=True, index=True)
    campaign_id = db.Column(db.Integer, nullable=True, index=True)
    provider = db.Column(db.String(40), nullable=False, index=True)
    model_used = db.Column(db.String(100), nullable=False)
    input_tokens = db.Column(db.Integer, default=0)
    output_tokens = db.Column(db.Integer, default=0)
    total_tokens = db.Column(db.Integer, default=0)
    latency_ms = db.Column(db.Integer, default=0)
    calculated_cost = db.Column(db.Numeric(12, 6), default=0)
    status = db.Column(db.String(30), default='success')
    error_message = db.Column(db.String(500), nullable=True)
    retry_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)


class UserAIPreference(db.Model):
    """Per-user AI preferences (Auto mode, creativity, streaming, etc.)."""
    __tablename__ = 'user_ai_preferences'

    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    preferred_provider = db.Column(db.String(40), default='auto', nullable=False)
    preferred_model = db.Column(db.String(120), nullable=True)
    creativity = db.Column(db.Float, default=0.7)  # maps to temperature
    response_length = db.Column(db.String(20), default='medium')  # short|medium|long
    language = db.Column(db.String(20), default='en')
    streaming_enabled = db.Column(db.Boolean, default=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('ai_preference', uselist=False, cascade='all, delete-orphan'))


class PromptTemplate(db.Model):
    """Reusable prompt templates for the AI pipeline."""
    __tablename__ = 'prompt_templates'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, nullable=True, index=True)
    name = db.Column(db.String(120), nullable=False)
    task_type = db.Column(db.String(50), nullable=True)
    system_prompt = db.Column(db.Text, nullable=True)
    user_prompt = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class WorkspaceAIContext(db.Model):
    """Lightweight workspace / campaign memory for context injection."""
    __tablename__ = 'workspace_ai_context'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, nullable=False, index=True)
    project_id = db.Column(db.Integer, nullable=True, index=True)
    campaign_id = db.Column(db.Integer, nullable=True, index=True)
    context_key = db.Column(db.String(80), nullable=False)
    context_value = db.Column(db.Text, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Task(db.Model):
    """Task Model for tracking campaign and client to-do checklists."""
    __tablename__ = 'tasks'

    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id', ondelete='CASCADE'), nullable=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id', ondelete='CASCADE'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    priority = db.Column(db.String(20), default='medium', nullable=False) # high, medium, low
    due_date = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), default='pending', nullable=False) # pending, in_progress, completed
    is_archived = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    campaign = db.relationship('Campaign', backref=db.backref('tasks', lazy=True, cascade='all, delete-orphan'))
    project = db.relationship('Project', backref=db.backref('tasks', lazy=True, cascade='all, delete-orphan'))
    user = db.relationship('User', backref=db.backref('tasks', lazy=True, cascade='all, delete-orphan'))

    def __repr__(self):
        return f"<Task {self.title} Status: {self.status}>"


class Note(db.Model):
    """Note Model for storing rich content/campaign notepad details."""
    __tablename__ = 'notes'

    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id', ondelete='CASCADE'), nullable=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id', ondelete='CASCADE'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    campaign = db.relationship('Campaign', backref=db.backref('notes', lazy=True, cascade='all, delete-orphan'))
    project = db.relationship('Project', backref=db.backref('notes', lazy=True, cascade='all, delete-orphan'))
    user = db.relationship('User', backref=db.backref('notes', lazy=True, cascade='all, delete-orphan'))

    def __repr__(self):
        return f"<Note {self.title}>"


class Report(db.Model):
    """Report Model storing compiled performance metrics and client briefs."""
    __tablename__ = 'reports'

    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id', ondelete='CASCADE'), nullable=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id', ondelete='CASCADE'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    content_markdown = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    campaign = db.relationship('Campaign', backref=db.backref('reports', lazy=True, cascade='all, delete-orphan'))
    project = db.relationship('Project', backref=db.backref('reports', lazy=True, cascade='all, delete-orphan'))
    user = db.relationship('User', backref=db.backref('reports', lazy=True, cascade='all, delete-orphan'))

    def __repr__(self):
        return f"<Report {self.title}>"


class AutomationRule(db.Model):
    """AutomationRule Model to manage simple rules for campaigns."""
    __tablename__ = 'automation_rules'

    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id', ondelete='CASCADE'), nullable=False)
    trigger_type = db.Column(db.String(100), nullable=False) # deadline_tomorrow, stage_start_reporting, campaign_completed
    action_type = db.Column(db.String(100), nullable=False)  # create_reminder, prepare_report_draft, suggest_archive
    is_enabled = db.Column(db.Boolean, default=True, nullable=False)

    campaign = db.relationship('Campaign', backref=db.backref('automation_rules', lazy=True, cascade='all, delete-orphan'))

    def __repr__(self):
        return f"<AutomationRule Campaign: {self.campaign_id} {self.trigger_type} -> {self.action_type}>"


class Reminder(db.Model):
    """Reminder Model to store context-specific notifications."""
    __tablename__ = 'reminders'

    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id', ondelete='CASCADE'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    context_text = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    campaign = db.relationship('Campaign', backref=db.backref('reminders', lazy=True, cascade='all, delete-orphan'))
    user = db.relationship('User', backref=db.backref('reminders', lazy=True, cascade='all, delete-orphan'))

    def __repr__(self):
        return f"<Reminder {self.title} IsRead: {self.is_read}>"


class ActivityLog(db.Model):
    """ActivityLog Model for client timeline tracking."""
    __tablename__ = 'activity_logs'

    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id', ondelete='CASCADE'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    activity_type = db.Column(db.String(100), nullable=False) # blog_published, ads_reviewed, campaign_updated, report_generated, file_uploaded, note_added, task_completed
    description = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    campaign = db.relationship('Campaign', backref=db.backref('activity_logs', lazy=True, cascade='all, delete-orphan'))
    user = db.relationship('User', backref=db.backref('activity_logs', lazy=True, cascade='all, delete-orphan'))

    def __repr__(self):
        return f"<ActivityLog {self.activity_type} - {self.description[:30]}>"


class TimelineMilestone(db.Model):
    """TimelineMilestone Model representing visual timeline progress."""
    __tablename__ = 'timeline_milestones'

    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id', ondelete='CASCADE'), nullable=False)
    stage = db.Column(db.String(50), nullable=False) # Planning, Execution, Monitoring, Reporting, Completed
    title = db.Column(db.String(255), nullable=False)
    due_date = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), default='pending', nullable=False) # pending, completed, delayed
    completed_at = db.Column(db.DateTime, nullable=True)

    campaign = db.relationship('Campaign', backref=db.backref('timeline_milestones', lazy=True, cascade='all, delete-orphan'))

    def __repr__(self):
        return f"<TimelineMilestone {self.title} Stage: {self.stage} Status: {self.status}>"


# ---------------------------------------------------------------------------
# Sprint 5A: Marketing platform integrations (read-only)
# ---------------------------------------------------------------------------

INTEGRATION_PROVIDERS = ('gsc', 'ga4')  # Sprint 5B: google_ads, meta_ads


class PlatformConnection(db.Model):
    """OAuth connection to a read-only marketing platform (GSC, GA4, etc.)."""
    __tablename__ = 'platform_connections'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id', ondelete='SET NULL'), nullable=True)
    provider = db.Column(db.String(50), nullable=False)  # gsc, ga4
    status = db.Column(db.String(30), default='connected', nullable=False)  # connected, disconnected, error, token_expired
    external_account_id = db.Column(db.String(255), nullable=False)
    external_account_name = db.Column(db.String(255), nullable=False)
    encrypted_access_token = db.Column(db.LargeBinary, nullable=True)
    encrypted_refresh_token = db.Column(db.LargeBinary, nullable=True)
    token_expires_at = db.Column(db.DateTime, nullable=True)
    scopes = db.Column(db.Text, nullable=True)
    _connection_metadata = db.Column('connection_metadata', db.Text, nullable=True)
    is_mock = db.Column(db.Boolean, default=False, nullable=False)
    last_sync_at = db.Column(db.DateTime, nullable=True)
    last_sync_status = db.Column(db.String(30), nullable=True)  # success, error
    last_sync_error = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('platform_connections', lazy=True, cascade='all, delete-orphan'))
    project = db.relationship('Project', backref=db.backref('platform_connections', lazy=True))
    sync_runs = db.relationship('SyncRun', backref='connection', lazy=True, cascade='all, delete-orphan')
    synced_metrics = db.relationship('SyncedMetric', backref='connection', lazy=True, cascade='all, delete-orphan')
    external_campaign_maps = db.relationship('ExternalCampaignMap', backref='connection', lazy=True, cascade='all, delete-orphan')

    __table_args__ = (
        db.UniqueConstraint('user_id', 'provider', 'external_account_id', name='unique_user_provider_account'),
    )

    @property
    def connection_metadata(self):
        try:
            return json.loads(self._connection_metadata) if self._connection_metadata else {}
        except (ValueError, TypeError):
            return {}

    @connection_metadata.setter
    def connection_metadata(self, val):
        self._connection_metadata = json.dumps(val) if val else None

    @property
    def access_token(self):
        from app.integrations.token_vault import decrypt_token
        return decrypt_token(self.encrypted_access_token)

    @access_token.setter
    def access_token(self, value):
        from app.integrations.token_vault import encrypt_token
        self.encrypted_access_token = encrypt_token(value) if value else None

    @property
    def refresh_token(self):
        from app.integrations.token_vault import decrypt_token
        return decrypt_token(self.encrypted_refresh_token)

    @refresh_token.setter
    def refresh_token(self, value):
        from app.integrations.token_vault import encrypt_token
        self.encrypted_refresh_token = encrypt_token(value) if value else None

    def __repr__(self):
        return f"<PlatformConnection {self.provider} {self.external_account_name}>"


class SyncRun(db.Model):
    """Audit record for a manual (or future scheduled) read-only sync."""
    __tablename__ = 'sync_runs'

    id = db.Column(db.Integer, primary_key=True)
    connection_id = db.Column(db.Integer, db.ForeignKey('platform_connections.id', ondelete='CASCADE'), nullable=False, index=True)
    status = db.Column(db.String(30), nullable=False)  # running, success, error
    records_read = db.Column(db.Integer, default=0, nullable=False)
    error_message = db.Column(db.Text, nullable=True)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    finished_at = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f"<SyncRun connection={self.connection_id} status={self.status}>"


class SyncedMetric(db.Model):
    """Normalized read-only metric cache from external platforms."""
    __tablename__ = 'synced_metrics'

    id = db.Column(db.Integer, primary_key=True)
    connection_id = db.Column(db.Integer, db.ForeignKey('platform_connections.id', ondelete='CASCADE'), nullable=False, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id', ondelete='SET NULL'), nullable=True)
    metric_key = db.Column(db.String(100), nullable=False)
    period_start = db.Column(db.Date, nullable=False)
    period_end = db.Column(db.Date, nullable=False)
    value_json = db.Column(db.Text, nullable=False)
    synced_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint(
            'connection_id', 'metric_key', 'period_start', 'period_end',
            name='unique_synced_metric_period'
        ),
    )

    @property
    def value(self):
        try:
            return json.loads(self.value_json)
        except (ValueError, TypeError):
            return {}

    @value.setter
    def value(self, val):
        self.value_json = json.dumps(val)

    def __repr__(self):
        return f"<SyncedMetric {self.metric_key} {self.period_start}-{self.period_end}>"


class ExternalCampaignMap(db.Model):
    """Maps an external campaign/property to a local Client ? Campaign (import dedupe)."""
    __tablename__ = 'external_campaign_maps'

    id = db.Column(db.Integer, primary_key=True)
    connection_id = db.Column(db.Integer, db.ForeignKey('platform_connections.id', ondelete='CASCADE'), nullable=False, index=True)
    external_campaign_id = db.Column(db.String(255), nullable=False)
    external_campaign_name = db.Column(db.String(255), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id', ondelete='SET NULL'), nullable=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id', ondelete='SET NULL'), nullable=True)
    _external_metadata = db.Column('external_metadata', db.Text, nullable=True)
    imported_at = db.Column(db.DateTime, nullable=True)
    last_seen_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    campaign = db.relationship('Campaign', backref=db.backref('external_maps', lazy=True))
    project = db.relationship('Project', backref=db.backref('external_campaign_maps', lazy=True))

    __table_args__ = (
        db.UniqueConstraint('connection_id', 'external_campaign_id', name='unique_external_campaign'),
    )

    @property
    def external_metadata(self):
        try:
            return json.loads(self._external_metadata) if self._external_metadata else {}
        except (ValueError, TypeError):
            return {}

    @external_metadata.setter
    def external_metadata(self, val):
        self._external_metadata = json.dumps(val) if val else None

    def __repr__(self):
        return f"<ExternalCampaignMap {self.external_campaign_name} imported={bool(self.campaign_id)}>"


# ?? AI Agent Framework (sits above AI Gateway) ???????????????????????????????

class AgentDefinition(db.Model):
    """Catalog entry for a specialized marketing AI agent."""
    __tablename__ = 'agents'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(50), nullable=True)  # research|seo|content|campaign|ads|analytics|email|social
    icon = db.Column(db.String(60), nullable=True)
    task_type = db.Column(db.String(50), nullable=True)  # maps to AI gateway TaskType
    system_prompt = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    sort_order = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'key': self.key,
            'name': self.name,
            'description': self.description,
            'category': self.category,
            'icon': self.icon,
            'task_type': self.task_type,
            'is_active': self.is_active,
            'sort_order': self.sort_order,
        }

    def __repr__(self):
        return f"<AgentDefinition {self.key}>"


class AgentWorkflow(db.Model):
    """Ordered multi-agent pipeline definition."""
    __tablename__ = 'agent_workflows'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=True, index=True)
    organization_id = db.Column(db.Integer, nullable=True, index=True)
    key = db.Column(db.String(80), nullable=False, index=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    # JSON array of agent keys, e.g. ["research","seo","content","campaign"]
    steps_json = db.Column(db.Text, nullable=False, default='[]')
    is_system = db.Column(db.Boolean, default=False, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def steps(self):
        try:
            return json.loads(self.steps_json) if self.steps_json else []
        except (ValueError, TypeError):
            return []

    @steps.setter
    def steps(self, value):
        self.steps_json = json.dumps(value or [])

    def to_dict(self):
        return {
            'id': self.id,
            'key': self.key,
            'name': self.name,
            'description': self.description,
            'steps': self.steps,
            'is_system': self.is_system,
            'is_active': self.is_active,
        }

    def __repr__(self):
        return f"<AgentWorkflow {self.key}>"


class AgentRun(db.Model):
    """Single or multi-agent execution record with step progress."""
    __tablename__ = 'agent_runs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    organization_id = db.Column(db.Integer, nullable=True, index=True)
    workflow_id = db.Column(db.Integer, db.ForeignKey('agent_workflows.id', ondelete='SET NULL'), nullable=True)
    agent_key = db.Column(db.String(50), nullable=True)  # set for single-agent runs
    mode = db.Column(db.String(20), default='single', nullable=False)  # single|workflow|auto
    status = db.Column(db.String(30), default='pending', nullable=False, index=True)
    # pending|running|completed|failed|cancelled
    input_json = db.Column(db.Text, nullable=True)
    context_json = db.Column(db.Text, nullable=True)
    steps_json = db.Column(db.Text, nullable=True)  # progress + per-step outputs
    final_output = db.Column(db.Text, nullable=True)
    error_message = db.Column(db.String(500), nullable=True)
    total_tokens = db.Column(db.Integer, default=0)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id', ondelete='SET NULL'), nullable=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id', ondelete='SET NULL'), nullable=True)
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    workflow = db.relationship('AgentWorkflow', backref=db.backref('runs', lazy=True))
    user = db.relationship('User', backref=db.backref('agent_runs', lazy=True))

    @property
    def input_payload(self):
        try:
            return json.loads(self.input_json) if self.input_json else {}
        except (ValueError, TypeError):
            return {}

    @input_payload.setter
    def input_payload(self, value):
        self.input_json = json.dumps(value or {})

    @property
    def context(self):
        try:
            return json.loads(self.context_json) if self.context_json else {}
        except (ValueError, TypeError):
            return {}

    @context.setter
    def context(self, value):
        self.context_json = json.dumps(value or {})

    @property
    def steps(self):
        try:
            return json.loads(self.steps_json) if self.steps_json else []
        except (ValueError, TypeError):
            return []

    @steps.setter
    def steps(self, value):
        self.steps_json = json.dumps(value or [])

    def to_dict(self, include_output=True):
        data = {
            'id': self.id,
            'user_id': self.user_id,
            'workflow_id': self.workflow_id,
            'agent_key': self.agent_key,
            'mode': self.mode,
            'status': self.status,
            'steps': self.steps,
            'total_tokens': self.total_tokens or 0,
            'project_id': self.project_id,
            'campaign_id': self.campaign_id,
            'error_message': self.error_message,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
        if include_output:
            data['input'] = self.input_payload
            data['final_output'] = self.final_output
        return data

    def __repr__(self):
        return f"<AgentRun {self.id} {self.status}>"


class AgentMemory(db.Model):
    """Persistent context for agents: workspace, campaign, brand voice, prior outputs."""
    __tablename__ = 'agent_memory'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    organization_id = db.Column(db.Integer, nullable=True, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id', ondelete='CASCADE'), nullable=True, index=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id', ondelete='CASCADE'), nullable=True, index=True)
    memory_type = db.Column(db.String(40), nullable=False, index=True)
    # workspace|campaign|client|brand_voice|previous_output|prompt_history
    agent_key = db.Column(db.String(50), nullable=True, index=True)
    run_id = db.Column(db.Integer, db.ForeignKey('agent_runs.id', ondelete='SET NULL'), nullable=True)
    key = db.Column(db.String(120), nullable=False)
    value_json = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def value(self):
        try:
            return json.loads(self.value_json) if self.value_json else None
        except (ValueError, TypeError):
            return self.value_json

    @value.setter
    def value(self, val):
        if isinstance(val, (dict, list)):
            self.value_json = json.dumps(val)
        else:
            self.value_json = json.dumps(val)

    def to_dict(self):
        return {
            'id': self.id,
            'memory_type': self.memory_type,
            'agent_key': self.agent_key,
            'key': self.key,
            'value': self.value,
            'project_id': self.project_id,
            'campaign_id': self.campaign_id,
            'run_id': self.run_id,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<AgentMemory {self.memory_type}:{self.key}>"


class AgentLog(db.Model):
    """Structured execution log lines for agent runs."""
    __tablename__ = 'agent_logs'

    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.Integer, db.ForeignKey('agent_runs.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    agent_key = db.Column(db.String(50), nullable=True, index=True)
    level = db.Column(db.String(20), default='info')  # info|warning|error|debug
    event = db.Column(db.String(80), nullable=False)  # started|step_started|step_completed|failed|...
    message = db.Column(db.Text, nullable=True)
    meta_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    run = db.relationship('AgentRun', backref=db.backref('logs', lazy=True, cascade='all, delete-orphan'))

    @property
    def meta(self):
        try:
            return json.loads(self.meta_json) if self.meta_json else {}
        except (ValueError, TypeError):
            return {}

    @meta.setter
    def meta(self, value):
        self.meta_json = json.dumps(value or {})

    def to_dict(self):
        return {
            'id': self.id,
            'run_id': self.run_id,
            'agent_key': self.agent_key,
            'level': self.level,
            'event': self.event,
            'message': self.message,
            'meta': self.meta,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<AgentLog {self.event} run={self.run_id}>"


# ?? Enterprise Knowledge Engine + RAG ????????????????????????????????????????

class KnowledgeCollection(db.Model):
    """Scoped knowledge collections: workspace, client, campaign, brand, personal, global."""
    __tablename__ = 'knowledge_collections'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id', ondelete='CASCADE'), nullable=True, index=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id', ondelete='CASCADE'), nullable=True, index=True)
    key = db.Column(db.String(80), nullable=False, index=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    # workspace|client|campaign|brand|personal|global
    collection_type = db.Column(db.String(40), nullable=False, default='workspace', index=True)
    is_system = db.Column(db.Boolean, default=False, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'key': self.key,
            'name': self.name,
            'description': self.description,
            'collection_type': self.collection_type,
            'organization_id': self.organization_id,
            'project_id': self.project_id,
            'campaign_id': self.campaign_id,
            'is_system': self.is_system,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<KnowledgeCollection {self.key}>"


class KnowledgeDocument(db.Model):
    """Ingested knowledge document with versioning and status."""
    __tablename__ = 'knowledge_documents'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id', ondelete='SET NULL'), nullable=True, index=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id', ondelete='SET NULL'), nullable=True, index=True)
    title = db.Column(db.String(255), nullable=False)
    # pdf|docx|txt|csv|xlsx|markdown|html|json|url|sitemap|note|brand|marketing|research|case_study|playbook
    doc_type = db.Column(db.String(40), nullable=False, default='txt', index=True)
    source_type = db.Column(db.String(40), nullable=False, default='upload')  # upload|url|manual|sitemap
    source_uri = db.Column(db.String(500), nullable=True)
    storage_path = db.Column(db.String(500), nullable=True)
    mime_type = db.Column(db.String(120), nullable=True)
    file_size = db.Column(db.Integer, default=0)
    # active|archived|deleted|indexing|failed
    status = db.Column(db.String(30), default='active', nullable=False, index=True)
    visibility = db.Column(db.String(20), default='shared', nullable=False)  # private|shared
    current_version = db.Column(db.Integer, default=1, nullable=False)
    chunk_count = db.Column(db.Integer, default=0)
    embedding_count = db.Column(db.Integer, default=0)
    checksum = db.Column(db.String(64), nullable=True)
    meta_json = db.Column(db.Text, nullable=True)
    error_message = db.Column(db.String(500), nullable=True)
    indexed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def meta(self):
        try:
            return json.loads(self.meta_json) if self.meta_json else {}
        except (ValueError, TypeError):
            return {}

    @meta.setter
    def meta(self, value):
        self.meta_json = json.dumps(value or {})

    def to_dict(self, include_meta=True):
        data = {
            'id': self.id,
            'title': self.title,
            'doc_type': self.doc_type,
            'source_type': self.source_type,
            'source_uri': self.source_uri,
            'status': self.status,
            'visibility': self.visibility,
            'current_version': self.current_version,
            'chunk_count': self.chunk_count or 0,
            'embedding_count': self.embedding_count or 0,
            'file_size': self.file_size or 0,
            'project_id': self.project_id,
            'campaign_id': self.campaign_id,
            'organization_id': self.organization_id,
            'indexed_at': self.indexed_at.isoformat() if self.indexed_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'error_message': self.error_message,
        }
        if include_meta:
            data['meta'] = self.meta
        return data

    def __repr__(self):
        return f"<KnowledgeDocument {self.id} {self.title}>"


class KnowledgeVersion(db.Model):
    """Document version history with restore support."""
    __tablename__ = 'knowledge_versions'

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey('knowledge_documents.id', ondelete='CASCADE'), nullable=False, index=True)
    version_number = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(255), nullable=False)
    content_text = db.Column(db.Text().with_variant(LONGTEXT, 'mysql'), nullable=True)
    storage_path = db.Column(db.String(500), nullable=True)
    checksum = db.Column(db.String(64), nullable=True)
    change_note = db.Column(db.String(255), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    document = db.relationship('KnowledgeDocument', backref=db.backref('versions', lazy=True, cascade='all, delete-orphan'))

    __table_args__ = (
        db.UniqueConstraint('document_id', 'version_number', name='uq_knowledge_doc_version'),
    )

    def to_dict(self, include_content=False):
        data = {
            'id': self.id,
            'document_id': self.document_id,
            'version_number': self.version_number,
            'title': self.title,
            'checksum': self.checksum,
            'change_note': self.change_note,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
        if include_content:
            data['content_text'] = self.content_text
        return data


class KnowledgeChunk(db.Model):
    """Intelligent text chunk belonging to a document version."""
    __tablename__ = 'knowledge_chunks'

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey('knowledge_documents.id', ondelete='CASCADE'), nullable=False, index=True)
    version_number = db.Column(db.Integer, nullable=False, default=1)
    chunk_index = db.Column(db.Integer, nullable=False, default=0)
    content = db.Column(db.Text().with_variant(LONGTEXT, 'mysql'), nullable=False)
    token_estimate = db.Column(db.Integer, default=0)
    meta_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    document = db.relationship('KnowledgeDocument', backref=db.backref('chunks', lazy=True, cascade='all, delete-orphan'))

    @property
    def meta(self):
        try:
            return json.loads(self.meta_json) if self.meta_json else {}
        except (ValueError, TypeError):
            return {}

    @meta.setter
    def meta(self, value):
        self.meta_json = json.dumps(value or {})

    def to_dict(self):
        return {
            'id': self.id,
            'document_id': self.document_id,
            'version_number': self.version_number,
            'chunk_index': self.chunk_index,
            'content': self.content,
            'token_estimate': self.token_estimate,
            'meta': self.meta,
        }


class KnowledgeEmbedding(db.Model):
    """Vector embedding for a chunk (provider-agnostic storage)."""
    __tablename__ = 'knowledge_embeddings'

    id = db.Column(db.Integer, primary_key=True)
    chunk_id = db.Column(db.Integer, db.ForeignKey('knowledge_chunks.id', ondelete='CASCADE'), nullable=False, unique=True, index=True)
    document_id = db.Column(db.Integer, db.ForeignKey('knowledge_documents.id', ondelete='CASCADE'), nullable=False, index=True)
    organization_id = db.Column(db.Integer, nullable=True, index=True)
    provider = db.Column(db.String(40), nullable=False, default='local')
    model = db.Column(db.String(120), nullable=False, default='local-hash-384')
    dims = db.Column(db.Integer, nullable=False, default=384)
    # JSON array of floats — local store; external DBs keep their own IDs
    vector_json = db.Column(db.Text().with_variant(LONGTEXT, 'mysql'), nullable=False)
    external_id = db.Column(db.String(120), nullable=True)  # pinecone/qdrant id when used
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    chunk = db.relationship('KnowledgeChunk', backref=db.backref('embedding', uselist=False, cascade='all, delete-orphan'))

    @property
    def vector(self):
        try:
            return json.loads(self.vector_json) if self.vector_json else []
        except (ValueError, TypeError):
            return []

    @vector.setter
    def vector(self, value):
        self.vector_json = json.dumps(list(value or []))


class CollectionDocument(db.Model):
    """Many-to-many: documents can belong to multiple collections."""
    __tablename__ = 'collection_documents'

    id = db.Column(db.Integer, primary_key=True)
    collection_id = db.Column(db.Integer, db.ForeignKey('knowledge_collections.id', ondelete='CASCADE'), nullable=False, index=True)
    document_id = db.Column(db.Integer, db.ForeignKey('knowledge_documents.id', ondelete='CASCADE'), nullable=False, index=True)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('collection_id', 'document_id', name='uq_collection_document'),
    )


class KnowledgeTag(db.Model):
    __tablename__ = 'knowledge_tags'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, nullable=True, index=True)
    document_id = db.Column(db.Integer, db.ForeignKey('knowledge_documents.id', ondelete='CASCADE'), nullable=False, index=True)
    tag = db.Column(db.String(80), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('document_id', 'tag', name='uq_knowledge_doc_tag'),
    )


class KnowledgePermission(db.Model):
    """RBAC-style permissions on collections or documents."""
    __tablename__ = 'knowledge_permissions'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, nullable=True, index=True)
    collection_id = db.Column(db.Integer, db.ForeignKey('knowledge_collections.id', ondelete='CASCADE'), nullable=True, index=True)
    document_id = db.Column(db.Integer, db.ForeignKey('knowledge_documents.id', ondelete='CASCADE'), nullable=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=True, index=True)
    role = db.Column(db.String(40), nullable=True)  # admin|manager|editor|viewer
    # read|write|admin
    permission = db.Column(db.String(20), nullable=False, default='read')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class KnowledgeSearchLog(db.Model):
    """Search analytics for the Knowledge Engine."""
    __tablename__ = 'knowledge_search_logs'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, nullable=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    search_query = db.Column(db.String(500), nullable=False)
    search_type = db.Column(db.String(30), default='semantic')  # semantic|hybrid|keyword
    collection_ids_json = db.Column(db.Text, nullable=True)
    top_k = db.Column(db.Integer, default=6)
    result_count = db.Column(db.Integer, default=0)
    latency_ms = db.Column(db.Integer, default=0)
    project_id = db.Column(db.Integer, nullable=True)
    campaign_id = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def to_dict(self):
        return {
            'id': self.id,
            'query': self.search_query,
            'search_type': self.search_type,
            'result_count': self.result_count,
            'latency_ms': self.latency_ms,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


# ?? Enterprise MCP + Tool Calling Platform ???????????????????????????????????

class ToolCategory(db.Model):
    __tablename__ = 'tool_categories'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(60), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=True)
    icon = db.Column(db.String(60), nullable=True)
    sort_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'key': self.key,
            'name': self.name,
            'description': self.description,
            'icon': self.icon,
            'sort_order': self.sort_order,
            'is_active': self.is_active,
        }


class ToolDefinition(db.Model):
    """Registered tool catalog entry (built-in or marketplace-installed)."""
    __tablename__ = 'tools'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(80), unique=True, nullable=False, index=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    category_key = db.Column(db.String(60), nullable=True, index=True)
    version = db.Column(db.String(20), default='1.0.0', nullable=False)
    # builtin|mcp|marketplace|http
    provider_type = db.Column(db.String(40), default='builtin', nullable=False)
    mcp_server = db.Column(db.String(80), nullable=True)
    input_schema_json = db.Column(db.Text, nullable=True)
    is_enabled = db.Column(db.Boolean, default=True, nullable=False)
    is_builtin = db.Column(db.Boolean, default=False, nullable=False)
    is_installed = db.Column(db.Boolean, default=True, nullable=False)
    requires_oauth = db.Column(db.Boolean, default=False, nullable=False)
    icon = db.Column(db.String(60), nullable=True)
    meta_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def input_schema(self):
        try:
            return json.loads(self.input_schema_json) if self.input_schema_json else {}
        except (ValueError, TypeError):
            return {}

    @input_schema.setter
    def input_schema(self, value):
        self.input_schema_json = json.dumps(value or {})

    @property
    def meta(self):
        try:
            return json.loads(self.meta_json) if self.meta_json else {}
        except (ValueError, TypeError):
            return {}

    @meta.setter
    def meta(self, value):
        self.meta_json = json.dumps(value or {})

    def to_dict(self):
        return {
            'id': self.id,
            'key': self.key,
            'name': self.name,
            'description': self.description,
            'category_key': self.category_key,
            'version': self.version,
            'provider_type': self.provider_type,
            'mcp_server': self.mcp_server,
            'input_schema': self.input_schema,
            'is_enabled': self.is_enabled,
            'is_builtin': self.is_builtin,
            'is_installed': self.is_installed,
            'requires_oauth': self.requires_oauth,
            'icon': self.icon,
            'meta': self.meta,
        }


class ToolPermission(db.Model):
    __tablename__ = 'tool_permissions'

    id = db.Column(db.Integer, primary_key=True)
    tool_key = db.Column(db.String(80), nullable=False, index=True)
    organization_id = db.Column(db.Integer, nullable=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=True, index=True)
    role = db.Column(db.String(40), nullable=True)  # admin|manager|editor|viewer
    # allow|deny
    effect = db.Column(db.String(10), default='allow', nullable=False)
    oauth_scopes_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def oauth_scopes(self):
        try:
            return json.loads(self.oauth_scopes_json) if self.oauth_scopes_json else []
        except (ValueError, TypeError):
            return []

    @oauth_scopes.setter
    def oauth_scopes(self, value):
        self.oauth_scopes_json = json.dumps(value or [])

    def to_dict(self):
        return {
            'id': self.id,
            'tool_key': self.tool_key,
            'organization_id': self.organization_id,
            'user_id': self.user_id,
            'role': self.role,
            'effect': self.effect,
            'oauth_scopes': self.oauth_scopes,
        }


class ToolRun(db.Model):
    __tablename__ = 'tool_runs'

    id = db.Column(db.Integer, primary_key=True)
    tool_key = db.Column(db.String(80), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    organization_id = db.Column(db.Integer, nullable=True, index=True)
    agent_key = db.Column(db.String(50), nullable=True, index=True)
    agent_run_id = db.Column(db.Integer, nullable=True, index=True)
    status = db.Column(db.String(30), default='pending', nullable=False, index=True)
    # pending|running|completed|failed|timeout|denied
    input_json = db.Column(db.Text, nullable=True)
    output_json = db.Column(db.Text, nullable=True)
    error_message = db.Column(db.String(500), nullable=True)
    retry_count = db.Column(db.Integer, default=0)
    duration_ms = db.Column(db.Integer, default=0)
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    @property
    def input_payload(self):
        try:
            return json.loads(self.input_json) if self.input_json else {}
        except (ValueError, TypeError):
            return {}

    @input_payload.setter
    def input_payload(self, value):
        self.input_json = json.dumps(value or {})

    @property
    def output_payload(self):
        try:
            return json.loads(self.output_json) if self.output_json else {}
        except (ValueError, TypeError):
            return {}

    @output_payload.setter
    def output_payload(self, value):
        self.output_json = json.dumps(value or {})

    def to_dict(self, include_io=True):
        data = {
            'id': self.id,
            'tool_key': self.tool_key,
            'user_id': self.user_id,
            'organization_id': self.organization_id,
            'agent_key': self.agent_key,
            'agent_run_id': self.agent_run_id,
            'status': self.status,
            'retry_count': self.retry_count or 0,
            'duration_ms': self.duration_ms or 0,
            'error_message': self.error_message,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
        if include_io:
            data['input'] = self.input_payload
            data['output'] = self.output_payload
        return data


class ToolLog(db.Model):
    __tablename__ = 'tool_logs'

    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.Integer, db.ForeignKey('tool_runs.id', ondelete='CASCADE'), nullable=False, index=True)
    level = db.Column(db.String(20), default='info')
    event = db.Column(db.String(80), nullable=False)
    message = db.Column(db.Text, nullable=True)
    meta_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    run = db.relationship('ToolRun', backref=db.backref('logs', lazy=True, cascade='all, delete-orphan'))

    @property
    def meta(self):
        try:
            return json.loads(self.meta_json) if self.meta_json else {}
        except (ValueError, TypeError):
            return {}

    @meta.setter
    def meta(self, value):
        self.meta_json = json.dumps(value or {})

    def to_dict(self):
        return {
            'id': self.id,
            'run_id': self.run_id,
            'level': self.level,
            'event': self.event,
            'message': self.message,
            'meta': self.meta,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class ToolConnection(db.Model):
    """Future OAuth / API connections for marketplace tools (credentials encrypted)."""
    __tablename__ = 'tool_connections'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, nullable=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=True, index=True)
    provider_key = db.Column(db.String(80), nullable=False, index=True)  # google|slack|hubspot|...
    display_name = db.Column(db.String(150), nullable=True)
    status = db.Column(db.String(30), default='disconnected')  # connected|disconnected|error|pending
    # Encrypted blob — never expose to frontend
    credentials_encrypted = db.Column(db.Text, nullable=True)
    scopes_json = db.Column(db.Text, nullable=True)
    meta_json = db.Column(db.Text, nullable=True)
    connected_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'provider_key': self.provider_key,
            'display_name': self.display_name,
            'status': self.status,
            'organization_id': self.organization_id,
            'connected_at': self.connected_at.isoformat() if self.connected_at else None,
            # credentials intentionally omitted
        }


class ToolSetting(db.Model):
    __tablename__ = 'tool_settings'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, nullable=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=True, index=True)
    tool_key = db.Column(db.String(80), nullable=True, index=True)
    setting_key = db.Column(db.String(80), nullable=False)
    value_json = db.Column(db.Text, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def value(self):
        try:
            return json.loads(self.value_json) if self.value_json else None
        except (ValueError, TypeError):
            return self.value_json

    @value.setter
    def value(self, val):
        self.value_json = json.dumps(val)


class ToolMarketplaceItem(db.Model):
    """Catalog of installable future integrations (stubs / metadata only)."""
    __tablename__ = 'tool_marketplace'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(80), unique=True, nullable=False, index=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    publisher = db.Column(db.String(120), nullable=True)
    category_key = db.Column(db.String(60), nullable=True)
    icon = db.Column(db.String(60), nullable=True)
    version = db.Column(db.String(20), default='1.0.0')
    requires_oauth = db.Column(db.Boolean, default=True)
    is_featured = db.Column(db.Boolean, default=False)
    is_available = db.Column(db.Boolean, default=True)
    # coming_soon|beta|ga
    availability = db.Column(db.String(30), default='coming_soon')
    install_count = db.Column(db.Integer, default=0)
    meta_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'key': self.key,
            'name': self.name,
            'description': self.description,
            'publisher': self.publisher,
            'category_key': self.category_key,
            'icon': self.icon,
            'version': self.version,
            'requires_oauth': self.requires_oauth,
            'is_featured': self.is_featured,
            'is_available': self.is_available,
            'availability': self.availability,
            'install_count': self.install_count or 0,
        }


class BackgroundJob(db.Model):
    """Async job tracking for Celery workers (progress + DLQ visibility)."""
    __tablename__ = 'background_jobs'

    id = db.Column(db.Integer, primary_key=True)
    task_name = db.Column(db.String(120), nullable=False, index=True)
    celery_task_id = db.Column(db.String(120), nullable=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    organization_id = db.Column(db.Integer, nullable=True, index=True)
    status = db.Column(db.String(30), default='queued', nullable=False, index=True)
    # queued|running|completed|failed|dead
    progress = db.Column(db.Integer, default=0)
    payload_json = db.Column(db.Text, nullable=True)
    result_json = db.Column(db.Text, nullable=True)
    error_message = db.Column(db.String(500), nullable=True)
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def to_dict(self):
        return {
            'id': self.id,
            'task_name': self.task_name,
            'celery_task_id': self.celery_task_id,
            'user_id': self.user_id,
            'organization_id': self.organization_id,
            'status': self.status,
            'progress': self.progress or 0,
            'error_message': self.error_message,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }



# Internal Administration RBAC - separate staff identity (Alembic / create_all)
from app.platform_admin.models import (  # noqa: E402, F401
    AdminRole,
    AdminPermission,
    AdminRolePermission,
    AdminUser,
    AdminSession,
    AdminAuditLog,
    AdminLoginEvent,
    AdminFeatureFlag,
)
