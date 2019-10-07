#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Initial version of the Opas Solr Server (API) 

This API server is based on the existing PEP-Web API 1.0.  The data returned 
may have additional fields but should be otherwise compatible with PEP API clients
such as PEP-Easy.

2019.0904.1 - Started conversion to snake_case...
2019.0617.1 - First version with 6 endpoints, 5 set up for Pydantic and one not yet
                converted - nrs
2019.0617.4 - Changed functions under decorators to snake case since the auto doc uses those 
              as sentences!
              
2019.0816.1 - Figured out that I need to return the same model in case of error. 
              Responseinfo has errors which is a struct with error messages.
              Setting resp.status_code returns the error code.
              
              EXAMPLE in get_the_author_index_entries_for_matching_author_names
                      Returns the error correctly when Solr is not running.
                      USE THAT AS A TEMPLATE.
              
              #TODO: This now needs to be done to each end point.


Run with:
    uvicorn server:app --reload
    
    or for debug:
    
    uvicorn main:app --debug --log-level=debug
 
(Debug set up in this file as well: app = FastAPI(debug=True))
                
Supports:
   /v1/Metadata/MostCited
   /v1/Metadata/Contents/{SourceCode}
   /v1/Metadata/Volumes/{SourceCode}
   /v1/Authors/Index/{authorNamePartial}
   /v1/Authors/Publications/{authorNamePartial}
   
   and this preliminary, not yet ported to Pydantic

   ​/Documents​/Abstracts​/{documentID}​/Getabstract
   
Endpoint and structure documentation automatically available when server is running at:

  http://127.0.0.1:8000/docs

(base URL + "/docs")

