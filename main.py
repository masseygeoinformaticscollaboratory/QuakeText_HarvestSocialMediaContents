import csv
import json
import re
import sys
import time

import requests
from datetime import datetime, timedelta, timezone
import pandas as pd

# Global parameters
# 1. Bounding box four coordinates
left = 174.6914167178354
bottom = -36.736880739350006
right = 174.71808570523245
top = -36.720242548667635

# 2. Number of Posts
# If not specified, use the default 100 posts
numOfPosts = 100

# 3. Information Sources
# If not specified, use the following settings
hasYouTube = False
hasReddit = True
hasTwitter = False

# 4. Time range
timeRangeStart: 1
timeRangeEnd: 2

# 5. Place names
search = []
GoogleSearch = []

# 6. Twitter API token
bearer_token = "AAAAAAAAAAAAAAAAAAAAADWspQEAAAAAaKUwhL7Z5j%2BWyS1MIZMjnSodkqU%3D9h2nV8ASy0HT1MSNgK6jPxH9siloVeLfzUACMGIeePDOOLYlim"

# 7. Global time range
Start_time = datetime.now()
End_time = datetime.now()

# Read the searching parameters from file "temp_parameters.txt"
# This file will be generated on the server when user click the search button
def readSearchParameters():
    global left, bottom, right, top, numOfPosts, hasTwitter, hasReddit, hasYouTube, timeRangeStart, timeRangeEnd
    with open('temp_parameters.txt', 'r') as file:
        json_strings = file.read()
        print(json_strings)
        data = json.loads(json_strings)
        left = data.get('left')
        bottom = data.get('bottom')
        right = data.get('right')
        top = data.get('top')
        numOfPosts = data.get('numOfPosts')
        hasTwitter = data.get('Twitter')
        hasYouTube = data.get('YouTube')
        hasReddit = data.get('Reddit')
        timeRangeStart = data.get('timeRangeStart')
        timeRangeEnd = data.get('timeRangeEnd')


