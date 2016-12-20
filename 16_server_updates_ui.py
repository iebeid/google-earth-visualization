import simplekml
import json, sys, os
from math import fabs
import cherrypy
cherrypy.config.update({'server.socket_port': 20605})
cherrypy.engine.restart()

# Simple helper function to update bounding box around list of coordinates
def update_box(box, coords):
    lomin = box.west
    lomax = box.east
    lamin = box.south
    lamax = box.north
    
    for c in coords:
        f = float(c[0])
        if f < lomin:
            lomin = f
        if f > lomax:
            lomax = f
        f = float(c[1])
        if f < lamin:
            lamin = f
        if f > lamax:
            lamax = f

    box.west = lomin
    box.east = lomax
    box.south = lamin
    box.north = lamax
    
    return box

# Calculate the color for a male/female pair
def calcColor(nmales, nfemales):
    npeople = nmales + nfemales
    dif = nmales - nfemales
    
    fac = max(-1., min(dif * 10. / npeople, 1.))
    
    col = "a0%02x00%02x" % ((128 + 127 * fac), (128 - 127 * fac))
    
    return col
    

# Define style

style = simplekml.Style()
style.linestyle.gxphysicalwidth = 30
style.linestyle.color = "ff00ff00"
style.polystyle.color = "800000ff"
    

# Load visualization data
jdata_county = json.load(open("county_male_female.json","r"))
jdata_state = json.load(open("state_male_female.json","r"))

# Dict to map variable name to index
indexmap_county = {}
for d in range(0, len(jdata_county[0])):
    indexmap_county[jdata_county[0][d]] = d
    
indexmap_state = {}
for d in range(0, len(jdata_state[0])):
    indexmap_state[jdata_state[0][d]] = d


# Make dictionary to map data. Need to map state and county
data_county = {}
for el in jdata_county[1:]:
    data_county[el[indexmap_county["state"]] + el[indexmap_county["county"]]] = el

data_state = {}
for el in jdata_state[1:]:
    data_state[el[indexmap_state["state"]]] = el


# Load geographic data
geo_county = json.load(open("gz_2010_us_050_00_20m.json","r"), encoding = "latin-1")
geo_state  = json.load(open("gz_2010_us_040_00_20m.json","r"), encoding = "latin-1")


# Generate network file to update everything

kml = simplekml.Kml()
clink = kml.newnetworklink(name = "Population data")
clink.link.href="http://127.0.0.1:20605/updateKml"
clink.link.refreshmode = "onInterval"
clink.link.refreshinterval = 2
kml.save("skml_16_server_updates_ui.kml")

    

np = 0
nf = 0


statecounties = {}

# Generate data for states
for state in geo_state["features"]:
    statecounties[state["properties"]["STATE"]] = (state["properties"]["NAME"], [])
  
# Create data for counties
for county in geo_county["features"]:
   
    # Which state do we need to add this to?
    st = county["properties"]["STATE"]

    statecounties[st][1].append(county)


# Create dummy kml for null update
nup = simplekml.Kml()
nup.document = None
nup.networklinkcontrol.minrefreshperiod = 1
nup.update = simplekml.Update()