"""

__author__      = "Neil R. Shapiro"
__copyright__   = "Copyright 2019, Psychoanalytic Electronic Publishing"
__license__     = "Apache 2.0"
__version__     = "2019.0906.1"
__status__      = "Development"

import sys
sys.path.append('./config')
sys.path.append('./libs')

import time
import datetime
from datetime import datetime
import re
import secrets
# import json
from urllib import parse
# from http import cookies

from enum import Enum
import uvicorn
from fastapi import FastAPI, Query, Path, Cookie, Header, Depends, HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, RedirectResponse
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.status import HTTP_200_OK, \
                             HTTP_400_BAD_REQUEST, \
                             HTTP_401_UNAUTHORIZED, \
                             HTTP_403_FORBIDDEN, \
                             HTTP_500_INTERNAL_SERVER_ERROR, \
                             HTTP_503_SERVICE_UNAVAILABLE

from fastapi.security import HTTPBasic, HTTPBasicCredentials

app = FastAPI()


from pydantic import BaseModel
from pydantic.types import EmailStr
from pydantic import ValidationError

import solrpy as solr
import json
import logging
logger = logging.getLogger(__name__)

from config.localsecrets import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
import jwt
import localsecrets as localsecrets
import localsecrets
import libs.opasConfig as opasConfig

import libs.opasAPISupportLib as opasAPISupportLib
import libs.opasBasicLoginLib as opasBasicLoginLib
#from libs.opasBasicLoginLib import get_current_user

from errorMessages import *
import models
import modelsOpasCentralPydantic
import opasCentralDBLib
from sourceInfoDB import SourceInfoDB

sourceInfoDB = SourceInfoDB()
# gActiveSessions = {}

#gOCDatabase = None # opasCentralDBLib.opasCentralDB()
CURRENT_DEVELOPMENT_STATUS = "Developing"

#def getSession():
    #if currentSession == None:
        #currentSession = modelsOpasCentralPydantic.Session()

app = FastAPI(
        debug=True,
        title="OPAS API for PEP-Web",
        description = "Open Publications Archive Software API",
        version = "1.0.0.Alpha",
        static_directory=r"./docs",
        swagger_static={
            "favicon": "pepfavicon.gif"
        },
    )

#app.add_middleware(SessionMiddleware,
                   #secret_key = secrets.token_urlsafe(16),
                   #session_cookie = secrets.token_urlsafe(16)
    #)

#origins = [
    #"http://pepeasy.pep-web.info",
    #"http://api.pep-web.info",
    #"http://pep-web.info",
    #"http://*.pep-web.info",
    #"http://localhost",
    #"http://development",
    #"http://localhost:8080",
    #"http://webfaction",
    #"http://127.0.0.1",
    #"http://127.0.0.1:8000",
    #"http://api.mypep.info",
    #"http://www.pep-web.info"
#]

origins = [
    "http://development",
    "http://development.org",
    "http://.development.org",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger.info('Started at %s', datetime.today().strftime('%Y-%m-%d %H:%M:%S"'))

#def getExpirationCookieStr(keepActive=False):
    #max_age = opasAPISupportLib.getMaxAge(keepActive)
    #ret_val = datetime.utcfromtimestamp(time.time() + max_age).strftime('%Y-%m-%d %H:%M:%S')
    #return ret_val #expiration cookie str

def check_if_user_logged_in(request:Request, 
                        response:Response):
    """
    
    """
    #TBD: Should just check token cookie here.
    ret_val = login_user(response, request)
    return ret_val.LoginReturnItem.authenticated  #  this may not be right.

#-----------------------------------------------------------------------------
@app.get("/v2/Admin/SessionCleanup/", response_model=models.ServerStatusItem, tags=["Admin"])
def cleanup_sessions(resp: Response, 
                          request: Request=Query(None, title="HTTP Request", description=opasConfig.DESCRIPTION_REQUEST) 
                          ):
    """
    Clean up old, open sessions (may only be needed during development
    
    Status: In Development
    """
    ocd, session_info = opasAPISupportLib.get_session_info(request, resp)   
    #TODO: Check if user is admin
    ocd.ocd.retire_expired_sessions()
    ocd.close_expired_sessions()
    ocd.close_connection()

    try:
        serverStatusItem = None
    except ValidationError as e:
        print(e.json())             
    
    
    return serverStatusItem



#-----------------------------------------------------------------------------
@app.get("/v2/Admin/Status/", response_model=models.ServerStatusItem, tags=["Session"])
def get_the_server_status(resp: Response, 
                          request: Request=Query(None, title="HTTP Request", description=opasConfig.DESCRIPTION_REQUEST) 
                          ):
    """
    Return the status of the database and text server
    
    Status: In Development
    """
    ocd, session_info = opasAPISupportLib.get_session_info(request, resp)   

    solr_ok = opasAPISupportLib.check_solr_docs_connection()
    db_ok = ocd.open_connection()
    ocd.close_connection()

    try:
        server_status_item = models.ServerStatusItem(text_server_ok = solr_ok, 
                                                   db_server_ok = db_ok,
                                                   user_ip = request.client.host,
                                                   solr_url = localsecrets.SOLRURL,
                                                   config_name = localsecrets.CONFIG,
                                                   timeStamp = datetime.utcfromtimestamp(time.time()).strftime('%Y-%m-%dT%H:%M:%SZ')  
                                          )
    except ValidationError as e:
        print(e.json())             
    
    
    return server_status_item

#-----------------------------------------------------------------------------
@app.get("/v2/Admin/WhoAmI/", tags=["Admin"])
def who_am_i(resp: Response,
             request: Request):
    """
    Temporary endpoint for debugging purposes
    """
    return {"client_host": request.client.host, 
            "referrer": request.headers.get('referrer', None), 
            "opasSessionID": request.cookies.get("opasSessionID", None), 
            "opasAccessToken": request.cookies.get("opasAccessToken", None),
            "opasSessionExpire": request.cookies.get("opasSessionExpire", None), 
            }

#-----------------------------------------------------------------------------
@app.get("/v2/Admin/WhoAmIGit/", tags=["Admin"])
def who_am_i2(resp: Response,
             request: Request):
    """
    Temporary endpoint for debugging purposes
    """
    return {"client_host": request.client.host, 
            "referrer": request.headers.get('referrer', None), 
            "opasSessionID": request.cookies.get("opasSessionID", None), 
            "opasAccessToken": request.cookies.get("opasAccessToken", None),
            "opasSessionExpire": request.cookies.get("opasSessionExpire", None), 
            }


#-----------------------------------------------------------------------------
security = HTTPBasic()
def get_current_username(resp: Response, 
                         request: Request,
                         credentials: HTTPBasicCredentials = Depends(security)):

    ocd, session_info = opasAPISupportLib.get_session_info(request, resp)   
    status, user = ocd.authenticate_user(credentials.username, credentials.password)
    if not user:
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return user

@app.get("/v2/Token/", tags=["Session"], description="Used for Basic Authentication")
def read_current_user(resp: Response, 
                      request: Request,
                      user: str = Depends(get_current_username), 
                      ka=False):

    session_id = opasAPISupportLib.get_session_id(request)
    access_token = opasAPISupportLib.get_access_token(request)
    expiration_time = datetime.utcfromtimestamp(time.time() + opasAPISupportLib.get_max_age(keep_active=ka))
    if session_id is not None and access_token is not None:
        pass
    else:
        if user:
            # user is authenticated
            # we need to close any open sessions.
            if session_id is not None and access_token is not None:
                # do a logout
                session_end_time = datetime.utcfromtimestamp(time.time())
                success = ocd.update_session(session_id=session_id, 
                                            session_end=session_end_time
                                            )    
    
            # NOW lets give them a new session
            # new session and then token
            session_id = secrets.token_urlsafe(16)
            max_age = opasAPISupportLib.get_max_age(ka)
            user.start_date = user.start_date.timestamp()  # we may just want to null these in the jwt
            user.end_date = user.end_date.timestamp()
            user.last_update = user.last_update.timestamp()
            access_token = jwt.encode({'exp': expiration_time.timestamp(), 'user': user.dict()}, SECRET_KEY, algorithm='HS256')
            # start a new session, with this user (could even still be the old user
            ocd, session_info = opasAPISupportLib.start_new_session(resp, request, session_id=session_id, access_token=access_token, user=user)
            # set accessTokenCookie!
            opasAPISupportLib.set_cookies(resp, session_id, accessToken=access_token, maxAge=max_age) #tokenExpiresTime=expirationTime)
        else: # Can't log in!
            raise HTTPException(
                status_code=HTTP_401_UNAUTHORIZED, 
                detail="Bad credentials"
            )
       
    try:
        loginReturnItem = models.LoginReturnItem(token_type = "bearer", 
                                                 session_id = session_id,
                                                 access_token = access_token,
                                                 authenticated = access_token is not None,
                                                 session_expires_time = expiration_time,
                                                 keep_active = ka,
                                                 error_message = None,
                                                 scope = None
                                          )
    except ValidationError as e:
        print(e.json())             

    return loginReturnItem
    
#-----------------------------------------------------------------------------
#@app.get("/v1/Session/") # at least start a session (getting a sessionID)
@app.get("/v1/Token/", tags=["Session"], description="Used by PEP-Easy to login; will be deprecated in V2")  
def get_token(resp: Response, 
              request: Request,
              grant_type=None, 
              username=None, 
              password=None, 
              ka=False):
    """
    Get the current sessionID, or generate one.  User by PEP-Easy from v1
    """
    ocd, session_info = opasAPISupportLib.get_session_info(request, resp)
    if grant_type=="password" and username is not None and password is not None:
        login_return_item = login_user(resp, request, grant_type, username, password, ka)
        return login_return_item
    else:
        err_code = resp.status_code = HTTP_400_BAD_REQUEST
        err_return = models.ErrorReturn(error = ERR_CREDENTIALS, error_message = ERR_MSG_INSUFFICIENT_INFO)
        return err_return

#-----------------------------------------------------------------------------
@app.get("/v1/License/Status/Login/", tags=["Session"])
def get_license_status(resp: Response, 
                       request: Request=Query(None, title="HTTP Request", description=opasConfig.DESCRIPTION_REQUEST)):
    """
    Return a LicenseStatusInfo object showing the user's license status info.
    {
        "licenseInfo": {
            "responseInfo": {
                "loggedIn": true,
                "username": "p.e.p.a.NeilRShapiro",
                "request": "\/api\/v1\/License\/Status\/Login",
                "timeStamp": "2019-07-09T09:54:10-04:00"
            },
            "responseSet": null
        }
    }
    """
    # get session info database record if there is one
    ocd, session_info = opasAPISupportLib.get_session_info(request, resp)
    session_id = session_info.session_id
    # is the user authenticated? if so, loggedIn is true
    logged_in = session_info.authenticated
    user_id = session_info.user_id
    username = None
    user = None
    if user_id == 0:
        user = ocd.get_user(userID=user_id)
        username = "NotLoggedIn"
        logged_in = False
    elif user_id is not None:
        user = ocd.get_user(userID=user_id)
        user.password = "Hidden"
        username = user.username
    
    print (user_id, user)
    # hide the password hash
    response_info = models.ResponseInfoLoginStatus(loggedIn = logged_in,
                                                  username = username,
                                                  request = request.url._url,
                                                  user=user,
                                                  timeStamp = datetime.utcfromtimestamp(time.time()).strftime('%Y-%m-%dT%H:%M:%SZ')
                                                  )
    
    license_info_struct = models.LicenseInfoStruct(responseInfo = response_info, 
                                                   responseSet = None
                                                  )
    
    license_info = models.LicenseStatusInfo(licenseInfo = license_info_struct)
    return license_info

#-----------------------------------------------------------------------------
@app.get("/v1/Login/", tags=["Session"])
def login_user(resp: Response, 
               request: Request=Query(None, title="HTTP Request", description=opasConfig.DESCRIPTION_REQUEST),
               grant_type=None, 
               username=None, 
               password=None, 
               ka=False, 
               #user: bool = Depends(get_current_user)
               ):
    """
    Login the user, via the URL per the GVPi API/PEPEasy interaction.
    
    Needed to support the original version of the PEP API.
    
    This may not be a good secure way to login.  May be deprecated 
       after the move from the GVPi server.  Newer clients
       should use the newer methods, when they are implemented
       in this new sever.
    
    Params: 
    
    
    TODO: Need to figure out the right way to do timeouts for this "easy" login.
          
    """
    print ("Login via: /v1/(Users)?/Login/", username, password)
    
    session_id = opasAPISupportLib.get_session_id(request)
    access_token = opasAPISupportLib.get_access_token(request)
    expirationTime = datetime.utcfromtimestamp(time.time() + opasAPISupportLib.get_max_age(keep_active=ka))
    print ("Login Request: Expiration Time: {expirationTime}")

    # if username and password are not supplied, uses browser basic auth via the Depends(get_current_user)
    if username is not None and password is not None:
        ocd = opasCentralDBLib.opasCentralDB()    
        # now try to login (authenticate)
        status, user = ocd.authenticate_user(username, password)
        if user:
            # user is authenticated
            # we need to close any open sessions.
            if session_id is not None and access_token is not None:
                # do a logout
                session_end_time = datetime.utcfromtimestamp(time.time())
                success = ocd.update_session(session_id=session_id, 
                                             session_end=session_end_time
                                            )    
                #opasAPISupportLib.deleteCookies(resp, session_id="", accessToken="")

            # NOW lets give them a new session
            # new session and then token
            session_id = secrets.token_urlsafe(16)
            max_age = opasAPISupportLib.get_max_age(ka)
            user.start_date = user.start_date.timestamp()  # we may just want to null these in the jwt
            user.end_date = user.end_date.timestamp()
            user.last_update = user.last_update.timestamp()
            access_token = jwt.encode({'exp': expirationTime.timestamp(), 'user': user.dict()}, SECRET_KEY, algorithm='HS256')
            # start a new session, with this user (could even still be the old user
            ocd, sessionInfo = opasAPISupportLib.start_new_session(resp, request, session_id=session_id, access_token=access_token, user=user)
            # set accessTokenCookie!
            opasAPISupportLib.set_cookies(resp, session_id, accessToken=access_token, maxAge=max_age) #tokenExpiresTime=expirationTime)
            err_code = None
        else:
            access_token = None # user rejected
            err_code = resp.status_code = HTTP_400_BAD_REQUEST
            err_return = models.ErrorReturn(error = ERR_CREDENTIALS, error_message = ERR_MSG_LOGIN_CREDENTIALS)
     
    else: # Can't log in!
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED, 
            detail="Bad credentials"
        )
    
    # this simple return without responseInfo matches the GVPi server return.
    if err_code != None:
        return err_return
    else:
        try:
            login_return_item = models.LoginReturnItem(token_type = "bearer", 
                                                       session_id = session_id,
                                                       access_token = access_token,
                                                       authenticated = access_token is not None,
                                                       session_expires_time = expirationTime,
                                                       keep_active = ka,
                                                       error_message = None,
                                                       scope = None
                                                      )
        except ValidationError as e:
            print(e.json())             

        return login_return_item

#-----------------------------------------------------------------------------
#@app.get("/v1/Users/Logout/") # I like it under Users so I did them both.
@app.get("/v1/Logout/", tags=["Session"])  # The original GVPi URL
def logout_user(resp: Response, 
                request: Request=Query(None, title="HTTP Request", description=opasConfig.DESCRIPTION_REQUEST)):
    """
    Close the user's session, and log them out.
    
    /v1/Logout/ is used by the GVPi/PEPEasy current config.
                It can be removed when we move off the GVPi server.
                              
    /v1/Users/Logout/ is the newer path, parallels logout /v1/Users/Login/ for clarity.
    

    """

    session_id = opasAPISupportLib.get_session_id(request)
    ocd = opasCentralDBLib.opasCentralDB()
    errCode = None
    if session_id is not None:
        session_info = ocd.get_session_from_db(session_id)
        session_end_time = datetime.utcfromtimestamp(time.time())
        success = ocd.update_session(session_id=session_id, 
                                     session_end=session_end_time
                                    )    
        if not success:
            #responseInfo = models.ResponseInfoLoginStatus(session_id = session_id)
            err_return = models.ErrorReturn(error = ERR_CONDITIONS, error_message = ERR_MSG_RECOVERABLE_CONDITION + " (SSave)")
            response_info = models.ResponseInfoLoginStatus(session_id = session_id, errors = err_return)
        else:    # all is well.
            response_info = models.ResponseInfoLoginStatus(sessionID = session_id)
            response_info.loggedIn = False
            opasAPISupportLib.delete_cookies(resp, sessionID="", accessToken="")
    else:
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail=ERR_MSG_LOGOUT_UNSUPPORTED
        )

    if errCode != None:
        return err_return
    else:
        license_info_struct = models.LicenseInfoStruct( responseInfo = response_info, 
                                                        responseSet = []
                                                      )
        license_info = models.LicenseStatusInfo(licenseInfo = license_info_struct)
        return license_info

#---------------------------------------------------------------------------------------------------------
# this function lets various endpoints like search, searchanalysis, and document, share this large parameter set.
def parse_search_query_parameters(search=None,
                               journal_name=None,
                               journal=None,
                               fulltext1=None,
                               fulltext2=None,
                               vol=None,
                               issue=None,
                               author=None,
                               title=None,
                               datetype=None,
                               startyear=None,
                               endyear=None,
                               dreams=None,
                               quotes=None,
                               abstracts=None,
                               dialogs=None,
                               references=None,
                               citecount=None, 
                               viewcount=None, 
                               viewedWithin=None, 
                               solrQ=None, 
                               disMax=None, 
                               edisMax=None, 
                               quick_search=None, 
                               sort=None, 
                            ):

    # initialize accumulated variables
    searchQ = "*:* "
    filterQ = "*:* "
    analyze_this = ""
    solr_max = None
    search_analysis_term_list = []
    
    if sort is not None:  # not sure why this seems to have a slash, but remove it
        sort = re.sub("\/", "", sort)
        
    if title is not None:
        analyze_this = "&& art_title_xml:{} ".format(title)
        filterQ += analyze_this
        search_analysis_term_list.append(analyze_this)  
    
    if journal_name is not None:
        analyze_this = "&& art_pepsourcetitle_fulltext:{} ".format(journal_name)
        filterQ += analyze_this
        search_analysis_term_list.append(analyze_this)  
        
    if journal is not None:
        code_for_query = ""
        analyze_this = ""
        # journal_code_list_pattern = "((?P<namelist>[A-z0-9]*[ ]*\+or\+[ ]*)+|(?P<namelist>[A-z0-9]))"
        journal_wildcard_pattern = r".*\*[ ]*"  # see if it ends in a * (wildcard)
        if re.match(journal_wildcard_pattern, journal):
            # it's a wildcard pattern
            code_for_query = journal
            analyze_this = "&& art_pepsourcetitlefull:{} ".format(code_for_query)
            filterQ += analyze_this
        else:
            journalCodeList = journal.split(" or ")
            if len(journalCodeList) > 1:
                # it was a list.
                code_for_query = " OR ".join(journalCodeList)
                analyze_this = "&& (art_pepsrccode:{}) ".format(code_for_query)
                filterQ += analyze_this
            else:
                sourceInfo = sourceInfoDB.lookupSourceCode(journal.upper())
                if sourceInfo is not None:
                    # it's a single source code
                    code_for_query = journal.upper()
                    analyze_this = "&& art_pepsrccode:{} ".format(code_for_query)
                    filterQ += analyze_this
                else: # not a pattern, or a code, or a list of codes.
                    # must be a name
                    code_for_query = journal
                    analyze_this = "&& art_pepsourcetitlefull:{} ".format(code_for_query)
                    filterQ += analyze_this
        
        search_analysis_term_list.append(analyze_this)
        # or it could be an abbreviation #TODO
        # or it counld be a complete name #TODO
            
    if vol is not None:
        analyze_this = "&& art_vol:{} ".format(vol)
        filterQ += analyze_this
        #searchAnalysisTermList.append(analyzeThis)  # Not collecting this!
        
    if issue is not None:
        analyze_this = "&& art_iss:{} ".format(issue)
        filterQ += analyze_this
        #searchAnalysisTermList.append(analyzeThis)  # Not collecting this!
            
    if author is not None:
        author = author.replace('"', '')
        analyze_this = "&& art_authors_xml:{} ".format(author)
        filterQ += analyze_this
        search_analysis_term_list.append(analyze_this)  
    
    if datetype is not None:
        #TODO for now, lets see if we need this. (We might)
        pass
    
    if startyear is not None and endyear is None:
        # put this in the filter query
        # parse startYear
        parsed_year_search = opasAPISupportLib.year_arg_parser(startyear)
        if parsed_year_search is not None:
            filterQ += parsed_year_search
            search_analysis_term_list.append(parsed_year_search)  
        else:
            logger.info("Search - StartYear bad argument {}".format(startyear))
        
    if startyear is not None and endyear is not None:
        # put this in the filter query
        # should check to see if they are each dates
        if re.match("[12][0-9]{3,3}", startyear) is None or re.match("[12][0-9]{3,3}", endyear) is None:
            logger.info("Search - StartYear {} /Endyear {} bad arguments".format(startyear, endyear))
        else:
            analyze_this = "&& art_year_int:[{} TO {}] ".format(startyear, endyear)
            filterQ += analyze_this
            search_analysis_term_list.append(analyze_this)
    
    if startyear is None and endyear is not None:
        if re.match("[12][0-9]{3,3}", endyear) is None:
            logger.info("Search - Endyear {} bad argument".format(endyear))
        else:
            analyze_this = "&& art_year_int:[{} TO {}] ".format("*", endyear)
            filterQ += analyze_this
            search_analysis_term_list.append(analyze_this)
    
    if citecount is not None:
        # This is the only query handled by GVPi and the current API.  But
        # the Solr database is set up so this could be easily extended to
        # the 10, 20, and "all" periods.  Here we add syntax to the 
        # citecount field, to allow the user to say:
        #  25 in 10 
        # which means 25 citations in 10 years
        # or 
        #  400 in ALL
        # which means 400 in all years. 
        # 'in' is required along with a space in front of it and after it
        # when specifying the period.
        # the default period is 5 years.
        match_ptn = "(?P<nbr>[0-9]+)(\s+IN\s+(?P<period>(5|10|20|All)))?"
        m = re.match(match_ptn, citecount, re.IGNORECASE)
        if m is not None:
            val = m.group("nbr")
            period = m.group("period")
    
        if val is None:
            val = 1
        if period is None:
            period = '5'
            
        analyze_this = "&& art_cited_{}:[{} TO *] ".format(period.lower(), val)
        filterQ += analyze_this
        search_analysis_term_list.append(analyze_this)
    
    if fulltext1 is not None:
        analyze_this = "&& text:{} ".format(fulltext1)
        searchQ += analyze_this
        search_analysis_term_list.append(analyze_this)
    
    if fulltext2 is not None:
        analyze_this = "&& text:{} ".format(fulltext2)
        searchQ += analyze_this
        search_analysis_term_list.append(analyze_this)
    
    if dreams is not None:
        analyze_this = "&& dreams_xml:{} ".format(dreams)
        searchQ += analyze_this
        search_analysis_term_list.append(analyze_this)
    
    if quotes is not None:
        analyze_this = "&& quotes_xml:{} ".format(quotes)
        searchQ += analyze_this
        search_analysis_term_list.append(analyze_this)
    
    if abstracts is not None:
        analyze_this = "&& abstracts_xml:{} ".format(abstracts)
        searchQ += analyze_this
        search_analysis_term_list.append(analyze_this)
    
    if dialogs is not None:
        analyze_this = "&& dialogs_xml:{} ".format(dialogs)
        searchQ += analyze_this
        search_analysis_term_list.append(analyze_this)
    
    if references is not None:
        analyze_this = "&& references_xml:{} ".format(references)
        searchQ += analyze_this
        search_analysis_term_list.append(analyze_this)
    
    if solrQ is not None:
        searchQ = solrQ # (overrides fields) # search = solrQ
        search_analysis_term_list = [solrQ]
    
    if disMax is not None:
        searchQ = disMax # (overrides fields) # search = solrQ
        solr_max = "disMax"
    
    if edisMax is not None:
        searchQ = edisMax # (overrides fields) # search = solrQ
        solr_max = "edisMax"
    
    if quick_search is not None: #TODO - might want to change this to match PEP-Web best
        searchQ = quick_search # (overrides fields) # search = solrQ
        solr_max = "edisMax"
    
    ret_val = models.QueryParameters(
                                     analyzeThis = analyze_this,
                                     searchQ = searchQ,
                                     filterQ = filterQ,
                                     solrMax = solr_max,
                                     searchAnalysisTermList = search_analysis_term_list,
                                     solrSortBy = sort
                                    )
    
    return ret_val
    
#---------------------------------------------------------------------------------------------------------
@app.get("/v1/Database/MoreLikeThese/", response_model=models.DocumentList, response_model_skip_defaults=True, tags=["Database"])
@app.get("/v1/Database/SearchAnalysis/", response_model=models.DocumentList, response_model_skip_defaults=True, tags=["Database"])
@app.get("/v1/Database/Search/", response_model=models.DocumentList, response_model_skip_defaults=True, tags=["Database"])
async def search_the_document_database(resp: Response, 
                                       request: Request=Query(None, title="HTTP Request", description=opasConfig.DESCRIPTION_REQUEST),  
                                       search: str=Query(None, title="Document request, with a search", description="This is a document request, with a search"),  
                                       journalName: str=Query(None, title="Match PEP Journal or Source Name", description="PEP part of a Journal, Book, or Video name (e.g., 'international'),", min_length=2),  
                                       journal: str=Query(None, title="Match PEP Journal or Source Code", description="PEP Journal Code (e.g., APA, CPS, IJP, PAQ),", min_length=2), 
                                       fulltext1: str=Query(None, title="Search for Words or phrases", description="Words or phrases (in quotes) anywhere in the document"),
                                       fulltext2: str=Query(None, title="Search for Words or phrases", description="Words or phrases (in quotes) anywhere in the document"),
                                       volume: str=Query(None, title="Match Volume Number", description="The volume number if the source has one"), 
                                       issue: str=Query(None, title="Match Issue Number", description="The issue number if the source has one"),
                                       author: str=Query(None, title="Match Author name", description="Author name, use wildcard * for partial entries (e.g., Johan*)"), 
                                       title: str=Query(None, title="Search Document Title", description="The title of the document (article, book, video)"),
                                       startyear: str=Query(None, title="First year to match or a range", description="First year of documents to match (e.g, 1999).  Range query: ^1999-2010 means between 1999-2010.  >1999 is after 1999 <1999 is before 1999"), 
                                       endyear: str=Query(None, title="Last year to match", description="Last year of documents to match (e.g, 2001)"), 
                                       dreams: str=Query(None, title="Search Text within 'Dreams'", description="Words or phrases (in quotes) to match within dreams"),  
                                       quotes: str=Query(None, title="Search Text within 'Quotes'", description="Words or phrases (in quotes) to match within quotes"),  
                                       abstracts: str=Query(None, title="Search Text within 'Abstracts'", description="Words or phrases (in quotes) to match within abstracts"),  
                                       dialogs: str=Query(None, title="Search Text within 'Dialogs'", description="Words or phrases (in quotes) to match within dialogs"),  
                                       references: str=Query(None, title="Search Text within 'References'", description="Words or phrases (in quotes) to match within references"),  
                                       citecount: str=Query(None, title="Find Documents cited this many times", description="Filter for documents cited more than the specified times in the past 5 years"),   
                                       viewcount: str=Query(None, title="Find Documents viewed this many times", description="Not yet implemented"),    
                                       viewedWithin: str=Query(None, title="Find Documents viewed this many times", description="Not yet implemented"),     
                                       solrQ: str=Query(None, title="Advanced Query (Solr Syntax)", description="Advanced Query in Solr Q syntax (see schema names)"),
                                       disMax: str=Query(None, title="Advanced Query (Solr disMax Syntax)", description="Solr disMax syntax - more like Google search"),
                                       edisMax: str=Query(None, title="Advanced Query (Solr edisMax Syntax) ", description="Solr edisMax syntax - more like Google search, better than disMax"), 
                                       quickSearch: str=Query(None, title="Advanced Query (Solr edisMax Syntax)", description="Advanced Query in Solr syntax (see schema names)"),
                                       sortBy: str=Query("score desc", title="Field names to sort by", description="Comma separated list of field names to sort by"),
                                       limit: int=Query(15, title="Document return limit", description=opasConfig.DESCRIPTION_LIMIT),
                                       offset: int=Query(0, title="Document return offset", description=opasConfig.DESCRIPTION_OFFSET)
                                       ):
    """
    Search the database per one or more of the fields specified.
    
    This code is front end for three endpoints in order to only have to code parameter handling once 
    (since they all would use the same parameters), easily distinguished here by the calling path.
    
    Some of the fields should be deprecated, but for now, they support PEP-Easy, as configured to use the GVPi based PEP Server
    
    MoreLikeThis and SearchAnalysis are brand new (20190625), and there right now for experimentation
    
    Trying to reduce these by making them "smarter". For example, 
        endyear isn't needed, because startyear can handle the ranges (and better than before).
        journal is also configured to take anything that would have otherwise been entered in journalName
    
    #TODO:    
       viewcount, viewedWithin not yet implemented...and probably will be streamlined for future use.
       disMax, edisMax also not yet implemented
    
    
    Status: In Development
    
    
    """

    ocd, sessionInfo = opasAPISupportLib.get_session_info(request, resp)
    
    
    if re.search(r"/Search/", request.url._url):
        print ("Search Request: ", request.url._url)

    if re.search(r"/SearchAnalysis/", request.url._url):
        print ("Analysis Request: ", request.url._url)
        analysisMode = True
    else:
        analysisMode = False

    if re.search(r"/MoreLikeThese/", request.url._url):
        print ("MoreLikeThese Request: ", request.url._url)
        moreLikeTheseMode = True
    else:
        moreLikeTheseMode = False

    current_year = datetime.utcfromtimestamp(time.time()).strftime('%Y')
    # this does intelligent processing of the query parameters and returns a smaller set of solr oriented         
    # params (per pydantic model QueryParameters), ready to use
    solr_query_params = parse_search_query_parameters(search=search,
                                                      journal_name=journalName,
                                                      journal=journal,
                                                      fulltext1=fulltext1,
                                                      fulltext2=fulltext2,
                                                      vol=volume,
                                                      issue=issue,
                                                      author=author,
                                                      title=title,
                                                      startyear=startyear,
                                                      endyear=endyear,
                                                      dreams=dreams,
                                                      quotes=quotes,
                                                      abstracts=abstracts,
                                                      dialogs=dialogs,
                                                      references=references,
                                                      citecount=citecount,
                                                      viewcount=viewcount,
                                                      viewedWithin=viewedWithin,
                                                      solrQ=solrQ,
                                                      disMax=disMax,
                                                      edisMax=edisMax,
                                                      quick_search=quickSearch,
                                                      sort = sortBy
                                                      )

    solr_query_params.urlRequest = request.url._url
    
    # We don't always need full-text, but if we need to request the doc later we'll need to repeat the search parameters plus the docID
    if analysisMode:
        ret_val = documentList = opasAPISupportLib.search_analysis(query_list=solr_query_params.searchAnalysisTermList, 
                                                                 filter_query = None,
                                                                 dis_max = solr_query_params.solrMax,
                                                                 query_analysis=analysisMode,
                                                                 more_like_these = None,
                                                                 fullTextRequested=False,
                                                                 limit=limit
                                                                 )
        
        statusMsg = "{} terms/clauses; queryAnalysis: {}".format(len(solr_query_params.searchAnalysisTermList), 
                                                                 moreLikeTheseMode, 
                                                                 analysisMode)
        print ("Done with search analysis.")
    else:  # we are going to do a regular search
        print ("....searchQ = {}".format(solr_query_params.searchQ))
        print ("....filterQ = {}".format(solr_query_params.filterQ))
        
        ret_val = documentList = opasAPISupportLib.search_text(query=solr_query_params.searchQ, 
                                                                   filter_query = solr_query_params.filterQ,
                                                                   full_text_requested=False,
                                                                   query_debug = False,
                                                                   more_like_these = moreLikeTheseMode,
                                                                   dis_max = solr_query_params.solrMax,
                                                                   sortBy = sortBy,
                                                                   limit=limit, 
                                                                   offset=offset,
                                                                   extraContextLen=200
                                                                   )

        if ret_val != {}:
            matches = len(documentList.documentList.responseSet)
            ret_val.documentList.responseInfo.request = request.url._url
        else:
            matches = 0
        print (f"....matches = {matches}")
        # fill in additional return structure status info
        statusMsg = f"{matches} hits; moreLikeThese:{moreLikeTheseMode}; queryAnalysis: {analysisMode}"
        print ("Done with search.")

    client_host = request.client.host

    if not analysisMode: # too slow to do this for that.
        ocd.record_session_endpoint(api_endpoint_id=opasCentralDBLib.API_DATABASE_SEARCH,
                                        params=request.url._url,
                                        status_message=statusMsg
                                        )

    return ret_val
    
@app.get("/v1/Database/MostDownloaded/", response_model=models.DocumentList, response_model_skip_defaults=True, tags=["Database"])
def get_the_most_viewed_articles(resp: Response,
                                 request: Request=Query(None, title="HTTP Request", description=opasConfig.DESCRIPTION_REQUEST), 
                                 period: str=Query('5', title="Period (5, 10, 20, or all)", description=opasConfig.DESCRIPTION_MOST_CITED_PERIOD),
                                 limit: int=Query(5, title="Document return limit", description=opasConfig.DESCRIPTION_LIMIT),
                                 offset: int=Query(0, title="Document return offset", description=opasConfig.DESCRIPTION_OFFSET)
                                ):
    """
    Return a list of documents which are the most downloaded (viewed)
    
    Status: 
    """
    
    ocd, session_info = opasAPISupportLib.get_session_info(request, resp)

    print ("in most viewed")
    try:
        ret_val = opasAPISupportLib.get_list_of_most_downloaded(period=period,
                                                                limit=limit,
                                                                offset=offset)
        # fill in additional return structure status info
        client_host = request.client.host
        ret_val.documentList.responseInfo.request = request.url._url
    except Exception as e:
        status_message = "Error: {}".format(e)
        ret_val = None
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST, 
            detail=status_message
        )        
    else:
        status_message = "Success"
        status_code = 200

    # Don't record
    #ocd, sessionInfo = opasAPISupportLib.getSessionInfo(request, resp)
    #ocd.recordSessionEndpoint(apiEndpointID=opasCentralDBLib.API_DATABASE_MOSTCITED,
                                      #params=request.url._url,
                                      #returnStatusCode = statusCode,
                                      #statusMessage=statusMessage
                                      #)

    print ("out most viewed")
    return ret_val  # document_list
    
@app.get("/v1/Database/MostCited/", response_model=models.DocumentList, response_model_skip_defaults=True, tags=["Database"])
def get_the_most_cited_articles(resp: Response,
                                request: Request=Query(None, title="HTTP Request", description=opasConfig.DESCRIPTION_REQUEST), 
                                period: str=Query('5', title="Period (5, 10, 20, or all)", description=opasConfig.DESCRIPTION_MOST_CITED_PERIOD),
                                limit: int=Query(10, title="Document return limit", description=opasConfig.DESCRIPTION_LIMIT),
                                offset: int=Query(0, title="Document return offset", description=opasConfig.DESCRIPTION_OFFSET)
                                ):
    """
    Return a list of documents for a SourceCode source (and optional year specified in query params).  
    
    Note: The GVPi implementation does not appear to support the limit and offset parameter
    
    Status: this endpoint is working.         
    """

    time.sleep(.5)
    ocd, session_info = opasAPISupportLib.get_session_info(request, resp)
    #if gOCDatabase.sessionID == None:  # make sure there's an open session for stat.
        #gOCDatabase.startSession()

    print ("in most cited")
    try:
        ret_val = documentList = opasAPISupportLib.database_get_most_cited(period=period, limit=limit, offset=offset)
        # fill in additional return structure status info
        # client_host = request.client.host
        ret_val.documentList.responseInfo.request = request.url._url
    except Exception as e:
        status_message = "Error: {}".format(e)
        ret_val = None
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail=status_message
        )
    else:
        status_message = "Success"
        status_code = 200

    # Don't record - (well ok for now during testing)
    ocd, session_info = opasAPISupportLib.get_session_info(request, resp)
    ocd.record_session_endpoint(api_endpoint_id=opasCentralDBLib.API_DATABASE_MOSTCITED,
                                      params=request.url._url,
                                      return_status_code = status_code,
                                      status_message=status_message
                                      )

    print ("out mostcited")
    return ret_val

@app.get("/v1/Database/WhatsNew/", response_model=models.WhatsNewList, response_model_skip_defaults=True, tags=["Database"])
def get_the_newest_uploaded_issues(resp: Response,
                                   request: Request=Query(None, title="HTTP Request", description=opasConfig.DESCRIPTION_REQUEST), 
                                   daysback: int=Query(14, title="Number of days to look back", description=opasConfig.DESCRIPTION_DAYSBACK),
                                   limit: int=Query(5, title="Document return limit", description=opasConfig.DESCRIPTION_LIMIT),
                                   offset: int=Query(0, title="Document return offset", description=opasConfig.DESCRIPTION_OFFSET)
                                  ):  
    """
    Return a list of issues for journals modified in the last week).  
    
    Status: this endpoint is working.          
    """
    
    time.sleep(.25)
    print ("In whats New")
    # ocd, session_info = opasAPISupportLib.getSessionInfo(request, resp)
    try:
        ret_val = whatsNewList = opasAPISupportLib.database_whats_new(limit=limit, offset=offset, daysBack=daysback)
        # fill in additional return structure status info
        # client_host = request.client.host
    except Exception as e:
        e = str(e)
        status_message = "Error: {}".format(e.replace("'", "\\'"))
        ret_val = None
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail=status_message
        )
    else:
        status_message = "Success"
        status_code = HTTP_200_OK
        ret_val.whatsNew.responseInfo.request = request.url._url

    # Don't record endpoint what's New
    #ocd.recordSessionEndpoint(apiEndpointID=opasCentralDBLib.API_DATABASE_WHATSNEW,
                                      #params=request.url._url,
                                      #returnStatusCode = statusCode,
                                      #statusMessage=statusMessage
                                      #)

    print ("Out whats New")
    return ret_val

##-----------------------------------------------------------------------------
#@app.get("/v1/Metadata/Banners/", response_model_skip_defaults=True, tags=["Metadata"])
#def get_banners(resp: Response, 
               #request: Request=Query(None, title="HTTP Request", description=opasConfig.DESCRIPTION_REQUEST),
               #):
    #"""
    #Return information on the location of a source's banner.
    #This v1 endpoint has not yet been used by a client.  
    #DEPRECATED.
    #Use /v1/Metadata/{SourceType}/ instead
          
    #"""
    #errCode = resp.status_code = HTTP_400_BAD_REQUEST
    #errorMessage = "Error: {}".format("This endpoint is was unused and is now deprecated. Use /v1/Metadata/{SourceType}/ instead")
    #errReturn = models.ErrorReturn(error = ERR_MSG_DEPRECATED, error_message = errorMessage)

    #return errReturn