# Get place names within the bounding box
def getPlaceNames():
    # Firstly, Read the NZ geo-information text file
    # The main 'geoname' table has the following fields :
    # ---------------------------------------------------
    # geonameid         : integer id of record in geonames database
    # name              : name of geographical point (utf8) varchar(200)
    # asciiname         : name of geographical point in plain ascii characters, varchar(200)
    # alternatenames    : alternatenames, comma separated, ascii names automatically transliterated, convenience attribute from alternatename table, varchar(10000)
    # latitude          : latitude in decimal degrees (wgs84)
    # longitude         : longitude in decimal degrees (wgs84)
    # feature class     : see http://www.geonames.org/export/codes.html, char(1)
    # feature code      : see http://www.geonames.org/export/codes.html, varchar(10)
    # country code      : ISO-3166 2-letter country code, 2 characters
    # cc2               : alternate country codes, comma separated, ISO-3166 2-letter country code, 200 characters
    # admin1 code       : fipscode (subject to change to iso code), see exceptions below, see file admin1Codes.txt for display names of this code; varchar(20)
    # admin2 code       : code for the second administrative division, a county in the US, see file admin2Codes.txt; varchar(80)
    # admin3 code       : code for third level administrative division, varchar(20)
    # admin4 code       : code for fourth level administrative division, varchar(20)
    # population        : bigint (8 byte int)
    # elevation         : in meters, integer
    # dem               : digital elevation model, srtm3 or gtopo30, average elevation of 3''x3'' (ca 90mx90m) or 30''x30'' (ca 900mx900m) area in meters, integer. srtm processed by cgiar/ciat.
    # timezone          : the iana timezone id (see file timeZone.txt) varchar(40)
    # modification date : date of last modification in yyyy-MM-dd format

    column_names = ['geonameid', 'name', 'asciiname', 'alternatenames', 'latitude', 'longitude', 'feature class',
                    'feature code', 'country code', 'cc2', 'admin1 code', 'admin2 code', 'admin3 code', 'admin4 code',
                    'population', 'elevation', 'dem', 'timezone', 'modification date']
    df = pd.read_csv("./res/GeoNamesNZ/NZ.txt", sep='\t', header=None, names=column_names)
    pd.set_option('display.max_columns', None)
    pd.set_option('display.max_rows', None)
    ## Secondly, deal with the bounding box area
    ## 1. If right border's longitude cross the 180 degree longitude
    ## For the left part, the upper right corner coordinate is [180, latitude]
    if (left > 0) & (right < 0):
        ## Left box area
        left1 = left
        top1 = top
        right1 = 180.0
        bottom1 = bottom
        filtered_df1 = df[(df['longitude'] >= left1) & (df['longitude'] <= right1) & (df['latitude'] <= top1) & (df['latitude'] >= bottom1)]
        print(filtered_df1['name'])

        ## For the left part
        left2 = -180.0
        top2 = top
        right2 = right
        bottom2 = bottom
        filtered_df2 = df[(df['longitude'] >= left2) & (df['longitude'] <= right2) & (df['latitude'] <= top2) & (df['latitude'] >= bottom2)]
        print(filtered_df2['name'])
        filtered_df = pd.concat([filtered_df1, filtered_df2], ignore_index=True)
    else:
        ## 2. If right border's longitude doesn't cross the 180 degree longitude
        ## don't need to split
        filtered_df = df[(df['longitude'] >= left) & (df['longitude'] <= right) & (df['latitude'] <= top) & (df['latitude'] >= bottom)]
        filtered_df.reset_index(drop=True, inplace=True)


    ## Each search statement is no longer than 330 characters as these two search APIs have a 512 characters length limitation (For Twiiter and Reddit)
    cha_len = 0
    current_search_place_names = ""
    for i in range(len(filtered_df)):
        current_length = 4 + len(filtered_df['name'][i])   # 4 characters stand for " OR" length
        cha_len += current_length
        if cha_len > 330:
            search.append(current_search_place_names[:-4])
            current_search_place_names = filtered_df['name'][i] + " OR "
            cha_len = current_length
        else:
            current_search_place_names += filtered_df['name'][i] + " OR "
            cha_len += current_length
    search.append(current_search_place_names[:-4])

    ## Each search statement is no longer than 32 words as the Google search API has a 32 words length limitation (For YouTube search)
    ## Everytime performing the search, impacts words already has 6 words, so place names can only have 26 words each time
    word_count = 0
    current_search_place_words = "("
    for i in range(len(filtered_df)):
        space_count = filtered_df['name'][i].count(' ')
        word_count += 1 + space_count
        if word_count > 26:
            GoogleSearch.append(current_search_place_words + ')')
            current_search_place_words = '((' + filtered_df['name'][i] + ')'
            word_count = 1 + filtered_df['name'][i].count(' ')
        else:
            current_search_place_words += '(' + filtered_df['name'][i] + ') OR '
            word_count += 1 + filtered_df['name'][i].count(' ')
    GoogleSearch.append(current_search_place_names + ')')

    print(filtered_df['name'])
    print(datetime.now().strftime("%H:%M:%S") , "Geo-place names fetched successfully.")


def bearer_oauth(r):
    r.headers["Authorization"] = f"Bearer {bearer_token}"
    r.headers["User-Agent"] = "v2RecentSearchPython"
    return r


