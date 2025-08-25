# -*- coding: utf-8 -*-
from odoo import models, fields, api, tools, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)

class TrainingCategory(models.Model):
    _name = 'training.category'
    _description = 'Training Category'
    _order = 'sequence, name'

    name = fields.Char('Category Name', required=True, translate=True)
    code = fields.Char('Category Code', required=True)
    description = fields.Text('Description', translate=True)
    sequence = fields.Integer('Sequence', default=10)
    color = fields.Integer('Color', default=0)
    active = fields.Boolean('Active', default=True)
    
    # Statistics
    course_count = fields.Integer('Courses Count', compute='_compute_course_count')
    
    @api.depends('name')
    def _compute_course_count(self):
        for category in self:
            category.course_count = self.env['training.course'].search_count([('category_id', '=', category.id)])
    
    def action_view_courses(self):
        """View courses for this category"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Courses in %s') % self.name,
            'res_model': 'training.course',
            'view_mode': 'list,form',
            'domain': [('category_id', '=', self.id)],
            'context': {'default_category_id': self.id},
        }

class TrainingCourse(models.Model):
    _name = 'training.course'
    _description = 'Training Course'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, name'

    name = fields.Char('Course Name', required=True, translate=True, tracking=True)
    code = fields.Char('Course Code', required=True)
    description = fields.Html('Description', translate=True)
    category_id = fields.Many2one('training.category', 'Category', required=True)
    instructor_id = fields.Many2one('res.users', 'Instructor', required=True)
    
    # Course Details
    duration_hours = fields.Float('Duration (Hours)', required=True)
    difficulty_level = fields.Selection([
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
        ('expert', 'Expert')
    ], 'Difficulty Level', required=True, default='beginner')
    
    # Prerequisites
    prerequisite_course_ids = fields.Many2many(
        'training.course', 'course_prerequisite_rel',
        'course_id', 'prerequisite_id', 'Prerequisites'
    )
    
    # Course Content
    learning_objectives = fields.Html('Learning Objectives', translate=True)
    course_materials = fields.Html('Course Materials', translate=True)
    
    # Scheduling
    start_date = fields.Datetime('Start Date')
    end_date = fields.Datetime('End Date')
    max_participants = fields.Integer('Max Participants', default=20)
    
    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ], 'Status', default='draft', tracking=True)
    
    # Settings
    is_mandatory = fields.Boolean('Mandatory Course')
    certification_required = fields.Boolean('Certification Required')
    passing_score = fields.Float('Passing Score (%)', default=70.0)
    
    sequence = fields.Integer('Sequence', default=10)
    active = fields.Boolean('Active', default=True)
    
    # Statistics
    enrollment_count = fields.Integer('Enrollments', compute='_compute_enrollment_count')
    completion_rate = fields.Float('Completion Rate (%)', compute='_compute_completion_rate')
    average_score = fields.Float('Average Score', compute='_compute_average_score')
    
    @api.depends('name')
    def _compute_enrollment_count(self):
        for course in self:
            course.enrollment_count = self.env['training.enrollment'].search_count([('course_id', '=', course.id)])
    
    @api.depends('enrollment_count')
    def _compute_completion_rate(self):
        for course in self:
            if course.enrollment_count > 0:
                completed = self.env['training.enrollment'].search_count([
                    ('course_id', '=', course.id),
                    ('status', '=', 'completed')
                ])
                course.completion_rate = (completed / course.enrollment_count) * 100
            else:
                course.completion_rate = 0.0
    
    @api.depends('enrollment_count')
    def _compute_average_score(self):
        for course in self:
            enrollments = self.env['training.enrollment'].search([
                ('course_id', '=', course.id),
                ('final_score', '>', 0)
            ])
            if enrollments:
                course.average_score = sum(enrollments.mapped('final_score')) / len(enrollments)
            else:
                course.average_score = 0.0
    
    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for course in self:
            if course.start_date and course.end_date and course.start_date >= course.end_date:
                raise ValidationError(_('End date must be after start date.'))
    
    def action_schedule(self):
        self.state = 'scheduled'
    
    def action_start(self):
        self.state = 'in_progress'
    
    def action_complete(self):
        self.state = 'completed'
    
    def action_cancel(self):
        self.state = 'cancelled'
    
    def action_view_enrollments(self):
        """View enrollments for this course"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Enrollments for %s') % self.name,
            'res_model': 'training.enrollment',
            'view_mode': 'list,form',
            'domain': [('course_id', '=', self.id)],
            'context': {'default_course_id': self.id},
        }
    
    def action_view_completion_rate(self):
        """View completion rate details for this course"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Completion Rate for %s') % self.name,
            'res_model': 'training.enrollment',
            'view_mode': 'list,form',
            'domain': [('course_id', '=', self.id), ('status', '=', 'completed')],
            'context': {'default_course_id': self.id},
        }
    
    def action_view_average_score(self):
        """View average score details for this course"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Scores for %s') % self.name,
            'res_model': 'training.enrollment',
            'view_mode': 'list,form',
            'domain': [('course_id', '=', self.id), ('score', '>', 0)],
            'context': {'default_course_id': self.id},
        }

