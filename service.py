import xbmc, xbmcgui, xbmcaddon, xbmcvfs
import re
import sys, os
import unicodedata
import time
import sqlite3

import buggalo
buggalo.GMAIL_RECIPIENT = "msahadl60@gmail.com"
# buggalo.SUBMIT_URL = 'http://msahadl.ms.funpic.de/buggalo-web/submit.php'

import resources.lib.utils as utils

if utils.getSetting('dbbackup') == 'true':
    import zipfile
    import datetime
    
# XBMC-JSON Datenbankabfrage
if sys.version_info < (2, 7):
    import simplejson
else:
    import json as simplejson



        
# Main class of the add-on
class WatchedList:
    
    # entry point for autostart in xbmc
    def runAutostart(self):
        try:
            utils.footprint()
            # workaround to disable autostart, if requested
            if utils.getSetting("autostart") == 'false':
                return 0
            # wait the delay time (only on autostart) and then run the database update
            if utils.getSetting("periodic") == 'true':
                utils.showNotification(utils.getString(32101), utils.getString(30004)%int(utils.getSetting("delay")))
    
                delaytime = int(utils.getSetting("delay")) * 60
                utils.log('Delay time before execution: %d seconds' % delaytime, xbmc.LOGDEBUG)
                starttime = time.time()
                # workaround to sleep the delaytime. When using the sleep-function, xbmc can not exit 
                while 1:
                    if xbmc.abortRequested:
                        return 1
                    if time.time() > starttime + delaytime:
                        break
                    xbmc.sleep(1000)
                #xbmc.sleep(delaytime*1000) # wait the delay time [minutes] in [milliseconds]
            self.runUpdate()
            
            # run the update again after the time interval - if option activated
            self.runProgram()
        except:
            buggalo.addExtraData('setting_autostart', utils.getSetting("autostart"));
            buggalo.addExtraData('setting_periodic', utils.getSetting("periodic"));
            buggalo.addExtraData('setting_interval', utils.getSetting("interval"));
            buggalo.onExceptionRaised()  

            
    # infinite loop for periodic database update
    def runProgram(self):
        try:
            utils.footprint()
            # handle the periodic execution
            while utils.getSetting("periodic") == 'true':
                starttime = time.time()
                sleeptime = int(utils.getSetting("interval")) * 3600 # wait interval until next startup in [seconds]
                # wait and then update again
                utils.log('wait %d seconds until next update' % sleeptime)
                utils.showNotification(utils.getString(32101), utils.getString(30003)%(sleeptime/3600))
                # workaround to sleep the delaytime. When using the sleep-function, xbmc can not exit 
                while 1:
                    if xbmc.abortRequested:
                        return 1
                    if time.time() > starttime + sleeptime:
                        break
                    xbmc.sleep(1000) # wait 1 second until next check if xbmc terminates
                self.runUpdate()
            # do not use the periodic update
            return 0
        except:
            buggalo.addExtraData('setting_periodic', utils.getSetting("periodic"));
            buggalo.addExtraData('setting_interval', utils.getSetting("interval"));
            buggalo.onExceptionRaised()  
            
    # entry point for manual start.
    # perform the update step by step
    def runUpdate(self):
        try:
            # check if player is running before doing the update
            while xbmc.Player().isPlaying() == True:
               if xbmc.abortRequested:
                   return 1
               xbmc.sleep(60)
            # flag to remember copying the databasefile if requested
            self.dbcopydone = False   
    
            # use the default file or a user file, for example to synchronize multiple clients
            if utils.getSetting("extdb") == 'false':
                self.dbdirectory = utils.data_dir()
                self.dbpath = os.path.join( utils.data_dir() , "watchedlist.db" )
            else:
                self.dbdirectory = utils.getSetting("dbpath").decode('utf-8') 
                self.dbpath = os.path.join( utils.getSetting("dbpath").decode('utf-8') , utils.getSetting("dbfilename").decode('utf-8') )
                if not os.path.isdir(utils.getSetting("dbpath")):
                    utils.showNotification(utils.getString(32102), utils.getString(30002)%(self.dbpath))
                    utils.log('db path does not exist: %s' % self.dbpath)
                    return 2              
                
            # load the addon-database
            if self.load_db():
                utils.showNotification(utils.getString(32102), utils.getString(32601))
                return 3
    
            # get the watched state from the addon
            self.watchedmovielist_wl_index = list([]) # use separate liste for imdb-index and the watched data for easier searching through the lists
            self.watchedmovielist_wl_data = list([]) # lastPlayed, playCount
            self.watchedepisodelist_wl = list([]) # imdbnumber, season, episode, lastplayed, playcount
            if self.get_watched_wl():
                utils.showNotification(utils.getString(32102), utils.getString(32602))
                return 4
            
            # add the watched state from imdb ratings csv file, if existing
            
            # get watched state from xbmc
            self.watchedmovielist_xbmc_index = list([]) # imdbnumber
            self.watchedmovielist_xbmc_data = list([]) # lastPlayed, playCount
            self.watchedepisodelist_xbmc = list([]) # imdbnumber, season, episode, lastplayed, playcount, episodeid
            self.tvshows = {} # dict: key=xbmcid, value=[imdbnumber, showname]
            
            if self.get_watched_xbmc():
                utils.showNotification(utils.getString(32102), utils.getString(32603))
                return 5
            self.tvshownames = {} #dict: key=imdbnumber, value=showname
            if self.sync_tvshows():
                utils.showNotification(utils.getString(32102), utils.getString(32604))
                return 5
    
            # import from xbmc into addon database
            res = self.write_wl_wdata()
            if res == 2: # user exit
                return 0 
            elif res == 1: # error
                utils.showNotification(utils.getString(32102), utils.getString(32604))
                return 6
            
            # close the sqlite database (addon)
            self.sqlcon.close()
            
            # export from addon database into xbmc database
            res = self.write_xbmc_wdata()
            if res == 2: # user exit
                return 0 
            elif res == 1: # error
                utils.showNotification(utils.getString(32102), utils.getString(32605))
                return 7
            
            utils.showNotification(utils.getString(32101), utils.getString(32107))
            utils.log('exit with success', xbmc.LOGDEBUG)
            
            return 0
        except:
            buggalo.addExtraData('setting_extdb', utils.getSetting("extdb"));
            buggalo.addExtraData('setting_dbpath', utils.getSetting("dbpath"));
            buggalo.addExtraData('setting_dbfilename', utils.getSetting("dbfilename"));
            buggalo.onExceptionRaised()  

    def load_db(self):
        try:
            #connect to the database. create database if it does not exist
            self.sqlcon = sqlite3.connect(self.dbpath);
            self.sqlcursor = self.sqlcon.cursor()
            # create tables if they don't exist
            sql = "CREATE TABLE IF NOT EXISTS movie_watched (idMovieImdb INTEGER PRIMARY KEY,playCount INTEGER,lastChange INTEGER,lastPlayed INTEGER,title TEXT)"
            self.sqlcursor.execute(sql)

            sql = "CREATE TABLE IF NOT EXISTS episode_watched (idShow INTEGER, season INTEGER, episode INTEGER, playCount INTEGER,lastChange INTEGER,lastPlayed INTEGER, PRIMARY KEY (idShow, season, episode))"
            self.sqlcursor.execute(sql)
            
            sql = "CREATE TABLE IF NOT EXISTS tvshows (idShow INTEGER, title TEXT, PRIMARY KEY (idShow))"
            self.sqlcursor.execute(sql)

        except sqlite3.Error as e:
            utils.log("Database error while opening %s: %s" % (self.dbpath, e.args[0]))
            if self.sqlcon:    
                self.sqlcon.close()
            return 1
        except:
            utils.log("Error while opening %s: %s" % (self.dbpath, sys.exc_info()[2]))
            if self.sqlcon:    
                self.sqlcon.close()
            buggalo.addExtraData('dbpath', self.dbpath)
            buggalo.onExceptionRaised()
            return 1     
        # only commit the changes if no error occured to ensure database persistence
        self.sqlcon.commit()
        return 0







    def get_watched_xbmc(self):
        try:
            # Get all watched movies and episodes by unique id from xbmc-database via JSONRPC
            
            ############################################
            # movies
            if utils.getSetting("w_movies") == 'true':
                utils.log('get_watched_xbmc: Get watched movies from xbmc database', xbmc.LOGDEBUG)
                # use the JSON-RPC to access the xbmc-database.
                rpccmd = {
                          "jsonrpc": "2.0",
                          "method": "VideoLibrary.GetMovies", 
                          "params": {
                                     "properties": ["title", "year", "imdbnumber", "lastplayed", "playcount"],
                                     "sort": { "order": "ascending", "method": "title" }
                                     }, 
                          "id": 1
                          }
                rpccmd = simplejson.dumps(rpccmd) # create string from dict
                json_query = xbmc.executeJSONRPC(rpccmd)
                json_query = unicode(json_query, 'utf-8', errors='ignore')
                json_response = simplejson.loads(json_query)    
                if json_response.has_key('result') and json_response['result'] != None and json_response['result'].has_key('movies'):
                    totalcount = json_response['result']['limits']['total']
                    count = 0
                    # go through all watched movies and save them in the class-variable self.watchedmovielist_xbmc
                    for item in json_response['result']['movies']:
                        count += 1
                        name = item['title'] + ' (' + str(item['year']) + ')'
                        res = re.compile('tt(\d+)').findall(item['imdbnumber'])
                        if len(res) == 0:
                            # no imdb-number for this movie in database. Skip
                            utils.log('Movie %s has no imdb-number in database. movieid=%d Try rescraping' % (name, int(item['movieid'])))
                            continue
                        imdbId = int(res[0])
                        lastplayed = utils.sqlDateTimeToTimeStamp(item['lastplayed'])
                        self.watchedmovielist_xbmc_index.append(imdbId)
                        self.watchedmovielist_xbmc_data.append(list([lastplayed, int(item['playcount']), name, int(item['movieid'])]))
                        # DIALOG_PROGRESS.update(count/totalcount*100 , utils.getString(32105), name)
            
            ############################################        
            # first tv shows with TheTVDB-ID, then tv episodes
            if utils.getSetting("w_episodes") == 'true':
                ############################################
                # get imdb tv-show id from xbmc database
                utils.log('get_watched_xbmc: Get watched episodes from xbmc database', xbmc.LOGDEBUG)
                rpccmd = {
                          "jsonrpc": "2.0", 
                          "method": "VideoLibrary.GetTVShows", 
                          "params": {
                                     "properties": ["title", "imdbnumber"],
                                     "sort": { "order": "ascending", "method": "title" }
                                     }, 
                          "id": 1}
                rpccmd = simplejson.dumps(rpccmd) # create string from dict
                json_query = xbmc.executeJSONRPC(rpccmd)
                json_query = unicode(json_query, 'utf-8', errors='ignore')
                json_response = simplejson.loads(json_query)    
                if json_response.has_key('result') and json_response['result'] != None and json_response['result'].has_key('tvshows'):
                    for item in json_response['result']['tvshows']:
                        tvshowId_xbmc = int(item['tvshowid'])
                        tvshowId_imdb = int(item['imdbnumber'])
                        self.tvshows[tvshowId_xbmc] = list([tvshowId_imdb, item['title']])

                        
                ############################################        
                # tv episodes
                rpccmd = {
                          "jsonrpc": "2.0",
                          "method": "VideoLibrary.GetEpisodes",
                          "params": {
                                     "properties": ["tvshowid", "season", "episode", "playcount", "showtitle", "lastplayed"]
                                     },
                          "id": 1
                          }
                rpccmd = simplejson.dumps(rpccmd) # create string from dict
                json_query = xbmc.executeJSONRPC(rpccmd)
                json_query = unicode(json_query, 'utf-8', errors='ignore')
                json_response = simplejson.loads(json_query)    
                if json_response.has_key('result') and json_response['result'] != None and json_response['result'].has_key('episodes'):
                    totalcount = json_response['result']['limits']['total']
                    count = 0
                    # go through all watched episodes and save them in the class-variable self.watchedepisodelist_xbmc
                    for item in json_response['result']['episodes']:
                        showtitle = item['showtitle']
                        tvshowId_xbmc = item['tvshowid']
                        try:
                            tvshowId_imdb = self.tvshows[tvshowId_xbmc][0]
                        except:
                            utils.log('get_watched_xbmc: xbmc tv showid %d is not in table xbmc-tvshows. Skipping %s S%02dE%02d' % (item['tvshowid'], item['showtitle'], item['season'], item['episode']), xbmc.LOGWARNING)
                            continue
                        lastplayed = utils.sqlDateTimeToTimeStamp(item['lastplayed']) # convert to integer-timestamp
                        self.watchedepisodelist_xbmc.append(list([tvshowId_imdb, int(item['season']), int(item['episode']), lastplayed, int(item['playcount']), int(item['episodeid'])]))
            utils.showNotification( utils.getString(32101), utils.getString(32299)%(len(self.watchedmovielist_xbmc_index), len(self.watchedepisodelist_xbmc)) )
            return 0
        except:
            utils.log(u'get_watched_xbmc:  error getting the xbmc database : %s' % sys.exc_info()[2], xbmc.LOGERROR)
            if self.sqlcon:    
                self.sqlcon.close()
            buggalo.onExceptionRaised()  
            return 1          
        
     
        

        
    def get_watched_wl(self):
        try:
            # get watched movies from addon database
            if utils.getSetting("w_movies") == 'true':
                utils.log('get_watched_wl: Get watched movies from WL database', xbmc.LOGDEBUG)
                self.sqlcursor.execute("SELECT idMovieImdb, lastPlayed, playCount, title FROM movie_watched ORDER BY title") 
                rows = self.sqlcursor.fetchall() 
                for row in rows:
                    self.watchedmovielist_wl_index.append(row[0])
                    self.watchedmovielist_wl_data.append(list([int(row[1]), int(row[2]), row[3]])) # lastplayed, playcount
            
            # get watched episodes from addon database
            if utils.getSetting("w_episodes") == 'true':
                utils.log('get_watched_wl: Get watched episodes from WL database', xbmc.LOGDEBUG)
                self.sqlcursor.execute("SELECT idShow, season, episode, lastPlayed, playCount FROM episode_watched ORDER BY idShow, season, episode") 
                rows = self.sqlcursor.fetchall() 
                for row in rows:
                    self.watchedepisodelist_wl.append(list([int(row[0]), int(row[1]), int(row[2]), int(row[3]), int(row[4])]))
            utils.showNotification(utils.getString(32101), utils.getString(32298)%(len(self.watchedmovielist_wl_index), len(self.watchedepisodelist_wl)))
        except sqlite3.Error as e:
            utils.log(u'get_watched_wl: SQLite Database error getting the wl database %s' % e.args[0], xbmc.LOGERROR)
            # error could be that the database is locked (for tv show strings). This is not an error to disturb the other functions
            return 1
        except:
            utils.log(u'get_watched_wl:  error getting the wl database : %s' % sys.exc_info()[2], xbmc.LOGERROR)
            if self.sqlcon:    
                self.sqlcon.close()
            buggalo.onExceptionRaised()  
            return 1     
        
        
        
        
        
    def sync_tvshows(self):
        try:
            utils.log(u'sync_tvshows:  sync tvshows with wl database : %s' % sys.exc_info()[2], xbmc.LOGDEBUG)
            # write eventually new tv shows to wl database
            for imdbId in self.tvshows:
                sql = 'INSERT OR IGNORE INTO tvshows (idShow,title) VALUES (?, ?)'
                self.sqlcursor.execute(sql, self.tvshows[imdbId])
            self.database_copy()    
            self.sqlcon.commit()
            # get all known tv shows from wl database
            self.sqlcursor.execute("SELECT idShow, title FROM tvshows") 
            rows = self.sqlcursor.fetchall() 
            for i in range(len(rows)):
                self.tvshownames[rows[i][0]] = rows[i][1]
        except sqlite3.Error as e:
            utils.log(u'sync_tvshows: SQLite Database error accessing the wl database %s' % e.args[0], xbmc.LOGERROR)
            # error could be that the database is locked (for tv show strings).
            return 1
        except:
            utils.log(u'sync_tvshows:  error getting the wl database : %s' % sys.exc_info()[2], xbmc.LOGERROR)
            if self.sqlcon:    
                self.sqlcon.close()
            buggalo.onExceptionRaised()  
            return 1   
        return 0 
        
        
        
    def write_wl_wdata(self):
        # Go through all watched movies from xbmc and check whether they are up to date in the addon database
        if utils.getSetting("w_movies") == 'true':
            utils.log('write_wl_wdata: Write watched movies to WL database', xbmc.LOGDEBUG)
            count_insert = 0
            count_update = 0
            if utils.getSetting("progressdialog") == 'true':
                 DIALOG_PROGRESS = xbmcgui.DialogProgress()
                 DIALOG_PROGRESS.create( utils.getString(32101) , utils.getString(32105))

            for i in range(len(self.watchedmovielist_xbmc_index)):
                if xbmc.abortRequested: break # this loop can take some time in debug mode and prevents xbmc exit
                if utils.getSetting("progressdialog") == 'true' and DIALOG_PROGRESS.iscanceled():
                    utils.showNotification(utils.getString(32202), utils.getString(32301)%(count_insert, count_update))
                    return 2
                imdbId = self.watchedmovielist_xbmc_index[i]
                row_xbmc = self.watchedmovielist_xbmc_data[i]
                if utils.getSetting("progressdialog") == 'true':
                    DIALOG_PROGRESS.update(100*i/(len(self.watchedmovielist_xbmc_index)-1), utils.getString(32105), utils.getString(32610) % (i+1, len(self.watchedmovielist_xbmc_index), row_xbmc[2]) )  
                lastplayed_xbmc = row_xbmc[0]
                playcount_xbmc = row_xbmc[1]
                if playcount_xbmc == 0:
                    # playcount in xbmc-list is empty. Nothing to save
                    if utils.getSetting("debug") == 'true':
                        utils.log(u'write_wl_wdata: not watched in xbmc: tt%d, %s' % (imdbId, row_xbmc[2]), xbmc.LOGDEBUG)
                    continue
                try:
                    # search the imdb id in the wl-list
                    try:
                        # the movie is already in the watched-list
                        j = self.watchedmovielist_wl_index.index(imdbId)
                        playcount_wl = self.watchedmovielist_wl_data[j][1]
                        lastplayed_wl = self.watchedmovielist_wl_data[j][0]
                        # compare playcount and lastplayed
                        
                        # check if an update of the wl database is necessary (xbmc watched status newer)
                        if not (playcount_xbmc > playcount_wl or lastplayed_xbmc > lastplayed_wl):
                            if utils.getSetting("debug") == 'true':
                                utils.log(u'write_wl_wdata: wl database up-to-date for movie tt%d, %s' % (imdbId, row_xbmc[2]), xbmc.LOGDEBUG)
                            continue
                        # check if the lastplayed-timestamp in xbmc is useful
                        if lastplayed_xbmc == 0:
                            lastplayed_new = lastplayed_wl
                        else:
                            lastplayed_new = lastplayed_xbmc
                        sql = 'UPDATE movie_watched SET playCount = ?, lastplayed = ?, lastChange = ? WHERE idMovieImdb LIKE ?'
                        values = list([playcount_wl, lastplayed_new, int(time.time()), imdbId])
                        self.sqlcursor.execute(sql, values)
                        count_update += 1
                        if utils.getSetting("debug") == 'true':
                            utils.showNotification(utils.getString(32403), row_xbmc[2])
                    except ValueError:
                        # the movie is not in the watched-list -> insert the movie
                        # row = self.watchedmovielist_xbmc_data[i]
                        # order: idMovieImdb,playCount,lastChange,lastPlayed,title
                        values = list([imdbId, row_xbmc[1], int(time.time()), row_xbmc[0], row_xbmc[2]])
                        sql = 'INSERT INTO movie_watched (idMovieImdb,playCount,lastChange,lastPlayed,title) VALUES (?, ?, ?, ?, ?)'
                        self.sqlcursor.execute(sql, values)
                        utils.log(u'write_wl_wdata: new entry for wl database: tt%d, %s' % (imdbId, row_xbmc[2]))
                        count_insert += 1
                        if utils.getSetting("debug") == 'true':
                            utils.showNotification(utils.getString(32402), row_xbmc[2])
                except sqlite3.Error as e:
                    utils.log(u'write_wl_wdata: Database error while updating movie tt%d, %s: %s' % (imdbId, row_xbmc[2], e.args[0]))
                    # error at this place is the result of duplicate movies, which produces a DUPLICATE PRIMARY KEY ERROR
                    continue
                except:
                    utils.log(u'write_wl_wdata: Error while updating movie tt%d, %s: %s' % (imdbId, row_xbmc[2], sys.exc_info()[2]))
                    if self.sqlcon:    
                        self.sqlcon.close()
                    if utils.getSetting("progressdialog") == 'true': DIALOG_PROGRESS.close()
                    buggalo.addExtraData('imdbId', imdbId); buggalo.addExtraData('lastplayed_xbmc', lastplayed_xbmc); buggalo.addExtraData('playcount_xbmc', playcount_xbmc)
                    buggalo.addExtraData('count_update', count_update); buggalo.addExtraData('count_insert', count_insert); 
                    buggalo.onExceptionRaised()  
                    return 1 
                    
            if utils.getSetting("progressdialog") == 'true': DIALOG_PROGRESS.close()
            # only commit the changes if no error occured to ensure database persistence
            if count_insert > 0 or count_update > 0:
                self.database_copy()
                self.sqlcon.commit()
            utils.showNotification(utils.getString(32202), utils.getString(32301)%(count_insert, count_update))
              
 
        
        ################################################################        
        # Go through all watched episodes from xbmc database and check whether they are up to date in the addon database
        if utils.getSetting("w_episodes") == 'true':
            utils.log('write_wl_wdata: Write watched episodes to WL database', xbmc.LOGDEBUG)
            count_insert = 0; count_update = 0;
            if utils.getSetting("progressdialog") == 'true':
                 DIALOG_PROGRESS = xbmcgui.DialogProgress()
                 DIALOG_PROGRESS.create( utils.getString(32101) , utils.getString(32105))
            
            for i in range(len(self.watchedepisodelist_xbmc)):
                if xbmc.abortRequested: break # this loop can take some time in debug mode and prevents xbmc exit
                if utils.getSetting("progressdialog") == 'true' and DIALOG_PROGRESS.iscanceled():
                    utils.showNotification(utils.getString(32203), utils.getString(32301)%(count_insert, count_update))
                    return 2
                row_xbmc = self.watchedepisodelist_xbmc[i]
                imdbId = row_xbmc[0]
                season = row_xbmc[1]
                episode = row_xbmc[2]
                lastplayed_xbmc = row_xbmc[3]
                playcount_xbmc = row_xbmc[4]
                
                if utils.getSetting("progressdialog") == 'true':
                    DIALOG_PROGRESS.update(100*i/(len(self.watchedepisodelist_xbmc)-1), utils.getString(32105), utils.getString(32611) % (i+1, len(self.watchedepisodelist_xbmc), self.tvshownames[imdbId], season, episode) )
                if playcount_xbmc == 0:
                    # playcount in xbmc-list is empty. Nothing to save
                    if utils.getSetting("debug") == 'true':
                        utils.log('write_wl_wdata: not watched in xbmc: %s S%02dE%02d' % (self.tvshownames[imdbId], season, episode), xbmc.LOGDEBUG)
                    continue
                try:
                    # search the episode in the wl-list
                    found = False
                    for j in range(len(self.watchedepisodelist_wl)):
                        row_wl = self.watchedepisodelist_wl[j]
                        
                        if row_wl[0] == imdbId and row_wl[1] == season and row_wl[2] == episode:
                            found = True
                            break
                    if found:
                        playcount_wl = row_wl[4]
                        lastplayed_wl = row_wl[3]
                        # check if an update of the wl database is necessary (xbmc watched status newer)
                        if not (playcount_xbmc > playcount_wl or lastplayed_xbmc > lastplayed_wl):
                            if utils.getSetting("debug") == 'true':
                                utils.log(u'write_wl_wdata: wl database up-to-date for %s, S%02dE%02d' % (self.tvshownames[imdbId], season, episode), xbmc.LOGDEBUG)
                            continue
                        # check if the lastplayed-timestamp in xbmc is useful
                        if lastplayed_xbmc == 0:
                            lastplayed_new = lastplayed_wl
                        else:
                            lastplayed_new = lastplayed_xbmc
                            
                        sql = 'UPDATE episode_watched SET playCount = ?, lastPlayed = ?, lastChange = ? WHERE idShow LIKE ? AND season LIKE ? AND episode LIKE ?'
                        values = list([playcount_xbmc, lastplayed_new, int(time.time()), imdbId, season, episode])
                        self.sqlcursor.execute(sql, values)
                        count_update += 1
                    else:
                        # insert new watched episode into wl database
                        sql = 'INSERT INTO episode_watched (idShow,season,episode,playCount,lastChange,lastPlayed) VALUES (?, ?, ?, ?, ?, ?)'
                        values = list([imdbId, season, episode, playcount_xbmc, int(time.time()), lastplayed_xbmc])
                        self.sqlcursor.execute(sql, values)
                        count_insert += 1
                    if utils.getSetting("debug") == 'true':
                        if sql.find('UPDATE') == 0: # use different messages for updated or inserted data
                            stringnumber = 32403
                        else:
                            stringnumber = 32402
                        utils.showNotification(utils.getString(stringnumber), '%s S%02dE%02d' % (self.tvshownames[imdbId], season, episode))
                        utils.log(u'write_wl_wdata: SQL Entry %s S%02dE%02d: playcount %d' % (self.tvshownames[imdbId], season, episode, playcount_xbmc), xbmc.LOGDEBUG)
    
                except sqlite3.Error as e:
                    utils.log(u'write_wl_wdata: Database error while updating %s S%02dE%02d: %s' % (self.tvshownames[imdbId], season, episode, e.args[0]), xbmc.LOGWARNING)
                    # error at this place is the result of duplicate movies, which produces a DUPLICATE PRIMARY KEY ERROR
                    continue
                except:
                    utils.log(u'write_wl_wdata: Error while updating %s S%02dE%02d: %s' % (self.tvshownames[imdbId], season, episode, sys.exc_info()[2]), xbmc.LOGERROR)
                    if self.sqlcon:    
                        self.sqlcon.close()
                    if utils.getSetting("progressdialog") == 'true': DIALOG_PROGRESS.close()
                    buggalo.addExtraData('imdbId', imdbId); buggalo.addExtraData('season', season); buggalo.addExtraData('episode', episode);
                    buggalo.addExtraData('count_update', count_update); buggalo.addExtraData('count_insert', count_insert); 
                    buggalo.addExtraData('lastplayed_xbmc', lastplayed_xbmc); buggalo.addExtraData('playcount_xbmc', playcount_xbmc);
                    buggalo.onExceptionRaised()  
                    return 1
                    
            self.database_copy()
            self.sqlcon.commit()
            if utils.getSetting("progressdialog") == 'true': DIALOG_PROGRESS.close()
            utils.showNotification(utils.getString(32203), utils.getString(32301)%(count_insert, count_update))
        return 0
        
        
        
        
        
        
    def write_xbmc_wdata(self):
        # Go through all watched movies from the wl-database and check, if the xbmc-database is up to date
        if utils.getSetting("w_movies") == 'true':
            utils.log('write_xbmc_wdata: Write watched movies to xbmc database', xbmc.LOGDEBUG)
            count_update = 0
            if utils.getSetting("progressdialog") == 'true':
                 DIALOG_PROGRESS = xbmcgui.DialogProgress()
                 DIALOG_PROGRESS.create( utils.getString(32101), utils.getString(32106))
            for j in range(len(self.watchedmovielist_wl_index)):
                if xbmc.abortRequested: break # this loop can take some time in debug mode and prevents xbmc exit
                if utils.getSetting("progressdialog") == 'true' and DIALOG_PROGRESS.iscanceled():
                    utils.showNotification(utils.getString(32204), utils.getString(32302)%(count_update))  
                    return 2
                
                imdbId = self.watchedmovielist_wl_index[j]
                row_wl = self.watchedmovielist_wl_data[j]
                if utils.getSetting("progressdialog") == 'true':
                    DIALOG_PROGRESS.update(100*j/(len(self.watchedmovielist_wl_index)-1), utils.getString(32106), utils.getString(32610) % (j+1, len(self.watchedepisodelist_xbmc), row_wl[2]) )
                try:
                    rpccmd = {} # empty variable that is eventually sent by buggalo
                    # search the imdb id in the xbmc-list
                    try:
                        # the movie is already in the xbmc-list
                        indices = [i for i, x in enumerate(self.watchedmovielist_xbmc_index) if x == imdbId] # the movie can have multiple entries in xbmc
                        lastplayed_wl = row_wl[0]
                        playcount_wl = row_wl[1]
                        for i in indices:
                            i = self.watchedmovielist_xbmc_index.index(imdbId)
                            row_xbmc = self.watchedmovielist_xbmc_data[i]
                            playcount_xbmc = row_xbmc[1]
                            lastplayed_xbmc = row_xbmc[0]
                            # compare playcount and lastplayed (update if xbmc data is older)
                            if not( playcount_xbmc < playcount_wl or lastplayed_xbmc < lastplayed_wl ):
                                if utils.getSetting("debug") == 'true':
                                    utils.log('write_xbmc_wdata: xbmc database up-to-date for tt%d, %s' % (imdbId, row_xbmc[2]), xbmc.LOGDEBUG)
                                continue
                            # check if the lastplayed-timestamp in wl is useful
                            if lastplayed_wl == 0:
                                lastplayed_new = lastplayed_xbmc
                            else:
                                lastplayed_new = lastplayed_wl
                            # update database
                            rpccmd = {
                                      "jsonrpc": "2.0", 
                                      "method": "VideoLibrary.SetMovieDetails", 
                                      "params": {"movieid": row_xbmc[3], "playcount": playcount_wl, "lastplayed": utils.TimeStamptosqlDateTime(lastplayed_new)}, 
                                      "id": 1
                                      }
                            rpccmd = simplejson.dumps(rpccmd) # create string from dict
                            json_query = xbmc.executeJSONRPC(rpccmd)
                            json_query = unicode(json_query, 'utf-8', errors='ignore')
                            json_response = simplejson.loads(json_query)  
                            if (json_response.has_key('result') and json_response['result'] == 'OK'):
                                utils.log('write_xbmc_wdata: xbmc database updated. playcount=%d (before: %d) for tt%d, %s' % (playcount_wl, playcount_xbmc, imdbId, row_xbmc[2]))
                                if utils.getSetting("debug") == 'true':
                                    utils.showNotification(utils.getString(32401), row_xbmc[2])
                                count_update += 1
                            else:
                                utils.log('write_xbmc_wdata: error updating xbmc database. tt%d, %s' % (imdbId, row_xbmc[2]))
                        
                    except ValueError:
                        # the movie is in the watched-list but not in the xbmc-list -> no action
                        utils.log('write_xbmc_wdata: movie not in xbmc database: tt%d, %s' % (imdbId, row_xbmc[2]), xbmc.LOGDEBUG)
                        continue
                except:
                    utils.log("write_xbmc_wdata: Error while updating movie tt%d, %s: %s" % (imdbId, row_xbmc[2], sys.exc_info()[2]))
                    if utils.getSetting("progressdialog") == 'true': DIALOG_PROGRESS.close()
                    buggalo.addExtraData('rpccmd', rpccmd); buggalo.addExtraData('count_update', count_update);
                    buggalo.addExtraData('rpccmd', imdbId);
                    buggalo.onExceptionRaised()  
                    return 1 

            if utils.getSetting("progressdialog") == 'true': DIALOG_PROGRESS.close() 
            utils.showNotification(utils.getString(32204), utils.getString(32302)%(count_update))    

        
        # Go through all watched episodes from the wl-database and check, if the xbmc-database is up to date
        if utils.getSetting("w_episodes") == 'true':
            utils.log('write_xbmc_wdata: Write watched episodes to xbmc database', xbmc.LOGDEBUG)
            count_update = 0
            if utils.getSetting("progressdialog") == 'true':
                 DIALOG_PROGRESS = xbmcgui.DialogProgress()
                 DIALOG_PROGRESS.create(utils.getString(32101), utils.getString(32106))
            for j in range(len(self.watchedepisodelist_wl)):
                if xbmc.abortRequested: break # this loop can take some time in debug mode and prevents xbmc exit
                if utils.getSetting("progressdialog") == 'true' and DIALOG_PROGRESS.iscanceled():
                    utils.showNotification(utils.getString(32205), utils.getString(32303)%(count_update)) 
                    return 2
                
                row_wl = self.watchedepisodelist_wl[j]
                imdbId = row_wl[0]
                season = row_wl[1]
                episode = row_wl[2]
                lastplayed_wl = row_wl[3]
                playcount_wl = row_wl[4]
                if utils.getSetting("progressdialog") == 'true':
                    DIALOG_PROGRESS.update(100*j/(len(self.watchedepisodelist_wl)-1), utils.getString(32106), utils.getString(32611) % (j+1, len(self.watchedepisodelist_wl), self.tvshownames[imdbId], season, episode) )
                # search the episodes matching in xbmc wl-list (multiple results possible)
                indices = [i for i, x in enumerate(self.watchedepisodelist_xbmc) if x[0] == imdbId and x[1] == season and x[2] == episode]
                for i in indices:
                    row_xbmc = self.watchedepisodelist_xbmc[i]
                    playcount_xbmc = row_xbmc[4]
                    lastplayed_xbmc = row_xbmc[3]
    
                    # check if update necessary
                    # compare playcount and lastplayed (update if xbmc data is older)
                    if not( playcount_xbmc < playcount_wl or lastplayed_xbmc < lastplayed_wl ):
                        if utils.getSetting("debug") == 'true':
                            utils.log('write_xbmc_wdata: xbmc database up-to-date for tt%d, S%02dE%02d' % (imdbId, season, episode), xbmc.LOGDEBUG)
                        continue
                    
                    # check if the lastplayed-timestamp in wl is useful
                    if lastplayed_wl == 0:
                        lastplayed_new = lastplayed_xbmc
                    else:
                        lastplayed_new = lastplayed_wl
                        
                    # update database
                    rpccmd = {
                              "jsonrpc": "2.0", 
                              "method": "VideoLibrary.SetEpisodeDetails", 
                              "params": {"episodeid": row_xbmc[5], "playcount": playcount_wl,  "lastplayed": utils.TimeStamptosqlDateTime(lastplayed_new)}, 
                              "id": 1
                              }
                    rpccmd = simplejson.dumps(rpccmd) # create string from dict
                    json_query = xbmc.executeJSONRPC(rpccmd)
                    json_query = unicode(json_query, 'utf-8', errors='ignore')
                    json_response = simplejson.loads(json_query)  
                    if json_response.has_key('result') and json_response['result'] == 'OK':
                   
                        utils.log('write_xbmc_wdata: xbmc database updated. playcount=%d (before: %d) for %s S%02dE%02d' % (playcount_wl, playcount_xbmc, self.tvshownames[imdbId], season, episode), xbmc.LOGDEBUG)
                        if utils.getSetting("debug") == 'true':
                            utils.showNotification(utils.getString(32401), '%s S%02dE%02d' % (self.tvshownames[imdbId], season, episode))
                        count_update += 1
                    else:
                        utils.log('write_xbmc_wdata: error updating xbmc database. playcount=%d. %s S%02dE%02d' % (playcount_wl, self.tvshownames[imdbId], season, episode))
            if utils.getSetting("progressdialog") == 'true': DIALOG_PROGRESS.close()
            utils.showNotification(utils.getString(32205), utils.getString(32303)%(count_update))    
        return 0
    
    
    
    
    
    # create a copy of the database, in case something goes wrong
    def database_copy(self):
        if utils.getSetting('dbbackup') == 'true' and (not self.dbcopydone):
            now = datetime.datetime.now()
            timestr = '%04d%02d%02d_%02d%02d%02d' % (now.year, now.month, now.day, now.hour, now.minute, now.second)
            zipfilename = os.path.join(self.dbdirectory, timestr + ' - watchedlist.db.zip')
            try:
                zf = zipfile.ZipFile(zipfilename, 'w')
                zf.write(self.dbpath, compress_type=zipfile.ZIP_DEFLATED, arcname='watchedlist.db')
                self.dbcopydone = True
                utils.log('database_copy: database backup copy created to %s' % zipfilename)
            except:
                buggalo.addExtraData('zipfilename', zipfilename);
                buggalo.onExceptionRaised()  
            finally:
                zf.close()
            