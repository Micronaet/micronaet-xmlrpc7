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
            if operation != 'check_cl_sl':
                # Super call for other cases:
                return super(XmlrpcOperation, self).execute_operation(
                    cr, uid, operation, parameter, context=context)
                    
            server_pool = self.pool.get('xmlrpc.server')
            xmlrpc_server = server_pool.get_xmlrpc_server(
                cr, uid, context=context)
            res = xmlrpc_server.execute('check_cl_sl', parameter)
            if res.get('error', False):
                _logger.error(res['error'])
                # TODO raise
            # TODO confirm export!    
        except:    
            _logger.error(sys.exc_info())
            raise osv.except_osv(
                _('Connect error:'), _('XMLRPC connecting server'))
        return res
    
class MrpProduction(orm.Model):
    ''' Add export function to invoice obj
    '''    
    _inherit = 'mrp.production'
  
    # -------------------------------------------------------------------------
    # Scheduled
    # -------------------------------------------------------------------------
    def xmlrpc_export_check_cl_sl(self, cr, uid, from_date, context=None):
        ''' Schedule check SL and CL
        '''
        if context is None:
            context = {}

        _logger.info('Start XMLRPC sync for lot creation')
        parameter = {}
        
        # ---------------------------------------------------------------------
        # Create parameters for XMLRPC call:
        # ---------------------------------------------------------------------
        # Generate string for export file:
        parameter['input_file_string'] = '' # No passed
        _logger.info('Data: %s' % (parameter, ))
        res = self.pool.get('xmlrpc.operation').execute_operation(
            cr, uid, 'check_cl_sl', parameter=parameter, context=context)
        
        # ---------------------------------------------------------------------
        # Parse result:    
        # ---------------------------------------------------------------------
        error = res.get('error', '')
        if error:
            _logger.error('Error in transfer operation: %s' % error)
            return False

        result_string_file = res.get('result_string_file', '')
        if not result_string_file:
            _logger.warning('Not reply from XMLRPC (no data or error)')
            return False

        # Read CL and SL result:        
        for line in result_string_file.split('\n'):            
            row = line.strip()
            if not row:
                continue # jump empty row

            # TODO check procedure:    
            #row = line.split('|')
            #if len(row) != 2:
            #    error_file += u'%s\n' % row
            #    continue
            #    
            #item_id = int(row[0].strip())
            #account_id = row[1].strip()
            #ul_pool.write(cr, uid, [item_id], {
            #    'account_id': account_id,
            #    }, context=context)
        # TODO send mail information    
        
        return True
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