##-----------------------------------------------------------------------------
#@app.get("/v1/Metadata/Banners/{SourceCode}", response_model_skip_defaults=True, tags=["Metadata"])
#def get_banners(resp: Response, 
               #request: Request=Query(None, title="HTTP Request", description=opasConfig.DESCRIPTION_REQUEST),
               #SourceCode: str=Path(..., title="PEP Code for Source", description=opasConfig.DESCRIPTION_SOURCECODE), 
               #):
    #"""
    #Return information on the location of a source's banner.
    #This v1 endpoint has not yet been used by a client.  
    #DEPRECATED.
    #Use /v1/Metadata/{SourceType}/ instead
          
    #"""
    #errCode = resp.status_code = HTTP_400_BAD_REQUEST
    #errorMessage = "Error: {}".format("This endpoint is was unused and is now deprecated. Use /v1/Metadata/{SourceType}/ instead")
    #errReturn = models.ErrorReturn(error = ERR_MSG_DEPRECATED, error_message = errorMessage)

    #return errReturn

    
#-----------------------------------------------------------------------------
@app.get("/v1/Metadata/Contents/{SourceCode}/", response_model=models.DocumentList, response_model_skip_defaults=True, tags=["Metadata"])
def get_journal_content_lists(resp: Response,
                              request: Request=Query(None, title="HTTP Request", description=opasConfig.DESCRIPTION_REQUEST), 
                              SourceCode: str=Path(..., title="PEP Code for Source", description=opasConfig.DESCRIPTION_SOURCECODE), 
                              year: str=Query("*", title="Contents Year", description="Year of source contents to return"),
                              limit: int=Query(15, title="Document return limit", description=opasConfig.DESCRIPTION_LIMIT),
                              offset: int=Query(0, title="Document return offset", description=opasConfig.DESCRIPTION_OFFSET)
                              ):
    """
    Return a list of documents for a SourceCode (and optional year specified in query params).  
    
    Note: The GVPi implementation does not appear to support the limit and offset parameter
    
    Status: this endpoint is working.     
    
    """
    
    ocd, session_info = opasAPISupportLib.get_session_info(request, resp)
    try:       
        ret_val = opasAPISupportLib.metadata_get_contents(SourceCode, year, limit=limit, offset=offset)
        # fill in additional return structure status info
        # client_host = request.client.host
    except Exception as e:
        status_message = "Error: {}".format(e)
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail=status_message
        )
    else:
        status_message = "Success"
        status_code = HTTP_200_OK
        ret_val.documentList.responseInfo.request = request.url._url

    ocd.record_session_endpoint(api_endpoint_id=opasCentralDBLib.API_METADATA_CONTENTS,
                                      params=request.url._url,
                                      document_id="{}.{}".format(SourceCode, year), 
                                      return_status_code = status_code,
                                      status_message=status_message
                                      )

    return ret_val # document_list

