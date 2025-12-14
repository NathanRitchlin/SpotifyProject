import requests
from flask import Flask, redirect, request, jsonify, session, render_template
import urllib.parse
import os
from datetime import datetime
from dotenv import load_dotenv
from google import genai
from openai import OpenAI
load_dotenv()
import time

app = Flask(__name__)
app.secret_key = os.getenv("secretKey")
clientID = os.getenv("clientID")
clientSecret = os.getenv("clientSecret")
aiKey = os.getenv("aiKey")
gptKey = os.getenv("gptKey")
redirectURI = "http://127.0.0.1:8888/callback"
authURL = "https://accounts.spotify.com/authorize"
tokenURL = "https://accounts.spotify.com/api/token"
apiBaseURL = "https://api.spotify.com/v1/"
clientGoogle = genai.Client(api_key= aiKey)
clientGPT = OpenAI(api_key= gptKey)


#Opening page of the website
@app.route("/")
def index():
    return "<h1>Welcome to the liked songs additional features website.</h1> <a href = '/login'> Login to spotify here </a> <br> <p>Note that when logging in, you are allowing this website to look at and alter your spotify account.</p>"

#Logs the user into their spotify account
@app.route("/login")
def login():
    scope = "user-read-playback-state playlist-modify-public user-library-read user-read-email"
    params = {
        "client_id": clientID,
        "response_type": "code",
        "scope": scope,
        "show_dialog": True,
        "redirect_uri": redirectURI,
        "show_dialog": False

    }

    auth_url = f"{authURL}?{urllib.parse.urlencode(params)}"
    return redirect(auth_url)

#rerouting page used when logging in to obtain acess tokens for the spotify API
@app.route("/callback")
def callback():
    if("error" in request.args):
        return jsonify({"error": request.args["error"]})
    if "code" in request.args:
        reqBody = {
            "grant_type" : "authorization_code",
            "code" : request.args["code"],
            "redirect_uri" : redirectURI,
            "client_id": clientID,
            "client_secret" : clientSecret
        }

        response = requests.post(tokenURL, data=reqBody)
        print(response)
        tokenInfo = response.json()
        session["access_token"] = tokenInfo["access_token"]
        session["refresh_token"] = tokenInfo["refresh_token"]
        session["expires_at"] = datetime.now().timestamp() + tokenInfo["expires_in"]

        return "<a href = '/artistGender'> Check the gender of your liked songs artists <a> <h2>OR</h2> <a href = '/likedsongs'> Check which liked songs arent in playlists </a> <h2>OR</h2> <a href = '/popularity'> Rank your liked songs by popularity </a> <br> <br><br><br><br><a href= '/feedback'> Give us some feedback! </a>"


#main website webpage
@app.route("/main")
def main():
    if("access_token" not in session):
        return redirect("/login")
    if(datetime.now().timestamp() > session["expires_at"]):
        return redirect("/refresh-token")
    return "<a href = '/artistGender'> Check the gender of your liked songs artists <a> <h2>OR</h2> <a href = '/likedsongs'> Check which liked songs arent in playlists </a> <h2>OR</h2> <a href = '/popularity'> Rank your liked songs by popularity </a> <br> <br><br><br><br><a href= '/feedback'> Give us some feedback! </a>"

#if the current API token runs out, a new one is acquired
@app.route("/refresh-token")
def refresh_token():
    if "refresh_token" not in session:
        return redirect("/login")
    if(datetime.now().timestamp() > session["expires_at"]):
        req_body = {
            "grant_type": "refresh_token",
            "refresh_token" : session["refresh_token"],
            "client_id": clientID , 
            "client_secret": clientSecret
        }
        response = requests.post(tokenURL, data = req_body)
        new_token_info = response.json()
        session["access_token"] = new_token_info["access_token"]
        session["expires_at"] = datetime.now().timestamp() + new_token_info["expires_in"]
        return redirect("/main")
        
    