class TrainingEnrollment(models.Model):
    _name = 'training.enrollment'
    _description = 'Training Enrollment'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'display_name'

    name = fields.Char('Reference', required=True, copy=False, readonly=True, default=lambda self: _('New'))
    display_name = fields.Char('Display Name', compute='_compute_display_name', store=True)
    
    sales_rep_id = fields.Many2one('sales.rep', 'Sales Representative', required=True, tracking=True)
    course_id = fields.Many2one('training.course', 'Course', required=True, tracking=True)
    
    # Enrollment Details
    enrollment_date = fields.Datetime('Enrollment Date', default=fields.Datetime.now, tracking=True)
    start_date = fields.Datetime('Start Date')
    completion_date = fields.Datetime('Completion Date')
    deadline = fields.Datetime('Deadline')
    
    # Progress
    progress_percentage = fields.Float('Progress (%)', default=0.0)
    attendance_hours = fields.Float('Attendance Hours', default=0.0)
    
    # Evaluation
    final_score = fields.Float('Final Score (%)', default=0.0)
    passed = fields.Boolean('Passed', compute='_compute_passed', store=True)
    
    # Status
    status = fields.Selection([
        ('enrolled', 'Enrolled'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled')
    ], 'Status', default='enrolled', tracking=True)
    
    # Notes
    notes = fields.Text('Notes')
    instructor_feedback = fields.Text('Instructor Feedback')
    
    @api.depends('sales_rep_id', 'course_id')
    def _compute_display_name(self):
        for enrollment in self:
            if enrollment.sales_rep_id and enrollment.course_id:
                enrollment.display_name = f"{enrollment.sales_rep_id.name} - {enrollment.course_id.name}"
            else:
                enrollment.display_name = enrollment.name or 'New'
    
    @api.depends('final_score', 'course_id.passing_score')
    def _compute_passed(self):
        for enrollment in self:
            if enrollment.course_id and enrollment.final_score >= enrollment.course_id.passing_score:
                enrollment.passed = True
            else:
                enrollment.passed = False
    
    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('training.enrollment') or _('New')
        return super(TrainingEnrollment, self).create(vals)
    
    def action_start(self):
        self.write({
            'status': 'in_progress',
            'start_date': fields.Datetime.now()
        })
    
    def action_complete(self):
        self.write({
            'status': 'completed',
            'completion_date': fields.Datetime.now(),
            'progress_percentage': 100.0
        })
        
        # Create certification if required and passed
        if self.course_id.certification_required and self.passed:
            self._create_certification()
    
    def action_fail(self):
        self.status = 'failed'
    
    def action_cancel(self):
        self.status = 'cancelled'
    
    def _create_certification(self):
        """Create certification record for completed course"""
        self.env['sales.rep.certification'].create({
            'sales_rep_id': self.sales_rep_id.id,
            'course_id': self.course_id.id,
            'enrollment_id': self.id,
            'certification_date': fields.Date.today(),
            'score': self.final_score,
            'valid_until': fields.Date.today() + timedelta(days=365),  # Valid for 1 year
        })

class SalesRepEvaluation(models.Model):
    _name = 'sales.rep.evaluation'
    _description = 'Sales Rep Evaluation'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'evaluation_date desc'

    name = fields.Char('Reference', required=True, copy=False, readonly=True, default=lambda self: _('New'))
    sales_rep_id = fields.Many2one('sales.rep', 'Sales Representative', required=True, tracking=True)
    evaluator_id = fields.Many2one('res.users', 'Evaluator', required=True, default=lambda self: self.env.user)
    
    # Evaluation Details
    evaluation_date = fields.Date('Evaluation Date', required=True, default=fields.Date.today)
    evaluation_period_start = fields.Date('Period Start', required=True)
    evaluation_period_end = fields.Date('Period End', required=True)
    evaluation_type = fields.Selection([
        ('quarterly', 'Quarterly'),
        ('semi_annual', 'Semi-Annual'),
        ('annual', 'Annual'),
        ('probation', 'Probation'),
        ('special', 'Special')
    ], 'Evaluation Type', required=True, default='quarterly')
    
    # Performance Scores
    sales_performance_score = fields.Float('Sales Performance (0-100)', default=0.0)
    customer_satisfaction_score = fields.Float('Customer Satisfaction (0-100)', default=0.0)
    product_knowledge_score = fields.Float('Product Knowledge (0-100)', default=0.0)
    communication_skills_score = fields.Float('Communication Skills (0-100)', default=0.0)
    teamwork_score = fields.Float('Teamwork (0-100)', default=0.0)
    punctuality_score = fields.Float('Punctuality (0-100)', default=0.0)
    
    # Overall Score
    overall_score = fields.Float('Overall Score', compute='_compute_overall_score', store=True)
    performance_rating = fields.Selection([
        ('excellent', 'Excellent (90-100)'),
        ('good', 'Good (80-89)'),
        ('satisfactory', 'Satisfactory (70-79)'),
        ('needs_improvement', 'Needs Improvement (60-69)'),
        ('unsatisfactory', 'Unsatisfactory (0-59)')
    ], 'Performance Rating', compute='_compute_performance_rating', store=True)
    
    # Goals and Objectives
    goals_achieved = fields.Text('Goals Achieved')
    goals_missed = fields.Text('Goals Missed')
    improvement_areas = fields.Text('Areas for Improvement')
    development_plan = fields.Text('Development Plan')
    
    # Comments
    evaluator_comments = fields.Text('Evaluator Comments')
    employee_comments = fields.Text('Employee Comments')
    
    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('reviewed', 'Reviewed'),
        ('approved', 'Approved')
    ], 'Status', default='draft', tracking=True)
    
    @api.depends('sales_performance_score', 'customer_satisfaction_score', 'product_knowledge_score',
                 'communication_skills_score', 'teamwork_score', 'punctuality_score')
    def _compute_overall_score(self):
        for evaluation in self:
            scores = [
                evaluation.sales_performance_score,
                evaluation.customer_satisfaction_score,
                evaluation.product_knowledge_score,
                evaluation.communication_skills_score,
                evaluation.teamwork_score,
                evaluation.punctuality_score
            ]
            evaluation.overall_score = sum(scores) / len(scores) if scores else 0.0
    
    @api.depends('overall_score')
    def _compute_performance_rating(self):
        for evaluation in self:
            score = evaluation.overall_score
            if score >= 90:
                evaluation.performance_rating = 'excellent'
            elif score >= 80:
                evaluation.performance_rating = 'good'
            elif score >= 70:
                evaluation.performance_rating = 'satisfactory'
            elif score >= 60:
                evaluation.performance_rating = 'needs_improvement'
            else:
                evaluation.performance_rating = 'unsatisfactory'
    
    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('sales.rep.evaluation') or _('New')
        return super(SalesRepEvaluation, self).create(vals)
    
    def action_submit(self):
        self.state = 'submitted'
    
    def action_review(self):
        self.state = 'reviewed'
    
    def action_approve(self):
        self.state = 'approved'
    
    def action_reset_to_draft(self):
        self.state = 'draft'