#-----------------------------------------------------------------------------
@app.get("/v1/Metadata/Contents/{SourceCode}/{SourceVolume}/", response_model=models.DocumentList, response_model_skip_defaults=True, tags=["Metadata"])
def get_journal_content_lists_for_volume(SourceCode: str, 
                                         SourceVolume: str, 
                                         resp: Response,
                                         request: Request=Query(None, title="HTTP Request", description=opasConfig.DESCRIPTION_REQUEST), 
                                         year: str=Query("*", title="HTTP Request", description=opasConfig.DESCRIPTION_YEAR),
                                         limit: int=Query(15, title="Document return limit", description=opasConfig.DESCRIPTION_LIMIT),
                                         offset: int=Query(0, title="Document return offset", description=opasConfig.DESCRIPTION_OFFSET)
                                         ):
    """
    Return a list of documents for a SourceCode and Source Volume (required).  
    
    Year can also be optionally specified in query params.  
    
    Status: this endpoint is working.     
    
    """
       
    ocd, session_info = opasAPISupportLib.get_session_info(request, resp)
    try:
        ret_val = documentList = opasAPISupportLib.metadata_get_contents(SourceCode, year, vol=SourceVolume, limit=limit, offset=offset)
        # fill in additional return structure status info
        # client_host = request.client.host
    except Exception as e:
        status_message = "Error: {}".format(e)
        print (status_message)
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail=status_message
        )
    else:
        status_message = "Success"
        statusCode = HTTP_200_OK
        ret_val.documentList.responseInfo.request = request.url._url
    
    ocd.record_session_endpoint(api_endpoint_id=opasCentralDBLib.API_METADATA_CONTENTS_FOR_VOL,
                                      document_id="{}.{}".format(SourceCode, SourceVolume), 
                                      params=request.url._url,
                                      return_status_code = statusCode,
                                      status_message=status_message
                                      )
    return ret_val

