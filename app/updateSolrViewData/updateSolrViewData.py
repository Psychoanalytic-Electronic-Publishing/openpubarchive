#!/usr/bin/env python
# -*- coding: utf-8 -*-
# To run:
#     python3 updateSolrviewData

print(
    """
    UpdateSolrViewData - Program to update the view and citation stat fields in the pepwebdocs
      database.
      
      By default, it only updates records which have views data.

      If you use command line option --all, it will add all citation and views data to the
        pepwebdocs data.  (This takes significantly longer.)
        
      Caution: Solr can be finicky and reject these updates presumably because the records
         being updated have child records.
         
         Two prerequisites for best chances of success:
            1) Initial clean install of Solr
            2) Solr 8.6 or newer
      
         - To be safe, the first update should be with option --all
         - Then views should be updated daily
         - Citations only need be updated bi-weekly (views will be done automatically
            at the same time)

      The records added are controlled by the database views:
         vw_stat_to_update_solr_docviews
         vw_stat_cited_crosstab
    """
)
__author__      = "Neil R. Shapiro"
__copyright__   = "Copyright 2020, Psychoanalytic Electronic Publishing"
__license__     = "Apache 2.0"
__version__     = "2020.0905.1"
__status__      = "Testing"

import sys
sys.path.append('../config')

UPDATE_AFTER = 2500

import logging
import time
import pymysql
import pysolr
import localsecrets
from pydantic import BaseModel

