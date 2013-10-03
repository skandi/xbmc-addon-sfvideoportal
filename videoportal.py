
import os, re, sys
from datetime import date, timedelta
import urllib, urllib2, HTMLParser
import xbmcgui, xbmcplugin, xbmcaddon
from mindmade import *
import simplejson
from BeautifulSoup import BeautifulSoup

__author__     = "Andreas Wetzel"
__copyright__  = "Copyright 2011, 2012, mindmade.org"
__credits__    = [ "Francois Marbot" ]
__maintainer__ = "Andreas Wetzel"
__email__      = "xbmc@mindmade.org"

#
# constants definition
############################################
PLUGINID = "plugin.video.sf-videoportal"

# plugin handle
pluginhandle = int(sys.argv[1])

# plugin modes
MODE_SENDUNGEN_AZ     = "sendungen_az"
MODE_SENDUNGEN_THEMEN = "sendungen_themen"
MODE_SENDUNGEN_THEMA  = "sendungen_thema"
MODE_SENDUNG          = "sendung"
MODE_SENDUNG_VERPASST = "sendung_verpasst"
MODE_VERPASST_DETAIL  = "verpasst_detail"
MODE_THEMEN           = "themen"
MODE_THEMA            = "thema"
MODE_PLAY             = "play"

# parameter keys
PARAMETER_KEY_MODE  = "mode"
PARAMETER_KEY_ID    = "id"
PARAMETER_KEY_URL   = "url"
PARAMETER_KEY_TITLE = "title"
PARAMETER_KEY_POS   = "pos"

ITEM_TYPE_FOLDER, ITEM_TYPE_VIDEO = range(2)
BASE_URL = "http://www.srf.ch/"
BASE_URL_PLAYER = "http://www.srf.ch/player/tv"
# for some reason, it only works with the old player version.
FLASH_PLAYER = "http://www.videoportal.sf.tv/flash/videoplayer.swf"
#FLASH_PLAYER = "http://www.srf.ch/player/tv/flash/videoplayer.swf"

settings = xbmcaddon.Addon( id=PLUGINID)

LIST_FILE = os.path.join( settings.getAddonInfo( "path"), "resources", "list.dat")
listItems = []

# DEBUGGER
#REMOTE_DBG = False 

# append pydev remote debugger
#if REMOTE_DBG:
#    # Make pydev debugger works for auto reload.
#    # Note pydevd module need to be copied in XBMC\system\python\Lib\pysrc
#    try:
#        import pysrc.pydevd as pydevd
#    # stdoutToServer and stderrToServer redirect stdout and stderr to eclipse console
#        pydevd.settrace('localhost', stdoutToServer=True, stderrToServer=True)
#    except ImportError:
#        sys.stderr.write("Error: " +
#            "You must add org.python.pydev.debug.pysrc to your PYTHONPATH.")
#        sys.exit(1)

#
# utility functions
############################################

# Log NOTICE

def parameters_string_to_dict( parameters):
    ''' Convert parameters encoded in a URL to a dict. '''
    paramDict = {}
    if parameters:
        paramPairs = parameters[1:].split("&")
        for paramsPair in paramPairs:
            paramSplits = paramsPair.split('=')
            if (len(paramSplits)) == 2:
                paramDict[paramSplits[0]] = urllib.unquote( paramSplits[1])
    return paramDict


def addDirectoryItem( type, name, params={}, image="", total=0):
    '''Add a list item to the XBMC UI.'''
    if (type == ITEM_TYPE_FOLDER):
        img = "DefaultFolder.png"
    elif (type == ITEM_TYPE_VIDEO):
        img = "DefaultVideo.png"

    name = htmldecode( name)
    params[ PARAMETER_KEY_TITLE] = name
    li = xbmcgui.ListItem( name, iconImage=img, thumbnailImage=image)
            
    if (type == ITEM_TYPE_VIDEO):
#        li.setProperty( "IsPlayable", "true")
        li.setProperty( "Video", "true")
        global listItems
        listItems.append( (name, params, image))
    
    params_encoded = dict()
    for k in params.keys():
        params_encoded[k] = params[k].encode( "utf-8")
    url = sys.argv[0] + '?' + urllib.urlencode( params_encoded)
    
    return xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=url, listitem=li, isFolder = (type == ITEM_TYPE_FOLDER), totalItems=total)


