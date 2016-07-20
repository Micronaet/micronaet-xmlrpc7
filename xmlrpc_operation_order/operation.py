# -*- coding: utf-8 -*-
###############################################################################
#
#    Copyright (C) 2001-2014 Micronaet SRL (<http://www.micronaet.it>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published
#    by the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################
import os
import sys
import logging
import openerp
import xmlrpclib
import openerp.netsvc as netsvc
import openerp.addons.decimal_precision as dp
from openerp.osv import fields, osv, expression, orm
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from openerp import SUPERUSER_ID
from openerp import tools
from openerp.tools.translate import _
from openerp.tools.float_utils import float_round as round
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT, 
    DEFAULT_SERVER_DATETIME_FORMAT, 
    DATETIME_FORMATS_MAP, 
    float_compare)


_logger = logging.getLogger(__name__)

class XmlrpcOperation(orm.Model):
    ''' Model name: XmlrpcOperation
    '''    
    _inherit = 'xmlrpc.operation'

    # ------------------
    # Override function:
    # ------------------
    def execute_operation(self, cr, uid, operation, parameter, context=None):
        ''' Virtual function that will be overrided
            operation: in this module is 'order'
            context: xmlrpc context dict
        '''
        try:
            if operation != 'order':
                # Super call for other cases:
                return super(XmlrpcOperation, self).execute_operation(
                    cr, uid, operation, parameter, context=context)
                    
            server_pool = self.pool.get('xmlrpc.server')
            xmlrpc_server = server_pool.get_xmlrpc_server(
                cr, uid, context=context)
            res = xmlrpc_server.execute('order', parameter)
            if res.get('error', False):
                _logger.error(res['error'])
                # TODO raise
            # TODO confirm export!    
        except:    
            _logger.error(sys.exc_info())
            raise osv.except_osv(
                _('Connect error:'), _('XMLRPC connecting server'))
        return res
    
class SaleOrder(orm.Model):
    ''' Add export function to order obj
    '''    
    _inherit = 'sale.order'
  
    def xmlrpc_export_order(self, cr, uid, ids, context=None):
        ''' Export current order 
            # TODO manage list of order?
        '''
        def clean_description(value):
            ''' Remove \n and \t and return first 40 char
            ''' 
            value = value.replace('\n', ' ')            
            value = value.replace('\t', ' ') 
            return value[:40]
            
        assert len(ids) == 1, 'No multi export for now' # TODO remove!!!

        # TODO use with validate trigger for get the number
        parameter = {}
        
        # Generate string for export file:
        ''' 
        NUMERO                    6
        CAUSALE                    2
        DATA                          8
        COD.CLIENTE            9
        SCADENZA                8
        COD.AGENTE            9
        NOTE                        16
        
        corpo righe        
        CODICE ARTICOLO   8
        DESCR.ARTICOLO    60
        UM                              2
        QUANTITA'              5+3 dec
        PREZZO                    5+5 dec
        SCONTO                   20
        IVA o ESENZIONI       5
        
        piede del documento
        TOT COLLI                  5
        PESO TOT KG            15
        PORTO                        3
        TRASP.MEZZO           1 (V vettore M mittente D dest)
        '''
        mask = '%s%s%s%s' % ( #3 block for readability:
            '%-6s%-2s%-8s%-9s%-8s%-9s%-16s', #header
            '%-8s%-60s%-2s%9.3f%11.5f%-20s%-5s%', #row
            '%-5s%-15s%-3s%1s', #foot
            '\r\n', # Win CR
            )

        parameter['input_file_string'] = ''
        for order in self.browse(cr, uid, ids, context=context):
            if not order.number:
                raise osv.except_osv(
                    _('XMLRPC sync error'), 
                    _('order must be validated!'))
                
            for line in order.order_line:
                parameter['input_file_string'] += self.pool.get(
                    'xmlrpc.server').clean_as_ascii(
                        mask % (                        
                            # -------------------------------------------------
                            #                    Header:
                            # -------------------------------------------------
                            order.name,
                            order.causal,
                            '%s%s%s' % (
                                order.date_order[:4], 
                                order.date_order[5:7], 
                                order.date_order[8:10], 
                                ),
                            order.partner_id.sql_customer_code,
                            order.deadline,
                            order.mx_agent_id.sql_agent_code or \
                                order.mx_agent_id.sql_supplier_code or '',
                            order.note,
                            
                            # -------------------------------------------------
                            #                    Lines:
                            # -------------------------------------------------

                            # -------------------------------------------------
                            #                    Detail:
                            # -------------------------------------------------
                            line.product_id.default_code or '', 
                            clean_description(
                                line.name if line.use_text_description \
                                    else line.product_id.name),
                            # UOM (2)
                            line.product_id.uom_id.account_ref or '',
                            # Q. 10N (2 dec.)
                            line.quantity, 
                            # Price 10N (3 dec.)
                            line.price_unit, 
                            # Tax (5)
                            line.order_line_tax_id[0].account_ref \
                                if line.order_line_tax_id else '', 
                            # Provv. (5)
                            0, 
                            # Discount (50)
                            line.multi_discount_rates or '',
                            # Discount numeric (10)
                            line.discount or '',
                            # Account (8)
                            line.account_id.account_ref or '', 
                            # Refund (1)
                            refund_line,

                            # -------------------------------------------------
                            #                     Foot:
                            # -------------------------------------------------
                            # Codice Pagamento 3
                            order.payment_term.import_id \
                                if order.payment_term else '', 
                            # TODO bank
                            ))

        res = self.pool.get('xmlrpc.operation').execute_operation(
            cr, uid, 'order', parameter=parameter, context=context)
            
        result_string_file = res.get('result_string_file', False)
        if result_string_file:
            if result_string_file.startswith('OK'):
                #self.write(cr, uid, ids, {
                #    'xmlrpc_sync': True,
                #    }, context=context)
                return True
            else:    
                raise osv.except_osv(
                    _('Sync error:'), 
                    _('Error: %s') % result_string_file,
                    )
                
        # TODO write better error
        raise osv.except_osv(
            _('Sync error:'), 
            _('Cannot sync with accounting! (return esit not present'),
            )
        return False
    
    #_columns = {
    #    'xmlrpc_sync': fields.boolean('XMLRPC syncronized'),        
    #    }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