# Fetch Tweets from Twitter
def fetchTwitter():
    global Start_time, End_time
    try:
        # Get current date and time
        currentDateAndTime = datetime.now()
        year = currentDateAndTime.year
        month = currentDateAndTime.month
        day = currentDateAndTime.day
        hour = currentDateAndTime.hour
        minute = currentDateAndTime.minute
        second = currentDateAndTime.second

        ## Solve the time difference problem with UTC+0, summer time and winter time considered
        current_timezone = datetime.now().astimezone().tzinfo
        # Get UTC offset in hours
        utc_offset = current_timezone.utcoffset(datetime.now()).total_seconds() / 3600

        # Compute the start time in UTC
        # New Zealand is ahead of Coordinated Universal Time, so we need to minus the offset hours.
        # Use Twitter default end time and minus the offset time (return Tweets from as recent as 30 seconds ago)
        today_zero = currentDateAndTime.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(seconds=30)
        if int(timeRangeStart) == 0:
            start_time = today_zero - timedelta(hours=utc_offset)
        elif int(timeRangeStart) == 1:
            start_time = today_zero - timedelta(days=1) - timedelta(hours=utc_offset)
        elif int(timeRangeStart) == 2:
            start_time = today_zero - timedelta(days=2) - timedelta(hours=utc_offset)
        elif int(timeRangeStart) == 3:
            start_time = today_zero - timedelta(days=3) - timedelta(hours=utc_offset)
        elif int(timeRangeStart) == 4:
            start_time = today_zero - timedelta(days=4) - timedelta(hours=utc_offset)
        elif int(timeRangeStart) == 5:
            start_time = today_zero - timedelta(days=5) - timedelta(hours=utc_offset)
        elif int(timeRangeStart) == 6:
            start_time = today_zero - timedelta(days=6) - timedelta(hours=utc_offset)
        else: raise Exception("error", "Invalid start time!")

        # Specify the end time in UTC
        # Due to the Twitter basic account API limits, we can only search for the Tweets within the past week.
        currentDateAndTime.replace(microsecond=0)
        currentDateAndTime -= timedelta(seconds=30)
        if int(timeRangeEnd) == 0:
            end_time = currentDateAndTime - timedelta(hours=utc_offset)
        elif int(timeRangeEnd) == 1:
            end_time = currentDateAndTime - timedelta(days=1) - timedelta(hours=utc_offset)
        elif int(timeRangeEnd) == 2:
            end_time = currentDateAndTime - timedelta(days=2) - timedelta(hours=utc_offset)
        elif int(timeRangeEnd) == 3:
            end_time = currentDateAndTime - timedelta(days=3) - timedelta(hours=utc_offset)
        elif int(timeRangeEnd) == 4:
            end_time = currentDateAndTime - timedelta(days=4) - timedelta(hours=utc_offset)
        elif int(timeRangeEnd) == 5:
            end_time = currentDateAndTime - timedelta(days=5) - timedelta(hours=utc_offset)
        elif int(timeRangeEnd) == 6:
            end_time = currentDateAndTime - timedelta(days=6) - timedelta(hours=utc_offset)
        else: raise Exception("error", "Invalid end time!")

        # Convert time format to meet with Twitter API time format
        Start_time = start_time
        End_time = end_time
        start_time = start_time.strftime('%Y-%m-%dT%H:%M:%S.000Z')
        end_time = end_time.strftime('%Y-%m-%dT%H:%M:%S.000Z')

        finalresult = []
        for i in range(10):
            queries = ['death OR (lost life) OR (lost lives) OR dead OR (lost their lives) OR killed OR (toll rises) OR casualties OR (bodies recovered)',    # Death
                      'missing OR injured OR trapped OR survived OR loss OR (under rescue) OR (waiting for rescue) OR homeless OR separated OR panic OR panicked OR evacuated',    # People's status
                      'destroyed OR destruction OR destroy OR damage OR damaged OR lost OR broken OR intact OR (good condition) OR collapse OR affected OR displaced OR impacted ',   # items status
                      'medication OR illness OR (preserving devices) OR powercuts OR well-being OR health OR power-cut OR wellbeing OR powercut',   # Health status
                      'park OR office OR offices OR mall OR malls OR restaurant OR restaurants OR students OR school OR university OR college OR academy OR building',   # public buildings (facilities)
                      'signal OR internet OR connection OR coverage OR (internet access) OR (no service) OR (cell tower) OR 4G OR 3G OR 2G',    # Mobile Network
                      'airport OR flights OR flight OR railway OR train OR bus OR ferry OR traffic OR buses OR trains OR airline OR terminal',  # public transport tools
                      'road OR street OR highway OR motorway OR bridges OR avenue OR lane OR freeway OR expressway OR Overpass OR underpass OR ramp OR ferry',   # public transport
                      'house OR home OR apartment OR duplex OR Condominium OR Townhouse OR Villa OR cottage OR cabin',  # Places people live in
                      'village OR suburb OR town OR city OR river OR mount OR mountain OR rivers OR mountains OR hamlet OR downtown OR area OR waterfront OR coastline OR bay OR valley OR metropolis',   # Places
                      '(Fes OR Marrakesh OR Rabat OR Casablanca OR Tangier OR Essaouira OR Meknes OR Tetouan OR Chefchaouen OR Agadir OR Ouarzazate OR (El Jadida) OR Larache OR Kenitra OR Oujda)',  # Only for morocco big cities
                      '(Salé OR (Al Hoceima) OR Safi OR Taza OR Taroudant OR Ksar el-Kebir OR Nador OR Settat OR Guelmim OR Azrou OR Beni-Mellal OR Midelt OR Taourirt OR Errachidia OR Guercif)'  # Only for morocco smaller cities
                      ]

            for count in range(len(search)):
                # Here we specify our query
                query = '(' + str(search[count]) + ' (' + queries[i] + ') )' + " lang:en" + " -is:retweet"

                # The search_recent method call the recent search endpoint to get Tweets based on the query, start and end times
                search_url = "https://api.twitter.com/2/tweets/search/recent"

                params = {'query': query, 'start_time': start_time, 'end_time': end_time, 'max_results': numOfPosts,
                          "tweet.fields": "created_at,author_id,context_annotations,entities",
                          "expansions": "author_id,geo.place_id"}
                # Perform a query
                search_results = requests.get(search_url, auth=bearer_oauth, params=params)
                print(datetime.now().strftime("%H:%M:%S"), "Twitter API: ", search_results)

                # Sometimes a certain search query cannot fetch any tweet, then the response will not have the'data' property
                # In this situation, we need to judge
                if 'data' in search_results:
                    finalresult.extend(search_results['data'])

        file_name = "./outputs/TwitterResults.json"
        with open(file_name, 'w') as filehandle:
            # Here we are writing the recent Tweet object JSON to the file
            json.dump(finalresult, filehandle,ensure_ascii=False, indent=4)

        print(datetime.now().strftime("%H:%M:%S"), "Tweets fetched successfully.")

    except Exception as e:
        print(datetime.now().strftime("%H:%M:%S"), "ERROR: An error occurred during Tweets fetching:")
        print(e)