#
# parsing functions
############################################

def getIdFromUrl( url):
    return re.compile( '[\?|\&]id=([0-9a-z\-]+)').findall( url)[0]

def getUrlWithoutParams( url):
    return url.split('?')[0]


def getJSONForId( id):
    json_url = BASE_URL + "/webservice/cvis/segment/" + id + "/.json?nohttperr=1;omit_video_segments_validity=1;omit_related_segments=1"
    url = fetchHttp( json_url).split( "\n")[1]
    json = simplejson.loads( url)
    return json


def getVideoFromJSON( json):
    streams = json["playlists"]["playlist"]
    index = 2 * int(settings.getSetting( id="quality"))
    sortedstreams = sorted( streams, key=lambda el: int(el["quality"]))
    if (index >= len(sortedstreams)):
        index = len(sortedstreams)-2
    
    return sortedstreams[index]["url"]

def getThumbnailForId( id):
    thumb = BASE_URL + "webservice/cvis/videogroup/thumbnail/" + id
    return thumb


#
# content functions
############################################


#
# mode handlers
############################################

def show_root_menu():
    addDirectoryItem( ITEM_TYPE_FOLDER, "Sendungen A-Z", {PARAMETER_KEY_MODE: MODE_SENDUNGEN_AZ})
    addDirectoryItem( ITEM_TYPE_FOLDER, "Sendungen nach Thema", {PARAMETER_KEY_MODE: MODE_SENDUNGEN_THEMEN})
    addDirectoryItem( ITEM_TYPE_FOLDER, "Sendung verpasst?", {PARAMETER_KEY_MODE: MODE_SENDUNG_VERPASST})
    xbmcplugin.endOfDirectory(handle=pluginhandle, succeeded=True)


def show_sendungen_abisz():
    url = BASE_URL_PLAYER + "/sendungen"
    soup = BeautifulSoup( fetchHttp( url))
    
    for show in soup.findAll( "li", "az_item"):
        url = show.find( "a")['href']
        title = show.find( "img", "az_thumb")['alt']
        id = getIdFromUrl( url)
        image = getThumbnailForId( id)
        addDirectoryItem( ITEM_TYPE_FOLDER, title, {PARAMETER_KEY_MODE: MODE_SENDUNG, PARAMETER_KEY_ID: id, PARAMETER_KEY_URL: url }, image)

    xbmcplugin.endOfDirectory(handle=pluginhandle, succeeded=True)


def show_sendungen_thematisch():
    url = BASE_URL_PLAYER + "/sendungen-nach-thema"
    soup = BeautifulSoup( fetchHttp( url, {"sort": "topic"}))

    topicNavigation = soup.find( "ul", {"id": "topic_navigation"})
    for topic in topicNavigation.findAll( "li"):
        title = topic.text
        onClick = topic['onclick']
        id = re.compile( '(az_unit_[a-zA-Z0-9_]*)').findall(onClick)[0]
        addDirectoryItem( ITEM_TYPE_FOLDER, title, {PARAMETER_KEY_MODE: MODE_SENDUNGEN_THEMA, PARAMETER_KEY_ID: id})

    xbmcplugin.endOfDirectory(handle=pluginhandle, succeeded=True)


def show_sendungen_thema( params):
    selected_topic = params.get( PARAMETER_KEY_ID)
    url = BASE_URL_PLAYER + "/sendungen-nach-thema"
    soup = BeautifulSoup( fetchHttp( url , {"sort" : "topic"}))

    topic = soup.find( "li", {"id" : selected_topic})
    for show in topic.findAll( "li", "az_item"):
        url = show.find( "a")['href']
        title = show.find( "img", "az_thumb")['alt']
        id = getIdFromUrl( url)
        image = getThumbnailForId( id)
        addDirectoryItem( ITEM_TYPE_FOLDER, title, {PARAMETER_KEY_MODE: MODE_SENDUNG, PARAMETER_KEY_ID: id, PARAMETER_KEY_URL: url }, image)

    xbmcplugin.endOfDirectory(handle=pluginhandle, succeeded=True)