#Sorts the user's liked songs by their (spotify given) popularity scores
@app.route("/popularity")
def get_popularity():
    if("access_token" not in session):
        return redirect("/login")
    if(datetime.now().timestamp() > session["expires_at"]):
        return redirect("/refresh-token")
    headers = {
        "Authorization" : f"Bearer {session['access_token']}"
    }
    me =  requests.get(apiBaseURL + "me", headers = headers)
    response = requests.get(apiBaseURL + "me"+ "/tracks", headers = headers)
    favorites = response.json()
    length = favorites["total"]
    offset = 0
    favorites_list = []
    songPopularities = {}
    #assembles the list of the user's liked songs (has to go 50 songs at a time)
    while(length> 0):
        response2 = requests.get(apiBaseURL + "me"+ "/tracks" + "?limit=50&offset=" + str(offset), headers = headers)
        favorites = response2.json()
        for s in favorites["items"]:
            favorites_list.append(s["track"]["id"])
        conglomerateSongs = "?market=US&ids="
        for song in favorites_list[offset:len(favorites_list)-1]:
            conglomerateSongs= conglomerateSongs + (song + ",") 
        if(len(favorites_list[offset:len(favorites_list)-1])!=0):
            conglomerateSongs = conglomerateSongs[:-1]
            response = requests.get(apiBaseURL + "tracks/" + conglomerateSongs, headers = headers)
            tracks = response.json()["tracks"]
            for track in tracks:
                if(track["is_playable"]):
                    songPopularities[track["id"]] = int(track["popularity"])
        offset+= 50
        length-= 50
    global least100
    global most100
    least100 = []
    most100 = []
    for i in range(100):
        minPop = min(songPopularities, key = songPopularities.get)
        maxPop = max(songPopularities, key = songPopularities.get)
        del songPopularities[minPop]
        del songPopularities[maxPop]
        least100.append(minPop)
        most100.append(maxPop)
    return render_template("html/popChoice.html")

#Assembles a list of all the liked songs the user has that aren't present in any other playlist and creates a new playlist with those songs
@app.route("/likedsongs")
def get_likedsongs():
    if("access_token" not in session):
        return redirect("/login")
    if(datetime.now().timestamp() > session["expires_at"]):
        return redirect("/refresh-token")

    #Headers needed for GET request permissions
    headers = {
        "Authorization" : f"Bearer {session['access_token']}"
    }
    headers2 = {
        "Authorization" : f"Bearer {session['access_token']}"
        "Content-Type: application/json"
    }
    me =  requests.get(apiBaseURL + "me", headers = headers)
    user = me.json()
    #Creating the playlist
    myPlaylist = {
            "name": "Stranded Songs",
            "description": "Liked songs with no playlist associated :(",
    }
    newPlaylist = requests.post(apiBaseURL + "me"+ "/playlists", json= myPlaylist, headers= headers)
    worked = newPlaylist.json()
    playlistID = worked["id"]
    #Gets all of the user's playlists
    response = requests.get(apiBaseURL + "me" + "/playlists", headers = headers)
    playlists = response.json()
    response2 = requests.get(apiBaseURL + "me"+ "/tracks", headers = headers)
    favorites = response2.json()
    length = favorites["total"]
    offset = 0
    favorites_list = []
    #need to delete other 'stranded songs' playlists
    
    
    
    #assembles the list of the user's liked songs (has to go 50 songs at a time)
    while(length> 0):
            response2 = requests.get(apiBaseURL + "me"+ "/tracks" + "?limit=50&offset=" + str(offset), headers = headers)
            favorites = response2.json()
            for s in favorites["items"]:
                favorites_list.append(s["track"]["id"])
            offset+= 50
            length-= 50
    pL = []
    counter = 0
    #Accumulates all tracks in all of the user's playlists by id and stores them in one array
    for p in playlists["items"]:
        print("playlist #", counter)
        counter +=1
        id = p["id"]
        playlist_tracks = requests.get(apiBaseURL + "playlists/" + id + "/tracks", headers= headers)
        playlist_response = playlist_tracks.json()
        length = playlist_response["total"]
        offset = 0
        while (length > 0):
            response2 = requests.get(apiBaseURL + "playlists/" + id + "/tracks" + "?limit=50&offset=" + str(offset), headers=headers)
            playlist50Songs = response2.json()
            for s in playlist50Songs["items"]:
                songs_list.append(s["track"]["id"])
            offset += 50
            length -= 50
        songs_list = []
        pL.append(songs_list)
    unaddedSongs = []
    counter = 0
    unaddedCounter = 0
    for song in favorites_list:
        added = isSongUnadded(song, pL)
        if(added):
            unaddedSongs.append(song)
            unaddedCounter+=1
        else:
            counter+=1
    #calculates how many songs the user had out of playlists/in the playlists to display to the user
    counterString = str(counter) + " songs were already in playlists"
    unaddedCounterString = str(unaddedCounter) + " songs werent in playlists"
    print(counter, " songs were already in playlists")
    print(unaddedCounter, " songs werent in playlists")
    x = 0
    for i in range(10):
        uris = {
            "uris" : []
        }
        for i in range(100):
            if(x< len(unaddedSongs)):
                songUri = "spotify:track:" + unaddedSongs[x]
                uris["uris"].append(songUri)
            x+=1
        addingSongs = requests.post(apiBaseURL + "playlists/"+ playlistID + "/tracks", json= uris, headers= headers)
    return "<h3>" + counterString + "</h3>" + "<h3>" + unaddedCounterString + "</h3>" "<a href = '/main'> Head back to main page </a><br><a href = '/main'> Give us some feedback! </a>"

