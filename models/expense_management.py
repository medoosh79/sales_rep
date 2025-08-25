# -*- coding: utf-8 -*-
from odoo import models, fields, api, tools, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta
import base64


class ExpenseCategory(models.Model):
    _name = 'expense.category'
    _description = 'Expense Category'
    _order = 'sequence, name'

    name = fields.Char('Category Name', required=True)
    code = fields.Char('Category Code', required=True)
    description = fields.Text('Description')
    sequence = fields.Integer('Sequence', default=10)
    active = fields.Boolean('Active', default=True)
    
    # Limits and Rules
    daily_limit = fields.Float('Daily Limit', help='Maximum amount per day for this category')
    monthly_limit = fields.Float('Monthly Limit', help='Maximum amount per month for this category')
    requires_receipt = fields.Boolean('Requires Receipt', default=True)
    requires_approval = fields.Boolean('Requires Approval', default=True)
    
    # Accounting
    account_id = fields.Many2one('account.account', string='Expense Account')
    
    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Category code must be unique!'),
    ]


class SalesRepExpense(models.Model):
    _name = 'sales.rep.expense'
    _description = 'Sales Representative Expense'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char('Expense Reference', required=True, copy=False, readonly=True, default=lambda self: _('New'))
    sales_rep_id = fields.Many2one('sales.rep', string='Sales Representative', required=True, tracking=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', related='sales_rep_id.employee_id', store=True)
    
    # Expense Details
    date = fields.Date('Expense Date', required=True, default=fields.Date.context_today, tracking=True)
    category_id = fields.Many2one('expense.category', string='Category', required=True, tracking=True)
    description = fields.Text('Description', required=True)
    amount = fields.Float('Amount', required=True, tracking=True)
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    
    # Location and Customer
    location = fields.Char('Location')
    customer_id = fields.Many2one('res.partner', string='Related Customer', domain=[('is_company', '=', True)])
    visit_id = fields.Many2one('daily.visit.schedule', string='Related Visit')
    
    # Receipt and Documentation
    receipt_attachment_ids = fields.Many2many('ir.attachment', 'expense_receipt_rel', 'expense_id', 'attachment_id', string='Receipt Attachments')
    has_receipt = fields.Boolean('Has Receipt', compute='_compute_has_receipt', store=True)
    
    # Approval Workflow
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('paid', 'Paid')
    ], string='Status', default='draft', tracking=True)
    
    submitted_date = fields.Datetime('Submitted Date', readonly=True)
    approved_date = fields.Datetime('Approved Date', readonly=True)
    approved_by = fields.Many2one('res.users', string='Approved By', readonly=True)
    rejected_date = fields.Datetime('Rejected Date', readonly=True)
    rejected_by = fields.Many2one('res.users', string='Rejected By', readonly=True)
    rejection_reason = fields.Text('Rejection Reason')
    
    # Payment
    payment_date = fields.Date('Payment Date')
    payment_method = fields.Selection([
        ('cash', 'Cash'),
        ('bank_transfer', 'Bank Transfer'),
        ('check', 'Check'),
        ('petty_cash', 'Petty Cash')
    ], string='Payment Method')
    
    # Additional Information
    notes = fields.Text('Notes')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    
    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('sales.rep.expense') or _('New')
        return super().create(vals)
    
    @api.depends('receipt_attachment_ids')
    def _compute_has_receipt(self):
        for expense in self:
            expense.has_receipt = bool(expense.receipt_attachment_ids)
    
    @api.constrains('amount')
    def _check_amount(self):
        for expense in self:
            if expense.amount <= 0:
                raise ValidationError(_('Expense amount must be positive.'))
    
    @api.constrains('date')
    def _check_date(self):
        for expense in self:
            if expense.date > fields.Date.today():
                raise ValidationError(_('Expense date cannot be in the future.'))
    
    def action_submit(self):
        """Submit expense for approval"""
        for expense in self:
            if expense.state != 'draft':
                raise UserError(_('Only draft expenses can be submitted.'))
            
            # Check if receipt is required
            if expense.category_id.requires_receipt and not expense.has_receipt:
                raise UserError(_('Receipt is required for this expense category.'))
            
            # Check daily and monthly limits
            self._check_expense_limits()
            
            expense.write({
                'state': 'submitted',
                'submitted_date': fields.Datetime.now()
            })
            
            # Send notification to managers
            self._send_approval_notification()
    
    def action_approve(self):
        """Approve expense"""
        for expense in self:
            if expense.state != 'submitted':
                raise UserError(_('Only submitted expenses can be approved.'))
            
            expense.write({
                'state': 'approved',
                'approved_date': fields.Datetime.now(),
                'approved_by': self.env.user.id
            })
            
            # Create accounting entry if needed
            self._create_accounting_entry()
    
    def action_reject(self):
        """Reject expense"""
        for expense in self:
            if expense.state != 'submitted':
                raise UserError(_('Only submitted expenses can be rejected.'))
            
            expense.write({
                'state': 'rejected',
                'rejected_date': fields.Datetime.now(),
                'rejected_by': self.env.user.id
            })
    
    def action_mark_paid(self):
        """Mark expense as paid"""
        for expense in self:
            if expense.state != 'approved':
                raise UserError(_('Only approved expenses can be marked as paid.'))
            
            expense.write({
                'state': 'paid',
                'payment_date': fields.Date.today()
            })
    
    def action_reset_to_draft(self):
        """Reset expense to draft"""
        for expense in self:
            if expense.state not in ['rejected']:
                raise UserError(_('Only rejected expenses can be reset to draft.'))
            
            expense.write({
                'state': 'draft',
                'submitted_date': False,
                'approved_date': False,
                'approved_by': False,
                'rejected_date': False,
                'rejected_by': False,
                'rejection_reason': False
            })
    
    def _check_expense_limits(self):
        """Check if expense exceeds category limits"""
        for expense in self:
            category = expense.category_id
            
            # Check daily limit
            if category.daily_limit > 0:
                daily_expenses = self.search([
                    ('sales_rep_id', '=', expense.sales_rep_id.id),
                    ('category_id', '=', category.id),
                    ('date', '=', expense.date),
                    ('state', 'in', ['submitted', 'approved', 'paid']),
                    ('id', '!=', expense.id)
                ])
                daily_total = sum(daily_expenses.mapped('amount')) + expense.amount
                
                if daily_total > category.daily_limit:
                    raise ValidationError(_('Daily limit exceeded for category %s. Limit: %s, Total: %s') % 
                                        (category.name, category.daily_limit, daily_total))
            
            # Check monthly limit
            if category.monthly_limit > 0:
                month_start = expense.date.replace(day=1)
                month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
                
                monthly_expenses = self.search([
                    ('sales_rep_id', '=', expense.sales_rep_id.id),
                    ('category_id', '=', category.id),
                    ('date', '>=', month_start),
                    ('date', '<=', month_end),
                    ('state', 'in', ['submitted', 'approved', 'paid']),
                    ('id', '!=', expense.id)
                ])
                monthly_total = sum(monthly_expenses.mapped('amount')) + expense.amount
                
                if monthly_total > category.monthly_limit:
                    raise ValidationError(_('Monthly limit exceeded for category %s. Limit: %s, Total: %s') % 
                                        (category.name, category.monthly_limit, monthly_total))
    
    def _send_approval_notification(self):
        """Send notification to managers for approval"""
        # Get sales managers
        managers = self.env['res.users'].search([('groups_id', 'in', [self.env.ref('sales_team.group_sale_manager').id])])
        
        for manager in managers:
            self.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=manager.id,
                summary=_('Expense Approval Required'),
                note=_('Expense %s from %s requires approval. Amount: %s') % 
                     (self.name, self.sales_rep_id.name, self.amount)
            )
    
    def _create_accounting_entry(self):
        """Create accounting entry for approved expense"""
        # This would integrate with accounting module
        # For now, we'll just log the action
        self.message_post(
            body=_('Accounting entry created for expense %s') % self.name,
            message_type='notification'
        )