#-----------------------------------------------------------------------------
@app.get("/v1/Metadata/Videos/", response_model=models.VideoInfoList, response_model_skip_defaults=True, tags=["Metadata"])
def get_a_list_of_video_names(resp: Response,
                               request: Request=Query(None, title="HTTP Request", description=opasConfig.DESCRIPTION_REQUEST), 
                               SourceCode: str=Query("*", title="PEP Code for Source", description=opasConfig.DESCRIPTION_SOURCECODE), 
                               limit: int=Query(200, title="Document return limit", description=opasConfig.DESCRIPTION_LIMIT),
                               offset: int=Query(0, title="Document return offset", description=opasConfig.DESCRIPTION_OFFSET)
                               ):
    """
    Get a complete list of journal names
    
    Status: this endpoint is working.     
    """
    ret_val = get_a_list_of_source_names(resp, request, SourceType="Video", SourceCode=SourceCode, limit=limit, offset=offset)
    return ret_val

#-----------------------------------------------------------------------------
@app.get("/v1/Metadata/Journals/", response_model=models.JournalInfoList, response_model_skip_defaults=True, tags=["Metadata"])
def get_a_list_of_journal_names(resp: Response,
                               request: Request=Query(None, title="HTTP Request", description=opasConfig.DESCRIPTION_REQUEST), 
                               SourceCode: str=Query("*", title="PEP Code for Source", description=opasConfig.DESCRIPTION_SOURCECODE), 
                               limit: int=Query(200, title="Document return limit", description=opasConfig.DESCRIPTION_LIMIT),
                               offset: int=Query(0, title="Document return offset", description=opasConfig.DESCRIPTION_OFFSET)
                               ):
    """
    Get a complete list of journal names
    
    Status: this endpoint is working.     
    """
    ret_val = get_a_list_of_source_names(resp, request, SourceType="Journal", SourceCode=SourceCode, limit=limit, offset=offset)
    return ret_val