@app.route("/artistGender")
def getGenders():
    if ("access_token" not in session):
        return redirect("/login")
    if (datetime.now().timestamp() > session["expires_at"]):
        return redirect("/refresh-token")

    # Headers needed for GET request permissions
    headers = {
        "Authorization": f"Bearer {session['access_token']}"
    }
    headers2 = {
        "Authorization": f"Bearer {session['access_token']}"
                         "Content-Type: application/json"
    }
    me = requests.get(apiBaseURL + "me", headers=headers)
    response2 = requests.get(apiBaseURL + "me" + "/tracks", headers=headers)
    favorites = response2.json()
    length = favorites["total"]
    offset = 0
    artists = {}

    # assembles the list of the user's liked songs artists
    while (length > 0):
        response2 = requests.get(apiBaseURL + "me" + "/tracks" + "?limit=50&offset=" + str(offset), headers=headers)
        favorites = response2.json()
        for s in favorites["items"]:
            for artist in s["track"]["artists"]:
                if(artist["name"] not in list(artists.keys())):
                    artists[artist["name"]] = 1
                else:
                    artists[artist["name"]] += 1
        offset += 50
        length -= 50
    print(artists)
    artists.pop("")
    artistList = []
    for artist in artists.keys():
        artistList.append(artist + ", ")

    genderList = []
    batchSize = 100
    length = len(artistList)
    while(length > 0):
        print(length)
        query = ""
        if(length >= batchSize):
            for x in range(len(artistList)-length, len(artistList)-length + batchSize):
                query += artistList[x]
            print(query)
            response = clientGPT.responses.create(
                model="gpt-5",
                input="Tell me the gender of the following artists. If the artist is a band, tell the gender of the lead singer. If you don't know, say Unknown. Return your response as a singular string, with M standing for male, F standing for female, and U standing for unknown/nonbinary. Make sure to check that the length of the string is 100, as that is the number of given artists. Here is the list:" + query
            )
            print(response.output_text)
            updatedText = response.output_text
            while (len(updatedText) < 100):
                updatedText += "?"
        else:
            for x in range(len(artistList)-length, len(artistList)):
                query += artistList[x]
            print(query)
            response = clientGPT.responses.create(
                model="gpt-5",
                input="Tell me the gender of the following artists. If the artist is a band, tell the gender of the lead singer. If you don't know, say Unknown. Return your response as a singular string, with M standing for male, F standing for female, and U standing for unknown/nonbinary. Here is the list:" + query
            )
            print(response.output_text)
            updatedText = response.output_text
            while (len(updatedText) < length):
                updatedText += "?"


        print(updatedText)
        for char in updatedText:
            genderList.append(char)
        if (length >= batchSize):
            length-= batchSize
        else:
            length = 0

    print(len(genderList))
    print(len(artists.keys()))
    counter = 0
    genderArtists = {}
    for artist in artists.keys():
        genderArtists[artist] = genderList[counter]
        counter += 1
    print(genderArtists)
    males = 0
    females = 0
    unknown = 0
    for stat in genderArtists.values():
        if(stat == "M"):
            males +=1
        elif(stat == "F"):
            females += 1
        else:
            unknown += 1
    print(males, females, unknown)
    return "<a href = '/main'> Head back to main page </a>"

