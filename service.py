import xbmc, xbmcgui, xbmcaddon, xbmcvfs
import re
import sys, os
import unicodedata
import time
import sqlite3

import resources.lib.utils as utils

if utils.getSetting('dbbackup') == 'true':
    import zipfile
    import datetime
    
# XBMC-JSON Datenbankabfrage
if sys.version_info < (2, 7):
    import simplejson
else:
    import json as simplejson


def get_timestamp(timestring):
    # now is time.time()
    timestamp = 0
    if timestring == '':
        timestamp = 0 # NULL timestamp
    return timestamp
        
# Main class of the add-on
class WatchedList:
    
    # entry point for autostart in xbmc
    def runAutostart(self):
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

            
    # infinite loop for periodic database update
    def runProgram(self):
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
        
    # entry point for manual start.
    # perform the update step by step
    def runUpdate(self):
        # check if player is running before doing the update
        while xbmc.Player().isPlaying() == True:
           if xbmc.abortRequested:
               return 1
           xbmc.sleep(60)
        # flag to remember copying the databasefile if requested
        self.dbcopydone = False   
        if utils.getSetting("progressdialog") == 'true':
            DIALOG_PROGRESS = xbmcgui.DialogProgress()
            DIALOG_PROGRESS.create( utils.getString(32101) , utils.getString(32102))
        # use the default file or a user file, for example to synchronize multiple clients
        if utils.getSetting("extdb") == 'false':
            self.dbdirectory = utils.data_dir()
            self.dbpath = os.path.join( utils.data_dir() , "watchedlist.db" )
        else:
            self.dbdirectory = utils.getSetting("dbpath").decode('utf-8') 
            self.dbpath = os.path.join( utils.getSetting("dbpath").decode('utf-8') , utils.getSetting("dbfilename").decode('utf-8') )
            if not os.path.isdir(utils.getSetting("dbpath")):
                utils.showNotification(utils.getString(32101)+': '+utils.getString(30001), utils.getString(30002)%(self.dbpath))
                utils.log('db path does not exist: %s' % self.dbpath)
                return 1              
            
        # load the addon-database
        if self.load_db():
            return 1
        if utils.getSetting("progressdialog") == 'true':
            DIALOG_PROGRESS.update(10 , utils.getString(32103))
        # get the watched state from the addon
        self.watchedmovielist_wl_index = list([]) # use separate liste for imdb-index and the watched data for easier searching through the lists
        self.watchedmovielist_wl_data = list([]) #
        self.watchedepisodelist_wl = list([]) # imdbnumber, season, episode, lastplayed, playcount
        self.get_watched_wl()
        
        # add the watched state from imdb ratings csv file, if existing
        
        # get watched state from xbmc
        if utils.getSetting("progressdialog") == 'true':
            DIALOG_PROGRESS.update(30 , utils.getString(32104))
        
        self.watchedmovielist_xbmc_index = list([]) # imdbnumber
        self.watchedmovielist_xbmc_data = list([]) # lastPlayed, playCount
        self.watchedepisodelist_xbmc = list([]) # imdbnumber, season, episode, lastplayed, playcount, episodeid
        self.tvshows = {} # imdbnumber, showname
        self.get_watched_xbmc()

        # import from xbmc into addon database
        if utils.getSetting("progressdialog") == 'true':
            DIALOG_PROGRESS.update(60 , utils.getString(32105))
        self.write_wl_wdata()
        
        # close the sqlite database (addon)
        self.sqlcon.close()
        
        # export from addon database into xbmc database
        if utils.getSetting("progressdialog") == 'true':
            DIALOG_PROGRESS.update(90 , utils.getString(32106))
        self.write_xbmc_wdata()
        
        if utils.getSetting("progressdialog") == 'true':
            DIALOG_PROGRESS.update(100 , utils.getString(32107))
            DIALOG_PROGRESS.close()
        
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
            return 1     
        # only commit the changes if no error occured to ensure database persistence
        self.sqlcon.commit()
        return 0
    
    def get_watched_xbmc(self):
        # Get all watched movies and episodes by unique id from xbmc-database via JSONRPC
        
        ############################################
        # movies
        if utils.getSetting("w_movies") == 'true':
            utils.log('get_watched_xbmc: Get watched movies from xbmc database', xbmc.LOGDEBUG)
            # use the JSON-RPC to access the xbmc-database.
            rpccmd = {
                      "jsonrpc": "2.0",
                      "method": "VideoLibrary.GetMovies", 
                      "params": {"properties": ["title", "year", "imdbnumber", "lastplayed", "playcount"], "sort": { "order": "ascending", "method": "title" }}, 
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
                    lastplayed = get_timestamp(item['lastplayed'])
                    self.watchedmovielist_xbmc_index.append(imdbId)
                    self.watchedmovielist_xbmc_data.append(list([lastplayed, int(item['playcount']), name, int(item['movieid'])]))
                    # DIALOG_PROGRESS.update(count/totalcount*100 , utils.getString(32105), name)
        
        ############################################
        # get imdb tv-show id from xbmc database
        if utils.getSetting("w_episodes") == 'true':
            utils.log('get_watched_xbmc: Get watched episodes from xbmc database', xbmc.LOGDEBUG)
            rpccmd = {
                      "jsonrpc": "2.0", 
                      "method": "VideoLibrary.GetTVShows", 
                      "params": {"properties": ["title", "imdbnumber"], "sort": { "method": "title" } }, 
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
                    # save title and imdbnumber in database for easier readibilty of the database
                    sql = 'INSERT OR IGNORE INTO tvshows (idShow,title) VALUES (?, ?)'
                    self.sqlcursor.execute(sql, self.tvshows[tvshowId_xbmc])
                self.sqlcon.commit()
                    
            ############################################        
            # tv episodes
            rpccmd = {
                      "jsonrpc": "2.0",
                      "method": "VideoLibrary.GetEpisodes",
                      "params": {"properties": ["tvshowid", "season", "episode", "playcount", "showtitle", "lastplayed"], "sort": { "order": "ascending", "method": "playcount" }},
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
                    tvshowId_imdb = self.tvshows[tvshowId_xbmc][0]
                    lastplayed = get_timestamp(item['lastplayed']) # convert to integer-timestamp
                    self.watchedepisodelist_xbmc.append(list([tvshowId_imdb, int(item['season']), int(item['episode']), lastplayed, int(item['playcount']), int(item['episodeid'])]))
        utils.showNotification( utils.getString(32101), utils.getString(32299)%(len(self.watchedmovielist_xbmc_index), len(self.watchedepisodelist_xbmc)) )
        
    def get_watched_wl(self):
        # get watched movies from addon database
        if utils.getSetting("w_movies") == 'true':
            utils.log('get_watched_wl: Get watched movies from WL database', xbmc.LOGDEBUG)
            self.sqlcursor.execute("SELECT idMovieImdb, lastPlayed, playCount, lastChange FROM movie_watched") 
            rows = self.sqlcursor.fetchall() 
            for row in rows:
                self.watchedmovielist_wl_index.append(row[0])
                self.watchedmovielist_wl_data.append(list([row[1], row[2]]))
        
        # get watched episodes from addon database
        if utils.getSetting("w_episodes") == 'true':
            utils.log('get_watched_wl: Get watched episodes from WL database', xbmc.LOGDEBUG)
            self.sqlcursor.execute("SELECT idShow, season, episode, lastPlayed, playCount FROM episode_watched") 
            rows = self.sqlcursor.fetchall() 
            for row in rows:
                self.watchedepisodelist_wl.append(list([row[0], row[1], row[2], row[3], row[4]]))
        utils.showNotification(utils.getString(32101), utils.getString(32298)%(len(self.watchedmovielist_wl_index), len(self.watchedepisodelist_wl)))
        
    def write_wl_wdata(self):
        # Go through all watched movies from xbmc and check whether they are up to date in the addon database
        if utils.getSetting("w_movies") == 'true':
            utils.log('write_wl_wdata: Write watched movies to WL database', xbmc.LOGDEBUG)
            count_insert = 0
            count_update = 0
            for i in range(len(self.watchedmovielist_xbmc_index)):
                imdbId = self.watchedmovielist_xbmc_index[i]
                row_xbmc = self.watchedmovielist_xbmc_data[i]
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
                        # compare playcount and lastplayed
    
                        
                        if playcount_xbmc == playcount_wl: # todo: consider lastplayed
                            if utils.getSetting("debug") == 'true':
                                utils.log(u'write_wl_wdata: wl database up-to-date for tt%d, %s' % (imdbId, row_xbmc[2]), xbmc.LOGDEBUG)
                            continue
                        # check if update necessary
                        sql = 'UPDATE movie_watched SET playCount = ? WHERE idMovieImdb LIKE ?'
                        values = list([playcount_wl, imdbId])
                        self.sqlcursor.execute(sql, values)
                        count_update += 1
                        
                    except ValueError:
                        # the movie is not in the watched-list -> insert the movie
                        # row = self.watchedmovielist_xbmc_data[i]
                        # order: idMovieImdb,playCount,lastChange,lastPlayed,title
                        values = list([imdbId, row_xbmc[1], int(time.time()), int(get_timestamp(row_xbmc[0])), row_xbmc[2]])
                        sql = 'INSERT INTO movie_watched (idMovieImdb,playCount,lastChange,lastPlayed,title) VALUES (?, ?, ?, ?, ?)'
                        self.sqlcursor.execute(sql, values)
                        utils.log(u'write_wl_wdata: new entry for wl database: tt%d, %s' % (imdbId, row_xbmc[2]))
                        count_insert += 1
                        if utils.getSetting("debug") == 'true':
                            utils.showNotification(utils.getString(32101) + ': ' + utils.getString(32402), row_xbmc[2])
                except sqlite3.Error as e:
                    utils.log(u'write_wl_wdata: Database error while updating movie tt%d, %s: %s' % (imdbId, row_xbmc[2], e.args[0]))
                    # error at this place is the result of duplicate movies, which produces a DUPLICATE PRIMARY KEY ERROR
                    continue
                except:
                    utils.log(u'write_wl_wdata: Error while updating movie tt%d, %s: %s' % (imdbId, row_xbmc[2], sys.exc_info()[2]))
                    if self.sqlcon:    
                        self.sqlcon.close()
                    return 1  
            # only commit the changes if no error occured to ensure database persistence
            if count_insert > 0 or count_update > 0:
                self.database_copy()
                self.sqlcon.commit()
            utils.showNotification(utils.getString(32101)+': '+utils.getString(32202), utils.getString(32301)%(count_insert, count_update))
              
 
        
        ################################################################        
        # Go through all watched episodes from xbmc database and check whether they are up to date in the addon database
        if utils.getSetting("w_episodes") == 'true':
            utils.log('write_wl_wdata: Write watched episodes to WL database', xbmc.LOGDEBUG)
            count_insert = 0
            count_update = 0
            for i in range(len(self.watchedepisodelist_xbmc)):
                row_xbmc = self.watchedepisodelist_xbmc[i]
                imdbId = row_xbmc[0]
                season = row_xbmc[1]
                episode = row_xbmc[2]
                lastplayed_xbmc = row_xbmc[3]
                playcount_xbmc = row_xbmc[4]
                
                if playcount_xbmc == 0:
                    # playcount in xbmc-list is empty. Nothing to save
                    if utils.getSetting("debug") == 'true':
                        utils.log('write_wl_wdata: not watched in xbmc: tt%d, S%02dE%02d' % (imdbId, season, episode), xbmc.LOGDEBUG)
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
                        # check if an update of the wl database is necessary
                        if playcount_xbmc == row_wl[4]:
                            continue
                        sql = 'UPDATE episode_watched SET playCount = ? WHERE idShow LIKE ? AND season LIKE ? AND episode LIKE ?'
                        values = list([playcount_xbmc, imdbId, season, episode])
                        self.sqlcursor.execute(sql, values)
                        count_update += 1
                    else:
                        # insert new watched episode into wl database
                        sql = 'INSERT INTO episode_watched (idShow,season,episode,playCount,lastChange,lastPlayed) VALUES (?, ?, ?, ?, ?, ?)'
                        values = list([imdbId, season, episode, playcount_xbmc, int(time.time()), lastplayed_xbmc])
                        self.sqlcursor.execute(sql, values)
                        count_insert += 1
                    if utils.getSetting("debug") == 'true':
                        idtmp = next((xbmcid for xbmcid, tvshow_row in self.tvshows.items() if tvshow_row[0] == imdbId), None)
                        showname = self.tvshows[idtmp][1]
                        utils.showNotification(utils.getString(32101) + ': ' + utils.getString(32402), '%s S%02dE%02d' % (showname, season, episode))
                        utils.log(u'write_wl_wdata: SQL Entry Episode tt%d S%02dE%02d: playcount %d' % (imdbId, season, episode, playcount_xbmc), xbmc.LOGDEBUG)
    
                except sqlite3.Error as e:
                    utils.log(u'write_wl_wdata: Database error while updating episode tt%d S%02dE%02d: %s' % (imdbId, season, episode, e.args[0]))
                    # error at this place is the result of duplicate movies, which produces a DUPLICATE PRIMARY KEY ERROR
                    continue
                except:
                    utils.log(u'write_wl_wdata: Error while updating movie tt%d S%02dE%02d: %s' % (imdbId, season, episode, sys.exc_info()[2]))
                    if self.sqlcon:    
                        self.sqlcon.close()
                    return 1
            self.sqlcon.commit()
            utils.showNotification(utils.getString(32101)+': '+utils.getString(32203)+' (Addon)', utils.getString(32301)%(count_insert, count_update))
        return 0
        
    def write_xbmc_wdata(self):
        # Go through all watched movies from the wl-database and check, if the xbmc-database is up to date
        if utils.getSetting("w_movies") == 'true':
            utils.log('write_xbmc_wdata: Write watched movies to xbmc database', xbmc.LOGDEBUG)
            count_update = 0
            for j in range(len(self.watchedmovielist_wl_index)):
                imdbId = self.watchedmovielist_wl_index[j]
                row_wl = self.watchedmovielist_wl_data[j]
                try:
                    # search the imdb id in the xbmc-list
                    try:
                        # the movie is already in the xbmc-list
                        i = self.watchedmovielist_xbmc_index.index(imdbId)
                        row_xbmc = self.watchedmovielist_xbmc_data[i]
                        playcount_xbmc = row_xbmc[1]
                        playcount_wl = row_wl[1]
                        # compare playcount (todo: and lastplayed)
                        if playcount_xbmc == playcount_wl:
                            if utils.getSetting("debug") == 'true':
                                utils.log('write_xbmc_wdata: xbmc database up-to-date for tt%d, %s' % (imdbId, row_xbmc[2]), xbmc.LOGDEBUG)
                            continue
                        # update database
                        rpccmd = {
                                  "jsonrpc": "2.0", 
                                  "method": "VideoLibrary.SetMovieDetails", 
                                  "params": {"movieid": row_xbmc[3], "playcount": playcount_wl}, 
                                  "id": 1
                                  }
                        rpccmd = simplejson.dumps(rpccmd) # create string from dict
                        json_query = xbmc.executeJSONRPC(rpccmd)
                        json_query = unicode(json_query, 'utf-8', errors='ignore')
                        json_response = simplejson.loads(json_query)  
                        if (json_response.has_key('result') and json_response['result'] == 'OK'):
                            utils.log('write_xbmc_wdata: xbmc database updated. playcount=%d (before: %d) for tt%d, %s' % (playcount_wl, playcount_xbmc, imdbId, row_xbmc[2]))
                            if utils.getSetting("debug") == 'true':
                                utils.showNotification(utils.getString(32101) + ': ' + utils.getString(32401), row_xbmc[2])
                            count_update += 1
                        else:
                            utils.log('write_xbmc_wdata: error updating xbmc database. tt%d, %s' % (imdbId, row_xbmc[2]))
                        
                    except ValueError:
                        # the movie is in the watched-listbut not in the xbmc-list -> no action
                        utils.log('write_xbmc_wdata: movie not in xbmc database: tt%d, %s' % (imdbId, row_xbmc[2]))
                        continue
                except:
                    utils.log("write_xbmc_wdata: Error while updating movie tt%d, %s: %s" % (imdbId, row_xbmc[2], sys.exc_info()[2]))
                    return 1  
            utils.showNotification(utils.getString(32101)+': '+utils.getString(32202)+' (XBMC)', utils.getString(32302)%(count_update))    

        
        # Go through all watched episodes from the wl-database and check, if the xbmc-database is up to date
        if utils.getSetting("w_episodes") == 'true':
            utils.log('write_xbmc_wdata: Write watched episodes to xbmc database', xbmc.LOGDEBUG)
            count_update = 0
            for j in range(len(self.watchedepisodelist_wl)):
                row_wl = self.watchedepisodelist_wl[j]
                imdbId = int(row_wl[0])
                season = int(row_wl[1])
                episode = int(row_wl[2])
                lastplayed_xbmc = int(row_wl[3])
                playcount_wl = int(row_wl[4])
                # search the episode in xbmc wl-list
                found = False
                for i in range(len(self.watchedepisodelist_xbmc)):
                    row_xbmc = self.watchedepisodelist_xbmc[i]
                    playcount_xbmc = row_xbmc[4]
                    if row_xbmc[0] == imdbId and row_xbmc[1] == season and row_xbmc[2] == episode:
                        found = True
                        break
                if not found:
                    # episode not in xbmc database. No update necessary
                    continue
                # check if update necessary
                # compare playcount (todo: and lastplayed)
                if playcount_xbmc == playcount_wl:
                    if utils.getSetting("debug") == 'true':
                        utils.log('write_xbmc_wdata: xbmc database up-to-date for tt%d, S%02dE%02d' % (imdbId, season, episode), xbmc.LOGDEBUG)
                    continue
                # update database
                rpccmd = {
                          "jsonrpc": "2.0", 
                          "method": "VideoLibrary.SetEpisodeDetails", 
                          "params": {"episodeid": row_xbmc[5], "playcount": playcount_wl}, 
                          "id": 1
                          }
                rpccmd = simplejson.dumps(rpccmd) # create string from dict
                json_query = xbmc.executeJSONRPC(rpccmd)
                json_query = unicode(json_query, 'utf-8', errors='ignore')
                json_response = simplejson.loads(json_query)  
                if json_response.has_key('result') and json_response['result'] == 'OK':
                    utils.log('write_xbmc_wdata: xbmc database updated. playcount=%d for tt%d, S%02dE%02d (before: %d)' % (playcount_wl, imdbId, season, episode, playcount_xbmc), xbmc.LOGDEBUG)
                    if utils.getSetting("debug") == 'true':
                        idtmp = next((xbmcid for xbmcid, tvshow_row in self.tvshows.items() if tvshow_row[0] == imdbId), None)
                        showname = self.tvshows[idtmp][1]
                        utils.showNotification(utils.getString(32101) + ': ' + utils.getString(32401), '%s S%02dE%02d' % (showname, season, episode))
                    count_update += 1
                else:
                    utils.log('write_xbmc_wdata: error updating xbmc database. tt%d, S%02dE%02d' % (playcount_wl, imdbId, season, episode))
            utils.showNotification(utils.getString(32101)+u': '+utils.getString(32203)+u' (XBMC)', utils.getString(32303)%(count_update))        
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
            finally:
                zf.close()
            