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
            if operation != 'purchase':
                # Super call for other cases:
                return super(XmlrpcOperation, self).execute_operation(
                    cr, uid, operation, parameter, context=context)
                    
            server_pool = self.pool.get('xmlrpc.server')
            xmlrpc_server = server_pool.get_xmlrpc_server(
                cr, uid, context=context)
            res = xmlrpc_server.execute('purchase', parameter)
            if res.get('error', False):
                _logger.error(res['error'])
                # TODO raise
            # TODO confirm export!    
        except:    
            _logger.error(sys.exc_info())
            raise osv.except_osv(
                _('Connect error:'), _('XMLRPC connecting server'))
        return res
    
class PurchaseOrderAccounting(orm.Model):
    ''' Add export function to order obj
    '''    
    _inherit = 'purchase.order.accounting'
  
    # Override sync action:
    def xmlrpc_sync_request(self, cr, uid, ids, context=None):
        ''' Override action anc call real action
        '''
        if type(ids) not in (tuple, list):
            ids = [ids]

        return self.xmlrpc_export_order(cr, uid, ids, context=context)
    
    def xmlrpc_export_order(self, cr, uid, ids, context=None):
        ''' Export current purchase order 
        '''
        def format_date(value):
            ''' Set date for accounting program:
            '''
            if value:
                return '%s%s%s' % (
                    value[:4], 
                    value[5:7], 
                    value[8:10], 
                    )
            return ''        
                
        assert len(ids) == 1, 'No multi export for now' # TODO remove!!!

        # TODO use with validate trigger for get the number
        parameter = {}
        
        mask = '%s%s%s%s' % ( #3 block for readability:
            '%-8s%-9s%-8s', #header
            '%-8s%-60s%-2s%8s%10s%-20s%-5s%-8s', #row
            '%-5s%-15s%-3s%1s', #foot
            '\r\n', # Win CR
            )

        parameter['input_file_string'] = ''
        for purchase in self.browse(cr, uid, ids, context=context):
            for line in purchase.line_ids:
                product = line.product_id
                data = (                        
                    # -------------------------------------------------
                    #                    Header:
                    # -------------------------------------------------
                    format_date(purchase.date),
                    purchase.supplier_id.sql_supplier_code or '',
                    format_date(purchase.deadline),
                    #purchase.note[:16] if purchase.note else '',
                                                
                    # -------------------------------------------------
                    #                    Lines:
                    # -------------------------------------------------
                    (product.default_code or '')[:8],
                    ((product.name.split('] ')[-1]).split('\n')[0])[:60],
                    product.uom_id.account_ref or '',
                    ('%9.3f' % line.real_qty).replace('.', ''),
                    ('%11.5f' % line.list_price).replace('.', ''),
                    '', #line.discount or '',
                    '', # TODO vat tax_id
                    format_date(line.deadline),

                    # -------------------------------------------------
                    #                    Footer:
                    # -------------------------------------------------
                    '', # TODO total parcels 
                    '', # TODO weight total
                    '', # TODO port
                    '', # TODO transport
                    )
                parameter['input_file_string'] += self.pool.get(
                    'xmlrpc.server').clean_as_ascii(mask % data)

        res = self.pool.get('xmlrpc.operation').execute_operation(
            cr, uid, 'purchase', parameter=parameter, context=context)
            
        result_string_file = res.get('result_string_file', False)
        if result_string_file:
            if result_string_file.startswith('OK'):
                self.write(cr, uid, ids, {
                    'name': result_string_file[2:], # Ref. order created
                    'xmlrpc_sync': True,
                    }, context=context)
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
    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