#-----------------------------------------------------------------------------
@app.get("/v1/Metadata/Volumes/{SourceCode}/", response_model=models.VolumeList, response_model_skip_defaults=True, tags=["Metadata"])
def get_a_list_of_volumes_for_a_journal(resp: Response,
                                        request: Request=Query(None, title="HTTP Request", description=opasConfig.DESCRIPTION_REQUEST), 
                                        SourceCode: str=Path(..., title="Code for a Source", description=opasConfig.DESCRIPTION_SOURCECODE), 
                                        limit: int=Query(opasConfig.DEFAULT_LIMIT_FOR_VOLUME_LISTS, title="Document return limit", description=opasConfig.DESCRIPTION_LIMIT),
                                        offset: int=Query(0, title="Document return offset", description=opasConfig.DESCRIPTION_OFFSET)
                                        ):
    """
    Return a list of volumes for a SourceCode (aka, PEPCode (e.g., IJP)) per the limit and offset parameters 
    
    Status: this endpoint is working.
    
    Sample Call:
       http://localhost:8000/v1/Metadata/Volumes/CPS/
       
    """
    
    ocd, session_info = opasAPISupportLib.get_session_info(request, resp)
    try:
        ret_val = opasAPISupportLib.metadata_get_volumes(SourceCode, limit=limit, offset=offset)
        # fill in additional return structure status info
        # client_host = request.client.host
    except Exception as e:
        status_message = "Error: {}".format(e)
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail=status_message
        )
    else:
        status_message = "Success"
        status_code = HTTP_200_OK
        ret_val.volumeList.responseInfo.request = request.url._url

    ocd.record_session_endpoint(api_endpoint_id=opasCentralDBLib.API_METADATA_VOLUME_INDEX,
                                      params=request.url._url,
                                      document_id="{}".format(SourceCode), 
                                      return_status_code = status_code,
                                      status_message=status_message
                                      )

    return ret_val # returns volumeList
#-----------------------------------------------------------------------------
@app.get("/v1/Metadata/Books/", response_model=models.SourceInfoList, response_model_skip_defaults=True, tags=["Metadata"])
def get_a_list_of_book_names(resp: Response,
                               request: Request=Query(None, title="HTTP Request", description=opasConfig.DESCRIPTION_REQUEST), 
                               SourceCode: str=Query("*", title="PEP Code for Source", description=opasConfig.DESCRIPTION_SOURCECODE), 
                               limit: int=Query(200, title="Document return limit", description=opasConfig.DESCRIPTION_LIMIT),
                               offset: int=Query(0, title="Document return offset", description=opasConfig.DESCRIPTION_OFFSET)
                               ):
    """
    Get a list of Book names equivalent to what is displayed on the original PEP-Web in the books tab.
    
    The data is pulled from the ISSN table.  Subvolumes, of SE and GW are not returned, nor is any volume marked
      with multivolumesubbok in the src_type_qualifier column.  This is exactly what's currently in PEP-Web's
      presentation today.
    
    Status: this endpoint is working.     
    """

    ret_val = get_a_list_of_source_names(resp, request, SourceType="Book", SourceCode=SourceCode, limit=limit, offset=offset)
    return ret_val

#-----------------------------------------------------------------------------
@app.get("/v1/Metadata/{SourceType}/{SourceCode}/", response_model=models.SourceInfoList, response_model_skip_defaults=True, tags=["Metadata"])
def get_a_list_of_source_names(resp: Response,
                               request: Request=Query(None, title="HTTP Request", description=opasConfig.DESCRIPTION_REQUEST), 
                               SourceType: str=Path(..., title="Source Type", description=opasConfig.DESCRIPTION_SOURCETYPE), 
                               SourceCode: str=Path(..., title="PEP Code for Source", description=opasConfig.DESCRIPTION_SOURCECODE), 
                               limit: int=Query(200, title="Document return limit", description=opasConfig.DESCRIPTION_LIMIT),
                               offset: int=Query(0, title="Document return offset", description=opasConfig.DESCRIPTION_OFFSET)
                               ):
    """
    Return a list of information about a source type, e.g., journal names 
    
    """
               
    ocd, session_info = opasAPISupportLib.get_session_info(request, resp)
    try:    
        if SourceCode == "*" or SourceType != "Journal":
            ret_val = source_info_list = opasAPISupportLib.metadata_get_source_by_type(SourceType, SourceCode, limit=limit, offset=offset)
        else:
            ret_val = source_info_list = opasAPISupportLib.metadata_get_source_by_code(SourceCode, limit=limit, offset=offset)            

    except Exception as e:
        status_message = "Error: {}".format(e)
        logger.error(status_message)
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail=status_message
        )
    else:
        status_message = "Success"
        status_code = HTTP_200_OK
        # fill in additional return structure status info
        # client_host = request.client.host
        ret_val.sourceInfo.responseInfo.request = request.url._url


    ocd.record_session_endpoint(api_endpoint_id=opasCentralDBLib.API_METADATA_SOURCEINFO,
                                      params=request.url._url,
                                      document_id="{}".format(SourceType), 
                                      return_status_code = status_code,
                                      status_message=status_message
                                      )

    return ret_val
