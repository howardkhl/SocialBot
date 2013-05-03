#------------------------------------------------------------------------------
# Author: Howard Lee 
#
# CSS 490 - SocialBot
# Spring, 2012
# Professor: Joe McCarthy
# 
# Group Name: BotOuttaHell
# Group Members: Jordan Carroll
#                Owen Hart
#                Ilya Novichenko
#                Keng-Wei (Jack) Chang
#                Howard Lee
#
# Strategy:
# We wrote a script to run our bot every 12 minutes
# In each run:
#   1. Follow 1~2 users
#   2. Check for mentions, iterate and reply to each mention (chance: always).
#   3. Grab a random target's timeline (chance: 1 in 2) and do either 
#      a reply (chance: 19 in 20) or retweet (chance: 1 in 20).
#   4. Tweet a canned message (chance: 1 in 20)
#
# For each reply, we utilize a web-based chat service Omegle 
#   (http://www.omegle.com). Our bot disguises itself as an human user 
#   to chat with another human user (could be bot as well). We start the 
#   chat by using Cleverbot as a conversation starter, after the human user 
#   at the other end feels comfortable, we'll then post the tweet which was 
#   grabbed from Twitter target's mention/timeline and see what kind of 
#   response we get from that human user. The response is then filtered 
#   through a list of "bad words", if it passes, we'll use it as a legit 
#   Twitter tweet; if not, the cycle restarts and a new human user is chosen.
#
# External resources used:
#   1. Omegle API
#   2. Cleverbot API
#
# Assumption:
# -- All files, including oauthfile are stored in Data\ folder.
# -- Args function written but not fully implemented. Using constant variables.
#------------------------------------------------------------------------------

from __future__ import division
from twitter.api import Twitter, TwitterError
from twitter.oauth import OAuth, write_token_file, read_token_file
from twitter.oauth_dance import oauth_dance
from pyomegle import GetAnswerTo
from TweetModifier import modifyTweet
from TweetModifier import stripUrls
from datetime import *

import argparse
import urllib2
import sys
import os
import random

DEBUG_MODE = False

#----------- constants ------------------
CONSUMER_KEY = 'p4VB8D8fg2lkZ0YoLCdVZQ'                         # Updated key
CONSUMER_SECRET = 'XsiyoHpTR4PqMm3GHKml77bdht4osggkJs2bRN1ug'   # Updated secret

#DEFAULT_USER = 'RulerBot'                       # default user
#USER_NAME = 'Ruler Bot'                      # default user name
FILE_TARGET_IDS = 'Data/target_user_ids.txt'    # change this before real deployment!
FILE_FOLLOWED_IDS = 'Data/followed_ids.txt'          # list of already followed ids
FILE_FOLLOWERS_IDS = 'Data/followers_ids.txt'          # list of followers ids
FILE_TWEET_IDS = 'Data/tweet_ids.txt'                # list of already tweeted ids
FILE_LAST_MENTION_ID = 'Data/last_mention_id.txt'    # id of last mentioned tweet
FILE_TWEETED_MESSAGES = 'Data/tweeted_messages.txt'  # list of tweeted messages
FILE_CANNED_MESSAGES = 'Data/canned_messages.txt'    # list of canned messages
FILE_TWITTER_OAUTH = 'Data/twitter_oauth.txt'        # oauto credential

DIRECTORY_TARGETS = "Targets/"				# where we store the already tweeted ids of each individual users

NUM_USERS_TO_FOLLOW_PER_DAY = 8                 # number of users to follow per day
NUM_HOURS_TO_RUN_PER_DAY = 17                   # number of hours to run per day
NUM_RUNS_PER_HOUR = 10                           # number of runs per hour
CHANCE_FOLLOW_TARGET = NUM_USERS_TO_FOLLOW_PER_DAY / NUM_HOURS_TO_RUN_PER_DAY/NUM_RUNS_PER_HOUR

CHANCE_TWEET_CANNED_MESSAGE = 1/20              # chance to tweet a canned message
CHANCE_TWEET_TARGET_TIMELINE = 1                # chance to tweet something from target's timeline
CHANCE_RETWEET = 1/20                           # chance to retweet
CHANCE_OMEGLE = 19/20                           # chance to omegle