def fetchReddit():
    posts = []
    # Search for ten times, each time uses one of the 10 groups of impact words
    for i in range(10):
        queries = [
            'death OR (lost life) OR (lost lives) OR dead OR (lost their lives) OR killed OR (toll rises) OR casualties OR (bodies recovered)',
            # Death
            'missing OR injured OR trapped OR survived OR loss OR (under rescue) OR (waiting for rescue) OR homeless OR separated OR panic OR panicked OR evacuated',
            # People's status
            'destroyed OR destruction OR destroy OR damage OR damaged OR lost OR broken OR intact OR (good condition) OR collapse OR affected OR displaced OR impacted ',
            # items status
            'medication OR illness OR (preserving devices) OR powercuts OR well-being OR health OR power-cut OR wellbeing OR powercut',
            # Health status
            'park OR office OR offices OR mall OR malls OR restaurant OR restaurants OR students OR school OR university OR college OR academy OR building',
            # public buildings (facilities)
            'signal OR internet OR connection OR coverage OR (internet access) OR (no service) OR (cell tower) OR 4G OR 3G OR 2G',
            # Mobile Network
            'airport OR flights OR flight OR railway OR train OR bus OR ferry OR traffic OR buses OR trains OR airline OR terminal',
            # public transport tools
            'road OR street OR highway OR motorway OR bridges OR avenue OR lane OR freeway OR expressway OR Overpass OR underpass OR ramp OR ferry',
            # public transport
            'house OR home OR apartment OR duplex OR Condominium OR Townhouse OR Villa OR cottage OR cabin',
            # Places people live in
            'village OR suburb OR town OR city OR river OR mount OR mountain OR rivers OR mountains OR hamlet OR downtown OR area OR waterfront OR coastline OR bay OR valley OR metropolis',
            # Places
            '(Fes OR Marrakesh OR Rabat OR Casablanca OR Tangier OR Essaouira OR Meknes OR Tetouan OR Chefchaouen OR Agadir OR Ouarzazate OR (El Jadida) OR Larache OR Kenitra OR Oujda)',
            # Only for morocco big cities
            '(Salé OR (Al Hoceima) OR Safi OR Taza OR Taroudant OR Ksar el-Kebir OR Nador OR Settat OR Guelmim OR Azrou OR Beni-Mellal OR Midelt OR Taourirt OR Errachidia OR Guercif)'
            # Only for morocco smaller cities
            ]

        for count in range(len(search)):
            ## Perform request
            url = 'https://www.reddit.com/search.json?q=' + "(" + str(search[count]) + " AND (" + queries[i] + "))" + '&limit=' + (str(numOfPosts)) + "&sort=new"
            while True:
                r = requests.get(url, headers={'User-agent': 'Location Mapper For Reddit'})

                if r.status_code == 200:
                    break
                else:
                    print("Reddit search cap reached! Sleep for 50 seconds.")
                    time.sleep(50)

            print(r)
            parsedjson = r.json()
            postList = parsedjson['data']['children']

            for item in postList:
                start_time_timestamp = Start_time.timestamp()
                end_time_timestamp = End_time.timestamp()
                # If the posts are within the date range
                if (item['data']['created_utc'] >= start_time_timestamp) & (item['data']['created_utc'] <= end_time_timestamp):
                    post_data = {
                        'title': item['data']['title'],
                        'content': item['data']['selftext'],
                        'time_UTC': item['data']['created_utc'],
                        'author_name': item['data']['author'],
                        'post_id': item['data']['id']
                    }
                    posts.append(post_data)

    with open('./outputs/RedditOutput.json', 'w', encoding='utf-8') as json_file:
        json.dump(posts, json_file, ensure_ascii=False, indent=4)
    print(datetime.now().strftime("%H:%M:%S"), "Reddit posts fetched successfully.")

