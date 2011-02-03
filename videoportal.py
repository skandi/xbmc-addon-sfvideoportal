
import re, sys
import urllib, urllib2, HTMLParser
import xbmcgui, xbmcplugin, xbmcaddon
from BeautifulSoup import BeautifulSoup

#
# constants definition
############################################

# plugin handle
pluginhandle = int(sys.argv[1])

# plugin modes
MODE_SENDUNGEN, MODE_SENDUNG, MODE_VERPASST, MODE_VERPASST_DETAIL = range(4)

# parameter keys
PARAMETER_KEY_MODE = "mode"
PARAMETER_KEY_URL = "url"

ITEM_TYPE_FOLDER, ITEM_TYPE_VIDEO = range(2)
BASE_URL = "http://www.videoportal.sf.tv"
FLASH_PLAYER = "http://www.videoportal.sf.tv/flash/videoplayer.swf"

settings = xbmcaddon.Addon( id="plugin.video.sf-videoportal")

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


def getIdFromUrl( url):
	return re.compile( 'id=([0-9a-z\-]+)').findall( url)[0]


def parseJSON( json):
	streams = re.compile( '{"codec_video":"(.+?)".+?"bitrate":([0-9]+).+?"url":"(.+?)"}').findall( json)
	sortedstreams = sorted( streams, key=lambda el: int(el[1]))
	codec, bitrate, url = sortedstreams[ int(settings.getSetting( "quality"))]
	return url.replace("\\/", "/") + " swfurl=" + FLASH_PLAYER + " swfvfy=true";


def getVideoForId( id):
	json_url = BASE_URL + "/cvis/segment/" + id + "/.json?nohttperr=1;omit_video_segments_validity=1;omit_related_segments=1"
	json = getHttpResponse( json_url)

	return parseJSON( json)


def getThumbnailForId( id):
	thumb = BASE_URL + "/cvis/videogroup/thumbnail/" + id + "?width=200"
	return thumb

def addDirectoryItem( type, name, parameters={}, image="", total=0):
	'''Add a list item to the XBMC UI.'''
	if (type == ITEM_TYPE_FOLDER):
		img = "DefaultFolder.png"
	elif (type == ITEM_TYPE_VIDEO):
		img = "DefaultVideo.png"

	li = xbmcgui.ListItem( htmldecode( name), iconImage=img, thumbnailImage=image)
            
	if (type == ITEM_TYPE_VIDEO):
		li.setProperty( "IsPlayable", "true")
		li.setProperty( "Video", "true")
		url = parameters["url"]
	else:        
		url = sys.argv[0] + '?' + urllib.urlencode(parameters)
    
	return xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=url, listitem=li, isFolder = (type == ITEM_TYPE_FOLDER), totalItems=total)


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
	responsetext = unicode( response.read(), encoding[0] );
	response.close()
	return responsetext.encode("utf-8")


#
# mode handlers
############################################

def show_root_menu():
	addDirectoryItem( ITEM_TYPE_FOLDER, "Sendungen", {PARAMETER_KEY_MODE: MODE_SENDUNGEN})
	addDirectoryItem( ITEM_TYPE_FOLDER, "Sendung verpasst?", {PARAMETER_KEY_MODE: MODE_VERPASST})
#	addDirectoryItem( ITEM_TYPE_FOLDER, "Channels", {PARAMETER_KEY_MODE: MODE_CHANNELS})
	xbmcplugin.endOfDirectory(handle=pluginhandle, succeeded=True)


def show_sendungen():
	url = BASE_URL + "/sendungen"
	html = getHttpResponse( url)
	match = re.compile( '<img class="az_thumb" src=.+?alt="([^"]+?)" /></a>.+?href="(.+?)"').findall( html)
	for name, url in match:
		id = getIdFromUrl( url)
		image = getThumbnailForId( id)
		addDirectoryItem( ITEM_TYPE_FOLDER, name, {PARAMETER_KEY_MODE: MODE_SENDUNG, PARAMETER_KEY_URL: BASE_URL + url}, image)

	xbmcplugin.endOfDirectory(handle=pluginhandle, succeeded=True)

def show_sendung( params):
	url = params.get( PARAMETER_KEY_URL)
	soup = BeautifulSoup( getHttpResponse( url))

	# current show
	show = soup.find( "div", "act_sendung_info")
	a = show.find( "a", { "class": None})
	title = a.string
	id = getIdFromUrl( a['href'])
	url = getVideoForId( id)
	thumb = re.sub( '\?width=\d+', '?width=200', show.find( "a").img['src'])
	addDirectoryItem( ITEM_TYPE_VIDEO, title, {PARAMETER_KEY_URL: url}, thumb)

	# previous shows
	previous = soup.find( "div", "prev_sendungen")
	shows = previous.findAll( "div", "comment_row")
	for show in shows:
		a = show.find( "a", "sendung_title")
		title = a.strong.string
		id = getIdFromUrl( a['href'])
		url = getVideoForId( id)
		thumb = re.sub( '\?width=[0-9]+', '?width=200', show.find( "a").img['src'])
		
		addDirectoryItem( ITEM_TYPE_VIDEO, title, {PARAMETER_KEY_URL: url}, thumb, len( shows) + 1)

	xbmcplugin.endOfDirectory(handle=pluginhandle, succeeded=True)


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
		url = getVideoForId( id)
		thumb = getThumbnailForId( thumbid)
		addDirectoryItem( ITEM_TYPE_VIDEO, title, {PARAMETER_KEY_URL: url}, thumb, len( match))
	
	xbmcplugin.endOfDirectory(handle=pluginhandle, succeeded=True)


#
# xbmc entry point
############################################

# read parameters and mode
params = parameters_string_to_dict(sys.argv[2])
mode = int(params.get(PARAMETER_KEY_MODE, "0"))

# depending on the mode, call the appropriate function to build the UI.
if not sys.argv[2]:
    # new start
    ok = show_root_menu()
elif mode == MODE_SENDUNGEN:
    ok = show_sendungen()
elif mode == MODE_SENDUNG:
    ok = show_sendung(params)
elif mode == MODE_VERPASST:
    ok = show_verpasst()
elif mode == MODE_VERPASST_DETAIL:
    ok = show_verpasst_detail(params)