class ExpenseReport(models.Model):
    _name = 'expense.report'
    _description = 'Expense Report'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_from desc, id desc'

    name = fields.Char('Report Name', required=True, copy=False, readonly=True, default=lambda self: _('New'))
    sales_rep_id = fields.Many2one('sales.rep', string='Sales Representative', required=True, tracking=True)
    
    # Report Period
    date_from = fields.Date('From Date', required=True, tracking=True)
    date_to = fields.Date('To Date', required=True, tracking=True)
    
    # Expense Lines
    expense_ids = fields.Many2many('sales.rep.expense', string='Expenses')
    expense_count = fields.Integer('Number of Expenses', compute='_compute_expense_summary', store=True)
    total_amount = fields.Float('Total Amount', compute='_compute_expense_summary', store=True)
    
    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('paid', 'Paid')
    ], string='Status', default='draft', tracking=True)
    
    # Approval
    submitted_date = fields.Datetime('Submitted Date', readonly=True)
    approved_date = fields.Datetime('Approved Date', readonly=True)
    approved_by = fields.Many2one('res.users', string='Approved By', readonly=True)
    
    # Additional Information
    notes = fields.Text('Notes')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    
    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('expense.report') or _('New')
        return super().create(vals)
    
    @api.depends('expense_ids')
    def _compute_expense_summary(self):
        for report in self:
            report.expense_count = len(report.expense_ids)
            report.total_amount = sum(report.expense_ids.mapped('amount'))
    
    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for report in self:
            if report.date_from > report.date_to:
                raise ValidationError(_('From date must be before to date.'))
    
    def action_load_expenses(self):
        """Load expenses for the selected period"""
        for report in self:
            expenses = self.env['sales.rep.expense'].search([
                ('sales_rep_id', '=', report.sales_rep_id.id),
                ('date', '>=', report.date_from),
                ('date', '<=', report.date_to),
                ('state', 'in', ['approved', 'paid'])
            ])
            report.expense_ids = [(6, 0, expenses.ids)]
    
    def action_submit(self):
        """Submit report for approval"""
        for report in self:
            if report.state != 'draft':
                raise UserError(_('Only draft reports can be submitted.'))
            
            if not report.expense_ids:
                raise UserError(_('Cannot submit empty expense report.'))
            
            report.write({
                'state': 'submitted',
                'submitted_date': fields.Datetime.now()
            })
    
    def action_approve(self):
        """Approve report"""
        for report in self:
            if report.state != 'submitted':
                raise UserError(_('Only submitted reports can be approved.'))
            
            report.write({
                'state': 'approved',
                'approved_date': fields.Datetime.now(),
                'approved_by': self.env.user.id
            })
            
            # Mark all expenses as approved
            report.expense_ids.write({'state': 'approved'})


class CostAnalysis(models.Model):
    _name = 'cost.analysis'
    _description = 'Cost Analysis'
    _auto = False
    _order = 'date desc'

    sales_rep_id = fields.Many2one('sales.rep', string='Sales Representative')
    date = fields.Date('Date')
    category_id = fields.Many2one('expense.category', string='Category')
    total_amount = fields.Float('Total Amount')
    expense_count = fields.Integer('Number of Expenses')
    avg_amount = fields.Float('Average Amount')
    territory_id = fields.Many2one('territory.assignment', string='Territory')
    
    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    row_number() OVER () AS id,
                    e.sales_rep_id,
                    e.date,
                    e.category_id,
                    SUM(e.amount) AS total_amount,
                    COUNT(e.id) AS expense_count,
                    AVG(e.amount) AS avg_amount,
                    ta.id AS territory_id
                FROM sales_rep_expense e
                LEFT JOIN sales_rep sr ON e.sales_rep_id = sr.id
                LEFT JOIN territory_assignment ta ON sr.id = ta.sales_rep_id
                WHERE e.state IN ('approved', 'paid')
                GROUP BY e.sales_rep_id, e.date, e.category_id, ta.id
            )
        """ % self._table)