DEFAULT_LAST_MENTION = '1'                      # default last mention id
MENTION_COUNT = 20                              # num of mentions to acquire
TARGET_FOLLOW = 2                               # num of targets to follow
LATEST_TWEET_COUNT = 5                          # num of latest tweets
REPLY_RETRY_COUNT = 10                          # num of times to look up target

#---------- variables -------------------
target_ids = []             # list of target ids
followed_ids = []           # list of followed target ids
follower_ids = []           # list of follower ids
tweet_ids = []              # list of tweet ids
tweeted_messages = []       # list of tweeted messages
canned_messages = []        # list of canned messages

#------------ main ----------------------
def main():

    parser = argparse.ArgumentParser(
        description = 'Twitter user: ' + DEFAULT_USER,
        epilog = 'It is a bot, or is it?')

    #--- parse arguments --------------------------------------
    try:
        parser.add_argument('-u', '--username', default = DEFAULT_USER)
        parser.add_argument('-t', '--targetids', default = FILE_TARGET_IDS)
        parser.add_argument('-l', '--lastmentionid', default = FILE_LAST_MENTION_ID)
        parser.add_argument('-m', '--cannedmessages', default = FILE_CANNED_MESSAGES)
        parser.add_argument('-o', '--oauthfile', default = FILE_TWITTER_OAUTH)        
    except:
        print 'Error parsing argument(s)\n'

    #--- set and assign args ----------------------------------
    args = parser.parse_args()
    display_args( args )
    check_username( args.username )
    set_target_ids( args.targetids )
    last_mention_id = set_last_mention_id( args.lastmentionid )
    set_canned_messages( args.cannedmessages )
    set_followed_ids()
    set_tweet_ids()
    set_tweeted_messages()
        
    #--- register oauth and get twitter tools -----------------
    t1, t2 = get_twitter_tools( args.oauthfile )
    set_follower_ids(t2)
    #--- acquire and follow a new target ----------------------
    if get_probability( CHANCE_FOLLOW_TARGET ):
        follow_target( t2 )

    #--- check own timeline for mentions ----------------------
    check_mentions( last_mention_id, t2 )
    
    #--- retweet / omegle latest tweet from most recently added target ---
    if get_probability( CHANCE_TWEET_TARGET_TIMELINE ):
        find_and_reply_target( t2 )
    
    #--- tweet a canned message ---
    if get_probability( CHANCE_TWEET_CANNED_MESSAGE ):
        tweet_canned_message( t2 )

def set_args( args ):
    username = args.username
    target_ids_floc = args.targetids
    last_mention_id_floc = args.lastmentionid
    canned_messages_floc = args.cannedmessages
        
def display_args( args ):
    print '\n', 'username =', args.username, \
          '\n', 'targetids =', args.targetids, \
          '\n', 'lastmentionid =', args.lastmentionid, \
          '\n', 'cannedmessages =', args.cannedmessages, \
          '\n', 'oauthfile =', args.oauthfile, '\n'
        
def get_probability( chance ):
    if random.random() < chance:
        return True
    else:
        return False

def get_twitter_tools( oauthfile ):
    #--- register oauth tokens -------------------------------------------
    try:
        oauth_token, oauth_token_secret = read_token_file( oauthfile )
    except IOError:
        print 'OAuth file {} not found'.format( oauthfile )
        response = raw_input( 'Do you want to initiate a new oauth dance (y or n)? ' )
        if not ( len( response ) > 0 and response[0].upper() == 'Y' ):
            oauth_token = oauth_token_secret = ''
        else:  
            oauth_token, oauth_token_secret = oauth_dance('Brilliant App', 
                CONSUMER_KEY, CONSUMER_SECRET, token_filename=oauthfile)

    #--- t1 = Twitter Search API, t2 = Twitter REST API ------------------
    t1 = Twitter(domain='search.twitter.com')
    t2 = Twitter(
        auth=OAuth(
            oauth_token, oauth_token_secret, CONSUMER_KEY, CONSUMER_SECRET),
        secure=True,
        api_version='1',
        domain='api.twitter.com')
    return t1, t2