class SalesRepCertification(models.Model):
    _name = 'sales.rep.certification'
    _description = 'Sales Rep Certification'
    _order = 'certification_date desc'

    name = fields.Char('Certification Name', compute='_compute_name', store=True)
    sales_rep_id = fields.Many2one('sales.rep', 'Sales Representative', required=True)
    course_id = fields.Many2one('training.course', 'Course', required=True)
    enrollment_id = fields.Many2one('training.enrollment', 'Enrollment')
    
    # Certification Details
    certification_date = fields.Date('Certification Date', required=True)
    valid_until = fields.Date('Valid Until')
    score = fields.Float('Score (%)')
    certificate_number = fields.Char('Certificate Number', readonly=True)
    
    # Status
    is_active = fields.Boolean('Active', default=True)
    is_expired = fields.Boolean('Expired', compute='_compute_is_expired')
    
    @api.depends('sales_rep_id', 'course_id')
    def _compute_name(self):
        for cert in self:
            if cert.sales_rep_id and cert.course_id:
                cert.name = f"{cert.course_id.name} - {cert.sales_rep_id.name}"
            else:
                cert.name = 'New Certification'
    
    @api.depends('valid_until')
    def _compute_is_expired(self):
        today = fields.Date.today()
        for cert in self:
            cert.is_expired = cert.valid_until and cert.valid_until < today
    
    @api.model
    def create(self, vals):
        if not vals.get('certificate_number'):
            vals['certificate_number'] = self.env['ir.sequence'].next_by_code('sales.rep.certification') or 'CERT000'
        return super(SalesRepCertification, self).create(vals)