## Funtions for fetching YouTube
# Function to convert relative time to a formatted date
def convert_relative_time(relative_time):
    base_date = datetime.now()
    if "hour" in relative_time:
        hours_ago = int(re.search(r'\d+', relative_time).group())
        return (base_date - timedelta(hours=hours_ago)).strftime("%b %d, %Y")
    elif "day" in relative_time:
        days_ago = int(re.search(r'\d+', relative_time).group())
        return (base_date - timedelta(days=days_ago)).strftime("%b %d, %Y")
    else:
        return "unknown"


# Function to extract the date from the snippet considering only the content before the first "..."
def extract_date_from_snippet(snippet):
    # Find the first "..."
    first_ellipsis_index = snippet.find("...")

    if first_ellipsis_index != -1:
        snippet_before_ellipsis = snippet[:first_ellipsis_index]

        # Using regular expressions to match date information
        date_pattern = r"(\w+ (?:\d+, )?\d+)"  # Match date in "Sep 24, 2023" or "Sep 2023" format
        matches = re.search(date_pattern, snippet_before_ellipsis)

        if matches:
            date_info = matches.group(1)
        else:
            # Extract the relative time information, e.g., "5 days ago"
            relative_time_pattern = r"(\d+ (?:hour|day)s? ago)"
            relative_time_match = re.search(relative_time_pattern, snippet_before_ellipsis)
            if relative_time_match:
                relative_time = relative_time_match.group(1)
                date_info = convert_relative_time(relative_time)
            else:
                date_info = "unknown"
    else:
        date_info = "unknown"

    return date_info