def check_username( username ):
    try:
        urllib2.urlopen( "https://api.twitter.com/1/users/lookup.json?screen_name={}".format( username ) )  
    except urllib2.HTTPError:
        print 'Invalid user id / screenname, terminating...'
        exit()
  
def set_target_ids( floc ):
    global target_ids
    target_ids_floc = floc
    try: 
        target_ids_file = open( target_ids_floc, 'r' ) 
        # populate target_ids array for later use
        for line in target_ids_file:
            tid = line.rstrip( '\n' )
            target_ids.append( tid )       
    except IOError:
        print target_ids_floc, 'not found, terminating...'
        exit()
    
def set_followed_ids():
    global followed_ids
    try: 
        followed_ids_file = open( FILE_FOLLOWED_IDS, 'r' ) 
        # populate followed_ids array for later use
        for line in followed_ids_file:
            fid = line.rstrip( '\n' )
            followed_ids.append( fid )
    except IOError:
        print FILE_FOLLOWED_IDS, 'not found\n'
        print 'Creating ' + FILE_FOLLOWED_IDS
        followed_ids_file = open(FILE_FOLLOWED_IDS, 'w')
        followed_ids_file = open(FILE_FOLLOWED_IDS, 'r')
        print FILE_FOLLOWED_IDS + ' created successfully\n'
def set_follower_ids(t2):
    global follower_ids
    try: 
        follower_ids = t2.followers.ids( id = DEFAULT_USER )
    except:
        print 'Unable to get list of followers'
def set_tweet_ids():
    global tweet_ids
    try: 
        tweet_ids_file = open( FILE_TWEET_IDS, 'r' ) 
        # populate tweet_ids array for later use
        for line in tweet_ids_file:
            tid = line.rstrip( '\n' )
            tweet_ids.append( tid )
        tweet_ids_file.close()
    except IOError:
        print FILE_TWEET_IDS, 'not found\n'
        print 'Creating ' + FILE_TWEET_IDS
        tweet_ids_file = open(FILE_TWEET_IDS, 'w')
        tweet_ids_file = open(FILE_TWEET_IDS, 'r')
        print FILE_TWEET_IDS + ' created successfully\n'
        tweet_ids_file.close()

def set_last_mention_id( floc ):
    try:
        last_mention_id_floc = floc 
        last_mention_id_file = open( last_mention_id_floc, 'r') 
    except IOError:
        print last_mention_id_floc, 'not found\n'
        print 'Creating ' + last_mention_id_floc + ' with default id = ' + DEFAULT_LAST_MENTION
        last_mention_id_file = open(last_mention_id_floc, 'w')
        last_mention_id_file.write( DEFAULT_LAST_MENTION )
        last_mention_id_file = open(last_mention_id_floc, 'r')
        print last_mention_id_floc + ' created successfully\n'

    return last_mention_id_file.readline()
        
def set_canned_messages( floc ):
    global canned_messages
    try:
        canned_messages_floc = floc
        canned_messages_file = open( canned_messages_floc, 'r') 
        # populate canned_messages array for later use
        for line in canned_messages_file:
            tmsg = line.rstrip( '\n' )
            canned_messages.append( tmsg )        
    except IOError:
        print canned_messages_floc, 'not found, terminating...'
        exit()

def set_tweeted_messages():
    global tweeted_messages
    try: 
        tweeted_messages_file = open( FILE_TWEETED_MESSAGES, 'r' ) 
        # populate tweeted_messages array for later use
        for line in tweeted_messages_file:
            tmsg = line.rstrip( '\n' )
            tweeted_messages.append( tmsg )
    except IOError:
        print FILE_TWEETED_MESSAGES, 'not found\n'
        print 'Creating ' + FILE_TWEETED_MESSAGES
        tweeted_messages_floc = open(FILE_TWEETED_MESSAGES, 'w')
        tweeted_messages_floc = open(FILE_TWEETED_MESSAGES, 'r')
        print FILE_TWEETED_MESSAGES + ' created successfully\n'
    