def show_sendung( params):
    sendid = params.get( PARAMETER_KEY_ID)
    urlParam = params.get( PARAMETER_KEY_URL)
    url = BASE_URL + getUrlWithoutParams( urlParam)
    soup = BeautifulSoup( fetchHttp( url, {"id": sendid}))

    for show in soup.findAll( "li", "sendung_item"):
        title = show.find( "h3", "title").text
        titleDate = show.find( "div", "title_date").text
        image = getUrlWithoutParams( show.find( "img")['src'])
        a = show.find( "a")
        id = getIdFromUrl( a['href'])
        addDirectoryItem( ITEM_TYPE_VIDEO, title + " " + titleDate, {PARAMETER_KEY_MODE: MODE_PLAY, PARAMETER_KEY_ID: id }, image)

    xbmcplugin.endOfDirectory(handle=pluginhandle, succeeded=True)


def show_verpasst():
    url = BASE_URL_PLAYER + "/sendungen-nach-datum"

    timestamp = params.get( PARAMETER_KEY_POS)
    if not timestamp:
        # get srf's timestamp for "now"
        timestamp = 999999999999 # very high to get today.
        soup = BeautifulSoup( fetchHttp( url, { "date": timestamp}))
        rightDay = soup.find( "div", { "id": "right_day"})
        timestamp = long(rightDay.find( "input", "timestamp")['value'])

    day = date.fromtimestamp( timestamp)

    for x in range(0, 12):
        title = day.strftime( "%A, %d. %B %Y")
        addDirectoryItem( ITEM_TYPE_FOLDER, title, {PARAMETER_KEY_MODE: MODE_VERPASST_DETAIL, PARAMETER_KEY_POS: day.strftime( "%s")})
        day = day - timedelta( days=1)

    xbmcplugin.endOfDirectory(handle=pluginhandle, succeeded=True)


def show_verpasst_detail( params):
    url = BASE_URL_PLAYER + "/sendungen-nach-datum"
    timestamp = params.get( PARAMETER_KEY_POS)
    soup = BeautifulSoup( fetchHttp( url, { "date": timestamp}))
    
    rightDay = soup.find( "div", { "id": "right_day"})
    
    for show in rightDay.findAll( "div", "overlay_sendung_item"):
        title = show.find( "a", "title").text
        time = show.find( "p", "time").text
        image = getUrlWithoutParams( show.find( "img")['src'])
        a = show.find("div", "sendung_item").find( "a")
        id = getIdFromUrl( a['href'])
        addDirectoryItem( ITEM_TYPE_VIDEO, time + ": " + title, {PARAMETER_KEY_MODE: MODE_PLAY, PARAMETER_KEY_ID: id }, image)

    xbmcplugin.endOfDirectory(handle=pluginhandle, succeeded=True)


#
# xbmc entry point
############################################

sayHi()

# read parameters and mode
params = parameters_string_to_dict(sys.argv[2])

mode = params.get(PARAMETER_KEY_MODE, "0")

# depending on the mode, call the appropriate function to build the UI.
if not sys.argv[2]:
    # new start
    ok = show_root_menu()
elif mode == MODE_SENDUNGEN_AZ:
    ok = show_sendungen_abisz()
elif mode == MODE_SENDUNGEN_THEMEN:
    ok = show_sendungen_thematisch()
elif mode == MODE_SENDUNGEN_THEMA:
    ok = show_sendungen_thema( params)
elif mode == MODE_SENDUNG:
    ok = show_sendung(params)
elif mode == MODE_SENDUNG_VERPASST:
    ok = show_verpasst()
elif mode == MODE_VERPASST_DETAIL:
    ok = show_verpasst_detail(params)
elif mode == MODE_PLAY:
    id = params["id"]
    json = getJSONForId( id)
    url = getVideoFromJSON( json)
    if "mark_in" in json.keys( ):
        start = json["mark_in"]
    elif "mark_in" in json["video"]["segments"][0].keys():
        start = json["video"]["segments"][0]["mark_in"]
    else: start = 0
    li = xbmcgui.ListItem( params[ PARAMETER_KEY_TITLE])
    li.setProperty( "IsPlayable", "true")
    li.setProperty( "Video", "true")
    li.setProperty( "startOffset", "%f" % (start))
    xbmc.Player().play( url, li)