def fetchYouTube():
    # API KEY
    api_key = "AIzaSyCwGU3gsJ3MENNMqDSbAdYPKcB9aH_xTkE"

    # Custom Search Engine ID
    cse_id = "048efae04f0fb446d"

    # Initialize a base date, e.g., today's date
    base_date = datetime.now()

    # Here, "disaster" stands for place names
    disaster = GoogleSearch

    # Keywords to search for
    # old_keywords = ["death", "dead", "(lost life)", "(lost lives)",   # six words
    #             "killed", "(toll rises)", "casualties", "(bodies recovered)",   # six words
    #             "missing", "injured", "trapped", "survived", "loss", "rescue",   # six words
    #             "homeless", "separated", "panic", "panicked", "evacuated", "destroy",   # six words
    #             "destruction", "destroyed", "damage", "lost", "broken", "intact",  # six words
    #             "(good condition)", "collapse", "affected", "displaced", "impacted"]   # six words

    # Below they are all six words per group
    keywords = ["(death OR dead OR (lost life) OR (lost lives))",
                "(killed OR (toll rises) OR casualties OR (bodies recovered))",
                "(missing OR injured OR trapped OR survived OR loss OR rescue)",
                "(homeless OR separated OR panic OR panicked OR evacuated OR destory)",
                "(destruction OR destroyed OR damage OR lost OR broken OR intact)",
                "((good condition) OR collapse OR affected OR displaced OR impacted)"]

    # Setting Time Range Filtering, requests results from the specified number of past month, here is 1
    time_range = "m1"

    # Setting Sorting Parameters
    # sort_params = ["date:r:20231006:20231011","date:r:20231012:20231020"]
    startdate = Start_time.strftime("%Y%m%d")
    enddate = End_time.strftime("%Y%m%d")
    sort_params = [f"date:r:{startdate}:{enddate}"]
    # Restricted results site
    site_restrict = "youtube.com"

    # Set the number of results per page (up to 10)
    results_per_page = 10

    # Total number of results to get per combination of keyword and time range
    total_results = int(numOfPosts)

    # Open or create a TSV file for writing data
    with open("./outputs/YouTubeOutputs.tsv", mode="a", newline="", encoding="utf-8") as tsv_file:
        fieldnames = ["title", "link", "snippet", "date"]
        writer = csv.DictWriter(tsv_file, fieldnames=fieldnames, delimiter="\t")

        # If the file is empty, write the table header
        if tsv_file.tell() == 0:
            writer.writeheader()

        # Iterate through keywords and time ranges
        for keyword in keywords:
            for sort_param in sort_params:
                # Initialize the start index
                start_index = 1

                # Output the search keyword and time range
                #print(f"Searching for: {keyword}.   time range: {sort_param}")

                # Initialize the row count
                row_count = 0

                for place_name in GoogleSearch:
                    # Initiate multiple API requests to get more results
                    while start_index <= total_results:
                        # Break out of the loop if row_count reaches 10

                        # Building API Requests
                        query = f"{place_name} {keyword}"
                        print(f"Searching for: {query}.   time range: {sort_param}")
                        url = f"https://www.googleapis.com/customsearch/v1?q={query}&key={api_key}&cx={cse_id}&start={start_index}&dateRestrict={time_range}&sort={sort_param}&siteSearch={site_restrict}&siteSearchFilter=i"
                        # Initiating API Requests
                        response = requests.get(url)

                        # Check if the request was successful
                        if response.status_code == 200:
                            search_results = response.json()
                            if 'items' in search_results and search_results['items']:
                                # Search results are not empty, process search results
                                each_count = 0
                                for item in search_results['items']:
                                    title = item['title']
                                    link = item['link']
                                    snippet = item['snippet']

                                    date_info = extract_date_from_snippet(snippet)

                                    # Write TSV file
                                    writer.writerow(
                                        {"title": title, "link": link, "snippet": snippet, "date": date_info})
                                    row_count += 1
                                    each_count += 1
                                # Break out of the loop if row_count reaches 10
                                if each_count < 10:
                                    print("     ", each_count)
                                    print("     No more results")
                                    break
                                else:
                                    print("     ", each_count)

                            else:
                                # No search results
                                print("     No search results")
                                break
                        else:
                            print(datetime.now().strftime("%H:%M:%S"), "Code:", response.status_code, " API request failed")
                            print(datetime.now().strftime("%H:%M:%S"), "start_index:", start_index)
                            ## sys.exit()

                        # Update the start index to get the next page of results
                        start_index += results_per_page


                # Print the number of rows written for this keyword and time range
                print(datetime.now().strftime("%H:%M:%S"), f"     Results written for {keyword}:   {row_count}")

    print(datetime.now().strftime("%H:%M:%S"), "YouTube captions fetched successfully.")

if __name__ == "__main__":
    print(datetime.now().strftime("%H:%M:%S"), "The program started fetching.")

    readSearchParameters()
    getPlaceNames()
    if hasTwitter:
        fetchTwitter()
    else:
        print(datetime.now().strftime("%H:%M:%S"), "Twitter is not selected. Skipping")

    if hasReddit:
        fetchReddit()
    else:
        print(datetime.now().strftime("%H:%M:%S"), "Reddit is not selected. Skipping")

    if hasYouTube:
        fetchYouTube()
    else:
        print(datetime.now().strftime("%H:%M:%S"), "YouTube is not selected. Skipping")

    print(datetime.now().strftime("%H:%M:%S"), "The program has completed fetching.")

    # When in production mode, add this line
    # Now for debug and demonstration reason, the window will not close immediately after executaion

    sys.exit()