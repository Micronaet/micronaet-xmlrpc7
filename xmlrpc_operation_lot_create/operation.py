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
            if operation != 'lot_create':
                # Super call for other cases:
                return super(XmlrpcOperation, self).execute_operation(
                    cr, uid, operation, parameter, context=context)
                    
            server_pool = self.pool.get('xmlrpc.server')
            xmlrpc_server = server_pool.get_xmlrpc_server(
                cr, uid, context=context)
            res = xmlrpc_server.execute('lot_create', parameter)
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
    def xmlrpc_export_lot_create(self, cr, uid, from_date, context=None):
        ''' Schedule update of production on accounting
        '''
        # ---------------------------------------------------------------------
        # Utility:
        # ---------------------------------------------------------------------
        def clean_mrp(name):
            '''
            '''
            name = name.split('/')[-1]
            #name = name[2:]
            return name

        if context is None:
            context = {}

        _logger.info('Start XMLRPC sync for lot creation')
        parameter = {}
        
        # ---------------------------------------------------------------------
        # Create parameters for XMLRPC call:
        # ---------------------------------------------------------------------
        # Generate string for export file:
        parameter['input_file_string'] = ''

        # Get new production to be sync:
        production_ids = self.search(cr, uid, [
            # From date filter for not all old importation (limit):
            ('create_date', '>=', from_date),            
            # New production:
            ('ul_state', '=', 'draft'),
            # Draft or production (other lot are created)
            ('state', 'in', ('draft', 'production')),
            ], context=context)
            
        # ---------------------------------------------------------------------
        # 1. Launch for every production the regenerate button
        # ---------------------------------------------------------------------
        _logger.info('%s production to update UL' % len(production_ids))
        for item_id in production_ids:
            self.load_package_for_production(cr, uid, [item_id], 
                context=context)
            
        # ---------------------------------------------------------------------
        # 2. Write lines not present
        # ---------------------------------------------------------------------
        ul_pool = self.pool.get('mrp.production.product.packaging')
        ul_ids = ul_pool.search(cr, uid, [
            # Only not sync:
            ('production_id', 'in', production_ids), # Only selected production
            #('production_id.ul_state', '=', 'draft'), # MRP to be sync
            ('account_id', '=', False), # Not sync
            ], context=context)
        
        # ---------------------------------------------------------------------
        # Generate file to be passed:
        # ---------------------------------------------------------------------
        mrp_check = [] # List of MRP order to check after import
        for ul in ul_pool.browse(cr, uid, ul_ids, context=context):
            if ul.production_id not in mrp_check:
                mrp_check.append(ul.production_id)                
            parameter['input_file_string'] += self.pool.get(
                'xmlrpc.server').clean_as_ascii(
                    '%-15s%-15s%-15s%-15s\r\n' % (
                    ul.id,
                    clean_mrp(ul.production_id.name),
                    ul.production_id.bom_id.product_id.default_code or '',
                    ul.ul_id.code or '',                
                    ))

        _logger.info('Data: %s' % (parameter, ))
        res = self.pool.get('xmlrpc.operation').execute_operation(
            cr, uid, 'lot_create', parameter=parameter, context=context)
        
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

        error_file = u''
        import pdb; pdb.set_trace()
        for line in result_string_file.split('\n'):            
            row = line.strip()
            if not row:
                continue # jump empty row
            row = line.split('|')
            if len(row) != 2:
                error_file += u'%s\n' % row
                continue
                
            item_id = int(row[0].strip())
            account_id = row[1].strip()
            ul_pool.write(cr, uid, [item_id], {
                'account_id', account_id,
                }, context=context)
            
        _logger.error('Error in file:\n %s' % error_file)
        
        # ---------------------------------------------------------------------
        # Close MRP all lot sync:
        # ---------------------------------------------------------------------
        import pdb; pdb.set_trace()
        for mrp in mrp_check:
            update = True
            for pack in mrp.product_packaging_ids:
                if not pack.account_id:
                    update = False
                    break
                if udpate: # MRP has all pack lot created and sync:
                    self.write(cr, uid, {
                        'ul_state': 'accounting',
                        }, context=context)
        _logger.info('End correct importation XMLRPC sync lot creation')
        return True
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