def follow_target( t2 ):
    """
    Compare target id to list of followed ids, if not already in list,
    follow that target and add target id to list of followed ids.
    """
    global target_ids
    global followed_ids
    
    success = False
    for i in range( TARGET_FOLLOW ):
        for tid in target_ids:
            if tid not in followed_ids:
                try:
                    target_obj = t2.friendships.create( id = tid )
                    print 'Friendship created successfully with @' + target_obj['screen_name'] + ' (' + tid + ')' + '\n'
                    followed_ids_file = open( FILE_FOLLOWED_IDS, 'a' )
                    followed_ids_file.write( tid + '\n' )
                    followed_ids_file.close()
                    followed_ids.append( tid )
                    success = True
                    return
                except:
                    print 'Error, friendship not created'
                    return
    if success == False:
        print 'No new target to follow...\n'
  
def check_mentions( id, t2 ):
    """
    Grab bot's own list of mentions, iterate thru the list, modify each
    mention and post it on Omegle. Grab result from Omegle and reply
    back on Twitter to user that mentioned it.
    """
    global tweet_ids
    
    try:
        mentions = t2.statuses.mentions( since_id = id, 
                                     include_rts = 1, include_entities=1, count = MENTION_COUNT )
    except:
        print 'TwitterHTTPError, mentions not received...\n'
        return
        
    #--- check for new mentions ---
    if len( mentions ) == 0:
        print 'No new mentions at this time...\n'
    else:
        print 'Number of new mentions:', len( mentions ), '\n'
    
    if DEBUG_MODE:
        print 'tweet ids before loop:'
        print '(', tweet_ids, ')', '\n'
    
    #--- iterate list of mentions, omegle, and reply accordingly ---
    count = len( mentions ) - 1
    while count >= 0:
        #--- check the id list again to see if any other cron job process added an id to the list. Update array.
        tweet_ids = []
        set_tweet_ids()
        
        if DEBUG_MODE:
            print 'tweet ids after reset:'
            print '(', tweet_ids, ')', '\n'
        
        #--- verify if already replied this mention ---
        if mentions[count]['id_str'] not in tweet_ids:
            
            #--- store tweet id so we won't run thru it again in future ---
            tweet_ids.append( mentions[count]['id_str'] )
            
            if DEBUG_MODE:
                print 'tweet ids after appending:'
                print '(', tweet_ids, ')', '\n'
            
            tweet_ids_file = open( FILE_TWEET_IDS, 'a' )
            tweet_ids_file.write( mentions[count]['id_str'] + '\n' )
            tweet_ids_file.close()
            
            #--- write and update last_mention_id ---
            last_mention_id_file = open( FILE_LAST_MENTION_ID, 'w')
            last_mention_id_file.write( mentions[count]['id_str'] )
            last_mention_id_file.close()
            
            #--- modify mention string ---
            original_mention = mentions[count]['text'].encode('utf-8')
            print 'Original:', original_mention, '(from @' + mentions[count]['user']['screen_name'] + ')'
            mod_mention = modifyTweet( mentions[count], DEFAULT_USER )
            print 'Modified: ' + mod_mention.encode('utf-8') + '\n'
            print 'Sending request to Omegle on:'
            print datetime.now(), '\n'
            
            if DEBUG_MODE:
                raw_input("wait...")
            
            #--- post on Omegle and grab response ---
            omegle_reply = GetAnswerTo( mod_mention.encode('utf-8') )
            if str( omegle_reply ) == '':
                print 'Error: not supposed to receive empty string from Omegle...\n'
                return
            
            #--- reply to user ---
            reply = '@' + str( mentions[count]['user']['screen_name'] ) + ' ' + str( omegle_reply )
            try:
                tweet = t2.statuses.update( status = reply, in_reply_to_status_id = mentions[count]['id'] )
            except:
                print 'Error tweeting, possibly duplicated response by Cleverbot, trying again...\n'
                return
            print '\n', '<<<===', original_mention
            print '===>>>', tweet['text'].encode('utf-8')
            print datetime.now(), '\n'
        else:
            print 'Already replied this mention, next...\n'
            
            #--- write and update last_mention_id ---
            last_mention_id_file = open( FILE_LAST_MENTION_ID, 'w')
            last_mention_id_file.write( mentions[count]['id_str'] )
            last_mention_id_file.close()
            
        count = count - 1