from datetime import datetime
programNameShort = "updateSolrviewData"  # used for log file
logFilename = programNameShort + "_" + datetime.today().strftime('%Y-%m-%d') + ".log"
FORMAT = '%(asctime)s %(name)s %(funcName)s %(lineno)d - %(levelname)s %(message)s'
logging.basicConfig(filename=logFilename, format=FORMAT, level=logging.ERROR, datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(programNameShort)
start_notice = f"Started at {datetime.today().strftime('%Y-%m-%d %H:%M:%S')}. Logfile {logFilename}"
print (start_notice)
logger.info(start_notice)

unified_article_stat = {}

class ArticleStat(BaseModel):
    document_id: str = None
    art_views_update: bool = False
    art_views_lastcalyear: int = 0
    art_views_last12mos: int = 0
    art_views_last6mos: int = 0
    art_views_last1mos: int = 0
    art_views_lastweek: int = 0
    art_cited_5: int = 0
    art_cited_10: int = 0
    art_cited_20: int = 0
    art_cited_all: int = 0

class MostCitedArticles(BaseModel):
    """
    __Table vw_stat_cited_crosstab__

    A view with rxCode counts derived from the fullbiblioxml table and the articles table
      for citing sources in one of the date ranges.
      
    Definition copied to keep this independent, from GitHub\openpubarchive\app\libs\modelsOpasCentralPydantic.py   
    """
    document_id: str = None
    countAll: int = 0
    count5: int = 0
    count10: int = 0
    count20: int = 0

class opasCentralDBMini(object):
    """
    This object should be used and then discarded on an endpoint by endpoint basis in any
      multiuser mode.
      
    Therefore, keeping session info in the object is ok,
    """
    def __init__(self, session_id=None, access_token=None, token_expires_time=None, username="NotLoggedIn", user=None):
        self.db = None
        self.connected = False
        #self.authenticated = False
        #self.session_id = session_id
        #self.access_token = access_token
        #self.user = None
        #self.sessionInfo = None
        
    def open_connection(self, caller_name=""):
        """
        Opens a connection if it's not already open.
        
        If already open, no changes.
        >>> ocd = opasCentralDB()
        >>> ocd.open_connection("my name")
        True
        >>> ocd.close_connection("my name")
        """
        try:
            status = self.db.open
            self.connected = True
        except:
            # not open reopen it.
            status = False
        
        if status == False:
            #  not tunneled
            try:
                self.db = pymysql.connect(host=localsecrets.DBHOST, port=localsecrets.DBPORT, user=localsecrets.DBUSER, password=localsecrets.DBPW, database=localsecrets.DBNAME)
                logger.debug(f"Database opened by ({caller_name}) Specs: {localsecrets.DBNAME} for host {localsecrets.DBHOST},  user {localsecrets.DBUSER} port {localsecrets.DBPORT}")
                self.connected = True
            except Exception as e:
                err_str = f"Cannot connect to database {localsecrets.DBNAME} for host {localsecrets.DBHOST},  user {localsecrets.DBUSER} port {localsecrets.DBPORT} ({e})"
                print(err_str)
                logger.error(err_str)
                self.connected = False
                self.db = None

        return self.connected

    def close_connection(self, caller_name=""):
        if self.db is not None:
            try:
                if self.db.open:
                    self.db.close()
                    self.db = None
                    logger.debug(f"Database closed by ({caller_name})")
                else:
                    logger.debug(f"Database close request, but not open ({caller_name})")
                    
            except Exception as e:
                logger.error(f"caller: {caller_name} the db is not open ({e})")

        # make sure to mark the connection false in any case
        self.connected = False           

    def get_most_viewed_crosstab(self):
        """
         Using the opascentral api_docviews table data, as dynamically statistically aggregated into
           the view vw_stat_most_viewed return the most downloaded (viewed) documents
           
        """
        ret_val = None
        row_count = 0
        # always make sure we have the right input value
        self.open_connection(caller_name="get_most_viewed_crosstab") # make sure connection is open
        
        if self.db is not None:
            cursor = self.db.cursor(pymysql.cursors.DictCursor)
            sql = """SELECT DISTINCTROW * FROM vw_stat_to_update_solr_docviews"""
            row_count = cursor.execute(sql)
            if row_count:
                ret_val = cursor.fetchall()
            cursor.close()
        else:
            logger.fatal("Connection not available to database.")
        
        self.close_connection(caller_name="get_most_downloaded_crosstab") # make sure connection is closed
        return row_count, ret_val

    def get_citation_counts(self) -> dict:
        """
         Using the opascentral vw_stat_cited_crosstab view, based on the api_biblioxml which is used to detect citations,
           return the cited counts for each art_id
           
        """
        citation_table = []
        print ("Collecting citation counts from cross-tab in biblio database...this will take a minute or two...")
        try:
            self.open_connection("collect_citation_counts")
            # Get citation lookup table
            try:
                cursor = self.db.cursor(pymysql.cursors.DictCursor)
                sql = """
                      SELECT cited_document_id, count5, count10, count20, countAll from vw_stat_cited_crosstab; 
                      """
                success = cursor.execute(sql)
                if success:
                    citation_table = cursor.fetchall()
                    cursor.close()
                else:
                    logger.error("Cursor execution failed.  Can't fetch.")
                    
            except MemoryError as e:
                print(("Memory error loading table: {}".format(e)))
            except Exception as e:
                print(("Table Query Error: {}".format(e)))
            
            self.close_connection("collect_citation_counts")
            
        except Exception as e:
            print(("Database Connect Error: {}".format(e)))
            citation_table["dummy"] = MostCitedArticles()
        
        return citation_table


#----------------------------------------------------------------------------------------
#  End OpasCentralDBMini
#----------------------------------------------------------------------------------------
def load_unified_article_stat():
    ocd =  opasCentralDBMini()
    # load most viewed data
    count, most_viewed = ocd.get_most_viewed_crosstab()
    # load citation data
    citation_table = ocd.get_citation_counts()

    # integrate data into article_stat
    for n in citation_table:
        try:
            doc_id = n.get("cited_document_id", None)
        except Exception as e:
            logger.error("no document id")
        else:
            unified_article_stat[doc_id] = ArticleStat(
                art_cited_5 = n.get("count5", 0), 
                art_cited_10 = n.get("count10", 0), 
                art_cited_20 = n.get("count20", 0), 
                art_cited_all = n.get("countAll", 0)
            ) 

    for n in most_viewed:
        doc_id = n.get("document_id", None)
        if doc_id is not None:
            try:
                unified_article_stat[doc_id].art_views_update = True
                unified_article_stat[doc_id].art_views_lastcalyear = n.get("lastcalyear", None)
                unified_article_stat[doc_id].art_views_last12mos = n.get("last12months", None) 
                unified_article_stat[doc_id].art_views_last6mos = n.get("last6months", None) 
                unified_article_stat[doc_id].art_views_last1mos = n.get("lastmonth", None)
                unified_article_stat[doc_id].art_views_lastweek = n.get("lastweek", None)
            except KeyError:
                unified_article_stat[doc_id] = ArticleStat()
                unified_article_stat[doc_id].art_views_update = True
                unified_article_stat[doc_id].art_views_lastcalyear = n.get("lastcalyear", None)
                unified_article_stat[doc_id].art_views_last12mos = n.get("last12months", None) 
                unified_article_stat[doc_id].art_views_last6mos = n.get("last6months", None) 
                unified_article_stat[doc_id].art_views_last1mos = n.get("lastmonth", None)
                unified_article_stat[doc_id].art_views_lastweek = n.get("lastweek", None)
                
def update_solr_stat_data(solrcon, all_records:bool=False):
    """
    Use in-place updates to update the views data
    """
    print (f"Loading records into Solr table.")
    update_count = 0
    skipped_as_update_error = 0
    skipped_as_missing = 0
    
    for key, art_stat in unified_article_stat.items():
        if all_records==False:
            if not art_stat.art_views_update:
                continue

        # set only includes those with the desired update value > 0 
        #   (see RDS vw_stat_to_update_solr_docviews to change criteria)
        doc_id = key
        found = False
        try:
            results = solrcon.search(q = f"art_id:{doc_id}")
            if results.raw_response["response"]["numFound"] > 0:
                found = True
        except Exception as e:
            logger.debug(f"Document {doc_id} not in Solr...skipping")
            skipped_as_missing += 1
        else:
            if found:
                #logger.info("Document in Solr...trying to update")
                if doc_id is not None:
                    upd_rec = {
                                "id":doc_id,
                                "art_cited_5": art_stat.art_cited_5, 
                                "art_cited_10": art_stat.art_cited_10, 
                                "art_cited_20": art_stat.art_cited_20, 
                                "art_cited_all": art_stat.art_cited_all, 
                                "art_views_lastcalyear": art_stat.art_views_lastcalyear, 
                                "art_views_last12mos": art_stat.art_views_last12mos, 
                                "art_views_last6mos": art_stat.art_views_last6mos, 
                                "art_views_last1mos": art_stat.art_views_last1mos, 
                                "art_views_lastweek": art_stat.art_views_lastweek
                    }                    
        
                    try:
                        solrcon.add([upd_rec], fieldUpdates={
                                                             "art_cited_5": 'set',
                                                             "art_cited_10": 'set',
                                                             "art_cited_20": 'set',
                                                             "art_cited_all": 'set',
                                                             "art_views_lastcalyear": 'set',
                                                             "art_views_last12mos": 'set',
                                                             "art_views_last6mos": 'set',
                                                             "art_views_last1mos": 'set',
                                                             "art_views_lastweek": 'set'
                                                             })
        
                        if update_count > 0 and update_count % UPDATE_AFTER == 0:
                            solr_docs2.commit()
                            errStr = f"updated {update_count} records with citation data"
                            print (errStr)
                            logger.warning(errStr)
                        
                    except Exception as err:
                        errStr = f"Solr call exception for update on {doc_id}: {err}"
                        print (errStr)
                        skipped_as_update_error += 1
                        logger.error(errStr)
                    else:
                        update_count += 1

    #  final commit
    try:
        solr_docs2.commit()
    except Exception as e:
        msg = f"Final commit error {e}"
        print(msg)
        logger.error(msg)

    logger.warning(f"Finished updating Solr stat with {update_count} article records updated; records skippted: {skipped_as_update_error }.")
    return update_count

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser() 
    parser.add_argument('--version', action='version',
                        version='%(prog)s {version}'.format(version=__version__))    
    parser.add_argument('--verbose', '-v', action='count', default=1, help="Multiple v's for more verbosity, e.g., -vvv")
    parser.add_argument("-a", "--all", dest="all_records", default=False, action="store_true",
                        help="Update records with views and any citation data (takes significantly longer)")
    
    args = parser.parse_args()
    args.verbose = 40 - (10*args.verbose) if args.verbose > 0 else 0
    logging.basicConfig(filename=logFilename, level=args.verbose)

    updates = 0
    SOLR_DOCS = "pepwebdocs"
    solrurl_docs = localsecrets.SOLRURL + SOLR_DOCS  
    if localsecrets.SOLRUSER is not None and localsecrets.SOLRPW is not None:
        solr_docs2 = pysolr.Solr(solrurl_docs, auth=(localsecrets.SOLRUSER, localsecrets.SOLRPW))
    else: #  no user and password needed
        solr_docs2 = pysolr.Solr(solrurl_docs)
    start_time = time.time()
    load_unified_article_stat()
    updates = update_solr_stat_data(solr_docs2, args.all_records)
    total_time = time.time() - start_time
    final_stat = f"{time.ctime()} Updated {updates} Solr records in {total_time} secs)."
    logging.getLogger().setLevel(logging.INFO)
    logger.info(final_stat)
    print (final_stat)
        