#feedback webpage which allows users to comment on the webpage, increasing its efficiency and satisfaction
@app.route("/feedback")
def returnFeedback():
    return '''
<head> <title>Likedsongs Booster</title> </head>
<body>
    <form action="http://localhost:5000/main">
        <label for="fname">Feedback is greatly appreciated!</label><br>
        <input type="text" id="fname" name="fname" height="50px" width = "50px"><br>
        <input type="submit" value="Submit">
    </form>
    <a href = '/main'> Head back to main page </a>
</body>
'''
#different routes for the length of playlists created in the popularity feature
@app.route("/10songs", endpoint='get10')
def get10():
    print(least100[:10])
    makePopularityPlaylists(10)
    return redirect("/feedback")

@app.route("/25songs", endpoint='get25')
def get25():
    print(least100[:25])
    makePopularityPlaylists(25)
    return redirect("/feedback")
@app.route("/50songs", endpoint='get50')
def get50():
    print(least100[:50])
    makePopularityPlaylists(50)
    return redirect("/feedback")


#makes the playlists created in the popularity feature
def makePopularityPlaylists(size):
    headers = {
        "Authorization" : f"Bearer {session['access_token']}"
    }
    myPlaylist = {
            "name": "Underground " + str(size),
            "description": str(size) + " most underground songs from your liked songs",
    }
    newPlaylist = requests.post(apiBaseURL + "me"+ "/playlists", json= myPlaylist, headers= headers)
    worked = newPlaylist.json()
    playlistID = worked["id"]
    uris = {
            "uris" : []
        }
    for i in range(size):
            songUri = "spotify:track:" + least100[i]
            uris["uris"].append(songUri)

    addingSongs = requests.post(apiBaseURL + "playlists/"+ playlistID + "/tracks", json= uris, headers= headers)

    myPlaylist = {
            "name":  "Popular " + str(size),
            "description": str(size) + " most popular songs from your liked songs",
    }
    newPlaylist = requests.post(apiBaseURL + "me"+ "/playlists", json= myPlaylist, headers= headers)
    worked = newPlaylist.json()
    playlistID = worked["id"]
    uris = {
            "uris" : []
        }
    for i in range(size):
            songUri = "spotify:track:" + most100[i]
            uris["uris"].append(songUri)

    addingSongs = requests.post(apiBaseURL + "playlists/"+ playlistID + "/tracks", json= uris, headers= headers)
        
#checks if a song is already in a playlist
def isSongUnadded(unaddedSong, playlists):
   for playlist in playlists:
       for song in playlist:
           if(song == unaddedSong):
               return False
   return True
                
#starts webapp

if(__name__ == "__main__"):
    app.run(host="0.0.0.0", port=8888, debug=True)