'''
--- Example ---
userFile = checkOutUser( 2034 )
if userFile:
    userFile.write("Hey")
    raw_input("wait...")
    checkInUser( userFile )
else:
    print "File in use."
'''
def checkOutUser( uid ):
    while True:
        try:
            print "Opening file..."
            f = open( DIRECTORY_TARGETS + str(uid) + ".usr", 'r+' )
            try:
                f2 = open( DIRECTORY_TARGETS + str(uid) + ".lock", 'r' )
                return None
            except:
                f2 = open( DIRECTORY_TARGETS + str(uid) + ".lock", 'w')
                f2.close()
            print "Success!"
            return f
        except:
            print "File not found. Creating."
            if not os.path.exists(DIRECTORY_TARGETS):
                os.makedirs(DIRECTORY_TARGETS)
            f = open( DIRECTORY_TARGETS + str(uid) + ".usr", 'w' )
            f.close()

def checkInUser( userFile ):
    try:
        userFile.close()
        os.remove( userFile.name.replace('.usr', '.lock' ) )
    except: pass

def find_and_reply_target( t2 ):
    """
    Find a target.
    """
    count = REPLY_RETRY_COUNT
    tweeted = False
    while tweeted == False and count > 0:
        
        #--- get a random target id ---
        #target_id = get_random_target()
        follower_id = get_follower_target()
        print 'Finding next target...follower id =', str(follower_id)
        
        #--- check if we tweeted successfully ---
        tweeted = reply_target( follower_id, t2 )
        if tweeted == False:
            count = count - 1
        if count == 0:
            print 'Finding target has reached max iteration of:', REPLY_RETRY_COUNT, '...Move on to next task...\n'
          
def get_random_target():
    """
    Return a random target from a list of target ids.
    Return 0 if not found.
    """
    global followed_ids
    followed_ids_count = len( followed_ids )
    if followed_ids_count != 0:
        return followed_ids[random.randint(0,(followed_ids_count-1))]
    else:
        return 0        
def get_follower_target():
    """
    Return a random target from a list of follower ids.
    Return 0 if not found.
    """
    global follower_ids
    follower_ids_count = len( follower_ids['ids'] )
    if follower_ids_count != 0:
        return follower_ids['ids'][random.randint(0,(follower_ids_count-1))]
    else:
        return 0        
def get_tweet( target_id, t2 ):
    """
    Return a tweet from given target. A valid tweet consists of:
    1. Has not yet been replied
    2. Does not mention another user rather the bot
    """
    global tweet_ids
    try:
        tweets = t2.statuses.user_timeline( id = target_id, include_entities=1, count = LATEST_TWEET_COUNT )
        
        #--- check the id list again to see if any other cron job process added an id to the list. Update array.
        tweet_ids = []
        set_tweet_ids()
        
        # #--- grab a random tweet from a num of latest tweets, filter out replied ---
        # tweet = tweets[ random.randint(0, LATEST_TWEET_COUNT-1) ]         
        # if tweet['id_str'] in tweet_ids:
            # print 'Target has invalid tweet: already replied this one...\n'
            # return ''
        # else:
            # return tweet
            
        #--- filter tweets that has mention of other users, and the ones we already replied ---
        for tweet in tweets:
            print '@' + str( tweet['user']['screen_name'] ) + ': ' + tweet['text'].encode('utf-8')
            if tweet['text'].find( '@' ) != -1 and \
               tweet['text'].find( '@' + DEFAULT_USER ) == -1:
                print 'Target has invalid tweet: cannot have mention of other users...\n'
            elif tweet['id_str'] in tweet_ids:
                print 'Target has invalid tweet: already replied this one...\n'
            else:
                return tweet
        return ''
    except TwitterError:
        print 'Hell Mary! we are catching TwitterHTTPError...\n'
        return ''
    except:
        print 'Unexplainable error happened, can someone grab me a coffee already?\n'
        return ''
    
