import csv
import time
import sys

from SPARQLWrapper import SPARQLWrapper
from apiclient import discovery
from apiclient.errors import HttpError

from lmdb_wrapper import LMDBWrapper
from utils import Config, Portal, SPARQLEndpoints, LMDBMovieConcept, \
    FreebaseMovieConcept
from freebase_wrapper import FreebaseWrapper



def get_and_persist_lmdb_actors(f):
    """
    This function queries LMDB for all actors which have a foaf:page link to free-
    base and stores the result in f.
    """
    result = []
    try:
        
        print "getting actor count from freebase"                  
        actorCount = lmdb.get_page_count(Portal.FREEBASE, LMDBMovieConcept.ACTOR)
        
        print "loading %i actors from lmdb" % actorCount
        with open(f, 'w') as fOut:
            csvwriter = csv.DictWriter(fOut, ['actorid', 'name', 'freebase_guid'], delimiter=';')
            csvwriter.writeheader() 
            for i in range(0, actorCount, Config.LMDB_PAGE_SIZE):
                loaded = False
                delay = 1
                print 'getting actors from %i to %i' % (i, (i + Config.LMDB_PAGE_SIZE))
                while not loaded:
                    time.sleep(delay)
                    try:
                        actors = lmdb.get_actors(Portal.FREEBASE,
                                                 i,  # offset 
                                                 Config.LMDB_PAGE_SIZE)  # limit
                    except IOError as _:
                        delay *= 2
                        print "a connection error occured, setting retry-delay to %i (%s)" % (delay, _.args)
                    else:
                        loaded = True
                csvwriter.writerows(actors)
                result += actors
                fOut.flush()
    except IOError as ioError:
        print str(ioError)
    else:
        return result
    
def get_and_persist_lmdb_films(f):
    """
    This function queries LMDB for all films which have a foaf:page link to freebase
    and stores the results f.
    """
    result = []
    try:
        print "getting film count from freebase"
        filmCount = lmdb.get_page_count(Portal.FREEBASE, LMDBMovieConcept.FILM)
        print "loading %i films from lmdb" % filmCount
                
        with open(f, 'w') as fOut:
            csvwriter = csv.DictWriter(fOut,
                                       ['filmid', 'name', 'date', 'freebase_guid'],
                                       delimiter=';')
            csvwriter.writeheader()
            for i in range(0, filmCount, Config.LMDB_PAGE_SIZE):
                loaded = False
                delay = 1
                print 'getting films from %i to %i \r' % (i, (i + Config.LMDB_PAGE_SIZE))
                while not loaded:
                    time.sleep(delay)
                    try:
                        films = lmdb.get_films(Portal.FREEBASE,
                                               i,  # offset 
                                               Config.LMDB_PAGE_SIZE)                        
                    except IOError as _:
                        delay *= 2
                        print "a connection error occured, setting retry-delay to %i (%s)" % (delay, _.args)
                    else:
                        loaded = True
                csvwriter.writerows(films)
                result += films
                fOut.flush()
    except IOError as ioError:
        print str(ioError)
    else:
        return result

def get_and_persist_lmdb_actors_by_film(fin, fout):
    """
    This function takes a list of films (each film is a dictionary) and queries
    LMDB to get all actors for each film. The complete film information is then
    stored in fout.
    """
    result = []
    try:
        print "loading films from file"
        films = []
        with open(fin, 'r') as fIn:
            csvreader = csv.DictReader(fIn, delimiter=';')
            for film in csvreader:
                films.append(film)

        print "getting actors for film"
        with open(fout, 'w') as fOut:
            csvwriter = csv.DictWriter(fOut,
                                       ['filmid', 'name', 'actors', 'date', 'freebase_guid'],
                                       delimiter=';')
            csvwriter.writeheader()
            n = len(films)
            i = 0            
            for film in films:
                if i % Config.LMDB_PAGE_SIZE == 0:
                    print "processed %i of %i films" % (i, n) 
                loaded = False
                delay = 1
                while not loaded:
                    time.sleep(delay)
                    try:
                        film['actors'] = ",".join(lmdb.get_actors_by_film(Portal.FREEBASE,
                                                                          int(film['filmid'])))
                    except IOError as _:
                        delay *= 2  # increase sleep delay in case of connection error
                        print "a connection error occured, setting retry-delay to %i (%s)" % (delay, _.args)
                    else:
                        loaded = True
                    if loaded:
                        csvwriter.writerow(film)
                i+=1
            result += films
    except IOError as ioError:
        print str(ioError)
    else:
        return result
        
