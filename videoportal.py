
import os, re, sys
import urllib, urllib2, HTMLParser
import xbmcgui, xbmcplugin, xbmcaddon
import simplejson
from BeautifulSoup import BeautifulSoup
from AddonStats import AddonStats

#
# constants definition
############################################
PLUGINID = "plugin.video.sf-videoportal"

# plugin handle
pluginhandle = int(sys.argv[1])

# plugin modes
MODE_SENDUNGEN       = "sendungen"
MODE_SENDUNG         = "sendung"
MODE_SENDUNG_PREV    = "sendung_prev"
MODE_VERPASST        = "verpasst"
MODE_VERPASST_DETAIL = "verpasst_detail"
MODE_CHANNEL_LIST    = "channel_list"
MODE_CHANNEL         = "channel"
MODE_PLAY            = "play"

# parameter keys
PARAMETER_KEY_MODE = "mode"
PARAMETER_KEY_ID = "id"
PARAMETER_KEY_URL = "url"
PARAMETER_KEY_TITLE = "title"
PARAMETER_KEY_POS   = "pos"

ITEM_TYPE_FOLDER, ITEM_TYPE_VIDEO = range(2)
BASE_URL = "http://www.videoportal.sf.tv"
FLASH_PLAYER = "http://www.videoportal.sf.tv/flash/videoplayer.swf"

settings = xbmcaddon.Addon( id=PLUGINID)

LIST_FILE = os.path.join( os.getcwd(), "resources", "list.dat")
listItems = []

#
# utility functions
############################################

# Log NOTICE
def log_notice(msg):
    xbmc.output("### [%s] - %s" % ("videoportal",msg,),level=xbmc.LOGNOTICE )


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


entitydict = { "E4": u"\xE4", "F6": u"\xF6", "FC": u"\xFC",
               "C4": u"\xE4", "D6": u"\xF6", "DC": u"\xDC",
               "2013": u"\u2013"}

def htmldecode( s):
	try:
		h = HTMLParser.HTMLParser()
		s = h.unescape( s)
		for k in entitydict.keys():
			s = s.replace( "&#x" + k + ";", entitydict[k])
	except UnicodeDecodeError:
		pass
		
	return s


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


def doLog( params):
    stats = AddonStats( PLUGINID, "http://www.mindmade.org/~andi/research/python/server.py")

    fromAddonInfo = ( "stars", "version")
    fromParams = ( PARAMETER_KEY_MODE, PARAMETER_KEY_URL, PARAMETER_KEY_ID)

    log = dict()
    for k in fromAddonInfo:
        log[k]   = settings.getAddonInfo( k)
    print params
    for k in fromParams:
        if k in params.keys():
            log[k]   = params[k]
    
    stats.log( log)


#
# parsing functions
############################################

def getIdFromUrl( url):
	return re.compile( 'id=([0-9a-z\-]+)').findall( url)[0]


def getJSONForId( id):
    json_url = BASE_URL + "/cvis/segment/" + id + "/.json?nohttperr=1;omit_video_segments_validity=1;omit_related_segments=1"
    json = simplejson.loads( getHttpResponse( json_url).split( "\n")[1])
    return json


def getVideoFromJSON( json):
    streams = json["streaming_urls"]
    sortedstreams = sorted( streams, key=lambda el: int(el["bitrate"]))

    quality = int(settings.getSetting( id="quality"))
    if (quality >= len(sortedstreams)):
        quality = len(sortedstreams)-1;
    
    return sortedstreams[ quality]["url"] + " swfvfy=true swfurl=" + FLASH_PLAYER



def getThumbnailForId( id):
	thumb = BASE_URL + "/cvis/videogroup/thumbnail/" + id + "?width=200"
	return thumb


#
# content functions
############################################

def getHttpResponse( url):
    log_notice("getHttpResponse from " + url)
    hdrs = {
        "User-Agent": "Mozilla/5.0 (Windows; U; Windows NT 5.1; en-GB; rv:1.9.0.3) Gecko/2008092417 Firefox/3.0.3",
    }

    req = urllib2.Request( url, headers=hdrs)
    response = urllib2.urlopen( req)
    encoding = re.findall("charset=([a-zA-Z0-9\-]+)", response.headers['content-type'])
    text = response.read()
    responsetext = unicode( text, encoding[0] );
    response.close()