#-----------------------------------------------------------------------------
@app.get("/v1/Authors/Index/{authorNamePartial}/", response_model=models.AuthorIndex, response_model_skip_defaults=True, tags=["Authors"])
def get_the_author_index_entries_for_matching_author_names(resp: Response,
                    request: Request=Query(None, title="HTTP Request", description=opasConfig.DESCRIPTION_REQUEST), 
                    authorNamePartial: str=Path(..., title="Author name or Partial Name", description=opasConfig.DESCRIPTION_AUTHORNAMEORPARTIAL), 
                    limit: int=Query(15, title="Document return limit", description=opasConfig.DESCRIPTION_LIMIT),
                    offset: int=Query(0, title="Document return offset", description=opasConfig.DESCRIPTION_OFFSET)
                    ):
    """
    ## Function
    Return a list (index) of authors.  The list shows the author IDs, which are a normalized form of an authors name.
    
    ## Return Type
    authorindex

    ## Status
    This endpoint is working.

    ## Sample Call
       http://localhost:8000/v1/Authors/Index/Tuck/

    """
    ret_val = None 
    
    ocd, session_info = opasAPISupportLib.get_session_info(request, resp)
    try:
        # returns models.AuthorIndex
        author_name_to_check = authorNamePartial.lower()  # work with lower case only, since Solr is case sensitive.
        ret_val = opasAPISupportLib.authors_get_author_info(author_name_to_check, limit=limit, offset=offset)
    except ConnectionRefusedError as e:
        status_message = f"The server is not running or is currently not accepting connections: {e}"
        print (status_message)
        logger.error(status_message)
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail=status_message
        )
        
    except Exception as e:
        status_message = "Error: {}".format(e)
        logger.error(status_message)
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail=status_message
        )
    else:
        status_message = "Success"
        resp.status_code = HTTP_200_OK
        # fill in additional return structure status info
        # client_host = request.client.host
        ret_val.authorIndex.responseInfo.request = request.url._url

    # for speed since this is used for author pick lists, don't record these
    #ocd.recordSessionEndpoint(apiEndpointID=opasCentralDBLib.API_AUTHORS_INDEX,
                                      #params=request.url._url,
                                      #returnStatusCode = resp.status_code = ,
                                      #statusMessage=statusMessage
                                      #)
                
    return ret_val  # Return author information or error

#-----------------------------------------------------------------------------
@app.get("/v1/Authors/Publications/{authorNamePartial}/", response_model=models.AuthorPubList, response_model_skip_defaults=True, tags=["Authors"])
def get_a_list_of_author_publications_for_matching_author_names(resp: Response,
                           request: Request=Query(None, title="HTTP Request", description=opasConfig.DESCRIPTION_REQUEST), 
                           authorNamePartial: str=Path(..., title="Author name or Partial Name", description=opasConfig.DESCRIPTION_AUTHORNAMEORPARTIAL), 
                           limit: int=Query(15, title="Document return limit", description=opasConfig.DESCRIPTION_LIMIT),
                           offset: int=Query(0, title="Document return offset", description=opasConfig.DESCRIPTION_OFFSET)
                           ):
    """
    
    ## Function
    Return a list of the author's publications.  
    
    ## Return Type
    authorPubList

    ## Status
    This endpoint is working.
    
    ## Sample Call
       http://localhost:8000/v1/Authors/Publications/Tuck/

    """
    #Note: (Markup notation in Docstring above is for FastAPI docs page.)
    
    ocd, session_info = opasAPISupportLib.get_session_info(request, resp)
    try:
        author_name_to_check = authorNamePartial.lower()  # work with lower case only, since Solr is case sensitive.
        ret_val = opasAPISupportLib.authors_get_author_publications(author_name_to_check, limit=limit, offset=offset)
    except Exception as e:
        status_message = "Error: {}".format(e)
        resp.status_code = HTTP_500_INTERNAL_SERVER_ERROR
        logger.error(status_message)
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail=status_message
        )
    else:
        status_message = "Success"
        ret_val.authorPubList.responseInfo.request = request.url._url
        resp.status_code = HTTP_200_OK
    
    # fill in additional return structure status info
    # client_host = request.client.host
    
    ocd.record_session_endpoint(api_endpoint_id=opasCentralDBLib.API_AUTHORS_PUBLICATIONS,
                                      params=request.url._url,
                                      status_message=status_message
                                      )

    return ret_val

@app.get("/v1/Documents/Abstracts/{documentID}/", response_model=models.Documents, response_model_skip_defaults=True, tags=["Documents"])
def view_an_abstract(resp: Response,
                     request: Request=Query(None, title="HTTP Request", description=opasConfig.DESCRIPTION_REQUEST), 
                     documentID: str=Path(..., title="Document ID or Partial ID", description=opasConfig.DESCRIPTION_DOCIDORPARTIAL), 
                     return_format: str=Query("TEXTONLY", title="Document return format", description=opasConfig.DESCRIPTION_RETURNFORMATS),
                     limit: int=Query(5, title="Document return limit", description=opasConfig.DESCRIPTION_LIMIT),
                     offset: int=Query(0, title="Document return offset", description=opasConfig.DESCRIPTION_OFFSET)
                     ):
    """
    Return an abstract for the requested documentID (e.g., IJP.077.0001A, or multiple abstracts for a partial ID (e.g., IJP.077)
    """

    ocd, session_info = opasAPISupportLib.get_session_info(request, resp)
    try:
        ret_val = documents = opasAPISupportLib.documents_get_abstracts(documentID, ret_format=return_format, limit=limit, offset=offset)
    except Exception as e:
        status_message = "Error: {}".format(e)
        logger.error(status_message)
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail=status_message
        )
    else:
        status_message = "Success"
        status_code = HTTP_200_OK
        #client_host = request.client.host
        ret_val.documents.responseInfo.request = request.url._url

    ocd.record_session_endpoint(api_endpoint_id=opasCentralDBLib.API_DOCUMENTS_ABSTRACTS,
                                      params=request.url._url,
                                      document_id="{}".format(documentID), 
                                      return_status_code = status_code,
                                      status_message=status_message
                                      )
    return ret_val

@app.get("/v2/Documents/Glossary/{termID}/", response_model=models.Documents, tags=["Documents"], response_model_skip_defaults=True)  # the current PEP API
def view_a_glossary_entry(resp: Response,
                          request: Request=Query(None, title="HTTP Request", description=opasConfig.DESCRIPTION_REQUEST), 
                          term_id: str=Path(..., title="Document ID or Partial ID", description=opasConfig.DESCRIPTION_DOCIDORPARTIAL),
                          search: str=Query(None, title="Document request from search results", description="This is a document request, including search parameters, to show hits"),
                          return_format: str=Query("HTML", title="Glossary return format", description=opasConfig.DESCRIPTION_RETURNFORMATS)
                         ):
    
    ret_val = None
    ocd, session_info = opasAPISupportLib.get_session_info(request, resp)
    # session_id = session_info.session_id
    # is the user authenticated? 
    # is this document embargoed?
    try:
        print ("TODO: USER NEEDS TO BE AUTHENTICATED for document download")
        
        if search is not None:
            arg_dict = dict(parse.parse_qsl(parse.urlsplit(search).query))
            if term_id is not None:
                # make sure this is part of the last search set.
                j = arg_dict.get("journal")
                if j is not None:
                    if j not in term_id:
                        arg_dict["journal"] = None
        else:
            arg_dict = {}
            
        print ("Glossary View Request: ", term_id, return_format)
        try:
            term_parts = term_id.split(".")
            if len(term_parts) == 4:
                term_id = term_parts[-2]
                print ("Glossary Term Modified: ", term_id, return_format)
            elif len(term_parts) == 3:
                term_id = term_parts[-1]
                print ("Glossary Term Modified: ", term_id, return_format)
            else:
                pass

        except Exception as e:
            print ("Error splitting term:", e)
            logger.error(status_message)
            #raise HTTPException(
                #status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                #detail=status_message
            #)
            #Keep it as is
            #termID = termID
            
        
        ret_val = opasAPISupportLib.documents_get_glossary_entry(term_id, 
                                                              retFormat=return_format, 
                                                              authenticated = session_info.authenticated)
        ret_val.documents.responseInfo.request = request.url._url

    except Exception as e:
        status_message = "View Glossary Error: {}".format(e)
        print (status_message)
        status_code = 400
        ret_val = None
    else:
        status_message = "Success"
        status_code = 200
        # fill in additional return structure status info
        client_host = request.client.host

    ocd.record_session_endpoint(api_endpoint_id=opasCentralDBLib.API_DOCUMENTS,
                                  params=request.url._url,
                                  document_id=term_id, 
                                  status_message=status_message
                                  )
    return ret_val
    