def get_and_persist_freebase_films(f):
    """
    This function queries freebase for all films which have a imdb_id set. The
    films are persisted in the given file.
    """
    print "loading films from freebase"
    result = []
    try:
        #film_count = freebase.get_count(Portal.IMDB, FreebaseMovieConcept.FILM)
        film_count = 199174
        print "getting %i films from freebase" % film_count
        with open(f, 'w') as fout:
            portal_key = freebase.get_portal_key(Portal.IMDB)
            dictwriter = csv.DictWriter(fout,
                                        ['id',
                                         'guid',
                                         'name',
                                         'initial_release_date',
                                         'directed_by',
                                         'written_by',
                                         'produced_by',
                                         'genre',
                                         'actors',
                                         'description',
                                         portal_key],
                                         delimiter=';',
                                         extrasaction='ignore')
            dictwriter.writeheader()
            
            i = 0 # no of films read
            cursor = "" # needed for paging
            while i < film_count:
                loaded = False
                delay = 1
                while not loaded:
                    time.sleep(delay)
                    t0 = time.time()
                    try:
                        print "getting films %i to %i" % (i, i + Config.FREEBASE_PAGE_SIZE)
                        response = freebase.get_films(Portal.IMDB,
                                                      Config.FREEBASE_PAGE_SIZE,
                                                      cursor)
                        print "got films, getting descriptions from text api"
                        for film in response[0]:
                            film['directed_by'] = ",".join([_['name'] for _ in film['directed_by']])
                            film['written_by'] = ",".join([_['name'] for _ in film['written_by']])
                            film['produced_by'] = ",".join([_['name'] for _ in film['produced_by']])
                            film['genre'] = ",".join([_['name'] for _ in film['genre']])
                            film['actors'] = ",".join([_['actor']['guid'] for _ in film['starring']])
                            film['description'] = freebase.get_film_description(film['id'])
                            film[portal_key] = ",".join(film[portal_key])
                    except (IOError, HttpError) as _:
                        delay *= 2  # increase sleep delay in case of connection error
                        print "a connection error occured, setting retry-delay to %i\n(%s)" % (delay, str(_))
                    else:
                        loaded = True
                        dictwriter.writerows(response[0])
                        cursor = response[1]
                        i += Config.FREEBASE_PAGE_SIZE
                        result += response[0]
                        fout.flush()
                        print "took %.2f seconds" % (time.time() - t0)
                        
    except IOError as ioError:
        print str(ioError)
    else:
        return result

def get_and_persist_freebase_actors_by_lmdb_actors(lmdb_actors_file, fout):
    i = 0
    result = []
    try:
        with open(lmdb_actors_file, 'r') as fin:
            with open(fout, 'w') as fOut:
                dictreader = csv.DictReader(fin,
                                            delimiter=';')
                dictwriter = csv.DictWriter(fOut,
                                            ['guid', 'name', 'lmdb'],
                                            delimiter=';')
                dictwriter.writeheader()
                
                for actor in dictreader:
                    i += 1
                    freebase_actor = freebase.get_actor_by_guid(actor['freebase_guid'])
                    if freebase_actor is not None:
                        freebase_actor['lmdb'] = actor['actorid']  
                        dictwriter.writerow(freebase_actor)
                    result += freebase_actor
                    if i % Config.LMDB_PAGE_SIZE == 0:
                        sys.stdout.write("Actors queried: %i   \r" % (i))
                        fOut.flush()
    except IOError as ioError:
        print str(ioError)
    else:
        return result
        
