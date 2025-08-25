# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime, timedelta
import base64
import io
import xlsxwriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.units import inch


class AdvancedReportWizard(models.TransientModel):
    _name = 'advanced.report.wizard'
    _description = 'Advanced Report Wizard'

    report_type = fields.Selection([
        ('sales_performance', 'Sales Performance Report'),
        ('commission_summary', 'Commission Summary Report'),
        ('territory_analysis', 'Territory Analysis Report'),
        ('gps_tracking', 'GPS Tracking Report'),
        ('visit_summary', 'Visit Summary Report'),
        ('kpi_dashboard', 'KPI Dashboard Report'),
        ('field_inventory', 'Field Inventory Report'),
    ], string='Report Type', required=True, default='sales_performance')
    
    date_from = fields.Date(string='From Date', required=True, 
                           default=lambda self: fields.Date.today().replace(day=1))
    date_to = fields.Date(string='To Date', required=True, 
                         default=fields.Date.today())
    
    sales_rep_ids = fields.Many2many('sales.rep', string='Sales Representatives')
    territory_ids = fields.Many2many('territory.assignment', string='Territories')
    
    export_format = fields.Selection([
        ('pdf', 'PDF'),
        ('excel', 'Excel'),
        ('both', 'Both PDF and Excel')
    ], string='Export Format', required=True, default='pdf')
    
    include_charts = fields.Boolean(string='Include Charts', default=True)
    include_summary = fields.Boolean(string='Include Summary', default=True)
    group_by_territory = fields.Boolean(string='Group by Territory', default=False)
    group_by_month = fields.Boolean(string='Group by Month', default=False)
    
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        # Set default date range to current month
        today = fields.Date.today()
        res['date_from'] = today.replace(day=1)
        res['date_to'] = today
        return res
    
    def generate_report(self):
        """Generate the selected report in the specified format"""
        self.ensure_one()
        
        if self.export_format == 'pdf':
            return self._generate_pdf_report()
        elif self.export_format == 'excel':
            return self._generate_excel_report()
        elif self.export_format == 'both':
            # Generate both formats and return a zip file
            return self._generate_both_formats()
    
    def _generate_pdf_report(self):
        """Generate PDF report"""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        story = []
        styles = getSampleStyleSheet()
        
        # Title
        title = self._get_report_title()
        story.append(Paragraph(title, styles['Title']))
        story.append(Spacer(1, 12))
        
        # Report period
        period_text = f"Report Period: {self.date_from} to {self.date_to}"
        story.append(Paragraph(period_text, styles['Normal']))
        story.append(Spacer(1, 12))
        
        # Get report data
        data = self._get_report_data()
        
        if self.include_summary:
            summary = self._generate_summary(data)
            story.append(Paragraph("Summary", styles['Heading2']))
            story.append(Paragraph(summary, styles['Normal']))
            story.append(Spacer(1, 12))
        
        # Generate table
        table_data = self._prepare_table_data(data)
        if table_data:
            table = Table(table_data)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 14),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(table)
        
        doc.build(story)
        buffer.seek(0)
        
        # Create attachment
        filename = f"{self.report_type}_{self.date_from}_{self.date_to}.pdf"
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(buffer.getvalue()),
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/pdf'
        })
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }
    
    def _generate_excel_report(self):
        """Generate Excel report"""
        buffer = io.BytesIO()
        workbook = xlsxwriter.Workbook(buffer)
        
        # Create formats
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#D7E4BC',
            'border': 1
        })
        
        data_format = workbook.add_format({
            'border': 1
        })
        
        number_format = workbook.add_format({
            'num_format': '#,##0.00',
            'border': 1
        })
        
        # Create worksheet
        worksheet = workbook.add_worksheet(self._get_report_title())
        
        # Write title and period
        worksheet.write(0, 0, self._get_report_title(), header_format)
        worksheet.write(1, 0, f"Period: {self.date_from} to {self.date_to}")
        
        # Get data and write to worksheet
        data = self._get_report_data()
        table_data = self._prepare_table_data(data)
        
        if table_data:
            # Write headers
            for col, header in enumerate(table_data[0]):
                worksheet.write(3, col, header, header_format)
            
            # Write data
            for row_idx, row_data in enumerate(table_data[1:], start=4):
                for col_idx, cell_data in enumerate(row_data):
                    if isinstance(cell_data, (int, float)):
                        worksheet.write(row_idx, col_idx, cell_data, number_format)
                    else:
                        worksheet.write(row_idx, col_idx, cell_data, data_format)
        
        # Add summary if requested
        if self.include_summary and data:
            summary_row = len(table_data) + 5
            worksheet.write(summary_row, 0, "Summary:", header_format)
            summary_text = self._generate_summary(data)
            worksheet.write(summary_row + 1, 0, summary_text)
        
        workbook.close()
        buffer.seek(0)
        
        # Create attachment
        filename = f"{self.report_type}_{self.date_from}_{self.date_to}.xlsx"
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(buffer.getvalue()),
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        })
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }
    
    def _get_report_title(self):
        """Get report title based on report type"""
        titles = {
            'sales_performance': 'Sales Performance Report',
            'commission_summary': 'Commission Summary Report',
            'territory_analysis': 'Territory Analysis Report',
            'gps_tracking': 'GPS Tracking Report',
            'visit_summary': 'Visit Summary Report',
            'kpi_dashboard': 'KPI Dashboard Report',
            'field_inventory': 'Field Inventory Report',
        }
        return titles.get(self.report_type, 'Advanced Report')
    
    def _get_report_data(self):
        """Get data for the selected report type"""
        if self.report_type == 'sales_performance':
            return self._get_sales_performance_data()
        elif self.report_type == 'commission_summary':
            return self._get_commission_summary_data()
        elif self.report_type == 'territory_analysis':
            return self._get_territory_analysis_data()
        elif self.report_type == 'gps_tracking':
            return self._get_gps_tracking_data()
        elif self.report_type == 'visit_summary':
            return self._get_visit_summary_data()
        elif self.report_type == 'kpi_dashboard':
            return self._get_kpi_dashboard_data()
        elif self.report_type == 'field_inventory':
            return self._get_field_inventory_data()
        return []
    
    def _get_sales_performance_data(self):
        """Get sales performance data"""
        domain = [('date', '>=', self.date_from), ('date', '<=', self.date_to)]
        if self.sales_rep_ids:
            domain.append(('sales_rep_id', 'in', self.sales_rep_ids.ids))
        
        # Get sales data from various sources
        sales_reps = self.env['sales.rep'].search([('id', 'in', self.sales_rep_ids.ids)] if self.sales_rep_ids else [])
        if not sales_reps:
            sales_reps = self.env['sales.rep'].search([])
        
        data = []
        for rep in sales_reps:
            # Calculate metrics for each rep
            visits = self.env['daily.visit.schedule'].search([
                ('sales_rep_id', '=', rep.id),
                ('date', '>=', self.date_from),
                ('date', '<=', self.date_to)
            ])
            
            commissions = self.env['commission.calculation'].search([
                ('sales_rep_id', '=', rep.id),
                ('date', '>=', self.date_from),
                ('date', '<=', self.date_to)
            ])
            
            data.append({
                'sales_rep': rep.name,
                'total_visits': len(visits),
                'completed_visits': len(visits.filtered(lambda v: v.status == 'completed')),
                'total_commission': sum(commissions.mapped('amount')),
                'territory': rep.territory_assignment_ids[0].territory_id.name if rep.territory_assignment_ids else 'N/A',
                'performance_score': rep.performance_score or 0,
            })
        
        return data
    
    def _get_commission_summary_data(self):
        """Get commission summary data"""
        domain = [('date', '>=', self.date_from), ('date', '<=', self.date_to)]
        if self.sales_rep_ids:
            domain.append(('sales_rep_id', 'in', self.sales_rep_ids.ids))
        
        commissions = self.env['commission.calculation'].search(domain)
        
        data = []
        for commission in commissions:
            data.append({
                'sales_rep': commission.sales_rep_id.name,
                'date': commission.date,
                'amount': commission.amount,
                'commission_type': commission.commission_scheme_id.name,
                'status': commission.state,
                'territory': commission.sales_rep_id.territory_assignment_ids[0].territory_id.name if commission.sales_rep_id.territory_assignment_ids else 'N/A',
            })
        
        return data
    
    def _get_territory_analysis_data(self):
        """Get territory analysis data"""
        territories = self.territory_ids if self.territory_ids else self.env['territory.assignment'].search([])
        
        data = []
        for territory in territories:
            reps = territory.sales_rep_ids
            total_visits = 0
            total_commission = 0
            
            for rep in reps:
                visits = self.env['daily.visit.schedule'].search([
                    ('sales_rep_id', '=', rep.id),
                    ('date', '>=', self.date_from),
                    ('date', '<=', self.date_to)
                ])
                
                commissions = self.env['commission.calculation'].search([
                    ('sales_rep_id', '=', rep.id),
                    ('date', '>=', self.date_from),
                    ('date', '<=', self.date_to)
                ])
                
                total_visits += len(visits)
                total_commission += sum(commissions.mapped('amount'))
            
            data.append({
                'territory': territory.territory_id.name,
                'total_reps': len(reps),
                'total_visits': total_visits,
                'total_commission': total_commission,
                'avg_commission_per_rep': total_commission / len(reps) if reps else 0,
            })
        
        return data
    
    def _get_gps_tracking_data(self):
        """Get GPS tracking data"""
        domain = [('timestamp', '>=', self.date_from), ('timestamp', '<=', self.date_to)]
        if self.sales_rep_ids:
            domain.append(('sales_rep_id', 'in', self.sales_rep_ids.ids))
        
        tracking_records = self.env['gps.tracking'].search(domain)
        
        data = []
        for record in tracking_records:
            data.append({
                'sales_rep': record.sales_rep_id.name,
                'timestamp': record.timestamp,
                'tracking_type': record.tracking_type,
                'address': record.address,
                'customer': record.customer_id.name if record.customer_id else 'N/A',
                'distance_to_customer': record.distance_to_customer,
                'speed': record.speed,
                'in_territory': 'Yes' if record.is_in_territory else 'No',
                'valid': 'Yes' if record.is_valid else 'No',
            })
        
        return data
    
    def _get_visit_summary_data(self):
        """Get visit summary data"""
        domain = [('date', '>=', self.date_from), ('date', '<=', self.date_to)]
        if self.sales_rep_ids:
            domain.append(('sales_rep_id', 'in', self.sales_rep_ids.ids))
        
        visits = self.env['daily.visit.schedule'].search(domain)
        
        data = []
        for visit in visits:
            data.append({
                'sales_rep': visit.sales_rep_id.name,
                'date': visit.date,
                'customer': visit.customer_id.name,
                'visit_type': visit.visit_type,
                'status': visit.status,
                'planned_time': visit.planned_time,
                'actual_time': visit.actual_time,
                'notes': visit.notes or 'N/A',
            })
        
        return data
    
    def _get_kpi_dashboard_data(self):
        """Get KPI dashboard data"""
        reps = self.sales_rep_ids if self.sales_rep_ids else self.env['sales.rep'].search([])
        
        data = []
        for rep in reps:
            kpis = self.env['sales.rep.kpi'].search([
                ('sales_rep_id', '=', rep.id),
                ('date', '>=', self.date_from),
                ('date', '<=', self.date_to)
            ])
            
            for kpi in kpis:
                data.append({
                    'sales_rep': rep.name,
                    'date': kpi.date,
                    'target_visits': kpi.target_visits,
                    'actual_visits': kpi.actual_visits,
                    'target_sales': kpi.target_sales,
                    'actual_sales': kpi.actual_sales,
                    'achievement_percentage': kpi.achievement_percentage,
                    'performance_score': kpi.performance_score,
                })
        
        return data
    
    def _get_field_inventory_data(self):
        """Get field inventory data"""
        domain = [('date', '>=', self.date_from), ('date', '<=', self.date_to)]
        if self.sales_rep_ids:
            domain.append(('sales_rep_id', 'in', self.sales_rep_ids.ids))
        
        inventories = self.env['field.inventory'].search(domain)
        
        data = []
        for inventory in inventories:
            for line in inventory.line_ids:
                data.append({
                    'sales_rep': inventory.sales_rep_id.name,
                    'date': inventory.date,
                    'location': inventory.location,
                    'product': line.product_id.name,
                    'theoretical_qty': line.theoretical_qty,
                    'actual_qty': line.actual_qty,
                    'difference': line.difference,
                    'status': inventory.state,
                })
        
        return data
    
    def _prepare_table_data(self, data):
        """Prepare table data for display"""
        if not data:
            return []
        
        if self.report_type == 'sales_performance':
            headers = ['Sales Rep', 'Total Visits', 'Completed Visits', 'Total Commission', 'Territory', 'Performance Score']
            rows = [[d['sales_rep'], d['total_visits'], d['completed_visits'], d['total_commission'], d['territory'], d['performance_score']] for d in data]
        elif self.report_type == 'commission_summary':
            headers = ['Sales Rep', 'Date', 'Amount', 'Commission Type', 'Status', 'Territory']
            rows = [[d['sales_rep'], d['date'], d['amount'], d['commission_type'], d['status'], d['territory']] for d in data]
        elif self.report_type == 'territory_analysis':
            headers = ['Territory', 'Total Reps', 'Total Visits', 'Total Commission', 'Avg Commission/Rep']
            rows = [[d['territory'], d['total_reps'], d['total_visits'], d['total_commission'], d['avg_commission_per_rep']] for d in data]
        elif self.report_type == 'gps_tracking':
            headers = ['Sales Rep', 'Timestamp', 'Type', 'Address', 'Customer', 'Distance', 'Speed', 'In Territory', 'Valid']
            rows = [[d['sales_rep'], d['timestamp'], d['tracking_type'], d['address'], d['customer'], d['distance_to_customer'], d['speed'], d['in_territory'], d['valid']] for d in data]
        elif self.report_type == 'visit_summary':
            headers = ['Sales Rep', 'Date', 'Customer', 'Visit Type', 'Status', 'Planned Time', 'Actual Time', 'Notes']
            rows = [[d['sales_rep'], d['date'], d['customer'], d['visit_type'], d['status'], d['planned_time'], d['actual_time'], d['notes']] for d in data]
        elif self.report_type == 'kpi_dashboard':
            headers = ['Sales Rep', 'Date', 'Target Visits', 'Actual Visits', 'Target Sales', 'Actual Sales', 'Achievement %', 'Performance Score']
            rows = [[d['sales_rep'], d['date'], d['target_visits'], d['actual_visits'], d['target_sales'], d['actual_sales'], d['achievement_percentage'], d['performance_score']] for d in data]
        elif self.report_type == 'field_inventory':
            headers = ['Sales Rep', 'Date', 'Location', 'Product', 'Theoretical Qty', 'Actual Qty', 'Difference', 'Status']
            rows = [[d['sales_rep'], d['date'], d['location'], d['product'], d['theoretical_qty'], d['actual_qty'], d['difference'], d['status']] for d in data]
        else:
            return []
        
        return [headers] + rows
    
    def _generate_summary(self, data):
        """Generate summary text for the report"""
        if not data:
            return "No data available for the selected period."
        
        summary = f"Total records: {len(data)}\n"
        
        if self.report_type == 'sales_performance':
            total_visits = sum(d['total_visits'] for d in data)
            total_commission = sum(d['total_commission'] for d in data)
            avg_performance = sum(d['performance_score'] for d in data) / len(data) if data else 0
            summary += f"Total visits: {total_visits}\n"
            summary += f"Total commission: {total_commission:.2f}\n"
            summary += f"Average performance score: {avg_performance:.2f}"
        elif self.report_type == 'commission_summary':
            total_amount = sum(d['amount'] for d in data)
            summary += f"Total commission amount: {total_amount:.2f}"
        elif self.report_type == 'territory_analysis':
            total_reps = sum(d['total_reps'] for d in data)
            total_commission = sum(d['total_commission'] for d in data)
            summary += f"Total representatives: {total_reps}\n"
            summary += f"Total commission: {total_commission:.2f}"
        
        return summary
    
    def _generate_both_formats(self):
        """Generate both PDF and Excel formats"""
        # For now, just generate PDF (can be extended to create a zip with both)
        return self._generate_pdf_report()