@app.get("/v1/Documents/{documentID}/", response_model=models.Documents, tags=["Documents"], response_model_skip_defaults=True)  # the current PEP API
@app.get("/v1/Documents/Document/{documentID}/", response_model=models.Documents, tags=["Documents"], response_model_skip_defaults=True) # more consistent with the model grouping
def view_a_document(resp: Response,
                    request: Request=Query(None, title="HTTP Request", description=opasConfig.DESCRIPTION_REQUEST), 
                    documentID: str=Path(..., title="Document ID or Partial ID", description=opasConfig.DESCRIPTION_DOCIDORPARTIAL), 
                    offset: int=Query(0, title="Document Page offset", description=opasConfig.DESCRIPTION_PAGEOFFSET),
                    page: int=Query(None, title="Document Page Request (from document pagination)", description=opasConfig.DESCRIPTION_PAGEREQUEST),
                    return_format: str=Query("HTML", title="Document return format", description=opasConfig.DESCRIPTION_RETURNFORMATS),
                    search: str=Query(None, title="Document request from search results", description="This is a document request, including search parameters, to show hits"),
                    # I don' think these are used/needed, but maybe when stepping through a set?  Though I think that would just use the search params
                    #journal_name: str=Query(None, title="Match PEP Journal or Source Name", description="PEP part of a Journal, Book, or Video name (e.g., 'international'),", min_length=2),  
                    #journal: str=Query(None, title="Match PEP Journal or Source Code", description="PEP Journal Code (e.g., APA, CPS, IJP, PAQ),", min_length=2), 
                    #fulltext1: str=Query(None, title="Search for Words or phrases", description="Words or phrases (in quotes) anywhere in the document"),
                    #fulltext2: str=Query(None, title="Search for Words or phrases", description="Words or phrases (in quotes) anywhere in the document"),
                    #vol: str=Query(None, title="Match Volume Number", description="The volume number if the source has one"), 
                    #issue: str=Query(None, title="Match Issue Number", description="The issue number if the source has one"),
                    #author: str=Query(None, title="Match Author name", description="Author name, use wildcard * for partial entries (e.g., Johan*)"), 
                    #title: str=Query(None, title="Search Document Title", description="The title of the document (article, book, video)"),
                    #start_year: str=Query(None, title="First year to match or a range", description="First year of documents to match (e.g, 1999).  Range query: ^1999-2010 means between 1999-2010.  >1999 is after 1999 <1999 is before 1999"), 
                    #end_year: str=Query(None, title="Last year to match", description="Last year of documents to match (e.g, 2001)"), 
                    #dreams: str=Query(None, title="Search Text within 'Dreams'", description="Words or phrases (in quotes) to match within dreams"),  
                    #quotes: str=Query(None, title="Search Text within 'Quotes'", description="Words or phrases (in quotes) to match within quotes"),  
                    #abstracts: str=Query(None, title="Search Text within 'Abstracts'", description="Words or phrases (in quotes) to match within abstracts"),  
                    #dialogs: str=Query(None, title="Search Text within 'Dialogs'", description="Words or phrases (in quotes) to match within dialogs"),  
                    #references: str=Query(None, title="Search Text within 'References'", description="Words or phrases (in quotes) to match within references"),  
                    #citecount: str=Query(None, title="Find Documents cited this many times", description="Filter for documents cited more than the specified times in the past 5 years"),   
                    #viewcount: str=Query(None, title="Find Documents viewed this many times", description="Not yet implemented"),    
                    #viewed_within: str=Query(None, title="Find Documents viewed this many times", description="Not yet implemented"),     
                    #solrQ: str=Query(None, title="Advanced Query (Solr Syntax)", description="Advanced Query in Solr Q syntax (see schema names)"),
                    #disMax: str=Query(None, title="Advanced Query (Solr disMax Syntax)", description="Solr disMax syntax - more like Google search"),
                    #edisMax: str=Query(None, title="Advanced Query (Solr edisMax Syntax) ", description="Solr edisMax syntax - more like Google search, better than disMax"), 
                    #quickSearch: str=Query(None, title="Advanced Query (Solr edisMax Syntax)", description="Advanced Query in Solr syntax (see schema names)"),
                    #sortBy: str=Query(None, title="Field names to sort by", description="Comma separated list of field names to sort by"),
                    ):
    """
    Return a document for the requested documentID (e.g., IJP.077.0001A, or multiple documents for a partial ID (e.g., IJP.077)
    """
    ret_val = None
    ocd, session_info = opasAPISupportLib.get_session_info(request, resp)
    #session_id = sessionInfo.session_id
    # is this document embargoed?
    # check if this is a Glossary request, this is per API.v1.
    m = re.match("(ZBK\.069\..*?)?(?P<termid>(Y.0.*))", documentID)
    if m is not None:    
        # this is a glossary request, submit only the termID
        term_id = m.group("termid")
        ret_val = view_a_glossary_entry(resp, request, term_id=term_id, search=search, return_format=return_format)
    else:
        try:
            print ("TODO: CHECK IF USER IS AUTHENTICATED for document download")
            # is the user authenticated? if so, loggedIn is true
            if session_info.authenticated:
                if search is not None:
                    argDict = dict(parse.parse_qsl(parse.urlsplit(search).query))
                    if documentID is not None:
                        # make sure this is part of the last search set.
                        j = argDict.get("journal")
                        if j is not None:
                            if j not in documentID:
                                argDict["journal"] = None
                else:
                    argDict = {}
                    
                solr_query_params = parse_search_query_parameters(**argDict)
                print ("Document View Request: ", solr_query_params, documentID, return_format)
                
                ret_val = opasAPISupportLib.documents_get_document( documentID, 
                                                                    solr_query_params,
                                                                    retFormat=return_format, 
                                                                    authenticated = session_info.authenticated
                                                                  )
            else:
                print ("user is not authenticated.  Returning abstract only)")
                
                ret_val = opasAPISupportLib.documents_get_abstracts( documentID,
                                                                     ret_format="TEXTONLY",
                                                                     authenticated=None,
                                                                     limit=opasConfig.DEFAULT_LIMIT_FOR_SOLR_RETURNS,
                                                                     offset=0
                                                                    )
                
        except Exception as e:
            status_message = "View Document Error: {}".format(e)
            print (status_message)
            ret_val = None
            raise HTTPException(
                status_code=HTTP_400_BAD_REQUEST,
                detail=status_message
            )
        else:
            status_message = "Success"
            status_code = HTTP_200_OK
            # fill in additional return structure status info
            client_host = request.client.host
            ret_val.documents.responseInfo.request = request.url._url
    
        ocd.record_session_endpoint(api_endpoint_id=opasCentralDBLib.API_DOCUMENTS,
                                          params=request.url._url,
                                          document_id="{}".format(documentID), 
                                          status_message=status_message
                                          )
    return ret_val

@app.get("/v1/Documents/Downloads/{retFormat}/{documentID}/", response_model_skip_defaults=True, tags=["Documents"])
def download_a_document(resp: Response,
                        request: Request=Query(None, title="HTTP Request", description=opasConfig.DESCRIPTION_REQUEST), 
                        documentID: str=Path(..., title="Document ID or Partial ID", description=opasConfig.DESCRIPTION_DOCIDORPARTIAL), 
                        return_format=Path(..., title="Download Format", description=opasConfig.DESCRIPTION_DOCDOWNLOADFORMAT),
                        ):

     
    ocd, session_info = opasAPISupportLib.get_session_info(request, resp)
    is_authenticated = check_if_user_logged_in(request, resp)  

    opasAPISupportLib.prep_document_download(documentID, ret_format=return_format, authenticated=True, baseFilename="opasDoc")    

    ocd.record_session_endpoint(api_endpoint_id=opasCentralDBLib.API_DOCUMENTS_EPUB,
                                      params=request.url._url,
                                      document_id="{}".format(documentID), 
                                      status_message=CURRENT_DEVELOPMENT_STATUS
                                      )

    return True

    
    
if __name__ == "__main__":
    print(f"Server Running ({localsecrets.BASEURL}:{localsecrets.API_PORT_MAIN})")
    uvicorn.run(app, host=localsecrets.BASEURL, port=9100, debug=True)

    print ("we're still here!")