def get_and_persist_freebase_films_by_lmdb_films(lmdb_films_file, fout):
    result = []
    i = 0
    try:
        with open(lmdb_films_file, 'r') as fin:
            with open(fout, 'w') as fOut:
                dictreader = csv.DictReader(fin, delimiter=';')
                dictwriter = csv.DictWriter(fOut,
                                            ['guid', 
                                             'name', 
                                             'starring', 
                                             'initial_release_date', 
                                             'lmdb'],
                                            delimiter=';',
                                            extrasaction='ignore')
                dictwriter.writeheader()
                for film in dictreader:
                    i += 1
                    freebase_film = freebase.get_film_by_guid(film['freebase_guid'])
                    if freebase_film is not None:
                        freebase_film['lmdb'] = film['filmid']
                        dictwriter.writerow(freebase_film)
                    result += freebase_film
                    if i % Config.LMDB_PAGE_SIZE == 0:
                        sys.stdout.write("Films queried: %i   \r" % (i))
                        fOut.flush()
    except IOError as ioError:
        print str(ioError)
    else:
        return result

def create_mappings(source_file, map_file, key_map):
    try:
        with open(source_file, 'r') as sourcef:
            with open(map_file, 'w') as mapf:
                dictreader = csv.DictReader(sourcef,
                                            delimiter=';'                                        
                                            )
                dictwriter = csv.DictWriter(mapf,
                                            key_map.values(),
                                            delimiter=';')
                dictwriter.writeheader()
                for row in dictreader:
                    map_row = {}
                    for key in key_map:
                        if key_map[key] is not None:
                            map_row[key_map[key]] = row[key] 
                    print map_row
                    dictwriter.writerow(map_row)
                map.flush()
    except IOError as ioError:
        print str(ioError)
            
# hit and run
if __name__ == "__main__":
    
    if len(sys.argv) <= 1:
        print "usage: program.py <google_api_key>"
        sys.exit(1)
    else:
        Config.GOOGLE_API_KEY = sys.argv[1]
        
        # connect to LMDB
        sparql_lmdb = SPARQLWrapper(SPARQLEndpoints.LMDB)
        lmdb = LMDBWrapper(sparql_lmdb)
    
        # connect to freebase
        freebase_endpoint = discovery.build('freebase',
                                            'v1',
                                            developerKey=Config.GOOGLE_API_KEY)
        freebase = FreebaseWrapper(freebase_endpoint)
        
        # process
        # lmdb <-> freebase stuff
#        get_and_persist_lmdb_actors(Config.LMDB_ACTORS_FILE)
#        get_and_persist_lmdb_films(Config.LMDB_FILMS_TMPFILE)
#        get_and_persist_lmdb_actors_by_film(Config.LMDB_FILMS_TMPFILE,
#                                            Config.LMDB_FILMS_FILE)
#        get_and_persist_freebase_actors_by_lmdb_actors(Config.LMDB_ACTORS_FILE,
#                                                       Config.FREEBASE_ACTORS_FILE)
#        get_and_persist_freebase_films_by_lmdb_films(Config.LMDB_FILMS_FILE,
#                                                     Config.FREEBASE_FILMS_FILE)
#        create_mappings(Config.LMDB_ACTORS_FILE,
#                        Config.ACTOR_MAPPING_FILE,
#                        {'actorid' : 'lmdb_id', 'freebase_guid' : 'freebase_guid'})
#        create_mappings(Config.LMDB_FILMS_FILE,
#                        Config.FILM_MAPPING_FILE,
#                        {'filmid' : 'lmdb_id', 'freebase_guid' : 'freebase_guid'})
        
        # lmdb <-> imdb stuff
        get_and_persist_freebase_films(Config.FREEBASE_IMDB_FILMS_FILE)
        sys.exit(0)