#    return responsetext.encode("utf-8")
    return responsetext


def list_prev_sendungen( url, soup, alreadylisted=0, selected=0):
    print "url: %s" % url
    global listItems
    doAppend = (alreadylisted==0)
    listed=0;
    if doAppend:
        items=simplejson.load( file( LIST_FILE, "r"))
        for item in items:
            title, params, thumb = item
            addDirectoryItem( ITEM_TYPE_VIDEO, title, params, thumb)
            listed = listed+1

    previous = soup.find( "div", "prev_sendungen")
    shows = previous.findAll( "div", "comment_row")
    for show in shows:
        a = show.find( "a", "sendung_title")
        if (a):
            title = a.strong.string
            id = getIdFromUrl( a['href'])
            thumb = re.sub( '\?width=[0-9]+', '?width=200', show.find( "a").img['src'])

            addDirectoryItem( ITEM_TYPE_VIDEO, title, {PARAMETER_KEY_MODE: MODE_PLAY, PARAMETER_KEY_ID: id}, thumb, len( shows) + listed + alreadylisted)

    # check for more 'history'
    nexturl=None
    baseurl = url.split('&page=', 1)[0]
    pagination = soup.find( "p", "pagination")
    if (pagination):
		# check for next page
        r = pagination.find( "a", "act")
        if (r):
            curpage = int(r.text)
            numpages = len( pagination.findAll( "a")) - 1
            print( "on page %d/%d" % (curpage, numpages))

            if (curpage < numpages):
                nexturl = baseurl + "&page=" + str( curpage+1)

    if not nexturl:
        nexturl = BASE_URL + soup.find( "div", "grey_box sendung_nav").find( "a")["href"]
	
    if (nexturl):
		addDirectoryItem( ITEM_TYPE_FOLDER, "mehr...", {PARAMETER_KEY_URL: nexturl, PARAMETER_KEY_MODE: MODE_SENDUNG_PREV, PARAMETER_KEY_POS: str( len(listItems)+1)})

    # signal end of list
    xbmcplugin.endOfDirectory(handle=pluginhandle, succeeded=True, updateListing=doAppend)

    # scroll list to bottom and select first new element
    if (selected):
        window = xbmcgui.Window(xbmcgui.getCurrentWindowId())
        window.getControl(50).selectItem( len(listItems)+1)
        window.getControl(50).selectItem( int(selected))

    # store listed items
    simplejson.dump( listItems, file( LIST_FILE, "w"))


#
# mode handlers
############################################

def show_root_menu():
	addDirectoryItem( ITEM_TYPE_FOLDER, "Sendungen", {PARAMETER_KEY_MODE: MODE_SENDUNGEN})
	addDirectoryItem( ITEM_TYPE_FOLDER, "Sendung verpasst?", {PARAMETER_KEY_MODE: MODE_VERPASST})
	addDirectoryItem( ITEM_TYPE_FOLDER, "Channels", {PARAMETER_KEY_MODE: MODE_CHANNEL_LIST})
	xbmcplugin.endOfDirectory(handle=pluginhandle, succeeded=True)


def show_sendungen():
    url = BASE_URL + "/sendungen"
    soup = BeautifulSoup( getHttpResponse( url))
    
    for show in soup.findAll( "div", "az_row"):
        url = show.find( "a")['href']
        title = show.find( "img", "az_thumb")['alt']
        id = getIdFromUrl( url)
        image = getThumbnailForId( id)
        addDirectoryItem( ITEM_TYPE_FOLDER, title, {PARAMETER_KEY_MODE: MODE_SENDUNG, PARAMETER_KEY_URL: BASE_URL + url}, image)

    xbmcplugin.endOfDirectory(handle=pluginhandle, succeeded=True)

def show_sendung( params):
	url = params.get( PARAMETER_KEY_URL)
	soup = BeautifulSoup( getHttpResponse( url))

	# current show
	show = soup.find( "div", "act_sendung_info")
	a = show.find( "a", { "class": None})
	title = a.string
	id = getIdFromUrl( a['href'])
	thumb = re.sub( '\?width=\\d+', '?width=200', show.find( "a").img['src'])
	addDirectoryItem( ITEM_TYPE_VIDEO, title, {PARAMETER_KEY_MODE: MODE_PLAY, PARAMETER_KEY_ID: id}, thumb)

	# previous shows
	listed = list_prev_sendungen( url, soup, 1)