nupstring = nup.kml(False)  

 
class Counties(object):

    def __init__(self):
        self._scale = 0
        self._data_mode = "MaleFemale"
        
        self._need_state_updates = {}
        for st in statecounties.keys():
            self._need_state_updates[st] = True
        self.needUpdate()
        

    def needUpdate(self):
        self._need_update = True
        for st in statecounties.keys():
            self._need_state_updates[st] = True
    
    
    def mapData(self, data, indexmap):
    
        if self._data_mode == "MaleFemale":  
            npeople  = int(data[indexmap["P0120001"]])
            nmales   = int(data[indexmap["P0120002"]])
            nfemales = npeople - nmales
            
            description = "%d male, %d female (dif: %d, %.2f%%)" % (nmales, nfemales, nfemales - nmales, (nfemales - nmales) * 100. / (nfemales + nmales)) 

            dif = nmales - nfemales
            fac = max(-1., min(dif * 10. / npeople, 1.))
            ##col = "a0%02x00%02x" % ((128 + 127 * fac), (128 - 127 * fac))
            col = "a0%02x00%02x"
       
            val = nmales / 3000
            
        elif self._data_mode == "Population":
        
            npeople  = int(data[indexmap["P0120001"]])
            
            description = "%d people" % (npeople) 
            col = "a000%02x00" % (min(npeople / 2000, 255))
            val = npeople / 3000
            
        else:
            print("*** Unknown mode %s!" % self._data_mode)            
            
        return val, col, description
 
    
    
    @cherrypy.expose
    def updateUI(self, *args, **kwargs):
        print("updateUI: args=%s kwargs=%s" % (args, kwargs))
         
        if "scale_slider" in kwargs:
            self._scale = int(kwargs["scale_slider"])
            self.needUpdate()
     
        if "data_mode" in kwargs:
            self._data_mode = kwargs["data_mode"]
            self.needUpdate()
    
    
    
    def addZ(self, coords, z):    
        out = []
        
        for c in coords:
            out.append([c[0], c[1], z])
        
        return out
    
    
     
    @cherrypy.expose
    def updateKml(self, *args, **kwargs):
        print("updateKml: args=%s kwargs=%s" % (args, kwargs))
        
        if not self._need_update:
            print("No update needed...")
            return nupstring
        
        
        print("Update needed, regenerating...")
        
 
        kml = simplekml.Kml()
        
        pnt = kml.newpoint(name="Machu Picchu, Peru")
        ##pnt.coordinates = simplekml.Coordinates(-72.516244)
        pnt.lookat = simplekml.LookAt(gxaltitudemode=simplekml.GxAltitudeMode.relativetoseafloor,
                              latitude=-13.209676, longitude=-72.503364, altitude=0.0,
                              range=14794.882995, heading=71.131493, tilt=66.768762)
                              
        # Generate data for states
        for state in geo_state["features"]:
 
            val, col, desc = self.mapData(data_state[state["properties"]["STATE"]], indexmap_state)
            
            fold = kml.newfolder(name = state["properties"]["NAME"])
            
            geo = fold.newmultigeometry()

            geo.name = state["properties"]["NAME"]

            box = simplekml.LatLonBox(north=-1000, south=1000, west=1000, east=-1000)

            if state["geometry"]["type"] == "Polygon":
                p = geo.newpolygon()
                p.altitudemode = "relativeToGround"
                p.extrude=1
                p.outerboundaryis = self.addZ(state["geometry"]["coordinates"][0], (((self._scale * val)/1000)*2692)+308)
                update_box(box, state["geometry"]["coordinates"][0])
            else:     
                for poly in state["geometry"]["coordinates"]:
                    p = geo.newpolygon()
                    p.altitudemode = "relativeToGround"
                    p.extrude=1
                    p.outerboundaryis = self.addZ(poly[0], (((self._scale * val)/1000)*2692)+308)
                    update_box(box, poly[0])

            switchsize = 600
            fadesize = 100

            geo.region = simplekml.Region(box, simplekml.Lod(minlodpixels = 0, maxlodpixels = switchsize, minfadeextent = 0, maxfadeextent = fadesize))

            # Network link for counties
            clink = kml.newnetworklink(name = "Counties for %s" % geo.name)
            clink.region = simplekml.Region(box, simplekml.Lod(minlodpixels = switchsize - fadesize, maxlodpixels = -1, minfadeextent = fadesize, maxfadeextent = 0))
            clink.link.href="http://127.0.0.1:20605/state?state=%s" % state["properties"]["STATE"]
            clink.link.refreshmode = "onInterval"
            clink.link.refreshinterval = 2


            geo.style.polystyle.outline = 0

            # Map data to color
            geo.description = desc
            geo.style.polystyle.color = col

            geo = None


        stateskml = kml
        
        self._need_update = False        
        
        return stateskml.kml(False)
       
       

    @cherrypy.expose
    def state(self, state):
        name, counties = statecounties[state]
        print("** Get data for state %s's counties" % name)
        
        if not self._need_state_updates[state]:
            print("No update needed...")
            return nupstring
         
        print("Update needed, regenerating...")
       
        # Create new version of the state's counties
        kml = simplekml.Kml()
        
        for county in counties:
            ind = county["properties"]["STATE"] + county["properties"]["COUNTY"]
            val, col, desc = self.mapData(data_county[ind], indexmap_county)
                
            box = simplekml.LatLonBox(north=-1000, south=1000, west=1000, east=-1000)
            
            # Create multi geo to hold outline
            geo = kml.newmultigeometry()

            geo.name = county["properties"]["NAME"] + " - " + county["properties"]["COUNTY"]
            geo.description = geo.name
        
                        
            if county["geometry"]["type"] == "Polygon":
                p = geo.newpolygon()
                p.altitudemode = "relativeToGround"
                p.extrude=1
                #p.outerboundaryis = county["geometry"]["coordinates"][0]
                p.outerboundaryis = self.addZ(county["geometry"]["coordinates"][0], (((self._scale * val)/1000)*2692)+308)
            else:     
                for poly in county["geometry"]["coordinates"]:
                    p = geo.newpolygon()
                    p.altitudemode = "relativeToGround"
                    p.extrude=1
                    #p.outerboundaryis = poly[0]
                    p.outerboundaryis = self.addZ(poly[0], (((self._scale * val)/1000)*2692)+308)
 
            # Map data to color
            
            
            
 
            geo.description = desc   
            geo.style.polystyle.color = col
        
        
        self._need_state_updates[state] = False      
        
        return kml.kml(False)
      
        
    
    
print("Starting server for data...")

conf = {'global' :  {'server.thread_pool' : 4 },
        '/' :       {'tools.sessions.on': True,
                     'tools.sessions.storage_type': 'ram'},
        '/ui.html': {'tools.staticfile.on': True,
                     'tools.staticfile.filename': '%s/16_ui.html' % os.path.abspath(os.curdir)}
       }

cherrypy.quickstart(Counties(), config = conf)
