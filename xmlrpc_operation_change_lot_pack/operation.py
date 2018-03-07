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
            operation: in this module is 'invoice'
            context: xmlrpc context dict
        '''
        try:
            if operation != 'lot_change_pack':
                # Super call for other cases:
                return super(XmlrpcOperation, self).execute_operation(
                    cr, uid, operation, parameter, context=context)
                    
            server_pool = self.pool.get('xmlrpc.server')
            xmlrpc_server = server_pool.get_xmlrpc_server(
                cr, uid, context=context)
            res = xmlrpc_server.execute('lot_change_pack', parameter)
            if res.get('error', False):
                _logger.error(res['error'])
                # TODO raise
            # TODO confirm export!    
        except:    
            _logger.error(sys.exc_info())
            raise osv.except_osv(
                _('Connect error:'), _('XMLRPC connecting server'))
        return res
    
class ProductProduct(orm.Model):
    ''' Add export function to move lot package
    '''    
    _inherit = 'product.product'
  
    # -------------------------------------------------------------------------
    # Scheduled
    # -------------------------------------------------------------------------
    def xmlrpc_export_lot_change_log_package(
            self, cr, uid, qty, from_obj, to_obj=False, pack_obj=False, 
            context=None):
        ''' Schedule update of production on accounting
            Browse object passed:
            from_id: original lot
            to_id: destination lot (if present)
            to_package: if new lot 
        '''
        if context is None:
            context = {}

        xml_pool = self.pool.get('xmlrpc.server')
        _logger.info('Start XMLRPC lot swap package')
        parameter = {}
        
        # ---------------------------------------------------------------------
        # Create parameters for XMLRPC call:
        # ---------------------------------------------------------------------
        # Generate string for export file:
        parameter['input_file_string'] = ''

        # ---------------------------------------------------------------------
        # Generate file to be passed:
        # ---------------------------------------------------------------------
        parameter['input_file_string'] += xml_pool.clean_as_ascii(
                '%10.2f%-20s%-20s%-20s\r\n' % (
                qty,
                # TODO change:
                from_obj.ref, # ID
                to_obj.name or '',
                pack_obj.code or '',
                ))

        _logger.info('Data: %s' % (parameter, ))
        res = xml_pool.execute_operation(
            cr, uid, 'lot_change_pack', parameter=parameter, context=context)
        
        # ---------------------------------------------------------------------
        # Parse result:    
        # ---------------------------------------------------------------------
        error = res.get('error', '')
        if error:
            raise osv.except_osv(
                _(u'Error moving'), 
                _(u'Error in transfer operation: %s') % error,
                )

        result_string_file = res.get('result_string_file', '')
        if not result_string_file:
            raise osv.except_osv(
                _(u'Error moving'), 
                _(u'Not reply from XMLRPC (no data or error)'),
                )

        if result_string_file.startswith('OK'):
            return True # Correct passed!
        else:    
            raise osv.except_osv(
                _(u'Error moving'), 
                _(u'Account error: %s' % result_string_file),
                )
            return False    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