def show_prev_sendung( params):
	url = params.get( PARAMETER_KEY_URL)
	soup = BeautifulSoup( getHttpResponse( url))
	list_prev_sendungen( url, soup, selected=params.get( "pos"))

def show_verpasst():
	url = BASE_URL + "/verpasst"
	html = getHttpResponse( url)
	match = re.compile( '<a class="day_line.+?href="(.+?)"><span class="day_name">(.+?)</span><span class="day_date">(.+?)</span></a>').findall( html.replace( "\n", ""))
	for url,name,date in match:
		title = "%s, %s" % (date, name.strip())
		addDirectoryItem( ITEM_TYPE_FOLDER, title, {PARAMETER_KEY_MODE: MODE_VERPASST_DETAIL, PARAMETER_KEY_URL: url})

	xbmcplugin.endOfDirectory(handle=pluginhandle, succeeded=True)


def show_verpasst_detail( params):
	url = BASE_URL + "/verpasst" + params.get( PARAMETER_KEY_URL)
	html = getHttpResponse( url)
	dayonly = re.compile( 'class="sendungen_missed_column">(.*?)</div></div></div></div>').findall( html)[0]
	match = re.compile( '<div class="sendung_item"><a href="([^"]+?)" class="sen.+?" title="([^"]+?)" src=.+?videogroup/thumbnail/([0-9a-z\-]+)\?width.+?class="time">(.+?)</p>').findall( dayonly)
	for url, name, thumbid, time in match:
		id = getIdFromUrl( url)
		title = "%s, %s" % (time, name)
		thumb = getThumbnailForId( thumbid)
		addDirectoryItem( ITEM_TYPE_VIDEO, title, {PARAMETER_KEY_MODE: MODE_PLAY, PARAMETER_KEY_ID: id}, thumb, len( match))
	
	xbmcplugin.endOfDirectory(handle=pluginhandle, succeeded=True)


def show_channel_list():
	url = BASE_URL + "/channels"
	soup = BeautifulSoup( getHttpResponse( url))
	channels = soup.findAll( "h2", "hidden")
	for ch in channels:
		title = re.sub( "Channel\s+Channel", "Channel", ch.string)
		link = BASE_URL + ch.parent.find( "a")["href"]
		thumb = BASE_URL + ch.parent.find( "img")["src"]
		addDirectoryItem( ITEM_TYPE_FOLDER, title, {PARAMETER_KEY_MODE: MODE_CHANNEL, PARAMETER_KEY_URL: link}, thumb, len( channels))
	xbmcplugin.endOfDirectory(handle=pluginhandle, succeeded=True)


def show_channel( params):
	url = params.get( PARAMETER_KEY_URL)
	soup = BeautifulSoup( getHttpResponse( url))
	items = soup.find( "div", "scroll-pane").findAll( "div", "teaser_item")
	for item in items:
		a = item.findAll( "a")[1]
		title = a.string
		id = getIdFromUrl( a["href"])
		thumb = re.sub( '\?width=\\d+', '?width=200', item.find( "img")["src"])
		addDirectoryItem( ITEM_TYPE_FOLDER, title, {PARAMETER_KEY_MODE: MODE_PLAY, PARAMETER_KEY_ID: id}, thumb, len( items))
	xbmcplugin.endOfDirectory(handle=pluginhandle, succeeded=True)
		

#
# xbmc entry point
############################################

# read parameters and mode
params = parameters_string_to_dict(sys.argv[2])

doLog( params)

mode = params.get(PARAMETER_KEY_MODE, "0")

# depending on the mode, call the appropriate function to build the UI.
if not sys.argv[2]:
    # new start
    ok = show_root_menu()
elif mode == MODE_SENDUNGEN:
    ok = show_sendungen()
elif mode == MODE_SENDUNG:
    ok = show_sendung(params)
elif mode == MODE_SENDUNG_PREV:
    ok = show_prev_sendung(params)
elif mode == MODE_VERPASST:
    ok = show_verpasst()
elif mode == MODE_VERPASST_DETAIL:
    ok = show_verpasst_detail(params)
elif mode == MODE_CHANNEL_LIST:
	show_channel_list()
elif mode == MODE_CHANNEL:
	show_channel( params)
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
