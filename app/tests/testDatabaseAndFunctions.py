#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os.path

folder = os.path.basename(os.path.dirname(os.path.abspath(__file__)))
if folder == "tests": # testing from within WingIDE, default folder is tests
    sys.path.append('../libs')
    sys.path.append('../config')
    sys.path.append('../../app')
else: # python running from should be within folder app
    sys.path.append('./libs')
    sys.path.append('./config')

import unittest
from datetime import datetime
import opasCentralDBLib
import pymysql

from unitTestConfig import base_api, base_plus_endpoint_encoded

class TestSQLStructure(unittest.TestCase):
    """
    Note: tests are performed in alphabetical order, hence the function naming
          with forced order in the names.   
    """
    def test_1_testviews(self):
        ocd = opasCentralDBLib.opasCentralDB()
        dbok = ocd.open_connection(caller_name="test_views") # make sure connection is open
        assert (dbok == True)
        tables = ["vw_active_sessions",
                  "vw_api_productbase",
                  "vw_api_productbase_instance_counts", 
                  "vw_api_sourceinfodb",
                  "vw_api_volume_limits",
                  "vw_instance_counts_books",
                  "vw_instance_counts_src", 
                  "vw_latest_session_activity",
                  "vw_reports_document_activity", 
                  "vw_reports_document_views", 
                  "vw_reports_session_activity",
                  "vw_reports_user_searches", 
                  "vw_stat_cited_crosstab",
                  "vw_stat_cited_crosstab_with_details",
                  "vw_stat_cited_in_all_years",
                  "vw_stat_cited_in_last_5_years",
                  "vw_stat_cited_in_last_10_years",
                  "vw_stat_cited_in_last_20_years",
                  "vw_stat_docviews_crosstab",
                  "vw_stat_docviews_last12months",
                  "vw_stat_docviews_lastmonth",
                  "vw_stat_docviews_lastsixmonths",
                  "vw_stat_docviews_lastweek",
                  "vw_stat_most_viewed",
                  "vw_stat_to_update_solr_docviews",
                  # "vw_stat_docviews_lastcalyear" # for now, nothing from last year
                  ]

        for table in tables:              
            curs = ocd.db.cursor(pymysql.cursors.DictCursor)
            sql = f"SELECT * from {table} LIMIT 10;" 
            try:
                cursed = curs.execute(sql)
                print (f"Found {cursed} rows (limit was 10)")
                sourceData = curs.fetchall()
                assert (len(sourceData) >= 1)
            except:
                print (f"Exception: can't query table {table}")
                assert (False)

        ocd.close_connection(caller_name="test_views") # make sure connection is closed

        
        
if __name__ == '__main__':
    
    unittest.main()
    print ("Tests Complete.")