class TrainingAnalytics(models.Model):
    _name = 'training.analytics'
    _description = 'Training Analytics'
    _auto = False
    _rec_name = 'date'

    date = fields.Date('Date')
    sales_rep_id = fields.Many2one('sales.rep', 'Sales Representative')
    course_id = fields.Many2one('training.course', 'Course')
    category_id = fields.Many2one('training.category', 'Category')
    territory_id = fields.Many2one('geo.node', 'Territory')
    
    # Metrics
    enrollment_count = fields.Integer('Enrollments')
    completion_count = fields.Integer('Completions')
    certification_count = fields.Integer('Certifications')
    total_training_hours = fields.Float('Total Training Hours')
    average_score = fields.Float('Average Score')
    completion_rate = fields.Float('Completion Rate (%)')
    
    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    ROW_NUMBER() OVER () AS id,
                    DATE(te.enrollment_date) AS date,
                    te.sales_rep_id,
                    te.course_id,
                    tc.category_id,
                    ta.geo_node_id AS territory_id,
                    COUNT(te.id) AS enrollment_count,
                    COUNT(CASE WHEN te.status = 'completed' THEN 1 END) AS completion_count,
                    COUNT(src.id) AS certification_count,
                    SUM(te.attendance_hours) AS total_training_hours,
                    AVG(te.final_score) AS average_score,
                    CASE 
                        WHEN COUNT(te.id) > 0 THEN 
                            (COUNT(CASE WHEN te.status = 'completed' THEN 1 END) * 100.0 / COUNT(te.id))
                        ELSE 0
                    END AS completion_rate
                FROM training_enrollment te
                LEFT JOIN training_course tc ON te.course_id = tc.id
                LEFT JOIN sales_rep sr ON te.sales_rep_id = sr.id
                LEFT JOIN territory_assignment ta ON sr.id = ta.sales_rep_id AND ta.active = true
                LEFT JOIN sales_rep_certification src ON te.id = src.enrollment_id
                GROUP BY
                    DATE(te.enrollment_date),
                    te.sales_rep_id,
                    te.course_id,
                    tc.category_id,
                    ta.geo_node_id
            )
        """ % self._table)