def reply_target( follower_id, t2 ):
    """
    Find a valid tweet from target, modify and
    Omegle it, then tweet a reply to target.
    """
    global tweet_ids
    
    #--- check for invalid target_id ---
    #if target_id == None or target_id == 0:
    #    print 'Invalid target id, retweet failed...\n'
    #    return False
    if follower_id == None or follower_id == 0:
        print 'Invalid follower id, mention failed...\n'
        return False
    #--- grab target's tweet ---
    #print 'Getting Tweet from Target Set'
    #tweet = get_tweet( str(target_id), t2 )
    print 'Getting Tweet from Follower Set'
    ftweet = get_tweet( str(follower_id), t2 )
    #if tweet == '' or tweet == None:
    #    return False
    if ftweet == '' or ftweet == None:
        return False
    else:
        #--- save tweet id, so we won't accidentally go at it again ---
        #tweet_ids.append( tweet['id_str'] ) 
        tweet_ids.append( ftweet['id_str'] ) 
        tweet_ids_file = open( FILE_TWEET_IDS, 'a' )
        #tweet_ids_file.write( tweet['id_str'] + '\n' )
        tweet_ids_file.write( ftweet['id_str'] + '\n' )
        tweet_ids_file.close()
        
        #--- retweet (1/20 chance) or omegle (19/20 chance) the tweet ---
        if get_probability( CHANCE_OMEGLE ):
            #--- display console info ---
            print 'Tweet by Follower: @' + ftweet['user']['screen_name'] + ':', ftweet['text'].encode('utf-8'), '\n'
            #--- post tweet on Omegle, modify response and tweet ---
            modified_tweet = modifyTweet( ftweet, DEFAULT_USER ).encode('utf-8')
            print 'Send to Omegle:', modified_tweet
            print datetime.now(), '\n'
            omegle_reply = ''
            omegle_reply = GetAnswerTo( modified_tweet )
            omegle_reply = stripUrls( omegle_reply )
            if str( omegle_reply ) == '':
                print 'Error: not supposed to receive empty string from Omegle...\n'
                return False
            reply = '@' + str( ftweet['user']['screen_name'] ) + ' ' + str( omegle_reply )
            try:
                reply_tweet = t2.statuses.update( status = reply, in_reply_to_status_id = ftweet['id'] )
            except:
                print 'Error tweeting, possibly duplicated response by Cleverbot, skipping...\n'
                return False 
            print '\n', 'Replying tweet by @' + str( ftweet['user']['screen_name'] ) + ':'
            print '<<<===', ftweet['text'].encode('utf-8')
            print '===>>>', reply_tweet['text'].encode('utf-8')
            print datetime.now(), '\n'
        else:
            #--- display console info ---
            print 'Tweet by @' + ftweet['user']['screen_name'] + ':', ftweet['text'].encode('utf-8'), '\n'
            #--- retweet only, how boring... ---
            try:
                t2.statuses.retweet( id = ftweet['id'] )
                print 'Very low chance, but bot retweeted target tweet.\n'
            except TwitterError:
                print '\n', 'Wota! Another TwitterHTTPError...\n'

        return True
    
def tweet_canned_message( t2 ):
    """
    Compare canned message to list of tweeted messages, if not already in list,
    tweet that canned message and add it to list of tweeted messages.
    """
    global canned_messages
    global tweeted_messages
    
    for cmsg in canned_messages:
        if cmsg not in tweeted_messages:
            try:
                t2.statuses.update( status = cmsg )
                print 'Tweeting canned message...'
                print '===>>> ' + cmsg.encode('utf-8')
                print datetime.now(), '\n'
            except:
                print 'Error tweeting canned message...\n'
                return
            try:
                tweeted_messages_file = open( FILE_TWEETED_MESSAGES, 'a' )
                tweeted_messages_file.write( cmsg + '\n' )
                tweeted_messages_file.close()
                tweeted_messages.append( cmsg )
                return
            except:
                print 'Error open/write', FILE_TWEETED_MESSAGES, '\n'
                return
    print 'No new canned message to tweet...\n'
    
if __name__ == '__main__':
    main()
